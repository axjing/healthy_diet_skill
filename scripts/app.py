# -*- coding: utf-8 -*-
"""饮食记录与健康代谢应用核心：确定性持久化、物理守恒核算、时序遥测大账本。
遵循 agentskills.io 规范，专为赋能 AI Agent 打造的确定性外骨骼引擎。
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _CURRENT_DIR not in sys.path:
    sys.path.insert(0, _CURRENT_DIR)

try:
    from . import calc, goals
except (ImportError, ValueError):
    import calc
    import goals

# 建议与量化遥测模块
try:
    from . import suggest
except (ImportError, ValueError):
    try:
        import suggest
    except ImportError:
        suggest = None

# Windows 控制台默认 gbk，设为 utf-8 以避免中文输出乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("HEALTHY_DIET_DATA_DIR", os.path.join(SKILL_DIR, "data"))
RECORDS_DIR = os.path.join(DATA_DIR, "records")
EXPORTS_DIR = os.path.join(DATA_DIR, "exports")
CUSTOM_FOODS_PATH = os.path.join(DATA_DIR, "custom_foods.json")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
HISTORY_CSV_PATH = os.path.join(EXPORTS_DIR, "diet_history.csv")

MACROS = ["cal", "protein", "carb", "fat", "fiber", "sugar", "sodium"]


def emit(result):
    """打印结果 JSON；若结果包含 error 字段则以非零退出码退出，便于脚本/agent 感知失败。"""
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if isinstance(result, dict) and "error" in result:
        sys.exit(2)


def atomic_write_json(path, data):
    """原子写入 JSON：采用进程PID与微秒区分临时文件，避免写一半崩溃或并发写坏数据。"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.{os.getpid()}_{datetime.now().strftime('%f')}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def sync_history_ledger():
    """全量聚合所有每日 records 生成或更新 data/exports/diet_history.csv 时间序列总账。"""
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    if not os.path.exists(RECORDS_DIR):
        return
    files = sorted([f for f in os.listdir(RECORDS_DIR) if f.endswith(".json") and len(f) == 15])
    if not files:
        return
    columns = ["date", "cal", "protein", "carb", "fat", "fiber", "sugar", "sodium",
               "exercise_cal", "net_cal", "weight", "meal_count"]
    lines = [",".join(columns)]
    for fname in files:
        d_str = fname[:-5]
        day = read_day(d_str)
        t = day_totals(day)
        exercise = sum(e.get("cal", 0) for e in day.get("exercise", []))
        net_cal = round(t["cal"] - exercise, 1)
        w = day.get("weight", "")
        row = [
            d_str,
            str(t["cal"]),
            str(t["protein"]),
            str(t["carb"]),
            str(t["fat"]),
            str(t["fiber"]),
            str(t["sugar"]),
            str(t["sodium"]),
            str(round(exercise, 1)),
            str(net_cal),
            str(w),
            str(len(day.get("meals", [])))
        ]
        lines.append(",".join(row))
    tmp = f"{HISTORY_CSV_PATH}.{os.getpid()}_{datetime.now().strftime('%f')}.tmp"
    with open(tmp, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines))
    os.replace(tmp, HISTORY_CSV_PATH)


def ensure_dirs():
    os.makedirs(RECORDS_DIR, exist_ok=True)
    os.makedirs(EXPORTS_DIR, exist_ok=True)


def load_foods():
    with open(calc.FOODS_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    foods = cfg["foods"]
    custom = []
    if os.path.exists(CUSTOM_FOODS_PATH):
        with open(CUSTOM_FOODS_PATH, encoding="utf-8") as f:
            custom = json.load(f).get("foods", [])
    return foods + custom, cfg["foods"], custom


def file_path_for(d):
    return os.path.join(RECORDS_DIR, f"{d}.json")


def validate_date(date_str):
    """校验并归一化日期为 YYYY-MM-DD（如 2026-9-7 -> 2026-09-07），非法则抛出 ValueError。
    归一化确保记录文件名与 range/export 按日期对象读取时一致，避免数据碎片。"""
    return datetime.strptime(str(date_str), "%Y-%m-%d").strftime("%Y-%m-%d")


def read_day(d):
    p = file_path_for(str(d))
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"date": str(d), "meals": [], "exercise": []}


