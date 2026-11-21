# -*- coding: utf-8 -*-
"""饮食热量计算核心引擎。
用法示例见 main()。
解析自然语言饮食描述 -> 匹配食物库 -> 单位换算 -> 烹饪修正 -> 输出营养核算。
"""
import json
import os
import re
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("HEALTHY_DIET_DATA_DIR", os.path.join(SKILL_DIR, "data"))
FOODS_PATH = os.path.join(DATA_DIR, "foods.json") if os.path.exists(os.path.join(DATA_DIR, "foods.json")) else os.path.join(SKILL_DIR, "data", "foods.json")
UNITS_PATH = os.path.join(DATA_DIR, "units.json") if os.path.exists(os.path.join(DATA_DIR, "units.json")) else os.path.join(SKILL_DIR, "data", "units.json")

# Windows 控制台默认 gbk，设为 utf-8 以避免中文输出乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

MACROS = ["cal", "protein", "carb", "fat", "fiber", "sugar", "sodium"]

NUTRIENT_UNITS = {
    "cal": "kcal",
    "protein": "g",
    "carb": "g",
    "net_carb": "g",
    "fat": "g",
    "fiber": "g",
    "sugar": "g",
    "sodium": "mg",
}

COMMON_UNITS = {
    **NUTRIENT_UNITS,
    "grams": "g",
    "weight": "kg",
    "body_fat_pct": "%",
    "waist_cm": "cm",
    "muscle_kg": "kg",
    "lbm_kg": "kg",
    "fat_mass_kg": "kg",
    "water_ml": "ml",
    "water": "ml",
    "exercise_cal": "kcal",
    "net_cal": "kcal",
    "duration": "min",
}


def format_nutrient_summary(totals):
    """格式化营养数值为带清晰单位的中文摘要，兼顾普通人群与健身控碳人群。"""
    cal = totals.get("cal", 0.0)
    p = totals.get("protein", 0.0)
    f = totals.get("fat", 0.0)
    c = totals.get("carb", 0.0)
    fib = totals.get("fiber", 0.0)
    s = totals.get("sodium", 0.0)
    net_c = round(max(0.0, c - fib), 1)
    carb_str = f"碳水 {c:.1f}g(净碳 {net_c:.1f}g)" if fib > 0 else f"碳水 {c:.1f}g"
    return f"热量 {cal:.1f} kcal | 蛋白质 {p:.1f}g | 脂肪 {f:.1f}g | {carb_str} | 钠 {s:.1f}mg"

DEFAULT_UNITS = [
    "小碗", "大碗", "毫升", "汤匙", "茶匙", "公升", "升", "斤", "两", "克", "公斤",
    "碗", "碟", "盘", "份", "人份", "小份", "中份", "大份", "勺", "杯", "瓶", "罐",
    "听", "盒", "小盒", "袋", "包", "桶", "盅", "个", "根", "块", "只", "片", "条",
    "串", "粒", "颗", "把", "朵", "段", "支", "个(大)", "个(小)", "根(小)", "小根",
    "小个", "中等", "克(生)", "g", "G", "kg", "KG", "L", "ml", "ML"
]

_UNIT_ORDER = list(DEFAULT_UNITS)
_UNIT_ALT = "|".join(re.escape(u) for u in sorted(set(_UNIT_ORDER), key=len, reverse=True))
_TRAILING_AMOUNT_RE = re.compile(r"([\d.]+)\s*(" + _UNIT_ALT + r")\s*$")

# 中文数字（含口语"两"和"半"），用于 "二两米饭"、"半碗粥" 这类描述
_CN_NUM = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "半": 0.5}
_CN_NUM_CLASS = "一二两三四五六七八九十半"


