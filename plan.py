#!/usr/bin/env python3
"""Deterministic training plan from the event, the athlete's week, and the terrain.

    python plan.py --profile profile.json [--terrain out/terrain.csv] --out plan.json

No model decides anything here: every number comes from one of the rules below,
and every rule names its source. The same inputs always give the same plan.

Rules used (see references/sport-science.md):
  R1  Polarised distribution: ~80% of time easy, ~20% hard (Seiler 2010).
  R2  Weekly volume rises by at most 10% and never above 1.2x the stated week.
  R3  Taper is 3 weeks, volume -20/-40/-60%, one intensity touch per week kept
      (Mujika & Padilla 2003).
  R4  Long run is 25-35% of the week and stops 3 weeks out.
  R5  Vertical ramps toward the race's own m/km; it is the specificity lever.
  R6  A weakness found in terrain.csv gets one dedicated session per week until
      the last build week.
"""
import argparse, datetime as dt, json, os, sys

PACE_FACTORS = {  # share of the week; sums to 1.0 across the non-rest days
    "long": 0.30, "quality": 0.20, "easy1": 0.17, "easy2": 0.17,
    "easy3": 0.11, "short": 0.05,
}


DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

PHASE_ZH = {"build": "建量期", "peak": "高峰期", "taper": "減量期", "race": "比賽週"}

GLOSSARY = [
    ("累積爬升", "全程向上爬的總高度，英文寫 D+。數字越大，整條路越辛苦。"),
    ("爬升密度", "每公里平均要爬多少米。HK100 是 54 米／公里，即每公里爬升約 54 米。"),
    ("心率區 Z1–Z5", "Z1 可以講電話；Z2 只可以講短句；Z3 講不到長句；"
                    "Z4 只講到單字；Z5 講不到話。"),
    ("強度課", "每週唯一一節刻意吃力的訓練，其餘時間都應該輕鬆。"),
    ("建量期／高峰期／減量期", "逐週加量 → 達到最高訓練量 → 賽前逐步減量讓身體恢復。"),
    ("80/20", "八成訓練時間輕鬆，兩成吃力。比例失衡是最常見的受傷原因。"),
    ("充碳", "賽前 2–3 日提高碳水攝取，讓肌肉儲備更多肝醣。"),
]


