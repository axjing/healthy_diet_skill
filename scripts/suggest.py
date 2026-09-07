# -*- coding: utf-8 -*-
"""健康评估与建议：根据单日摄入汇总和营养目标给出调优建议。"""
import json

import app
import goals


def evaluate_day(date_str, targets=None):
    """输出健康评估：达标情况、问题项、针对性建议、健康评分(100制)。"""
    if targets is None:
        targets = goals.daily_targets("男", 70, 175, 30, "轻度", "维持")
    data = app.analyze_day(date_str, targets)
    t = data["totals"]
    st = t.get("status", {})
    suggestions = []
    score = 100
    issues = []

    # 热量
    if st.get("cal_over"):
        issues.append("热量超标")
        suggestions.append("今日热量超标，下一餐可选择低卡高纤食物，如绿叶蔬菜、清汤，并将主食减半。")
        score -= 25
    elif st.get("cal_under"):
        issues.append("热量摄入不足")
        suggestions.append("今日热量不足，建议补充优质蛋白和复合碳水，如鸡胸肉、全麦面包、牛奶。")
        score -= 10

    # 蛋白质
    if "protein_pct" in st:
        if st["protein_pct"] < 60:
            issues.append("蛋白质偏低")
            suggestions.append("蛋白质摄入不足，可增加蛋、奶、鸡胸肉、鱼虾或豆制品。")
            score -= 15

    # 碳水
    if "carb_pct" in st and st["carb_pct"] > 130:
        issues.append("碳水偏高")
        suggestions.append("碳水化合物偏高，减少精制主食与含糖饮品，增加粗粮比例。")
        score -= 10

    # 脂肪
    if "fat_pct" in st and st["fat_pct"] > 130:
        issues.append("脂肪偏高")
        suggestions.append("脂肪摄入偏高，减少油炸、重油烹饪和肥肉，多用蒸煮代替。")
        score -= 10

    # 添加糖（每日 <25g，WHO 建议）
    if t.get("sugar", 0) > 25:
        issues.append("添加糖偏多")
        suggestions.append("添加糖摄入超过25g/日建议上限，减少奶茶、甜饮料与甜点。")
        score -= 10

    # 钠（每日 <2000mg 参考）
    if t.get("sodium", 0) > 2000:
        issues.append("钠摄入过多")
        suggestions.append("钠摄入过高，减少腌制食品、外卖、调味品用量，多喝水。")
        score -= 10

    # 膳食纤维（每日 25-30g 参考）
    if t.get("fiber", 0) < 15:
        suggestions.append("膳食纤维不足，可补充燕麦、豆类、绿叶菜与水果。")
        score -= 5

    # 净热量
    if t.get("exercise_cal"):
        suggestions.append(f"今日运动消耗 {t['exercise_cal']:.0f} 千卡，净摄入 {t['net_cal']:.0f} 千卡。")

    if not suggestions:
        suggestions.append("今日饮食结构良好，请继续保持均衡搭配。")

    return {
        "date": str(date_str),
        "score": max(score, 0),
        "issues": issues,
        "status": st,
        "suggestions": suggestions,
    }


def main():
    import sys
    date_str = sys.argv[1] if len(sys.argv) > 1 else "2026-09-07"
    profile = app.load_settings().get("profile")
    targets = goals.daily_targets(*profile) if profile else None
    print(json.dumps(evaluate_day(date_str, targets), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()