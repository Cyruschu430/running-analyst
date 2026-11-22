#!/usr/bin/env python3
"""One runnable check. Synthetic data in, known invariants out.

    python test_running_analyst.py

No framework, no fixtures — if the maths breaks, this fails.
"""
import datetime as dt
import sys

import nutrition
import plan
import strength
import report as core
import report_html as html

SEC = dt.timedelta(seconds=1)
T0 = dt.datetime(2026, 1, 1, 6, 0, 0)


def synthetic(n_km=10, speed=3.0, grade=0.0, hr=150):
    """Straight line at constant speed/grade, 1 Hz, 10 m per sample."""
    recs, d, alt = [], 0.0, 100.0
    step_m, step_t = speed, 1
    total = n_km * 1000
    i = 0
    while d <= total:
        recs.append((d, alt, speed, hr, 88, 170, T0 + dt.timedelta(seconds=i),
                     22.30 + d / 111000.0, 114.20 + d / 105000.0))
        d += step_m
        alt += step_m * grade
        i += step_t
    return recs


def test_flat_is_self_consistent():
    recs = synthetic()
    segs, table = html.km_segments(recs)
    assert len(segs) >= 9, f"expected ~10 km segments, got {len(segs)}"
    # the model is fitted on this same flat data, so every km must agree
    worst = max(abs(s["delta_s"]) for s in segs)
    assert worst <= 3, f"flat run should match model, worst delta {worst}s"
    assert len(table) >= 1, "grade table empty"
    return len(segs), worst