def write_day(d, data):
    atomic_write_json(file_path_for(str(d)), data)
    try:
        sync_history_ledger()
    except Exception:
        pass


def set_weight(date_str, weight):
    """记录某日体重(kg)。"""
    date_str = validate_date(date_str)
    w = float(weight)
    if not (20.0 <= w <= 300.0):
        raise ValueError(f"体重数值应在 20-300 kg 之间，收到: {weight}")
    day = read_day(date_str)
    day["weight"] = round(w, 2)
    write_day(date_str, day)
    return {"ok": True, "date": date_str, "weight": round(w, 2)}


def normalize_ts(ts):
    """校验并归一化补记时间为 YYYY-MM-DD HH:MM:SS；非法抛 ValueError。"""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(ts, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise ValueError(f"时间格式应为 YYYY-MM-DD HH:MM[:SS]，收到: {ts}")


def meal_classify_hour_str(ts):
    try:
        return calc.meal_classify(datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").hour)
    except Exception:
        return "加餐"


VALID_MEALS = {"早餐", "午餐", "晚餐", "加餐"}


def add_meal(date_str, description, ts=None, meal_override=None):
    """新增一餐记录。description 可为食物描述串、结构化列表或 JSON。返回新增餐次及其明细。"""
    date_str = validate_date(date_str)
    foods, _, _ = load_foods()
    _, units, cooking = calc.load_data()
    index = calc.build_index(foods)
    res = calc.parse_meal(description, foods, units, cooking, index)
    if not res["items"]:
        return {"error": "未能解析任何食物", "parsed": res}
    if meal_override and meal_override not in VALID_MEALS:
        return {"error": f"餐次非法，可选值：{','.join(sorted(VALID_MEALS))}", "given": meal_override}
    ts = ts or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ts = normalize_ts(ts)
    meal_name = meal_override or meal_classify_hour_str(ts)

    # 规范化记录中的 text 摘要表示
    if isinstance(description, (list, tuple)):
        text_desc = ", ".join(
            f"{it.get('amount','')}{it.get('unit','')}{it.get('food','')}{'('+it['cooking']+')' if it.get('cooking') else ''}"
            if isinstance(it, dict) else str(it)
            for it in description
        )
    elif isinstance(description, dict) and "items" in description:
        text_desc = ", ".join(
            f"{it.get('amount','')}{it.get('unit','')}{it.get('food','')}{'('+it['cooking']+')' if it.get('cooking') else ''}"
            if isinstance(it, dict) else str(it)
            for it in description.get("items", [])
        )
    elif isinstance(description, str) and (description.strip().startswith("[") or description.strip().startswith("{")):
        if res.get("items"):
            text_desc = ", ".join(
                f"{it.get('amount','')}{it.get('unit','')}{it.get('food','')}{'('+it['cooking']+')' if it.get('cooking') else ''}"
                for it in res["items"]
            )
        else:
            text_desc = description
    else:
        text_desc = str(description)

    day = read_day(date_str)
    day["meals"].append({
        "ts": ts,
        "meal": meal_name,
        "text": text_desc,
        "items": res["items"],
        "totals": res["totals"],
    })
    write_day(date_str, day)
    warnings = []
    if ts[:10] != date_str:
        warnings.append(f"--ts 日期({ts[:10]})与记录日期({date_str})不一致，已按 {date_str} 入库")
    if res.get("unrecognized"):
        for u in res["unrecognized"]:
            warnings.append(f"未识别项: {u.get('input')} ({u.get('error')})")
    if res.get("excluded"):
        for ex in res["excluded"]:
            warnings.append(f"排除项: {ex.get('input')}")

    result = {
        "ok": True,
        "meal": meal_name,
        "text": text_desc,
        "totals": res["totals"],
        "items": res["items"]
    }
    if warnings:
        result["warnings"] = warnings
    if res.get("unrecognized"):
        result["unrecognized"] = res["unrecognized"]
    return result


def day_totals(day):
    t = {m: 0.0 for m in MACROS}
    for meal in day.get("meals", []):
        totals = meal.get("totals") or {}  # 防御手改/旧版数据缺 totals 字段
        for m in MACROS:
            t[m] += totals.get(m, 0)
    return {m: round(v, 1) for m, v in t.items()}


def analyze_day(date_str, targets=None):
    """单日统计 + 达标判定 + 热量收支（运动消耗）+ 健康评估。"""
    date_str = validate_date(date_str)
    day = read_day(date_str)
    t = day_totals(day)
    exercise = sum(e.get("cal", 0) for e in day.get("exercise", []))
    t["exercise_cal"] = exercise
    t["net_cal"] = round(t["cal"] - exercise, 1)
    if targets:
        t["status"] = {
            "cal_remaining": round(targets["cal_target"] - t["cal"], 1),
            "cal_over": t["cal"] > targets["cal_target"] * 1.05,
            "cal_under": t["cal"] < targets["cal_target"] * 0.85,
            "protein_pct": round(t["protein"] / targets["protein_g_target"] * 100),
            "carb_pct": round(t["carb"] / targets["carb_g_target"] * 100),
            "fat_pct": round(t["fat"] / targets["fat_g_target"] * 100),
        }
    t["meal_count"] = len(day.get("meals", []))
    res = {"date": str(date_str), "totals": t, "meals": day.get("meals", []), "exercise": day.get("exercise", [])}
    if "weight" in day:
        res["weight"] = day["weight"]
    return res


def delete_meal(date_str, index):
    date_str = validate_date(date_str)
    day = read_day(date_str)
    if 0 <= index < len(day.get("meals", [])):
        removed = day["meals"].pop(index)
        write_day(date_str, day)
        return {"ok": True, "removed": removed}
    return {"error": "索引越界", "meal_count": len(day.get("meals", []))}


def edit_meal(date_str, index, description=None, meal_override=None):
    date_str = validate_date(date_str)
    day = read_day(date_str)
    if not (0 <= index < len(day.get("meals", []))):
        return {"error": "索引越界"}
    meal = day["meals"][index]
    if meal_override:
        if meal_override not in VALID_MEALS:
            return {"error": f"餐次非法，可选值：{','.join(sorted(VALID_MEALS))}", "given": meal_override}
        meal["meal"] = meal_override
    if description is not None:
        food, _, c = load_foods()
        _, units, cooking = calc.load_data()
        res = calc.parse_meal(description, food, units, cooking, calc.build_index(food))
        if res["items"]:
            meal["text"] = description
            meal["items"] = res["items"]
            meal["totals"] = res["totals"]
        else:
            return {"error": "新描述解析失败"}
    write_day(date_str, day)
    return {"ok": True, "meal": meal}


def add_exercise(date_str, item, duration_min, cal):
    date_str = validate_date(date_str)
    if duration_min is None or duration_min <= 0:
        raise ValueError(f"运动时长(分钟)应大于0，收到: {duration_min}")
    if cal is None or cal < 0:
        raise ValueError(f"消耗热量不能为负，收到: {cal}")
    day = read_day(date_str)
    day.setdefault("exercise", []).append({"item": item, "min": duration_min, "cal": cal})
    write_day(date_str, day)
    return {"ok": True}


def range_stats(start, end):
    """区间汇总：逐日 + 总计 + 平均值（含运动消耗与净摄入）。"""
    rows = []
    cur = start
    days_count = (end - start).days + 1
    meal_days = 0
    exercise_days = 0
    while cur <= end:
        day = read_day(cur)
        t = day_totals(day)
        exercise = sum(e.get("cal", 0) for e in day.get("exercise", []))
        t["exercise_cal"] = round(exercise, 1)
        t["net_cal"] = round(t["cal"] - exercise, 1)
        if t["cal"] > 0:
            meal_days += 1
        if exercise > 0:
            exercise_days += 1
        if "weight" in day:
            t["weight"] = day["weight"]
        rows.append({"date": str(cur), **t})
        cur += timedelta(days=1)
    total = {m: round(sum(r.get(m, 0) for r in rows), 1) for m in MACROS}
    total["exercise_cal"] = round(sum(r.get("exercise_cal", 0) for r in rows), 1)
    total["net_cal"] = round(total["cal"] - total["exercise_cal"], 1)

    # 有记录饮食日的摄入结构平均值
    n = max(meal_days, 1)
    avg = {m: round(total[m] / n, 1) for m in MACROS}
    # 运动日均消耗（按实际运动天数核算；若无运动则为0）
    avg["exercise_cal"] = round(total["exercise_cal"] / max(exercise_days, 1), 1) if exercise_days > 0 else 0.0
    # 区间自然日日均净摄入
    avg["net_cal"] = round(total["net_cal"] / max(days_count, 1), 1)

    meta = {
        "days_in_range": days_count,
        "days_with_meals": meal_days,
        "days_with_exercise": exercise_days,
    }
    return {"start": str(start), "end": str(end), "meta": meta, "rows": rows, "total": total, "avg": avg}


def to_csv(rows, path):
    columns = ["date"] + MACROS + ["exercise_cal", "net_cal"]
    lines = [",".join(columns)]
    for r in rows:
        lines.append(",".join(str(r.get(c, 0)) for c in columns))
    with open(path, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines))
    return path


def to_json_export(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    return path


def custom_food_add(name, cal, protein=0, carb=0, fat=0, fiber=0, sugar=0, sodium=0, serving=None):
    current = {"foods": []}
    if os.path.exists(CUSTOM_FOODS_PATH):
        with open(CUSTOM_FOODS_PATH, encoding="utf-8") as f:
            current = json.load(f)
    entry = {"name": name, "aliases": [], "category": "自定义", "cal": cal, "protein": protein,
             "carb": carb, "fat": fat, "fiber": fiber, "sugar": sugar, "sodium": sodium,
             "serving": serving or {}}
    current["foods"] = [f for f in current.get("foods", []) if f["name"] != name]
    current["foods"].append(entry)
    atomic_write_json(CUSTOM_FOODS_PATH, current)
    return entry


def load_settings():
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_settings(s):
    atomic_write_json(SETTINGS_PATH, s)
    return s


def profile_init(sex, weight, height, age, activity, goal):
    """保存用户档案，用于目标计算。返回 daily_targets 结果。
    先校验（活动量/目标/数值范围），失败时不写入档案。"""
    profile = [sex, float(weight), float(height), int(age),
               goals.resolve_activity_name(activity), goal]
    targets = goals.daily_targets(*profile)
    s = load_settings()
    s["profile"] = profile
    save_settings(s)
    targets["ok"] = True
    return targets


def profile_targets():
    """从档案计算目标；无档案时返回None。"""
    s = load_settings()
    if "profile" in s:
        return goals.daily_targets(*s["profile"])
    return None


# ---------------------------------------------------------------------------
# Python Native SDK 接口（供各类 Agent 框架直接 import 调用）
# ---------------------------------------------------------------------------

def record(items_or_text, date=None, meal=None, ts=None):
    """Python SDK: 记录一餐饮食。支持结构化条目列表/JSON或口语文本。"""
    date_str = validate_date(date) if date else datetime.now().strftime("%Y-%m-%d")
    return add_meal(date_str, items_or_text, ts=ts, meal_override=meal)


def telemetry(date=None):
    """Python SDK: 获取单日生理摄入与高密度量化健康遥测指标。"""
    date_str = validate_date(date) if date else datetime.now().strftime("%Y-%m-%d")
    prof = load_settings().get("profile")
    targets = goals.daily_targets(*prof) if prof else None
    if suggest:
        return suggest.evaluate_day(date_str, targets)
    return analyze_day(date_str, targets)


def weight(kg, date=None):
    """Python SDK: 记录体重(kg)。"""
    date_str = validate_date(date) if date else datetime.now().strftime("%Y-%m-%d")
    return set_weight(date_str, kg)


def exercise(item, minutes, cal, date=None):
    """Python SDK: 记录运动消耗。"""
    date_str = validate_date(date) if date else datetime.now().strftime("%Y-%m-%d")
    return add_exercise(date_str, item, float(minutes), float(cal))


def adaptive(days=30):
    """Python SDK: 闭环自适应能量代谢校准。"""
    prof = load_settings().get("profile")
    fallback = goals.daily_targets(*prof)["tdee"] if prof else 2000.0
    return goals.calibrate_adaptive_tdee(RECORDS_DIR, fallback_tdee=fallback, window_days=days)


def custom(name, cal, protein=0.0, carb=0.0, fat=0.0, fiber=0.0, sugar=0.0, sodium=0.0):
    """Python SDK: 注册自定义食物。"""
    return add_custom_food(name, cal, protein, carb, fat, fiber, sugar, sodium)


def profile(sex, weight_kg, height_cm, age, activity="轻度", goal="维持"):
    """Python SDK: 设定身体档案与营养基准。"""
    return profile_init(sex, weight_kg, height_cm, age, activity, goal)


# ---------------------------------------------------------------------------
# CLI 主入口
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(prog="diet")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", aliases=["record"], help="记录一餐，支持自然语言或结构化 JSON：diet record '1碗米饭,煎鸡胸肉' 或 diet record --items '[...]'")
    p.add_argument("arg1", nargs="?", default=None, help="日期(YYYY-MM-DD)或直接食物描述/JSON")
    p.add_argument("arg2", nargs="?", default=None, help="食物描述(当arg1为日期时)")
    p.add_argument("--items", help="结构化条目 JSON 列表，如 '[{\"food\": \"米饭\", \"amount\": 1, \"unit\": \"碗\"}]'")
    p.add_argument("--meal", choices=sorted(VALID_MEALS), help="餐次覆盖：早餐/午餐/晚餐/加餐")
    p.add_argument("--ts", default=None, help="补记时间 YYYY-MM-DD HH:MM[:SS]")

    p = sub.add_parser("delete", help="删除某日某餐索引")
    p.add_argument("date")
    p.add_argument("index", type=int)

    p = sub.add_parser("edit", help="修改某日某餐")
    p.add_argument("date")
    p.add_argument("index", type=int)
    p.add_argument("--text")
    p.add_argument("--meal")

    p = sub.add_parser("day", help="查看某日分析（默认查看今日）")
    p.add_argument("date", nargs="?", default=None)
    p.add_argument("--targets", action="store_true")

    p = sub.add_parser("telemetry", help="获取当日能量、营养素、达标缺口与量化健康遥测向量（专供 Agent 决策认知）")
    p.add_argument("date", nargs="?", default=None, help="目标日期，默认今日")

    p = sub.add_parser("range", help="区间统计 开始 结束")
    p.add_argument("start")
    p.add_argument("end")

    p = sub.add_parser("export", help="导出 CSV/JSON，如 diet export 2026-09-01 2026-09-07 out --format csv")
    p.add_argument("start")
    p.add_argument("end")
    p.add_argument("out")
    p.add_argument("--format", choices=["csv", "json"], default="csv")

    p = sub.add_parser("goals", help="计算热量目标，参数 性别 体重身高 年龄 活动量 目标")
    p.add_argument("args", nargs="*")

    p = sub.add_parser("adaptive", help="闭环代谢自适应遥测：基于历史摄入与体重遥测回归自校准真实 TDEE")
    p.add_argument("--days", type=int, default=30, help="回溯天数(默认30天)")

    p = sub.add_parser("weight", help="记录体重(kg)：diet weight <数值> 或 diet weight 2026-09-07 <数值>")
    p.add_argument("arg1", help="体重数值或日期")
    p.add_argument("arg2", nargs="?", default=None, help="体重数值(当arg1为日期时)")

    p = sub.add_parser("profile_init", help="保存档案: 性别 体重 身高 年龄 活动量 目标")
    p.add_argument("sex")
    p.add_argument("weight", type=float)
    p.add_argument("height", type=float)
    p.add_argument("age", type=int)
    p.add_argument("activity", default="轻度")
    p.add_argument("goal", default="维持")

    p = sub.add_parser("custom", help="添加自定义食物：名称 每100g热量 蛋白 碳水 脂肪")
    p.add_argument("name")
    p.add_argument("cal", type=float)
    p.add_argument("--protein", type=float, default=0)
    p.add_argument("--carb", type=float, default=0)
    p.add_argument("--fat", type=float, default=0)
    p.add_argument("--fiber", type=float, default=0)
    p.add_argument("--sugar", type=float, default=0)
    p.add_argument("--sodium", type=float, default=0)

    p = sub.add_parser("exercise", help="运动记录：[日期] 项目 分钟 消耗热量，如 diet exercise 跑步 30 300")
    p.add_argument("arg1", help="日期或运动项目")
    p.add_argument("arg2", help="运动项目或分钟")
    p.add_argument("arg3", help="分钟或消耗热量")
    p.add_argument("arg4", nargs="?", default=None, help="消耗热量(当arg1为日期时)")

    p = sub.add_parser("eval", help="计算一条描述")
    p.add_argument("text")

    args = ap.parse_args()

    if args.cmd in ("add", "record"):
        target_date = datetime.now().strftime("%Y-%m-%d")
        description = None

        if args.items:
            description = args.items
            if args.arg1:
                try:
                    target_date = validate_date(args.arg1)
                except ValueError:
                    pass
        elif args.arg1:
            try:
                target_date = validate_date(args.arg1)
                description = args.arg2
            except ValueError:
                description = f"{args.arg1} {args.arg2 or ''}".strip()
                target_date = datetime.now().strftime("%Y-%m-%d")
        else:
            description = args.arg2

        if not description:
            emit({"error": "缺少食物描述或 --items 结构化条目"})
        else:
            emit(add_meal(target_date, description, args.ts, args.meal))
    elif args.cmd == "delete":
        emit(delete_meal(args.date, args.index))
    elif args.cmd == "edit":
        if args.text is None and not args.meal:
            emit({"error": "请提供 --text 新描述或 --meal 新餐次"})
        else:
            emit(edit_meal(args.date, args.index, args.text, args.meal))
    elif args.cmd == "day":
        target_date = validate_date(args.date) if args.date else datetime.now().strftime("%Y-%m-%d")
        targets = profile_targets() if args.targets else None
        print(json.dumps(analyze_day(target_date, targets), ensure_ascii=False, indent=2))
    elif args.cmd == "telemetry":
        target_date = validate_date(args.date) if args.date else datetime.now().strftime("%Y-%m-%d")
        profile = load_settings().get("profile")
        targets = goals.daily_targets(*profile) if profile else None
        if suggest:
            emit(suggest.evaluate_day(target_date, targets))
        else:
            emit(analyze_day(target_date, targets))
    elif args.cmd == "exercise":
        if args.arg4 is not None:
            ex_date = validate_date(args.arg1)
            ex_item = args.arg2
            ex_min = float(args.arg3)
            ex_cal = float(args.arg4)
        else:
            ex_date = datetime.now().strftime("%Y-%m-%d")
            ex_item = args.arg1
            ex_min = float(args.arg2)
            ex_cal = float(args.arg3)
        emit(add_exercise(ex_date, ex_item, ex_min, ex_cal))
    elif args.cmd == "delete":
        emit(delete_meal(args.date, args.index))
    elif args.cmd == "edit":
        if args.text is None and not args.meal:
            emit({"error": "请提供 --text 新描述或 --meal 新餐次"})
        else:
            emit(edit_meal(args.date, args.index, args.text, args.meal))
    elif args.cmd == "day":
        target_date = validate_date(args.date) if args.date else datetime.now().strftime("%Y-%m-%d")
        targets = profile_targets() if args.targets else None
        print(json.dumps(analyze_day(target_date, targets), ensure_ascii=False, indent=2))
    elif args.cmd == "weight":
        if args.arg2:
            target_date = validate_date(args.arg1)
            try:
                w_val = float(args.arg2)
            except ValueError:
                emit({"error": f"体重数值非法，收到: {args.arg2}"})
                sys.exit(2)
        else:
            try:
                w_val = float(args.arg1)
                target_date = datetime.now().strftime("%Y-%m-%d")
            except ValueError:
                emit({"error": f"请输入有效的体重数值(kg)，收到: {args.arg1}"})
                sys.exit(2)
        emit(set_weight(target_date, w_val))
    elif args.cmd == "adaptive":
        profile = load_settings().get("profile")
        fallback = goals.daily_targets(*profile)["tdee"] if profile else 2000.0
        res = goals.calibrate_adaptive_tdee(RECORDS_DIR, fallback_tdee=fallback, window_days=args.days)
        emit(res)
    elif args.cmd == "range":
        s = datetime.strptime(validate_date(args.start), "%Y-%m-%d").date()
        e = datetime.strptime(validate_date(args.end), "%Y-%m-%d").date()
        if s > e:
            emit({"error": f"开始日期晚于结束日期: {args.start} > {args.end}"})
        elif (e - s).days > 731:
            emit({"error": "日期区间过长（最多 731 天），请缩小范围"})
        else:
            print(json.dumps(range_stats(s, e), ensure_ascii=False, indent=2))
    elif args.cmd == "export":
        s = datetime.strptime(validate_date(args.start), "%Y-%m-%d").date()
        e = datetime.strptime(validate_date(args.end), "%Y-%m-%d").date()
        if s > e:
            emit({"error": f"开始日期晚于结束日期: {args.start} > {args.end}"})
        elif (e - s).days > 731:
            emit({"error": "日期区间过长（最多 731 天），请缩小范围"})
        else:
            rows = range_stats(s, e)["rows"]
            p = to_csv(rows, args.out) if args.format == "csv" else to_json_export(rows, args.out)
            print(json.dumps({"exported": p, "rows": len(rows)}, ensure_ascii=False))
    elif args.cmd == "profile_init":
        emit(profile_init(args.sex, args.weight, args.height, args.age, args.activity, args.goal))
    elif args.cmd == "goals":
        a = list(args.args)
        if len(a) < 4:
            emit({"error": "goals 需要至少 4 个参数：性别 体重 身高 年龄 [活动量 目标]",
                  "given": len(a)})
        else:
            try:
                a[1], a[2] = float(a[1]), float(a[2])
                a[3] = int(a[3])
            except ValueError:
                emit({"error": f"体重/身高/年龄需为数字，收到: {args.args}"})
            else:
                emit(goals.daily_targets(*a))
    elif args.cmd == "custom":
        emit(custom_food_add(args.name, args.cal, args.protein, args.carb, args.fat,
                             fiber=args.fiber, sugar=args.sugar, sodium=args.sodium))
    elif args.cmd == "exercise":
        emit(add_exercise(args.date, args.item, args.min, args.cal))
    elif args.cmd == "eval":
        foods, base, custom = load_foods()
        _, units, cooking = calc.load_data()
        parsed = calc.parse_meal(args.text, foods, units, cooking, calc.build_index(foods))
        if not parsed["items"]:
            emit({"error": "未能解析任何食物", **parsed})
        else:
            print(json.dumps(parsed, ensure_ascii=False, indent=2))
    elif args.cmd == "analyze":
        if args.dry_run:
            provider = args.provider or vision.load_vision_config().get("provider", "qwen")
            info = vision.PROVIDERS[provider]
            model = args.model or vision.load_vision_config().get("model") or info["default_model"]
            try:
                messages = vision.build_messages(args.image)
            except ValueError as exc:
                print(json.dumps({"dry_run": True, "error": str(exc)}, ensure_ascii=False, indent=2))
                sys.exit(2)
            print(json.dumps({"dry_run": True, "provider": provider, "model": model,
                              "base_url": info["base_url"], "messages": messages},
                             ensure_ascii=False, indent=2))
        else:
            desc = vision.analyze_image(args.image, provider=args.provider, model=args.model)
            foods, _, _ = load_foods()
            _, units, cooking = calc.load_data()
            parsed = calc.parse_meal(desc, foods, units, cooking, calc.build_index(foods))
            if not parsed["items"]:
                emit({"error": f"识别结果未能解析出食物: {desc}", "description": desc, "parsed": parsed})
            else:
                print(json.dumps({"description": desc, "parsed": parsed}, ensure_ascii=False, indent=2))
    elif args.cmd == "vision":
        if args.vision_cmd == "list":
            cfg = vision.load_vision_config()
            rows = []
            for p, info in vision.PROVIDERS.items():
                rows.append({
                    "provider": p,
                    "name": info["name"],
                    "default_model": info["default_model"],
                    "active": cfg.get("provider") == p,
                    "model": cfg.get("model") if cfg.get("provider") == p else info["default_model"],
                    "key_from_settings": bool(cfg.get("provider") == p and cfg.get("api_key")),
                    "key_from_env": info["env_key"],
                    "env_set": bool(os.environ.get(info["env_key"])),
                })
            print(json.dumps({"current": cfg.get("provider"), "providers": rows}, ensure_ascii=False, indent=2))
        elif args.vision_cmd == "config":
            out = vision.save_vision_config(args.provider, args.api_key, args.model)
            print(json.dumps({"ok": True, "saved": {**out, "api_key": "***"}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except ImportError as exc:
        # 延迟导入后，ImportError 只可能来自图片识别所需的 openai 库
        print(json.dumps({"error": f"图片识别需要 openai 库: {exc}。请执行 pip install openai（其余命令不受影响）"}, ensure_ascii=False, indent=2))
        sys.exit(2)
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        sys.exit(2)
