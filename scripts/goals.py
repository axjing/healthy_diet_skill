# -*- coding: utf-8 -*-
"""目标管理：BMR / TDEE / 每日热量与营养素目标推荐（Mifflin-St Jeor 公式）。
"""
import json
import os
import sys
from datetime import datetime, timedelta

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

    # 依据 ISSN / Morton et al.，按目标设定体重锚定蛋白质每公斤克数，
    # 彻底消除“热量赤字越大、蛋白质目标反而越萎缩”的代谢分解悖论
    protein_anchor_map = {
        "减重": 1.9,
        "减脂": 1.9,
        "维持": 1.4,
        "增肌": 1.8,
        "增重": 1.8,
    }
    anchor_per_kg = protein_anchor_map.get(goal, 1.5)
    protein_by_weight = float(weight) * anchor_per_kg
    protein_by_ratio = cal * ratio["蛋白"] / 4
    # 取二者中更安全的充足值（减脂低热量时优先体重锚定，防止肌肉流失）
    protein_g = max(protein_by_ratio, protein_by_weight) if goal in ("减重", "减脂") else protein_by_ratio

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


def calibrate_adaptive_tdee(records_dir, fallback_tdee=2000.0, window_days=30):
    """闭环自适应代谢遥测：基于过去 window_days 天的体重遥测变化与实际净摄入反推真实物理 TDEE。
    原理公式：Delta Energy (kcal) = Delta Weight (kg) * 7700 kcal
    真实 TDEE = 平均净摄入 - (Delta Energy / 间隔天数)
    """
    if not os.path.exists(records_dir):
        return {
            "status": "insufficient_data",
            "message": "暂无历史饮食记录，继续使用先验经验公式 (Mifflin-St Jeor)",
            "tdee": round(fallback_tdee)
        }

    files = sorted([f for f in os.listdir(records_dir) if f.endswith(".json") and len(f) == 15])
    if len(files) < 7:
        return {
            "status": "insufficient_data",
            "message": f"当前记录天数 ({len(files)} 天) 不足 7 天，暂无法构建自适应闭环模型，继续使用先验估算",
            "days_recorded": len(files),
            "tdee": round(fallback_tdee)
        }

    cutoff = (datetime.now() - timedelta(days=window_days)).strftime("%Y-%m-%d")
    valid_data = []
    for fname in files:
        d_str = fname[:-5]
        if d_str < cutoff:
            continue
        p = os.path.join(records_dir, fname)
        try:
            with open(p, encoding="utf-8") as f:
                day = json.load(f)
        except Exception:
            continue
        cal_total = sum(m.get("totals", {}).get("cal", 0) for m in day.get("meals", []))
        ex_total = sum(e.get("cal", 0) for e in day.get("exercise", []))
        w = day.get("weight")
        valid_data.append({
            "date": d_str,
            "intake": cal_total,
            "exercise": ex_total,
            "net": cal_total - ex_total,
            "weight": float(w) if w is not None else None
        })

    weights_logged = [x for x in valid_data if x["weight"] is not None]
    if len(weights_logged) < 2:
        return {
            "status": "missing_weight_telemetry",
            "message": "体重遥测数据不足（需至少记录 2 次以上体重），请使用 `diet weight <kg>` 记录晨起体重以开启代谢自适应闭环",
            "weights_count": len(weights_logged),
            "tdee": round(fallback_tdee)
        }

    first_w = weights_logged[0]
    last_w = weights_logged[-1]
    d_start = datetime.strptime(first_w["date"], "%Y-%m-%d")
    d_end = datetime.strptime(last_w["date"], "%Y-%m-%d")
    delta_days = (d_end - d_start).days

    if delta_days < 7:
        return {
            "status": "time_span_too_short",
            "message": f"两次体重记录间隔仅 {delta_days} 天（建议至少 7 天以消除水分波动干扰），继续使用基准 TDEE",
            "days_between": delta_days,
            "tdee": round(fallback_tdee)
        }

    period_data = [x for x in valid_data if first_w["date"] <= x["date"] <= last_w["date"]]
    avg_intake = sum(x["intake"] for x in period_data) / max(len(period_data), 1)

    delta_weight = last_w["weight"] - first_w["weight"]
    delta_stored_energy = delta_weight * 7700.0
    daily_energy_flux = delta_stored_energy / delta_days

    adaptive_tdee_val = avg_intake - daily_energy_flux
    clamped_tdee = max(1000.0, min(4500.0, adaptive_tdee_val))
    deviation = round(clamped_tdee - fallback_tdee, 1)

    return {
        "status": "calibrated",
        "message": f"闭环自适应校准成功：基于 {delta_days} 天真实体重变化 ({delta_weight:+.2f}kg) 与日均摄入 ({avg_intake:.0f} kcal) 反推计算",
        "adaptive_tdee": round(clamped_tdee),
        "empirical_tdee": round(fallback_tdee),
        "metabolic_deviation": deviation,
        "days_span": delta_days,
        "delta_weight_kg": round(delta_weight, 2),
        "avg_daily_intake_kcal": round(avg_intake, 1)
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
