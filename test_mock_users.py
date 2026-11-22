#!/usr/bin/env python3
"""Run the whole pipeline against five mock athletes and one broken dataset.

Not a unit test of one function: each persona goes in as an activity and a
profile, and everything that a user would see is checked for internal
consistency. A failure here is a failure a real athlete would hit.

    python test_mock_users.py
"""
import datetime as dt
import json
import math
import sys

import mock_users
import nutrition
import plan as plan_mod
import report as core

STEP = 100.0
TODAY = dt.date(2026, 11, 15)


def profile_for(p):
    """Persona shorthand -> the shape plan.build() expects."""
    raw = dict(p["profile"])          # pop() below must not eat the fixture
    prof = dict(raw)
    prof["current"] = dict(weekly_km=raw.pop("weekly_km", None),
                           longest_run_h=raw.pop("longest_run_h", None))
    prof["schedule"] = dict(raw["schedule"])
    return prof


def reconcile(recs, bins):
    """Bins must add up to the activity, not to something adjacent to it."""
    elapsed = sum(max(0.0, (b[6] - a[6]).total_seconds())
                  for a, b in zip(recs, recs[1:]) if a[6] and b[6])
    act = sum(b["act_s"] for b in bins)
    dplus = sum(b["d_plus_m"] for b in bins)
    climb = sum(max(0.0, b[1] - a[1]) for a, b in zip(recs, recs[1:]))
    return dict(
        time_pct=abs(act - elapsed) / elapsed * 100 if elapsed else 0,
        climb_pct=abs(dplus - climb) / climb * 100 if climb else 0,
    )


def check_persona(p):
    recs = mock_users.make_activity(p["run"])
    table = core.grade_table(recs)
    dec = core.decoupling(core.thirds(recs))
    lookup = core.speed_lookup(table)
    assert lookup is not None, f"{p['name']}: no speed lookup"
    bins = core.bins_100m(recs, lookup, STEP)
    assert bins, f"{p['name']}: no bins"

    # geometry: every interior bin is exactly STEP long, coordinates are [lon, lat]
    lengths = [b["length_m"] for b in bins[:-1]]
    assert all(abs(x - STEP) < 0.2 for x in lengths), \
        f"{p['name']}: bin length drift {min(lengths)}..{max(lengths)}"
    lons = [c[0] for b in bins for c in b["coords"]]
    lats = [c[1] for b in bins for c in b["coords"]]
    assert 113.8 < min(lons) and max(lons) < 114.6, f"{p['name']}: lon out of HK {min(lons)}"
    assert 22.1 < min(lats) and max(lats) < 22.6, f"{p['name']}: lat out of HK {min(lats)}"

    rec = reconcile(recs, bins)
    assert rec["time_pct"] < 3.0, f"{p['name']}: time mismatch {rec['time_pct']:.1f}%"
    assert rec["climb_pct"] < 10.0, f"{p['name']}: climb mismatch {rec['climb_pct']:.1f}%"
    assert dec is not None and math.isfinite(dec) and abs(dec) < 40, \
        f"{p['name']}: decoupling {dec}"

    prof = profile_for(p)
    built = plan_mod.build(prof, [], TODAY)
    weeks = built["plan"]
    assert len(weeks) >= 4, f"{p['name']}: only {len(weeks)} weeks"
    n_days = prof["schedule"]["days_per_week"]

    for w in weeks:
        runs = [s for s in w["sessions"] if s["type"] != "strength"]
        if w["phase"] == "race":
            assert w["km_target"] > 0
            continue
        if w["phase"] == "taper":
            assert 0 < len(runs) <= n_days, f"{p['name']}: taper has {len(runs)} runs"
        else:
            assert len(runs) == n_days, f"{p['name']}: {len(runs)} runs vs {n_days} days"
        assert w["hours"] > 0 and w["km_target"] > 0, f"{p['name']}: empty week"
        if p["name"].startswith("Injured"):
            assert not [s for s in w["sessions"] if s["zone"] in ("Z3-Z4", "Z5")], \
                f"{p['name']}: intensity prescribed despite injury"

    if p["name"].startswith("Injured"):
        assert built.get("health_gate"), "injured persona has no health gate"

    # same input, same plan — every time
    again = plan_mod.build(profile_for(p), [], TODAY)
    assert json.dumps(built, sort_keys=True) == json.dumps(again, sort_keys=True), \
        f"{p['name']}: plan is not deterministic"

    t = nutrition.targets(prof["weight_kg"], prof["target_hours"])
    g_h = t["race_carb_g_h"]
    assert 60 <= g_h[0] <= g_h[1] <= 90, f"{p['name']}: race carbs {g_h}"
    rows = nutrition.race_week(t, prof["target_hours"])
    assert len(rows) >= 5 and all(r["carbs_g"] for r in rows)

    return dict(name=p["name"], bins=len(bins), km=round(recs[-1][0] / 1000, 1),
                time_pct=round(rec["time_pct"], 1), climb_pct=round(rec["climb_pct"], 1),
                dec=round(dec, 1), weeks=len(weeks),
                hours=round(sum(w["hours"] for w in weeks if w["phase"] != "race"), 1),
                carbs=g_h)


def check_degraded():
    """Missing sensors must degrade, not crash."""
    recs = mock_users.make_activity(mock_users.PERSONAS[1]["run"])
    table = core.grade_table(recs)
    lookup = core.speed_lookup(table)

    no_gps = mock_users.without_gps(recs)
    bins = core.bins_100m(no_gps, lookup, STEP)
    assert bins == [], "GPS-less file should produce no geometry, not fake coordinates"

    no_hr = mock_users.without_hr(recs)
    dec = core.decoupling(core.thirds(no_hr))
    assert dec is None or math.isfinite(dec), "HR-less file broke decoupling"

    try:
        core.load("/dev/null")
    except SystemExit as e:
        assert "no usable records" in str(e) or "records" in str(e), str(e)
    else:
        raise AssertionError("empty file did not fail cleanly")
    return True


def main():
    print(f"{'persona':<16}{'bins':>5}{'km':>7}{'Δt%':>7}{'ΔD+%':>7}{'dec%':>7}"
          f"{'weeks':>6}{'h':>7}  carbs g/h")
    ok = 0
    for p in mock_users.PERSONAS:
        r = check_persona(p)
        print(f"{r['name']:<16}{r['bins']:>5}{r['km']:>7}{r['time_pct']:>7}"
              f"{r['climb_pct']:>7}{r['dec']:>7}{r['weeks']:>6}{r['hours']:>7}"
              f"  {r['carbs'][0]}–{r['carbs'][1]}")
        ok += 1
    assert check_degraded()
    print(f"\n{ok} personas + degraded data: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
