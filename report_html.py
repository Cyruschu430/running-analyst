#!/usr/bin/env python3
"""FIT + goal profile -> one self-contained report.html (2D/3D terrain).

    python report_html.py activity.fit --profile profile.json --out report.html

All numbers come from report.py; this file only arranges them. Copy is written
in professional written Chinese. Every metric carries a source — see
references/sport-science.md. Nothing here is invented.
"""
import argparse, json

import report as core

# goal -> (vertical density benchmark m/km, emphasis)
# ponytail: there is no published universal m/km standard. These are category
# conventions used only as a fallback -- when the profile names a target event
# with distance and D+, the organiser's own route supplies the benchmark.
GOALS = {
    "10k_road":      (5,  "配速穩定性"),
    "marathon_road": (10, "後段配速衰減"),
    "half_trail":    (30, "上坡經濟性"),
    "ultra_trail":   (45, "爬升密度、下坡技術與補給"),
}


def km_segments(recs):
    table = core.grade_table(recs)
    lookup = core.speed_lookup(table)
    if lookup is None:
        raise SystemExit("no grade table: the run is too short to build a model")

    segs, idx = [], 1
    cur = dict(actual=0.0, model=0.0, dplus=0.0, dist=0.0, gsum=0.0, hr=[], cad=[])
    for i in range(1, len(recs)):
        dd = recs[i][0] - recs[i - 1][0]
        while recs[i][0] >= idx * 1000:
            # a km holding <100 m of data is a GPS dropout, not a 0:00 kilometre
            if cur["dist"] >= 100:
                g = cur["gsum"] / cur["dist"]
                segs.append(dict(km=idx, grade=round(g, 3), d_plus=round(cur["dplus"]),
                                 actual_s=round(cur["actual"]), model_s=round(cur["model"]),
                                 delta_s=round(cur["actual"] - cur["model"]),
                                 hr=round(core.mean(cur["hr"]) or 0),
                                 cadence=round((core.mean(cur["cad"]) or 0) * 2),
                                 gap=False))
            idx += 1
            cur = dict(actual=0.0, model=0.0, dplus=0.0, dist=0.0, gsum=0.0, hr=[], cad=[])
            if idx > 300:  # ponytail: 300 km ceiling; raise if anyone races further
                return segs, table
        if dd > 300:            # GPS dropout: not distance, not time, not grade
            cur = dict(actual=0.0, model=0.0, dplus=0.0, dist=0.0, gsum=0.0, hr=[], cad=[])
            i += 1
            continue
        g = core.grade_at(recs, i) or 0
        spd = recs[i][2]
        # ponytail: paused / GPS-hole samples fall back to model speed so a
        # stopped watch is not reported as "time lost on this climb".
        cur["actual"] += dd / (spd if spd > 0.5 else lookup(g))
        cur["model"] += dd / lookup(g)
        cur["dplus"] += max(0.0, recs[i][1] - recs[i - 1][1])
        cur["dist"] += dd
        cur["gsum"] += dd * g
        if recs[i][3]:
            cur["hr"].append(recs[i][3])
        if recs[i][4]:
            cur["cad"].append(recs[i][4])
    return segs, table


def route_features(recs, table, step=100):
    """100 m segments carrying the time delta versus the athlete's own model.

    Binning lives in core.bins_100m so the map and the terrain CSV cannot
    disagree about the same metre of trail.
    """
    lookup = core.speed_lookup(table)
    if lookup is None:
        return {"type": "FeatureCollection", "features": []}
    feats = [{"type": "Feature",
              "properties": {"km": round(b["chainage_m"] / 1000, 2),
                             "grade": b["grade_pct"],
                             "delta": b["delta_s"]},
              "geometry": {"type": "LineString", "coordinates": b["coords"]}}
             for b in core.bins_100m(recs, lookup, step)]
    return {"type": "FeatureCollection", "features": feats}


def target_density(prof):
    """Benchmark from the target event when known, else the category convention."""
    km, dp = prof.get("distance_km"), prof.get("d_plus_m")
    if km and dp:
        return dp / km, "目標賽事路線"
    return float(GOALS.get(prof["goal"], (30, ""))[0]), "類別慣例（非標準值）"


