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

# 4b) 固定难度等级答题（1=简单 2=普通 3=困难 4=挑战）
python cli.py play --child 小明 --rounds 5 --level 3

# 5) 启动 Web 界面
python app.py --port 5000
# 打开 http://127.0.0.1:5000

# 6) 导入外部题库（Phase 3：先进待审队列，审核后才进正式题库）
python cli.py import bigbench --task logical_deduction/three_objects --limit 20
python cli.py review                          # 查看待审队列
python cli.py review --approve <题目id>        # 审核通过后移入正式题库
python cli.py import logiqa --task dev --limit 10  # 非商业许可，需谨慎

# 7) 批量导入平台（PR1）
python cli.py import-all config/datasets.yaml            # 按配置批量导入
python cli.py import-all config/datasets.yaml --dry-run  # 只统计不入库
python cli.py import-all config/datasets.yaml --retry --checkpoint
python cli.py import stats          # 批处理统计（RAW/VALID/REJECT/REVIEW/READY）
python cli.py bank check-license    # 许可证合规检查
python cli.py analyze-bank          # 题库质量分析（能力空缺/难度/层级/许可证）
python cli.py import reasoning_gym --task knights_knaves --limit 15  # 程序化生成
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
│   ├── difficulty/engine.py   # 难度评分引擎（结构化指标，0~10）
│   ├── difficulty/levels.py   # 难度分 → 用户等级（1~4）映射（唯一出处）
│   ├── taxonomy.py            # V2：10 大能力分类 + 技能标签 + 年龄分级
│   ├── license_policy.py      # 许可证策略（config/license_policy.yaml）
│   ├── child_suitability.py   # 儿童适配层（6 维评分 + suitable 结论）
│   ├── dedup.py               # 三层去重（ID / 文本 Hash / 逻辑结构 Hash）
│   ├── questions/
│   │   ├── themes.py          # 主题词库（角色/物品/场景）
│   │   ├── generator.py       # 统一生成器（模板→验证→难度→入库）
│   │   ├── selector.py        # QuestionSelector：按用户等级/题型/避重复选题
│   │   └── templates/         # 6 个题型模板
│   │       ├── truth.py       # 真假话
│   │       ├── ordering.py    # 顺序排列
│   │       ├── conditional.py # 条件推理
│   │       ├── set_logic.py   # 集合关系
│   │       ├── exclusion.py   # 排除推理
│   │       ├── matching.py    # 配对推理（一一对应/排除）
│   │       └── color_pattern.py  # 颜色规律（模式与规律）
│   ├── bank/
│   │   ├── store.py           # 题库存储（JSON 文件 + 索引）
│   │   ├── seed.py            # 人工种子题（含经典"四只老鼠"）
│   │   ├── importer.py        # 外部题导入管线（四道闸门 + 审核入库）
│   │   ├── normalizer.py      # 外部题统一中间模型（不强行转 DSL）
│   │   ├── provenance.py      # 题目溯源 + 待审队列（data/imports/）
│   │   ├── external.py        # 外部题库独立存储（data/external/<来源>/，按来源分目录）
│   │   ├── import_job.py      # 批量导入：配置/dry-run/账本/retry/checkpoint
│   │   └── sources/           # 外部题库源适配器
│   │       ├── bigbench.py    # BIG-bench logical_deduction（Apache-2.0，含规则翻译器）
│   │       ├── logiqa.py      # LogiQA2.0（CC BY-NC-SA，非商业；支持官方中文版 *_zh.txt）
│   │       └── reasoning_gym.py # Reasoning Gym（Apache-2.0，程序化生成，儿童任务白名单）
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
  | `difficulty` / `difficulty_score` | 内部星级 + 连续难度分（0..10） |
  | `difficulty_level` | 用户可见等级 1~4（`difficulty/levels.py` 映射） |
  | `source_info` | 来源与许可证：type/name/license/dataset_id/original_id/url |
  | `provenance` | 导入溯源：imported_at/modified/translator/review_status |

  例（真假话）：`statements[].logic = "NOT_ALL(cheese)"`，`constraints[].logic = "TRUTH_COUNT == 1"`。

  内置题（种子 + 生成）自动标记 `source_info = {type: builtin, name: children_reasoning,
  license: MIT}`；外部题由导入管线写入完整的来源与许可证信息。

## 外部题库导入（Phase 3）