def refresh_units(units_dict=None, foods_list=None):
    """根据 units 配置及所有食物自定义 serving 动态更新单位索引与正则匹配式。"""
    global _UNIT_ORDER, _UNIT_ALT, _TRAILING_AMOUNT_RE
    all_units = set(DEFAULT_UNITS)
    if units_dict:
        all_units.update(units_dict.keys())
    if foods_list:
        for f in foods_list:
            if "serving" in f and isinstance(f["serving"], dict):
                all_units.update(f["serving"].keys())
    _UNIT_ORDER = sorted(all_units, key=len, reverse=True)
    _UNIT_ALT = "|".join(re.escape(u) for u in _UNIT_ORDER)
    _TRAILING_AMOUNT_RE = re.compile(r"([\d.]+)\s*(" + _UNIT_ALT + r")\s*$")


def load_data():
    with open(FOODS_PATH, encoding="utf-8") as f:
        food_cfg = json.load(f)
    with open(UNITS_PATH, encoding="utf-8") as f:
        unit_cfg = json.load(f)
    refresh_units(unit_cfg.get("units"), food_cfg.get("foods"))
    return food_cfg["foods"], unit_cfg["units"], unit_cfg["cooking"]


def build_index(foods):
    """建立 名称/别名 -> 食物 的索引，用于模糊匹配。"""
    index = {}
    for f in foods:
        keys = [f["name"]] + f.get("aliases", []) + f.get("alias", []) if isinstance(f.get("alias"), list) else [f["name"]] + f.get("aliases", []) + ([f["alias"]] if f.get("alias") else [])
        for k in keys:
            index[k.lower()] = f
    return index


def _is_subsequence(sub, s):
    """判断字符串 sub 的字符是否按顺序出现在 s 中（支持模糊插入匹配）。"""
    it = iter(s)
    return all(c in it for c in sub)


def find_food(query, index):
    """在食物库中查找最匹配的食物。返回 (食物, 匹配方式, 其他候选食物名列表)。"""
    q = query.lower().strip()
    if not q:
        return None, None, []
    if q in index:
        return index[q], "精确", []

    candidates = []
    for k, f in index.items():
        if len(k) < 2:
            continue
        # 1. 完全包含子串：k in q (如 '米饭' in '1碗白米饭')
        if k in q:
            score = len(k) / len(q)
            # 成品菜肴/快餐权重加成，避免被食材基础词冲垮
            if f.get("category") in _PREPARED_CATEGORIES:
                score += 0.35
            candidates.append((score, len(k), f, "包含"))
        # 2. 简略/插入式子序列匹配：k 是 q 的子序列 (如 '西红柿炒蛋' in '西红柿炒鸡蛋')
        elif len(k) >= 3 and _is_subsequence(k, q):
            score = (len(k) / len(q)) + 0.25
            if f.get("category") in _PREPARED_CATEGORIES:
                score += 0.35
            candidates.append((score, len(k), f, "相似"))
        # 3. 反向包含：q in k (如 '拿铁' in '拿铁咖啡', '鸡肉' in '鸡胸肉')
        elif len(q) >= 2 and q in k:
            score = (len(q) / len(k)) * 0.85
            candidates.append((score, len(q), f, "前缀/后缀"))
        # 4. 反向子序列匹配：q 是 k 的子序列 (如 '鸡肉' 在 '鸡胸肉')
        elif len(q) >= 2 and _is_subsequence(q, k):
            score = (len(q) / len(k)) * 0.75
            candidates.append((score, len(q), f, "子序列"))

    if candidates:
        candidates.sort(key=lambda x: (-x[0], -x[1]))
        top = candidates[0][2]
        match_type = candidates[0][3]
        alts = []
        seen = {top["name"]}
        for _, _, f, _ in candidates[1:]:
            if f["name"] not in seen:
                seen.add(f["name"])
                alts.append(f["name"])
        return top, match_type, alts[:3]
    return None, None, []


def _cn_to_num(s):
    """简单中文数字转数值：支持 半/单字连写/十/XX十/十X。无法解析返回 None。"""
    if s == "半":
        return 0.5
    if "十" in s:
        parts = s.split("十")
        if len(parts) != 2:
            return None
        tens = _CN_NUM.get(parts[0], 1) if parts[0] else 1
        ones = _CN_NUM.get(parts[1], 0) if parts[1] else 0
        return tens * 10 + ones
    total = 0
    for ch in s:
        if ch not in _CN_NUM:
            return None
        total = total * 10 + _CN_NUM[ch]
    return total


