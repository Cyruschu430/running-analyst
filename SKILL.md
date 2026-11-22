---
name: running-analyst
description: Use when turning a run FIT file into a report.
---

# Running Analyst

Turn one activity `.fit` file into a sourced performance report. Works with any
watch brand; no account, no upload.

## Before any analysis — ask these, in this order

The report is only as good as the goal it is judged against. Ask **before**
running anything; do not assume a distance or a benchmark.

| # | Ask | Unlocks |
|---|---|---|
| 1 | 你的訓練目標是什麼？（10K／半馬／全馬／越野／超馬） | assessment benchmark and report emphasis |
| 2 | 報了哪場比賽？日期？ | countdown and specificity |
| 3 | 賽事總距離、總攀升多少？ | the event's own m/km benchmark (HK100 = 5,142 m / 96 km = 54) |
| 4 | 目標完成時間？ | the bar the plan is judged against — recorded as `target_hours` |
| 4b | 現時水平：最長跑過幾遠／幾久？每週跑幾多公里？最近有無比賽成績？ | `current.longest_run_h` and `current.weekly_km` cap the first weeks so the plan cannot invent capacity |
| 5 | 有沒有乳酸閾值心率（LTHR）？ | intensity judgement and HR zones |
| 6 | 有沒有官方 GPX？ | course analysis before any run exists |
| 7 | 年齡、性別？ | recorded; does not change volume (no defensible formula) |
| 8 | 有沒有傷患、痛症、長期病？ | any answer stops intensity prescription and refers to a clinician |
| 9 | 一週可以投入幾多日訓練？邊幾日？ | `schedule.days_per_week` — the plan uses exactly that many running days |
| 9b | 工作時間表？邊幾日返工、幾點收工？ | which days can hold a session and the weekday cap |
| 10 | 住邊區？附近邊條山徑可以練爬升？ | names the actual hill for the quality session |
| 11 | 有做重量訓練嗎？一週幾次、有咩器材（健身室／阻力帶／無）？ | adds strength sessions with sets and reps, placed clear of quality and long days |
| 12 | 體重？有無腸胃問題、食物敏感、飲食限制？ | weight scales every carb/protein target; gut issues change the race-day plan |

Rules:

- **1–3 are mandatory.** Without them the report falls back to a category
  convention and says so; that is a weaker answer, not a wrong one.
- **Ask for the official GPX from the race organiser, not a GPS trace of
  someone's recce.** The organiser's file is the course; a recce is one person's
  line through it.
- **4 and 4b are a pair.** A target time with no current level produces a plan
  that looks fine and is unbuildable. Ask both, then let the tool state the gap
  (e.g. "模型預測 13.9 小時，目標 16.0 小時").
- **12 is required for the nutrition page.** Without body mass there are no
  grams, only adjectives. Ask about gut issues too: a carb-load that the athlete
  cannot absorb is worse than none.
- **7 is context, not a formula.** Age and sex are stored and shown, but no
  volume or intensity number is derived from them; inventing an age-based
  adjustment would be the same sin as inventing a threshold.
- **8 gates the whole plan.** Any condition or current pain removes Z3+ work and
  says so at the top. Never soften it.
- **9 and 10 decide the calendar.** A 09:00–18:00 week caps weekday sessions;
  the long run goes on the first free day. Ask, then schedule around the answer.
- **Never fill 5 by guessing.** If LTHR is unknown, say the intensity section is
  unavailable and offer to derive it from a maximal 1-hour effort later.
- If there is no race, ask what the next 8 weeks are for — a benchmark of "none"
  produces a report with no verdict.

## Then, before the race report

```bash
python report.py --course course.gpx            # distance, D+, grade split, steepest km
python report.py --audit-profile profile.json   # what is missing and what it blocks
```

A plan needs the course, the week and the weakness:

```bash
python plan.py --profile profile.json --terrain out/terrain.csv --out out/plan.json
python plan.py --profile profile.json --format pdf --pdf out/plan.pdf   # printable A4
python plan.py --profile profile.json --format icu --outdir out/icu    # intervals.icu workouts
```

The plan is deterministic: same profile in, same weeks out. Taper weeks drop
sessions, not just minutes — a seven-day week in a taper is not a taper.

