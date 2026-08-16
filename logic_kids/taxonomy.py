"""儿童综合思维训练 · 能力分类体系（V2.1 / V2.2，专家意见第一节、第十五节）。

10 大类认知能力 + 技能标签（Skill Tag）+ 年龄分级。
所有题目（内置生成、外部导入）都要标注 category / skills / age_range，
这是以后"儿童能力画像"与个性化训练的基础。
"""
from __future__ import annotations

# 10 大类认知能力（专家意见第一节）
ABILITIES = {
    "classification": {"name": "分类与归纳", "emoji": "🗂️"},
    "pattern":        {"name": "模式与规律", "emoji": "🔁"},
    "deduction":      {"name": "演绎逻辑",   "emoji": "🧩"},
    "ordering":       {"name": "排序与约束", "emoji": "📏"},
    "relation":       {"name": "关系推理",   "emoji": "🪢"},
    "spatial":        {"name": "空间推理",   "emoji": "🧭"},
    "math":           {"name": "数学问题解决", "emoji": "🔢"},
    "science":        {"name": "常识/科学推理", "emoji": "🔬"},
    "language":       {"name": "语言推理",   "emoji": "🔤"},
    "strategy":       {"name": "计划与策略", "emoji": "♟️"},
}

# 技能标签（Skill Tag）—— 比"题型"更细的认知技能
SKILLS = {
    "deduction": "演绎推理",
    "negation": "否定转换",
    "conditional_reasoning": "条件推理",
    "transitive_reasoning": "传递推理",
    "exclusion": "排除法",
    "one_to_one": "一一对应",
    "set_logic": "集合关系",
    "quantifier": "量词理解",
    "ordering": "排序",
    "relation_reasoning": "关系推理",
    "multi_hop_reasoning": "多步关系链",
    "pattern_recognition": "规律识别",
    "induction": "归纳推理",
    "arithmetic": "算术",
    "comparison": "比较",
    "language_reasoning": "语言理解",
    "visual_abstraction": "图形抽象",
    "spatial_reasoning": "空间推理",
    "planning": "计划策略",
    "counting": "计数",
}

# 年龄分级（V2.4）
AGE_RANGES = {
    "A": "5-7岁",
    "B": "7-9岁",
    "C": "9-11岁",
    "D": "11-13岁",
}

# 内置题型 -> (能力大类, 技能标签列表) 的缺省映射
TYPE_DEFAULTS = {
    "truth_statements": ("deduction", ["deduction", "negation", "quantifier", "set_logic"]),
    "ordering":         ("ordering",  ["ordering", "transitive_reasoning", "deduction"]),
    "conditional":      ("deduction", ["deduction", "conditional_reasoning"]),
    "set_logic":        ("deduction", ["set_logic", "quantifier", "deduction"]),
    "exclusion":        ("deduction", ["exclusion", "deduction"]),
    "matching":         ("relation",  ["relation_reasoning", "one_to_one", "exclusion"]),
    "color_pattern":    ("pattern",   ["pattern_recognition", "induction"]),
    "external_text":    ("deduction", ["deduction", "language_reasoning"]),
}

# 难度等级 -> 建议年龄（低难度更适合低龄）
LEVEL_AGE = {1: "A", 2: "B", 3: "C", 4: "D"}


def ability_label(ability: str) -> str:
    return ABILITIES.get(ability, {}).get("name", ability)


def ability_emoji(ability: str) -> str:
    return ABILITIES.get(ability, {}).get("emoji", "")


def skill_label(skill: str) -> str:
    return SKILLS.get(skill, skill)


def defaults_for(qtype: str) -> tuple:
    """某题型缺省 (category, skills)；未登记时按演绎逻辑兜底。"""
    return TYPE_DEFAULTS.get(qtype, ("deduction", ["deduction"]))


def age_label(age: str) -> str:
    return AGE_RANGES.get(age, age)


def validate_age(age) -> str:
    if age not in AGE_RANGES:
        raise ValueError(f"年龄分级必须是 A/B/C/D，收到 {age!r}")
    return age
