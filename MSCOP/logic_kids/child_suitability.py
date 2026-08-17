"""儿童适配层（专家意见第十五节）。

"通过逻辑验证"不等于"适合儿童"。这里给每题打 6 个适配维度分（1..5），
并给出 child_suitable 结论。阈值可在导入配置里调整。
"""
from __future__ import annotations

from . import taxonomy

THRESHOLD = 4   # 任意维度 >4 即视为不适合当前儿童模式
CULTURAL_LIMIT = 3  # 文化依赖单独限制


def evaluate(question) -> dict:
    """返回 {reading_level, language_complexity, abstractness, reasoning_depth,
    calculation_load, cultural_dependency, suitable}。"""
    prof = question.difficulty_profile or {}
    language = prof.get("language_complexity", 1)
    depth = prof.get("reasoning_depth", 1)
    calc = prof.get("computation_load", 1)
    n = max(len(question.options), len(question.entities), 1)

    # 抽象程度：按能力大类估计（模式/关系较直观，演绎/数学较抽象）
    abstractness = {
        "pattern": 1, "relation": 2, "classification": 2,
        "ordering": 2, "spatial": 3, "deduction": 3,
        "math": 4, "science": 4, "language": 3, "strategy": 4,
    }.get(question.category, 3)

    # 文化依赖：中文原生题最低；机器翻译题稍高；未翻译英文题最高
    cultural = 1
    if question.source_info and question.source_info.type == "external":
        dataset = (question.source_info.dataset_id or "")
        if "lang=zh" in dataset:
            cultural = 1
        elif question.translations:
            cultural = 2
        else:
            cultural = 4  # 未翻译的英文题对中文儿童文化负担高

    reading = min(5, max(1, language + (1 if n >= 5 else 0)))
    result = {
        "reading_level": reading,
        "language_complexity": language,
        "abstractness": abstractness,
        "reasoning_depth": depth,
        "calculation_load": calc,
        "cultural_dependency": cultural,
    }
    suitable = all(v <= THRESHOLD for v in result.values()) \
        and cultural <= CULTURAL_LIMIT
    result["suitable"] = bool(suitable)
    return result


def is_suitable(question) -> bool:
    return bool(evaluate(question)["suitable"])
