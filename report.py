#!/usr/bin/env python3
"""One command: FIT -> honest trail-run report (JSON + markdown).

    python report.py activity.fit [--gpx course.gpx] [--json out.json]

Needs fitdecode. Deliberately one file, no framework, no DB.
"""
import argparse, collections, json, math, sys
import fitdecode

W = 15  # legacy: samples each side (unused; grade is distance-based now)
GRADE_WINDOW_M = 40.0   # metres each side. A sample window would smooth 27 m at
                        # walking pace but 126 m at 4.2 m/s, which biases the
                        # uphill bins against the downhill ones.
WARMUP_SKIP_S = 600      # ignore the first 10 min: optical HR lags and drifts up


def mean(xs):
    v = [x for x in xs if x is not None]
    return sum(v) / len(v) if v else None


def load(path):
    recs, sess = [], {}
    with fitdecode.FitReader(path, check_crc=fitdecode.CrcCheck.DISABLED) as f:
        for fr in f:
            if fr.frame_type != fitdecode.FIT_FRAME_DATA:
                continue
            d = {fl.name: fl.value for fl in fr.fields}
            if fr.name == "session":
                sess = d
            elif fr.name == "record":
                # brand-agnostic: some devices only write speed/altitude,
                # others only the enhanced_* pair
                dist = d.get("distance")
                alt = d.get("enhanced_altitude")
                if alt is None:
                    alt = d.get("altitude")
                spd = d.get("enhanced_speed")
                if spd is None:
                    spd = d.get("speed")
                if None in (dist, alt, spd):
                    continue
                lat = d.get("position_lat")
                lon = d.get("position_long")
                recs.append((dist, alt, spd,
                             d.get("heart_rate"), d.get("cadence"), d.get("power"),
                             d.get("timestamp"),
                             lat * 180 / 2 ** 31 if lat is not None else None,
                             lon * 180 / 2 ** 31 if lon is not None else None))
    if not recs:
        raise SystemExit(f"no usable records in {path} — need distance, altitude and speed "
                         f"(enhanced or standard fields)")
    if len(recs) < 120:
        raise SystemExit(f"only {len(recs)} records in {path} — too short to model anything")
    return recs, sess


def grade_at(r, i, window_m=GRADE_WINDOW_M):
    """Grade over a fixed DISTANCE window, so smoothing does not depend on speed."""
    d0 = r[i][0]
    a, steps = i, 0
    while a > 0 and d0 - r[a][0] < window_m and steps < 500:
        a -= 1
        steps += 1
    b, steps = i, 0
    while b < len(r) - 1 and r[b][0] - d0 < window_m and steps < 500:
        b += 1
        steps += 1
    dd = r[b][0] - r[a][0]
    return None if dd < 5 else (r[b][1] - r[a][1]) / dd


def grade_table(recs):
    bins = collections.defaultdict(list)
    for i, x in enumerate(recs):
        g = grade_at(recs, i)
        if g is None or x[2] < 0.8:
            continue
        bins[round(g * 20) / 20].append(x)
    out = []
    for g in sorted(bins):
        v = bins[g]
        if len(v) < 60:
            continue
        sp = mean([x[2] for x in v])
        out.append(dict(grade=round(g, 2), n=len(v), kmh=round(sp * 3.6, 2),
                        sec_per_km=round(1000 / sp), hr=round(mean([x[3] for x in v]) or 0),
                        cadence=round((mean([x[4] for x in v]) or 0) * 2),
                        watts=round(mean([x[5] for x in v]) or 0)))
    return out


def thirds(recs, skip_first_s=WARMUP_SKIP_S):
    """Flat moving samples in thirds, excluding warm-up (HR lag dominates otherwise)."""
    if recs[0][6] is None:
        return []
    t0 = recs[0][6]
    flat = [x for i, x in enumerate(recs)
            if x[6] is not None and (x[6] - t0).total_seconds() >= skip_first_s
            and (g := grade_at(recs, i)) is not None
            and abs(g) < 0.02 and x[2] > 0.8 and x[3]]
    n = len(flat) // 3
    if n < 60:
        return []
    return [dict(speed_kmh=round(mean([x[2] for x in p]) * 3.6, 2),
                 hr=round(mean([x[3] for x in p])))
            for p in (flat[:n], flat[n:2 * n], flat[2 * n:])]


