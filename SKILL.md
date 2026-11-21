---
name: healthy-diet
description: 个人饮食营养记录、热量核算、代谢监测与闭环健康管理的 Agent Skill。当用户描述饮食（口语文字或拍照发图打卡）、记录体重/运动、询问热量预算/营养达标情况、寻求个性化饮食建议、或进行长期闭环代谢调控时使用。
license: MIT
compatibility: Python 3.10+ (100% 标准库，零外部依赖)
metadata:
  version: "2.0.0"
  specification: "agentskills.io"
  category: "lifestyle-and-health"
---

# 饮食健康管理技能 (Healthy Diet)

将用户的饮食输入转化为高精度结构化营养数据，按日期分文件原子持久化至本地 JSON，基于物理能量守恒定律核算热量与宏量营养素，并通过闭环生理遥测提供个性化代谢指导。遵循 [Agent Skills 规范](https://agentskills.io)。

## 渐进式参考文档 (Progressive References)

为保持本指令上下文精简，深度理论、模式定义与架构设计独立存放，按需查阅：
- [完整架构与重构设计方案](docs/agent_skill_architecture_plan.md)：系统第一性原理、架构拓扑、全字段量纲定义与端到端演练。
- [营养与代谢生理学参考](references/nutrition_science.md)：Mifflin-St Jeor 公式、Forbes 闭环代谢自适应模型、质量锚定蛋白质定额、Delta Mass 油脂物理守恒模型。
- [数据结构与持久化规范](references/schema.md)：每日记录 `records/`、时序总账 `diet_history.csv`、用户档案 `settings.json` 与自定义食物 `custom_foods.json` 的 JSON Schema。
- [记录模板定义](assets/record_template.json)：标准饮食记录基础模板。

---

## 核心分工原则 (Brain vs. Exoskeleton)

| 模块 | 宿主 AI Agent (大脑与感知端) | healthy_diet_skill 引擎 (确定性外骨骼) |
| :--- | :--- | :--- |
| **视觉感知** | 用户发食物图片，Agent 多模态视网膜直读分解食材与分量 | 不引入外部视觉 API，避免冗余网络中间层 |
| **自然语言** | 负责口语、方言、倒装、模糊词与否定排除消歧，提取结构化条目 | 提供结构化 `--items` 优先解析，辅以确定性查表换算 |
| **物理核算** | 不心算、不瞎猜热量 | Atwater 能量质量守恒 ($4P+4C+9F$) 与 Delta Mass 油脂吸附 |
| **数据持久化**| 发起 Tool Calling | 按日期本地 JSON 原子写盘，自动同步 `diet_history.csv` |
| **健康教练** | 结合用户作息、喜好与情绪，生成有温度的个性化指导 | 提供纯数值量化生理遥测向量（`telemetry`）、缺口与评分 |
| **开放世界** | 库内无食物时，Agent 用世界常识估算并调用 `custom` 注册 | 固化为本地确定性数据，下次直接可查，自愈永不断链 |

---

## 快速调用指南 (Quick Start)

所有命令日期默认均为**今日**，时间默认当前时间：

```bash
# 1. 初始化用户身体档案与目标（仅首次或身体指标变化时使用）
python scripts/app.py profile_init 男 70 175 30 轻度 减重

# 2. 记录一餐：推荐结构化输入（100% 免疫正则歧义）
python scripts/app.py record --items '[{"food": "米饭", "amount": 1.5, "unit": "碗"}, {"food": "鸡胸肉", "amount": 150, "unit": "克", "cooking": "煎"}]'

# 2.b 记录一餐：亦支持口语自然语言极简输入
python scripts/app.py record "1碗半米饭, 150克煎鸡胸肉, 清炒西兰花"

# 3. 记录晨起体重（开启闭环能量代谢自适应遥测）
python scripts/app.py weight 70.2

# 4. 记录运动消耗
python scripts/app.py exercise 慢跑 30 300

# 5. 获取高密度生理遥测指标（日内巡航 pacing 或全天结转 auditing）
python scripts/app.py telemetry

# 6. 长期闭环自适应能量代谢校准（基于真实进食大账本与体重遥测反推真实 TDEE）
python scripts/app.py adaptive --days 30

# 7. 开放世界自愈：注册库外/自制食品（每100g营养素）
python scripts/app.py custom "自制黑芝麻糕" 450 --protein 12 --fat 28 --carb 38
```

同时支持 Python 原生 SDK 导入直接调用（适合 CodeAct 智能体）：
```python
from scripts import app
res = app.record(items=[{"food": "米饭", "amount": 1, "unit": "碗"}])
status = app.telemetry()
```

---

## 典型 Agent 交互与工作流规范

### 1. 饮食打卡场景 (文字或多模态照片)
1. **用户口语输入**（如“中午吃了一碗半米饭，煎鸡胸肉大概150克，清炒西兰花”）：
   - Agent 识别食材，组装为结构化条目：
     `[{"food": "米饭", "amount": 1.5, "unit": "碗"}, {"food": "鸡胸肉", "amount": 150, "unit": "克", "cooking": "煎"}, {"food": "西兰花", "amount": 150, "unit": "克", "cooking": "清炒"}]`
   - Agent 执行调用：`python scripts/app.py record --items '<JSON>'`
2. **用户发送餐食照片**：
   - Agent 自身眼睛直接观察图片，辨识出包含的食物、粗估分量与烹饪方式。
   - 组装为结构化条目后调用 `record`。
3. **输出给用户的反馈**：
   - 用清晰的中文向用户汇报：餐次、包含食物、热量、三大宏量、净吸油量（`cooking_oil_g`）。

### 2. 开放世界自愈机制 (Self-Healing Fallback)
- 当用户吃冷门、外卖特色菜或自制食品时，若调用 `record` 发现 `unrecognized` 列表不为空：
  1. Agent **不要直接报错放弃**，而是调用自身的营养常识推断该食物每 100g 的合理能量、蛋白、碳水与脂肪。
  2. Agent 执行 `python scripts/app.py custom "<名称>" <千卡> --protein ... --carb ... --fat ...` 固化沉淀。
  3. 再次执行 `record` 入库，并向用户提示 `[AI估算]`。

### 3. 日内配速与晚间建议场景
- 用户询问“今天还剩多少热量？”、“晚餐吃什么？”时：
  1. 执行 `python scripts/app.py telemetry`。
  2. 观察返回的 `telemetry.energy.remaining_cal`（剩余热量）、`telemetry.macros.protein_g.gap_g`（蛋白质缺口克数）与 `quality.fiber_gap_g`（纤维缺口）。
  3. **Agent 自行组织有温度的回答**，例如：“你今天还剩 550 kcal 预算，但全天蛋白质还差 45g。今晚建议安排一块掌心大小的香煎龙利鱼（约200g），再来一大盘白灼西兰花补充纤维……”

### 4. 代谢诊断与闭环校准场景
- 当用户记录体重满 14~30 天，或困惑“吃得很少为什么体重不掉”时：
  1. 执行 `python scripts/app.py adaptive --days 30`。
  2. 读取真实 `empirical_tdee` 与静态 `prior_tdee` 的差异（`metabolic_adaptation_cal`）。
  3. 解释代谢适应、NEAT 变化，给出科学的破动日（Refeed Day）或热量微调建议。

---

## 物理模型守恒说明

1. **Delta Mass 油脂守恒模型**：
   烹饪增加的热量 $\Delta E$ 严格 $100\%$ 源自吸附的烹调油（$\Delta m_{\text{oil}} = \Delta E / 9.0\text{ g}$），透明披露 `cooking_oil_g`，原生蛋白质与纤维绝不虚假膨胀。
2. **生熟水合状态校准**：
   熟化主食（如“燕麦粥”、“米饭”）与干燥生料（如“燕麦片”、“生大米”）严格区分，绝不产生热量翻倍的荒谬计算。
3. **质量锚定蛋白质保护**：
   减脂期蛋白质按体重强制锚定 **$1.9\text{ g/kg}$**，守住去脂体重。

---

## 数据主权与持久化

- **单日明细**：`data/records/<YYYY-MM-DD>.json`（原子替换写入，防并发坏盘）。
- **终生大账本**：`data/exports/diet_history.csv`（自动同步追加，随时可用 Excel/Pandas 分析）。
- **数据路径隔离**：支持环境变量 `HEALTHY_DIET_DATA_DIR` 指定任意持久化路径。
- **运行环境**：100% Python 3.10+ 标准库，零安装依赖，开箱即用。
