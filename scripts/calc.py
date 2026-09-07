# -*- coding: utf-8 -*-
"""饮食热量计算核心引擎。
用法示例见 main()。
解析自然语言饮食描述 -> 匹配食物库 -> 单位换算 -> 烹饪修正 -> 输出营养核算。
"""
import json
import os
import re
import sys
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOODS_PATH = os.path.join(SKILL_DIR, "data", "foods.json")
UNITS_PATH = os.path.join(SKILL_DIR, "data", "units.json")

MACROS = ["cal", "protein", "carb", "fat", "fiber", "sugar", "sodium"]


def load_data():
    with open(FOODS_PATH, encoding="utf-8") as f:
        food_cfg = json.load(f)
    with open(UNITS_PATH, encoding="utf-8") as f:
        unit_cfg = json.load(f)
    return food_cfg["foods"], unit_cfg["units"], unit_cfg["cooking"]


def build_index(foods):
    """建立 名称/别名 -> 食物 的索引，用于模糊匹配。"""
    index = {}
    for f in foods:
        keys = [f["name"]] + f.get("aliases", []) + f.get("alias", []) if isinstance(f.get("alias"), list) else [f["name"]] + f.get("aliases", []) + ([f["alias"]] if f.get("alias") else [])
        for k in keys:
            index[k.lower()] = f
    return index


def find_food(query, index):
    """在食物库中查找最匹配的食物。返回 (食物, 匹配方式)。"""
    q = query.lower().strip()
    if not q:
        return None, None
    if q in index:
        return index[q], "精确"
    # 子串匹配：查询包含食物名校 或 食物名包含查询
    candidates = []
    for k, f in index.items():
        if k in q:
            candidates.append((len(k), f))
    if candidates:
        # 取最长匹配
        candidates.sort(key=lambda x: -x[0])
        return candidates[0][1], "包含"
    return None, None


_UNIT_ORDER = ["小碗", "大碗", "毫升", "汤匙", "茶匙", "公升", "升", "斤", "两", "克", "公斤", "碗", "碟", "盘", "份", "人份", "勺", "杯", "个", "根", "块", "只", "片", "条", "串", "粒", "颗", "把", "朵", "段", "个(大)", "个(小)", "根(小)", "小根", "小份", "中份", "小个", "中等", "克(生)", "g", "G", "kg", "KG", "L", "ml", "ML"]


def parse_amount(text):
    """从描述中解析'数量+单位'，例如 '2个鸡蛋'、'1碗米饭'、'150克鸡胸肉'。
    单位必须是已知单位表中的项，避免把食物名误吞进单位。"""
    text = text.strip()
    m = re.match(r"^([\d.]+)\s*(\S*)", text)
    if not m:
        return 1, None, text
    amount = float(m.group(1))
    raw_unit = m.group(2)
    # 在已知单位表中查找前缀最长匹配
    best = None
    for unit in sorted(_UNIT_ORDER, key=len, reverse=True):
        if raw_unit.startswith(unit):
            best = unit
            break
    if best:
        # 计算 rest：文本中位于该单位之后的部分
        idx = text.find(best, len(m.group(1)))
        rest = text[idx + len(best):].strip()
        return amount, best, rest
    # 没有已知单位，视为数量后直接跟食物名（如 '2鸡蛋'）
    return amount, None, raw_unit + text[m.end():].strip()


def resolve_grams(amount, unit, food, units):
    """将(数量,单位)换算为克数。若单位在食物serving表或通用单位表，返回克数；否则None。"""
    if unit is None:
        # 无单位，默认按1份serving（若食物有serving取最常见的）
        serving = food.get("serving") or {}
        if serving:
            g = sum(list(serving.values())) / len(serving)
            return g * amount
        return amount * 100
    # 尝试食物专属serving
    serving = food.get("serving") or {}
    if unit in serving:
        return serving[unit] * amount
    # 尝试通用单位
    if unit in units:
        return units[unit] * amount
    # 未知单位，回退到克
    try:
        return float(unit) if False else None
    except Exception:
        return None


def compute_item(description, foods, units, cooking, index=None):
    """计算单条饮食记录。description 形如 '2个鸡蛋(煎)' 或 '150克鸡胸肉'。"""
    index = index or build_index(foods)
    text = description.strip()
    # 提取烹饪方式
    cook = None
    cm = re.search(r"[（(]([^）)]*)[）)]|(煎|炸|烤|蒸|煮|红烧|糖醋|清炒|爆炒|干煸|凉拌|油焖|白灼|烧烤|烟熏|麻辣|炖)", text)
    if cm:
        grp = cm.group(1) if cm.group(1) else cm.group(2)
        cook = grp if grp in cooking else None

    # 去掉烹饪注释后再去匹配食物
    clean = re.sub(r"[（(][^）)]*[）)]", "", text)
    # 解析数量
    amount, unit, food_query = parse_amount(clean)
    food, match = find_food(food_query, index)
    if not food:
        return {"ok": False, "error": f"未找到食物: {food_query}", "input": description}

    grams = resolve_grams(amount, unit, food, units)
    if grams is None:
        return {"ok": False, "error": f"无法换算单位: {unit}", "input": description}

    # 烹饪修正
    factor = cooking.get(cook, 1.0) if cook else 1.0
    w = grams / 100.0
    item = {
        "ok": True,
        "food": food["name"],
        "matched": match,
        "amount": amount,
        "unit": unit or "份",
        "grams": grams,
        "cooking": cook,
        "cooking_factor": factor,
        "values": {m: round(info_per_100 * w * factor, 1) for m, info_per_100 in food.items() if m in MACROS},
    }
    item["values"].pop("cal")
    item["values"]["cal"] = round(food["cal"] * w * factor, 0)
    return item


def parse_meal(text, foods, units, cooking, index=None):
    """解析一餐多种食物，用逗号/分号/顿号/换行分隔。"""
    index = index or build_index(foods)
    items = []
    for part in re.split(r"[,，;；、\n]+", text):
        part = part.strip()
        if not part:
            continue
        r = compute_item(part, foods, units, cooking, index)
        if r.get("ok"):
            items.append(r)
    # 汇总
    totals = {m: 0.0 for m in MACROS}
    for it in items:
        for m in MACROS:
            totals[m] += it["values"].get(m, 0)
    totals = {m: round(v, 1) for m, v in totals.items()}
    return {"items": items, "totals": totals}


def meal_classify(hour):
    if 5 <= hour < 10:
        return "早餐"
    if 10 <= hour < 14:
        return "午餐"
    if 14 <= hour < 17:
        return "加餐"
    if 17 <= hour < 22:
        return "晚餐"
    return "加餐"


def main():
    if len(sys.argv) >= 2:
        text = " ".join(sys.argv[1:])
    else:
        text = "1碗米饭,150克鸡胸肉(煎),1个鸡蛋,清炒西兰花"
    foods, units, cooking = load_data()
    index = build_index(foods)
    res = parse_meal(text, foods, units, cooking, index)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
