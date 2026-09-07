# -*- coding: utf-8 -*-
"""目标管理：BMR / TDEE / 每日热量与营养素目标推荐（Mifflin-St Jeor 公式）。
"""
import json
import sys

# Windows 控制台默认 gbk，设为 utf-8 以避免中文输出乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def bmr_mifflin(sex, weight_kg, height_cm, age):
    """Mifflin-St Jeor 基础代谢率 (kcal/day)。sex: '男'/'女'/'M'/'F'。"""
    male = sex in ("男", "M", "m", "男性")
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if male else base - 161


ACTIVITY = {
    "久坐": 1.2,
    "轻度": 1.375,
    "中度": 1.55,
    "重度": 1.725,
    "极高": 1.9,
}
# 常用活动量别名
_ACTIVITY_ALIAS = {
    "久坐": "久坐", "不运动": "久坐", "坐办公室": "久坐",
    "轻度": "轻度", "轻": "轻度", "每周运动1-3次": "轻度",
    "中度": "中度", "中": "中度", "每周运动3-5次": "中度",
    "重度": "重度", "重": "重度", "每周运动6-7次": "重度",
    "极高": "极高", "每天剧烈运动": "极高",
}

GOAL_FACTOR = {
    "减重": -500,
    "减脂": -400,
    "维持": 0,
    "增肌": 300,
    "增重": 400,
}


def resolve_activity(name):
    name = str(name).strip()
    return ACTIVITY.get(_ACTIVITY_ALIAS.get(name, name), 1.375)


def resolve_activity_name(name):
    name = str(name).strip()
    return _ACTIVITY_ALIAS.get(name, name)


def daily_targets(sex, weight, height, age, activity="轻度", goal="维持"):
    """返回每日目标：热量、宏量营养素（克 + 供能比）、BMR、TDEE。"""
    bmr = bmr_mifflin(sex, weight, height, age)
    tdee = bmr * resolve_activity(activity)
    adjust = GOAL_FACTOR.get(goal, 0)
    cal = tdee + adjust
    cal = max(cal, 1200)  # 底线

    # 供能比默认：蛋白质25%(增肌可上调)，碳水45%，脂肪30%
    ratio = {"蛋白": 0.25, "碳水": 0.45, "脂肪": 0.30}
    if goal in ("增肌", "增重"):
        ratio = {"蛋白": 0.30, "碳水": 0.45, "脂肪": 0.25}
    if goal in ("减重", "减脂"):
        ratio = {"蛋白": 0.30, "碳水": 0.40, "脂肪": 0.30}

    protein_g = cal * ratio["蛋白"] / 4
    carb_g = cal * ratio["碳水"] / 4
    fat_g = cal * ratio["脂肪"] / 9
    return {
        "bmr": round(bmr),
        "tdee": round(tdee),
        "activity": activity,
        "goal": goal,
        "cal_target": round(cal),
        "ratio": ratio,
        "protein_g_target": round(protein_g),
        "carb_g_target": round(carb_g),
        "fat_g_target": round(fat_g),
    }


def main():
    if len(sys.argv) >= 5:
        sex, weight, height, age = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4])
        activity = sys.argv[5] if len(sys.argv) > 5 else "轻度"
        goal = sys.argv[6] if len(sys.argv) > 6 else "维持"
    else:
        sex, weight, height, age, activity, goal = "男", 70, 175, 30, "轻度", "减重"
    print(json.dumps(daily_targets(sex, weight, height, age, activity, goal), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
