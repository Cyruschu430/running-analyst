# Running Analyst

**A post-training agent for runners.** Turn one activity file into an honest,
sourced performance report — what happened, where you lost time, and why.

No account, no server, no upload. One command, one HTML file.

> Reference only — not medical advice. Consumer sensors carry error; read trends,
> not absolutes. Training and injury risk remain your own. See `references/limits.md`.

## What it does

Given a `.fit` file (any brand) and a goal profile, it produces:

| Output | What it answers |
|---|---|
| `metrics.json` | Machine-readable: grade→speed curve, splits, decoupling, course projection |
| `report.html` | Self-contained report: assessment, 2D/3D terrain map, per-km table, advice |

The map colours the route by **time lost versus your own model**, so a red
segment is a place where terrain cost you more than your own history predicts.

## Install

```bash
python3 -m venv .venv && .venv/bin/pip install fitdecode
```

Only dependency: `fitdecode`. Everything else is the standard library.
(`fitparse` fails on some vendor files; fitdecode is the tolerant one.)

## Use

```bash
cp profile.example.json profile.json     # then edit your goal
.venv/bin/python report_html.py activity.fit --profile profile.json --out report.html
.venv/bin/python report.py activity.fit  # terminal summary only
```

Per-100 m attribution, with optional terrain roughness and athlete notes:

```bash
.venv/bin/python report.py run.fit --terrain out/terrain.csv          # time vs model, bin by bin
.venv/bin/python report.py run.fit --terrain out/terrain.csv --dtm dtm_hk_25m.asc
.venv/bin/python report.py run.fit --terrain out/terrain.csv --remarks notes.json
```

`schedule.days_per_week` is the number of days the athlete can actually train —
the plan uses exactly that many running days and scales strength down when the
week is short (a 2-day athlete gets one long run, one quality session, no lifting
days of its own).

Add `"strength": {"enabled": true, "sessions": 2, "minutes": 30}` to the profile
for two short strength sessions a week, placed clear of the key running days
(Beattie 2017; Rønnestad & Mujika 2014).

`--dtm` takes an Esri ASCII grid: Hong Kong users convert the CSDI/LandSD DTM
with the `hk-dtm-pipeline` skill; anyone else exports their own DEM to `.asc`.
`terrain_index_m` is Riley (1999) TRI — the RMS of the eight neighbour
differences, in metres. `--remarks` is a JSON list of
`{"from_m": 14500, "to_m": 15600, "note": "石級＋濕滑"}`; the `remark` column only
exists when you supply one, because technical difficulty cannot be measured from
a track file.

A plan from the same inputs — deterministic, every rule cited:

```bash
.venv/bin/python plan.py --profile profile.json --terrain out/terrain.csv --out out/plan.json
```

Race nutrition comes from the same profile (body mass + target hours) and is
scaled from the ACSM/AND position stand, not invented:

```bash
.venv/bin/python nutrition.py 60 16     # weight kg, race hours
```

It appears as the last page of the PDF when the profile has `weight_kg`.
Ranges only — fluid and sodium are sweat-rate dependent, and the tool says so.

Print it for a watch that cannot take a plan:

```bash
.venv/bin/python plan.py --profile profile.json --format pdf --pdf out/plan.pdf
```

Ten A4 pages: cover with the warnings, then one page per week (sessions in
weekday order). Rendering uses the Chromium already on the machine — no new
dependency.

The plan starts at *your* stated week, rises at most 10% per week to 1.2×, keeps
~80/20 easy/hard, tapers 3 weeks, and gives the weakness found in `terrain.csv`
one dedicated session per week. It also tells you when the week is too small for
the race you entered rather than quietly producing an under-built plan.

Course only (no activity needed), profile audit, training history:

```bash
.venv/bin/python report.py --course course.gpx          # what the race demands
.venv/bin/python report.py --audit-profile profile.json # what is missing
.venv/bin/python report.py --history myrun/ --lthr 170  # weekly load + HR zones
```

Check the maths still holds, then check the numbers add up:

```bash
.venv/bin/python test_running_analyst.py          # synthetic invariants
.venv/bin/python verify.py activity.fit           # segments vs device totals
```

## Getting the file out of a watch

| Device | Route |
|---|---|
| COROS | App → activity → export FIT (programmatic via the COROS MCP gateway) |
| Garmin | Connect → activity → Export original, or copy `*.fit` over USB |
| Suunto / Wahoo / Bryton | App export, or copy from the device over USB |
| Apple Watch | No export API — bridge with HealthFit or RunGap to produce a FIT |

The analysis is identical for every brand: FIT is the contract.

## Goal profile

`goal` selects the benchmark and the emphasis — the same run is judged
differently for a 10K and a 100K.

| goal | vertical benchmark | emphasis |
|---|---|---|
| `10k_road` | 5 m/km | pacing consistency |
| `marathon_road` | 10 m/km | late-race fade |
| `half_trail` | 30 m/km | climbing economy |
| `ultra_trail` | 45 m/km | vertical density, descent, fuelling |

Add `lthr` (lactate-threshold HR) to the profile if you know it — intensity and
heart-rate-zone advice are derived from it. Without it the report says so and
skips the intensity judgement rather than guessing an absolute bpm.

## Design rules

1. **Every number is computed by code, never by a language model.** The same
   file yields the same figures on any agent, any model.
2. **Every metric carries a source** — peer-reviewed, industry convention, or
   this athlete's own data. See `references/sport-science.md`.
3. **The personal grade→speed model is empirical (n = 1)** and labelled as such.
   It is not Minetti's formula and is never presented as one.
4. **Course projection interpolates between grade bins** and refuses to project
   from fewer than three bins. Snapping to the nearest 5% bin misstates speed by
   up to ~10% at the edge, which compounds over 95 km.
5. **Decoupling is `speed/heart-rate`, reported as the fractional drop from the
   first to the last flat third** — positive means faded. Comparing an HR ratio
   against a pace ratio directly double-counts and flips the sign.
6. **No data leaves the machine.** Files are read locally and nothing is uploaded.

## Limits

Sensor assumptions, method limits and what the tool refuses to do:
`references/limits.md`. Roadmap (sensors, cohort modelling): `ROADMAP.md`.

## Tests

```bash
python test_running_analyst.py   # invariants of the maths
python test_mock_users.py        # five mock athletes end-to-end
```

The mock suite feeds five synthetic but self-consistent athletes (and one
file with no GPS) through the whole pipeline: bin reconciliation, coordinate
sanity, plan structure, taper, injury gate, nutrition and determinism.

## Optional assets

```bash
python assets.py      # photos for the strength page, cached under assets/exercise/
```

Public domain, not committed. Without them the PDF uses line pictograms.

## Licence

MIT — see `LICENSE`. Third-party components and their terms:
`THIRD_PARTY_NOTICES.md`.
