# 小小推理家 · 儿童逻辑推理训练软件

一个面向儿童的**逻辑推理题生成、验证、分级与自适应训练平台**。

它不是一个"题目 JSON + 随机抽题器"，而是按下面的流水线组织的（对齐专家意见）：

> 题目内容层 → 逻辑模型层 → 自动验证层 → 难度评估层 → 题库层 → 出题策略层 → 儿童交互层

核心原则：

1. **文字只是表现层，Logic DSL 表达式才是核心。** 每句话、每个选项、每条约束都有一个可计算的逻辑表达式。
2. **Solver 是裁判。** 题目生成后不能相信生成器；必须穷举所有状态、检查约束、确认解的数量。只有唯一解（或答案被唯一确定）的题才能入库。
3. **程序负责证明，人/模板负责创造。**

---

## 快速开始

```bash
# 安装依赖（核心引擎零第三方依赖；Flask 用于 Web，pytest 用于测试）
pip install -r requirements.txt

# 1) 载入人工种子题 + 生成一批题目
python cli.py seed
python cli.py generate 60 --seed 42

# 2) 校验题库（应当全部通过）
python cli.py validate

# 3) 查看题库统计
python cli.py stats

# 4) 命令行答题演示（自适应出题）
python cli.py play --child 小明 --rounds 5

# 5) 启动 Web 界面
python app.py --port 5000
# 打开 http://127.0.0.1:5000
```

运行测试：

```bash
python -m pytest tests/ -q
```

> 测试的数据目录由 `tests/conftest.py` 重定向到临时目录，运行测试
> **不会触碰** `data/` 下的真实题库与儿童档案（曾有过测试清空真实题库的教训）。

---

## 目录结构

```text
reasoning/
├── app.py                     # Web 启动入口
├── cli.py                     # 命令行：seed/generate/validate/stats/play
├── requirements.txt
├── logic_kids/
│   ├── models.py              # 统一 Question Schema（JSON 可序列化）
│   ├── config.py              # 数据目录配置
│   ├── logic/
│   │   ├── dsl.py             # Logic DSL 词法 + 递归下降解析 → AST
│   │   ├── ast.py             # AST 节点 + 求值器
│   │   └── solver.py          # Solver：布尔枚举 2^n + 排列枚举 n!，求全部解
│   ├── validator/validator.py # Question Validator（题目质量检查）
│   ├── difficulty/engine.py   # 难度评分引擎（0~10 → ★）
│   ├── questions/
│   │   ├── themes.py          # 主题词库（角色/物品/场景）
│   │   ├── generator.py       # 统一生成器（模板→验证→难度→入库）
│   │   └── templates/         # 5 个题型模板
│   │       ├── truth.py       # 真假话
│   │       ├── ordering.py    # 顺序排列
│   │       ├── conditional.py # 条件推理
│   │       ├── set_logic.py   # 集合关系
│   │       └── exclusion.py   # 排除推理
│   ├── bank/
│   │   ├── store.py           # 题库存储（JSON 文件 + 索引）
│   │   └── seed.py            # 人工种子题（含经典"四只老鼠"）
│   ├── engine/adaptive.py     # 自适应出题（薄弱技能→70/20/10 难度→选题）
│   └── progress/store.py      # SQLite：儿童档案 + 答题历史 + 掌握度
├── web/
│   ├── app.py                 # Flask 路由（只给表现层，判题在服务端）
│   ├── templates/             # index.html / profile.html
│   └── static/                # style.css / app.js / profile.js
├── data/                      # 运行时生成：questions/*.json + bank_index.json + profiles.db
└── tests/
```

---

## 统一数据模型

每道题是一个 `Question`（见 `logic_kids/models.py`）：

| 字段 | 说明 |
|------|------|
| `story` | 标题 + 场景文字 + 角色代号→显示名 |
| `entities` | 实体代号（A/B/C…） |
| `variables` | 变量（`boolean` 或 `rank`） |
| `statements` | 陈述句（text + logic + speaker）——真假话题 |
| `constraints` | 约束/事实（text + logic） |
| `options` / `option_logic` | 选项文字 + 对应的逻辑表达式 |
| `answer` | 正确选项下标 |
| `hints` / `explanation` | 逐步提示 + 儿童友好解释 |
| `difficulty` / `difficulty_score` | 星级 + 连续难度分 |

例（真假话）：`statements[].logic = "NOT_ALL(cheese)"`，`constraints[].logic = "TRUTH_COUNT == 1"`。

## Logic DSL

支持的表达式（`logic_kids/logic/dsl.py`）：

- 布尔运算：`&&` `||` `!` `( )`，常量 `TRUE`/`FALSE`
- 量词：`ALL(prop)` 所有、`SOME(prop)` 有些、`NONE(prop)` 没有、
  `NOT_ALL(prop)` 不是所有（`SOME_NOT` 是它的旧别名，语义相同）
- 计数：`COUNT(prop)`、`EXACTLY(k, e1, e2, …)`
- 排列比较：`RANK(A) < RANK(B)`、`RANK(A) == 1`、支持链式 `RANK(A)<RANK(B)<RANK(C)`
- 约束：`TRUTH_COUNT == k`（真假话）、`ORDER(A, B, C)`（全序）