def synthetic_hilly(n_km=6):
    """1 km flat at 3.0 m/s, then 1 km at 10% and 2.2 m/s, alternating."""
    recs, d, alt, i = [], 0.0, 100.0, 0
    while d <= n_km * 1000:
        km = int(d // 1000)
        uphill = km % 2 == 1
        v = 2.2 if uphill else 3.0
        g = 0.10 if uphill else 0.0
        recs.append((d, alt, v, 150, 88, 170, T0 + dt.timedelta(seconds=i),
                     22.30 + d / 111000.0, 114.20 + d / 105000.0))
        d += v
        alt += v * g
        i += 1
    return recs


def test_uphill_is_slower():
    segs, _ = html.km_segments(synthetic_hilly())
    flat = [s for s in segs if s["d_plus"] == 0]
    up = [s for s in segs if s["d_plus"] > 50]
    assert flat and up, "need both flat and uphill km in the fixture"
    assert min(u["actual_s"] for u in up) > max(f["actual_s"] for f in flat), \
        "uphill km must take longer than flat km"
    return flat[0]["actual_s"], up[0]["actual_s"]


def test_route_geometry():
    recs = synthetic()
    gj = html.route_features(recs, html.km_segments(recs)[1])
    assert gj["features"], "no route segments produced"
    f = gj["features"][0]
    assert f["geometry"]["type"] == "LineString"
    assert 114 < f["geometry"]["coordinates"][0][0] < 115
    return len(gj["features"])


def synthetic_drift(n_km=6, hr_start=150, hr_end=170):
    """Constant speed, heart rate rising linearly — classic drift."""
    recs, d, alt, i, n = [], 0.0, 100.0, 0, n_km * 1000 / 3.0
    while d <= n_km * 1000:
        hr = hr_start + (hr_end - hr_start) * (d / (n_km * 1000))
        recs.append((d, alt, 3.0, round(hr), 88, 170, T0 + dt.timedelta(seconds=i),
                     22.30 + d / 111000.0, 114.20 + d / 105000.0))
        d += 3.0
        i += 1
    return recs


def test_decoupling_sign():
    """Positive must mean 'faded': same speed, higher HR."""
    val = core.decoupling(core.thirds(synthetic_drift()))
    assert val is not None and val > 5, f"HR drift at constant speed must read positive, got {val}"
    return val


def test_grade_is_distance_weighted():
    """Per-km grade must reflect the whole kilometre, not one boundary sample."""
    segs, _ = html.km_segments(synthetic_hilly())
    flat = [s for s in segs if s["d_plus"] == 0]
    up = [s for s in segs if s["d_plus"] > 50]
    assert flat and up
    assert abs(flat[0]["grade"]) < 0.01, f"flat km grade {flat[0]['grade']} should be ~0"
    assert up[0]["grade"] > 0.05, f"climb km grade {up[0]['grade']} should be ~0.10"
    return flat[0]["grade"], up[0]["grade"]


def test_decoupling_zero_on_constant():
    recs = synthetic()
    val = core.decoupling(core.thirds(recs))
    assert val is not None and abs(val) < 1.0, f"constant effort should not decouple, got {val}"
    return val


def test_gps_gap_creates_no_fake_km():
    """A 1.5 km dropout must not become a 0:00 kilometre or dump time into the next."""
    recs, d, i = [], 0.0, 0
    while d <= 5000:
        if 2000 <= d < 3500:
            d += 1500
            i += 1
            continue
        recs.append((d, 100.0, 3.0, 150, 88, 170, T0 + dt.timedelta(seconds=i),
                     22.30 + d / 111000.0, 114.20 + d / 105000.0))
        d += 3.0
        i += 1
    segs, _ = html.km_segments(recs)
    kms = [s["km"] for s in segs]
    assert 3 not in kms, f"dropout kilometre reported as data: {kms}"
    assert all(s["actual_s"] <= 400 for s in segs), "jump time leaked into a segment"
    return kms


def test_grade_window_is_distance_based():
    """Same slope at 1 m/s and 4 m/s must give the same grade estimate."""
    def climb(speed):
        recs, d, alt, i = [], 0.0, 100.0, 0
        while d <= 2000:
            recs.append((d, alt, speed, 150, 88, 170, T0 + dt.timedelta(seconds=i),
                         22.30 + d / 111000.0, 114.20 + d / 105000.0))
            d += speed
            alt += speed * 0.10
            i += 1
        return recs
    slow = core.grade_at(climb(1.0), 1000)
    fast = core.grade_at(climb(4.0), 250)
    assert abs(slow - 0.10) < 0.02 and abs(fast - 0.10) < 0.02, (slow, fast)
    return slow, fast


def test_warmup_excluded_from_decoupling():
    """A high-HR opening must not be read as decoupling."""
    recs = synthetic(8)
    out = []
    for x in recs:
        sec = (x[6] - T0).total_seconds()
        hr = 170 if sec < 300 else 150          # warm-up spike, then steady
        out.append(x[:3] + (hr,) + x[4:])
    val = core.decoupling(core.thirds(out))
    assert val is not None and abs(val) < 3, f"warm-up leaked into decoupling: {val}"
    return val


def test_projection_needs_three_bins(tmp="/tmp/_p.gpx"):
    """A two-bin curve cannot describe a course; refuse instead of guessing."""
    gpx = ('<?xml version="1.0"?><gpx xmlns="http://www.topografix.com/GPX/1/1">'
           '<trk><trkseg>'
           '<trkpt lat="22.30" lon="114.20"><ele>10</ele></trkpt>'
           '<trkpt lat="22.31" lon="114.20"><ele>60</ele></trkpt>'
           '<trkpt lat="22.32" lon="114.20"><ele>110</ele></trkpt>'
           '</trkseg></trk></gpx>')
    open(tmp, "w").write(gpx)
    two = [dict(grade=0.0, kmh=10.0), dict(grade=0.1, kmh=7.0)]
    three = two + [dict(grade=-0.1, kmh=11.0)]
    assert core.course_fit(two, tmp) is None, "projection accepted an under-determined curve"
    got = core.course_fit(three, tmp)
    assert got and got["course_km"] > 0, "projection failed with a usable curve"
    # a climbing course must take longer than the same distance at flat speed
    assert got["moving_h"] > got["course_km"] / 10.0, "uphill course projected at flat speed"
    return got["course_km"], got["moving_h"]


def test_target_density_uses_the_event():
    """HK100 is 5142 m over 96 km -> 53.6 m/km, not a generic 45."""
    t, basis = html.target_density({"goal": "ultra_trail", "distance_km": 96, "d_plus_m": 5142})
    assert abs(t - 53.6) < 0.1 and "賽事" in basis, (t, basis)
    t2, basis2 = html.target_density({"goal": "ultra_trail"})
    assert t2 == 45 and "慣例" in basis2, (t2, basis2)
    return round(t, 1), round(t2)


def test_map_agrees_with_km_table():
    """Route segments must carry the same time delta as the per-km table."""
    recs = synthetic_hilly(8)
    segs, table = html.km_segments(recs)
    gj = html.route_features(recs, table)
    km_total = sum(s["delta_s"] for s in segs)
    map_total = sum(f["properties"]["delta"] for f in gj["features"])
    assert abs(km_total - map_total) <= max(20, abs(km_total) * 0.2), (km_total, map_total)
    return round(km_total), round(map_total)


def test_course_stats_counts_the_climb(tmp="/tmp/_c.gpx"):
    """1 km at 10% must read ~100 m D+ and a full grade split."""
    pts = []
    for i in range(21):
        pts.append(f'<trkpt lat="{22.30 + i * 0.00045:.6f}" lon="114.20"><ele>{i * 5}</ele></trkpt>')
    open(tmp, "w").write('<?xml version="1.0"?><gpx xmlns="http://www.topografix.com/GPX/1/1">'
                         "<trk><trkseg>" + "".join(pts) + "</trkseg></trk></gpx>")
    c = core.course_stats(tmp)
    assert abs(c["course_d_plus"] - 100) < 12, c
    assert 0.9 < c["course_km"] < 1.1, c
    assert 95 <= sum(c["bands"].values()) <= 105, c["bands"]
    return c["course_km"], c["course_d_plus"], c["bands"]


def test_terrain_rows_add_up():
    """The CSV must explain the run: slow minus fast ~ net delta vs model."""
    recs = synthetic_hilly(8)
    table = core.grade_table(recs)
    rows = core.terrain_rows(recs, table)
    assert rows and set(rows[0]) >= {"chainage_m", "grade_pct", "pred_s", "act_s", "delta_s"}, rows[0]
    assert rows[0]["chainage_m"] == rows[0]["length_m"] or rows[0]["length_m"] >= 100
    net = sum(r["delta_s"] for r in rows)
    assert abs(net) < 60, f"attribution does not close: {net}s"
    classes = {r["class_"] for r in rows}
    assert classes <= {"slow", "fast", "on-model"}, classes
    return len(rows), net


def write_asc(path, n=60, cell=0.000225, func=lambda r, c: 100.0):
    # centred so the synthetic route (22.30 / 114.20) falls inside the grid
    lines = [f"ncols {n}", f"nrows {n}", "xllcorner 114.195",
             "yllcorner 22.295", f"cellsize {cell}", "NODATA_value -9999"]
    for r in range(n):
        lines.append(" ".join(f"{func(r, c):.1f}" for c in range(n)))
    open(path, "w").write("\n".join(lines))


def test_terrain_index_flat_vs_rough(tmp="/tmp/_t.asc"):
    """TRI must read 0 on a flat surface and scale with roughness."""
    write_asc(tmp, 60, 0.000225, lambda r, c: 100.0)
    flat = core.load_asc(tmp)
    assert abs(core.tri_at(flat, 22.30, 114.20)) < 0.01

    write_asc(tmp + "2", 60, 0.000225, lambda r, c: 100.0 + (10 if (r + c) % 2 else -10))
    rough = core.load_asc(tmp + "2")
    tri = core.tri_at(rough, 22.30, 114.20)
    # checkerboard: 4 orthogonal neighbours differ by 20 m, 4 diagonals by 0
    # -> RMS = sqrt(4*400/8) = 14.14 m
    assert tri and abs(tri - 14.14) < 0.5, f"checkerboard TRI should be ~14.1 m, got {tri}"
    return round(core.tri_at(flat, 22.30, 114.20), 2), round(tri, 1)


def test_terrain_rows_optional_columns(tmp="/tmp/_k.asc", tmp2="/tmp/_r.json"):
    """DTM and remarks are optional; each adds its own column only when supplied."""
    recs = synthetic_hilly(4)
    table = core.grade_table(recs)
    import json as _json
    base = core.terrain_rows(recs, table)
    assert "terrain_index_m" not in base[0] and "remark" not in base[0]

    write_asc(tmp, 220, 0.000225, lambda r, c: 100.0 + r * 0.5)   # must cover the route
    _json.dump([{"from_m": 0, "to_m": 500, "note": "石級＋濕滑"}], open(tmp2, "w"))
    rows = core.terrain_rows(recs, table, asc=core.load_asc(tmp),
                             remarks=_json.load(open(tmp2)))
    assert "terrain_index_m" in rows[0] and rows[0]["terrain_index_m"] != ""
    assert rows[0]["remark"] == "石級＋濕滑" and rows[-1]["remark"] == ""
    assert all(float(r["length_m"]) == 100.0 for r in rows[:-1]), "bins must be exact"
    return len(rows)


def test_plan_rules():
    """The plan must obey its own rules: start at base, cap 1.2x, taper, 20% hard."""
    prof = dict(event="Test 100", event_date="2027-01-23", distance_km=96,
                d_plus_m=5142, target_hours=16, weekly_hours=8, goal="ultra_trail")
    rows = [dict(chainage_m=i * 100, grade_pct=-9.0, delta_s=20, class_="slow")
            for i in range(140, 160)]
    weeks = plan.build(prof, rows, dt.date(2026, 11, 15))["plan"]
    build = [w for w in weeks if w["phase"] == "build"]
    taper = [w for w in weeks if w["phase"] == "taper"]
    race = [w for w in weeks if w["phase"] == "race"]

    assert build[0]["hours_planned"] == 8.0, build[0]["hours_planned"]
    assert max(w["hours_planned"] for w in build) <= 9.6 + 1e-9, "exceeded 1.2x base"
    assert build[0]["hours"] <= build[0]["hours_planned"] + 1e-9, "ran more than planned"
    assert [w["hours"] for w in taper] == sorted((w["hours"] for w in taper), reverse=True), \
        "taper must shrink week by week"
    assert all(12 <= w["hard_share"] <= 22 for w in build), "hard share out of band"
    assert race[0]["km_target"] == 96 and race[0]["vert_target_m"] == 5142
    assert race[0]["hours"] <= 2.0, "race week training hours must exclude the race itself"
    for w in weeks:
        assert abs(sum(s["minutes"] for s in w["sessions"] if s["zone"] != "race") / 60
                   - w["hours"]) < 0.11, (w["week_from_today"], w["hours"])
    assert weeks[0]["week_from_today"] == 10
    kinds = {s["type"] for w in build for s in w["sessions"]}
    assert "descent technique" in kinds, f"weakness session missing: {kinds}"
    return weeks[0]["hours"], weeks[-3]["hours"], weeks[-1]["hours"]


def test_icu_export(tmp="/tmp/_icu"):
    """One text file per non-race session, and the steps must add up to its minutes."""
    import os, re, shutil
    shutil.rmtree(tmp, ignore_errors=True)
    prof = dict(event="Test 100", event_date="2027-01-23", distance_km=96,
                d_plus_m=5142, target_hours=16, weekly_hours=8, goal="ultra_trail")
    built = plan.build(prof, [], dt.date(2026, 11, 15))
    n = plan.export_icu(built, tmp)
    sessions = [s for w in built["plan"] for s in w["sessions"] if s["type"] != "race"]
    assert n == len(sessions), (n, len(sessions))

    total = 0
    for f in os.listdir(tmp):
        if not f.endswith(".txt") or f == "README.txt":
            continue
        text = open(os.path.join(tmp, f)).read()
        steps = [int(x) for x in re.findall(r"- (\d+)m", text)]
        m = re.search(r"— (\d+) min", text)
        assert steps and m, f
        reps = re.search(r"Main Set (\d+)x", text)
        n = int(reps.group(1)) if reps else 1
        # warm + reps*(work+rest) + cool
        got = steps[0] + n * (steps[1] + steps[2]) + steps[-1] if n > 1 else sum(steps)
        total += abs(got - int(m.group(1)))
    assert total <= len(sessions) * 2, f"step minutes drift by {total} min"
    return n


def test_schedule_and_health():
    """Work days cap the week; a declared injury removes intensity entirely."""
    prof = dict(event="T", event_date="2027-01-23", distance_km=96, d_plus_m=5142,
                target_hours=16, weekly_hours=8, goal="ultra_trail",
                schedule=dict(work_days=[1, 2, 3, 4, 5], weekday_max_minutes=75, long_day="Sun"))
    weeks = plan.build(prof, [], dt.date(2026, 11, 15))["plan"]
    build = [w for w in weeks if w["phase"] == "build"]
    cap = 75
    for w in build:
        for s in w["sessions"]:
            if s["type"] == "long trail":
                assert s["day"] == "Sun", f"long run on a work day: {s['day']}"
            elif s["zone"] != "race":
                assert s["minutes"] <= cap, (s["day"], s["minutes"])

    hurt = dict(prof, health=dict(conditions=["knee pain"], current_pain="left ankle"))
    gated = plan.build(hurt, [], dt.date(2026, 11, 15))
    assert gated["health_gate"], "health gate not raised"
    zones = {s["zone"] for w in gated["plan"] for s in w["sessions"]}
    assert "Z3-Z4" not in zones, "intensity prescribed despite injury"
    return cap


def test_current_level_caps_the_plan():
    """The plan may not invent capacity the athlete does not have."""
    prof = dict(event="T", event_date="2027-01-23", distance_km=96, d_plus_m=5142,
                target_hours=16, weekly_hours=8, goal="ultra_trail",
                current=dict(longest_run_h=2.0, weekly_km=30, projected_hours=13.9))
    built = plan.build(prof, [], dt.date(2026, 11, 15))
    first = built["plan"][0]
    assert first["km_target"] <= 30 * 1.1 + 1e-6, first["km_target"]
    longs = [s for w in built["plan"] for s in w["sessions"] if s["type"] == "long trail"]
    assert max(s["minutes"] for s in longs) <= 2.0 * 60 * 1.1 + 1, "long run jumped past current level"
    assert built["feasibility"] and "13.9" in built["feasibility"]
    # sessions must read in weekday order
    order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for w in built["plan"]:
        idx = [order.index(s["day"]) for s in w["sessions"]]
        assert idx == sorted(idx), f"week {w['week_from_today']} not in weekday order"
    return first["km_target"], max(s["minutes"] for s in longs)


def test_strength_sessions():
    """Two strength sessions a week, never the day before quality or the long run."""
    base = dict(event="T", event_date="2027-01-23", distance_km=96, d_plus_m=5142,
                target_hours=16, weekly_hours=8, goal="ultra_trail",
                schedule=dict(work_days=[1, 2, 3, 4, 5], long_day="Sun"))
    off = plan.build(dict(base, strength=dict(enabled=False)), [], dt.date(2026, 11, 15))
    assert all(s["type"] != "strength" for w in off["plan"] for s in w["sessions"])

    on = plan.build(dict(base, strength=dict(enabled=True, sessions=2, minutes=30)),
                    [], dt.date(2026, 11, 15))
    order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for w in on["plan"]:
        if w["phase"] == "race":
            continue
        st = [s for s in w["sessions"] if s["type"] == "strength"]
        # taper keeps one light session; race week has none
        want = 1 if w["phase"] == "taper" else 2
        assert len(st) == want, (w["week_from_today"], w["phase"], len(st))
        quality = next(s["day"] for s in w["sessions"] if s["zone"] == "Z3-Z4")
        long_day = next(s["day"] for s in w["sessions"] if s["type"] == "long trail")
        blocked = {order[(order.index(quality) - 1) % 7], quality,
                   order[(order.index(long_day) - 1) % 7], long_day}
        assert not ({s["day"] for s in st} & blocked), f"strength on a key-session eve: {blocked}"
        assert w["strength_min"] == 30 * want
    return len(st)


def test_nutrition_scales_with_weight_and_duration():
    """Targets are arithmetic on the position stand, not vibes."""
    t = nutrition.targets(60, 16)
    assert t["carb_load_g"] == 600, "10 g/kg load"
    assert t["carb_easy_g"] == 300 and t["carb_quality_g"] == 480
    assert t["race_carb_total_g"] == (960, 1440), "60-90 g/h over 16 h"
    assert t["protein_g"] == (72, 120)
    big = nutrition.targets(80, 10)
    assert big["carb_load_g"] == 800 and big["race_carb_total_g"] == (600, 900)
    week = nutrition.race_week(t, 16)
    assert [r["day"] for r in week][-1] == "比賽中"
    assert all("note" in r for r in week)
    return t["carb_load_g"], t["race_carb_total_g"]


def test_day_count_is_honoured():
    """If the athlete has N days, the plan uses N days of running — no more."""
    for n in (2, 3, 5, 7):
        prof = dict(event="T", event_date="2027-01-23", distance_km=96, d_plus_m=5142,
                    target_hours=16, weekly_hours=8, goal="ultra_trail",
                    schedule=dict(work_days=[1, 2, 3, 4, 5], long_day="Sun",
                                  days_per_week=n))
        weeks = plan.build(prof, [], dt.date(2026, 11, 15))["plan"]
        for w in weeks:
            if w["phase"] == "race":
                continue
            runs = [s for s in w["sessions"] if s["type"] != "strength"]
            if w["phase"] == "taper":
                assert 0 < len(runs) <= n, (n, len(runs))
            else:
                assert len(runs) == n, (n, len(runs), [s["type"] for s in runs])
    return n


def test_strength_content():
    """Both sessions exist, every exercise has a cue and a pictogram, and the
    equipment tiers actually downgrade the list."""
    gym = strength.sessions("gym")
    assert len(gym) == 2
    for title, exs in gym:
        assert len(exs) >= 5, title
        for name, cue, kind in exs:
            assert name and cue and kind
            svg = strength._fig(kind)
            assert svg.startswith("<svg") and "stroke" in svg
    home = strength.sessions("home")
    none = strength.sessions("none")
    assert len(none[0][1]) <= len(home[0][1]) <= len(gym[0][1])
    blocks = strength.BLOCKS
    assert len(blocks) == 3 and "RPE" in blocks[0][1]
    return len(gym[0][1]) + len(gym[1][1])


if __name__ == "__main__":
    n, worst = test_flat_is_self_consistent()
    print(f"flat self-consistency: {n} segments, worst delta {worst}s")
    a, b = test_uphill_is_slower()
    print(f"gradient response: flat km {a}s vs 10% km {b}s")
    print(f"route geometry: {test_route_geometry()} segments")
    print(f"decoupling on constant effort: {test_decoupling_zero_on_constant()}%")
    print(f"decoupling under HR drift: {test_decoupling_sign()}% (positive = faded)")
    fg, ug = test_grade_is_distance_weighted()
    print(f"per-km grade: flat {fg} vs climb {ug}")
    print(f"gps gap: kilometres kept {test_gps_gap_creates_no_fake_km()}")
    gs, gf = test_grade_window_is_distance_based()
    print(f"grade window speed-invariant: 1 m/s {gs:.3f} vs 4 m/s {gf:.3f}")
    print(f"decoupling with warm-up spike: {test_warmup_excluded_from_decoupling()}%")
    ck, ch = test_projection_needs_three_bins()
    print(f"course projection: {ck} km -> {ch} h, refuses 2-bin curve")
    te, tf = test_target_density_uses_the_event()
    print(f"vertical benchmark: event {te} m/km vs fallback {tf} m/km")
    kt, mt = test_map_agrees_with_km_table()
    print(f"map vs km table delta: {mt}s vs {kt}s")
    ck2, cd2, cb = test_course_stats_counts_the_climb()
    print(f"course stats: {ck2} km, {cd2} m D+, bands {cb}")
    tn, tnet = test_terrain_rows_add_up()
    print(f"terrain csv: {tn} bins, net {tnet:+}s")
    f_tri, r_tri = test_terrain_index_flat_vs_rough()
    print(f"terrain index: flat {f_tri} m vs rough {r_tri} m")
    print(f"optional columns: {test_terrain_rows_optional_columns()} exact bins")
    h0, ht, hr = test_plan_rules()
    print(f"plan rules: start {h0} h, taper {ht} h, race week {hr} h, 20% hard, descent session present")
    print(f"icu export: {test_icu_export()} workout files")
    print(f"schedule + health gate: weekday cap {test_schedule_and_health()} min, "
          f"intensity removed when injured")
    print(f"strength: {test_strength_sessions()} sessions/week, clear of key days")
    print(f"day count honoured: {test_day_count_is_honoured()} days max")
    print(f"strength content: {test_strength_content()} exercises with pictograms")
    nl, nt = test_nutrition_scales_with_weight_and_duration()
    print(f"nutrition: {nl} g carb load at 60 kg, {nt[0]}-{nt[1]} g during a 16 h race")
    ck3, cl = test_current_level_caps_the_plan()
    print(f"current level: first week {ck3} km, longest run {cl} min, feasibility reported")
    print("OK")
    sys.exit(0)
