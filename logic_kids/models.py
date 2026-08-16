"""统一 Question 数据模型（专家意见第二节、第八节）。

设计要点：
    - 文字只是表现层（story/statements/options 的 text 字段）；
    - logic 表达式才是核心（statements[].logic / constraints[].logic / option_logic[]）；
    - source_info + provenance 记录题目来源与许可证（内置/外部题库都要可追溯）；
    - 全部字段可 JSON 序列化，题库文件即 JSON。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class SourceInfo:
    """题目来源（专家意见第八节：题库来源概念）。

    type        "builtin"（自有生成/种子）| "external"（外部数据集）
    name        来源名，如 "children_reasoning" / "BIG-bench" / "LogiQA2.0"
    license     许可证，如 "MIT" / "Apache-2.0" / "CC-BY-NC-SA-4.0"
    dataset_id  外部数据集标识（如 BIG-bench task 路径）
    original_id 外部数据集中原始题目 id
    url         来源地址
    """
    type: str = "builtin"
    name: str = "children_reasoning"
    license: str = "MIT"
    dataset_id: str = ""
    original_id: str = ""
    url: str = ""


@dataclass
class Provenance:
    """导入溯源（专家意见第八节：这道题从哪里来、改过没有）。"""
    imported_at: str = ""        # 导入时间（ISO）
    modified: bool = False       # 是否经过改写/转换
    translator: str = ""         # 转换器标识（如 bigbench 规则翻译器）
    review_status: str = "pending"  # pending / approved / rejected
    logic_validated: bool = False   # 是否通过 Solver/Validator 逻辑验证
    difficulty_calibrated: bool = False  # 难度是否由本引擎重新校准


@dataclass
class Variable:
    name: str                 # 变量名，如 "A_cheese"（布尔）或 "rank_A"（排列）
    type: str = "boolean"     # "boolean" | "rank"


@dataclass
class Statement:
    text: str                 # 儿童看到的话（表现层）
    logic: str                # 这句话的真假表达式（核心）
    speaker: Optional[str] = None   # 说话者实体代号（A/B/C…），None 表示叙述者


@dataclass
class Constraint:
    text: str                 # 儿童看到的规则/事实（表现层）
    logic: str                # 约束表达式（核心），如 TRUTH_COUNT == 1


@dataclass
class Story:
    title: str
    text: str
    roles: dict = field(default_factory=dict)   # 实体代号 -> 显示名，如 {"A": "小灰"}


@dataclass
class Question:
    id: str
    type: str                 # 题型：truth_statements / ordering / conditional / set_logic / exclusion
    story: Story
    entities: list            # 实体代号列表，如 ["A", "B", "C"]
    variables: list           # list[Variable]
    statements: list          # list[Statement]（真假话题；其他题型可为空）
    constraints: list         # list[Constraint]
    question_prompt: str      # 提问文字，如 "谁最高？"
    options: list             # 选项文字
    option_logic: list        # 与 options 等长的逻辑表达式；"TRUE"/"FALSE" 表示恒真/恒假选项
    answer: int               # 正确选项下标
    hints: list               # 逐步提示（由生成器根据模型结构生成）
    explanation: str          # 儿童友好的解释
    difficulty: int = 1       # ★ 星级 1..5（由难度引擎计算）
    difficulty_score: float = 0.0   # 0..10 连续分（由难度引擎计算）
    difficulty_level: Optional[int] = None  # 用户可见等级 1..4（levels.py 映射）
    source: str = "generated" # "seed" | "generated"
    source_info: Optional[SourceInfo] = None    # 来源 + 许可证（可追溯）
    provenance: Optional[Provenance] = None     # 导入溯源（外部题）
    translations: Optional[dict] = None         # 语言变体，如 {"zh": {...}}（中文版）
    category: str = ""                          # 能力大类（taxonomy.ABILITIES；空=待回填）
    skills: list = field(default_factory=list)  # 技能标签（taxonomy.SKILLS）
    age_range: str = ""                         # 年龄分级 A/B/C/D（空=待计算）
    difficulty_profile: dict = field(default_factory=dict)  # 二维难度（engine 计算）
    created_at: str = ""

    # ---------- 序列化 ----------
    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "Question":
        d = dict(d)
        d["story"] = Story(**d["story"])
        d["variables"] = [Variable(**v) for v in d["variables"]]
        d["statements"] = [Statement(**s) for s in d["statements"]]
        d["constraints"] = [Constraint(**c) for c in d["constraints"]]
        if d.get("source_info") is not None:
            d["source_info"] = SourceInfo(**d["source_info"])
        if d.get("provenance") is not None:
            d["provenance"] = Provenance(**d["provenance"])
        has_category = "category" in d
        q = cls(**d)
        # 旧题库文件没有 category/skills：按题型回填缺省标签
        if not has_category or not q.category:
            from . import taxonomy
            q.category, q.skills = taxonomy.defaults_for(q.type)
        if not q.skills:
            from . import taxonomy
            _, q.skills = taxonomy.defaults_for(q.type)
        # 旧题库文件可能没有 difficulty_level：用评分反算，保证新旧数据一致
        if q.difficulty_level is None and q.difficulty_score:
            from .difficulty import levels
            q.difficulty_level = levels.level_for_score(q.difficulty_score)
        if not q.age_range:
            from . import taxonomy
            q.age_range = taxonomy.LEVEL_AGE.get(q.difficulty_level or 1, "B")
        return q

    @classmethod
    def from_json(cls, text: str) -> "Question":
        return cls.from_dict(json.loads(text))

    # ---------- 便捷访问 ----------
    def variable_names(self) -> list:
        return [v.name for v in self.variables]

    def entity_name(self, code: str) -> str:
        return self.story.roles.get(code, code)

    def level_label(self) -> str:
        """儿童友好的等级名，如 "🚀 困难"；未计算时按评分反算。"""
        from .difficulty import levels
        lv = self.difficulty_level
        if lv is None:
            lv = levels.level_for_score(self.difficulty_score)
        return levels.label(lv)


def ensure_builtin_source(question: Question) -> Question:
    """内置题（种子/生成）补全来源信息，缺省标记为自有题库。"""
    if question.source_info is None:
        question.source_info = SourceInfo(type="builtin",
                                          name="children_reasoning",
                                          license="MIT")
    return question


def ensure_taxonomy(question: Question) -> Question:
    """补全能力分类/技能标签（外部题已有自己的标签则保留）。"""
    from . import taxonomy
    if not question.category:
        question.category, question.skills = taxonomy.defaults_for(question.type)
    if not question.skills:
        _, question.skills = taxonomy.defaults_for(question.type)
    return question