def assessment(rep, prof):
    dens = (rep["ascent"] or 0) / rep["distance_km"]
    target, basis = target_density(prof)
    ratio = dens / target if target else 0
    out = []
    lthr = prof.get("lthr")
    if rep["avg_hr"] and lthr:
        pct = rep["avg_hr"] / lthr * 100
        tone = "中高強度；不宜以輕鬆長課視之" if pct >= 85 else \
               "中等強度" if pct >= 75 else "偏低強度，屬恢復或基礎課"
        note = "；LTHR 為估算值" if prof.get("lthr_basis") else ""
        out.append("本次訓練平均心率 %d bpm，為乳酸閾值的 %.0f%%（%s）%s。"
                   % (rep["avg_hr"], pct, tone, note))
        if prof.get("lthr_basis"):
            out.append("LTHR 依據：%s。" % prof["lthr_basis"])
    elif rep["avg_hr"]:
        # ponytail: no LTHR in the profile -> say so instead of guessing an absolute bpm
        out.append("未設定乳酸閾值（LTHR），本節不作強度判斷；於 profile 加入 lthr 後即可按百分比評估。")
    if ratio < 0.7:
        out.append("爬升密度為 %.0f m/km，僅達%s %.0f m/km 的 %.0f%%，比賽特異性不足。"
                   % (dens, basis, target, ratio * 100))
    elif ratio > 1.3:
        out.append("爬升密度為 %.0f m/km，高於%s %.0f m/km，須留意恢復安排。"
                   % (dens, basis, target))
    else:
        out.append("爬升密度為 %.0f m/km，接近%s %.0f m/km。" % (dens, basis, target))
    if abs(rep.get("decoupling_pct") or 0) > 8:
        out.append("後段每一下心跳推動的速度下降 %.1f%%（正常範圍約 5%% 以內），"
                   "顯示疲勞、補給不足或天氣影響。" % rep["decoupling_pct"])
    return out, dens, target


SPORT_ZH = {"running/trail": "越野跑", "running": "路跑", "trail_running": "越野跑",
            "hiking": "行山", "cycling": "單車", "swimming": "游泳"}


def advice(prof, worst):
    target, basis = target_density(prof)
    tips = ["本週總爬升以目標賽事密度換算：跑量 × %.0f m/km（例：30 公里 → %.0f m），"
            "分散在長課與爬坡課，不要單節硬塞。"
            % (target, round(30 * target / 10) * 10)]
    if worst and worst[0]["delta_s"] > 30:
        w = worst[0]
        if w["grade"] < -0.03:
            focus = "落坡技術：縮短步幅、提高步頻，避免剎車式落腳"
        elif w["grade"] > 0.03:
            focus = "上坡經濟性：以可持續功率爬升，不要在坡底衝刺"
        else:
            focus = "平路配速穩定性：前段避免過快"
        tips.append("第 %d 公里（坡度 %+.0f%%）較模型慢 %d 秒，重點為%s。"
                    % (w["km"], w["grade"] * 100, w["delta_s"], focus))
    lthr = prof.get("lthr")
    if lthr:
        tips.append("長課心率維持於 Zone 2（約 %d–%d bpm，即 65–75%% LTHR），以建立可持續強度基準。"
                    % (round(lthr * 0.65), round(lthr * 0.75)))
    else:
        tips.append("輕鬆長課心率應明顯低於乳酸閾值；於 profile 加入 lthr 可獲具體心率區間。")
    return tips


