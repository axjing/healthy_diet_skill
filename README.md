# Healthy Diet - 饮食热量记录与营养分析

把自然语言饮食描述解析为结构化记录，自动核算热量与营养素，存入按日期分文件的本地 JSON 数据，并提供目标管理、统计分析、健康评估与数据导出。

## 功能概览

| 模块 | 说明 |
|------|------|
| **饮食记录** | 自然语言输入，自动解析食物名、数量、单位、烹饪方式 |
| **图片识别** | 多模态大模型（QwenVL/GLM-4V/GPT-4o）拍照识别，自动生成饮食描述 |
| **营养核算** | 数量 × 单位 → 克 → 查表 → 烹饪修正 → 输出 7 项营养素 |
| **目标管理** | Mifflin-St Jeor 公式算 BMR/TDEE，给出热量与三大宏量目标 |
| **统计分析** | 单日/区间汇总，含摄入、运动消耗、净热量 |
| **健康评估** | 百分制评分 + 问题项 + 针对性饮食建议 |
| **数据导出** | CSV / JSON，含运动消耗和净热量列 |
| **自定义食物** | 用户可添加库外食物，后续记录中直接使用 |

## 快速开始

```bash
# 1. 初始化用户档案（仅需一次）
python scripts/app.py profile_init 男 70 175 30 轻度 减重

# 2. 记录一餐
python scripts/app.py add 2026-09-07 "1碗米饭,150克鸡胸肉(煎),1个鸡蛋,清炒西兰花"

# 3. 查看当日分析
python scripts/app.py day 2026-09-07 --targets

# 4. 健康评估
python scripts/suggest.py 2026-09-07

# 5. 区间统计与导出
python scripts/app.py range 2026-09-01 2026-09-07
python scripts/app.py export 2026-09-01 2026-09-07 output.csv --format csv
```

## 图片识别（可选，需多模态大模型 API）

拍照即可记录一餐，openai Python 库调用多模态大模型自动识别食物并生成结构化描述，复用现有核算引擎：

```bash
# 0. 安装依赖（仅图片识别需要）
pip install openai

# 1. 配置服务商（仅一次）
python scripts/app.py vision list                                # 查看支持的服务商
python scripts/app.py vision config qwen sk-xxxxxxxx --model qwen-vl-max

# 2.a 拍照识别并直接记录
python scripts/app.py add 2026-09-07 --image lunch.jpg --meal 午餐

# 2.b 只识别看结果，不写入记录
python scripts/app.py analyze lunch.jpg
```

**支持的服务商**（OpenAI 兼容接口，多模型可切换）：

| provider | 服务 | 默认模型 | API Key 环境变量 |
|----------|------|---------|-------------------|
| `qwen` | 通义千问 QwenVL | `qwen-vl-max` | `DASHSCOPE_API_KEY` |
| `glm` | 智谱 GLM-4V | `glm-4v` | `ZHIPUAI_API_KEY` |
| `openai` | OpenAI GPT-4o | `gpt-4o` | `OPENAI_API_KEY` |

**Key 来源优先级**：`vision config` 显式配置 > 环境变量。还可执行：

```bash
python scripts/app.py analyze lunch.jpg --dry-run   # 预览将发送的请求体（不发请求）
python scripts/app.py analyze lunch.jpg --provider openai --model gpt-4o   # 临时切换
```

识别产出的描述（如 `1碗米饭，150克鸡胸肉(煎)`）会经过 `calc.parse_meal` 标准化——单位换算、烹饪修正、食物库匹配全链路复用，存储格式与手输完全一致。**未配置 API Key 时，纯文字记录功能不受影响，完全离线可用。**

## 命令参考

### 饮食记录

```bash
# 基本记录（日期 + 描述，逗号分隔多种食物）
python scripts/app.py add <日期> "<食物描述>"

# 指定餐次和补记时间
python scripts/app.py add 2026-09-06 "2个鸡蛋,1杯牛奶" --meal 早餐 --ts "2026-09-06 07:30:00"

# 只核算不保存
python scripts/app.py eval "150克鸡胸肉(煎),1碗米饭"
```

**餐次**：可选 早餐 / 午餐 / 晚餐 / 加餐。不指定则按时间自动归类（`--ts` 或当前时间）。

**食物描述语法**：
- 分隔符：逗号 `,`、中文逗号 `，`、分号 `;`、顿号 `、`、换行
- `2个鸡蛋` → 数量 2 × 单位 个（50g/个）
- `150克鸡胸肉(煎)` → 150g，烹饪系数 1.35
- `清炒西兰花` → 自动识别"清炒"烹饪方式
- 无数字默认 1，无单位按食物库中常见一份量

### 餐次管理

```bash
# 查看某日所有餐次（索引从 0 开始）
python scripts/app.py day 2026-09-07

# 修改餐次描述或餐次类别
python scripts/app.py edit <日期> <索引> --text "新描述" --meal 午餐

# 删除某餐
python scripts/app.py delete <日期> <索引>
```

### 运动记录

```bash
python scripts/app.py exercise 2026-09-07 跑步 30 300
#                              日期      项目   分钟  千卡
```

`day` 和 `range` 输出会自动包含 `exercise_cal`（运动消耗）和 `net_cal`（净摄入）。

### 目标管理

```bash
# 单次计算（不保存）
python scripts/app.py goals <性别> <体重kg> <身高cm> <年龄> <活动量> <目标>

# 初始化档案并保存（后续 day --targets 自动读取）
python scripts/app.py profile_init <性别> <体重kg> <身高cm> <年龄> <活动量> <目标>
```

**活动量**：久坐(1.2) / 轻度(1.375) / 中度(1.55) / 重度(1.725) / 极高(1.9)

