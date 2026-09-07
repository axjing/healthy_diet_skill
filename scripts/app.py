# -*- coding: utf-8 -*-
"""饮食记录应用：持久化、增删改查、统计分析、导出、热量收支联动。
数据按日期存储在 data/records/<YYYY-MM-DD>.json，用户自定义食物在 data/custom_foods.json。
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

import calc
import goals
import vision

# Windows 控制台默认 gbk，设为 utf-8 以避免中文输出乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORDS_DIR = os.path.join(SKILL_DIR, "data", "records")
CUSTOM_FOODS_PATH = os.path.join(SKILL_DIR, "data", "custom_foods.json")
SETTINGS_PATH = os.path.join(SKILL_DIR, "data", "settings.json")

MACROS = ["cal", "protein", "carb", "fat", "fiber", "sugar", "sodium"]


def ensure_dirs():
    os.makedirs(RECORDS_DIR, exist_ok=True)


def load_foods():
    cfg = json.load(open(calc.FOODS_PATH, encoding="utf-8"))
    foods = cfg["foods"]
    custom = []
    if os.path.exists(CUSTOM_FOODS_PATH):
        custom = json.load(open(CUSTOM_FOODS_PATH, encoding="utf-8")).get("foods", [])
    return foods + custom, cfg["foods"], custom


def file_path_for(d):
    return os.path.join(RECORDS_DIR, f"{d}.json")


def validate_date(date_str):
    """校验日期格式为 YYYY-MM-DD，非法则抛出 ValueError。"""
    datetime.strptime(str(date_str), "%Y-%m-%d")
    return str(date_str)


def read_day(d):
    p = file_path_for(str(d))
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    return {"date": str(d), "meals": [], "exercise": []}


def write_day(d, data):
    ensure_dirs()
    with open(file_path_for(str(d)), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def meal_classify_hour_str(ts):
    try:
        dt = datetime.fromisoformat(ts) if "T" in ts else datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        return calc.meal_classify(dt.hour)
    except Exception:
        return "加餐"


VALID_MEALS = {"早餐", "午餐", "晚餐", "加餐"}


def add_meal(date_str, description, ts=None, meal_override=None):
    """新增一餐记录。description 可为食物描述串。返回新增餐次及其明细。"""
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
    meal_name = meal_override or meal_classify_hour_str(ts)
    day = read_day(date_str)
    day["meals"].append({
        "ts": ts,
        "meal": meal_name,
        "text": description,
        "items": res["items"],
        "totals": res["totals"],
    })
    write_day(date_str, day)
    return {"ok": True, "meal": meal_name, "totals": res["totals"]}


def day_totals(day):
    t = {m: 0.0 for m in MACROS}
    for meal in day.get("meals", []):
        for m in MACROS:
            t[m] += meal["totals"].get(m, 0)
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
    return {"date": str(date_str), "totals": t, "meals": day.get("meals", []), "exercise": day.get("exercise", [])}


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
    if description:
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
    day = read_day(date_str)
    day.setdefault("exercise", []).append({"item": item, "min": duration_min, "cal": cal})
    write_day(date_str, day)
    return {"ok": True}


def range_stats(start, end):
    """区间汇总：逐日 + 总计 + 平均值（含运动消耗与净摄入）。"""
    rows = []
    cur = start
    while cur <= end:
        day = read_day(cur)
        t = day_totals(day)
        exercise = sum(e.get("cal", 0) for e in day.get("exercise", []))
        t["exercise_cal"] = round(exercise, 1)
        t["net_cal"] = round(t["cal"] - exercise, 1)
        rows.append({"date": str(cur), **t})
        cur += timedelta(days=1)
    total = {m: round(sum(r.get(m, 0) for r in rows), 1) for m in MACROS}
    total["exercise_cal"] = round(sum(r.get("exercise_cal", 0) for r in rows), 1)
    n = max(len([r for r in rows if r["cal"] > 0]), 1)
    avg = {m: round(total[m] / n, 1) for m in MACROS}
    avg["exercise_cal"] = round(total["exercise_cal"] / n, 1)
    avg["net_cal"] = round(total["cal"] / n - total["exercise_cal"] / n, 1)
    return {"start": str(start), "end": str(end), "rows": rows, "total": total, "avg": avg}


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
    current = json.load(open(CUSTOM_FOODS_PATH, encoding="utf-8")) if os.path.exists(CUSTOM_FOODS_PATH) else {"foods": []}
    entry = {"name": name, "aliases": [], "category": "自定义", "cal": cal, "protein": protein,
             "carb": carb, "fat": fat, "fiber": fiber, "sugar": sugar, "sodium": sodium,
             "serving": serving or {}}
    current["foods"] = [f for f in current["foods"] if f["name"] != name]
    current["foods"].append(entry)
    with open(CUSTOM_FOODS_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return entry


def load_settings():
    if os.path.exists(SETTINGS_PATH):
        return json.load(open(SETTINGS_PATH, encoding="utf-8"))
    return {}


def save_settings(s):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
    return s


def profile_init(sex, weight, height, age, activity, goal):
    """保存用户档案，用于目标计算。返回 daily_targets 结果。"""
    profile = [sex, float(weight), float(height), int(age),
               goals.resolve_activity_name(activity), goal]
    s = load_settings()
    s["profile"] = profile
    save_settings(s)
    return goals.daily_targets(*profile)


def profile_targets():
    """从档案计算目标；无档案时返回None。"""
    s = load_settings()
    if "profile" in s:
        return goals.daily_targets(*s["profile"])
    return None


def main():
    ap = argparse.ArgumentParser(prog="diet")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="记录一餐，如 diet add 2026-09-07 \"1碗米饭,煎鸡胸肉\"；或 --image 图片识别")
    p.add_argument("date")
    p.add_argument("text", nargs="?")
    p.add_argument("--image")
    p.add_argument("--provider")
    p.add_argument("--meal")
    p.add_argument("--ts", default=None)

    p = sub.add_parser("delete", help="删除某日某餐索引")
    p.add_argument("date")
    p.add_argument("index", type=int)

    p = sub.add_parser("edit", help="修改某日某餐")
    p.add_argument("date")
    p.add_argument("index", type=int)
    p.add_argument("--text")
    p.add_argument("--meal")

    p = sub.add_parser("day", help="查看某日分析")
    p.add_argument("date")
    p.add_argument("--targets", action="store_true")

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
    p.add_argument("--sugar", type=float, default=0)
    p.add_argument("--sodium", type=float, default=0)

    p = sub.add_parser("exercise", help="运动记录：日期 项目 分钟 消耗热量")
    p.add_argument("date")
    p.add_argument("item")
    p.add_argument("min", type=float)
    p.add_argument("cal", type=float)

    p = sub.add_parser("eval", help="计算一条描述")
    p.add_argument("text")

    p = sub.add_parser("analyze", help="识别图片中的食物（不保存），如 diet analyze photo.jpg")
    p.add_argument("image")
    p.add_argument("--provider")
    p.add_argument("--model")
    p.add_argument("--dry-run", action="store_true", help="只输出将发送的请求体，不实际调用")

    p = sub.add_parser("vision", help="配置/查看图片识别服务商")
    vp = p.add_subparsers(dest="vision_cmd", required=True)
    v_list = vp.add_parser("list", help="列出支持的服务商与当前配置")
    v_cfg = vp.add_parser("config", help="配置服务商 API Key：vision config <provider> <api_key> [--model]")
    v_cfg.add_argument("provider", choices=list(vision.PROVIDERS.keys()))
    v_cfg.add_argument("api_key")
    v_cfg.add_argument("--model")

    args = ap.parse_args()

    if args.cmd == "add":
        description = args.text
        vision_desc = None
        if args.image:
            vision_desc = vision.analyze_image(args.image, provider=args.provider)
            description = f"{args.text}，{vision_desc}" if args.text else vision_desc
        if not description:
            print(json.dumps({"error": "缺少食物描述或 --image 图片"}, ensure_ascii=False, indent=2))
            sys.exit(2)
        else:
            res = add_meal(args.date, description, args.ts, args.meal)
            if vision_desc:
                res = {"vision": vision_desc, **res}
            print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.cmd == "delete":
        print(json.dumps(delete_meal(args.date, args.index), ensure_ascii=False, indent=2))
    elif args.cmd == "edit":
        print(json.dumps(edit_meal(args.date, args.index, args.text, args.meal), ensure_ascii=False, indent=2))
    elif args.cmd == "day":
        targets = profile_targets() if args.targets else None
        print(json.dumps(analyze_day(args.date, targets), ensure_ascii=False, indent=2))
    elif args.cmd == "range":
        s = datetime.strptime(validate_date(args.start), "%Y-%m-%d").date()
        e = datetime.strptime(validate_date(args.end), "%Y-%m-%d").date()
        print(json.dumps(range_stats(s, e), ensure_ascii=False, indent=2))
    elif args.cmd == "export":
        s = datetime.strptime(validate_date(args.start), "%Y-%m-%d").date()
        e = datetime.strptime(validate_date(args.end), "%Y-%m-%d").date()
        rows = range_stats(s, e)["rows"]
        p = to_csv(rows, args.out) if args.format == "csv" else to_json_export(rows, args.out)
        print(json.dumps({"exported": p, "rows": len(rows)}, ensure_ascii=False))
    elif args.cmd == "profile_init":
        print(json.dumps(profile_init(args.sex, args.weight, args.height, args.age, args.activity, args.goal), ensure_ascii=False, indent=2))
    elif args.cmd == "goals":
        a = list(args.args)
        if len(a) < 4:
            print(json.dumps({"error": "goals 需要至少 4 个参数：性别 体重 身高 年龄 [活动量 目标]",
                              "given": len(a)}, ensure_ascii=False, indent=2))
        else:
            for i in (1, 2):
                a[i] = float(a[i])
            a[3] = int(a[3])
            print(json.dumps(goals.daily_targets(*a), ensure_ascii=False, indent=2))
    elif args.cmd == "custom":
        print(json.dumps(custom_food_add(args.name, args.cal, args.protein, args.carb, args.fat,
                                         sugar=args.sugar, sodium=args.sodium), ensure_ascii=False, indent=2))
    elif args.cmd == "exercise":
        print(json.dumps(add_exercise(args.date, args.item, args.min, args.cal), ensure_ascii=False))
    elif args.cmd == "eval":
        foods, base, custom = load_foods()
        _, units, cooking = calc.load_data()
        print(json.dumps(calc.parse_meal(args.text, foods, units, cooking, calc.build_index(foods)), ensure_ascii=False, indent=2))
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
        print(json.dumps({"error": f"缺少依赖库: {exc}。请先执行 pip install openai"}, ensure_ascii=False, indent=2))
        sys.exit(2)
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        sys.exit(2)