def parse_amount(text):
    """从描述中解析'数量+单位'，例如 '2个鸡蛋'、'1碗米饭'、'150克鸡胸肉'。
    同时支持：
    - 数量后置（'米饭150克'、'鸡蛋2个'）
    - 中文数字（'二两米饭'、'半碗粥'、'两听可乐'）
    - 复合口语数量词（'一碗半米饭'、'两个半苹果'、'1斤半牛肉'）
    - 特殊分数单位（'大半碗'、'小半碗'、'半碗'）
    - 模糊修饰词前缀自动剥离（'约200克三文鱼'、'大概1碗饭'、'少许坚果'）
    单位必须是已知单位表中的项，避免把食物名误吞进单位。"""
    text = text.strip()
    if text.startswith("-"):
        # 负数：返回 0 交由 compute_item 按"数量应大于0"拒绝
        return 0, None, text

    # 1. 剥离前缀口语模糊修饰词（约、大约、大概、差不多、估计）
    text = re.sub(r"^(约|大约|大概|差不多|估计)\s*", "", text).strip()

    # 2. 口语特殊极小量词（少许、适量、一小撮）
    if re.match(r"^(少许|适量)\s*", text):
        rest = re.sub(r"^(少许|适量)\s*", "", text).strip()
        return 0.3, "份", rest
    if re.match(r"^(一小撮|一撮)\s*", text):
        rest = re.sub(r"^(一小撮|一撮)\s*", "", text).strip()
        return 0.2, "份", rest

    # 3. 特殊分数单位前缀（大半碗、小半碗、半碗、大半个）
    m_fraction = re.match(r"^(大半|小半|半)\s*(" + _UNIT_ALT + r")", text)
    if m_fraction:
        frac_word = m_fraction.group(1)
        unit = m_fraction.group(2)
        rest = text[m_fraction.end():].strip()
        frac_val = 0.75 if frac_word == "大半" else (0.3 if frac_word == "小半" else 0.5)
        return frac_val, unit, rest

    # 4. 复合中文/数字“X单位半”模式（如 '一碗半米饭'、'两个半苹果'、'1斤半牛肉'、'1个半鸡蛋'）
    m_half = re.match(r"^([\d.]+|[" + _CN_NUM_CLASS + r"]+)\s*(" + _UNIT_ALT + r")半", text)
    if m_half:
        num_str = m_half.group(1)
        base_n = _cn_to_num(num_str) if any(c in _CN_NUM_CLASS for c in num_str) else None
        if base_n is None:
            try:
                base_n = float(num_str)
            except ValueError:
                base_n = None
        if base_n is not None:
            unit = m_half.group(2)
            rest = text[m_half.end():].strip()
            return base_n + 0.5, unit, rest

    # 5. 中文数字开头且紧邻已知单位才转换（避免误伤 '四季豆' 等以数字字开头的食物名）
    m_cn = re.match(r"^([" + _CN_NUM_CLASS + r"]+)(" + _UNIT_ALT + r")", text)
    if m_cn:
        n = _cn_to_num(m_cn.group(1))
        if n is not None:
            text = str(n) + text[m_cn.end(1):]

    # 6. 标准阿拉伯数字开头（如 '150克鸡胸肉'、'2个鸡蛋'、'1.5碗米饭'）
    m = re.match(r"^([\d.]+)\s*(\S*)", text)
    if not m:
        # 数量后置：从文本尾部提取 数字+单位（如 '米饭150克'）
        m2 = _TRAILING_AMOUNT_RE.search(text)
        if m2:
            rest = text[:m2.start()].strip()
            if rest and re.search(r"[\u4e00-\u9fffA-Za-z]", rest):
                try:
                    return float(m2.group(1)), m2.group(2), rest
                except ValueError:
                    return 0, None, text
        return 1, None, text
    try:
        amount = float(m.group(1))
    except ValueError:
        return 0, None, text
    raw_unit = m.group(2)
    # 在已知单位表中查找前缀最长匹配
    best = None
    for unit in _UNIT_ORDER:
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


