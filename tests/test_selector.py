"""QuestionSelector 测试（专家意见第三节：用户选择难度后题目真正受到限制）。"""
import random

import pytest

from logic_kids.bank import store
from logic_kids.difficulty import levels
from logic_kids.questions.generator import generate_batch
from logic_kids.questions.selector import select_question
from logic_kids.progress import store as progress


@pytest.fixture(scope="module")
def bank():
    store.clear()
    batch = generate_batch(60, seed=11)
    store.save_many(batch)
    # 四个用户等级都要有题，否则回退逻辑会把断言变模糊
    covered = {levels.level_for_score(q.difficulty_score) for q in batch}
    assert covered == {1, 2, 3, 4}, f"生成批次未覆盖全部等级: {covered}"
    return batch


def test_select_by_level_stays_in_band(bank):
    rng = random.Random(3)
    for lv in (1, 2, 3, 4):
        for _ in range(10):
            pick = select_question(difficulty=lv, rng=rng)
            assert pick is not None
            q = pick["question"]
            assert pick["difficulty_level"] == lv
            lo, hi = levels.score_range(lv)
            assert lo <= q.difficulty_score <= hi


def test_select_category(bank):
    ids = set()
    for seed in range(30):
        pick = select_question(difficulty=2, category="ordering",
                               rng=random.Random(seed))
        assert pick is not None and pick["qtype"] == "ordering"
        ids.add(pick["question"].id)
    assert len(ids) >= 2


def test_select_avoids_recent(bank):
    cid = progress.create_child("选择器测试娃")
    picked = set()
    rng = random.Random(9)
    for _ in range(5):
        pick = select_question(difficulty=1, child_id=cid, rng=rng)
        assert pick is not None
        qid = pick["question"].id
        assert qid not in picked, "不应重复出同一道题"
        picked.add(qid)
        progress.record_attempt(cid, qid, pick["qtype"], True)


def test_invalid_inputs(bank):
    with pytest.raises(ValueError):
        select_question(difficulty=5)
    with pytest.raises(ValueError):
        select_question(difficulty="3")
    with pytest.raises(ValueError):
        select_question(category="不存在的题型")


def test_all_excluded_returns_none(bank):
    all_ids = set(store.list_ids())
    pick = select_question(difficulty=4, exclude_ids=all_ids,
                           rng=random.Random(1))
    assert pick is None
