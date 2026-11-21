# -*- coding: utf-8 -*-
"""健康评估与建议：根据单日摄入汇总和营养目标给出调优建议。"""
import json
import os
import sys
from datetime import datetime

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _CURRENT_DIR not in sys.path:
    sys.path.insert(0, _CURRENT_DIR)

try:
    from . import app, calc, goals
except (ImportError, ValueError):
    import app
    import calc
    import goals

# Windows 控制台默认 gbk，设为 utf-8 以避免中文输出乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def build_telemetry(t, targets, st, day_data=None):
    """提取纯净的生理指标与量化偏差遥测向量 (Quantitative Telemetry Vector)，专供 Agent 决策认知。"""
    cal_actual = t.get("cal", 0.0)
    cal_target = targets.get("cal_target") if targets else None
    cal_rem = round(max(0.0, cal_target - cal_actual), 1) if cal_target else None
    cal_delta = round(cal_actual - cal_target, 1) if cal_target else 0.0

    p_actual = t.get("protein", 0.0)
    p_target = targets.get("protein_g_target") if targets else None
    p_gap = round(max(0.0, p_target - p_actual), 1) if p_target else 0.0

    c_actual = t.get("carb", 0.0)
    c_target = targets.get("carb_g_target") if targets else None

    f_actual = t.get("fat", 0.0)
    f_target = targets.get("fat_g_target") if targets else None

    oil_g = t.get("cooking_oil_g", 0.0)
    fiber_g = t.get("fiber", 0.0)
    sugar_g = t.get("sugar", 0.0)
    sodium_mg = t.get("sodium", 0.0)
    net_carb_g = t.get("net_carb", max(0.0, round(c_actual - fiber_g, 1)))
    exercise_cal = t.get("exercise_cal", 0.0)
    net_cal = t.get("net_cal", cal_actual)

    # 身体成分指标提取
    body = {}
    weight = None
    if day_data:
        for k in ("weight", "body_fat_pct", "waist_cm", "muscle_kg", "lbm_kg", "fat_mass_kg"):
            if k in day_data:
                body[k] = day_data[k]
        weight = day_data.get("weight")
    if weight is None and targets and "weight" in targets:
        weight = targets.get("weight")

    # 水分摄入与代谢负荷 (Hydration)
    water_ml = day_data.get("water_ml", 0) if day_data else 0
    target_water_ml = 2000
    if weight and weight > 0:
        target_water_ml = int(round(weight * 35.0 + (exercise_cal / 100.0) * 100.0))
    water_gap = max(0, target_water_ml - water_ml)

    # 肌肉蛋白合成单餐脉冲 (MPS Distribution & Leucine Threshold)
    meals = day_data.get("meals", []) if day_data else []
    threshold_g = max(20.0, round(weight * 0.35, 1)) if (weight and weight > 0) else 20.0
    pulses = []
    for idx, m in enumerate(meals):
        m_name = m.get("meal", f"第{idx+1}餐")
        m_prot = m.get("totals", {}).get("protein", 0.0)
        pulses.append({
            "meal": m_name,
            "protein_g": round(m_prot, 1),
            "reached_leucine_threshold": bool(m_prot >= threshold_g),
        })
    actual_pulses = sum(1 for p in pulses if p["reached_leucine_threshold"])

    # 训练周期化状态
    workout_detected = day_data.get("workout_detected", False) if day_data else False
    day_type = targets.get("day_type", "standard") if targets else ("workout" if workout_detected else "standard")

    return {
        "units": {
            "energy": "kcal",
            "protein": "g",
            "carb": "g",
            "net_carb": "g",
            "fat": "g",
            "fiber": "g",
            "sugar": "g",
            "sodium": "mg",
            "cooking_oil": "g",
            "exercise": "kcal",
            "net_energy": "kcal",
            "water": "ml",
            "body_fat_pct": "%",
            "waist_cm": "cm",
            "muscle_kg": "kg",
            "lbm_kg": "kg",
            "fat_mass_kg": "kg",
        },
        "energy": {
            "consumed_cal": cal_actual,
            "target_cal": cal_target,
            "remaining_cal": cal_rem,
            "delta_cal": cal_delta,
            "pct": round(cal_actual / cal_target * 100, 1) if (cal_target and cal_target > 0) else None,
            "exercise_cal": exercise_cal,
            "net_cal": net_cal,
            "safety_floor": targets.get("safety_floor") if targets else None,
        },
        "macros": {
            "protein_g": {
                "actual": p_actual,
                "target": p_target,
                "gap_g": p_gap,
                "pct": st.get("protein_pct"),
            },
            "carb_g": {
                "actual": c_actual,
                "target": c_target,
                "pct": st.get("carb_pct"),
                "net_carb_g": net_carb_g,
            },
            "fat_g": {
                "actual": f_actual,
                "target": f_target,
                "pct": st.get("fat_pct"),
            },
        },
        "mps": {
            "threshold_g": threshold_g,
            "actual_pulses": actual_pulses,
            "target_pulses": 3 if (targets and targets.get("protein_g_target", 0) >= 80) else 2,
            "distribution": pulses,
            "well_distributed": bool(actual_pulses >= 2) if len(meals) >= 2 else None,
        },
        "hydration": {
            "consumed_ml": water_ml,
            "target_ml": target_water_ml,
            "pct": round(water_ml / target_water_ml * 100, 1) if target_water_ml else 0.0,
            "gap_ml": water_gap,
            "status": "adequate" if water_ml >= target_water_ml else ("deficit" if water_ml < 1500 else "mild_deficit"),
        },
        "body": body,
        "periodization": {
            "day_type": day_type,
            "workout_detected": workout_detected,
        },
        "quality": {
            "fiber_g": fiber_g,
            "fiber_gap_g": round(max(0.0, 25.0 - fiber_g), 1),
            "cooking_oil_g": oil_g,
            "sugar_g": sugar_g,
            "excess_sugar": bool(sugar_g > 50.0),
            "sodium_mg": sodium_mg,
            "excess_sodium": bool(sodium_mg > 2000.0),
        }
    }


