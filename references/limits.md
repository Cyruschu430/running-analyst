# Limits & assumptions

Every number in a trailkit report is an estimate from a consumer wrist device.
Read this before quoting any figure.

## 1. Sensor assumptions

| Channel | What we assume | Real error |
|---|---|---|
| Distance / speed | GPS + accelerometer fusion, ~1 Hz | 1–3% on road; worse under canopy and on switchbacks (multipath 10–30 m) |
| Elevation | **Barometric** altimeter where the file has one | ±3–10 m per reading, drifts with weather; GPS-only z is 2–3× worse and is flagged in the report |
| Grade | Derived from smoothed altitude over a ±15 s window | ±1–2 percentage points; short steps and stairs are under-represented |
| Heart rate | Optical wrist sensor | 15–45 s lag; locks onto cadence at high step rates; unreliable in cold or when the strap is loose |
| Cadence | Wrist accelerometer, **one-leg** | Report doubles it to steps/min; accuracy good, but does not describe ground contact |
| Gait dynamics (GCT, L/R balance, vertical oscillation) | Only present with a chest strap or pod | Wrist-only files report these fields as **zero**, which the report states explicitly |
| Power | Modelled from speed/grade/acceleration (running power is not measured) | Useful for relative comparison within one athlete, not as an absolute wattage |

**Never compare absolute values across devices.** Within-athlete, same-device
change is the only defensible comparison.

## 2. Method limits

- **Grade→speed curve** needs ≥60 samples per grade bin; bins with fewer are dropped. A flat-only run produces no curve.
- **Grade is measured over a fixed 40 m window in each direction**, not a fixed
  number of samples. A sample window would smooth 27 m at walking pace and
  126 m at 4.2 m/s, which biases uphill bins against downhill ones.
- **Decoupling** = the fractional drop in `speed ÷ heart rate` between the first
  and last third of flat (±2%) moving samples, **after discarding the first
  10 minutes**. Positive = faded. The warm-up exclusion is not optional: optical
  HR lags and rises at the start, and including it manufactured a +3.5% drift on
  a run whose true value was −0.9%.
- **GPS dropouts are discarded, not interpolated.** Any sample-to-sample step
  over 300 m resets the segment; a kilometre holding under 100 m of data is
  omitted rather than reported as 0:00. Gaps therefore appear as missing
  kilometres, which is honest.
- **Course projection interpolates linearly between 5% grade bins** and refuses
  to run with fewer than three bins. A nearest-bin lookup is up to ~10% wrong at
  a bin edge; across 95 km that is hours.
- **Map colouring and course projection share one interpolating curve.** They
  previously held separate nearest-bin copies; the map is now proven to carry
  the same delta as the per-km table (test asserts within 20%).
- **The vertical benchmark comes from the target event when the profile has
  distance and D+**, and from a labelled category convention otherwise. No body
  publishes a universal m/km standard.
- **Intensity needs `lthr`.** With no lactate-threshold heart rate in the profile
  the report declines to judge intensity instead of applying an absolute bpm
  cut-off that only fits one athlete.
- **Files are read from either `enhanced_*` or standard fields** (`speed`,
  `altitude`). A file carrying neither is rejected with a message rather than
  silently producing an empty report.
- **Attribution bins are exact.** Each 100 m bin closes on its boundary: the
  crossing sample interval is split pro rata in distance, climb and time, and
  the remainder opens the next bin. Before this, bins reached 202 m for a 100 m
  target and mixed two terrains into one row.
- **`terrain_index_m` is Riley (1999) TRI on an Esri ASCII grid.** At 25 m cells
  it underreads stairs and rock steps — treat it as ground roughness, not
  technicality. Use 5 m cells for technical trails. No grid supplied, no column:
  the tool does not guess terrain.
- **Technical difficulty is athlete-supplied.** `--remarks` is the only source;
  with no remarks the CSV carries no difficulty claim at all.
- **Distances above 300 km are truncated** (segment loop ceiling). Raise the cap
  if anyone races further.
- **Course projection** applies this athlete's observed speeds to a route profile. It is valid for terrain of similar technicality. It does **not** model:
  - fatigue beyond ~2.5 h (no long-run data yet),
  - fuelling or dehydration,
  - night running, weather, or carried weight,
  - checkpoints, queues, or stops (a stop allowance is stated separately, never hidden inside the moving time).
- **n = 1.** A curve fitted to one athlete describes that athlete only. It is not a model of runners, and it must not be presented as one.
- GPS elevation noise inflates cumulative ascent by 10–25% versus a barometric or DTM reference. If the report's D+ disagrees with the organiser's figure, the organiser's figure wins.

## 3. What this tool does NOT do

- Does not diagnose injury, illness, overtraining, or heart conditions.
- Does not predict race finishing times with any guarantee.
- Does not replace a coach who can see you move, or a clinician who can examine you.
- Does not tell you to train through pain. Pain is a stop signal, not a data point.

## 4. Disclaimer (zh-HK)

> 本報告由公開感測數據自動計算，**僅供訓練參考，不構成醫療建議**。
> 手錶嘅 GPS、光學心率、高度計都有誤差，數字只反映趨勢，唔係絕對真值。
> 任何訓練或比賽決定、受傷風險，由使用者自行承擔。
> 如有痛症、舊患、心血管或慢性病病史，請先諮詢醫生、物理治療師或合資格教練。
> 本工具唔會、亦不應被理解為鼓勵你帶傷訓練或勉強完成賽事。

## 5. Disclaimer (EN, for the public repo)

> Generated from consumer wearable data. **Reference only — not medical advice.**
> GPS, optical heart rate and barometric altitude all carry error; treat the
> numbers as trends, not ground truth. Training and racing decisions, and any
> risk of injury, remain the user's own responsibility. Consult a physician,
> physiotherapist or qualified coach if you have pain, a prior injury, or a
> cardiovascular or chronic condition. This tool does not encourage training
> through pain or forcing a finish.