**外部题与内置题库完全分开存储、分开管理**：

```text
data/
├── questions/ + bank_index.json   # 内置题库（种子题 + 生成题）
├── external/<来源slug>/            # 外部题库（审核通过后按来源分目录）
│   ├── <qid>.json
│   └── index.json                 # 该来源的索引
└── imports/<来源>/                 # 待审队列（审核前）
```

外部题绝不直接进内置题库（专家意见第十一节）：先写入 `data/imports/` 待审队列，
审核通过才移入 `data/external/<来源>/`。管线：

  ```text
  外部数据集 → ① Schema Validation → ② Logic Validation（Solver）
            → ③ Unique Solution → ④ Difficulty Calibration → 待审队列 → 审核 → 正式题库
  ```

  已接入两个数据源（专家意见第六、七节选型）：

  | 数据源 | 许可证 | 说明 |
  |---|---|---|
  | BIG-bench `logical_deduction` | Apache-2.0（可商用） | 规则翻译器把排序句转成 DSL（`RANK(X)<RANK(Y)`），可走 Solver 四道闸门；翻译不了自动跳过并计数 |
| LogiQA2.0 | CC BY-NC-SA 4.0（**非商业**） | 自然语言逻辑推理选择题，**不强行转 DSL**；支持官方中文版（`--lang zh`），人工抽检后可用 `review --approve --force` 放行（保留未验证标记） |

  关键规则：

  - **能转 DSL 的题自动审核**：`review --approve` 会复验 Solver/Validator（唯一解）；
    未通过逻辑验证的题（自然语言题）默认拒绝，人工抽检认可后加 `--force` 放行
    （`logic_validated=False` 标记会一直保留，方便追溯）。
- **难度一律由本引擎重算**：`engine.apply()`（外部数据集自带的难度标签不被信任）；
  无 DSL 的题用结构启发式兜底并标记 `difficulty_calibrated=False`。
  - **许可证随题记录**：`source_info.license` 与 `provenance.translator` 让每道题
    都可追溯到"从哪里来、改过什么、谁转换的"。
  - 导入的题目目前保留原始英文题干/选项（等待中文改写），因此只应经过人工审核后
    再进入儿童可用的正式题库。

### 批量导入平台（PR1）

`import_job.py` 把"一次导一个来源"升级成**批处理平台**：

- **ImportConfig**：`config/datasets.yaml` 声明多个来源/任务/数量/是否自动审核；
- **dry-run**：`--dry-run` 只跑扫描→转换→验证，不写任何队列/题库；
- **账本**：`data/import_stats.json` 累计每个来源的 RAW/VALID/REJECT/REVIEW/READY，
  `cli.py import stats` 输出表格（含内置库与已有外部库）；
- **retry / checkpoint**：`--retry` 只重跑上次失败的来源；`--checkpoint` 跳过已入库
  或已在待审队列的题目，支持断点续导；
- **三层去重**（`dedup.py`）：ID（source+original_id）、文本 SHA256、逻辑结构 Hash
  （默认只统计不删除，`--dedup-logic` 可开启硬删除）；
- **儿童适配层**（`child_suitability.py`）：6 维评分（阅读水平/语言复杂度/抽象度/
  推理深度/计算量/文化依赖）+ `suitable` 结论，未翻译英文题会直接判"不适合"；
- **质量分级**：`quality = A/B/C/rejected`（A=已验证+儿童语言审核、B=逻辑正确但
  机器翻译、C=仅外部答案人工抽检），`translations.zh.status` 记录
  machine/reviewed/child_adapted；
- **许可证硬过滤**（`license_policy.py`）：`bank check-license` 输出
  Production-safe / Non-commercial / Unknown 三类统计。

### 综合训练模式

题库选择新增 **🧠 综合训练**（专家意见第二十二节）：按能力权重
（演绎 25% / 排序 15% / 模式 15% / 关系 10% / 数学 10% / 空间 10% / 其余 15%）
从**内置 + 外部混合**选题，儿童不再面对"内置/外部二选一"。

### 固定数据源版本

BIG-bench 已于 2026-04-17 归档为只读：`sources/bigbench.py` 固定到归档 commit
`092b196c`（可用环境变量 `BIGBENCH_REF` 覆盖），不"永远拉最新"。

### 题库质量分析器（V2.5）

