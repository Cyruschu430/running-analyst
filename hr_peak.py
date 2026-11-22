#!/usr/bin/env python3
"""Highest sustained heart rate in a FIT file — the input to an LTHR estimate."""
import sys
import report as core


def best_window(recs, seconds):
    hr = [(r[6], r[3]) for r in recs if r[3] is not None and r[6] is not None]
    if len(hr) < 10:
        return None
    best, i = (0, None), 0
    for j in range(len(hr)):
        while (hr[j][0] - hr[i][0]).total_seconds() > seconds:
            i += 1
        if (hr[j][0] - hr[i][0]).total_seconds() >= seconds * 0.98:
            vals = [h for _, h in hr[i:j + 1]]
            m = sum(vals) / len(vals)
            if m > best[0]:
                best = (m, hr[i][0])
    return best


if __name__ == "__main__":
    recs, _ = core.load(sys.argv[1])
    print(f"records: {len(recs)}  max HR: {max(r[3] for r in recs if r[3])}")
    for w in (300, 1200, 3600):
        m, t = best_window(recs, w)
        print(f"best {w // 60:>2} min avg: {m:.1f} bpm (from {t:%H:%M:%S})")
