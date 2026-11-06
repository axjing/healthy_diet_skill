# 数据结构与持久化规范 (Data Schema Reference)

本文档归档于 `references/`，详细定义本技能产生与消费的各项数据文件格式。

---

## 1. 每日记录文件 (`data/records/<YYYY-MM-DD>.json`)

每日常规记录按日期独立建档，存储餐次明细与运动消耗：

```json
{
  "date": "2026-09-07",
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
          "values": {
            "cal": 269.0,
            "protein": 36.0,
            "carb": 0.0,
            "fat": 8.1,
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
        "fat": 8.5,
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

## 2. 用户设置档案 (`data/settings.json`)

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

## 3. 自定义食物数据库 (`data/custom_foods.json`)

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
