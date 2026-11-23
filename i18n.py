"""Render-time English pass.

The generators stay Chinese-canonical (that is what the athlete reads by
default). For a shareable English artefact the finished HTML is rewritten by
this table, so both languages come from one code path and no number is ever
re-typed. Fragment-level so templated lines (week meta, per-km rows) keep
their computed values. `residual()` is the check: it must return nothing.
"""
import re

LITERALS = [
    # ---- plan.py: phases, days, session types
    ("建量期／高峰期／減量期", "Build / Peak / Taper"),
    ("減量期減至每週 1 節；比賽前一週不做重量。", "Cut to one session a week in the taper; no lifting in race week."),
    ("排在輕鬆跑之後或另一日；與強度課、長課至少相隔 6 小時。", "Place after an easy run or on another day; at least 6 h from any quality or long session."),
    ("本計劃由 Running Analyst 依你的輸入計算，僅供訓練參考，不構成醫療建議。如有痛症請停止並諮詢醫生。",
     "Computed by Running Analyst from your inputs. Training reference only, not medical advice. If you have pain, stop and see a clinician."),
    ("規則：Seiler 2010（80/20）· Mujika &amp; Padilla 2003（減量）· 週量每週增幅上限 10% ·",
     "Rules: Seiler 2010 (80/20) · Mujika &amp; Padilla 2003 (taper) · weekly volume capped at +10% ·"),
    ("示範照片：free-exercise-db（Unlicense / public domain）。每組兩張為開始與結束位置。",
     "Demo photos: free-exercise-db (Unlicense / public domain). Two frames per set: start and end position."),
    ("姿勢有疑問請找合資格教練。", "If a position feels wrong, ask a qualified coach."),
    ("全程向上爬的總高度，英文寫 D+。數字越大，整條路越辛苦。",
     "Total metres climbed (D+). The bigger the number, the harder the course."),
    ("每公里平均要爬多少米。HK100 是 54 米／公里，即每公里爬升約 54 米。",
     "Metres climbed per kilometre. HK100 is 54 m/km — about 54 m of ascent every kilometre."),
    ("Z1 可以講電話；Z2 只可以講短句；Z3 講不到長句；Z4 只講到單字；Z5 講不到話。",
     "Z1 you can hold a conversation; Z2 only short sentences; Z3 no long sentences; Z4 single words; Z5 none."),
    ("每週唯一一節刻意吃力的訓練，其餘時間都應該輕鬆。",
     "The one deliberately hard session each week; everything else should be easy."),
    ("逐週加量 → 達到最高訓練量 → 賽前逐步減量讓身體恢復。",
     "Build week on week → peak volume → taper into the race to arrive recovered."),
    ("八成訓練時間輕鬆，兩成吃力。比例失衡是最常見的受傷原因。",
     "80% of training time easy, 20% hard. Getting this ratio wrong is the most common cause of injury."),
    ("賽前 2–3 日提高碳水攝取，讓肌肉儲備更多肝醣。",
     "Raise carbohydrate intake 2–3 days out so the muscles store more glycogen."),
    ("先諮詢醫生／物理治療師，再執行任何強度課。本計劃暫時只保留 Z1–Z2：",
     "Consult a clinician before any quality session. This plan keeps to Z1–Z2 only: "),
    ("6 次 200 米下坡重複；短步幅、快步頻、輕著地",
     "6 × 200 m downhill repeats; short stride, high cadence, soft landing"),
    ("6 次 3 分鐘爬坡；全程可持續功率，不要在坡底衝刺",
     "6 × 3 min climbs at sustainable power; do not sprint at the base"),
    ("本週最重要一課：長距離＋爬升，排在最有空的一日",
     "The week's key session: distance + climb, on the day you have most time"),
    ("提升上坡效率", "Improve uphill efficiency"),
    ("喚醒雙腿，不追求表現", "Wake the legs; no performance target"),
    ("短而輕鬆，賽前兩日完全休息", "Short and easy; full rest two days before"),
    ("輕鬆，能說話的強度", "Easy — conversational"),
    ("下肢複合動作＋核心", "Lower-body compound + core"),
    ("與跑步相隔 6 小時以上", "at least 6 h from any run"),
    ("肌力訓練", "Strength"),
    ("場地與器材", "Venue and kit"),
    ("槓鈴或壺鈴、深蹲架、踏板／箱。質量比重量重要。",
     "Barbell or kettlebell, rack, step box. Quality beats load."),
    ("阻力帶（約 HK$80–150）、一張穩固椅子、牆。", "Resistance band (about HK$80–150), a solid chair, a wall."),
    ("樓梯、公園長椅、單槓；提踵與上台階用樓梯已足夠。",
     "Stairs, a park bench, a pull-up bar; stairs are enough for calf raises and step-ups."),
    ("每週 2 節 · 每節 30 分鐘", "2 sessions a week · 30 min each"),
    ("比賽飲食", "Race nutrition"),
    ("此頁為指引換算，非個人化建議，亦非醫療建議。",
     "Converted from published guidance; not individualised and not medical advice."),
    ("依個人流汗率調整，並非固定值。", "Adjust to your own sweat rate; not a fixed number."),
    ("充碳第二日；飲水正常，不需刻意灌水。", "Second carb-loading day; drink normally, do not force fluids."),
    ("晚餐以易消化碳水為主，份量熟悉，不試新食物。",
     "Dinner: easy-to-digest carbohydrate, a familiar portion, nothing new."),
    ("比賽日早上", "Race morning"),
    ("賽前 2–3 小時，1–2 g/kg 易消化碳水；賽前 15 分鐘可再 15–30 g。",
     "2–3 h before: 1–2 g/kg of easy carbohydrate; 15–30 g more 15 min before the start."),
    ("開始充碳；減少油脂與高纖食物（走油、少菜梗），避免腸胃負擔。",
     "Carb loading starts; cut fat and high-fibre food (no oil, less roughage) to spare the gut."),
    ("每小時 60–90 g，合共約 960–1440 g；用多種可轉運碳水（葡萄糖＋果糖），每 20–30 分鐘一次。",
     "60–90 g/h, about 960–1440 g in total; multiple transportable carbs (glucose + fructose), every 20–30 min."),
    ("正常訓練飲食；每餐有碳水，蛋白質 1.2–2.0 g/kg。",
     "Normal training diet; carbohydrate at every meal, protein 1.2–2.0 g/kg."),
    ("3 組 × 8 次，最後 2 次仍可保持姿勢（RPE 6）", "3 × 8, still holding position on the last 2 reps (RPE 6)"),
    ("4 組 × 6 次，重量加到第 3 組開始吃力（RPE 7–8）", "4 × 6, load until set 3 starts to bite (RPE 7–8)"),
    ("2 組 × 6 次，重量不變、組數減半（RPE 6）", "2 × 6, same load, half the sets (RPE 6)"),
    ("第 1–4 週 學習動作", "Weeks 1–4: learn the movements"),
    ("第 5–8 週 加重", "Weeks 5–8: add load"),
    ("第 9–10 週 減量", "Weeks 9–10: taper"),
    ("腳與肩同寬，膝對腳尖，坐到與地面平行再起身", "Feet shoulder-width, knees over toes, sit to parallel and stand"),
    ("前後腳分開，後膝垂直下沉，重心留在前腳", "Split stance, back knee straight down, weight on the front foot"),
    ("背保持直，臀部向後推，感覺大腿後側拉緊", "Back flat, hips back, feel the hamstring load"),
    ("身體成一直線，髖部向上頂，每邊 30 秒", "Body in one line, hips driven up, 30 s per side"),
    ("肩肘成一直線，臀部不塌不翹，正常呼吸", "Shoulder over elbow, hips level, breathe normally"),
    ("仰臥，對側手腳同時伸出，腰貼地", "Lie on your back, opposite arm and leg out, lower back down"),
    ("踏上約膝高的台階，後腳不發力，慢慢落", "Step onto a knee-high box, back leg passive, lower slowly"),
    ("前腳掌站在台階邊緣或器械上，腳跟完全落下再推起，頂點停一秒",
     "Ball of the foot on a step edge, heel all the way down, press up, pause 1 s at the top"),
    ("單腳版本：扶牆或器械平衡，腳跟完全落下再推起", "Single-leg version: hold a wall, heel all the way down, press up"),
    ("半蹲姿勢，帶拉緊，每邊 10 步", "Half squat, band under tension, 10 steps each way"),
    ("深蹲", "Squat"), ("分腿蹲", "Split squat"), ("髖鉸鏈（硬拉／RDL）", "Hip hinge (deadlift / RDL)"),
    ("提踵", "Calf raise"), ("單腿提踵", "Single-leg calf raise"), ("上台階", "Step-up"),
    ("平板支撐", "Plank"), ("側平板", "Side plank"), ("死蟲", "Dead bug"),
    ("彈力帶側向走", "Banded lateral walk"), ("A 下肢＋核心", "A · lower body + core"),
    ("B 髖主導＋單腳", "B · hip hinge + single leg"), ("上肢＋核心", "Upper body + core"),
    # ---- plan.py: table + headings
    ("訓練重點依據", "Why this focus"), ("強度比例", "Intensity mix"), ("醫療", "Medical"),
    ("爬升 (m)", "Ascent (m)"), ("心率區", "HR zone"), ("分鐘", "Min"),
    ("備註", "Note"), ("內容", "Session"), ("做法", "How"), ("階段", "Phase"),
    ("進度", "Progression"), ("時間", "Time"), ("碳水", "Carbs"),
    ("累積爬升", "Total ascent"), ("爬升密度", "Climb density"),
    ("心率區 Z1–Z5", "HR zones Z1–Z5"), ("強度課", "Quality session"),
    ("名詞解釋", "Glossary"), ("注意", "Watch out"), ("訓練計劃", "training plan"),
    # ---- report_html.py
    ("HK100 2027｜訓練評估報告", "Training assessment report"),
    ("路線依「實際與模型之時間差」著色：紅為較慢，綠為較快。",
     "Route coloured by time difference against the model: red slower, green faster."),
    ("路線按地形粗糙度（TRI）上色：綠色平坦、黃色中等、紅色崎嶇（3 m LiDAR DTM）。",
     "Route coloured by terrain ruggedness (TRI): green flat, amber moderate, red broken (3 m LiDAR DTM)."),
    ("模型＝以你本人過往 FIT 記錄擬合的「坡度—速度」關係：同一坡度你平常跑得多快，再逐段換算應需時間。",
     "The model is a grade–speed relationship fitted to your own FIT history: how fast you normally run at a given grade, converted into an expected time per segment."),
    ("以你本人過往 FIT 記錄擬合：每個坡度區間你平均跑多快。用同一條路線逐段換算「應需時間」，再與實際時間比較。它是你自己的基準，不是通用公式。",
     "Fitted to your own FIT history: your average speed in each grade band. Applied segment by segment to give an expected time, then compared with what happened. It is your baseline, not a general formula."),
    ("身體由「可持續」轉為「快速累積乳酸」的分界心率。低於此值可長時間維持；高於此值只能撐數十分鐘。本報告用它換算每次訓練的相對強度。",
     "The heart rate where sustainable effort turns into fast lactate accumulation. Below it you last hours; above it, tens of minutes. Used here to scale relative intensity."),
    ("Riley (1999)：每個像素與周圍八格高差的均方根，單位為米。數值越大，地面越破碎（石級、沖溝、亂石）。本報告以 3 米 LiDAR 裸地 DTM 計算。",
     "Riley (1999): root mean square of the elevation difference to the eight neighbours, in metres. Higher means more broken ground (steps, gullies, loose rock). Computed here from a 3 m LiDAR bare-earth DTM."),
    ("每個像素與周圍八格高差的均方根，單位為米。數值越大，地面越破碎（石級、沖溝、亂石）。本報告以 3 米 LiDAR 裸地 DTM 計算；地圖 3D 起伏為 z12 壓縮顯示級，兩者尺度不同，請勿直接對照高度。",
     "Root mean square of the elevation difference to the eight neighbours, in metres. Higher means more broken ground (steps, gullies, loose rock). Computed from a 3 m LiDAR bare-earth DTM; the 3D relief is a z12 display tile, a coarser scale — do not read heights across the two."),
    ("兩個數列同向變化的程度，範圍 −1 至 +1。+1 完全同步、0 無關、−1 完全反向。|r| 低於 0.3 一般視為關係微弱。",
     "How strongly two series move together, from −1 to +1: +1 identical, 0 unrelated, −1 opposite. |r| below 0.3 is generally a weak relationship."),
    ("把全部路段的數值由小至大排列，九成路段低於此值。用中位數看「典型情況」，用 p90 看「最差的一成」。",
     "All segments sorted low to high: nine in ten fall below this value. Median shows the typical case; p90 shows the worst tenth."),
    ("上柱＝慢於模型，下柱＝快於模型；最大差距 78 秒。", "Bars above the line are slower than model, below are faster."),
    ("比較前段與後段的「速度 ÷ 心率」。正值代表同樣心率跑得更慢，即耐力開始下滑；負值代表後段反而更有效率。已剔除頭 10 分鐘熱身。",
     "Speed ÷ heart rate, first third against last third. Positive means slower at the same heart rate — endurance fading; negative means the back end was more efficient. The first 10 minutes are excluded."),
    ("總爬升 ÷ 總距離，單位 m/km。它反映路線的陡峭程度，用來判斷一次練習是否接近目標賽道的需求。",
     "Total ascent ÷ total distance, in m/km. How steep the route is, used to judge whether a session matches what the race demands."),
    ("本報告由穿戴裝置資料自動計算，僅供訓練參考，不構成醫療建議。GPS、光學心率與氣壓高度計均存在誤差，",
     "Computed automatically from device data. Training reference only, not medical advice. GPS, optical heart rate and barometric altitude all carry error;"),
    ("數據宜作趨勢判讀，不宜視為絕對真值。訓練與比賽決策及受傷風險由使用者自行承擔；如有痛症、舊患或",
     "read trends, not absolutes. Training and racing decisions, and injury risk, remain your own. If you have pain, a prior injury or"),
    ("心血管疾病史，請先諮詢醫生、物理治療師或合資格教練。疼痛為停止訊號，並非數據指標。",
     "a history of cardiovascular disease, consult a clinician, physiotherapist or qualified coach first. Pain is a stop signal, not a data point."),
    ("本週總爬升以目標賽事密度換算：跑量 × 54 m/km（例：30 公里 → 1610 m），分散在長課與爬坡課，不要單節硬塞。",
     "Weekly ascent is set by the race's own density: distance × 54 m/km (e.g. 30 km → 1610 m), spread across the long run and the hill session — never stuffed into one session."),
    ("長課心率維持於 Zone 2（約 110–128 bpm，即 65–75% LTHR），以建立可持續強度基準。",
     "Keep the long run in Zone 2 (about 110–128 bpm, 65–75% LTHR) to build a sustainable baseline."),
    ("本次訓練平均心率 164 bpm，為乳酸閾值心率（Lactate Threshold Heart Rate，LTHR）的 96%（中高強度；不宜以輕鬆長課視之）；LTHR 為估算值。",
     "Average heart rate was 164 bpm — 96% of estimated lactate-threshold heart rate (LTHR). Moderate-to-hard; this is not an easy long run. LTHR is an estimate."),
    ("LTHR 依據：", "LTHR basis: "),
    ("爬升密度為 27 m/km，僅達目標賽事路線 54 m/km 的 51%，比賽特異性不足。",
     "Climb density was 27 m/km — 51% of the race's 54 m/km. Not specific enough to the race."),
    ("LTHR（Lactate Threshold Heart Rate，乳酸閾值心率）", "LTHR (lactate threshold heart rate)"),
    ("TRI（Terrain Ruggedness Index，地形粗糙度指數）", "TRI (terrain ruggedness index)"),
    ("p90（第 90 百分位）", "p90 (90th percentile)"),
    ("r（皮爾森相關係數）", "r (Pearson correlation)"),
    ("後段效率變化（decoupling）", "Late-race decoupling"),
    ("模型（坡度—速度模型）", "The model (grade → speed)"),
    ("分段表現", "Segments"), ("分段數據", "Segment data"), ("待改善路段", "Worst segments"),
    ("綜合評估", "Assessment"), ("訓練建議", "What to do"), ("路線與地形", "Route and terrain"),
    ("名詞解釋", "Glossary"), ("平均心率", "Average HR"), ("後段效率變化", "Decoupling"),
    ("累計爬升", "Ascent"), ("總時間", "Total time"), ("距離", "Distance"),
    ("爬升 m", "Ascent m"), ("與模型差（秒）", "vs model (s)"),
    ("坡度", "Grade"), ("步頻", "Cadence"), ("心率", "HR"), ("公里", "km"),
    ("切換 3D 地形", "3D terrain"), ("切換 2D 平面", "2D map"), ("切換上色", "Recolour"),
    ("▶ 播放", "▶ Play"), ("點擊路線查看分段數據", "Tap the route for segment data"),
    ("較模型慢 ", "slower than model "), ("較模型快 ", "faster than model "), ("與模型一致", "on model"),
    ("坡度 ", "grade "),
    ("本次訓練", "This session"),
    ("每週跑步基準", "base week"), ("賽事爬升密度", "race climb density"),
    ("<span>快</span>", "<span>Fast</span>"), ("<span>慢</span>", "<span>Slow</span>"),
    # ---- shared fragments
    ("越野跑", "trail run"), ("路跑", "road run"),
    ("建量期", "Build"), ("高峰期", "Peak"), ("減量期", "Taper"), ("比賽週", "Race week"),
    ("週一", "Mon"), ("週二", "Tue"), ("週三", "Wed"), ("週四", "Thu"),
    ("週五", "Fri"), ("週六", "Sat"), ("週日", "Sun"),
    ("輕鬆跑", "Easy run"), ("上坡重複", "Hill repeats"), ("落坡技術", "Descent technique"),
    ("長距離越野", "Long trail"), ("肌力", "Strength"), ("比賽", "Race"),
    ("長課", "Long run"), ("充碳", "Carb load"), ("比賽日", "Race day"), ("比賽中", "During the race"),
    ("健身室", "Gym"), ("家中", "Home"), ("戶外", "Outdoors"), ("至", "to"), ("<th>日</th>", "<th>Day</th>"),
    ("小時", "h"), ("地形 AWS Terrain Tiles（Mapzen）", "relief AWS Terrain Tiles (Mapzen)"),
    ("；", "; "), ("：", ": "), ("｜", " | "),
    ("底圖", "Basemap"), ("起點", "Start"), ("終點", "Finish"), ("暫停", "Pause"),
    ("紅色表示該段耗時高於模型預期。", "red means that kilometre took longer than the model expected."),
    ("較模型 ", "vs model "), (" 秒", " s"),
]