量词按变量名后缀展开：`ALL(cheese)` 覆盖所有以 `_cheese` 结尾的布尔变量。

**量词语义约定（避免儿童语言歧义）**："有些人没有" 在中文里容易被理解成"至少一个有且至少一个没有"，
因此——
- "不是所有都有"（含"谁都没有"这种情况）→ `NOT_ALL(prop)`
- "有些人有，有些人没有"（至少要有一个有）→ `SOME(prop) && NOT_ALL(prop)`
- 模板与种子题全部按此约定书写（专家审查 P1）。

## Solver 与 Validator

- `solver.solve()` 枚举全部状态（布尔 2^n，排列 n!），过滤约束后返回所有解。
  **状态空间有上限保护**：布尔变量 ≤ 12、排列变量 ≤ 8，超限直接抛
  `QuestionError`（专家审查 P1，防止生成器/Web 被拖死）。
- `validator.validate()` 检查：
  1. 选项 ≥2 且互不重复；
  2. 有解；
  3. 正确选项唯一（恰好一个选项被所有解蕴含）；
  4. 存储答案与逻辑一致；
  5. 干扰项合理（每个错误选项至少在某个状态下能成立）；
  6. 陈述句不能恒真/恒假（要有推理价值）。

只有 `report.ok` 的题才会入库。**种子题也不例外**：`seed.validated_seeds()`
先过 Validator 再入库（seed → validate → difficulty → save），Web 启动与 CLI
`seed` 共用这一入口，任何路径都不能绕过检查（专家审查 P0）。

## 题型语义一致性

**顺序排列题的关系类型与题干必须配套**（专家审查 P0）：
- 排队场景 → 故事"排成一列"，问"谁排在第 X 位？"
- 身高场景 → 故事"比身高"，问"谁是第 X 高？"
- 比赛场景 → 故事"跑步比赛"，问"谁获得第 X 名？"

三种场景各有配套的故事、提问、解释与提示用词（`templates/ordering.py` 的
`SCENARIOS`），生成结果由 `tests/test_templates.py::test_ordering_story_prompt_semantics_match`
逐题抽查，杜绝"比身高却问排第几位"这类语义错位。

## 难度评分

`difficulty/engine.py`：

```
score = 0.45*变量数 + 0.35*条件数 + 0.7*嵌套深度 + 0.75*推理链长
      + 0.15*干扰项 + 0.2*解空间log10 + 0.8*真假话约束 - 2.4
```

映射：`0~2 ★ / 2~4 ★★ / 4~6 ★★★ / 6~8 ★★★★ / 8~10 ★★★★★`。

## 自适应出题

`engine/adaptive.py`：

1. 选薄弱技能：未练过的题型优先（探索），否则掌握度最低的；
2. 定难度：掌握度→当前水平，再按 **70% 当前 / 20% 简单 / 10% 挑战** 抖动；
3. 从题库选符合题型+难度的题，避开最近做过的。

## Web 安全设计

前端只拿表现层（故事、陈述、选项文字、提示数），**绝不返回** `answer`/`option_logic`/`solution`；判题在服务端 `POST /api/answer` 完成。见 `tests/test_web.py::test_next_question_no_leak`。

服务端还做如下校验（专家审查 P1）：

- **身份绑定**：`/api/next` 校验儿童存在后写入 session，`/api/answer` 只认 session
  里的儿童（忽略请求体中的 `child_id`，防伪造换人）；SQLite 开启
  `PRAGMA foreign_keys = ON` 防孤儿记录。
- **参数校验**：`choice` 必须是整数且在选项范围内、`question_id` 必须匹配
  `^[A-Za-z0-9_-]+$`（防路径穿越）、`child_id` 必须是存在的正整数，否则返回 400/404。
- **判题安全**：判题逻辑在服务端，前端只拿到 `correct / correct_index / correct_text / explanation`。

---

## 专家审查修复记录

| 优先级 | 问题 | 修复 |
|---|---|---|
| P0 | ordering 的"身高/跑步"与"排队位置"语义冲突 | 三种场景各有配套题干（见上节） |
| P0 | Web 启动载入 seed 绕过 Validator | `seed.validated_seeds()` 统一先验证再入库 |
| P0 | 种子题存在多解 | 换唯一解变体，并把原题（64 解）固定为回归测试 |
| P1 | `SOME_NOT` 与儿童语言"有些没有"歧义 | 改名 `NOT_ALL`；"有些人有，有些人没有" 用 `SOME && NOT_ALL` |
| P1 | `/api/answer` 不校验 choice 类型/范围 | 服务端严格校验，非法返回 400 |
| P1 | `child_id` 可伪造 / 孤儿记录 | session 身份绑定 + FK 强制 |
| P1 | 题目 id 路径穿越 | 白名单正则校验 |
| P1 | Solver 状态空间无上限 | 布尔 ≤12、排列 ≤8，超限抛错 |

---

## 后续可扩展

- 题型：配对问题、多条件排序、多人真假话（专家题型表 ⑦~⑩）
- 题库采集层：爬虫 → 结构化 → Logic DSL → Solver 验证（Solver 仍是裁判）
- 自动变体：同一模板换主题词后重新 Solver 验证（已具备基础）
- 能力画像的更细粒度建模（IRT / 知识追踪）