def evaluate_day(date_str, targets=None, phase=None, workout_day=None):
    """输出健康评估：达标情况、问题项、针对性建议、健康评分(100制)及量化遥测指标。
    支持双时态状态机 (Temporal Dual-Phase State Machine)：
    - 'pacing' (日内配额进度模式)：进餐中不作全天惩罚性扣分，评估当前餐次搭配并给出下一餐前瞻性建议。
    - 'auditing' (全天结转审计模式)：全天结算，基于 AHEI/DBI 五维指标进行量化评分并给出微置换建议。
    无档案目标(targets=None)时，仅给出基于摄入量/健康指标的通用建议。"""
    data = app.analyze_day(date_str, targets, workout_day=workout_day)
    t = data["totals"]
    st = t.get("status", {})
    suggestions = []
    issues = []

    today_str = datetime.now().strftime("%Y-%m-%d")
    is_today = (str(date_str) == today_str)
    cur_hour = datetime.now().hour
    meal_count = t.get("meal_count", 0)

    # 自动探测状态阶段
    if phase is None:
        if is_today and cur_hour < 20 and meal_count < 3:
            phase = "pacing"
        else:
            phase = "auditing"

    telemetry = build_telemetry(t, targets, st, day_data=data)

    if targets is None:
        suggestions.append("尚未设置饮食目标档案，无法进行热量/营养素达标评估。"
                           "可先执行 profile_init 记录性别、体重、身高、年龄、活动量与目标。")
        return {
            "date": str(date_str),
            "phase": phase,
            "score": 100,
            "issues": issues,
            "status": st,
            "telemetry": telemetry,
            "units": dict(calc.COMMON_UNITS),
            "suggestions": suggestions,
        }

    # ---------------- 模式 1：日内进餐中模式 (Pacing Mode) ----------------
    if phase == "pacing":
        score = 100
        rem_cal = round(targets["cal_target"] - t["cal"], 1)
        rem_protein = max(0.0, round(targets["protein_g_target"] - t["protein"], 1))

        # 仅对已实际发生且超标的行为预警与扣分，不扣除“尚未吃够”的假扣分
        if st.get("cal_over"):
            issues.append("热量已提前超标")
            suggestions.append(f"【热量超标预警】今日热量已达 {t['cal']:.0f} kcal，提前超出全天预算（超出 {abs(rem_cal):.0f} kcal），后续餐次请严格控制油脂主食，选择无油绿叶蔬菜。")
            score -= 25

        if t.get("sugar", 0) > 50:
            issues.append("糖摄入偏多")
            suggestions.append(f"【添加糖过量】今日累计游离糖已达 {t.get('sugar', 0):.1f}g（建议上限 50.0g），后续请避免含糖饮料、奶茶与甜点。")
            score -= 10

        if t.get("sodium", 0) > 2000:
            issues.append("钠摄入过多")
            suggestions.append(f"【钠摄入超标】今日累计钠已达 {t.get('sodium', 0):.0f} mg（参考上限 2000.0 mg），后续餐次注意减盐清淡，多喝水促进代谢。")
            score -= 10

        # 正向配额导航建议
        suggestions.insert(0, f"【日内进度】今日已摄入 {t['cal']:.0f} kcal / 目标 {targets['cal_target']} kcal"
                              f"（尚余 {rem_cal:.0f} kcal 预算，已完成 {round(t['cal'] / targets['cal_target'] * 100)}%）。")
        if rem_protein > 5:
            suggestions.append(f"【下餐配额提示】全天蛋白质尚差 {rem_protein:.0f}g 达标（已摄入 {t['protein']:.1f}g / 目标 {targets['protein_g_target']}g），下一餐建议优先安排掌心大小的瘦肉/鱼虾或蛋奶豆制品。")

        # 训练日/休息日周期化配额指引
        if targets.get("day_type") == "workout":
            suggestions.append(f"【训练日周期策略】今日为训练日(高碳日)：碳水目标设定为 {targets.get('carb_g_target')}g，热量赤字收窄，以充足糖原保障高强度输出。")
        elif targets.get("day_type") == "rest":
            suggestions.append(f"【休息日周期策略】今日为休息日(低碳日)：碳水目标调整为 {targets.get('carb_g_target')}g，配合适量健康脂肪，在保障恢复同时扩大减脂缺口。")

        # 练前/练后餐实时指引
        for m in data.get("meals", []):
            m_type = m.get("meal")
            m_tot = m.get("totals", {})
            if m_type == "练前餐":
                m_fat = m_tot.get("fat", 0.0)
                m_carb = m_tot.get("carb", 0.0)
                if m_fat > 15.0:
                    suggestions.append(f"【练前餐油脂偏高】练前餐含脂肪 {m_fat:.1f}g，过高油脂延缓胃排空易致腹胀，建议以快/中速复合碳水+低脂蛋白为主（油脂控制在 10g 内）。")
                elif m_carb < 15.0:
                    suggestions.append(f"【练前餐碳水提示】练前餐碳水仅 {m_carb:.1f}g，建议练前 1~2 小时补充 20~40g 复合碳水（如香蕉、燕麦、全麦面包）储备肌糖原。")
            elif m_type == "练后餐":
                m_prot = m_tot.get("protein", 0.0)
                if m_prot < 20.0:
                    suggestions.append(f"【练后窗口提醒】练后餐蛋白质仅 {m_prot:.1f}g（未达 20g 合成阈值），建议及时补充 20~35g 优质蛋白（如蛋白粉、即食鸡胸肉）启动肌肉修复。")

        # 水分日内进度提示
        hyd = telemetry.get("hydration", {})
        if hyd.get("gap_ml", 0) > 500:
            suggestions.append(f"【水分补给提醒】今日已记录饮水 {hyd['consumed_ml']} ml，距离目标 ({hyd['target_ml']} ml) 尚缺 {hyd['gap_ml']} ml。充足水分对高蛋白代谢和肌肉饱满度至关重要。")

        if t.get("exercise_cal"):
            suggestions.append(f"今日运动消耗 {t['exercise_cal']:.0f} 千卡，净摄入 {t['net_cal']:.0f} 千卡。")

        return {
            "date": str(date_str),
            "phase": "pacing",
            "score": max(score, 0),
            "grade": "Pacing",
            "issues": issues,
            "status": st,
            "telemetry": telemetry,
            "units": dict(calc.COMMON_UNITS),
            "suggestions": suggestions,
        }

    # ---------------- 模式 2：全天结转审计模式 (Auditing Mode) ----------------
    score = 100

    # 维度 1：能量平衡度 (25分)
    if st.get("cal_over"):
        issues.append("热量超标")
        diff = round(t["cal"] - targets["cal_target"], 1)
        suggestions.append(f"【热量超标】今日热量超标：实际摄入 {t['cal']:.0f} kcal，超出目标 ({targets['cal_target']} kcal) 达 {diff} kcal。下一餐可选择低卡高纤食物（如绿叶蔬菜、清汤），并将主食减半。")
        score -= 25
    elif st.get("cal_under"):
        issues.append("热量摄入不足")
        diff = round(targets["cal_target"] - t["cal"], 1)
        suggestions.append(f"【热量摄入不足】今日热量不足：实际摄入 {t['cal']:.0f} kcal，距离目标 ({targets['cal_target']} kcal) 尚缺 {diff} kcal（完成度 {round(t['cal'] / targets['cal_target'] * 100)}%）。建议补充优质蛋白和复合碳水，如鸡胸肉、全麦面包、牛奶。")
        score -= 10

    if "safety_floor" in targets and t.get("cal", 0) < targets["safety_floor"]:
        issues.append("低于生理安全热量底线")
        floor_gap = round(targets["safety_floor"] - t.get("cal", 0), 1)
        suggestions.append(f"【低于生理安全底线】今日热量摄入 ({t['cal']:.0f} kcal) 低于生理安全底线 ({targets['safety_floor']} kcal)，缺口达 {floor_gap} kcal。长期过低易引起代谢适应与肌肉流失，建议温和制造缺口。")
        score -= 10

    # 维度 2：蛋白质与宏量平衡 (25分)
    if "protein_pct" in st:
        if st["protein_pct"] < 60:
            issues.append("蛋白质偏低")
            p_gap = round(max(0.0, targets["protein_g_target"] - t["protein"]), 1)
            suggestions.append(f"【蛋白质偏低】蛋白质摄入不足：全天仅摄入 {t['protein']:.1f}g，达到目标 ({targets['protein_g_target']}g) 的 {st['protein_pct']}%（缺口 {p_gap}g）。可增加蛋、奶、鸡胸肉、鱼虾或豆制品。")
            score -= 15

    if "carb_pct" in st and st["carb_pct"] > 130:
        issues.append("碳水偏高")
        suggestions.append(f"【碳水偏高】碳水化合物偏高：全天摄入 {t['carb']:.1f}g，达到目标 ({targets['carb_g_target']}g) 的 {st['carb_pct']}%。减少精制主食与含糖饮品，增加粗粮比例。")
        score -= 10

    if "fat_pct" in st and st["fat_pct"] > 130:
        issues.append("脂肪偏高")
        suggestions.append(f"【脂肪偏高】脂肪摄入偏高：全天摄入 {t['fat']:.1f}g，达到目标 ({targets['fat_g_target']}g) 的 {st['fat_pct']}%。减少油炸、重油烹饪和肥肉，多用蒸煮代替。")
        score -= 10

    # 维度 3：控糖减盐 (20分)
    if t.get("sugar", 0) > 50:
        issues.append("糖摄入偏多")
        suggestions.append(f"【添加糖偏多】今日统计总糖偏多：累计摄入 {t['sugar']:.1f}g（参考上限 50.0g）。若主要来自整果与纯奶可放宽关注，但需重点留意含糖饮料、奶茶与加工甜点中的游离糖。")
        score -= 5

    if t.get("sodium", 0) > 2000:
        issues.append("钠摄入过多")
        suggestions.append(f"【钠摄入过多】钠摄入过高：全天钠摄入 {t['sodium']:.0f} mg，超过 2000.0 mg/日健康上限。减少腌制食品、外卖重盐调料，多喝水促进代谢。")
        score -= 10

    # 维度 4：膳食纤维 (15分)
    if t.get("fiber", 0) < 15:
        issues.append("膳食纤维不足")
        f_gap = round(max(0.0, 25.0 - t["fiber"]), 1)
        suggestions.append(f"【膳食纤维不足】膳食纤维不足：全天仅摄入 {t['fiber']:.1f}g（低于 15.0g 临界线，距 25.0g 目标尚差 {f_gap}g）。可补充燕麦、豆类、绿叶菜与水果。")
        score -= 5

    # 维度 5：净热量与运动联动
    if t.get("exercise_cal"):
        suggestions.append(f"今日运动消耗 {t['exercise_cal']:.0f} 千卡，净摄入 {t['net_cal']:.0f} 千卡。")

    # 维度 6：增肌减脂进阶维度（周期化、蛋白单餐脉冲、练前练后时机、高蛋白水分补给）
    if targets.get("day_type") == "workout":
        suggestions.append(f"【训练日周期复盘】训练日高碳执行中（碳水完成度 {st.get('carb_pct', 0)}%），糖原回填充分，支持高强度肌肥大训练与修复。")
    elif targets.get("day_type") == "rest":
        suggestions.append(f"【休息日周期复盘】休息日低碳控热执行平稳（碳水 {t['carb']:.1f}g / 目标 {targets['carb_g_target']}g），有效维持燃脂节奏。")

    # 蛋白质单餐脉冲 (MPS Distribution)
    mps = telemetry.get("mps", {})
    if t.get("protein", 0) >= 60.0 and mps.get("actual_pulses", 0) < 2 and len(data.get("meals", [])) >= 2:
        issues.append("蛋白质摄入过于集中")
        suggestions.append(f"【蛋白质单餐脉冲】全天蛋白质虽达 {t['protein']:.1f}g，但单餐达到有效亮氨酸阈值(≥{mps['threshold_g']}g)的餐次仅 {mps['actual_pulses']} 次。单次暴饮暴食蛋白质吸收率受限，建议分散至 3~4 餐中均匀刺激肌肉合成(MPS)。")

    # 练前练后餐质检
    for m in data.get("meals", []):
        m_type = m.get("meal")
        m_tot = m.get("totals", {})
        if m_type == "练前餐":
            m_fat = m_tot.get("fat", 0.0)
            if m_fat > 15.0:
                issues.append("练前餐油脂偏高")
                suggestions.append(f"【练前餐油脂偏高】练前餐脂肪达 {m_fat:.1f}g，过高油脂延缓胃排空易致腹胀，建议练前以低脂复合碳水为主（脂肪控制在 10g 内）。")
        elif m_type == "练后餐":
            m_prot = m_tot.get("protein", 0.0)
            if m_prot < 20.0:
                issues.append("练后蛋白质不足")
                suggestions.append(f"【练后合成窗口】练后餐蛋白质仅 {m_prot:.1f}g（低于 20g 阈值），未能最大化利用训练后的肌肉蛋白合成黄金窗口，建议备好蛋白粉或即食鸡胸肉。")

    # 高蛋白高负荷水分审计
    hyd = telemetry.get("hydration", {})
    if t.get("protein", 0) >= 80.0 and hyd.get("consumed_ml", 0) < 1500:
        issues.append("高蛋白饮食饮水不足")
        suggestions.append(f"【高蛋白补水预警】全天高蛋白摄入 ({t['protein']:.1f}g) 显著增加肾脏溶质负荷与尿素代谢，但今日饮水仅 {hyd['consumed_ml']} ml（建议 ≥ {hyd['target_ml']} ml）。请明日增加补水以保护代谢与肌肉水合。")
        score -= 5

    if not suggestions:
        suggestions.append(f"今日热量摄入 {t['cal']:.0f} kcal 结构良好，三大营养素配比均衡，请继续保持！")

    final_score = max(score, 0)
    grade = "S" if final_score >= 90 else ("A" if final_score >= 80 else ("B" if final_score >= 70 else ("C" if final_score >= 60 else "D")))

    return {
        "date": str(date_str),
        "phase": "auditing",
        "grade": grade,
        "score": final_score,
        "issues": issues,
        "status": st,
        "telemetry": telemetry,
        "units": dict(calc.COMMON_UNITS),
        "suggestions": suggestions,
    }


def main():
    args = sys.argv[1:]
    date_str = datetime.now().strftime("%Y-%m-%d")
    workout_day = None
    for arg in args:
        if arg == "--workout":
            workout_day = True
        elif arg == "--rest":
            workout_day = False
        elif not arg.startswith("--"):
            date_str = arg
    profile = app.load_settings().get("profile")
    targets = goals.daily_targets(*profile, workout_day=workout_day) if profile else None
    print(json.dumps(evaluate_day(date_str, targets, workout_day=workout_day), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        sys.exit(2)