PATTERNS = [
    # plan: week heading / meta / warnings / feasibility
    (r"距離比賽 (\d+) 日", r"days to race: \1"),
    (r"(\d+) 週 ·", r"\1 weeks ·"),
    (r"跑步 ([\d.]+) 小時", r"Running \1 h"),
    (r"＋ 肌力 (\d+) 分鐘", r"+ strength \1 min"),
    (r"累積爬升 (\d+) m", r"\1 m ascent"),
    (r"吃力時間佔 (\d+)%", r"\1% hard"),
    (r"賽前激活 ([\d.]+) 小時（不計比賽）", r"race-week activation \1 h (excluded from the race)"),
    (r"比賽 (\d+) km · ", r"Race \1 km · "),
    (r"上次有 (\d+) 段落坡較模型慢，合共慢 (\d+) 秒，最慢一段在 ([\d.]+) 公里",
     r"Last time \1 descending segments were slower than your model — \2 s in total, worst at \3 km"),
    (r"上次有 (\d+) 段上坡較模型慢，合共慢 (\d+) 秒，最慢一段在 ([\d.]+) 公里",
     r"Last time \1 climbing segments were slower than your model — \2 s in total, worst at \3 km"),
    (r"模型預測 ([\d.]+) 小時，目標 ([\d.]+) 小時：目標較預測(快|慢) ([\d.]+) 小時。",
     r"Model predicts \1 h; the target is \2 h — \3 h \4 than the prediction."),
    (r"最長一課 ([\d.]+) 小時，為目標時間的 (\d+)%；提高週量或接受差距。",
     r"Longest run \1 h — \2% of the race time; raise the weekly hours or accept the gap."),
    (r"(\d+) 個星期吃力時間超過兩成（最高 (\d+)%）；80/20 是上限，不是下限。",
     r"\1 weeks carry more than 20% hard time (max \2%). 80/20 is a ceiling, not a target."),
    (r"(\d+) 個星期完全冇強度刺激；超馬可以偏低，但建議保留一節短強度。",
     r"\1 weeks have no hard stimulus at all. Ultramarathons can run low, but keep one short quality session."),
    (r"體重 ([\d.]+) kg · 每日碳水：輕鬆日 (\d+) g／", r"Body mass \1 kg · daily carbohydrate: easy day \2 g /"),
    (r"高強度日 (\d+) g／充碳 (\d+) g ·", r"quality day \1 g / carb load \2 g ·"),
    (r"蛋白質 (\d+)–(\d+) g／日", r"protein \1–\2 g/day"),
    (r"比賽中水分 (\d+)–(\d+) ml/h、鈉\s+(\d+)–(\d+) mg/h", r"During the race: fluid \1–\2 ml/h, sodium \3–\4 mg/h"),
    (r"；場地：(.+?)<", r"; venue: \1<"),
    # report: per-km rows and headers
    (r"第 (\d+) 公里：坡度 ([+\-]?\d+)%，實際較模型慢 (\d+) 秒。", r"Km \1: grade \2%, \3 s slower than model."),
    (r"第 (\d+) 公里：較模型 ([+\-]?\d+) 秒（坡度 ([+\-]?\d+)%）", r"Km \1: \2 s vs model (grade \3%)"),
    (r"第 (\d+) 公里（坡度 ([+\-]?\d+)%）較模型慢 (\d+) 秒，重點為落坡技術：縮短步幅、提高步頻，避免剎車式落腳。",
     r"Km \1 (grade \2%) ran \3 s slower than model — descent technique: shorter stride, higher cadence, no braking foot strike."),
    (r"([\d.]+) km · 累計爬升 (\d+) m", r"\1 km · \2 m ascent"),
    (r"爬升密度 (\d+) / 目標 (\d+) m/km", r"Climb density \1 / target \2 m/km"),
    (r"累計爬升 (\d+) m", r"\1 m ascent"),
    (r"第 (\d+) 週", r"Week \1"),
    # the LTHR basis line is athlete data, not template — pattern it before fragments touch it
    (r"估算：由 (\d{4}-\d{2}-\d{2}) 的 (\d+) km 越野（最大心率 (\d+)）推算 — 最佳 (\d+) 分鐘平均 (\d+) bpm、最佳 (\d+) 分鐘平均 (\d+) bpm；取 (\d+)。非 (\d+) 分鐘實測，誤差約 ±(\d+) bpm。",
     r"Estimated from the \2 km trail run on \1 (max HR \3): best \4-min average \5 bpm, best \6-min average \7 bpm; using \8. Not a \9-minute field test — about ±\10 bpm."),
    (r"各公里相對模型之時間差", r"Time difference vs model, per km"),
]

_LIT = sorted(((z, e) for z, e in LITERALS), key=lambda p: -len(p[0]))
_RX = [(re.compile(p), r) for p, r in PATTERNS]
CJK = re.compile(r"[\u4e00-\u9fff]")


def to_english(html):
    for rx, rep in _RX:              # templated lines first — they carry the numbers
        html = rx.sub(rep, html)
    for z, e in _LIT:                # then fixed fragments
        html = html.replace(z, e)
    return html


def _selfcheck():
    """Fails if the table stops covering a sample of both artefacts' wording."""
    sample = ("<li><b>長課</b>：最長一課 2.5 小時，為目標時間的 16%；提高週量或接受差距。</li>"
              "<p>第 5 公里：坡度 +8%，實際較模型慢 40 秒。</p>")
    out = to_english(sample)
    assert not CJK.search(out), residual(out)
    assert "2.5 h" in out and "16%" in out and "40 s" in out, out
    print("i18n ok")


if __name__ == "__main__":
    _selfcheck()


def residual(html):
    """Lines still holding Chinese — the pass is only done when this is empty."""
    out = []
    for line in re.sub(r"<[^>]+>", "\n", html).splitlines():
        t = " ".join(line.split())
        if CJK.search(t):
            out.append(t)
    return out
