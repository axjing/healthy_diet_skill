# Healthy Diet Agent Skill 架构设计与重构方案
> **基于 agentskills.io 规范的个人饮食营养、物理能量守恒与闭环代谢管理外骨骼**

---

## 1. 项目愿景与设计哲学 (Vision & First Principles)

### 1.1 核心定位
本项目的核心定位是**专为 AI Agent（如 Claude, Gemini, GPT, Antigravity 等）打造的确定性生理代谢与饮食健康管理 Agent Skill**，严格对齐 [agentskills.io](https://agentskills.io) 开放标准。

它不是一个需要终端用户在 Bash 命令行里敲指令的传统单机 Python 工具，更不是一个脱离 Agent 运行的独立 GUI 软件。**它的唯一第一类公民用户是 AI Agent**。

### 1.2 第一性原理分工原则 (Division of Labor)
在人机共生与 Agentic 架构下，传统软件与大模型的边界必须严格依循第一性原理重新划定：

* **大模型擅长什么？（交给 Agent）**
  1. **多模态物理感知**：直接观察分析用户拍摄的食物、餐盘、外卖照片，辨识食材种类与分量。
  2. **复杂语义理解**：处理中国广大地域千奇百怪的自然语言、方言、倒装、排除修饰（“不要葱花”、“少放油”）及模糊口语（“两小口米饭”、“大半碗粥”）。
  3. **开放世界自愈补偿**：当食物库缺失冷门或自制菜肴时，利用百亿参数世界常识估算宏量营养素并自动注册。
  4. **情境化共情与动态指导**：结合用户作息、心理感受、运动安排，将冰冷的数字转化为有温度的个性化私人营养师建议。

* **大模型弱项是什么？（交给 Skill 确定性引擎）**
  1. **数学与物理守恒计算**：杜绝大模型数字幻觉，严格遵循 Atwater 能量质量守恒定律（$4P + 4C + 9F = \text{Cal}$）与 Delta Mass 油脂吸附物理模型。
  2. **磁盘原子持久化与数据主权**：按日期分文件存储本地纯 JSON，维护时间序列 CSV 大账本，确保数据本地可控、隐私绝对安全。
  3. **非线性与闭环统计拟合**：Forbes 组织能量密度模型与真实摄入/体重遥测的时序回归校准（Closed-Loop Adaptive TDEE）。
  4. **纯粹的高密度量化遥测**：为 Agent 提供无偏、精确的摄入数值、预算缺口、失衡等级向量。

### 1.3 核心工程指标
* **零外部依赖 (Zero Dependencies)**：100% 基于 Python 3.10+ 标准库，彻底移除第三方 SDK（如 `openai`），杜绝因外部依赖安装或版本冲突导致技能失效。
* **零外部配置 (Zero Setup)**：无需配置任何第三方视觉 API Key； Agent 自身直接通过多模态视网膜感知图像。
* **绝对可移植性 (Machine-Agnostic)**：代码库严禁任何机器盘符或绝对路径；支持通过 `HEALTHY_DIET_DATA_DIR` 环境变量实现代码与数据存储目录物理隔离。
* **毫秒级执行响应**：所有运算本地完成，平均响应耗时 $< 10\text{ms}$，单日分析与持久化 $< 50\text{ms}$。

---

## 2. 整体架构与数据流拓扑 (Architecture Topology)

```
                            ┌───────────────────────────────────┐
                            │            用户输入通道           │
                            │  • 自然语言描述 (文字/语音转写)   │
                            │  • 餐食随手拍照片 (多模态图片)    │
                            │  • 体重/运动打卡与代谢状态咨询    │
                            └─────────────────┬─────────────────┘
                                              │
                                              ▼
                            ┌───────────────────────────────────┐
                            │    宿主 AI Agent (大脑与感知端)   │
                            │  • 原生多模态视觉：感知提取食材   │
                            │  • 语义解析消歧：提取结构化条目   │
                            │  • 开放世界自愈：估算并注册生僻菜 │
                            │  • 认知决策：合成个性化指导建议   │
                            └─────────┬───────────────▲─────────┘
                                      │ Tool Calling  │ Telemetry
                                      ▼               │ Vector
┌─────────────────────────────────────────────────────┴─────────────────────────────────────────┐
│                    healthy_diet_skill 确定性物理与数据引擎 (外骨骼)                           │
│                    (100% Python 标准库 / 零第三方依赖 / 跨平台即开即用)                       │
├──────────────────────────┬────────────────────────────┬───────────────────────────────────────┤
│    物理守恒计算引擎      │      原子持久化与大账本    │        闭环生理与偏差遥测引擎         │
│     (scripts/calc.py)    │      (scripts/app.py)      │     (scripts/goals.py & suggest.py)   │
│                          │                            │                                       │
│  • Agent 结构化协议优先  │  • 按日建档 records/*.json │  • 双时态状态机 (pacing / auditing)   │
│  • Delta Mass 吸油物理量 │  • 全量大账本 diet_history │  • 纯净数值量化遥测 (Telemetry Vector)│
│  • 生熟水合状态密度折算  │  • PID 独立临时文件原子写  │  • Forbes 闭环自适应能量回归校准      │
│  • 口语自然语言降级后备  │  • 环境变量支持数据隔离    │  • 质量锚定保肌蛋白质底线 (1.9 g/kg)  │
└──────────────────────────┴────────────────────────────┴───────────────────────────────────────┘
```

---

## 3. 详细接口规范与数据契约 (Interface & Data Contracts)

为了适配各类 Agent 框架（无论是基于命令行 Bash 执行的 ReAct 智能体，还是直接运行 Python 代码的 CodeAct/Notebook 智能体，或是 MCP Tool Server 封装），系统提供**CLI 命令行**与 **Python Native SDK** 双重通道。

### 3.1 核心工具接口清单

| 工具命令 | 参数规范 | 功能与设计原则 |
| :--- | :--- | :--- |
| **`record`** | `[date] [text] [--items '<JSON>'] [--meal <餐次>]` | 记录饮食。**推荐传入 `--items` 结构化条目**；亦可直接传口语文本。日期缺省为今日。 |
| **`telemetry`**| `[date]` | 获取当天量化遥测向量（热量/三大宏量缺口/油盐/雷达评分）。日期缺省为今日。 |
| **`weight`** | `[date] <kg>` | 记录晨起体重遥测，触发自动更新时序大账本。日期缺省为今日。 |
| **`exercise`**| `[date] <项目> <分钟> <千卡>` | 记录运动消耗，更新净热量。日期可缺省为今日。 |
| **`adaptive`**| `[--days N]` | 基于历史摄入与体重时序，闭环回归校准真实 TDEE 与代谢漂移。 |
| **`custom`**  | `<name> <cal> --protein ... --carb ... --fat ...` | 开放世界冷门食品自愈注册（Agent 世界常识沉淀到本地）。 |
| **`profile`** | `<性别> <体重> <身高> <年龄> <活动量> <目标>` | 初始化或更新用户生理基准与推荐目标配额。 |
| **`history`** | `[--start S] [--end E] [--format csv\|json]` | 查询区间历史明细或导出时序总账。 |

---

### 3.2 结构化调用协议 (Agent Tool-Call Protocol)

#### 3.2.1 记录饮食 (`record`)
Agent 优先调用结构化条目，消除正则误判风险：

* **CLI 模式调用示例**：
  ```bash
  python scripts/app.py record --items '[{"food": "米饭", "amount": 1.5, "unit": "碗"}, {"food": "鸡胸肉", "amount": 150, "unit": "克", "cooking": "煎"}]'
  ```
* **Python SDK 模式调用示例**：
  ```python
  from scripts import app
  res = app.record(items=[
      {"food": "米饭", "amount": 1.5, "unit": "碗"},
      {"food": "鸡胸肉", "amount": 150, "unit": "克", "cooking": "煎"}
  ], meal="午餐")
  ```
* **返回格式**：
  ```json
  {
    "ok": true,
    "meal": "午餐",
    "text": "1.5碗米饭, 150克鸡胸肉(煎)",
    "totals": {
      "cal": 530.0,
      "protein": 41.9,
      "carb": 58.3,
      "fat": 14.4,
      "fiber": 0.7,
      "sugar": 0.0,
      "sodium": 77.7
    },
    "items": [
      {
        "food": "米饭",
        "grams": 225.0,
        "values": { "cal": 261.0, "protein": 5.9, "carb": 58.3, "fat": 0.7, "fiber": 0.7, "sugar": 0.0, "sodium": 2.7 }
      },
      {
        "food": "鸡胸肉",
        "grams": 150.0,
        "cooking": "煎",
        "cooking_factor": 1.35,
        "cooking_oil_g": 7.7,
        "values": { "cal": 269.0, "protein": 36.0, "carb": 0.0, "fat": 13.7, "fiber": 0.0, "sugar": 0.0, "sodium": 75.0 }
      }
    ]
  }
  ```

##### `record` 返回字段与单位对照表
| 字段路径 | 数据类型 | 物理单位 | 含义与业务说明 |
| :--- | :---: | :---: | :--- |
| `ok` | boolean | 无 | 执行与写盘状态 |
| `meal` | string | 无 | 餐次分类（`早餐` / `午餐` / `晚餐` / `加餐`） |
| `text` | string | 无 | 本餐可读文本摘要 |
| `totals.cal` | float | **千卡 (kcal)** | 本餐摄入总热量 |
| `totals.protein` | float | **克 (g)** | 本餐蛋白质总量 |
| `totals.carb` | float | **克 (g)** | 本餐碳水化合物总量 |
| `totals.fat` | float | **克 (g)** | 本餐脂肪总量（含烹调油） |
| `totals.fiber` | float | **克 (g)** | 本餐膳食纤维总量 |
| `totals.sugar` | float | **克 (g)** | 本餐糖总量（天然糖 + 添加糖） |
| `totals.sodium` | float | **毫克 (mg)** | 本餐钠离子总量 |
| `items[].food` | string | 无 | 匹配的标准食物名称 |
| `items[].grams` | float | **克 (g)** | 换算后的食物可食部净重量 |
| `items[].cooking` | string | 无 | 烹饪方式（无则为 null） |
| `items[].cooking_factor` | float | **无量纲比率** | 烹饪热量缩放倍率 (1.0 ~ 1.7) |
| `items[].cooking_oil_g` | float | **克 (g)** | Delta Mass 吸附烹饪净油脂量 |
| `items[].values.*` | float | 与 totals 相同 | 该食材单项贡献的各项营养素数值 |


---

#### 3.2.2 高密度生理遥测 (`telemetry`)
`telemetry` 是 Agent 认知决策的核心输入源。它合并了单日累计、目标配额对比与健康诊断，摒弃死板的长篇文本，输出**纯净的生理指标偏差向量**：

* **CLI 模式调用示例**：
  ```bash
  python scripts/app.py telemetry
  ```
* **返回格式 (高密度遥测向量)**：
  ```json
  {
    "date": "2026-11-20",
    "phase": "pacing",
    "score": 88,
    "grade": "Pacing",
    "telemetry": {
      "energy": {
        "consumed_cal": 1250.0,
        "target_cal": 1800.0,
        "remaining_cal": 550.0,
        "delta_cal": -550.0,
        "pct": 69.4,
        "exercise_cal": 300.0,
        "net_cal": 950.0,
        "safety_floor": 1500.0
      },
      "macros": {
        "protein_g": { "actual": 60.0, "target": 110.0, "gap_g": 50.0, "pct": 54.5 },
        "carb_g": { "actual": 160.0, "target": 220.0, "pct": 72.7 },
        "fat_g": { "actual": 38.0, "target": 60.0, "pct": 63.3 }
      },
      "quality": {
        "fiber_g": 14.5,
        "fiber_gap_g": 10.5,
        "cooking_oil_g": 18.2,
        "sugar_g": 12.0,
        "excess_sugar": false,
        "sodium_mg": 1850.0,
        "excess_sodium": false
      }
    },
    "issues": [
      "蛋白质达标进度滞后 (缺口 50g)"
    ],
    "hints": [
      "日内预算尚余 550 kcal，下一餐应重点补充高生物利用度瘦肉/蛋奶/豆制品约 50g 蛋白。"
    ]
  }
  ```

##### `telemetry` 返回字段与单位对照表
| 字段路径 | 数据类型 | 物理单位 | 含义与业务说明 |
| :--- | :---: | :---: | :--- |
| `date` | string | 无 | 目标日期 (`YYYY-MM-DD`) |
| `phase` | string | 无 | 状态阶段：`pacing` (日内巡航) / `auditing` (全天结算) |
| `score` | int | **分 (0~100)** | 综合健康评分 |
| `grade` | string | 无 | 综合评级 (`S` / `A` / `B` / `C` / `D` / `Pacing`) |
| `telemetry.energy.consumed_cal` | float | **千卡 (kcal)** | 当天累计实际摄入能量 |
| `telemetry.energy.target_cal` | float | **千卡 (kcal)** | 当天推荐摄入能量目标 |
| `telemetry.energy.remaining_cal`| float | **千卡 (kcal)** | 当天剩余可用热量配额预算 |
| `telemetry.energy.delta_cal` | float | **千卡 (kcal)** | 能量净偏差 (`consumed - target`) |
| `telemetry.energy.pct` | float | **百分比 (%)** | 全天热量目标消耗进度比率 |
| `telemetry.energy.exercise_cal` | float | **千卡 (kcal)** | 当天运动消耗能量 |
| `telemetry.energy.net_cal` | float | **千卡 (kcal)** | 净能量负荷 (`consumed - exercise`) |
| `telemetry.energy.safety_floor` | float | **千卡 (kcal)** | 代谢安全底线（男 1500，女 1200） |
| `telemetry.macros.protein_g.actual` | float | **克 (g)** | 实际蛋白质摄入量 |
| `telemetry.macros.protein_g.target` | float | **克 (g)** | 目标蛋白质定额（减脂期 $1.9\text{ g/kg}$） |
| `telemetry.macros.protein_g.gap_g` | float | **克 (g)** | **蛋白质达标绝对缺口** |
| `telemetry.macros.protein_g.pct` | float | **百分比 (%)** | 蛋白质达标率 |
| `telemetry.macros.carb_g.actual` | float | **克 (g)** | 实际碳水化合物摄入量 |
| `telemetry.macros.carb_g.target` | float | **克 (g)** | 目标碳水化合物定额 |
| `telemetry.macros.carb_g.pct` | float | **百分比 (%)** | 碳水化合物达标率 |
| `telemetry.macros.fat_g.actual` | float | **克 (g)** | 实际脂肪摄入量 |
| `telemetry.macros.fat_g.target` | float | **克 (g)** | 目标脂肪定额 |
| `telemetry.macros.fat_g.pct` | float | **百分比 (%)** | 脂肪达标率 |
| `telemetry.quality.fiber_g` | float | **克 (g)** | 实际膳食纤维摄入量 |
| `telemetry.quality.fiber_gap_g` | float | **克 (g)** | 膳食纤维距离推荐 $25\text{g}$ 的缺口 |
| `telemetry.quality.cooking_oil_g`| float | **克 (g)** | **烹饪累计吸附外源植物油量** |
| `telemetry.quality.sugar_g` | float | **克 (g)** | 累计总糖摄入量 |
| `telemetry.quality.excess_sugar`| boolean | 无 | 糖分超标标志位 ($> 50\text{g}$) |
| `telemetry.quality.sodium_mg` | float | **毫克 (mg)** | 累计钠离子摄入量 |
| `telemetry.quality.excess_sodium`| boolean| 无 | 钠摄入超标标志位 ($> 2000\text{mg}$) |
| `issues[]` | string | 无 | 诊断出的生理失衡标签列表 |
| `hints[]` | string | 无 | 面向 Agent 的规划微提示列表 |

---

#### 3.2.3 闭环自适应能量代谢校准 (`adaptive`)
解决传统开环公式未考虑非运动消耗（NEAT）下调、代谢适应与肠道吸收个体差的问题：

* **CLI 模式调用示例**：
  ```bash
  python scripts/app.py adaptive --days 30
  ```
* **返回格式**：
  ```json
  {
    "status": "calibrated",
    "window_days": 30,
    "valid_days_count": 28,
    "weight_start_kg": 72.5,
    "weight_end_kg": 71.0,
    "weight_delta_kg": -1.5,
    "mean_daily_intake_cal": 1720.0,
    "empirical_tdee": 2085.0,
    "prior_tdee": 2200.0,
    "metabolic_adaptation_cal": -115.0,
    "recommended_cut_target": 1585.0,
    "protein_floor_g": 134.9
  }
  ```

##### `adaptive` 返回字段与单位对照表
| 字段路径 | 数据类型 | 物理单位 | 含义与业务说明 |
| :--- | :---: | :---: | :--- |
| `status` | string | 无 | 校准状态：`calibrated` (校准成功) / `insufficient_data` (数据天数不足) |
| `window_days` | int | **天 (days)** | 回溯统计分析时间窗口长度 |
| `valid_days_count` | int | **天 (days)** | 窗口期内有饮食记录的有效天数 |
| `weight_start_kg` | float | **千克 (kg)** | 窗口期初的体重锚点 |
| `weight_end_kg` | float | **千克 (kg)** | 窗口期末的最新体重数值 |
| `weight_delta_kg` | float | **千克 (kg)** | 净体重变化量 (`weight_end - weight_start`) |
| `mean_daily_intake_cal` | float | **千卡/天 (kcal/day)** | 窗口期内每日平均真实摄入能量 |
| `empirical_tdee` | float | **千卡/天 (kcal/day)** | **经验推导的实际每日总能量消耗 (TDEE)** |
| `prior_tdee` | float | **千卡/天 (kcal/day)** | 1990 年静态公式预估的理论先验 TDEE |
| `metabolic_adaptation_cal`| float | **千卡/天 (kcal/day)** | **代谢适应漂移量** (`empirical - prior`) |
| `recommended_cut_target` | float | **千卡/天 (kcal/day)** | 基于真实代谢重算的推荐减脂热量目标 |
| `protein_floor_g` | float | **克/天 (g/day)** | 质量锚定保肌蛋白质绝对底线 ($1.9\text{ g/kg}$) |

---

## 4. 营养生理学与热力学物理守恒模型 (Biophysical Science)

### 4.1 Delta Mass 烹饪油脂增量物理模型
拒绝传统软件无依据地随意缩放脂肪与热量，杜绝破坏 Atwater 能量质量守恒定律：
$$\Delta E = E_{\text{base}} \times (\text{Factor} - 1.0)$$

1. **经典油脂烹调（煎/炒/炸/干煸/油焖等）**：
   额外热量 $\Delta E$ 严格且 $100\%$ 由食材吸附的烹调油提供：
   $$\Delta m_{\text{oil}} = \frac{\Delta E}{9.0\text{ kcal/g}}, \quad \text{Fat}_{\text{total}} = \text{Fat}_{\text{raw}} + \Delta m_{\text{oil}}$$
   系统在每条明细中输出确凿的 `cooking_oil_g`，让隐形油脂暴露无遗。
2. **微量营养素守恒**：
   食材原有的蛋白质、膳食纤维与钠含量不随烹调油脂虚假膨胀。

### 4.2 Forbes & Hall 动态能量守恒闭环
人体去脂/脂肪混合组织的能量密度常数约为：
$$1\text{ kg 体重变化} \approx 7,700\text{ kcal}$$
基于连续或离散时间序列大账本，实际每日能量消耗（TDEE）定义为：
$$\text{TDEE}_{\text{empirical}} = \bar{E}_{\text{intake}} - \frac{(W_{\text{end}} - W_{\text{start}}) \times 7,700}{\Delta t}$$

### 4.3 质量锚定蛋白质保护模型 (Mass-Anchored Protein Allocation)
杜绝低热量减重时按百分比计算蛋白质导致肌肉严重萎缩：
- **减重 / 减脂期**：强制锚定 **$1.9\text{ g/kg}$**，最大化肌肉蛋白合成（MPS）与饱腹感。
- **增肌期**：锚定 **$1.8\text{ g/kg}$**。
- **维持期**：锚定 **$1.4\text{ g/kg}$**。

---

## 5. 三层食物解析与自愈式图谱 (Three-Tier Food Resolution)

为了实现用户无感知的日常饮食记录，建立三层食物解析机制：

```
用户输入 (文字 / 图像识别)
         │
         ▼
[第 1 层：内置高频营养库 (data/foods.json)] ──(命中)──> 确定性计算
         │ (未命中)
         ▼
[第 2 层：用户历史自定义库 (data/custom_foods.json)] ──(命中)──> 确定性计算
         │ (未命中)
         ▼
[第 3 层：Agent 开放世界常识推理与自愈补偿]
  • Agent 结合烹饪常识估算营养素与热量
  • 自动调用 custom 固化到第 2 层
  • 继续执行确定性计算，向用户提示 [AI估算]，永不断链
```

---

## 6. 时序大账本与数据主权 (Persistence & Data Sovereignty)

1. **单日明细归档**：`data/records/<YYYY-MM-DD>.json`。
   - 包含每日独立餐次明细、时间戳、食物克数、净烹饪油量及运动消耗。
   - 每次写盘使用独立进程临时文件原子化重命名（Atomic Replace），彻底免疫并发损坏。
2. **终生时序总账镜像**：`data/exports/diet_history.csv`。
   - 任何增删改均自动触发 `sync_history_ledger()` 增量全量刷新。
   - 用户可随时使用 Excel、Pandas 或苹果 Numbers 打开分析，实现终身数据完全归属用户。
3. **环境隔离支持**：
   - 支持通过环境变量 `HEALTHY_DIET_DATA_DIR` 指定任意外部数据存储路径，方便在只读容器、多租户 Agent 隔离沙箱中运行。

---

## 7. 典型端到端交互场景演练 (End-to-End Walkthrough)

### 场景 A：日常自然语言模糊打卡
* **用户**：“中午在外面吃了碗牛肉面，加了份煎蛋，汤挺油的”
* **Agent 内部工作流**：
  1. 语义识别：提取食物 `牛肉面 1碗`、`鸡蛋 1个 (烹饪: 煎)`。
  2. 工具调用：`python scripts/app.py record --items '[{"food":"牛肉面","amount":1,"unit":"碗"},{"food":"鸡蛋","amount":1,"unit":"个","cooking":"煎"}]'`
  3. 脚本计算：牛肉面 540 kcal，煎蛋吸油 3.8g / 115 kcal，总计 655 kcal。
  4. Agent 回复：“已为您记下【午餐】：牛肉面1碗 + 煎蛋1个，合计 655 千卡（蛋白 28g、碳水 62g、脂肪 32g，含吸附煎烹油约 3.8g）。今天热量还在预算内！”

### 场景 B：拍照打卡（多模态直读）
* **用户**：发送一张工作餐照片（餐盘里有一荤两素一碗饭）
* **Agent 内部工作流**：
  1. 视觉感知：Agent 视网膜直读图片，识别出：白米饭约大半碗（150g）、清蒸鲈鱼约4片（120g）、清炒菜心一份（150g）。
  2. 工具调用：`python scripts/app.py record --items '[{"food":"米饭","amount":1,"unit":"碗"},{"food":"鲈鱼","amount":120,"unit":"克","cooking":"清蒸"},{"food":"菜心","amount":150,"unit":"克","cooking":"清炒"}]'`
  3. Agent 回复：“看照片这是一顿非常健康的减脂午餐！已为您入库：米饭1碗、清蒸鲈鱼120g、清炒菜心150g，共计 365 千卡，优质蛋白 26g，搭配十分优秀。”

### 场景 C：自愈式冷门菜肴录入
* **用户**：“下午加餐吃了两块我妈自制的黑芝麻核桃糕”
* **Agent 内部工作流**：
  1. 本地库查验无果。
  2. Agent 凭借营养学常识估算：坚果类糕点每 100g 约 480 kcal，蛋白 12g，脂肪 32g，碳水 35g，两块约 50g。
  3. 工具调用 1：`python scripts/app.py custom "黑芝麻核桃糕" 480 --protein 12 --fat 32 --carb 35`
  4. 工具调用 2：`python scripts/app.py record --items '[{"food":"黑芝麻核桃糕","amount":50,"unit":"克"}]' --meal 加餐`
  5. Agent 回复：“已为您录入并永久建档自制【黑芝麻核桃糕】（约50克，240千卡，优质不饱和脂肪16g）。下次吃直接告诉我即可！”

### 场景 D：日内巡航与下餐前瞻建议
* **用户**：“下午五点了，今天还剩多少热量？晚上吃什么好？”
* **Agent 内部工作流**：
  1. 工具调用：`python scripts/app.py telemetry`
  2. 脚本返回：`phase: "pacing"`, 今日已摄入 1150 kcal，目标 1750 kcal（余 600 kcal）；全天蛋白已摄入 52g / 目标 110g（缺口高达 58g）；纤维还差 14g。
  3. Agent 动态个性化回复：“你今天热量控制得很棒，晚餐还有 600 千卡充裕预算！但目前蛋白质缺口较大（还差 58g）。今晚强烈建议安排一次‘高蛋白大餐’：推荐 250g 香煎或清蒸鸡胸肉/龙利鱼（补充约 45g 蛋白），搭配一大盘蒜蓉西兰花补充纤维，主食来半根玉米即可，既饱腹又稳稳达标！”

### 场景 E：长期闭环代谢诊断
* **用户**：“我严格按照 1600 大卡吃了一个月，为什么最近两周体重完全不下降？”
* **Agent 内部工作流**：
  1. 工具调用：`python scripts/app.py adaptive --days 30`
  2. 脚本回归分析：前两周体重下降 1.2kg，近两周体重平台；计算出的经验实际 TDEE 为 1750 kcal（低于公式预估的 2050 kcal，产生了约 300 kcal 的代谢适应性下调与 NEAT 减少）。
  3. Agent 科学解答：“根据您过去 30 天的大账本与体重曲线分析，您身体发生了典型的‘自适应生热（Metabolic Adaptation）’，同时可能日常非运动活动（NEAT）自发减少了。建议未来 3 天安排一次高碳水‘放纵日/破动日’（Refeed Day）把热量拉回维持线重置瘦素水平，下周增加每天 2000 步轻快走，不需要盲目把热量压得更低。”

---

## 8. 重构实施与验证计划 (Action Plan)

| 步骤 | 执行模块 | 任务描述 | 验证标准 |
| :---: | :--- | :--- | :--- |
| **1** | **依赖瘦身** | 删除 `scripts/vision.py` 与 `tests/test_vision.py`，移除 `openai` 外部库依赖 | 技能核心仅依赖标准库，零安装步骤 |
| **2** | **双模计算** | 更新 `scripts/calc.py` 原生支持结构化列表/字典解析，保持 Delta Mass 油脂模型 | 结构化条目与口语均能正确计算 |
| **3** | **统一接口** | 更新 `scripts/app.py` 支持 `record`、`--items`、`telemetry` 子命令与 Python SDK 暴露 | 单条命令搞定记录与高密度遥测 |
| **4** | **纯数值遥测** | 更新 `scripts/suggest.py` 构建 `telemetry` 字典（能量/宏量/微量/偏差向量） | 输出纯净高密度 JSON，无冗余死板文本 |
| **5** | **技能指导重构** | 重写 `SKILL.md`，对齐 agentskills.io 规范，明确 Agent 认知与调用工作流 | Agent 能自主调配工具链并生成专业回复 |
| **6** | **全套测试** | 编写新增条目、遥测向量与边缘用例的自动化测试 | `pytest -v` 100% 毫秒级全绿 |
