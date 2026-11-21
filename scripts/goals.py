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


def daily_targets(sex, weight, height, age, activity="轻度", goal="维持", workout_day=None):
    """返回每日目标：热量、宏量营养素（克 + 供能比）、BMR、TDEE。
    支持普通健身人群的碳水循环与训练日/休息日动态适配 (workout_day=True/False/None)。"""
    if goal not in GOAL_FACTOR:
        raise ValueError(f"未知目标: {goal}，可选：{'/'.join(GOAL_FACTOR)}")
    if not (20 <= float(weight) <= 300):
        raise ValueError(f"体重应在 20-300 kg 之间，收到: {weight}")
    if not (50 <= float(height) <= 260):
        raise ValueError(f"身高应在 50-260 cm 之间，收到: {height}")
    if not (1 <= int(age) <= 120):
        raise ValueError(f"年龄应在 1-120 岁之间，收到: {age}")
    w = float(weight)
    h = float(height)
    a = int(age)
    bmr = bmr_mifflin(sex, w, h, a)
    tdee = bmr * resolve_activity(activity)
    s = str(sex).strip().lower()
    male = s in ("男", "男性", "m", "male")
    safety_floor = 1500 if male else 1200

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

    def _calc_target_block(cal_val, carb_ratio, fat_ratio, protein_ratio, day_label):
        cal_adj = max(cal_val, safety_floor)
        # 依据国际运动营养学会 (ISSN)，抗阻与增肌减脂人群优先以体重锚定蛋白质 (1.6~2.2 g/kg)
        p_anchor = w * anchor_per_kg
        if goal in ("减重", "减脂", "增肌", "增重"):
            p_g = p_anchor
            rem_cal = max(0.0, cal_adj - p_g * 4)
            tot_cf_ratio = carb_ratio + fat_ratio
            c_g = (rem_cal * (carb_ratio / tot_cf_ratio)) / 4 if tot_cf_ratio > 0 else (cal_adj * carb_ratio / 4)
            f_g = (rem_cal * (fat_ratio / tot_cf_ratio)) / 9 if tot_cf_ratio > 0 else (cal_adj * fat_ratio / 9)
        else:
            p_g = cal_adj * protein_ratio / 4
            c_g = cal_adj * carb_ratio / 4
            f_g = cal_adj * fat_ratio / 9

        return {
            "day_type": day_label,
            "cal_target": round(cal_adj),
            "protein_g_target": round(p_g),
            "protein_g_per_kg": round(p_g / w, 2),
            "carb_g_target": round(c_g),
            "fat_g_target": round(f_g),
            "ratio": {
                "蛋白": round(p_g * 4 / cal_adj, 2),
                "碳水": round(c_g * 4 / cal_adj, 2),
                "脂肪": round(f_g * 9 / cal_adj, 2),
            },
        }

    # 1. 常规基准目标 (Standard Baseline)
    base_adjust = GOAL_FACTOR.get(goal, 0)
    std_ratio = {"蛋白": 0.25, "碳水": 0.45, "脂肪": 0.30}
    if goal in ("增肌", "增重"):
        std_ratio = {"蛋白": 0.30, "碳水": 0.45, "脂肪": 0.25}
    if goal in ("减重", "减脂"):
        std_ratio = {"蛋白": 0.30, "碳水": 0.40, "脂肪": 0.30}
    standard_target = _calc_target_block(tdee + base_adjust, std_ratio["碳水"], std_ratio["脂肪"], std_ratio["蛋白"], "standard")

    # 2. 训练日目标 (Workout Day: 充足碳水支撑大重量训练，防肌糖原耗竭，促进肌肥大)
    if goal in ("减重", "减脂"):
        # 减脂训练日：温和赤字 (-200 kcal)，提高碳水供能比至 45%，保障力量输出与抗阻强度
        wk_cal = tdee - 200
        wk_target = _calc_target_block(wk_cal, 0.45, 0.25, 0.30, "workout")
    elif goal in ("增肌", "增重"):
        # 增肌训练日：充分盈余 (+400 kcal)，碳水 50% 促进肌糖原超量恢复
        wk_cal = tdee + 400
        wk_target = _calc_target_block(wk_cal, 0.50, 0.25, 0.25, "workout")
    else:
        # 维持训练日：补充训练消耗 (+200 kcal)
        wk_cal = tdee + 200
        wk_target = _calc_target_block(wk_cal, 0.48, 0.27, 0.25, "workout")

    # 3. 休息日目标 (Rest Day: 低碳控胰岛素，深化赤字，提升健康脂肪维持激素稳定)
    if goal in ("减重", "减脂"):
        # 减脂休息日：充分赤字 (-500 kcal)，碳水调至 32%，脂肪 35% 延长饱腹感并稳定性激素
        rst_cal = tdee - 500
        rst_target = _calc_target_block(rst_cal, 0.32, 0.35, 0.33, "rest")
    elif goal in ("增肌", "增重"):
        # 增肌休息日：维持热量 (+100 kcal 微盈余)，避免休息日过多脂肪堆积
        rst_cal = tdee + 100
        rst_target = _calc_target_block(rst_cal, 0.42, 0.30, 0.28, "rest")
    else:
        # 维持休息日：平衡补偿 (-150 kcal)
        rst_cal = tdee - 150
        rst_target = _calc_target_block(rst_cal, 0.40, 0.35, 0.25, "rest")

    # 解析当前选择的目标类型
    active = standard_target
    day_type = "standard"
    if workout_day is not None:
        if isinstance(workout_day, str):
            w_str = workout_day.strip().lower()
            is_wk = w_str in ("workout", "training", "1", "true", "yes", "训练", "练", "训练日")
        else:
            is_wk = bool(workout_day)
        if is_wk:
            active = wk_target
            day_type = "workout"
        else:
            active = rst_target
            day_type = "rest"

    return {
        "bmr": round(bmr),
        "tdee": round(tdee),
        "activity": activity,
        "goal": goal,
        "safety_floor": safety_floor,
        "day_type": day_type,
        "cal_target": active["cal_target"],
        "ratio": active["ratio"],
        "protein_g_target": active["protein_g_target"],
        "protein_g_per_kg": active["protein_g_per_kg"],
        "carb_g_target": active["carb_g_target"],
        "fat_g_target": active["fat_g_target"],
        "workout_targets": wk_target,
        "rest_targets": rst_target,
        "standard_targets": standard_target,
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

    # 计算最新 7 日平滑趋势体重 (7-Day Moving Trend Weight)
    recent_weights = [x["weight"] for x in weights_logged[-7:]]
    trend_weight = round(sum(recent_weights) / len(recent_weights), 2) if recent_weights else last_w["weight"]

    # 减脂平台期检测与 Refeed (充碳日) 智能诊断
    plateau_detected = False
    refeed_recommended = False
    refeed_strategy = None
    if delta_days >= 14 and (fallback_tdee - avg_intake >= 250) and abs(delta_weight) <= 0.35:
        plateau_detected = True
        refeed_recommended = True
        ref_cal = round(fallback_tdee)
        ref_carb = round(ref_cal * 0.55 / 4)
        ref_protein = round(last_w["weight"] * 1.8)
        ref_fat = round((ref_cal - ref_carb * 4 - ref_protein * 4) / 9)
        refeed_strategy = {
            "title": "打破减脂瓶颈：单日高碳充碳日建议 (Refeed Day)",
            "cal_target": ref_cal,
            "carb_g": ref_carb,
            "protein_g": ref_protein,
            "fat_g": max(25, ref_fat),
            "mechanism": "连续持续赤字引发了机体瘦素(Leptin)下调与代谢适应。安排 1 天维持热量高碳饮食（严格低脂），可有效刺激甲状腺素T3与瘦素回升，为后续继续减脂重塑敏感度。"
        }

    res_out = {
        "status": "calibrated",
        "message": f"闭环自适应校准成功：基于 {delta_days} 天真实体重变化 ({delta_weight:+.2f}kg) 与日均摄入 ({avg_intake:.0f} kcal) 反推计算",
        "adaptive_tdee": round(clamped_tdee),
        "empirical_tdee": round(fallback_tdee),
        "metabolic_deviation": deviation,
        "days_span": delta_days,
        "delta_weight_kg": round(delta_weight, 2),
        "avg_daily_intake_kcal": round(avg_intake, 1),
        "trend_weight_kg": trend_weight,
        "plateau_detected": plateau_detected,
        "refeed_recommended": refeed_recommended,
    }
    if refeed_strategy:
        res_out["refeed_strategy"] = refeed_strategy
    return res_out


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
