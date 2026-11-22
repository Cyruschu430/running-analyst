#!/usr/bin/env python3
"""Mock athletes with realistic, self-consistent activity data.

Why: one real FIT file proves nothing about reliability. These personas are
synthetic — the physics is simple and the numbers are made up — but each one is
internally consistent (distance, climb, pace, HR and drift all agree), so the
pipeline can be exercised against a beginner, a road marathoner, a trail
runner, an ultra runner and an injured athlete without touching personal data.

Record layout matches report.load(): (dist_m, alt_m, speed_m_s, hr, cadence,
power, timestamp, lat, lon).
"""
import datetime as dt
import math

# name, profile, activity shape
PERSONAS = [
    dict(
        name="Rookie 10K",
        profile=dict(athlete="Mock Rookie", goal="10k_road", event="City 10K",
                     event_date="2027-03-14", distance_km=10, d_plus_m=40,
                     target_hours=0.95, weekly_hours=4, days_per_week=3,
                     weekly_km=18, longest_run_h=0.9, weight_kg=72, age=32,
                     schedule=dict(work_days=[1, 2, 3, 4, 5], weekday_max_minutes=45,
                                   long_day="Sun", days_per_week=3)),
        run=dict(km=10.0, d_plus=45, flat_pace_s=345, hr_easy=148, drift=0.04,
                 grade_amp=0.012, seed=11)),
    dict(
        name="Marathon sub-4",
        profile=dict(athlete="Mock Marathoner", goal="marathon_road", event="HK Marathon",
                     event_date="2027-02-07", distance_km=42.195, d_plus_m=320,
                     target_hours=3.92, weekly_hours=8, days_per_week=5,
                     weekly_km=55, longest_run_h=2.5, weight_kg=61, age=38, lthr=171,
                     schedule=dict(work_days=[1, 2, 3, 4, 5], weekday_max_minutes=70,
                                   long_day="Sun", days_per_week=5)),
        run=dict(km=24.0, d_plus=180, flat_pace_s=305, hr_easy=152, drift=0.06,
                 grade_amp=0.008, seed=22)),
    dict(
        name="Half trail",
        profile=dict(athlete="Mock Trail", goal="half_trail", event="Trail Half",
                     event_date="2027-04-11", distance_km=21, d_plus_m=1100,
                     target_hours=2.6, weekly_hours=6, days_per_week=4,
                     weekly_km=42, longest_run_h=2.2, weight_kg=66, age=29, lthr=176,
                     schedule=dict(work_days=[1, 2, 3, 4, 5], weekday_max_minutes=60,
                                   long_day="Sat", days_per_week=4)),
        run=dict(km=21.0, d_plus=1050, flat_pace_s=330, hr_easy=155, drift=0.05,
                 grade_amp=0.05, seed=33)),
    dict(
        name="Ultra 100K",
        profile=dict(athlete="Mock Ultra", goal="ultra_trail", event="HK100 2027",
                     event_date="2027-01-23", distance_km=96, d_plus_m=5142,
                     target_hours=16, weekly_hours=10, days_per_week=6,
                     weekly_km=70, longest_run_h=4.0, weight_kg=60, age=41, lthr=168,
                     schedule=dict(work_days=[1, 2, 3, 4, 5], weekday_max_minutes=75,
                                   long_day="Sun", days_per_week=6)),
        run=dict(km=42.0, d_plus=2200, flat_pace_s=330, hr_easy=150, drift=0.07,
                 grade_amp=0.06, seed=44)),
    dict(
        name="Injured (knee)",
        profile=dict(athlete="Mock Injured", goal="marathon_road", event="HK Marathon",
                     event_date="2027-02-07", distance_km=42.195, d_plus_m=320,
                     target_hours=4.5, weekly_hours=6, days_per_week=3,
                     weekly_km=30, longest_run_h=1.5, weight_kg=70, age=35,
                     health="左膝痛，上樓梯有痛",
                     schedule=dict(work_days=[1, 2, 3, 4, 5], weekday_max_minutes=60,
                                   long_day="Sun", days_per_week=3)),
        run=dict(km=8.0, d_plus=60, flat_pace_s=370, hr_easy=150, drift=0.03,
                 grade_amp=0.01, seed=55)),
]


def make_activity(spec, start=(22.200, 114.100)):
    """1 Hz records that satisfy the run spec's distance and climb.

    ponytail: fixed 1 Hz, no pauses — enough to exercise every code path, and
    any timing artefact it introduces is the same one every persona gets.
    """
    km = spec["km"]
    target_dp = spec["d_plus"]
    amp = spec["grade_amp"]
    flat_v = 1000.0 / spec["flat_pace_s"]

    # grade as two sines; scale so the positive area matches the requested climb
    def raw_grade(d):
        return (math.sin(2 * math.pi * d / 900.0) * 0.6
                + math.sin(2 * math.pi * d / 2300.0 + 1.1) * 0.4)

    steps = 4000
    step_m = km * 1000 / steps
    pos = sum(max(0.0, raw_grade(i * step_m)) * step_m for i in range(steps))
    scale = (target_dp / pos) if pos else 0.0

    def grade(d):
        return raw_grade(d) * scale

    recs = []
    d, ele = 0.0, 12.0
    lat, lon = start
    t = 0
    while d < km * 1000:
        g = grade(d)
        # uphill costs more than downhill returns; capped so descents stay sane
        v = flat_v / (1 + 5.2 * g) if g >= 0 else flat_v * min(1.18, 1 - 1.6 * g)
        v = max(0.6, v)
        climb = min(1.0, max(0.0, g) * 9)          # capped so HR stays physiological
        hr = spec["hr_easy"] + 26 * climb + spec["drift"] * 14 * (d / (km * 1000))
        hr = max(95, min(188, hr))
        cad = int(178 - 30 * max(0.0, g) + 4 * min(0.0, g))
        # 1 degree latitude ≈ 111 km; bearing 40° keeps the track on land
        step = v
        lat += step * math.cos(math.radians(40)) / 111000.0
        lon += step * math.sin(math.radians(40)) / 102000.0
        recs.append((round(d, 2), round(ele, 2), round(v, 3), int(hr), cad,
                     int(150 + 60 * v / flat_v),
                     dt.datetime(2026, 1, 1) + dt.timedelta(seconds=t),
                     round(lat, 7), round(lon, 7)))
        ele += g * step
        d += step
        t += 1
    return recs


def without_gps(recs):
    return [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], None, None) for r in recs]


def without_hr(recs):
    return [(r[0], r[1], r[2], None, r[4], r[5], r[6], r[7], r[8]) for r in recs]


if __name__ == "__main__":
    for p in PERSONAS:
        r = make_activity(p["run"])
        print(f"{p['name']:<18} {len(r):>5} records  {r[-1][0] / 1000:.1f} km  "
              f"HR {r[0][3]}→{r[-1][3]}")
