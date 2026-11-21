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
    from . import app, goals
except (ImportError, ValueError):
    import app
    import goals

# Windows 控制台默认 gbk，设为 utf-8 以避免中文输出乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def build_telemetry(t, targets, st):
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
    exercise_cal = t.get("exercise_cal", 0.0)
    net_cal = t.get("net_cal", cal_actual)

    return {
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
            },
            "fat_g": {
                "actual": f_actual,
                "target": f_target,
                "pct": st.get("fat_pct"),
            },
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


def evaluate_day(date_str, targets=None, phase=None):
    """输出健康评估：达标情况、问题项、针对性建议、健康评分(100制)及量化遥测指标。
    支持双时态状态机 (Temporal Dual-Phase State Machine)：
    - 'pacing' (日内配额进度模式)：进餐中不作全天惩罚性扣分，评估当前餐次搭配并给出下一餐前瞻性建议。
    - 'auditing' (全天结转审计模式)：全天结算，基于 AHEI/DBI 五维指标进行量化评分并给出微置换建议。
    无档案目标(targets=None)时，仅给出基于摄入量/健康指标的通用建议。"""
    data = app.analyze_day(date_str, targets)
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

    telemetry = build_telemetry(t, targets, st)

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
            suggestions.append(f"今日热量已达 {t['cal']:.0f} kcal，提前超出全天预算，后续餐次请严格控制油脂主食，选择无油绿叶蔬菜。")
            score -= 25

        if t.get("sugar", 0) > 50:
            issues.append("糖摄入偏多")
            suggestions.append("今日统计游离糖分已偏多，后续请避免含糖饮料、奶茶与甜点。")
            score -= 10

        if t.get("sodium", 0) > 2000:
            issues.append("钠摄入过多")
            suggestions.append("今日累计钠已超 2000mg，后续餐次注意减盐清淡，多喝水促进代谢。")
            score -= 10

        # 正向配额导航建议
        suggestions.insert(0, f"【日内进度】今日已摄入 {t['cal']:.0f} kcal / 目标 {targets['cal_target']} kcal"
                              f"（尚余 {rem_cal:.0f} kcal 预算，已完成 {round(t['cal'] / targets['cal_target'] * 100)}%）。")
        if rem_protein > 5:
            suggestions.append(f"【下餐配额提示】全天蛋白质尚差 {rem_protein:.0f}g 达标，下一餐建议优先安排掌心大小的瘦肉/鱼虾或蛋奶豆制品。")

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
            "suggestions": suggestions,
        }

    # ---------------- 模式 2：全天结转审计模式 (Auditing Mode) ----------------
    score = 100

    # 维度 1：能量平衡度 (25分)
    if st.get("cal_over"):
        issues.append("热量超标")
        suggestions.append("今日热量超标，下一餐可选择低卡高纤食物，如绿叶蔬菜、清汤，并将主食减半。")
        score -= 25
    elif st.get("cal_under"):
        issues.append("热量摄入不足")
        suggestions.append("今日热量不足，建议补充优质蛋白和复合碳水，如鸡胸肉、全麦面包、牛奶。")
        score -= 10

    if "safety_floor" in targets and t.get("cal", 0) < targets["safety_floor"]:
        issues.append("低于生理安全热量底线")
        suggestions.append(f"今日热量摄入低于生理安全底线 ({targets['safety_floor']} kcal)，长期过低易引起代谢适应与肌肉流失，建议温和制造缺口。")
        score -= 10

    # 维度 2：蛋白质与宏量平衡 (25分)
    if "protein_pct" in st:
        if st["protein_pct"] < 60:
            issues.append("蛋白质偏低")
            suggestions.append("蛋白质摄入不足，可增加蛋、奶、鸡胸肉、鱼虾或豆制品。")
            score -= 15

    if "carb_pct" in st and st["carb_pct"] > 130:
        issues.append("碳水偏高")
        suggestions.append("碳水化合物偏高，减少精制主食与含糖饮品，增加粗粮比例。")
        score -= 10

    if "fat_pct" in st and st["fat_pct"] > 130:
        issues.append("脂肪偏高")
        suggestions.append("脂肪摄入偏高，减少油炸、重油烹饪和肥肉，多用蒸煮代替。")
        score -= 10

    # 维度 3：控糖减盐 (20分)
    if t.get("sugar", 0) > 50:
        issues.append("糖摄入偏多")
        suggestions.append("今日统计总糖偏多（含天然糖分）。若主要来自整果与纯奶可放宽关注，但需重点留意含糖饮料、奶茶与加工甜点中的游离糖。")
        score -= 5

    if t.get("sodium", 0) > 2000:
        issues.append("钠摄入过多")
        suggestions.append("钠摄入过高，减少腌制食品、外卖、调味品用量，多喝水。")
        score -= 10

    # 维度 4：膳食纤维 (15分)
    if t.get("fiber", 0) < 15:
        issues.append("膳食纤维不足")
        suggestions.append("膳食纤维不足，可补充燕麦、豆类、绿叶菜与水果。")
        score -= 5

    # 维度 5：净热量与运动联动
    if t.get("exercise_cal"):
        suggestions.append(f"今日运动消耗 {t['exercise_cal']:.0f} 千卡，净摄入 {t['net_cal']:.0f} 千卡。")

    if not suggestions:
        suggestions.append("今日饮食结构良好，请继续保持均衡搭配。")

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
        "suggestions": suggestions,
    }


def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    profile = app.load_settings().get("profile")
    targets = goals.daily_targets(*profile) if profile else None
    print(json.dumps(evaluate_day(date_str, targets), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        sys.exit(2)