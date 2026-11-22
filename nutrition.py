#!/usr/bin/env python3
"""Race nutrition targets — arithmetic on published guidelines, not opinions.

Sources (see references/sport-science.md):
  Thomas, Erdman & Burke 2016, ACSM / AND / DC position stand,
  Med Sci Sports Exerc 48(3):543-568
    - daily carbohydrate 3-12 g/kg body mass depending on load
    - carbohydrate loading 10-12 g/kg for 36-48 h before events > 90 min
    - during exercise 30-60 g/h for 1-2.5 h, up to 90 g/h beyond, using
      multiple transportable carbohydrates
    - protein 1.2-2.0 g/kg for endurance athletes
  Fluid and sodium are sweat-rate dependent: the stand gives ranges, not targets.

Everything below is a RANGE from that stand scaled by body mass and race
duration. It is not personalised, and it is not medical advice.
"""
import json
import sys


def targets(weight_kg, race_hours):
    w, h = float(weight_kg), float(race_hours)
    return dict(
        weight_kg=w,
        carb_easy_g=round(w * 5),
        carb_quality_g=round(w * 8),
        carb_load_g=round(w * 10),
        protein_g=(round(w * 1.2), round(w * 2.0)),
        race_carb_g_h=(60, 90),
        race_carb_total_g=(round(60 * h), round(90 * h)),
        fluid_ml_h=(400, 800),
        sodium_mg_h=(300, 600),
    )


def race_week(t, race_hours):
    """D-7 to race day. Carb load is 36-48 h; low fat and low fibre during the
    load is a gut-comfort convention, not a measured requirement."""
    load = t["carb_load_g"]
    normal = t["carb_quality_g"]
    return [
        dict(day="D-7 至 D-4", carbs_g=normal,
             note="正常訓練飲食；每餐有碳水，蛋白質 1.2–2.0 g/kg。"),
        dict(day="D-3", carbs_g=load,
             note="開始充碳；減少油脂與高纖食物（走油、少菜梗），避免腸胃負擔。"),
        dict(day="D-2", carbs_g=load, note="充碳第二日；飲水正常，不需刻意灌水。"),
        dict(day="D-1", carbs_g=round(load * 0.9),
             note="晚餐以易消化碳水為主，份量熟悉，不試新食物。"),
        dict(day="比賽日早上", carbs_g=round(t["weight_kg"] * 2),
             note="賽前 2–3 小時，1–2 g/kg 易消化碳水；賽前 15 分鐘可再 15–30 g。"),
        dict(day="比賽中", carbs_g=t["race_carb_total_g"],
             note=f"每小時 {t['race_carb_g_h'][0]}–{t['race_carb_g_h'][1]} g，"
                  f"合共約 {t['race_carb_total_g'][0]}–{t['race_carb_total_g'][1]} g；"
                  f"用多種可轉運碳水（葡萄糖＋果糖），每 20–30 分鐘一次。"),
    ]


def as_text(t, race_hours):
    rows = race_week(t, race_hours)
    lines = [f"體重 {t['weight_kg']:g} kg · 目標時間 {race_hours:g} h",
             f"每日碳水：輕鬆日 {t['carb_easy_g']} g／質量日 {t['carb_quality_g']} g／"
             f"充碳 {t['carb_load_g']} g",
             f"蛋白質 {t['protein_g'][0]}–{t['protein_g'][1]} g／日"]
    for r in rows:
        g = r["carbs_g"]
        g = f"{g[0]}–{g[1]} g" if isinstance(g, tuple) else f"{g} g"
        lines.append(f"  {r['day']:<10} {g:<12} {r['note']}")
    return "\n".join(lines)


if __name__ == "__main__":
    weight = float(sys.argv[1]) if len(sys.argv) > 1 else 60
    hours = float(sys.argv[2]) if len(sys.argv) > 2 else 16
    print(as_text(targets(weight, hours), hours))