def svg_profile(segs, w=900, h=190):
    """Per-km delta against the model, zero line in the middle.

    ponytail: fixed pixel height, no chart lib — one SVG, no dependency, prints.
    """
    if not segs:
        return ""
    mx = max(abs(s["delta_s"]) for s in segs) or 1
    mid = h / 2
    scale = (h / 2 - 22) / mx
    bw = w / len(segs)
    bars = []
    for i, s in enumerate(segs):
        d = s["delta_s"]
        hh = max(abs(d) * scale, 1.5)
        col = ("#c0392b" if d > 0.35 * mx else "#e67e22" if d > 0.1 * mx
               else "#1e8449" if d < -0.1 * mx else "#8794a3")
        y = mid - hh if d > 0 else mid
        bars.append(
            f'<rect x="{i*bw+0.8:.1f}" y="{y:.1f}" width="{max(bw-1.6,1):.1f}" '
            f'height="{hh:.1f}" fill="{col}" opacity=".92">'
            f'<title>第 {s["km"]} 公里：較模型 {d:+d} 秒（坡度 {s["grade"]*100:+.0f}%）</title></rect>')
    ticks = "".join(
        f'<text x="{i*bw+2:.0f}" y="{h-4}" font-size="9" fill="#8A9099">{segs[i]["km"]}</text>'
        for i in range(0, len(segs), max(1, len(segs) // 10)))
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" role="img" '
            f'aria-label="各公里相對模型之時間差">{"".join(bars)}'
            f'<line x1="0" x2="{w}" y1="{mid}" y2="{mid}" stroke="#0C0F14" stroke-width="1"/>'
            f'{ticks}</svg>')


def map_block(geojson):
    gj = json.dumps(geojson, ensure_ascii=False)
    return f"""
<div id="map"></div>
<div class="mapctl">
  <button id="t3d">切換 3D 地形</button>
  <span class="hint">點擊路線查看分段數據</span>
</div>
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet">
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<script>
const ROUTE = {gj};
const map = new maplibregl.Map({{
  container: 'map',
  style: {{
    version: 8,
    sources: {{
      esri: {{ type: 'raster',
               tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}'],
               tileSize: 256, maxzoom: 17,
               attribution: '底圖 © Esri, Maxar, Earthstar Geographics' }},
      dem: {{ type: 'raster-dem',
              tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{{z}}/{{x}}/{{y}}.png'],
              encoding: 'terrarium', tileSize: 256, maxzoom: 15 }},
      route: {{ type: 'geojson', data: ROUTE }}
    }},
    layers: [
      {{ id: 'bg', type: 'background', paint: {{ 'background-color': '#0d141c' }} }},
      {{ id: 'esri', type: 'raster', source: 'esri',
         paint: {{ 'raster-opacity': 0.85, 'raster-saturation': -0.25, 'raster-brightness-max': 0.85 }} }},
      {{ id: 'hill', type: 'hillshade', source: 'dem',
         paint: {{ 'hillshade-shadow-color': '#000000', 'hillshade-highlight-color': '#ffffff',
                   'hillshade-accent-color': '#243447', 'hillshade-exaggeration': 0.45 }} }},
      {{ id: 'glow', type: 'line', source: 'route',
         paint: {{ 'line-color': '#ffffff', 'line-width': 8, 'line-blur': 7, 'line-opacity': 0.15 }} }},
      {{ id: 'route', type: 'line', source: 'route',
         paint: {{
           'line-width': 3.2, 'line-opacity': 0.95,
           'line-color': ['interpolate', ['linear'], ['get', 'delta'],
                          -30, '#1e8449', -5, '#27ae60', 5, '#95a5a6', 20, '#e67e22', 45, '#c0392b']
         }} }}
    ]
  }},
  center: [114.15, 22.38], zoom: 10, pitch: 0,
  attributionControl: {{ compact: true, customAttribution: '底圖 © Esri · 地形 AWS Terrain Tiles（Mapzen）· MapLibre GL JS' }}
}});
map.addControl(new maplibregl.NavigationControl({{ visualizePitch: true }}), 'bottom-right');
const b = new maplibregl.LngLatBounds();
ROUTE.features.forEach(f => f.geometry.coordinates.forEach(c => b.extend(c)));
map.fitBounds(b, {{ padding: 40, pitch: 45, bearing: -18, duration: 0 }});

let is3d = false;
document.getElementById('t3d').onclick = e => {{
  is3d = !is3d;
  if (is3d) {{
    map.setTerrain({{ source: 'dem', exaggeration: 1.5 }});
    map.easeTo({{ pitch: 65, bearing: -18, duration: 700 }});
  }} else {{
    map.setTerrain(null);
    map.easeTo({{ pitch: 0, duration: 700 }});
  }}
  e.target.textContent = is3d ? '切換 2D 平面' : '切換 3D 地形';
}};
map.on('click', 'route', ev => {{
  const p = ev.features[0].properties;
  new maplibregl.Popup({{ closeButton: false }})
    .setLngLat(ev.lngLat)
    .setHTML('<b>' + p.km + ' km</b><br>坡度 ' + p.grade + '%<br>較模型 '
             + (p.delta > 0 ? '+' : '') + p.delta + ' 秒')
    .addTo(map);
}});
map.on('mouseenter', 'route', () => map.getCanvas().style.cursor = 'pointer');
map.on('mouseleave', 'route', () => map.getCanvas().style.cursor = '');
</script>"""


def build(rep, prof, segs, gj):
    notes, dens, target = assessment(rep, prof)
    worst = sorted(segs, key=lambda s: -s["delta_s"])[:3]
    tips = advice(prof, worst)
    rows = "".join(
        f"<tr><td>{s['km']}</td><td>{s['grade']*100:+.0f}%</td><td>{s['d_plus']}</td>"
        f"<td>{s['actual_s']//60}:{s['actual_s']%60:02d}</td>"
        f"<td class=\"{'neg' if s['delta_s'] > 10 else 'pos' if s['delta_s'] < -10 else ''}\">"
        f"{s['delta_s']:+d}</td><td>{s['hr'] or '—'}</td><td>{s['cadence'] or '—'}</td></tr>"
        for s in segs)
    worst_li = "".join(
        f"<li>第 {s['km']} 公里：坡度 {s['grade']*100:+.0f}%，實際較模型慢 {s['delta_s']} 秒。</li>"
        for s in worst)
    return f"""<!doctype html><html lang="zh-Hant-HK"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Running Analyst｜{prof['event']}</title>
<style>
:root{{--ink:#0C0F14;--paper:#FBFAF7;--dim:#6C7480;--line:#E2DFD8;
 --volt:#D8FF3E;--accent-ink:#6E7A12;--bad:#B3261E;--good:#1B6B3A}}
*{{box-sizing:border-box}}
html{{background:#E8E6E0}}
body{{margin:0 auto;max-width:1040px;background:var(--paper);color:var(--ink);
 font:15px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC",system-ui,sans-serif;
 -webkit-font-smoothing:antialiased}}
.hero{{background:var(--ink);color:#F7F5F0;padding:34px 40px 30px}}
.brand{{font-size:10px;letter-spacing:.30em;text-transform:uppercase;color:#9AA3AE;
 display:flex;align-items:center;gap:10px}}
.brand::before{{content:"";width:26px;height:3px;background:var(--volt);display:inline-block}}
h1{{font-size:34px;line-height:1.15;font-weight:600;letter-spacing:-.02em;margin:14px 0 8px}}
.sub{{color:#A8B0BA;font-size:12.5px;letter-spacing:.02em}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));
 gap:0;margin:26px 40px 0;border-top:1px solid var(--line)}}
.kpi{{padding:16px 18px 14px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}}
.kpi:first-child{{padding-left:0;border-left:3px solid var(--volt)}}
.kpi:first-child b{{font-size:34px}}
.kpi:nth-child(6n){{border-right:none}}
.kpi b{{display:block;font-size:27px;font-weight:600;letter-spacing:-.03em;
 font-variant-numeric:tabular-nums;line-height:1.15}}
.kpi span{{display:block;margin-top:4px;font-size:10.5px;color:var(--dim);
 letter-spacing:.10em;text-transform:uppercase}}
main{{padding:6px 40px 44px}}
main{{counter-reset:sec}}
h2{{display:flex;align-items:baseline;gap:12px;font-size:11px;font-weight:650;
 letter-spacing:.18em;text-transform:uppercase;color:var(--dim);
 margin:38px 0 14px;padding-bottom:0}}
h2::before{{counter-increment:sec;content:counter(sec,decimal-leading-zero);
 font-size:10px;letter-spacing:.06em;color:var(--accent-ink);
 font-variant-numeric:tabular-nums;font-weight:700}}
h2::after{{content:"";flex:1;height:1px;background:var(--line);transform:translateY(-3px)}}
ul{{margin:12px 0;padding-left:0;list-style:none}}
li{{position:relative;padding-left:18px;margin:9px 0;color:#20262E}}
li::before{{content:"";position:absolute;left:0;top:.62em;width:6px;height:6px;
 background:var(--accent-ink);border-radius:50%}}
#map{{height:460px;border-radius:2px;overflow:hidden;border:1px solid #11151B;
 border-top:3px solid var(--volt);box-shadow:0 18px 40px -26px rgba(12,15,20,.55)}}
.mapctl{{display:flex;align-items:center;gap:12px;margin-top:12px}}
button{{font:inherit;font-size:12px;letter-spacing:.06em;text-transform:uppercase;
 padding:8px 16px;border:1px solid var(--ink);border-radius:0;background:transparent;
 cursor:pointer;transition:background .15s,color .15s}}
button:hover{{background:var(--ink);color:var(--volt)}}
.hint{{font-size:11.5px;color:var(--dim);letter-spacing:.02em}}
table{{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}}
th,td{{text-align:right;padding:8px 10px;border-bottom:1px solid var(--line)}}
th:first-child,td:first-child{{text-align:left}}
th{{font-weight:600;color:var(--dim);font-size:10.5px;letter-spacing:.12em;
 text-transform:uppercase;border-bottom:1px solid var(--ink)}}
tbody tr:hover{{background:#F4F2EC}}
td.neg{{color:var(--bad);font-weight:600}} td.pos{{color:var(--good);font-weight:600}}
footer{{margin:48px 40px 0;padding:18px 0 40px;border-top:1px solid var(--line);
 color:var(--dim);font-size:11px;line-height:1.7;letter-spacing:.01em}}
@media print{{.hero{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
</style></head><body>
<header class="hero">

<div class="brand">RUNNING ANALYST</div>
<h1>{prof['event']}｜訓練評估報告</h1>
<div class="sub">{prof.get('athlete','')}　·　{SPORT_ZH.get(rep['sport'], rep['sport'])}　·　{rep['distance_km']} 公里　·
{rep['elapsed_hms']}　·　累計爬升 {rep['ascent']} m　·　{rep['device'] or ''}</div>

<div class="kpis">
<div class="kpi"><b>{rep['distance_km']} km</b><span>距離</span></div>
<div class="kpi"><b>{rep['elapsed_hms']}</b><span>總時間</span></div>
<div class="kpi"><b>{rep['ascent']} m</b><span>累計爬升</span></div>
<div class="kpi"><b>{dens / target * 100:.0f}%</b><span>爬升密度 {dens:.0f} / 目標 {target:.0f} m/km</span></div>
<div class="kpi"><b>{rep['avg_hr']}</b><span>平均心率</span></div>
<div class="kpi"><b>{rep.get('decoupling_pct','—')}%</b><span>後段效率變化</span></div>
</div>
</header>
<main>

<h2>綜合評估</h2>
<ul>{"".join(f"<li>{n}</li>" for n in notes)}</ul>

<h2>路線與地形</h2>
<p class="sub">路線依「實際與模型之時間差」著色：紅為較慢，綠為較快。模型依本人坡度與速度關係推算。</p>
{map_block(gj)}

<h2>分段表現</h2>
<p class="sub">各公里相對模型之時間差；紅色表示該段耗時高於模型預期。</p>
{svg_profile(segs)}
<p class="hint">上柱＝慢於模型，下柱＝快於模型；最大差距 {max(abs(x['delta_s']) for x in segs)} 秒。</p>

<h2>待改善路段</h2>
<ul>{worst_li}</ul>

<h2>分段數據</h2>
<table><thead><tr><th>公里</th><th>坡度</th><th>爬升 m</th><th>時間</th>
<th>與模型差（秒）</th><th>心率</th><th>步頻</th></tr></thead>
<tbody>{rows}</tbody></table>

<h2>訓練建議</h2>
<ul>{"".join(f"<li>{t}</li>" for t in tips)}</ul>

</main>
<footer>
本報告由穿戴裝置資料自動計算，僅供訓練參考，不構成醫療建議。GPS、光學心率與氣壓高度計均存在誤差，
數據宜作趨勢判讀，不宜視為絕對真值。訓練與比賽決策及受傷風險由使用者自行承擔；如有痛症、舊患或
心血管疾病史，請先諮詢醫生、物理治療師或合資格教練。疼痛為停止訊號，並非數據指標。
</footer>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fit")
    ap.add_argument("--profile", default="profile.json")
    ap.add_argument("--out", default="report.html")
    a = ap.parse_args()

    prof = json.load(open(a.profile))
    recs, s = core.load(a.fit)
    dur = (recs[-1][6] - recs[0][6]).total_seconds()
    rep = dict(device=s.get("product_name"), sport=f"{s.get('sport')}/{s.get('sub_sport')}",
               distance_km=round(s.get("total_distance", recs[-1][0]) / 1000, 2),
               elapsed_hms=f"{int(dur//3600)}:{int(dur%3600//60):02d}:{int(dur%60):02d}",
               ascent=s.get("total_ascent"), avg_hr=s.get("avg_heart_rate"))
    segs, table = km_segments(recs)
    rep["decoupling_pct"] = core.decoupling(core.thirds(recs))

    gj = route_features(recs, table)
    out = build(rep, prof, segs, gj)
    open(a.out, "w", encoding="utf-8").write(out)
    print(f"wrote {a.out} ({len(out)/1024:.0f} KB) · {len(segs)} km · "
          f"{len(gj['features'])} route segments")


if __name__ == "__main__":
    main()
