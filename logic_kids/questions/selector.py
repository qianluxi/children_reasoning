"""QuestionSelector（专家意见第三节：用户选择难度后题目真正受到限制）。

选择流程：
    用户选择 level=3
        ↓
    QuestionSelector
        ↓
    difficulty_score ∈ [5.0, 7.4]
        ↓
    从题库选题

规则：
    · 精确匹配用户等级；该等级题目不足时，向相邻等级放宽（reason 明确说明）；
    · 可指定题型（category）与儿童 id（避开最近做过的题，为后续自适应铺路）；
    · 返回值与 adaptive.next_question 同构：{"question", "qtype", "difficulty", "reason"}。
"""
from __future__ import annotations

import random

from ..bank import external, store
from ..difficulty import levels
from .. import taxonomy
from ..progress import store as progress
from .generator import GENERATORS

# 综合训练模式的能力权重（专家意见第二十二节）
MIXED_WEIGHTS = {
    "deduction": 0.25, "ordering": 0.15, "pattern": 0.15, "relation": 0.10,
    "math": 0.10, "spatial": 0.10, "language": 0.05, "science": 0.05,
    "strategy": 0.05, "classification": 0.05,
}


def select_question(difficulty: int = None,
                    child_id: int = None,
                    category: str = None,
                    rng: random.Random = None,
                    avoid_recent: bool = True,
                    exclude_ids: set = None,
                    external_bank: bool = False,
                    source: str = None,
                    mixed: bool = False) -> dict | None:
    """按用户选择的难度等级选题。

    参数：
        difficulty  用户可见等级 1..4；None 表示不限等级（任意抽）。
        child_id    儿童 id；传入时避开最近做过的题。
        category    题型（如 "ordering"）；None 表示全部题型。
        rng         随机源（测试可注入种子）。
        avoid_recent 是否避开最近做过的题（默认 True）。
        exclude_ids 额外排除的题目 id（测试/去重用）。
        external_bank 从外部题库选题（True）；默认内置题库。
        source      外部题库来源 slug（如 "bigbench"）；None 表示全部外部来源。
        mixed       综合训练：按能力权重从内置 + 外部混合选题。
    """
    rng = rng or random.Random()
    if mixed:
        return _select_mixed(difficulty, child_id, rng, exclude_ids)
    if difficulty is not None:
        levels.validate_level(difficulty)
    if category is not None and category not in GENERATORS:
        raise ValueError(f"未知题型: {category}")
    if external_bank and source is not None \
            and source not in {s["slug"] for s in external.list_sources()}:
        raise ValueError(f"未知外部题库来源: {source}")

    recent = set(exclude_ids or ())
    if avoid_recent and child_id is not None:
        recent |= progress.recent_question_ids(child_id)

    # 先精确匹配用户等级；不足时按相邻等级放宽
    if difficulty is not None:
        for lv in levels.adjacent_levels(difficulty):
            ids = _query(external_bank, source, qtype=category,
                         difficulty_level=lv, exclude_ids=recent)
            if ids:
                qid = rng.choice(ids)
                q = _load(external_bank, source, qid)
                if lv == difficulty:
                    reason = f"你选择的等级：{levels.label(lv)}"
                else:
                    reason = (f"你选择的等级 {levels.label(difficulty)} 题目暂时不够，"
                              f"这次先从相邻的 {levels.label(lv)} 里挑")
                return {"question": q, "qtype": q.type,
                        "difficulty": q.difficulty, "difficulty_level": lv,
                        "reason": reason}

    # 完全没有匹配等级：退到任意难度（并明确说明）
    ids = _query(external_bank, source, qtype=category, exclude_ids=recent)
    if ids:
        qid = rng.choice(ids)
        q = _load(external_bank, source, qid)
        return {"question": q, "qtype": q.type, "difficulty": q.difficulty,
                "difficulty_level": levels.level_for_score(q.difficulty_score),
                "reason": f"题库中该等级暂无题目，随便挑了一道：{q.type}"}
    return None


def _query(external_bank: bool, source: str, **kw) -> list:
    if external_bank:
        return external.query(slug=source, **kw)
    return store.query(**kw)


def _load(external_bank: bool, source: str, qid: str):
    if external_bank:
        if source:
            return external.load_question(source, qid)
        return external.load_question_any(qid)
    return store.load_question(qid)


def _select_mixed(difficulty: int, child_id: int, rng: random.Random,
                  exclude_ids: set = None) -> dict | None:
    """综合训练：先按能力权重抽能力，再在该能力下从内置 + 外部选题。"""
    recent = set(exclude_ids or ())
    if child_id:
        recent |= progress.recent_question_ids(child_id)
    order = levels.adjacent_levels(difficulty) if difficulty is not None else [None]
    pool = {}
    for lv in order:
        for ability in MIXED_WEIGHTS:
            ids = store.query(category=ability, difficulty_level=lv,
                              exclude_ids=recent)
            ids += external.query(category=ability, difficulty_level=lv,
                                  exclude_ids=recent)
            if ids:
                pool.setdefault(ability, []).extend(ids)
        if pool:
            break  # 优先精确等级；不足时向外放宽
    if not pool:
        ids = store.query(exclude_ids=recent) + external.query(exclude_ids=recent)
        if not ids:
            return None
        qid = rng.choice(ids)
        q = store.load_question(qid) or external.load_question_any(qid)
        return {"question": q, "qtype": q.type, "difficulty": q.difficulty,
                "difficulty_level": levels.level_for_score(q.difficulty_score),
                "reason": "综合训练（任意能力）"}
    abilities = [a for a in MIXED_WEIGHTS if pool.get(a)]
    weights = [MIXED_WEIGHTS[a] for a in abilities]
    ability = rng.choices(abilities, weights=weights)[0]
    qid = rng.choice(pool[ability])
    q = store.load_question(qid) or external.load_question_any(qid)
    return {"question": q, "qtype": q.type, "difficulty": q.difficulty,
            "difficulty_level": levels.level_for_score(q.difficulty_score),
            "reason": f"综合训练 · {taxonomy.ability_label(ability)}"}
