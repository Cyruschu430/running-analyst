# 計算依據與文獻來源

每一項輸出都必須能追溯到三類來源之一。報告與 skill 不得混用。

| 標記 | 含義 | 可否作為賣點 |
|---|---|---|
| ✅ 同儕評審 | 期刊論文，有 DOI／卷期 | 可以，需註明 |
| ⚠️ 廠商／教練慣例 | 業界廣泛使用但無同儕評審 | 只可作參考，須標示 |
| 🔬 本人實測 | 由使用者自身數據回歸得出，n = 1 | **不可**當作通用模型 |

---

## 1. 坡度與速度／能量成本 ✅

**Minetti AE, Moia C, Roi GS, Susta D, Ferretti G.** Energy cost of walking and
running at extreme uphill and downhill slopes. *Journal of Applied Physiology*
93:1039–1046, 2002.

- 跑步平地能量成本約 3.40 J·kg⁻¹·m⁻¹、步行約 1.64；上坡急升，下坡下降。
- +45% 坡度時，步行成本低於跑步 → 「陡坡改為步行較省」的生理依據（power hiking）。
- **用途**：作為坡度—速度曲線的理論對照基準，以及上坡策略（幾時該走）的依據。
- **限制**：跑步機、恆速、極端坡度；不考慮技術地形（樓梯、碎石）。

> 本工具**沒有**直接套用 Minetti 公式。見第 2 節。

## 2. 個人坡度—速度模型 🔬

由使用者本人的 FIT 逐秒資料，按坡度分箱（±20%、每 5% 一格）計算平均速度，
建成 `speed = f(grade)` 曲線；每箱至少 60 個樣本。

- **性質**：純經驗回歸，n = 1。**不是**文獻模型，不可外推到其他人。
- **用途**：分段「實際 vs 模型」比較 —— 同一運動員、同一裝置、同一時期內的相對判讀。
- **限制**：樣本不足的坡度區間會被剔除；技術地形與疲勞不在模型內；超過約 2.5 小時的
  外推未經驗證。
- **升級路徑**：Phase 4 以混合效應模型（每位跑手一個隨機效應）擴展至多運動員。

## 3. 有氧解耦（Pa:HR decoupling）⚠️→✅

- **概念來源（教練慣例）**：Joe Friel 提出以「前半／後半 配速:心率 比率變化」判斷
  有氧基礎，常用的 5% 門檻屬教練經驗值，非論文結論。標記為 ⚠️。
- **生理機制（同儕評審）**：**Coyle EF, González-Alonso J.** Cardiovascular drift
  during prolonged exercise: new perspectives. *Exercise and Sport Sciences Reviews*
  29(2):88–92, 2001. —— 長時間運動下每搏輸出量下降、心率上升，心率漂移主要源自心率
  上升而非皮膚血流增加。
- **本工具做法**：只取平坦段（±2%）、移動樣本，分成三段比較速度與心率；輸出百分比。
- **限制**：高溫高濕會放大漂移；不可區分「疲勞」與「脫水／補給不足」；心率光學感測有
  15–45 秒延遲。

## 4. 訓練負荷（TRIMP 類）✅

**Banister EW.** Modeling elite athletic performance. In: MacDougall JD, Wenger HA,
Green HJ (eds). *Physiological Testing of Elite Athletes*. Champaign, IL: Human
Kinetics, 1991.

- 以心率儲備加權 × 時間，得出單一負荷值；後續衍生出 fitness–fatigue（衝量—反應）模型。
- **用途**：跨課比較訓練壓力、安排恢復。
- **限制**：依賴準確的最大心率與靜息心率；不反映機械負荷（跑量、下坡衝擊）。

## 5. 地形難度指數 ✅

**Riley SJ, DeGloria SD, Elliot R.** A terrain ruggedness index that quantifies
topographic heterogeneity. *Photogrammetric Engineering & Remote Sensing*
65(7):837–844, 1999.

- TRI = 中心像元與八鄰域高程差的平方和開方。用於連續地形粗糙度，而非分類標籤。
- **用途**：配合坡度標準差、平面／剖面曲率，建立連續「技術難度」指數。
- **限制**：香港無可靠 trail surface 資料集；TRI 只反映高程變化，不区分樓梯、碎石、
  濕滑。需要正交影像＋視覺模型作第二通道。

## 6. 地圖對位（chainage map-matching）

**Newson P, Krumm J.** Hidden Markov map matching through noise and sparseness.
*Proceedings of ACM SIGSPATIAL GIS*, 2009.

- 以 HMM 將含噪 GPS 軌跡吸附到路網，處理 10–30 公尺誤差與稀疏取樣。
- **用途**：把逐秒資料對應到「沿線距離（chainage）」，令分段、檢查點、官方分段可對齊。
- **限制**：需要可靠路線幾何；香港山徑在 OSM 的精度不一。DOI 待補。

## 7. 心率變異（HRV）與恢復

**Plews DJ, Laursen PB, Stanley J, Kilding AE, Buchheit M.** Training adaptation and
heart rate variability in elite endurance athletes. *International Journal of Sports
Physiology and Performance* 8(2):161–167, 2013.（待核實卷期）

- 以個人基線的滾動平均比較每日 HRV，而非固定門檻。
- **限制**：腕式裝置的夜間 HRV 與胸帶／ECG 不可互換。

## 8. 明確不採用

- **ACWR（急慢性負荷比）**：Gabbett 2016 提出後受到方法學批評（如 Impellizzeri 等），
  本工具不作為處方依據。
- **VDOT／Daniels 表**：出自教練著作而非同儕評審，僅可作對話參考，不進報告數字。
- **廠商專有指標**（COROS Effort Pace、Strava GAP、Garmin Training Effect）：屬閉源
  實作，只可引用為「裝置聲稱」，不可當作獨立驗證。

---

## 報告撰寫規則

1. 每個數字後面能指回上面其中一節；指不到就不要寫。
2. 🔬 類結論必須在報告內標明「本人實測，n = 1」。
3. ⚠️ 類結論必須寫「業界慣例」而非「研究顯示」。
4. 任何未列於此文件的模型，不得在報告中出現。

## Vertical-density benchmark — ⚠️ convention, not a standard

No body publishes a universal "m/km" requirement per distance. The category
figures in `GOALS` (5 / 10 / 30 / 45) are working conventions and are labelled
as such in the report. When the profile names a target event with its distance
and D+, the benchmark is taken from **the organiser's own route** — HK100 2027 is
5,142 m over 96 km = 53.6 m/km — which is a fact about the course, not a claim
about physiology. Prefer the event figure whenever it exists.

## Strength training — ✅ peer reviewed

- **Beattie et al. 2017**, *J Strength Cond Res* — strength training improves
  running economy in distance runners without bulk gain.
- **Rønnestad & Mujika 2014**, *Scand J Med Sci Sports* — concurrent strength and
  endurance training: performance improves when sessions are separated, and
  strength placed immediately before a key endurance session blunts it.

Placement rule used by `plan.py`: two short sessions a week (default 30 min,
lower-body compound + trunk), never on the day before the quality session or
the long run. Volume is reported separately from running hours — strength is
not hidden inside the running week.

⚠️ Volume and page numbers above should be re-checked against the published
record before any public citation.
