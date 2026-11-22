# Roadmap

Ordered by **what becomes possible**, not by what is fun to build. Each phase
must ship a usable artifact on its own; hardware never gates the next phase.

## Phase 0 — One command (done)

`trailkit run activity.fit` → grade→speed curve, fatigue decoupling, course
projection. Watch only. Works on any brand's FIT.

**Unlocked:** nothing new. This is the baseline every later claim is measured against.

## Phase 1 — Report + terrain layer (no new hardware)

- `report.html` — self-contained, sendable
- `terrain.csv` — per 100 m: grade, D+, predicted vs actual speed, time delta
- `map.html` — route coloured by **time lost vs model**, not by prettiness
- DTM derivatives (TRI, roughness, slope SD) → continuous terrain index

**Unlocked:** "where did I lose time, on what terrain, and how much" — the one
question Strava/GoldenCheetah do not answer. This is the product.

**Cost:** 0. **Risk:** DTM coverage/alignment, GPS chainage matching error.

## Phase 2 — Chest strap (HR accuracy)

Buy: any ANT+/BLE chest strap compatible with the watch (COROS, Polar H10, Garmin HRM).

**Unlocked:**
- Optical HR lag (15–45 s) disappears → real HR-vs-grade response, not a delayed echo
- Cardiac drift becomes interpretable (heat vs fatigue vs fuelling)
- LTHR detection from field data instead of a lab guess
- Interval compliance: did the watch keep you in zone, or did you drift?

**Not unlocked:** anything about how you land. HR is central, not mechanical.

**Cost:** ~HK$400–700. **Verdict:** worth it — it makes every existing metric
more trustworthy for the price of one pair of shoes.

## Phase 3 — Pod (gait mechanics)

Buy (only after probing the field list): COROS POD 2 (waist), Stryd, or a
current-gen foot pod.

**Unlocked:**
- Ground contact time, L/R balance, vertical oscillation, leg stiffness
- The fatigue signature: GCT and cadence drift over a long run, at matched speed
- Terrain decoded from **biomechanical response** rather than from a map — the
  defensible inversion, and the only version of this idea that is publishable

**Not unlocked:** injury prediction. Asymmetry is a monitoring signal, never a
diagnosis. Report it as a trend with the disclaimer attached.

**Cost:** ~HK$1,000–2,500. **Gate:** probe an actual FIT first — if the fields
land as zeros, the hardware buys nothing.

## Phase 4 — Cohort (n > 1)

- `trailkit compare *.fit` → same-grade, same-route comparisons across runners
- 5–10 runners × ≥8 activities each (≈50–80 files) before any model claim
- Mixed-effects model: random effect per athlete, fixed effects grade + duration

**Unlocked:** a statement that generalises. Until this exists, everything is a
single-subject study and must be labelled as one.

**Cost:** effort, not money. **Risk:** consent and data handling — local only,
no upload, delete on request.

## Phase 5 — Prediction (only now, and only narrowly)

- Fade model fitted on long runs (>3 h), not extrapolated from 2 h
- Race projection with an explicit uncertainty band, never a single number
- Backtest: predict a race, then compare with the actual result

**Not unlocked:** certainty. A 100 km prediction from 20 activities carries
hours of uncertainty; the report must show the band.

---

## Buy / don't buy

| Buy | Why |
|---|---|
| Chest strap | Cheapest accuracy upgrade; fixes an entire channel |
| Pod (after probing) | Only real route to biomechanics |
| **Don't** buy a second watch | GPS/baro differences are noise compared with the modelling error |
| **Don't** buy a lab VO2 test yet | Phase 1–2 field data answers more per dollar |

## What never changes

The disclaimer holds at every phase: consumer sensors, reference only, not
medical advice, injury risk is the user's own. More sensors add resolution,
not certainty.
