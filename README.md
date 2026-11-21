# Healthy Diet - 个人饮食营养记录与代谢管理 Agent Skill

[![Agent Skills Standard](https://img.shields.io/badge/Agent_Skills-agentskills.io-blue)](https://agentskills.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests: 35 Passed](https://img.shields.io/badge/Tests-35%20Passed-brightgreen)](tests/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero%20(Stdlib)-success)](scripts/)

专为 AI Agent 打造的确定性生理代谢与饮食健康管理 Agent Skill。将饮食输入（文字描述或多模态照片）转化为高精度结构化营养数据，按日期分文件原子持久化至本地 JSON，基于 Atwater 与 Delta Mass 物理能量质量守恒定律核算热量，并通过 Forbes 闭环自适应能量代谢回归提供量化生理遥测。

针对**增肌减脂普通人群**深度增强：原生内置补剂与健身轻食库、碳水循环与练休周期化目标、训练前后营养时机核验、单餐蛋白质脉冲（MPS）分布、高蛋白时代谢补水监控、多维体形成分（体脂率/腰围/去脂体重）追踪及平台期充碳日（Refeed Day）破局。

本技能遵循 [agentskills.io](https://agentskills.io) 开放标准构建。

---

## 核心功能矩阵

| 模块 | CLI 命令 | Python SDK 接口 | 说明 |
| :--- | :--- | :--- | :--- |
| **饮食记录** | `app.py record [--items '<JSON>'] [--meal 练前餐/练后餐]` | `app.record(...)` | 记录饮食，支持常用补剂与轻食（蛋白粉、肌酸、即食鸡胸、蛋清等） |
| **生理遥测** | `app.py telemetry [--workout/--rest]` | `app.telemetry(...)` | 获取单日能量、三大宏量缺口克数、单餐 MPS 亮氨酸脉冲与补水负荷 |
| **饮水记录** | `app.py water <ml>` | `app.water(...)` | 记录水分摄入，高蛋白时代谢负荷监测与缺口预警 |
| **体形遥测** | `app.py weight <kg> [--fat %] [--waist cm]` | `app.weight(...)` | 记录体重、体脂率、腰围与骨骼肌，自动解算去脂体重(LBM) |
| **运动打卡** | `app.py exercise <项目> <分> <卡>` | `app.exercise(...)` | 记录运动消耗，更新生理净热量 |
| **闭环校准** | `app.py adaptive [--days 30]` | `app.adaptive(...)` | 7天平滑体重(EWMA)回归真实 TDEE，平台期自动输出 Refeed 充碳方案 |
| **自愈注册** | `app.py custom <名> <卡> ...` | `app.custom(...)` | 注册库外冷门/自制食品，自愈本地知识图谱 |
| **身体档案** | `app.py profile_init ...` | `app.profile(...)` | 初始化用户身体生理基准与目标配额 |
| **时序导出** | `app.py export ...` | `app.history(...)` | 导出时间序列总账 (CSV/JSON) |

---

## 安装与智能体挂载 (Installation & Agent Setup)

本项目严格遵循 [agentskills.io](https://agentskills.io) 开放规范，支持通过 **npm / npx 智能体生态** 极简安装与挂载给各类 AI 智能体（Claude Code, Cursor, Antigravity, GitHub Copilot 等）。

### 1. 推荐：通过 `npx skills` 官方智能体包管理器安装 (Agent Skills Manager)
[skills CLI](https://github.com/vercel-labs/skills) 是目前 AI 智能体的事实标准包管理器。只需一行命令即可将本技能挂载到指定智能体或全局工作区：

```bash
# 方式 A：从 GitHub 仓库一键为当前项目添加本技能（智能体自动识别 .agents/skills/）
npx skills add axjing/healthy_diet_skill

# 方式 B：本地开发调试：在本项目根目录下直接挂载安装
npx skills add .

# 方式 C：全局安装给宿主所有智能体使用 (-g，跨项目全部生效)
npx skills add axjing/healthy_diet_skill -g

# 方式 D：指定特定智能体客户端挂载（如 Claude Code）
npx skills add axjing/healthy_diet_skill --agent claude-code
```

### 2. npm / npx 命令行工具执行与引入 (Node.js & npm Integration)
本项目已完整配置 `package.json` 与跨平台二进制引导器 `bin/healthy-diet.js`：

```bash
# 方式 A：免安装，直接通过 npx 运行饮食与遥测命令
npx healthy-diet-skill record "1碗米饭, 150克煎鸡胸肉"
npx healthy-diet-skill telemetry

# 方式 B：通过 npm 全局安装 CLI 工具
npm install -g healthy-diet-skill
healthy-diet telemetry

# 方式 C：作为项目本地开发依赖安装
npm install -D healthy-diet-skill
```

### 3. 主流智能体客户端目录一键挂载 (Manual / Git Clone)
若直接通过 Git 管理，可将本仓库克隆至各智能体框架的预设扩展路径：

| 智能体客户端 | 推荐安装路径 | 一键挂载命令 |
| :--- | :--- | :--- |
| **Claude Code** | `~/.claude/skills/healthy-diet` | `git clone https://github.com/axjing/healthy_diet_skill.git ~/.claude/skills/healthy-diet` |
| **Google Antigravity / Gemini CLI** | `~/.gemini/skills/healthy-diet` | `git clone https://github.com/axjing/healthy_diet_skill.git ~/.gemini/skills/healthy-diet` |
| **Cursor / Universal Agents** | `.agents/skills/healthy-diet` | `git clone https://github.com/axjing/healthy_diet_skill.git .agents/skills/healthy-diet` |

### 4. 运行前置环境
- **Node.js**: `>= 18.0.0`（仅使用 npm / npx 安装管理工具时需要）
- **Python**: `>= 3.10+`（底层物理计算与持久化引擎，**100% 仅使用标准库，无需 pip 安装任何外部依赖**）

---

## 快速开始

```bash
# 1. 初始化用户身体档案与目标
python scripts/app.py profile_init 男 70 175 30 轻度 减重

# 2. 记录一餐（首选结构化条目，免疫正则歧义）
python scripts/app.py record --items '[{"food": "米饭", "amount": 1.5, "unit": "碗"}, {"food": "鸡胸肉", "amount": 150, "unit": "克", "cooking": "煎"}]'

# 2.b 亦支持极简自然语言描述
python scripts/app.py record "1碗半米饭, 150克煎鸡胸肉, 清炒西兰花"

# 3. 记录晨起体重遥测
python scripts/app.py weight 70.2

# 4. 记录运动消耗
python scripts/app.py exercise 慢跑 30 300

# 5. 获取高密度量化遥测指标（专供 Agent 决策认知）
python scripts/app.py telemetry

# 6. 运行闭环能量代谢自适应回归校准
python scripts/app.py adaptive --days 30
```

### Python SDK 原生调用示例 (适合 CodeAct / Notebook 智能体)
```python
from scripts import app

# 结构化记录
res = app.record(items=[
    {"food": "米饭", "amount": 1, "unit": "碗"},
    {"food": "鸡胸肉", "amount": 150, "unit": "克", "cooking": "煎"}
], meal="午餐")

# 获取高密度生理遥测
telemetry = app.telemetry()
print(f"剩余热量预算: {telemetry['telemetry']['energy']['remaining_cal']} kcal")
print(f"蛋白质尚缺口: {telemetry['telemetry']['macros']['protein_g']['gap_g']} g")
```

---

## 物理守恒与营养学模型

1. **Atwater 与 Delta Mass 烹饪油脂吸附守恒**：
   $$\Delta E = E_{\text{base}} \times (\text{Factor} - 1.0)$$
   $$\Delta m_{\text{oil}} = \frac{\Delta E}{9.0\text{ kcal/g}}, \quad \text{Fat}_{\text{total}} = \text{Fat}_{\text{raw}} + \Delta m_{\text{oil}}$$
   系统在每条单品明细中输出确凿的 `cooking_oil_g`，原生蛋白质与纤维绝不虚假膨胀。
2. **Forbes 组织能量密度与闭环自适应 TDEE**：
   $$1\text{ kg 体重变化} \approx 7,700\text{ kcal}$$
   $$\text{TDEE}_{\text{empirical}} = \bar{E}_{\text{intake}} - \frac{(W_{\text{end}} - W_{\text{start}}) \times 7,700}{\Delta t}$$
3. **质量锚定蛋白质保护**：
   减脂期蛋白质按体重强制锚定 **$1.9\text{ g/kg}$**，守住去脂体重。

---

## 项目结构 (遵循 agentskills.io 规范)

```
healthy-diet/
├── SKILL.md            # Required: Agent 技能元数据 (YAML Frontmatter) 与执行指导
├── README.md           # 项目说明与快速开始指南
├── LICENSE             # MIT 开源许可证
├── .gitignore          # 忽略用户运行时数据 (records, settings, exports)
├── docs/               # 深度技术方案与架构文档
│   └── agent_skill_architecture_plan.md # 完整架构重构规范与全量字段量纲说明
├── scripts/            # 确定性工具引擎 (100% Python 标准库，零外部依赖)
│   ├── __init__.py     # 标准 Python 包声明
│   ├── app.py          # 主入口、CLI 调度、原子持久化与 Python SDK
│   ├── calc.py         # 物理计算引擎：结构化/口语解析、Delta Mass 模型
│   ├── goals.py        # BMR/TDEE 目标与 Forbes 闭环自适应代谢回归
│   └── suggest.py      # 双相状态机 (pacing/auditing) 与高密度遥测向量输出
├── references/         # 渐进式披露参考文档 (Progressive Disclosure)
│   ├── nutrition_science.md # 代谢生理学、蛋白质定额、烹饪修正系数表
│   └── schema.md       # JSON 数据结构规范与全量字段量纲定义
├── assets/             # 静态模板
│   └── record_template.json # 饮食记录数据模板
├── tests/              # 自动化测试套件
│   ├── test_calc.py    # 自然语言解析、结构化条目、Delta Mass 物理测试
│   ├── test_goals.py   # BMR/TDEE、代谢底线与 Forbes 闭环回归测试
│   ├── test_suggest.py # 遥测向量、双相状态机与扣分审计测试
│   └── test_app.py     # 数据持久化、Python SDK 与 CLI 逻辑集成测试
└── data/               # 基础营养知识图谱
    ├── foods.json      # 内置标准食物营养数据库
    └── units.json      # 单位换算表与烹饪修正系数
```

---

## 测试运行

系统自带完整的单元测试套件，毫秒级运行：

```bash
# 使用 pytest
pytest -v

# 或使用标准库 unittest（零安装运行）
python -m unittest discover tests -v
```

---

## 开源协议

本项目采用 [MIT License](LICENSE) 授权许可。
