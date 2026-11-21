# 数据结构与持久化规范 (Data Schema Reference)

本文档归档于 `references/`，详细定义本技能产生与消费的各项数据文件格式。

---

## 1. 每日记录文件 (`data/records/<YYYY-MM-DD>.json`)

每日常规记录按日期独立建档，存储餐次明细、运动消耗与体重遥测：

```json
{
  "date": "2026-09-07",
  "weight": 70.2,
  "meals": [
    {
      "ts": "2026-09-07 12:30:00",
      "meal": "午餐",
      "text": "1碗米饭,150克鸡胸肉(煎)",
      "items": [
        {
          "ok": true,
          "food": "米饭",
          "matched": "精确",
          "amount": 1.0,
          "unit": "碗",
          "grams": 150.0,
          "cooking": null,
          "cooking_factor": 1.0,
          "values": {
            "cal": 174.0,
            "protein": 3.9,
            "carb": 38.8,
            "fat": 0.4,
            "fiber": 0.4,
            "sugar": 0.0,
            "sodium": 1.8
          }
        },
        {
          "ok": true,
          "food": "鸡胸肉",
          "matched": "精确",
          "amount": 150.0,
          "unit": "克",
          "grams": 150.0,
          "cooking": "煎",
          "cooking_factor": 1.35,
          "cooking_oil_g": 7.7,
          "values": {
            "cal": 269.0,
            "protein": 36.0,
            "carb": 0.0,
            "fat": 13.7,
            "fiber": 0.0,
            "sugar": 0.0,
            "sodium": 75.0
          }
        }
      ],
      "totals": {
        "cal": 443.0,
        "protein": 39.9,
        "carb": 38.8,
        "fat": 14.1,
        "fiber": 0.4,
        "sugar": 0.0,
        "sodium": 76.8
      }
    }
  ],
  "exercise": [
    {
      "item": "慢跑",
      "min": 30.0,
      "cal": 300.0
    }
  ]
}
```

---

## 2. 导出时序大账本 (`data/exports/diet_history.csv`)

每次写操作（`add`、`weight`、`exercise` 等）均由 `sync_history_ledger()` 自动增量/全量同步至此 CSV 文件，供长期趋势分析、外部数据管道流转或闭环自适应回归：

| 列名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `date` | string | 记录日期 (`YYYY-MM-DD`) |
| `weight_kg` | float | 当日体重（未记录为空） |
| `cal` | float | 当日摄入总热量 (kcal) |
| `protein_g` | float | 蛋白质总量 (g) |
| `carb_g` | float | 碳水化合物总量 (g) |
| `fat_g` | float | 脂肪总量 (g) |
| `fiber_g` | float | 膳食纤维总量 (g) |
| `sugar_g` | float | 糖总量 (g) |
| `sodium_mg` | float | 钠总量 (mg) |
| `cooking_oil_g`| float | 烹饪吸附额外油脂总量 (g) |
| `exercise_cal` | float | 当日运动消耗总热量 (kcal) |
| `net_cal` | float | 净摄入热量 (`cal - exercise_cal`) |
| `meals_count` | int | 记录的餐次数目 |

---

## 3. 用户设置档案 (`data/settings.json`)

存储由 `profile_init` 生成的用户身体指标与 `vision config` 生成的多模态视觉配置：

```json
{
  "profile": [
    "男",
    70.0,
    175.0,
    30,
    "轻度",
    "减重"
  ],
  "vision": {
    "provider": "qwen",
    "api_key": "sk-...",
    "model": "qwen-vl-max"
  }
}
```

---

## 4. 自定义食物数据库 (`data/custom_foods.json`)

存储用户通过 `custom` 命令追加录入的食品成分数据：

```json
{
  "foods": [
    {
      "name": "高蛋白能量棒",
      "aliases": [],
      "category": "自定义",
      "cal": 350.0,
      "protein": 30.0,
      "carb": 30.0,
      "fat": 10.0,
      "fiber": 5.0,
      "sugar": 2.0,
      "sodium": 120.0,
      "serving": {
        "根": 60.0,
        "份": 60.0
      }
    }
  ]
}
```

---

## 5. CLI 指令签名汇总 (CLI Command Signatures)

`scripts/app.py` 暴露的无冗余确定性计算与存储接口：

| 命令 | 签名与参数 | 说明 |
| :--- | :--- | :--- |
| **饮食打卡** | `add [date] <food_text> [meal]` | 日期可选（默认今日），餐次可选（自动推断或默认根据时间） |
| **体重录入** | `weight [date] <kg>` | 记录当日空腹体重遥测值，触发闭环大账本更新 |
| **运动打卡** | `exercise [date] <item> <min> <cal>` | 记录运动项目与消耗能量 |
| **单日报表** | `day [date]` | 获取指定日期的摄入热量、宏量微量营养素及评分建议 |
| **多日汇总** | `summary <days>` | 获取最近 N 天的历史聚合与趋势数据 |
| **自适应校准**| `adaptive [--days N]` | 基于历史实际摄入与体重变化闭环校准真实 TDEE 与代谢漂移 |
| **全量导出** | `export` | 全量更新并输出 `data/exports/diet_history.csv` |
| **初始画像** | `profile_init <性别> <体重> <身高> <年龄> <活动量> <目标>` | 初始化或更新用户身体指标与默认目标 |
| **设置目标** | `goal_set <cal> <p> <c> <f> [fiber] [sugar] [sodium]` | 手动指定自定义营养素配额 |
| **录入自定义**| `custom <name> <cal> <p> <c> <f> [fiber] [sugar] [sodium]` | 录入个性化包装食品数据 |

