"""统一题目模型（专家意见第十节：ExternalQuestion → NormalizedQuestion → Question）。

外部题库格式千差万别，一律先归一化为 NormalizedQuestion，再转换为内部 Question：

    External Dataset
          ↓
    NormalizedQuestion（统一字段，含 source_info / provenance）
          ↓
    Question（内部统一模型，可带 DSL 也可不带）

核心原则（专家意见第九节）：不强行把外部题转换成 DSL。能转就转
（进入 Solver 四道闸门），不能转就保留文字字段，标记待人工/LLM 改写审核。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..models import (Question, Story, Variable, Statement, Constraint,
                      SourceInfo, Provenance)


@dataclass
class NormalizedQuestion:
    """外部题的统一中间模型。"""
    source: SourceInfo
    provenance: Provenance
    qtype: str = "external_text"       # 内部题型标签
    story_title: str = ""
    story_text: str = ""
    entities: list = field(default_factory=list)        # 实体代号（可空）
    roles: dict = field(default_factory=dict)           # 代号 -> 显示名
    variables: list = field(default_factory=list)       # list[Variable]
    statements: list = field(default_factory=list)      # list[Statement]
    constraints: list = field(default_factory=list)     # list[Constraint]
    question_prompt: str = ""
    options: list = field(default_factory=list)
    option_logic: list = field(default_factory=list)    # 可空（无 DSL）
    answer: int = -1
    hints: list = field(default_factory=list)
    explanation: str = ""
    category: str = ""                                  # 能力大类
    skills: list = field(default_factory=list)          # 技能标签
    age_range: str = ""                                 # 年龄分级 A/B/C/D

    @property
    def has_dsl(self) -> bool:
        """是否有可交给 Solver 的逻辑表达（约束或选项逻辑）。"""
        return bool(self.constraints and any(c.logic for c in self.constraints)) \
            or bool(self.option_logic and any(self.option_logic))

    def to_question(self, qid: str) -> Question:
        from .. import taxonomy
        category = self.category
        skills = self.skills
        if not category:
            category, skills = taxonomy.defaults_for(self.qtype)
        return Question(
            id=qid,
            type=self.qtype,
            story=Story(title=self.story_title, text=self.story_text,
                        roles=self.roles),
            entities=list(self.entities),
            variables=list(self.variables),
            statements=list(self.statements),
            constraints=list(self.constraints),
            question_prompt=self.question_prompt,
            options=list(self.options),
            option_logic=list(self.option_logic),
            answer=self.answer,
            hints=list(self.hints),
            explanation=self.explanation,
            source=self.source.name.lower(),
            source_info=self.source,
            provenance=self.provenance,
            category=category,
            skills=skills,
            age_range=self.age_range,
            created_at=self.provenance.imported_at,
        )
