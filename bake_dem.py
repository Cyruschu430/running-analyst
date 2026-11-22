#!/usr/bin/env python3
"""Bake a bare-earth DTM into terrarium PNG tiles for embedding in the report.

MapLibre's raster-dem only decodes terrarium / mapbox encodings, and Esri's
World Elevation is LERC, so the only way to put a 3 m LiDAR DTM under the 3D
view is to encode the tiles ourselves. Output is a JSON file of
{"z/x/y": "data:image/png;base64,..."}; anything not baked falls back to the
public terrarium tiles at runtime.

    python bake_dem.py dtm.asc --zoom 12 14 --out dem_tiles.json
"""
import argparse
import base64
import json
import math
import struct
import zlib

import report as core


def png(width, height, rows):
    """Minimal 8-bit RGB PNG writer (filter 0), stdlib only."""
    raw = b"".join(b"\x00" + r for r in rows)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def sample(asc, lon, lat):
    """Bilinear elevation in metres, None outside the grid."""
    cx = asc.get("dx") or asc["cellsize"]
    cy = asc.get("dy") or asc["cellsize"]
    fx = (lon - asc["xllcorner"]) / cx
    fy = (lat - asc["yllcorner"]) / cy
    rows = asc["rows"]
    h, w = len(rows), len(rows[0])
    if not (0 <= fx < w - 1 and 0 <= fy < h - 1):
        return None
    c, r = int(fx), h - 1 - int(fy)
    tx, ty = fx - int(fx), fy - int(fy)
    z00, z10 = rows[r][c], rows[r][c + 1]
    z01, z11 = rows[r - 1][c], rows[r - 1][c + 1]
    if -9999 in (z00, z10, z01, z11):
        return None
    top = z00 + (z10 - z00) * tx
    bot = z01 + (z11 - z01) * tx
    return top + (bot - top) * ty


def tile_png(asc, z, x, y):
    n = 2 ** z
    rows, blank = [], 0
    for i in range(256):
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + (i + 0.5) / 256) / n))))
        row = bytearray()
        for j in range(256):
            lon = (x + (j + 0.5) / 256) / n * 360 - 180
            v = sample(asc, lon, lat)
            if v is None:
                blank += 1
                v = 0
            e = int(round((v + 32768) * 256))
            e = max(0, min(0xFFFFFF, e))
            row += bytes(((e >> 16) & 255, (e >> 8) & 255, e & 255))
        rows.append(bytes(row))
    if blank > 256 * 256 * 0.98:          # tile is outside the DTM
        return None
    return png(256, 256, rows)


def tiles_for(bbox, z):
    x0, y0 = lonlat_to_tile(bbox[0], bbox[3], z)
    x1, y1 = lonlat_to_tile(bbox[2], bbox[1], z)
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            yield x, y


def lonlat_to_tile(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    lat_r = math.radians(lat)
    y = int((1 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2 * n)
    return max(0, min(n - 1, x)), max(0, min(n - 1, y))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dtm")
    ap.add_argument("--bbox", nargs=4, type=float, required=True,
                    metavar=("W", "S", "E", "N"))
    ap.add_argument("--zoom", nargs=2, type=int, default=(12, 14))
    ap.add_argument("--out", default="dem_tiles.json")
    a = ap.parse_args()

    asc = core.load_asc(a.dtm)
    out, total = {}, 0
    for z in range(a.zoom[0], a.zoom[1] + 1):
        for x, y in tiles_for(a.bbox, z):
            p = tile_png(asc, z, x, y)
            if p is None:
                continue
            key = f"{z}/{x}/{y}"
            out[key] = "data:image/png;base64," + base64.b64encode(p).decode()
            total += len(out[key])
            print(f"{key}  {len(p) // 1024} KB")
    json.dump(out, open(a.out, "w"))
    print(f"{len(out)} tiles, {total / 1024 / 1024:.2f} MB base64 → {a.out}")


if __name__ == "__main__":
    main()