def _preferred_serving_grams(serving):
    """无单位时选食物最常见一份量：优先计数单位(个/块/片…)，其次 份/碗/杯，最后取第一项。
    不再把不同单位类型（碗/两/个…）的克数取平均——那没有物理意义。"""
    if not serving:
        return None
    preferred = _PIECE_UNITS | {"杯", "碗", "份"}
    for k, v in serving.items():
        if k in preferred:
            return float(v)
    return float(next(iter(serving.values())))


def resolve_grams(amount, unit, food, units):
    """将(数量,单位)换算为克数。若单位在食物serving表或通用单位表，返回克数；否则None。"""
    if unit is None:
        # 无单位：按食物最常见的一份量估算
        g = _preferred_serving_grams(food.get("serving") or {})
        return (g if g is not None else 100.0) * amount
    # 尝试食物专属serving
    serving = food.get("serving") or {}
    if unit in serving:
        return serving[unit] * amount
    # 尝试通用单位
    if unit in units:
        return units[unit] * amount
    # 识别到的计数单位（个/根/块/只/片/颗/粒等）若未在serving中给出：
    # 仅对 serving 中同为计数单位的项取平均；没有则退回 100g 默认
    if unit in _PIECE_UNITS:
        piece_vals = [float(v) for k, v in serving.items() if k in _PIECE_UNITS]
        if piece_vals:
            return (sum(piece_vals) / len(piece_vals)) * amount
        return 100.0 * amount
    # 未知且无法换算的单位
    return None


# 这些分类的食物已是成品/半成品/补剂（营养值已含处理或冲饮），不再应用烹饪系数加成
_PREPARED_CATEGORIES = {"菜肴", "综合/快餐", "零食甜品", "饮品", "调味", "油脂", "运动补剂"}

# 计数类单位（单个/根/块…），食物 serving 未给出时按食物平均单份重估算
_PIECE_UNITS = {"个", "颗", "粒", "根", "块", "只", "片", "条", "串", "朵", "段", "把", "个(大)", "个(小)", "根(小)"}


# 否定前缀，用于识别用户描述中'不吃/不要'的项，避免计入热量
_NEGATION_PREFIXES = ("不要", "不吃", "别放", "无", "免", "不加", "不喝", "去")


