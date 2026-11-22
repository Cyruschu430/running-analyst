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


def route_features(recs, table, step=100, asc=None):
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
                             "delta": b["delta_s"],
                             **({"tri": round(t, 2)} if (asc and (t := core.tri_at(
                                 asc, b["coords"][len(b["coords"]) // 2][1],
                                 b["coords"][len(b["coords"]) // 2][0])) is not None) else {})},
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
        out.append("本次訓練平均心率 %d bpm，為乳酸閾值心率"
                   "（Lactate Threshold Heart Rate，LTHR）的 %.0f%%（%s）%s。"
                   % (rep["avg_hr"], pct, tone, note))
        if prof.get("lthr_basis"):
            out.append("LTHR 依據：%s。" % prof["lthr_basis"])
    elif rep["avg_hr"]:
        # ponytail: no LTHR in the profile -> say so instead of guessing an absolute bpm
        out.append("未設定乳酸閾值心率（Lactate Threshold Heart Rate，LTHR），本節不作強度判斷；於 profile 加入 lthr 後即可按百分比評估。")
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


def map_block(geojson, has_dtm=False, dem_tiles=None):
    gj = json.dumps(geojson, ensure_ascii=False)
    mode_btn = '<button id="tmode">切換上色</button>' if has_dtm else ""
    if dem_tiles:
        dem_url = "'lidar://{z}/{x}/{y}'"
        dem_maxz = 14
        attr = ("'底圖 © Esri, HERE, Garmin, © OpenStreetMap contributors · "
                "地形 土木工程拓展署 LiDAR DTM 2020（3 m，內嵌）· MapLibre GL JS'")
        dem_js = ("const DEM_TILES = " + json.dumps(dem_tiles) + ";\n"
                  "maplibregl.addProtocol('lidar', (params, abort) => new Promise((res, rej) => {\n"
                  "  const key = params.url.replace('lidar://', '');\n"
                  "  const b64 = DEM_TILES[key];\n"
                  "  if (b64) { const bin = atob(b64.slice(b64.indexOf(',') + 1));\n"
                  "    const buf = new Uint8Array(bin.length);\n"
                  "    for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);\n"
                  "    res({ data: buf.buffer }); return; }\n"
                  "  fetch('https://s3.amazonaws.com/elevation-tiles-prod/terrarium/' + key + '.png')\n"
                  "    .then(r => r.arrayBuffer()).then(d => res({ data: d })).catch(rej);\n"
                  "}));")
    else:
        dem_url = "'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'"
        dem_maxz = 15
        attr = ("'底圖 © Esri, HERE, Garmin, © OpenStreetMap contributors · "
                "地形 AWS Terrain Tiles（Mapzen）· MapLibre GL JS'")
        dem_js = ""
    return f"""
<div id="map"></div>
<div class="mapctl">
  <button id="pbtn">▶ 播放</button>
  <button id="t3d">切換 3D 地形</button>
  {mode_btn}
  <span class="hint" id="pb">0.0 / 0 km</span>
  <span class="hint">點擊路線查看分段數據</span>
</div>
<div class="scrubwrap">
  <input id="scrub" type="range" min="0" max="1000" value="0" step="1" aria-label="拖動查看分段">
  <span id="seg" class="seg">0.0 km</span>
</div>
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet">
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<script>
const ROUTE = {gj};
const BY_DELTA = ['interpolate', ['linear'], ['get', 'delta'],
                  -30, '#1e8449', -5, '#27ae60', 5, '#95a5a6', 20, '#e67e22', 45, '#c0392b'];
const BY_TRI = ['case', ['has', 'tri'],
                ['interpolate', ['linear'], ['get', 'tri'],
                 0, '#1e8449', 1, '#f1c40f', 2.5, '#c0392b'], '#8794a3'];
let cmode = 'delta';
{dem_js}
const map = new maplibregl.Map({{
  container: 'map',
  style: {{
    version: 8,
    sources: {{
      esri: {{ type: 'raster',
               tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{{z}}/{{y}}/{{x}}'],
               tileSize: 256, maxzoom: 17,
               attribution: '底圖 © Esri, HERE, Garmin, © OpenStreetMap contributors' }},
      dem: {{ type: 'raster-dem',
              tiles: [{dem_url}],
              encoding: 'terrarium', tileSize: 256, maxzoom: {dem_maxz} }},
      route: {{ type: 'geojson', data: ROUTE }},
      dot: {{ type: 'geojson', data: {{ type: 'FeatureCollection', features: [] }} }}
    }},
    layers: [
      {{ id: 'bg', type: 'background', paint: {{ 'background-color': '#0d141c' }} }},
      {{ id: 'esri', type: 'raster', source: 'esri',
         paint: {{ 'raster-opacity': 1 }} }},
      {{ id: 'hill', type: 'hillshade', source: 'dem',
         paint: {{ 'hillshade-shadow-color': '#000000', 'hillshade-highlight-color': '#ffffff',
                   'hillshade-accent-color': '#243447', 'hillshade-exaggeration': 0.25 }} }},
      {{ id: 'glow', type: 'line', source: 'route',
         paint: {{ 'line-color': '#ffffff', 'line-width': 8, 'line-blur': 7, 'line-opacity': 0.15 }} }},
      {{ id: 'route', type: 'line', source: 'route',
         paint: {{
           'line-width': 3.2, 'line-opacity': 0.95,
           'line-color': BY_DELTA
         }} }},
      {{ id: 'dot-glow', type: 'circle', source: 'dot',
         paint: {{ 'circle-radius': 16, 'circle-color': '#E8590C', 'circle-opacity': 0.22, 'circle-blur': 1 }} }},
      {{ id: 'dot', type: 'circle', source: 'dot',
         paint: {{ 'circle-radius': 7, 'circle-color': '#E8590C',
                   'circle-stroke-width': 2.5, 'circle-stroke-color': '#FFFFFF' }} }}
    ]
  }},
  center: [114.15, 22.38], zoom: 10, pitch: 0,
  attributionControl: {{ compact: true, customAttribution: {attr} }}
}});
map.addControl(new maplibregl.NavigationControl({{ visualizePitch: true }}), 'bottom-right');
const tbtn = document.getElementById('tmode');
if (tbtn) {{
  const sub = document.getElementById('mapsub');
  const TXT = {{
    delta: '路線依「實際與模型之時間差」著色：紅為較慢，綠為較快。'
           + '模型＝以你本人過往 FIT 記錄擬合的「坡度—速度」關係：同一坡度你平常跑得多快，再逐段換算應需時間。',
    tri: '路線按地形粗糙度（TRI）上色：綠色平坦、黃色中等、紅色崎嶇（3 m LiDAR DTM）。'
  }};
  tbtn.onclick = () => {{
    cmode = cmode === 'delta' ? 'tri' : 'delta';
    map.setPaintProperty('route', 'line-color', cmode === 'delta' ? BY_DELTA : BY_TRI);
    sub.textContent = TXT[cmode];
  }};
}}

// playback: a dot sweeping the course in 30 s
(() => {{
  const pbtn = document.getElementById('pbtn'), pb = document.getElementById('pb');
  if (!pbtn) return;
  const path = [], owner = [];
  ROUTE.features.forEach((f, k) => f.geometry.coordinates.forEach(c => {{ path.push(c); owner.push(k); }}));
  if (path.length < 2) return;
  const R = 6371000, rad = Math.PI / 180;
  const cum = [0];
  for (let i = 1; i < path.length; i++) {{
    const a = path[i - 1], b = path[i];
    const dla = (b[1] - a[1]) * rad, dlo = (b[0] - a[0]) * rad;
    const la = (a[1] + b[1]) / 2 * rad;
    cum.push(cum[i - 1] + R * Math.hypot(dla, dlo * Math.cos(la)));
  }}
  const total = cum[cum.length - 1], DUR = 30000;
  let playing = false, elapsed = 0, start = 0;
  const setDot = d => {{
    let i = 1;
    while (i < path.length - 1 && cum[i] < d) i++;
    const span = cum[i] - cum[i - 1] || 1, t = (d - cum[i - 1]) / span;
    const a = path[i - 1], b = path[i];
    const lon = a[0] + (b[0] - a[0]) * t, lat = a[1] + (b[1] - a[1]) * t;
    const src = map.getSource('dot');
    if (!src) return null;
    src.setData({{ type: 'FeatureCollection', features: [{{ type: 'Feature',
      properties: {{}}, geometry: {{ type: 'Point', coordinates: [lon, lat] }} }}] }});
    pb.textContent = (d / 1000).toFixed(1) + ' / ' + (total / 1000).toFixed(0) + ' km';
    const dlon = (b[0] - a[0]) * Math.cos(lat * rad);
    return [lon, lat, Math.atan2(dlon, b[1] - a[1]) * 180 / Math.PI];
  }};
  let brg = null, last = 0;
  const frame = ts => {{
    if (!playing) return;
    elapsed = Math.min(DUR, ts - start);
    // 10 Hz: terrain re-render per frame saturates the GPU on modest machines
    if (ts - last >= 100) {{
      last = ts;
      const pos = setDot(total * elapsed / DUR);
      if (pos) {{
        const h = pos[2];
        brg = brg === null ? h : brg + ((((h - brg) % 360) + 540) % 360 - 180) * 0.2;
        map.jumpTo({{ center: [pos[0], pos[1]], bearing: brg, pitch: 58, zoom: 14.2 }});
      }}
    }}
    if (elapsed < DUR) requestAnimationFrame(frame);
    else {{ playing = false; pbtn.textContent = '▶ 播放'; stopFollow(); }}
  }};
  let saved = null;
  const startFollow = () => {{
    saved = {{ center: map.getCenter(), zoom: map.getZoom(), pitch: map.getPitch(), bearing: map.getBearing() }};
    brg = null;
  }};
  const stopFollow = () => {{
    if (!saved) return;
    map.easeTo({{ center: saved.center, zoom: saved.zoom, pitch: saved.pitch,
                  bearing: saved.bearing, duration: 900 }});
    saved = null;
  }};
  pbtn.onclick = () => {{
    if (playing) {{ playing = false; pbtn.textContent = '▶ 播放'; stopFollow(); return; }}
    if (elapsed >= DUR) elapsed = 0;
    start = performance.now() - elapsed;
    playing = true; pbtn.textContent = '⏸ 暫停';
    startFollow();
    requestAnimationFrame(frame);
  }};
  const scrub = document.getElementById('scrub'), seg = document.getElementById('seg');
  const describe = d => {{
    let i = 1;
    while (i < path.length - 1 && cum[i] < d) i++;
    const f = ROUTE.features[owner[i]].properties;
    const dlt = f.delta > 0 ? '較模型慢 ' + Math.round(f.delta) + ' 秒'
                            : (f.delta < 0 ? '較模型快 ' + Math.round(-f.delta) + ' 秒' : '與模型一致');
    return (d / 1000).toFixed(1) + ' km　·　坡度 ' + (f.grade > 0 ? '+' : '') + f.grade
           + '%　·　' + dlt;
  }};
  if (scrub) {{
    scrub.oninput = () => {{
      if (playing) {{ playing = false; pbtn.textContent = '▶ 播放'; }}
      const d = total * scrub.value / 1000;
      setDot(d);
      seg.textContent = describe(d);
    }};
  }}
  map.once('load', () => setDot(0));
}})();
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


def terrain_stats(gj):
    """Ruggedness summary + whether it explains the time loss."""
    feats = [f["properties"] for f in gj["features"] if "tri" in f["properties"]]
    if len(feats) < 20:
        return None
    tri = [f["tri"] for f in feats]
    dl = [f["delta"] for f in feats]
    tri_sorted = sorted(tri)

    def corr(a, b):
        ma, mb = sum(a) / len(a), sum(b) / len(b)
        num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
        den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
        return num / den if den else 0.0

    down = [(f["tri"], f["delta"]) for f in feats if f["grade"] < -3]
    r_all = corr(tri, dl)
    r_down = corr([d[0] for d in down], [d[1] for d in down]) if len(down) > 10 else None
    return dict(n=len(feats), median=tri_sorted[len(tri) // 2],
                p90=tri_sorted[int(len(tri) * 0.9)], mx=tri_sorted[-1],
                r_all=r_all, r_down=r_down, n_down=len(down))


def build(rep, prof, segs, gj, has_dtm=False, dem_tiles=None):
    notes, dens, target = assessment(rep, prof)
    worst = sorted(segs, key=lambda s: -s["delta_s"])[:3]
    tips = advice(prof, worst)
    rows = "".join(
        f"<tr><td>{s['km']}</td><td>{s['grade']*100:+.0f}%</td><td>{s['d_plus']}</td>"
        f"<td>{s['actual_s']//60}:{s['actual_s']%60:02d}</td>"
        f"<td class=\"{'neg' if s['delta_s'] > 10 else 'pos' if s['delta_s'] < -10 else ''}\">"
        f"{s['delta_s']:+d}</td><td>{s['hr'] or '—'}</td><td>{s['cadence'] or '—'}</td></tr>"
        for s in segs)
    ts = terrain_stats(gj) if has_dtm else None
    if ts:
        if abs(ts["r_all"]) < 0.2 and (ts["r_down"] is None or abs(ts["r_down"]) < 0.25):
            verdict = ("地形粗糙度解釋不到時間損失；主因更可能在體能、配速或補給。")
        elif ts["r_down"] is not None and ts["r_down"] > 0.3:
            verdict = ("落坡段的時間損失與地形粗糙度相關，技術訓練有直接回報。")
        else:
            verdict = "地形與時間損失的關係不明確，需更多同類路線數據。"
        terrain_block = (
            f'<h2>地形粗糙度</h2>\n'
            f'<p class="sub">TRI：每個像素與 8 個鄰居高差的 RMS（Riley 1999），'
            f'以 LiDAR 派生 3 m 裸地 DTM 計算。</p>\n'
            f'<ul><li>{ts["n"]} 段：中位數 {ts["median"]:.2f} m、第 90 百分位（p90，九成路段低於此值）{ts["p90"]:.2f} m、'
            f'最大 {ts["mx"]:.2f} m。</li>'
            f'<li>與時間損失的相關性（皮爾森 r：+1 表示完全同步、0 表示無關、'
            f'−1 表示完全反向）：全段 r = {ts["r_all"]:+.2f}；'
            + (f'落坡段（{ts["n_down"]} 段）r = {ts["r_down"]:+.2f}。' if ts["r_down"] is not None
               else "落坡段數據不足。")
            + f'</li><li>{verdict}</li></ul>\n')
    else:
        terrain_block = ""
    worst_li = "".join(
        f"<li>第 {s['km']} 公里：坡度 {s['grade']*100:+.0f}%，實際較模型慢 {s['delta_s']} 秒。</li>"
        for s in worst)
    return f"""<!doctype html><html lang="zh-Hant-HK"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Running Analyst｜{prof['event']}</title>
<style>
:root{{--ink:#0C0F14;--paper:#FBFAF7;--dim:#6C7480;--line:#E2DFD8;
 --accent:#E8590C;--blue:#1B4D8F;--bad:#B3261E;--good:#1B6B3A}}
*{{box-sizing:border-box}}
html{{background:#E8E6E0}}
body{{margin:0 auto;max-width:1040px;background:var(--paper);color:var(--ink);
 font:15px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC",system-ui,sans-serif;
 -webkit-font-smoothing:antialiased}}
.hero{{background:var(--paper);color:var(--ink);padding:34px 40px 26px;
 border-bottom:1px solid var(--ink)}}
.brand{{font-size:10px;letter-spacing:.30em;text-transform:uppercase;color:var(--dim);
 display:flex;align-items:center;gap:10px}}
.brand::before{{content:"";width:26px;height:3px;background:var(--accent);display:inline-block}}
h1{{font-size:34px;line-height:1.15;font-weight:600;letter-spacing:-.02em;margin:14px 0 8px}}
.sub{{color:var(--dim);font-size:12.5px;letter-spacing:.02em}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));
 gap:0;margin:26px 40px 0;border-top:1px solid var(--line)}}
.kpi{{padding:16px 18px 14px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}}
.kpi:first-child{{padding-left:0;border-left:3px solid var(--accent)}}
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
 font-size:10px;letter-spacing:.06em;color:var(--blue);
 font-variant-numeric:tabular-nums;font-weight:700}}
h2::after{{content:"";flex:1;height:1px;background:var(--line);transform:translateY(-3px)}}
ul{{margin:12px 0;padding-left:0;list-style:none}}
li{{position:relative;padding-left:18px;margin:9px 0;color:#20262E}}
li::before{{content:"";position:absolute;left:0;top:.62em;width:6px;height:6px;
 background:var(--blue);border-radius:50%}}
#map{{height:460px;border-radius:2px;overflow:hidden;border:1px solid #11151B;
 border-top:3px solid var(--accent);box-shadow:0 18px 40px -26px rgba(12,15,20,.35)}}
.mapctl{{display:flex;align-items:center;gap:12px;margin-top:12px}}
button{{font:inherit;font-size:12px;letter-spacing:.06em;text-transform:uppercase;
 padding:8px 16px;border:1px solid var(--ink);border-radius:0;background:transparent;
 cursor:pointer;transition:background .15s,color .15s}}
button:hover{{background:var(--ink);color:var(--paper)}}
.hint{{font-size:11.5px;color:var(--dim);letter-spacing:.02em}}
.scrubwrap{{display:flex;align-items:center;gap:14px;margin-top:14px}}
#scrub{{-webkit-appearance:none;appearance:none;flex:1;height:2px;background:var(--line);
 outline:none;cursor:pointer}}
#scrub::-webkit-slider-thumb{{-webkit-appearance:none;width:14px;height:14px;border-radius:50%;
 background:var(--accent);border:2px solid var(--paper);box-shadow:0 0 0 1px var(--accent)}}
#scrub::-moz-range-thumb{{width:12px;height:12px;border-radius:50%;background:var(--accent);
 border:2px solid var(--paper);box-shadow:0 0 0 1px var(--accent)}}