`python cli.py analyze-bank` 输出题库的能力 / 难度 / 层级 / 许可证分布，并给出
**能力空缺警告**（如"空间推理题不足""演绎逻辑占比过高""高难度题不足"），
告诉下一步该引入什么数据集，而不是凭感觉。

三层题库（专家意见第二节）：

| 层级 | 质量 | 用途 |
|---|---|---|
| production | A 级（已验证 + 儿童语言审核） | 儿童正常训练 |
| experimental | B 级（逻辑正确但机器翻译） | 开发者测试 |
| raw | C 级 / 待审队列 | 永不直接给儿童 |

### Reasoning Gym（程序化题库源，PR2）

Reasoning Gym 是 Apache-2.0 的程序化推理任务框架（可生成、可验证、可调难度）。
适配器只开放 **11 个儿童任务白名单**，覆盖不同能力：

```text
knights_knaves / syllogism    → 演绎逻辑
family_relationships          → 关系推理
leg_counting / letter_counting / rectangle_count / chain_sum / time_intervals → 数学/计数
number_sequence               → 模式与规律
arc_1d                        → 模式/图形抽象
maze                          → 空间推理
```

答案由 reasoning-gym 自带算法验证器保证；题目为英文自然语言、无法转 DSL，
默认进入待审队列（raw/experimental 层级），`review --approve --force`
人工抽检后放行。中文版由 `zh_translate_question` 机器翻译生成（按任务模板：
数列/算式/动物计数/时长/迷宫/图形规律/三段论/真假人/亲属关系等），
`python cli.py external translate reasoning_gym` 可批量补翻译。
儿童化改写由 `zh_child_question` 生成（`translations.zh_child`，
status=child_adapted）：用元数据重建儿童语言题面（"小蚂蚁走迷宫"、
"小动物排队找规律"），Web 中文版优先展示儿童版；改写后质量升级为 B
（逻辑正确 + 儿童语言已审核）。原 machine 版本保留在 `translations.zh`。
依赖：`pip install -r requirements.txt`（含 reasoning-gym）。

### 图形化渲染

迷宫、ARC 格子、长方形计数等**图形题**不再只显示纯文本：
`logic_kids/visuals.py` 用 Pillow 按需渲染成 PNG，
`/api/question/<qid>/visual` 提供图片，前端有图形时自动展示图片并隐藏纯文本题干。
支持：maze（墙/通道/起点 S/终点 G 着色）、arc_1d（ARC 色板 + 训练例子→测试输入）、
rectangle_count（ASCII 图形着色）。

### 界面与选择

Web 流程：选择儿童 → **选择题库**（🧩 内置题库 / 🌐 外部题库）→
选外部来源（BIG-bench / LogiQA…，显示各来源题数与许可证）→
**选题目语言**（中文版 / English 原文）→ 选难度 → 答题。
选外部题库后只出该来源的题；`/api/next` 支持 `bank: builtin|external`、
`source` 与 `lang: zh|en` 参数，判题/提示接口对内置题与外部题都生效。

外部题的中文版由规则翻译器生成（`bank/sources/bigbench.py` 的
`zh_translate_question`），存放在题目 JSON 的 `translations.zh` 字段里，
原题保留不动。已入库的题可用 `python cli.py external translate` 批量补翻译。

  常用命令：

  ```bash
  python cli.py import bigbench --task logical_deduction/three_objects --limit 20
  python cli.py review                          # 列出待审队列
  python cli.py review --approve ext_bigbench_logical_deduction_three_objects_0
  python cli.py review --approve-all --force    # 人工抽检后批量放行（含无 DSL 题）
  python cli.py review --reject <题目id>
  python cli.py external list                   # 列出外部题库来源
  python cli.py external stats                  # 外部题库统计（可按来源）
  python cli.py external translate              # 给外部题批量生成中文版
  ```

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

## 难度评分与用户等级

`difficulty/engine.py`：

```
score = 0.45*变量数 + 0.35*条件数 + 0.7*嵌套深度 + 0.75*推理链长
      + 0.15*干扰项 + 0.2*解空间log10 + 0.8*真假话约束
      + 0.18*否定数 + 0.1*合取数 + 0.05*最小推理步数 - 2.4
```

引擎同时输出结构化指标 `engine.metrics()`：
`entity_count / constraint_count / chain_length / negation_count /
conjunction_count / quantifier_complexity / solution_space /
minimum_reasoning_steps`（专家意见第四节；其中"最小推理步数"目前是
结构代理启发式，后续可替换为真实的证明搜索度量）。