def decoupling(t):
    """Aerobic decoupling = change in efficiency (speed per heartbeat).

    Efficiency factor EF = speed / heart rate. Decoupling is the fractional
    *drop* in EF from the first to the last third, so **positive = faded**
    (same speed now costs more beats) and negative = efficiency improved.
    Comparing an HR ratio against a pace ratio directly double-counts.
    """
    if len(t) < 3 or not t[0]["hr"] or not t[-1]["hr"]:
        return None
    ef = [x["speed_kmh"] / x["hr"] for x in t]
    return round((ef[0] - ef[-1]) / ef[0] * 100, 1)


def speed_lookup(table, min_bins=1):
    """Interpolating grade->speed lookup. Nearest-bin snapping is up to ~10%
    wrong at a bin edge, so every consumer must use the same interpolation."""
    speeds = {t["grade"]: t["kmh"] / 3.6 for t in table}
    if len(speeds) < min_bins:
        return None
    ks = sorted(speeds)

    def f(g):
        if len(ks) == 1:
            return speeds[ks[0]]      # flat-only run: one bin is the whole truth
        g = max(ks[0], min(ks[-1], g))
        if g in speeds:
            return speeds[g]
        for lo, hi in zip(ks, ks[1:]):
            if lo <= g <= hi:
                t = (g - lo) / (hi - lo)
                return speeds[lo] * (1 - t) + speeds[hi] * t
        return speeds[ks[-1]]
    return f


def bins_100m(recs, lookup, step=100.0):
    """Exact fixed-distance bins carrying geometry and time-vs-model.

    A bin closes ON the step boundary: the crossing sample interval is split
    proportionally in distance, climb and time, and the remainder opens the next
    bin. Without the split a bin can be up to one sample long (measured: 202 m
    for a 100 m target), which silently mixes two terrains into one row.
    """
    out = []
    cur = dict(a=0.0, m=0.0, dpl=0.0, gs=0.0, dist=0.0, coords=[], chain=0.0)
    i = 1
    while i < len(recs):
        a, b = recs[i - 1], recs[i]
        if a[7] is None or b[7] is None:
            i += 1
            continue
        total = b[0] - a[0]
        if total > 300:                     # GPS dropout, not distance
            cur = dict(a=0.0, m=0.0, dpl=0.0, gs=0.0, dist=0.0,
                       coords=[[b[8], b[7]]], chain=b[0])
            i += 1
            continue
        if not cur["coords"]:
            cur["coords"] = [[a[8], a[7]]]
            cur["chain"] = a[0]
        g = grade_at(recs, i) or 0
        speed = b[2] if b[2] > 0.5 else lookup(g)
        left = total
        pos_lat, pos_lon, pos_ele, pos_d = a[7], a[8], a[1], a[0]
        while left > 1e-9:
            take = min(left, step - cur["dist"])
            f = take / total
            de = (b[1] - a[1]) * f
            cur["dist"] += take
            cur["a"] += take / speed
            cur["m"] += take / lookup(g)
            cur["dpl"] += max(0.0, de)
            cur["gs"] += take * g
            pos_lat += (b[7] - a[7]) * f
            pos_lon += (b[8] - a[8]) * f
            pos_ele += de
            pos_d += take
            cur["coords"].append([pos_lon, pos_lat])
            if cur["dist"] >= step - 1e-6:
                out.append(dict(chainage_m=round(pos_d),
                                length_m=round(cur["dist"], 1),
                                grade_pct=round(cur["gs"] / cur["dist"] * 100, 1),
                                d_plus_m=round(cur["dpl"]), pred_s=round(cur["m"]),
                                act_s=round(cur["a"]),
                                delta_s=round(cur["a"] - cur["m"]),
                                coords=cur["coords"]))
                cur = dict(a=0.0, m=0.0, dpl=0.0, gs=0.0, dist=0.0,
                           coords=[[pos_lon, pos_lat]], chain=pos_d)
            left -= take
        i += 1
    if cur["dist"] >= 20 and len(cur["coords"]) >= 2:      # trailing partial bin
        out.append(dict(chainage_m=round(recs[-1][0]), length_m=round(cur["dist"], 1),
                        grade_pct=round(cur["gs"] / cur["dist"] * 100, 1),
                        d_plus_m=round(cur["dpl"]), pred_s=round(cur["m"]),
                        act_s=round(cur["a"]), delta_s=round(cur["a"] - cur["m"]),
                        coords=cur["coords"]))
    return out


