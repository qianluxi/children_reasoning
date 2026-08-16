"""自适应出题引擎（专家意见第十三节）。

流程：儿童能力模型 -> 选薄弱技能 -> 定适当难度(70/20/10) -> 从题库选题。

难度选择：以该题型的"当前水平"为基准，
  · 70% 出当前水平
  · 20% 出简单一档（保底、建立信心）
  · 10% 出挑战一档（促进提升）
"""
from __future__ import annotations

import random

from ..bank import store
from ..progress import store as progress
from ..questions.generator import GENERATORS

ALL_TYPES = list(GENERATORS.keys())


def _mastery_to_level(mastery: float | None) -> int:
    """把掌握度映射为当前难度水平（1..5）。"""
    if mastery is None:
        return 1
    if mastery < 0.4:
        return 1
    if mastery < 0.6:
        return 2
    if mastery < 0.8:
        return 3
    if mastery < 0.95:
        return 4
    return 5


def pick_weakest_type(child_id: int, rng: random.Random) -> str:
    """优先未练过的题型（探索），其次掌握度最低的题型。"""
    unseen = [t for t in ALL_TYPES if progress.mastery(child_id, t) is None]
    if unseen:
        return rng.choice(unseen)
    scored = [(progress.mastery(child_id, t), t) for t in ALL_TYPES]
    scored.sort(key=lambda x: x[0])  # 掌握度升序
    # 在最差的几个里随机，避免总是同一题型
    worst = scored[:2]
    return rng.choice(worst)[1]


def pick_difficulty(child_id: int, qtype: str, rng: random.Random) -> int:
    base = _mastery_to_level(progress.mastery(child_id, qtype))
    roll = rng.random()
    if roll < 0.7:
        target = base
    elif roll < 0.9:
        target = base - 1
    else:
        target = base + 1
    return max(1, min(5, target))


def next_question(child_id: int, rng: random.Random = None) -> dict | None:
    """为儿童挑一道题，返回 {question, qtype, difficulty, reason}。"""
    rng = rng or random.Random()
    qtype = pick_weakest_type(child_id, rng)
    difficulty = pick_difficulty(child_id, qtype, rng)
    recent = progress.recent_question_ids(child_id)

    # 依次放宽难度，找到可用的题
    for d in _difficulty_fallbacks(difficulty):
        ids = [i for i in store.query(qtype=qtype, difficulty=d) if i not in recent]
        if ids:
            qid = rng.choice(ids)
            q = store.load_question(qid)
            return {"question": q, "qtype": qtype, "difficulty": d,
                    "reason": f"薄弱技能:{qtype}，目标难度:{'★'*d}"}
    # 该题型没有可用题：放宽到任意难度
    ids = [i for i in store.query(qtype=qtype) if i not in recent]
    if ids:
        qid = rng.choice(ids)
        q = store.load_question(qid)
        return {"question": q, "qtype": qtype, "difficulty": q.difficulty,
                "reason": f"薄弱技能:{qtype}"}
    return None


def _difficulty_fallbacks(d: int) -> list:
    """从目标难度向外扩散的搜索顺序。"""
    order = [d]
    for delta in (1, -1, 2, -2, 3, -3, 4, -4):
        nd = d + delta
        if 1 <= nd <= 5 and nd not in order:
            order.append(nd)
    return order