def compute_item(description, foods, units, cooking, index=None):
    """计算单条饮食记录。
    description 可为自然语言字符串（如 '2个鸡蛋(煎)' 或 '150克鸡胸肉'），
    或结构化字典（如 {'food': '鸡胸肉', 'amount': 150, 'unit': '克', 'cooking': '煎'}）。
    """
    refresh_units(units, foods)
    index = index or build_index(foods)

    if isinstance(description, dict):
        food_query = str(description.get("food") or description.get("name") or "").strip()
        try:
            amount = float(description.get("amount", 1.0))
        except (ValueError, TypeError):
            amount = 1.0
        unit = description.get("unit") or "份"
        cook = description.get("cooking")
        if cook and cook not in cooking:
            cook = None
        if amount <= 0:
            return {"ok": False, "error": f"数量应大于0: {description}", "input": description}
        food, match, alts = find_food(food_query, index)
        if not food:
            return {
                "ok": False,
                "error": f"未找到食物: {food_query}",
                "input": description,
                "food_query": food_query,
                "amount": amount,
                "unit": unit or "份",
            }
        grams = resolve_grams(amount, unit, food, units)
        if grams is None:
            return {"ok": False, "error": f"无法换算单位: {unit}", "input": description}
    else:
        text = str(description).strip()

        # 语义否定拦截：若用户描述明确为不吃/不要，标记为 negated
        for neg in _NEGATION_PREFIXES:
            if text.startswith(neg):
                return {
                    "ok": False,
                    "negated": True,
                    "error": f"已识别为不吃/不要排除项: {description}",
                    "input": description,
                }

        # 从括号中提取真实的烹饪方式（如 '鸡胸肉(煎)'），仅当括号内容属于烹饪表时才算。
        # 若括号内容是食物名的一部分（如 '麻辣烫(人均)'），则保留，用于匹配食物。
        cook = None
        paren = re.search(r"[（(]([^）)]*)[）)]", text)
        if paren and paren.group(1) in cooking:
            cook = paren.group(1)
        else:
            # 无括号烹饪标注时，从文本中识别烹饪词（如 '清炒西兰花'）。成品菜名（如 '红烧排骨'）
            # 会在下方用 cook_word_in_name / prepared 守卫避免二次加成。
            cm = re.search(r"(清蒸|白灼|红烧|糖醋|清炒|爆炒|干煸|油焖|烧烤|烟熏|油炸|麻辣|炒|煎|炸|烤|蒸|煮|炖|凉拌)", text)
            if cm and cm.group(1) in cooking:
                cook = cm.group(1)

        # 去掉烹饪标注括号后再匹配食物；仅剥离属于烹饪表的括号，保留食物名自带的括号（如 '(人均)'）
        clean = re.sub(r"[（(](?:清蒸|白灼|红烧|糖醋|清炒|爆炒|干煸|油焖|烧烤|烟熏|油炸|麻辣|炒|煎|炸|烤|蒸|煮|炖|凉拌)[）)]", "", text)
        # 解析数量
        amount, unit, food_query = parse_amount(clean)
        if amount <= 0:
            return {"ok": False, "error": f"数量应大于0: {description}", "input": description}
        food, match, alts = find_food(food_query, index)
        if not food:
            return {
                "ok": False,
                "error": f"未找到食物: {food_query}",
                "input": description,
                "food_query": food_query,
                "amount": amount,
                "unit": unit or "份",
            }

        grams = resolve_grams(amount, unit, food, units)
        if grams is None:
            return {"ok": False, "error": f"无法换算单位: {unit}", "input": description}

    # 烹饪修正：仅对原始食材（主食/蛋类/奶类/肉禽/水产/豆类/蔬菜/水果/坚果）应用；
    # 已是成品/半成品（菜肴/快餐/零食等），或烹饪词本就内嵌在食物名/别名里（如 '红烧排骨'、'烤红薯'）
    # 时，不再二次加成，因为其营养值已含相应烹饪处理。
    factor = 1.0
    prepared = food.get("category") in _PREPARED_CATEGORIES
    names = {food["name"]} | set(food.get("aliases") or [])
    cook_word_in_name = bool(cook) and any(cook in n for n in names)
    if cook and not prepared and not cook_word_in_name:
        factor = cooking.get(cook, 1.0)

    w = grams / 100.0
    base_cal = food["cal"] * w
    target_cal = round(base_cal * factor, 0)
    delta_cal = max(0.0, target_cal - base_cal) if factor > 1.0 else 0.0

    # 外源介质质量增量模型 (Delta Mass Model)：
    # 严格遵循 Atwater 能量与质量守恒定律：烹饪增加的热量必然源自外源吸附的烹调油或糖。
    delta_fat = 0.0
    delta_sugar = 0.0
    delta_carb = 0.0

    if factor > 1.0 and delta_cal > 0:
        if cook in ("糖醋", "蜜汁", "拔丝"):
            # 糖醋/含糖酱汁：约40%热量源自外源添加糖，60%源自油脂
            delta_sugar = round((delta_cal * 0.4) / 4.0, 1)
            delta_carb = delta_sugar
            delta_fat = round((delta_cal * 0.6) / 9.0, 1)
        else:
            # 经典油脂烹饪（煎/炸/炒/清炒/干煸/油焖/烧烤/红烧等）：额外热量 100% 由吸附油脂提供
            delta_fat = round(delta_cal / 9.0, 1)

    vals = {}
    for m in MACROS:
        raw_val = food.get(m, 0.0) * w
        if m == "cal":
            vals["cal"] = target_cal
        elif m == "fat":
            vals["fat"] = round(raw_val + delta_fat, 1)
        elif m == "carb":
            vals["carb"] = round(raw_val + delta_carb, 1)
        elif m == "sugar":
            vals["sugar"] = round(raw_val + delta_sugar, 1)
        else:
            # 蛋白、纤维、钠不随烹调油脂虚假膨胀
            vals[m] = round(raw_val, 1)

    vals["net_carb"] = round(max(0.0, vals.get("carb", 0.0) - vals.get("fiber", 0.0)), 1)

    item = {
        "ok": True,
        "food": food["name"],
        "matched": match,
        "amount": amount,
        "unit": unit or "份",
        "grams": grams,
        "cooking": cook if factor != 1.0 else None,
        "cooking_factor": factor,
        "values": vals,
        "units": dict(NUTRIENT_UNITS),
    }
    if delta_fat > 0:
        item["cooking_oil_g"] = delta_fat
    if alts:
        item["alternatives"] = alts
    return item