def load_asc(path):
    """Minimal Esri ASCII Grid reader (stdlib only). Rows stored north-first."""
    meta, rows = {}, []
    with open(path) as fh:
        for line in fh:
            parts = line.split()
            if not parts:
                continue
            key = parts[0].lower()
            if key in ("ncols", "nrows", "xllcorner", "yllcorner", "cellsize",
                       "dx", "dy", "nodata_value", "xllcenter", "yllcenter"):
                meta[key] = float(parts[1])
            else:
                rows.append([float(v) for v in parts])
    # GDAL writes dx/dy instead of cellsize; the grid is square enough to average
    if "cellsize" not in meta and ("dx" in meta or "dy" in meta):
        meta["cellsize"] = meta.get("dx", meta.get("dy"))
    if "xllcenter" in meta:
        meta["xllcorner"] = meta["xllcenter"] - meta["cellsize"] / 2
    if "yllcenter" in meta:
        meta["yllcorner"] = meta["yllcenter"] - meta["cellsize"] / 2
    meta["rows"] = rows
    meta["nodata"] = meta.get("nodata_value", -9999)
    return meta


def tri_at(asc, lat, lon):
    """Riley (1999) terrain ruggedness index at one cell: RMS of the 8 neighbour
    differences. Metres, so it reads directly against climb and distance."""
    rows = asc["rows"]
    cx = asc.get("dx") or asc["cellsize"]      # degrees of longitude per cell
    cy = asc.get("dy") or asc["cellsize"]      # degrees of latitude per cell
    col = int((lon - asc["xllcorner"]) / cx)
    row = len(rows) - 1 - int((lat - asc["yllcorner"]) / cy)
    if not (1 <= row < len(rows) - 1 and 1 <= col < len(rows[0]) - 1):
        return None
    z = rows[row][col]
    if z == asc["nodata"]:
        return None
    tot, n = 0.0, 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr or dc:
                v = rows[row + dr][col + dc]
                if v != asc["nodata"]:
                    tot += (v - z) ** 2
                    n += 1
    return math.sqrt(tot / n) if n else None