def schedule(prof):
    """Which days can hold a session, and how long a weekday session may be.

    Deterministic from what the athlete told us: work days are unavailable in
    daylight, so the long run goes on the first non-work day and the quality
    session on a work day, capped to the evening window.
    """
    sched = prof.get("schedule") or {}
    work = sched.get("work_days") or [1, 2, 3, 4, 5]
    work0 = [d - 1 for d in work]
    free = [d for d in range(7) if d not in work0]
    long_day = sched.get("long_day")
    long_idx = DAY_NAMES.index(long_day) if long_day in DAY_NAMES else (free[0] if free else 5)
    quality_pool = [d for d in work0] or [0]
    quality_idx = quality_pool[len(quality_pool) // 2]
    cap = int(sched.get("weekday_max_minutes") or 75)
    requested = sched.get("days_per_week") or sched.get("days")
    if requested:
        days = [d - 1 for d in requested] if isinstance(requested, list) else []
        n = len(days) if days else int(requested)
    else:
        n = 7 - 0                                   # all free days plus weekday evenings
        days = []
    n = max(1, min(7, n))
    return dict(work=work0, free=free, long_idx=long_idx, quality_idx=quality_idx,
                weekday_cap=cap, days_per_week=n, fixed_days=days)


def strength_cfg(prof):
    """Two short strength sessions a week by default once the athlete confirms it.

    R7: heavy/compound strength improves running economy and is not optional for
    an ultra build (Beattie 2017; Ronnestad & Mujika 2014) — but it must not sit
    next to the quality session or the long run, because of the interference
    effect.
    """
    cfg = prof.get("strength") or {}
    if cfg.get("enabled") is False or cfg.get("sessions", 0) == 0:
        return None
    return dict(sessions=int(cfg.get("sessions", 2)),
                minutes=int(cfg.get("minutes", 30)),
                focus=cfg.get("focus", "下肢複合動作＋核心"))


def health_gate(prof):
    """Any declared condition or current pain stops intensity prescription."""
    h = prof.get("health") or {}
    flags = [x for x in (h.get("conditions") or []) if x]
    if h.get("current_pain"):
        flags.append(str(h["current_pain"]))
    if not flags:
        return None
    return ("先諮詢醫生／物理治療師，再執行任何強度課。本計劃暫時只保留 Z1–Z2："
            + "、".join(flags))


def weeks_to(event_date, today=None):
    today = today or dt.date.today()
    days = (event_date - today).days
    return max(1, -(-days // 7)), days


def phase(weeks_out, total_weeks):
    if weeks_out <= 1:
        return "race"
    if weeks_out <= 3:
        return "taper"
    if weeks_out <= max(4, round(total_weeks * 0.45)):
        return "peak"
    return "build"


def weakness_sessions(terrain_rows):
    """Turn the CSV into one readable weakness, or none. Never invent one.

    Ranked by SECONDS LOST, not by how many bins: one 25-second descent bin
    matters more than five 2-second uphill ones.
    """
    if not terrain_rows:
        return []
    slow = [r for r in terrain_rows if r.get("class_") == "slow"]
    if len(slow) < 5:
        return []
    down = [r for r in slow if float(r["grade_pct"]) < -3]
    up = [r for r in slow if float(r["grade_pct"]) > 3]
    down_lost = sum(r["delta_s"] for r in down)
    up_lost = sum(r["delta_s"] for r in up)
    if down_lost >= up_lost and down:
        mid = sorted(down, key=lambda r: -r["delta_s"])[0]["chainage_m"]
        return [dict(kind="descent", lost_s=down_lost, bins=len(down), at_m=mid,
                     action="6 次 200 米下坡重複；短步幅、快步頻、輕著地",
                     why=f"上次有 {len(down)} 段落坡較模型慢，合共慢 {down_lost} 秒，"
                         f"最慢一段在 {mid / 1000:.1f} 公里")]
    if up:
        mid = sorted(up, key=lambda r: -r["delta_s"])[0]["chainage_m"]
        return [dict(kind="climb", lost_s=up_lost, bins=len(up), at_m=mid,
                     action="6 次 3 分鐘爬坡；全程可持續功率，不要在坡底衝刺",
                     why=f"上次有 {len(up)} 段上坡較模型慢，合共慢 {up_lost} 秒，"
                         f"最慢一段在 {mid / 1000:.1f} 公里")]
    return []


def week_hours(base, weeks_out, total_weeks):
    """R2 + R3: start at the athlete's own week, +10%/week capped at 1.2x, then taper.

    Starts AT base, never below: assuming the athlete can be pushed down to 70%
    of what they already do has no basis.
    """
    peak = base * 1.2
    if weeks_out == 1:
        return round(base * 0.35, 1)          # race week: two short runs, not a block
    if weeks_out <= 3:
        return round(peak * {3: 0.80, 2: 0.60}[weeks_out], 1)
    index = total_weeks - weeks_out           # weeks completed before this one
    return round(min(peak, base * (1 + 0.10 * index)), 1)


def session_days(sch):
    """Which days actually get a session, in priority order.

    Long run first (it needs the most time), then the intensity session, then the
    remaining days the athlete offered. If they can only train twice, they get two.
    """
    n = sch["days_per_week"]
    if sch.get("fixed_days"):
        pool = list(sch["fixed_days"])
        pool.sort(key=lambda d: (d != sch["long_idx"], d != sch["quality_idx"]))
    else:
        pool = [sch["long_idx"], sch["quality_idx"]]
        rest = [d for d in range(7) if d not in pool]
        # spread the remaining days out rather than stacking them together
        pool += rest[::2] + rest[1::2]
    seen, out = set(), []
    for d in pool:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out[:n]


def training_sessions(prof, sch, hours, km, density, weak, gate, cur_long,
                      progress=0.0, phase="build"):
    """Split the week across the days the athlete actually has.

    Taper is not "the same week with fewer minutes" — the number of sessions
    drops too, otherwise the athlete is still on their feet seven days a week
    (Mujika & Padilla 2003: cut volume 40-60%, keep some intensity).
    """
    days = session_days(sch)
    if phase == "taper":
        days = days[:min(len(days), 4)]
    total = hours * 60
    out = []

    long_min = int(total * 0.30)
    long_min = min(long_min, int(cur_long * 60 * 1.1)) if cur_long else long_min
    long_min = max(long_min, sch["weekday_cap"] + 15)
    out.append(dict(day=DAY_NAMES[days[0]], type="long trail", minutes=long_min,
                    vert_m=int(km * density * 0.4), zone="Z1-Z2",
                    note="本週最重要一課：長距離＋爬升，排在最有空的一日"))

    if len(days) == 1:
        return out

    qual_min = min(int(total * 0.20), sch["weekday_cap"])
    if phase == "taper":
        qual_min = int(qual_min * 0.7)
    if gate:
        out.append(dict(day=DAY_NAMES[days[1]], type="easy", minutes=qual_min,
                        vert_m=int(qual_min * 3), zone="Z1-Z2",
                        note="強度課暫停：" + gate))
    else:
        kind = weak[0]["kind"] if weak else "climb"
        note = weak[0]["action"] if weak else "提升上坡效率"
        hill = (prof.get("training_hills") or [None])[0]
        if hill:
            note += f"；場地：{hill}"
        out.append(dict(day=DAY_NAMES[days[1]],
                        type="hill repeats" if kind == "climb" else "descent technique",
                        minutes=qual_min, vert_m=int(qual_min * 8), zone="Z3-Z4", note=note))

    easy_days = days[2:]
    if easy_days:
        spare = max(0, total - long_min - qual_min)
        per = min(int(spare / len(easy_days)), sch["weekday_cap"])
        for d in easy_days:
            out.append(dict(day=DAY_NAMES[d], type="easy", minutes=per,
                            vert_m=int(per * 3), zone="Z1-Z2", note="輕鬆，能說話的強度"))
    return out


def build(prof, terrain_rows, today=None):
    event = dt.date.fromisoformat(prof["event_date"])
    total_weeks, days = weeks_to(event, today)
    base = float(prof["weekly_hours"])
    race_density = (prof["d_plus_m"] / prof["distance_km"]) if prof.get("d_plus_m") else 40.0
    weak = weakness_sessions(terrain_rows)
    cur = prof.get("current") or {}
    cur_long = float(cur.get("longest_run_h") or 0)
    cur_km = float(cur.get("weekly_km") or 0)
    projected = float(cur.get("projected_hours") or 0)
    target = float(prof.get("target_hours") or 0)
    sch = schedule(prof)
    gate = health_gate(prof)

    weeks = []
    for w in range(total_weeks, 0, -1):
        ph = phase(w, total_weeks)
        hours = week_hours(base, w, total_weeks)
        # R5: vertical ramps with the phase, capped by what fits in the week
        density = min(race_density, race_density * (0.55 + 0.45 * (1 - w / total_weeks)) + 5)
        if ph == "taper":
            density *= 0.6
        if ph == "race":
            density *= 0.3
        km = max(10.0, hours * 7.0)      # ~7 km/h trail average, stated as an assumption
        sessions = []
        if ph == "race":
            sessions = [
                dict(day=DAY_NAMES[sch["quality_idx"]], type="easy", minutes=30, vert_m=50,
                     zone="Z1-Z2", note="喚醒雙腿，不追求表現"),
                dict(day=DAY_NAMES[(sch["quality_idx"] + 2) % 7], type="easy", minutes=20,
                     vert_m=0, zone="Z1", note="短而輕鬆，賽前兩日完全休息"),
                dict(day=DAY_NAMES[sch["long_idx"]], type="race",
                     minutes=int(prof.get("target_hours", 16) * 60),
                     vert_m=prof.get("d_plus_m", 0), zone="race", note="比賽日"),
            ]
        else:
            sessions = training_sessions(prof, sch, hours, km, density, weak, gate,
                                         cur_long, progress=(total_weeks - w) / max(1, total_weeks),
                                         phase=ph)

        st = strength_cfg(prof)
        if st and ph != "race":
            # place strength on easy days, never adjacent to quality or long
            # only the day BEFORE a key session is off-limits (interference is
            # worst when strength precedes quality); the day after is fine
            blocked = {(sch["quality_idx"] - 1) % 7, sch["quality_idx"],
                       (sch["long_idx"] - 1) % 7, sch["long_idx"]}
            candidates = [d for d in range(7) if d not in blocked and d not in sch["work"][:2]]
            # a 2-day athlete cannot add two more days of lifting; scale it down
            n_st = min(st["sessions"], max(0, sch["days_per_week"] - 2))
            if ph == "taper":
                n_st = min(n_st, 1)
            if ph == "race" or w <= 1:
                n_st = 0
            for d in candidates[:n_st]:
                sessions.append(dict(day=DAY_NAMES[d], type="strength",
                                     minutes=st["minutes"], vert_m=0, zone="肌力",
                                     note=st["focus"] + "；與跑步相隔 6 小時以上"))

        if cur_km:
            km = min(km, cur_km * 1.1 * (1 + 0.05 * (total_weeks - w)))

        hard = sum(s["minutes"] for s in sessions if s["zone"] in ("Z3-Z4", "Z5"))
        run_min = sum(s["minutes"] for s in sessions
                      if s["zone"] not in ("肌力", "race")) or 1
        # the schedule can be tighter than the model: report what is actually runnable
        actual = round(sum(s["minutes"] for s in sessions if s["zone"] != "race") / 60, 1)
        race_h = round(sum(s["minutes"] for s in sessions if s["zone"] == "race") / 60, 1)
        long_runs = [s["minutes"] for s in sessions if s["type"] == "long trail"]

        weeks.append(dict(
            week_from_today=w, phase=ph, hours=actual, hours_planned=hours,
            shortfall_pct=round((hours - actual) / hours * 100) if hours else 0,
            race_h=race_h,
            strength_min=sum(s["minutes"] for s in sessions if s["zone"] == "肌力"),
            race_line=(f"比賽 {prof.get('distance_km', 0)} km · 累積爬升 {prof.get('d_plus_m', 0)} m · "
                       f"賽前激活 {actual} 小時（不計比賽）") if ph == "race" else "",
            km_target=round(prof.get("distance_km", km) if ph == "race"
                            else km * (actual / hours if hours else 1), 1),
            vert_target_m=round(prof.get("d_plus_m", 0) if ph == "race" else km * density),
            hard_share=round(hard / run_min * 100),
            long_run_h=round((long_runs[0] if long_runs else 0) / 60, 1),
            sessions=sorted(sessions, key=lambda x: DAY_NAMES.index(x["day"]))))
    return dict(
        event=prof.get("event"), event_date=prof["event_date"], days=days,
        weeks=total_weeks, weekly_hours_base=base, race_density=round(race_density),
        weakness=weak, health_gate=gate, schedule=sch,
        current=dict(longest_run_h=cur_long or None, weekly_km=cur_km or None,
                     projected_hours=projected or None),
        feasibility=(("模型預測 %.1f 小時，目標 %.1f 小時：目標較預測%s %.1f 小時。"
                      % (projected, target, "快" if target < projected else "慢",
                         abs(target - projected))) if projected and target else None),
        notes=[f"training days per week: {sch['days_per_week']}",
               f"work days: {[DAY_NAMES[d] for d in sch['work']]}, weekday cap {sch['weekday_cap']} min",
               f"long run on {DAY_NAMES[sch['long_idx']]}, quality on {DAY_NAMES[sch['quality_idx']]}"],
        rules=["R1 Seiler 2010", "R2 <=10%/week", "R3 Mujika 2003",
                              "R4 long run 25-35%", "R5 vertical specificity",
                              "R6 weakness session"],
        plan=weeks)


DAY_ZH = {"Mon": "週一", "Tue": "週二", "Wed": "週三", "Thu": "週四",
          "Fri": "週五", "Sat": "週六", "Sun": "週日"}
TYPE_ZH = {"easy": "輕鬆跑", "hill repeats": "上坡重複", "descent technique": "落坡技術",
           "long trail": "長距離越野", "strength": "肌力", "race": "比賽"}


def render_html(plan, prof, base_dir="."):
    """Printable A4 plan: cover + one page per week. Every number comes from plan."""
    def esc(x):
        return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    warn = []
    if plan.get("health_gate"):
        warn.append(("醫療", plan["health_gate"]))
    hi = [w for w in plan["plan"] if w["phase"] in ("build", "peak") and w["hard_share"] > 22]
    if hi:
        warn.append(("強度比例", f"{len(hi)} 個星期吃力時間超過兩成（最高 "
                                 f"{max(w['hard_share'] for w in hi)}%）；80/20 是上限，不是下限。"))
    flat = [w for w in plan["plan"] if w["phase"] in ("build", "peak") and w["hard_share"] < 5]
    if flat:
        warn.append(("強度比例", f"{len(flat)} 個星期完全冇強度刺激；超馬可以偏低，但建議保留一節短強度。"))
    if plan.get("weakness"):
        warn.append(("訓練重點依據", plan["weakness"][0]["why"]))
    longest = max(w["long_run_h"] for w in plan["plan"])
    if prof.get("target_hours") and longest < 5:
        warn.append(("長課", f"最長一課 {longest} 小時，為目標時間的 "
                            f"{longest / prof['target_hours'] * 100:.0f}%；提高週量或接受差距。"))

    rows = []
    for w in plan["plan"]:
        cells = "".join(
            f"<tr><td>{esc(DAY_ZH.get(s['day'], s['day']))}</td><td>{esc(TYPE_ZH.get(s['type'], s['type']))}</td>"
            f"<td class='n'>{s['minutes']}</td><td class='n'>{s['vert_m']}</td>"
            f"<td>{esc(s['zone'])}</td><td class='note'>{esc(s['note'])}</td></tr>"
            for s in w["sessions"])
        rows.append(f"""
<section class="week">
  <h2>第 {plan['weeks'] - w['week_from_today'] + 1} 週　<span class="phase">{PHASE_ZH.get(w['phase'], w['phase'])}</span></h2>
  <p class="meta">{w['race_line'] or (f"跑步 {round(w['hours'] - w['strength_min'] / 60, 1)} 小時"
    + (f" ＋ 肌力 {w['strength_min']} 分鐘" if w['strength_min'] else "")
    + f" · {w['km_target']} km · 累積爬升 {w['vert_target_m']} m · 吃力時間佔 {w['hard_share']}%")}</p>
  <table>
    <thead><tr><th>日</th><th>內容</th><th>分鐘</th><th>爬升 (m)</th><th>心率區</th><th>備註</th></tr></thead>
    <tbody>{cells}</tbody>
  </table>
</section>""")

    warn_html = "".join(f"<li><b>{esc(k)}</b>：{esc(v)}</li>" for k, v in warn) or "<li>無</li>"
    gloss_html = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in GLOSSARY)

    nut = ""
    if prof.get("weight_kg") and prof.get("target_hours"):
        import nutrition
        t = nutrition.targets(prof["weight_kg"], prof["target_hours"])

        def carb_cell(g):
            val = "–".join(str(x) for x in g) if isinstance(g, tuple) else str(g)
            return f"{val} g"

        nrows = "".join(
            f"<tr><td>{esc(r['day'])}</td><td class='n'>{carb_cell(r['carbs_g'])}</td>"
            f"<td class='note'>{esc(r['note'])}</td></tr>"
            for r in nutrition.race_week(t, prof["target_hours"]))
        nut = f"""
<section class="week">
  <h2>比賽飲食 <span class="phase">Thomas et al. 2016</span></h2>
  <p class="meta">體重 {t['weight_kg']:g} kg · 每日碳水：輕鬆日 {t['carb_easy_g']} g／
     高強度日 {t['carb_quality_g']} g／充碳 {t['carb_load_g']} g ·
     蛋白質 {t['protein_g'][0]}–{t['protein_g'][1]} g／日</p>
  <table>
    <thead><tr><th>時間</th><th>碳水</th><th>做法</th></tr></thead>
    <tbody>{nrows}</tbody>
  </table>
  <p class="meta">比賽中水分 {t['fluid_ml_h'][0]}–{t['fluid_ml_h'][1]} ml/h、鈉
     {t['sodium_mg_h'][0]}–{t['sodium_mg_h'][1]} mg/h — 依個人流汗率調整，並非固定值。
     此頁為指引換算，非個人化建議，亦非醫療建議。</p>
</section>"""

    st_html = ""
    scfg = prof.get("strength") or {}
    if scfg.get("enabled", True):
        import strength
        eq = scfg.get("equipment", "gym")
        import assets as _assets
        cards = ""
        for title, exs in strength.sessions(eq):
            def media(k):
                pics = _assets.photo_paths(k)
                if pics:
                    rel = [os.path.relpath(x, os.path.abspath(base_dir)) for x in pics]
                    return ("<span class='pics'>"
                            + "".join(f"<img src='{esc(r)}' alt=''/>" for r in rel)
                            + "</span>")
                return strength._fig(k)

            items = "".join(
                f"<div class='ex'>{media(k)}"
                f"<div><b>{esc(n)}</b><span>{esc(c)}</span></div></div>"
                for n, c, k in exs)
            cards += f"<h3>{esc(title)}</h3><div class='grid'>{items}</div>"
        prog = "".join(f"<tr><td>{esc(h)}</td><td class='note'>{esc(d)}</td></tr>"
                       for h, d in strength.BLOCKS)
        st_html = f"""
<section class="week">
  <h2>肌力訓練　<span class="phase">每週 2 節 · 每節 30 分鐘</span></h2>
  <p class="meta">排在輕鬆跑之後或另一日；與強度課、長課至少相隔 6 小時。
     減量期減至每週 1 節；比賽前一週不做重量。</p>
  {cards}
  <h3>進度</h3>
  <table class="kv"><thead><tr><th>階段</th><th>做法</th></tr></thead><tbody>{prog}</tbody></table>
  <h3>場地與器材</h3>
  <table class="kv"><tbody>
    <tr><td>健身室</td><td class="note">槓鈴或壺鈴、深蹲架、踏板／箱。質量比重量重要。</td></tr>
    <tr><td>家中</td><td class="note">阻力帶（約 HK$80–150）、一張穩固椅子、牆。</td></tr>
    <tr><td>戶外</td><td class="note">樓梯、公園長椅、單槓；提踵與上台階用樓梯已足夠。</td></tr>
  </tbody></table>
  <p class="meta">示範照片：free-exercise-db（Unlicense / public domain）。每組兩張為開始與結束位置。
     姿勢有疑問請找合資格教練。</p>
</section>"""

    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<title>{esc(plan['event'])} 訓練計劃</title>
<style>
 @page {{ size: A4; margin: 14mm 14mm 16mm; }}
 body {{ font-family: "Noto Sans TC", system-ui, sans-serif; color: #12161C; font-size: 11pt; }}
 .cover {{ margin-bottom: 8mm;
           -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
 h1 {{ font-size: 24pt; margin: 8px 0 5px; letter-spacing: -.01em; color: #12161C; }}
 .brand {{ letter-spacing: .26em; font-size: 8pt; color: #5C6470; text-transform: uppercase;
           display: flex; align-items: center; gap: 8px; }}
 .brand::before {{ content: ""; width: 22px; height: 3px; background: #E8590C; }}
 .sub {{ color: #5C6470; margin: 0 0 4px; font-size: 9.5pt; }}
 .warn {{ background: #FBF4E4; border-left: 3px solid #B3261E; padding: 8px 12px; margin: 14px 0; }}
 .warn li {{ margin: 3px 0; }}
 .gloss {{ margin: 12px 0 0; font-size: 9pt; color: #333; }}
 .gloss dt {{ font-weight: 600; margin-top: 4px; }}
 .gloss dd {{ margin: 0 0 0 0; color: #555; }}
 .week {{ page-break-before: always; }}
 h2 {{ font-size: 13pt; margin: 0 0 2px; }}
 .phase {{ font-size: 8pt; color: #C2410C; background: #FDF0E8; border: 1px solid #E8590C;
           padding: 1px 7px; border-radius: 2px; vertical-align: middle;
           letter-spacing: .08em; font-weight: 600; }}
 .meta {{ color: #555; font-size: 9.5pt; margin: 0 0 8px; }}
 table {{ width: 100%; border-collapse: collapse; font-size: 9.5pt; }}
 th, td {{ border-bottom: 1px solid #e2e2e2; padding: 5px 6px; text-align: left; }}
 th {{ white-space: nowrap; font-weight: 650; font-size: 8pt; letter-spacing: .10em; text-transform: uppercase;
       color: #5C6470; border-bottom: 1px solid #0C0F14; background: none; }}
 td.n {{ text-align: right; font-variant-numeric: tabular-nums; }}
 td.note {{ color: #444; }}
 td.n, th:nth-child(2) {{ white-space: nowrap; }}
 .kv td:first-child {{ width: 24%; white-space: nowrap; }}
 .week td:nth-child(1), .week th:nth-child(1) {{ width: 9%; white-space: nowrap; }}
 .week td:nth-child(2), .week th:nth-child(2) {{ width: 15%; }}
 .week td:nth-child(3), .week th:nth-child(3) {{ width: 8%; }}
 .week td:nth-child(4), .week th:nth-child(4) {{ width: 9%; }}
 .week td:nth-child(5), .week th:nth-child(5) {{ width: 9%; }}
 .week td:nth-child(6) {{ font-size: 9pt; line-height: 1.45; }}
 .grid {{ display: flex; flex-wrap: wrap; gap: 10px 18px; margin: 4px 0 10px; }}
 .ex {{ display: flex; gap: 8px; width: 47%; align-items: center; }}
 .ex b {{ display: block; font-size: 10pt; }}
 .pics img {{ width: 66px; height: 88px; object-fit: cover; border-radius: 2px; margin-right: 2px; }}
 .ex span {{ display: block; font-size: 8.5pt; color: #555; }}
 h3 {{ font-size: 11pt; margin: 12px 0 4px; }}
 th:nth-child(2), td:nth-child(2) {{ width: 15%; }}
 footer {{ margin-top: 10px; font-size: 8pt; color: #777; }}
</style></head><body>
<div class="cover">
<div class="brand">Running Analyst</div>
<h1>{esc(plan['event'] or '訓練計劃')}</h1>
<p class="sub">{esc(plan['event_date'])} · 距離比賽 {plan['days']} 日 · {plan['weeks']} 週 ·
每週跑步基準 {plan['weekly_hours_base']:g} 小時 · 賽事爬升密度 {plan['race_density']} m/km</p>
</div>
<div class="warn"><b>注意</b><ul>{warn_html}</ul></div>
<div class="gloss"><b>名詞解釋</b><dl>{gloss_html}</dl></div>
{''.join(rows)}
{nut}
{st_html}
<footer>規則：Seiler 2010（80/20）· Mujika &amp; Padilla 2003（減量）· 週量每週增幅上限 10% ·
本計劃由 Running Analyst 依你的輸入計算，僅供訓練參考，不構成醫療建議。如有痛症請停止並諮詢醫生。</footer>
</body></html>"""


def export_pdf(plan, prof, out_pdf):
    """HTML -> PDF via headless Chromium (already on this machine; no new dependency)."""
    import os, subprocess, tempfile
    html = render_html(plan, prof, os.path.dirname(os.path.abspath(out_pdf)))
    html_path = os.path.splitext(out_pdf)[0] + ".html"
    open(html_path, "w").write(html)
    chrome = next((c for c in ("chromium-browser", "chromium", "google-chrome")
                   if any(os.access(os.path.join(p, c), os.X_OK)
                          for p in os.environ.get("PATH", "").split(os.pathsep))), None)
    if not chrome:
        raise SystemExit("no Chromium found — the printable HTML was written to " + html_path)
    subprocess.run([chrome, "--headless", "--disable-gpu", "--no-sandbox",
                    "--no-pdf-header-footer", f"--print-to-pdf={out_pdf}",
                    "file://" + os.path.abspath(html_path)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return html_path, out_pdf


def export_icu(plan, outdir, lthr=None):
    """Intervals.icu workout-builder text, one file per session.

    intervals.icu pushes planned workouts to Garmin, COROS, Suunto and Wahoo, so
    one text format replaces four brand integrations. Targets use LTHR when the
    profile has it, otherwise the platform's own HR zones.
    """
    import os
    os.makedirs(outdir, exist_ok=True)
    easy = "Z2 HR" if not lthr else "68-78% LTHR"
    hard = "Z4 HR" if not lthr else "88-92% LTHR"
    recover = "Z1 HR" if not lthr else "60-70% LTHR"
    written = 0
    for w in plan["plan"]:
        for s in w["sessions"]:
            if s["type"] == "race":
                continue
            mins = s["minutes"]
            if s["type"] == "easy":
                body = (f"Warmup\n- 10m {easy}\n"
                        f"Main\n- {mins - 10}m {easy}\n")
            elif s["type"] == "long trail":
                warm = max(10, int(mins * 0.1))
                body = (f"Warmup\n- {warm}m ramp 60-75% LTHR\n"
                        f"Main\n- {mins - warm}m {easy}\n")
            else:
                warm = max(10, int(mins * 0.15))
                cool = max(5, int(mins * 0.10))
                main = mins - warm - cool
                reps = max(3, round(main / 8))
                work = max(2, round(main / reps * 0.75))
                rest = max(1, round(main / reps) - work)
                cool = mins - warm - reps * (work + rest)   # absorb the rounding here
                body = (f"Warmup\n- {warm}m ramp 60-75% LTHR\n"
                        f"Main Set {reps}x\n- {work}m {hard}\n- {rest}m {recover}\n"
                        f"Cooldown\n- {cool}m {recover}\n")
            name = f"W{w['week_from_today']:02d}-{s['day']}-{s['type'].replace(' ', '_')}.txt"
            with open(os.path.join(outdir, name), "w") as fh:
                fh.write(f"# {plan['event']} W{w['week_from_today']} {s['day']} "
                         f"{s['type']} — {mins} min, climb {s['vert_m']} m\n{body}")
            written += 1
    with open(os.path.join(outdir, "README.txt"), "w") as fh:
        fh.write(
            "Import: intervals.icu -> Library -> Workouts -> Add Workout -> paste one file, "
            "or use its workout import, then put it on the calendar.\n"
            "Sync: intervals.icu -> Settings -> Connections -> authorise Garmin / COROS / "
            "Suunto / Wahoo; planned workouts then appear on the watch.\n"
            "Targets are LTHR percentages when profile.lthr is set, otherwise device zones.\n")
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--terrain")
    ap.add_argument("--out")
    ap.add_argument("--today")
    ap.add_argument("--format", choices=["json", "icu", "pdf", "html"], default="json")
    ap.add_argument("--outdir", help="for --format icu: folder of workout text files")
    ap.add_argument("--pdf", help="write a printable PDF here")
    a = ap.parse_args()

    prof = json.load(open(a.profile))
    rows = []
    if a.terrain:
        import csv
        rows = list(csv.DictReader(open(a.terrain)))
        for r in rows:
            r["delta_s"] = int(float(r["delta_s"]))
            r["chainage_m"] = int(float(r["chainage_m"]))

    today = dt.date.fromisoformat(a.today) if a.today else None
    plan = build(prof, rows, today)
    if a.out:
        json.dump(plan, open(a.out, "w"), indent=2, ensure_ascii=False)
    if a.format in ("pdf", "html") or a.pdf:
        target = a.pdf or (a.outdir or "out/plan") + ".pdf"
        if a.format == "html":
            hp = os.path.splitext(target)[0] + ".html"
            open(hp, "w").write(render_html(plan, prof, os.path.dirname(os.path.abspath(hp))))
            print(f"wrote {os.path.splitext(target)[0] + '.html'}")
        else:
            html_path, pdf_path = export_pdf(plan, prof, target)
            print(f"wrote {pdf_path}  (source {html_path})")
    if a.format == "icu":
        n = export_icu(plan, a.outdir or "out/icu", prof.get("lthr"))
        print(f"wrote {n} workout files -> {a.outdir or 'out/icu'}")

    # 80/20 is a ceiling on hard work, not a target to hit; only flag the other side
    hi_hard = [x for x in plan["plan"] if x["phase"] in ("build", "peak") and x["hard_share"] > 22]
    if hi_hard:
        print(f"note: {len(hi_hard)} week(s) exceed 20% hard time "
              f"(max {max(x['hard_share'] for x in hi_hard)}%) — 80/20 is a ceiling")
    tight = [x for x in plan["plan"] if x["shortfall_pct"] > 10]
    if tight:
        print(f"note: {len(tight)} week(s) are tighter than planned "
              f"(weekday cap {plan['schedule']['weekday_cap']} min) — the schedule, not the plan, is the limit")
    w = plan["weakness"]
    print(f"{plan['event']}  {plan['event_date']}  {plan['days']} days / {plan['weeks']} weeks")
    print(f"base {plan['weekly_hours_base']} h/wk · race density {plan['race_density']} m/km")
    print(f"weakness: {w[0]['action'] if w else 'none found in terrain.csv'}")
    if w:
        print(f"  why: {w[0]['why']}")
    if plan.get("feasibility"):
        print(f"target vs prediction: {plan['feasibility']}")
    elif not plan["current"]["projected_hours"]:
        print("target vs prediction: no prediction supplied — analyse a run first, "
              "then set current.projected_hours")
    longest = max(x["long_run_h"] for x in plan["plan"])
    target = float(prof.get("target_hours") or 0)
    if target:
        print(f"longest run {longest} h = {longest / target * 100:.0f}% of the {target:g} h race "
              f"({plan['weekly_hours_base']} h/week allows no more)")
        need = 5.0 / PACE_FACTORS["long"]
        if longest < 5.0:
            print(f"  -> a 5 h long run at {PACE_FACTORS['long']:.0%} of the week needs ~{need:.0f} h/week, "
                  f"not {plan['weekly_hours_base']:g}; raise the week or accept the gap")
    print(f"\n{'wk':>3} {'phase':<6} {'h':>5} {'plan':>5} {'km':>6} {'D+':>6} {'hard%':>6}")
    for x in plan["plan"]:
        print(f"{x['week_from_today']:>3} {x['phase']:<6} {x['hours']:>5} "
              f"{x['hours_planned']:>5} {x['km_target']:>6} {x['vert_target_m']:>6} "
              f"{x['hard_share']:>5}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
