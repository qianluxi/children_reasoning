"""统一 Question 数据模型（专家意见第二节）。

设计要点：
    - 文字只是表现层（story/statements/options 的 text 字段）；
    - logic 表达式才是核心（statements[].logic / constraints[].logic / option_logic[]）；
    - 全部字段可 JSON 序列化，题库文件即 JSON。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional


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
        q = cls(**d)
        # 旧题库文件可能没有 difficulty_level：用评分反算，保证新旧数据一致
        if q.difficulty_level is None and q.difficulty_score:
            from .difficulty import levels
            q.difficulty_level = levels.level_for_score(q.difficulty_score)
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
