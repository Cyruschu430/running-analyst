#!/usr/bin/env python3
"""Optional photographs for the strength page.

Source: free-exercise-db (github.com/yuhonas/free-exercise-db), released under
the Unlicense / public domain, two stills per movement (start and end position).
The repo documents the whole package as public domain; the upstream provenance of
the individual photographs is not separately stated, so check before commercial
redistribution.

    python assets.py            # fetch into assets/exercise/
    python assets.py --check    # what is cached

Nothing breaks without them: the PDF falls back to the built-in pictograms.
"""
import os
import sys
import urllib.request

BASE = "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises/"
DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "exercise")

# our movement key -> dataset exercise id
MAP = {
    "squat": "Bodyweight_Squat",
    "split": "Split_Squats",
    "calf": "Standing_Calf_Raises",
    "plank": "Plank",
    "hinge": "Romanian_Deadlift",
    "step": "Step-up_with_Knee_Raise",
    "deadbug": "Dead_Bug",
    "side": "Side_Bridge",          # side plank; dataset has no dedicated side plank still
    "band": "Monster_Walk",          # band lateral walk
}

ATTRIBUTION = ("示範照片：free-exercise-db（Unlicense / public domain）"
               "github.com/yuhonas/free-exercise-db")


# dataset frame 0 is the set-up pose; for movement where it reads as a different
# exercise (plank starts from a kneeling position) show only the working frame
FRAMES = {"plank": [1]}


def photo_paths(key):
    """[(start, end)] if cached, else [] — never a network call at render time."""
    ex = MAP.get(key)
    if not ex:
        return []
    out = []
    for i in FRAMES.get(key, [0, 1]):
        p = os.path.join(DEST, ex, f"{i}.jpg")
        if os.path.exists(p):
            out.append(p)
    return out if out else []


def fetch():
    os.makedirs(DEST, exist_ok=True)
    got = 0
    for key, ex in MAP.items():
        for i in (0, 1):
            url = f"{BASE}{ex}/{i}.jpg"
            path = os.path.join(DEST, ex, f"{i}.jpg")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if os.path.exists(path):
                got += 1
                continue
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    data = r.read()
                open(path, "wb").write(data)
                got += 1
                print(f"  {ex}/{i}.jpg  {len(data) // 1024} KB")
            except Exception as e:
                print(f"  MISS {ex}/{i}.jpg: {e}")
    return got


if __name__ == "__main__":
    if "--check" in sys.argv:
        for key in MAP:
            print(f"{key:<8}", "cached" if photo_paths(key) else "-")
    else:
        print(f"{fetch()} images cached in {DEST}")
