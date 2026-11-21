# 数据结构与持久化规范 (Data Schema Reference)

本文档归档于 `references/`，详细定义本技能产生与消费的各项数据文件格式。

---

## 1. 每日记录文件 (`data/records/<YYYY-MM-DD>.json`)

每日常规记录按日期独立建档，存储餐次明细、运动消耗、补水记录与多维体形成分遥测：

```json
{
  "date": "2026-09-07",
  "weight": 70.2,
  "body_fat_pct": 16.5,
  "waist_cm": 81.5,
  "muscle_kg": 34.8,
  "lbm_kg": 58.6,
  "fat_mass_kg": 11.6,
  "water_ml": 2200,
  "units": {
    "cal": "kcal",
    "protein": "g",
    "carb": "g",
    "fat": "g",
    "fiber": "g",
    "sugar": "g",
    "sodium": "mg",
    "grams": "g",
    "weight": "kg",
    "body_fat_pct": "%",
    "waist_cm": "cm",
    "muscle_kg": "kg",
    "lbm_kg": "kg",
    "fat_mass_kg": "kg",
    "water": "ml",
    "exercise_cal": "kcal",
    "net_cal": "kcal",
    "duration": "min"
  },
  "meals": [
    {
      "ts": "2026-09-07 16:30:00",
      "meal": "练前餐",
      "text": "1根香蕉,1杯黑咖啡",
      "summary": "热量 95.0 kcal | 蛋白质 1.3g | 脂肪 0.2g | 碳水 24.7g | 钠 1.0mg",
      "items": [...]
    },
    {
      "ts": "2026-09-07 18:30:00",
      "meal": "练后餐",
      "text": "1勺蛋白粉,1盒即食鸡胸肉",
      "summary": "热量 235.0 kcal | 蛋白质 48.0g | 脂肪 3.0g | 碳水 3.5g | 钠 428.0mg",
      "items": [...]
    }
  ],
  "exercise": [
    {
      "item": "力量训练",
      "min": 60.0,
      "cal": 300.0
    }
  ]
}
```

---

## 2. 导出时序大账本 (`data/exports/diet_history.csv`)

每次写操作（`add`、`weight`、`water`、`exercise` 等）均由 `sync_history_ledger()` 自动增量/全量同步至此 CSV 文件，供长期趋势分析、外部数据管道流转或闭环自适应回归：

| 列名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `date` | string | 记录日期 (`YYYY-MM-DD`) |
| `weight_kg` | float | 当日体重（未记录为空） |
| `body_fat_pct` | float | 体脂百分比 (%) |
| `waist_cm` | float | 晨起空腹腰围 (cm) |
| `muscle_kg` | float | 骨骼肌肉量 (kg) |
| `water_ml` | int | 当日累计饮水量 (ml) |
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

存储由 `profile_init` 生成的用户身体指标与偏好配置：

```json
{
  "profile": [
    "男",
    70.0,
    175.0,
    30,
    "中度",
    "减重"
  ]
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
| **饮食打卡** | `record [date] <food_text> [--meal 餐次] [--items JSON]` | 支持结构化 JSON 或自然语言，餐次支持早餐/午餐/晚餐/加餐/练前餐/练后餐 |
| **体重录入** | `weight <kg> [--fat %] [--waist cm] [--muscle kg] [--date YYYY-MM-DD]` | 记录晨起体重与体形成分，自动解算去脂体重(LBM)与脂肪量 |
| **饮水记录** | `water <ml> [--date YYYY-MM-DD] [--set]` | 记录饮水量（默认累加，--set 覆盖），高蛋白代谢负荷预警 |
| **运动打卡** | `exercise [date] <item> <min> <cal>` | 记录运动项目与消耗能量，更新生理净热量 |
| **单日报表** | `day [date] [--workout / --rest]` | 查看单日摄入、运动消耗、补水与多维体态，支持训练日/休息日周期化切换 |
| **生理遥测** | `telemetry [date] [--workout / --rest]` | 输出高密度生理遥测向量（含 MPS 脉冲分布、补水负荷、缺口克数）供 Agent 决策 |
| **多日汇总** | `range <start> <end>` | 获取指定日期区间的摄入大盘、平均值与运动覆盖率 |
| **自适应校准**| `adaptive [--days N]` | 基于历史大账本与体重回归真实 TDEE，平台期自动输出 Refeed 充碳日方案 |
| **全量导出** | `export <start> <end> <out_path> [--format csv/json]` | 导出指定时间范围的详尽大账本 |
| **初始画像** | `profile_init <性别> <体重> <身高> <年龄> <活动量> <目标>` | 初始化或更新用户身体生理基准与默认目标 |
| **录入自定义**| `custom <name> <cal> <p> <c> <f> [fiber] [sugar] [sodium]` | 录入个性化包装食品数据 |