Report the plan's own warning when it appears — if the longest run is a small
fraction of the race time, say so plainly instead of presenting the plan as
sufficient.

Once past activities exist:

```bash
python report.py --history myrun/ --lthr 170    # weekly load + intensity distribution
```

The order matters: **course first** (what the race demands), **history second**
(what the athlete has been doing), **the run report last** (how yesterday went).

## When to use

- The user drops a `.fit` / `.gpx` and asks about a run ("analyse this", "how was my session", "why did I fade").
- The user asks for a route coloured by where they lost time.
- You need deterministic numbers to reason over instead of guessing from the watch summary.

## Commands

```bash
python report_html.py activity.fit --profile profile.json --out report.html
python report.py activity.fit --gpx course.gpx --json metrics.json
python test_running_analyst.py          # proves the maths still holds
python test_mock_users.py               # five mock athletes end-to-end + broken data
```

`profile.json` carries the goal — `10k_road`, `marathon_road`, `half_trail`,
`ultra_trail` — plus the target event. The goal changes the benchmark and the
report's emphasis; the same run is judged differently for a 10K and a 100K.

## Proving it works

`test_mock_users.py` runs five synthetic athletes (10K beginner, sub-4
marathoner, trail half, ultra, injured) plus a GPS-less/HR-less file through
the same code a real FIT goes through, and checks that bins reconcile with the
activity, coordinates land in Hong Kong, plans honour the athlete's available
days, taper weeks shrink, an injured athlete gets no intensity, and the same
profile always yields the same plan.

Synthetic ≠ real: it proves the pipeline is internally consistent and does not
crash on edge cases. It cannot prove the grade→speed model is right for a new
athlete — only a real file can.

## Hard rules

1. **Never compute a number yourself.** Read `metrics.json` / the printed
   summary. If a figure is not in there, say it is not available.
2. **Never present the grade→speed model as a published formula.** It is fitted
   to this athlete only (n = 1) and must be labelled as such.
3. **Every claim needs a source** in `references/sport-science.md` (✅ peer
   reviewed / ⚠️ industry convention / 🔬 this athlete). No source, no sentence.
4. **No medical advice, ever.** If the user reports pain or injury, stop the
   analysis and direct them to a clinician. Pain is a stop signal, not a metric.
5. **Do not upload the file anywhere.** Everything is local.

## Reading the output

- `綜合評估` — deterministic verdict from the goal profile, not the model's opinion.
- Route map — colour is *time lost vs the athlete's own model*, not raw speed.
- `分段表現` — per-km actual vs model; the red bars are the answer to "where".
- `訓練建議` — one or two rules-generated actions, not a plan.
- Plan PDF — cover (warnings, glossary), one page per week, nutrition page,
  strength page. Every number comes from `plan.json`; the text adds nothing.

Strength is prescribed as two 30-minute sessions, placed clear of the quality
and long-run days. Photographs are optional: `python assets.py` fetches them
into `assets/exercise/` (public domain, not committed); without them the PDF
falls back to line pictograms.

## Files

| Path | Purpose |
|---|---|
| `report.py` | FIT → metrics (grade table, splits, decoupling, course projection) |
| `plan.py` | deterministic plan, schedule, health gate, PDF, ICU export |
| `nutrition.py` | race-week carbohydrate/protein targets (Thomas et al. 2016) |
| `strength.py` | two 30-min sessions with sets, reps and progression |
| `assets.py` | optional photos for the strength page (fetched, not committed) |
| `report_html.py` | FIT + profile → single-file HTML with 2D/3D map |
| `references/sport-science.md` | provenance for every metric |
| `references/limits.md` | sensor assumptions and what the tool refuses to claim |
| `ROADMAP.md` | what unlocks with a chest strap / pod / cohort |

## Failure modes to state plainly

| Situation | Say this |
|---|---|
| No barometric altimeter | "Elevation is GPS-derived; ascent is inflated — trend only." |
| Gait fields all zero | "Wrist-only file: no ground contact time or balance." |
| No long runs in history | "A 100 km projection from a 2 h run is an extrapolation, not a forecast." |
| Vendor disagrees on D+ | "The organiser's figure wins." |
