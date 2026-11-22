"""Compare two DTMs at the same route points (metres)."""
import sys
import report as core


def z(asc, lat, lon):
    cx = asc.get("dx") or asc["cellsize"]
    cy = asc.get("dy") or asc["cellsize"]
    c = int((lon - asc["xllcorner"]) / cx)
    r = len(asc["rows"]) - 1 - int((lat - asc["yllcorner"]) / cy)
    return asc["rows"][r][c]


if __name__ == "__main__":
    a = core.load_asc(sys.argv[1])
    b = core.load_asc(sys.argv[2])
    recs, _ = core.load(sys.argv[3])
    d = []
    for i in range(0, len(recs), 200):
        lat, lon = recs[i][7], recs[i][8]
        if lat is None or lon is None:
            continue
        d.append(z(b, lat, lon) - z(a, lat, lon))
    d.sort()
    print("B minus A at %d points: median %+.1f m, p10 %+.1f, p90 %+.1f, worst %+.1f"
          % (len(d), d[len(d) // 2], d[int(len(d) * .1)], d[int(len(d) * .9)],
             max(d, key=abs)))