**连续分 → 用户可见等级** 只在 `difficulty/levels.py` 定义（专家意见第二节：
难度等级与难度评分必须分离，分界线调整不影响生成器）：

```
difficulty_score:  0.00~2.49   2.50~4.99   5.00~7.49   7.50~10.0
difficulty_level:       1           2           3           4
UI 显示:           🌱 简单      ⭐ 普通      🚀 困难      🧠 挑战
```

星级（1~5 ★）保留为内部粗分带，仅供自适应引擎等内部逻辑使用；儿童界面只显示等级。

### V2：二维难度

除总分外，每题还有 `difficulty_profile`（1..5 五维，专家意见第十六节）：

```text
cognitive_load      认知负荷（实体/条件/嵌套）
reasoning_depth     推理深度（链长/真假话假设/否定转换）
language_complexity 语言负担（文本长度；外部未翻译英文 +1）
distractor_strength 干扰强度（选项数等）
computation_load    计算负担（数学类更高）
```

两个总分相同的问题对儿童的"困难点"可能完全不同（逻辑难语言简单 vs 语言难逻辑简单），
五维拆解是以后"难度选择真正有意义"的基础。题型校准（如颜色规律题结构分数系统性
高估时）在 `engine._TYPE_ADJUST` 里集中维护。

## V2：能力分类体系（taxonomy.py）

所有题目（内置生成 + 外部导入）都标注三样东西：

```text
category    能力大类：classification/pattern/deduction/ordering/relation/
                    spatial/math/science/language/strategy
skills[]    技能标签：如 deduction、negation、transitive_reasoning、pattern_recognition…
age_range   年龄分级：A=5-7岁 / B=7-9岁 / C=9-11岁 / D=11-13岁
```

- 内置题型 → 能力映射集中在 `taxonomy.TYPE_DEFAULTS`；
- 外部适配器在归一化时打标签（BIG-bench → ordering；LogiQA → deduction）；
- 年龄分级由难度等级 + 题型/来源推断（直观类能力如 pattern/relation 封顶 C）。

儿童能力画像页（`/profile`）现在按"能力维度"（🧠）和"各题型"（📊）两层展示，
答题记录落库时写入 `category`，为后续个性化训练打基础。

## QuestionSelector（用户选择难度）

`questions/selector.py`（专家意见第三节）：

```
用户选择 level=3
        ↓
select_question(difficulty=3, child_id, category)
        ↓
difficulty_score ∈ [5.0, 7.49]
        ↓
从题库选题（等级不足时向相邻等级放宽，reason 明确说明）
```

Web 流程：选择儿童 → 选择难度（4 级）→ 答题 → 下一题保持同一难度；
点击"换难度"可随时返回选择页。`POST /api/next` 接受 `level`（1~4）与
可选 `category`（题型）；不传 `level` 时仍走自适应出题。

## 自适应出题

`engine/adaptive.py`：

1. 选薄弱技能：未练过的题型优先（探索），否则掌握度最低的；
2. 定难度：掌握度→当前水平，再按 **70% 当前 / 20% 简单 / 10% 挑战** 抖动；
3. 从题库选符合题型+难度的题，避开最近做过的。

## 答题记录

`attempts` 表除对错外，还记录 `time_ms`（解题用时）与 `difficulty_score`
（专家意见第十七节：**正确率 + 解题时间** 比单纯正确率更能反映儿童真实能力，
为后续 `ChildAbility` 能力画像铺路）。旧数据库首次启动时自动补列。

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

  - 题型：多条件排序、多人真假话（配对推理已内置）
  - Phase 3b：外部题中文改写/翻译器（当前保留英文原文，需人工审核后入正式题库）
  - Phase 3c：更多数据源（LSAT reasoning CC BY 4.0；OpenBookQA 偏知识推理，暂缓）
  - 自动变体：同一模板换主题词后重新 Solver 验证（已具备基础）
- 能力画像的更细粒度建模（IRT / 知识追踪）
- Phase 2：题库统一 QuestionSchema（source/license/provenance），内置题先行
- Phase 3：外部题库导入层（Raw → Normalizer → Validator → Bank，先评估 LogiQA2.0 / BIG-bench）
- Phase 4：自适应难度（ChildAbility → 题型能力 → 难度预测）
