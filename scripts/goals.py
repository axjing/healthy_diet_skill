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
    s = str(sex).strip().lower()
    male = s in ("男", "男性", "m", "male")
    female = s in ("女", "女性", "f", "female")
    if not male and not female:
        raise ValueError(f"性别应为 男/女（或 M/F），收到: {sex}")
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
    key = _ACTIVITY_ALIAS.get(name, name)
    if key not in ACTIVITY:
        raise ValueError(f"未知活动量: {name}，可选：久坐/轻度/中度/重度/极高"
                         "（别名：不运动/每周运动1-3次/每周运动3-5次/每周运动6-7次/每天剧烈运动）")
    return ACTIVITY[key]


def resolve_activity_name(name):
    name = str(name).strip()
    return _ACTIVITY_ALIAS.get(name, name)


def daily_targets(sex, weight, height, age, activity="轻度", goal="维持"):
    """返回每日目标：热量、宏量营养素（克 + 供能比）、BMR、TDEE。"""
    if goal not in GOAL_FACTOR:
        raise ValueError(f"未知目标: {goal}，可选：{'/'.join(GOAL_FACTOR)}")
    if not (20 <= float(weight) <= 300):
        raise ValueError(f"体重应在 20-300 kg 之间，收到: {weight}")
    if not (50 <= float(height) <= 260):
        raise ValueError(f"身高应在 50-260 cm 之间，收到: {height}")
    if not (1 <= int(age) <= 120):
        raise ValueError(f"年龄应在 1-120 岁之间，收到: {age}")
    bmr = bmr_mifflin(sex, float(weight), float(height), int(age))
    tdee = bmr * resolve_activity(activity)
    adjust = GOAL_FACTOR.get(goal, 0)
    cal = tdee + adjust
    s = str(sex).strip().lower()
    male = s in ("男", "男性", "m", "male")
    safety_floor = 1500 if male else 1200
    cal = max(cal, safety_floor)  # 依据临床与运动营养学指南，区分男/女性最低生理代谢安全底线

    # 供能比默认：蛋白质25%(增肌可上调)，碳水45%，脂肪30%
    ratio = {"蛋白": 0.25, "碳水": 0.45, "脂肪": 0.30}
    if goal in ("增肌", "增重"):
        ratio = {"蛋白": 0.30, "碳水": 0.45, "脂肪": 0.25}
    if goal in ("减重", "减脂"):
        ratio = {"蛋白": 0.30, "碳水": 0.40, "脂肪": 0.30}

    protein_g = cal * ratio["蛋白"] / 4
    carb_g = cal * ratio["碳水"] / 4
    fat_g = cal * ratio["脂肪"] / 9
    protein_g_per_kg = round(protein_g / float(weight), 2)
    return {
        "bmr": round(bmr),
        "tdee": round(tdee),
        "activity": activity,
        "goal": goal,
        "safety_floor": safety_floor,
        "cal_target": round(cal),
        "ratio": ratio,
        "protein_g_target": round(protein_g),
        "protein_g_per_kg": protein_g_per_kg,
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
