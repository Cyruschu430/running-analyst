#!/usr/bin/env python3
"""Reconcile the per-km table against the device's own session totals.

    python verify.py activity.fit

Catches the class of bug that unit tests miss: numbers that look plausible but
do not add up to what the watch recorded.

Tolerances (deliberate, stated rather than hidden):
  * time  — segments only cover whole kilometres and exclude stopped samples,
            so the sum is allowed to run short of the device moving time.
  * D+    — barometric noise and the partial final kilometre mean the sum can
            differ from the device by tens of metres on a hilly run.
"""
import sys

import report as core
import report_html as html

TIME_TOL_PCT = 3.0
DPLUS_TOL_PCT = 10.0


if len(sys.argv) < 2:
    raise SystemExit("usage: verify.py ACTIVITY.fit")


def check(path):
    recs, s = core.load(path)
    segs, _ = html.km_segments(recs)
    timer = round(s.get("total_timer_time") or 0)
    ascent = s.get("total_ascent") or 0

    act = sum(x["actual_s"] for x in segs)
    dpl = sum(x["d_plus"] for x in segs)

    problems = []
    if timer:
        err = abs(act - timer) / timer * 100
        if err > TIME_TOL_PCT:
            problems.append(f"time sum {act}s vs timer {timer}s ({err:.1f}% > {TIME_TOL_PCT}%)")
    if ascent:
        err = abs(dpl - ascent) / ascent * 100
        if err > DPLUS_TOL_PCT:
            problems.append(f"D+ sum {dpl}m vs device {ascent}m ({err:.1f}% > {DPLUS_TOL_PCT}%)")

    print(f"segments        {len(segs)}")
    print(f"time            {act}s vs timer {timer}s  ({abs(act-timer)/max(timer,1)*100:.1f}%)")
    print(f"vertical        {dpl}m vs device {ascent}m  ({abs(dpl-ascent)/max(ascent,1)*100:.1f}%)")
    print(f"decoupling      {core.decoupling(core.thirds(recs))}%  (positive = faded)")
    if problems:
        print("\nFAIL")
        for p in problems:
            print("  -", p)
        return 1
    print("\nOK — segment totals reconcile with the device")
    return 0


if __name__ == "__main__":
    sys.exit(check(sys.argv[1]))
