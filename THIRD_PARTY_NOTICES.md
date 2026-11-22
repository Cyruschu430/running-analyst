# Third-party notices

## Runtime

| Component | Version | Licence | How we use it |
|---|---|---|---|
| [fitdecode](https://github.com/polyvertex/fitdecode) | ≥0.10 | MIT | Decode FIT files. Copyright notice retained. |
| [MapLibre GL JS](https://github.com/maplibre/maplibre-gl-js) | 4.7 / 5.6 (CDN) | BSD-3-Clause | Map rendering in `report.html`. Attribution shown on the map. |
| [AWS Terrain Tiles (Terrarium)](https://registry.opendata.aws/terrain-tiles/) | — | Open data (Mapzen-derived) | 3D terrain and hillshade. Attribution shown on the map. |

Python standard library only, otherwise. No pandas / numpy / GIS stack required.

## Referenced projects — ideas only, no code copied

| Project | Licence | What we took | What we did NOT do |
|---|---|---|---|
| GoldenCheetah | GPL-3.0 | Concepts: fitness–fatigue (PMC/TSB), critical power framing | No code, no translation, no linking |
| Runalyze | GPL-3.0 | Concepts: TRIMP, grade-adjusted pace, ascent correction | No code |
| FitTrackee | AGPL-3.0 | Concepts: activity data model | No code |
| python-fitparse | MIT | Nothing (we use fitdecode; fitparse fails on COROS files) | — |
| stravalib | Apache-2.0 | Nothing yet; will be used directly if a Strava adapter is added | — |

**Rule:** GPL/AGPL projects are read for algorithm descriptions and papers, never
for source. Copying GPL code into this MIT project would re-license the whole
thing; re-implementing a published method with a citation does not.

## Scientific methods

Methods are cited, not copied. Full provenance in `references/sport-science.md`.

- Minetti et al. 2002, *J Appl Physiol* 93:1039–1046 — gradient energy cost (theoretical benchmark only; not fitted to the athlete).
- Coyle & González-Alonso 2001, *Exerc Sport Sci Rev* 29(2):88–92 — cardiovascular drift.
- Banister 1991, *Physiological Testing of Elite Athletes* — TRIMP.
- Riley, DeGloria & Elliot 1999, *PE&RS* 65(7):837–844 — terrain ruggedness index.
- Newson & Krumm 2009, ACM SIGSPATIAL — HMM map matching.

Formulas and measurements are facts and are not copyrightable; the papers'
text and figures are. We reproduce neither.

## Terrain data (not shipped with the repository)

| Source | Resolution | Used for |
|---|---|---|
| CEDD LiDAR DTM 2020, CSDI `cedd_rcd_1629267205233_87895` | 0.5 m tiles, resampled | TRI and the per-100 m terrain index |
| LandsD territory-wide DTM, CSDI | 5 m | 3D relief, baked to z12 (~35 m) display tiles |

Both are published open data; attribution is required and is shown on the map
in any generated report. No government raster is committed — `*.asc`, `*.tif`
and baked tile JSON are gitignored, and a report is a derived artefact the
reader generates locally.

Two scales appear in one report: TRI is computed from a 3 m bare-earth grid,
while the 3D relief is a ~35 m display tile. They are deliberately not
comparable cell-for-cell, and the report says so in the TRI section.

## Data that must never be committed

| Item | Why |
|---|---|
| `*.fit`, `*.gpx` from a device | Contains GPS traces of a real person; personal data under HK PDPO |
| HK100 course GPX | Organiser's file; redistribution rights not granted |
| `profile.json` with real names / dates | Personal data |

Ship examples as synthetic or truncated fixtures instead.
