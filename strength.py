#!/usr/bin/env python3
"""Two strength sessions with sets, reps, progression and simple pictograms.

Why strength at all: Beattie 2017 (running economy), Ronnestad & Mujika 2014
(concurrent training). Placement matters more than the exercises — a hard
lifting session the day before a quality run blunts the run.

The drawings are deliberately crude side-view pictograms, not photographs. They
show the shape of the movement; they are not a form check.
"""
import sys

# name, cue, sets x reps by block, svg key
BLOCKS = [
    ("第 1–4 週 學習動作", "3 組 × 8 次，最後 2 次仍可保持姿勢（RPE 6）"),
    ("第 5–8 週 加重", "4 組 × 6 次，重量加到第 3 組開始吃力（RPE 7–8）"),
    ("第 9–10 週 減量", "2 組 × 6 次，重量不變、組數減半（RPE 6）"),
]

SESSION_A = [
    ("深蹲", "腳與肩同寬，膝對腳尖，坐到與地面平行再起身", "squat"),
    ("分腿蹲", "前後腳分開，後膝垂直下沉，重心留在前腳", "split"),
    ("提踵", "前腳掌站在台階邊緣或器械上，腳跟完全落下再推起，頂點停一秒", "calf"),
    ("平板支撐", "肩肘成一直線，臀部不塌不翹，正常呼吸", "plank"),
    ("側平板", "身體成一直線，髖部向上頂，每邊 30 秒", "side"),
]

SESSION_B = [
    ("髖鉸鏈（硬拉／RDL）", "背保持直，臀部向後推，感覺大腿後側拉緊", "hinge"),
    ("上台階", "踏上約膝高的台階，後腳不發力，慢慢落", "step"),
    ("單腿提踵", "單腳版本：扶牆或器械平衡，腳跟完全落下再推起", "calf"),
    ("死蟲", "仰臥，對側手腳同時伸出，腰貼地", "deadbug"),
    ("彈力帶側向走", "半蹲姿勢，帶拉緊，每邊 10 步", "band"),
]


def _fig(kind):
    """Crude side-view pictogram. Head circle + limbs; posture is the point."""
    head = "<circle cx='50' cy='14' r='7' fill='none' stroke='#222' stroke-width='2'/>"
    body = {"squat": "<path d='M50 21 L46 45' /><path d='M46 45 L34 58 L36 74' />"
                      "<path d='M46 45 L58 58 L56 74' /><path d='M46 30 L62 34' />",
            "split": "<path d='M50 21 L48 44' /><path d='M48 44 L30 52 L26 72' />"
                     "<path d='M48 44 L64 56 L70 72' /><path d='M48 30 L64 36' />",
            "calf": "<path d='M50 21 L50 46' /><path d='M50 46 L50 70 L46 78' />"
                    "<path d='M50 46 L50 70 L56 78' /><path d='M50 30 L66 34' />",
            "plank": "<path d='M22 34 L66 40' /><path d='M30 34 L18 52' />"
                     "<path d='M66 40 L76 52' />",
            "side": "<path d='M28 40 L60 46' /><path d='M32 40 L26 56' />",
            "hinge": "<path d='M50 21 L44 44' /><path d='M44 44 L36 60 L38 76' />"
                     "<path d='M44 44 L56 60 L58 76' /><path d='M44 30 L66 42' />",
            "step": "<path d='M50 21 L48 44' /><path d='M48 44 L34 60 L36 76' />"
                    "<path d='M48 44 L64 52 L66 62' /><rect x='58' y='62' width='24' height='14' "
                    "fill='none' stroke='#bbb' stroke-width='1.5'/>",
            "deadbug": "<path d='M26 40 L58 40' /><path d='M30 40 L16 26' />"
                       "<path d='M58 40 L74 28' />",
            "band": "<path d='M50 21 L48 44' /><path d='M48 44 L36 58 L34 74' />"
                    "<path d='M48 44 L60 58 L62 74' /><path d='M34 74 L52 74' "
                    "stroke='#c33' stroke-dasharray='4 3'/>"}
    return (f"<svg viewBox='0 0 100 84' width='78' height='66' "
            f"xmlns='http://www.w3.org/2000/svg'>{head}<g fill='none' stroke='#222' "
            f"stroke-width='2.2' stroke-linecap='round'>{body[kind]}</g></svg>")


def sessions(equipment="gym"):
    """Return the two sessions, downgraded to what the athlete actually has."""
    a, b = SESSION_A, SESSION_B
    if equipment == "home":
        a = [x for x in a if x[2] in ("squat", "split", "calf", "plank", "side")]
        b = [x for x in b if x[2] in ("hinge", "step", "calf", "deadbug", "band")]
    elif equipment == "none":
        a = [x for x in a if x[2] in ("squat", "split", "calf", "plank")]
        b = [x for x in b if x[2] in ("hinge", "step", "calf", "deadbug")]
    return [("A 下肢＋核心", a), ("B 髖主導＋單腳", b)]


def as_text(equipment="gym"):
    lines = []
    for title, exs in sessions(equipment):
        lines.append(title)
        for name, cue, _ in exs:
            lines.append(f"  {name:<14} {cue}")
        lines.append("")
    for head, detail in BLOCKS:
        lines.append(f"{head}: {detail}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(as_text(sys.argv[1] if len(sys.argv) > 1 else "gym"))
