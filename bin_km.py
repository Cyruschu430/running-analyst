"""Print the 100 m bin chainages nearest each 5 km mark (for map labels)."""
import sys

import report as core

recs, _ = core.load(sys.argv[1])
table = core.grade_table(recs)
lookup = core.speed_lookup(table)
bins = core.bins_100m(recs, lookup, 100)
kms = [round(b["chainage_m"] / 1000, 2) for b in bins]
print("bins", len(kms), "first", kms[:3], "last", kms[-2:])
print("near 5k marks:", [k for k in kms if min(k % 5, 5 - k % 5) < 0.15])
