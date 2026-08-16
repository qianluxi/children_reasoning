"""题目生成器（专家意见第十八节：自动变体生成）。

把各题型模板统一封装，随机生成题目 -> Solver 验证唯一解 -> Validator 质量检查
-> 难度评分 -> 返回可入库的 Question。模板换主题词即可产生大量变体。
"""
from __future__ import annotations

import random

from ..difficulty import engine
from ..models import ensure_builtin_source, ensure_taxonomy
from ..validator.validator import validate
from .templates import (truth, ordering, conditional, set_logic, exclusion,
                        matching, color_pattern)

GENERATORS = {
    "truth_statements": truth.generate,
    "ordering": ordering.generate,
    "conditional": conditional.generate,
    "set_logic": set_logic.generate,
    "exclusion": exclusion.generate,
    "matching": matching.generate,
    "color_pattern": color_pattern.generate,
}

TYPE_NAMES = {
    "truth_statements": "真假话",
    "ordering": "顺序排列",
    "conditional": "条件推理",
    "set_logic": "集合关系",
    "exclusion": "排除推理",
    "matching": "配对推理",
    "color_pattern": "颜色规律",
    "external_text": "外部逻辑",
}


def generate_one(qtype: str, rng: random.Random, **kwargs):
    """生成一道指定类型的题；通过验证则返回，否则返回 None。"""
    gen = GENERATORS.get(qtype)
    if gen is None:
        raise ValueError(f"未知题型: {qtype}")
    q = gen(rng, **kwargs)
    if q is None:
        return None
    report = validate(q)
    if not report.ok:
        return None
    engine.apply(q)
    ensure_builtin_source(q)
    ensure_taxonomy(q)
    return q


def generate_batch(count: int, seed: int = None, types: list = None,
                   per_type_max_tries: int = 1000) -> list:
    """批量生成题目，尽量在各题型间均匀分布。返回 Question 列表。"""
    rng = random.Random(seed)
    types = types or list(GENERATORS.keys())
    results = []
    # 轮转各题型，直到达到 count 或用尽尝试
    idx = 0
    tries = 0
    while len(results) < count and tries < count * per_type_max_tries:
        qtype = types[idx % len(types)]
        idx += 1
        tries += 1
        q = generate_one(qtype, rng)
        if q is not None:
            results.append(q)
    return results