.seg{{font-size:12px;color:var(--ink);font-variant-numeric:tabular-nums;min-width:250px;
 letter-spacing:.01em}}
.gloss{{margin:6px 0 0;font-size:13px;line-height:1.65}}
.gloss dt{{font-weight:650;margin:12px 0 2px;color:var(--ink)}}
.gloss dd{{margin:0;color:#3A424C}}
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
<p class="sub" id="mapsub">路線依「實際與模型之時間差」著色：紅為較慢，綠為較快。
模型＝以你本人過往 FIT 記錄擬合的「坡度—速度」關係：同一坡度你平常跑得多快，再逐段換算應需時間。</p>
{map_block(gj, has_dtm, dem_tiles)}

<h2>分段表現</h2>
<p class="sub">各公里相對模型之時間差；紅色表示該段耗時高於模型預期。</p>
{svg_profile(segs)}
<p class="hint">上柱＝慢於模型，下柱＝快於模型；最大差距 {max(abs(x['delta_s']) for x in segs)} 秒。</p>

{terrain_block}

<h2>待改善路段</h2>
<ul>{worst_li}</ul>

<h2>分段數據</h2>
<table><thead><tr><th>公里</th><th>坡度</th><th>爬升 m</th><th>時間</th>
<th>與模型差（秒）</th><th>心率</th><th>步頻</th></tr></thead>
<tbody>{rows}</tbody></table>

<h2>訓練建議</h2>
<ul>{"".join(f"<li>{t}</li>" for t in tips)}</ul>

<h2>名詞解釋</h2>
<dl class="gloss">
<dt>LTHR（Lactate Threshold Heart Rate，乳酸閾值心率）</dt>
<dd>身體由「可持續」轉為「快速累積乳酸」的分界心率。低於此值可長時間維持；高於此值只能撐數十分鐘。本報告用它換算每次訓練的相對強度。</dd>
<dt>模型（坡度—速度模型）</dt>
<dd>以你本人過往 FIT 記錄擬合：每個坡度區間你平均跑多快。用同一條路線逐段換算「應需時間」，再與實際時間比較。它是你自己的基準，不是通用公式。</dd>
<dt>TRI（Terrain Ruggedness Index，地形粗糙度指數）</dt>
<dd>Riley (1999)：每個像素與周圍八格高差的均方根，單位為米。數值越大，地面越破碎（石級、沖溝、亂石）。本報告以 3 米 LiDAR 裸地 DTM 計算。</dd>
<dt>p90（第 90 百分位）</dt>
<dd>把全部路段的數值由小至大排列，九成路段低於此值。用中位數看「典型情況」，用 p90 看「最差的一成」。</dd>
<dt>r（皮爾森相關係數）</dt>
<dd>兩個數列同向變化的程度，範圍 −1 至 +1。+1 完全同步、0 無關、−1 完全反向。|r| 低於 0.3 一般視為關係微弱。</dd>
<dt>後段效率變化（decoupling）</dt>
<dd>比較前段與後段的「速度 ÷ 心率」。正值代表同樣心率跑得更慢，即耐力開始下滑；負值代表後段反而更有效率。已剔除頭 10 分鐘熱身。</dd>
<dt>爬升密度</dt>
<dd>總爬升 ÷ 總距離，單位 m/km。它反映路線的陡峭程度，用來判斷一次練習是否接近目標賽道的需求。</dd>
</dl>

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
    ap.add_argument("--dtm", help="Esri ASCII bare-earth DTM (adds terrain ruggedness)")
    ap.add_argument("--dem-tiles", help="baked terrarium tiles (bake_dem.py) for the 3D view")
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

    asc = core.load_asc(a.dtm) if a.dtm else None
    gj = route_features(recs, table, asc=asc)
    dem = json.load(open(a.dem_tiles)) if a.dem_tiles else None
    out = build(rep, prof, segs, gj, asc is not None, dem)
    open(a.out, "w", encoding="utf-8").write(out)
    print(f"wrote {a.out} ({len(out)/1024:.0f} KB) · {len(segs)} km · "
          f"{len(gj['features'])} route segments")


if __name__ == "__main__":
    main()