def parse_meal(meal_input, foods, units, cooking, index=None):
    """解析一餐多种食物。
    meal_input 可为：
    - 自然语言描述串（逗号/分号/顿号/换行分隔，如 '1碗米饭, 150克鸡胸肉(煎)'）
    - 结构化条目列表（Agent 协议，如 [{'food': '米饭', 'amount': 1, 'unit': '碗'}]）
    - JSON 格式的结构化字符串
    """
    refresh_units(units, foods)
    index = index or build_index(foods)
    items = []
    unrecognized = []
    excluded = []

    parts = []
    if isinstance(meal_input, (list, tuple)):
        parts = meal_input
    elif isinstance(meal_input, dict):
        parts = meal_input.get("items") or [meal_input]
    elif isinstance(meal_input, str):
        trimmed = meal_input.strip()
        if (trimmed.startswith("[") and trimmed.endswith("]")) or (trimmed.startswith("{") and trimmed.endswith("}")):
            try:
                parsed = json.loads(trimmed)
                if isinstance(parsed, list):
                    parts = parsed
                elif isinstance(parsed, dict) and "items" in parsed:
                    parts = parsed["items"]
                elif isinstance(parsed, dict):
                    parts = [parsed]
                else:
                    parts = [p.strip() for p in re.split(r"[,，;；、\n]+", meal_input) if p.strip()]
            except Exception:
                # 尝试解析被 Windows/PowerShell 等终端剥离双引号的松散结构化对象列表
                # 例如: [{food: 米饭, amount: 1, unit: 碗}, {food: 鸡胸肉, amount: 150, unit: 克, cooking: 煎}]
                loose_dicts = []
                for block in re.findall(r"\{([^}]+)\}", trimmed):
                    d = {}
                    for kv in re.findall(r"([a-zA-Z_]\w*)\s*[:=]\s*([^,;]+)", block):
                        k = kv[0].strip().strip("'\"")
                        v = kv[1].strip().strip("'\"")
                        d[k] = v
                    if d and ("food" in d or "name" in d):
                        loose_dicts.append(d)
                if loose_dicts:
                    parts = loose_dicts
                else:
                    parts = [p.strip() for p in re.split(r"[,，;；、\n]+", meal_input) if p.strip()]
        else:
            parts = [p.strip() for p in re.split(r"[,，;；、\n]+", meal_input) if p.strip()]
    else:
        parts = []

    for part in parts:
        if not part:
            continue
        r = compute_item(part, foods, units, cooking, index)
        if r.get("ok"):
            items.append(r)
        elif r.get("negated"):
            excluded.append(r)
        else:
            unrecognized.append(r)
    # 汇总
    totals = {m: 0.0 for m in MACROS}
    for it in items:
        for m in MACROS:
            totals[m] += it["values"].get(m, 0)
    totals = {m: round(v, 1) for m, v in totals.items()}
    totals["net_carb"] = round(max(0.0, totals["carb"] - totals["fiber"]), 1)
    res = {
        "items": items,
        "totals": totals,
        "units": dict(NUTRIENT_UNITS),
        "summary": format_nutrient_summary(totals),
    }
    if unrecognized:
        res["unrecognized"] = unrecognized
    if excluded:
        res["excluded"] = excluded
    return res


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