def terrain_rows(recs, table, step=100.0, asc=None, remarks=None):
    """CSV rows: where the time went, bin by bin. No DEM, so no terrain index."""
    lookup = speed_lookup(table)
    if lookup is None:
        return []
    rows = []
    for b in bins_100m(recs, lookup, step):
        frac = b["delta_s"] / b["act_s"] if b["act_s"] else 0
        row = dict(
            chainage_m=b["chainage_m"], length_m=b["length_m"], grade_pct=b["grade_pct"],
            d_plus_m=b["d_plus_m"], pred_s=b["pred_s"], act_s=b["act_s"],
            delta_s=b["delta_s"], delta_pct=round(frac * 100, 1),
            class_=("slow" if frac > 0.05 else "fast" if frac < -0.05 else "on-model"))
        if asc:
            mid = b["coords"][len(b["coords"]) // 2]
            tri = tri_at(asc, mid[1], mid[0])   # coords are [lon, lat]
            row["terrain_index_m"] = round(tri, 1) if tri is not None else ""
        if remarks:
            note = next((r["note"] for r in remarks
                         if r["from_m"] <= b["chainage_m"] <= r["to_m"]), "")
            row["remark"] = note         # only present when the athlete supplied one
        rows.append(row)
    return rows


def read_gpx(gpx):
    """[(lat, lon, ele)] — refuses a course without elevation."""
    import xml.etree.ElementTree as ET
    ns = "{http://www.topografix.com/GPX/1/1}"
    pts = []
    for p in ET.parse(gpx).getroot().iter(ns + "trkpt"):
        ele = p.find(ns + "ele")
        if p.get("lat") is None or ele is None:
            raise SystemExit(f"{gpx}: track points need lat/lon and <ele>; "
                             f"refusing to project without elevation")
        pts.append((float(p.get("lat")), float(p.get("lon")), float(ele.text)))
    if len(pts) < 2:
        raise SystemExit(f"{gpx}: no track points")
    return pts


PROFILE_FIELDS = {
    "goal": "selects the assessment benchmark and the report's emphasis",
    "event": "names the target race in the report",
    "event_date": "enables the countdown",
    "distance_km": "with d_plus_m, gives the event's own vertical benchmark",
    "d_plus_m": "with distance_km, gives the event's own vertical benchmark",
    "target_hours": "turns the projection into a plan, not a number",
    "weekly_hours": "keeps the advice inside the athlete's week",
    "lthr": "intensity judgement and heart-rate zones (otherwise declined)",
    "sensors": "decides which metrics are trustworthy",
}


def audit_profile(prof):
    """What is missing, and what each missing field blocks."""
    missing = [(k, why) for k, why in PROFILE_FIELDS.items() if not prof.get(k)]
    if not missing:
        print("profile complete — every section can be computed")
        return 0
    print(f"{len(missing)} missing field(s):")
    for k, why in missing:
        print(f"  {k:<13} -> {why}")
    return 1


def history(folder, lthr=None):
    """Weekly load and intensity distribution across every FIT in a folder."""
    import glob, os
    rows = []
    for f in sorted(glob.glob(os.path.join(folder, "*.fit"))):
        try:
            recs, s = load(f)
        except SystemExit as e:
            print(f"  skip {os.path.basename(f)}: {e}")
            continue
        rows.append(dict(
            date=recs[0][6].date() if recs[0][6] else None,
            km=(s.get("total_distance") or recs[-1][0]) / 1000,
            dplus=s.get("total_ascent") or 0,
            hours=(s.get("total_timer_time") or 0) / 3600,
            hr=s.get("avg_heart_rate"),
            samples=[x[3] for x in recs if x[3]]))

    if not rows:
        print(f"no FIT files in {folder}")
        return 1

    weeks = collections.defaultdict(list)
    for r in rows:
        key = r["date"].isocalendar()[:2] if r["date"] else ("?", 0)
        weeks[key].append(r)

    print(f"{'week':<10}{'runs':>5}{'km':>8}{'D+':>7}{'hours':>7}{'avg HR':>8}")
    for key in sorted(weeks):
        rs = weeks[key]
        hrs = [r["hr"] for r in rs if r["hr"]]
        print(f"{key[0]}-W{key[1]:02d}:{'':<2}{len(rs):>5}{sum(r['km'] for r in rs):>8.1f}"
              f"{sum(r['dplus'] for r in rs):>7.0f}{sum(r['hours'] for r in rs):>7.1f}"
              f"{(sum(hrs)/len(hrs) if hrs else 0):>8.0f}")

    if lthr:
        bands = [0] * 5
        n = 0
        for r in rows:
            for hr in r["samples"]:
                p = hr / lthr
                i = 0 if p < 0.75 else 1 if p < 0.85 else 2 if p < 0.92 else 3 if p < 1.0 else 4
                bands[i] += 1
                n += 1
        names = ["Z1 <75%", "Z2 75-85%", "Z3 85-92%", "Z4 92-100%", "Z5 >100%"]
        if n:
            print("\nintensity distribution (share of moving seconds):")
            for nm, c in zip(names, bands):
                print(f"  {nm:<12}{c / n * 100:5.1f}%")
    else:
        print("\nno lthr supplied -> intensity distribution skipped (no guessing)")
    return 0


def course_stats(gpx):
    """The course on its own: distance, climb, grade profile. No personal curve needed."""
    pts = read_gpx(gpx)

    def hav(a, b):
        R = 6371.0
        la1, lo1 = map(math.radians, a[:2])
        la2, lo2 = map(math.radians, b[:2])
        h = (math.sin((la2 - la1) / 2) ** 2
             + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
        return 2 * R * math.asin(math.sqrt(h)) * 1000

    bins, dd, dr = [], 0.0, 0.0
    for i in range(len(pts) - 1):
        step = hav(pts[i], pts[i + 1])
        rise = pts[i + 1][2] - pts[i][2]
        dd += step
        dr += rise
        if dd >= 100:
            bins.append((dd, dr))     # accumulate the whole bin, not the last step
            dd = dr = 0.0
    km = sum(b[0] for b in bins)
    up = sum(max(0.0, b[1]) for b in bins)
    bands = {"陡上 >10%": 0.0, "緩上 3–10%": 0.0, "平 -3–3%": 0.0,
             "緩落 -10–-3%": 0.0, "陡落 <-10%": 0.0}
    for d, r in bins:
        g = r / d if d else 0
        key = ("陡上 >10%" if g > 0.10 else "緩上 3–10%" if g > 0.03 else
               "陡落 <-10%" if g < -0.10 else "緩落 -10–-3%" if g < -0.03 else "平 -3–3%")
        bands[key] += d / 1000
    # steepest sustained kilometre
    win, best, run = 10, (0.0, 0), 0.0
    for i in range(len(bins) - win):
        r = sum(bins[j][1] for j in range(i, i + win))
        dsum = sum(bins[j][0] for j in range(i, i + win))
        if dsum and r / dsum > best[0]:
            best = (r / dsum, i)
    return dict(course_km=round(km / 1000, 1), course_d_plus=round(up),
                density=round(up / (km / 1000)) if km else 0,
                bands={k: round(v / (km / 1000) * 100) for k, v in bands.items() if v},
                steepest_km_pct=round(best[0] * 100, 1))


def course_fit(table, gpx):
    """Predict moving time on a course using this athlete's own grade->speed curve."""
    pts = read_gpx(gpx)

    def hav(a, b):
        R = 6371.0
        la1, lo1 = map(math.radians, a[:2])
        la2, lo2 = map(math.radians, b[:2])
        h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
        return 2 * R * math.asin(math.sqrt(h)) * 1000

    seg = [(hav(pts[i], pts[i + 1]), pts[i + 1][2] - pts[i][2]) for i in range(len(pts) - 1)]
    lookup = speed_lookup(table, min_bins=3)
    if lookup is None:
        return None      # fewer than three grade bins cannot describe a course

    moving = 0.0
    km = dp = 0.0
    i, band = 0, collections.defaultdict(float)
    while i < len(seg):
        dd = de = 0.0
        while i < len(seg) and dd < 100:
            dd += seg[i][0]
            de += seg[i][1]
            i += 1
        if dd < 20:
            continue
        g = de / dd
        moving += dd / lookup(g)
        km += dd
        dp += max(0, de)
        band["up" if g > 0.05 else "down" if g < -0.05 else "flat"] += dd / lookup(g)
    return dict(course_km=round(km / 1000, 1), course_d_plus=round(dp),
                moving_h=round(moving / 3600, 2),
                with_15pct_stops_h=round(moving / 0.85 / 3600, 2),
                time_share={k: round(v / moving * 100) for k, v in band.items()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fit", nargs="?")
    ap.add_argument("--gpx")
    ap.add_argument("--json")
    ap.add_argument("--course", help="analyse a GPX on its own, no FIT needed")
    ap.add_argument("--history", help="folder of FIT files: weekly load + intensity split")
    ap.add_argument("--terrain", help="write per-100 m attribution CSV here")
    ap.add_argument("--dtm", help="Esri ASCII grid for terrain_index (CSDI/LandSD or your own)")
    ap.add_argument("--remarks", help="JSON [{from_m,to_m,note}] from the athlete, optional")
    ap.add_argument("--audit-profile", help="list missing profile fields and what they block")
    ap.add_argument("--lthr", type=float, help="lactate-threshold HR for the history split")
    a = ap.parse_args()

    if a.audit_profile:
        sys.exit(audit_profile(json.load(open(a.audit_profile))))
    if a.history:
        sys.exit(history(a.history, a.lthr))
    if a.course:
        c = course_stats(a.course)
        print(f"{c['course_km']} km  {c['course_d_plus']} m D+  "
              f"({c['density']} m/km, steepest km {c['steepest_km_pct']}%)")
        print("time share by grade: " + "  ".join(f"{k} {v}%" for k, v in c["bands"].items()))
        print("\nProjection needs an activity FIT: the curve is the athlete's own, not a formula.")
        return

    recs, s = load(a.fit)
    dur = (recs[-1][6] - recs[0][6]).total_seconds()
    dist = s.get("total_distance", recs[-1][0])
    g = grade_table(recs)
    t = thirds(recs)
    rep = dict(
        file=a.fit,
        device=s.get("product_name") or s.get("manufacturer"),
        sport=f"{s.get('sport')}/{s.get('sub_sport')}",
        disclaimer="Reference only, not medical advice. Wearable sensor error applies; "
                   "training and injury risk remain the user's own responsibility.",

        distance_km=round(dist / 1000, 2),
        elapsed_hms=f"{int(dur // 3600)}:{int(dur % 3600 // 60):02d}:{int(dur % 60):02d}",
        moving_s=round(s.get("total_timer_time", dur)),
        avg_pace_s_per_km=round((s.get("total_timer_time") or dur) / (dist / 1000)),
        avg_hr=s.get("avg_heart_rate"), max_hr=s.get("max_heart_rate"),
        avg_cadence_spm=round((s.get("avg_running_cadence") or 0) * 2),
        avg_power=s.get("avg_power"),
        ascent=s.get("total_ascent"), descent=s.get("total_descent"),
        calories=s.get("total_calories"),
        gait_fields_present=bool(s.get("avg_stance_time") or s.get("avg_vertical_oscillation")),
        grade_table=g,
        flat_thirds=t,
        decoupling_pct=decoupling(t),
    )
    if a.gpx:
        rep["course_projection"] = course_fit(g, a.gpx)

    if a.terrain:
        asc = load_asc(a.dtm) if a.dtm else None
        remarks = json.load(open(a.remarks)) if a.remarks else None
        rows = terrain_rows(recs, g, asc=asc, remarks=remarks)
        if not rows:
            raise SystemExit("no grade table — too short to attribute time")
        import csv
        with open(a.terrain, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        slow = sum(r["delta_s"] for r in rows if r["class_"] == "slow")
        fast = sum(r["delta_s"] for r in rows if r["class_"] == "fast")
        print(f"\nterrain csv: {len(rows)} bins -> {a.terrain}")
        print(f"  slow bins +{slow}s, fast bins {fast}s, net {slow + fast:+}s")

    if a.json:
        json.dump(rep, open(a.json, "w"), indent=2, default=str)

    print(f"{rep['sport']}  {rep['distance_km']} km  {rep['elapsed_hms']}  "
          f"{rep['ascent']} m D+  HR {rep['avg_hr']}  cad {rep['avg_cadence_spm']} spm")
    print(f"\n{'grade':>6} {'km/h':>6} {'pace':>7} {'HR':>4} {'cad':>4} {'W':>4}")
    for r in g:
        print(f"{r['grade']*100:+5.0f}% {r['kmh']:6.2f} "
              f"{r['sec_per_km']//60}:{r['sec_per_km']%60:02d} {r['hr']:4d} {r['cadence']:4d} {r['watts']:4d}")
    if t:
        print("\nflat thirds: " + " | ".join(f"{x['speed_kmh']} km/h @ {x['hr']}" for x in t)
              + f"  -> decoupling {rep['decoupling_pct']}%")
    if "course_projection" in rep:
        c = rep["course_projection"]
        print(f"\ncourse {c['course_km']} km / {c['course_d_plus']} m D+ -> "
              f"moving {c['moving_h']} h, with 15% stops {c['with_15pct_stops_h']} h "
              f"{c['time_share']}")
    print(f"\ngait dynamics: {'YES' if rep['gait_fields_present'] else 'NO (wrist only)'}")
    print("\n" + "-" * 64)
    print("Reference only — not medical advice.")
    print("GPS / optical HR / barometric altitude all carry error; trend > absolute value.")
    print("Training & racing decisions, and injury risk, are the user's own responsibility.")
    print("Pain is a stop signal, not a data point.", end="\n\n")


if __name__ == "__main__":
    main()