**目标**：减重(-500) / 减脂(-400) / 维持(0) / 增肌(+300) / 增重(+400)

活动量支持别名：`不运动`→久坐，`每周运动1-3次`→轻度，`每周运动3-5次`→中度，等等。

### 统计与导出

```bash
# 区间统计（含运动消耗和净热量）
python scripts/app.py range <开始日期> <结束日期>

# 导出 CSV（含 date,cal,protein,carb,fat,fiber,sugar,sodium,exercise_cal,net_cal）
python scripts/app.py export <开始日期> <结束日期> <输出路径> --format csv

# 导出 JSON
python scripts/app.py export <开始日期> <结束日期> output.json --format json
```

### 健康评估

```bash
python scripts/suggest.py <日期>
```

输出包含：
- **健康评分**（百分制，扣分项）
- **问题项**（热量超标/不足、蛋白质偏低、碳水/脂肪/糖/钠偏高、膳食纤维不足）
- **针对性建议**（具体食物推荐）
- **运动净热量**（如有运动记录）

评估基于已保存的档案目标。未设置档案时，仅给出基于摄入量的通用建议。

### 自定义食物

```bash
python scripts/app.py custom <名称> <每100g千卡> \
    --protein <克> --carb <克> --fat <克> --sugar <克> --sodium <毫克>
```

自定义食物保存到 `data/custom_foods.json`，后续记录中直接使用名称即可匹配。

## 输出示例

```
【9月7日 星期四】早餐 · 午餐 · 晚餐
- 摄入 1,650 千卡 / 目标 1,767（剩 117）
- 蛋白 85g(64%)  碳水 180g(102%)  脂肪 48g(81%)
- 钠 1,860mg  糖 12g  膳食纤维 18g
- 运动消耗 300 千卡，净摄入 1,350 千卡
```

## 数据结构

```
data/
├── foods.json          # 内置食物库（~140 种常见食物，每 100g 营养值）
├── units.json          # 口语单位 → 克换算表 + 烹饪方式热量修正系数
├── settings.json       # 用户档案（profile_init 写入）
├── custom_foods.json   # 用户自定义食物（custom 命令写入）
└── records/
    └── 2026-09-07.json # 某日记录（meals 列表 + exercise 列表）
```

### 每日记录格式

```json
{
  "date": "2026-09-07",
  "meals": [
    {
      "ts": "2026-09-07 12:30:00",
      "meal": "午餐",
      "text": "1碗米饭,150克鸡胸肉(煎)",
      "items": [...],
      "totals": {"cal": 443, "protein": 52.5, ...}
    }
  ],
  "exercise": [
    {"item": "跑步", "min": 30, "cal": 300}
  ]
}
```

## 烹饪修正系数

食物入库时的营养值为食材原始数据，记录时根据烹饪方式自动调整：

| 烹饪方式 | 系数 | 适用说明 |
|---------|------|---------|
| 蒸/煮/炖/凉拌/白灼/清蒸/水煮 | 1.0 | 无额外油脂，基准值 |
| 清炒 | 1.1 | 少量油 |
| 爆炒/烧烤/烤/烟熏/火锅 | 1.2 | 中等油脂 |
| 红烧/干煎/油焖/糖醋/麻辣 | 1.35–1.4 | 较多油脂 |
| 干煸 | 1.5 | 高油脂 |
| 油炸/炸 | 1.7 | 油炸食品 |

**注意**：已完成菜品（菜肴/快餐/零食等类别）和烹饪词已内嵌在食物名中的（如"红烧排骨""烤红薯"）不再重复加成，避免虚高。

## 营养素说明

| 字段 | 说明 | 单位 |
|------|------|------|
| cal | 热量 | 千卡(kcal) |
| protein | 蛋白质 | 克(g) |
| carb | 碳水化合物 | 克(g) |
| fat | 脂肪 | 克(g) |
| fiber | 膳食纤维 | 克(g) |
| sugar | 糖（含天然糖与添加糖总量） | 克(g) |
| sodium | 钠 | 毫克(mg) |

## 环境要求

- **Python 3.10+**
- 核心功能（记录/统计/目标/评估）仅依赖标准库
- **图片识别（可选）**需安装 `pip install openai`
- Windows 下建议设置 `PYTHONIOENCODING=utf-8` 或脚本已内置 UTF-8 输出修复

## 项目结构

```
healthy_diet_skill/
├── SKILL.md            # 技能元数据与详细设计文档
├── README.md           # 本文件
├── .gitignore
├── scripts/
│   ├── app.py          # CLI 主入口，命令调度，数据 CRUD
│   ├── calc.py         # 核心解析引擎：自然语言 → 结构化食物记录
│   ├── goals.py        # BMR/TDEE 计算（Mifflin-St Jeor），宏量目标
│   ├── suggest.py      # 健康评估：评分 + 问题诊断 + 针对性建议
│   └── vision.py       # 多模态图片识别（可选）：QwenVL/GLM-4V/GPT-4o
└── data/
    ├── foods.json      # 内置食物营养数据库
    └── units.json      # 单位换算表 + 烹饪修正系数
```

## 设计决策

- **按日期分文件**：一个 `YYYY-MM-DD.json`，离线可用，易追溯，方便 grep
- **纯 JSON 存储**：无数据库依赖，任何编辑器/脚本可直接处理
- **自然语言解析优先**：最大兼容用户口语输入，而非强制结构化格式
- **烹饪修正后置**：食物库保持食材原始值，用户描述烹饪方式后才应用系数
- **成品菜不二次加成**：菜肴/快餐/零食等已含烹饪热量，与原始食材区分处理
