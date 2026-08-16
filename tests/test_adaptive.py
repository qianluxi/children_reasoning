"""进度存储与自适应出题引擎测试。

数据目录由 tests/conftest.py 重定向到临时目录（不碰真实 data/）；
开始时清空临时题库并重建，保证可重复。
"""
import pytest
import random
import uuid

from logic_kids.bank import store
from logic_kids.questions.generator import generate_batch
from logic_kids.progress import store as progress
from logic_kids.engine import adaptive


@pytest.fixture(scope="module")
def bank():
    store.clear()
    batch = generate_batch(40, seed=7)
    store.save_many(batch)
    yield batch


def _new_child():
    return progress.create_child(f"测试_{uuid.uuid4().hex[:8]}")


def test_child_crud():
    cid = _new_child()
    assert isinstance(cid, int) and cid > 0
    names = [c["name"] for c in progress.list_children()]
    assert any(n.startswith("测试_") for n in names)


def test_record_and_mastery(bank):
    cid = _new_child()
    # 连续答对 5 道真假话
    truth_qs = [q for q in bank if q.type == "truth_statements"][:5]
    for q in truth_qs:
        progress.record_attempt(cid, q.id, q.type, correct=True)
    m = progress.mastery(cid, "truth_statements")
    assert m == 1.0
    # 未练过的题型掌握度为 None
    assert progress.mastery(cid, "ordering") is None


def test_profile_shape(bank):
    cid = _new_child()
    prof = progress.profile(cid, list(adaptive.ALL_TYPES))
    assert set(prof.keys()) == set(adaptive.ALL_TYPES)
    for info in prof.values():
        assert "mastery" in info and "attempts" in info


def test_next_question_returns_valid(bank):
    cid = _new_child()
    rng = random.Random(1)
    for _ in range(10):
        pick = adaptive.next_question(cid, rng)
        assert pick is not None
        q = pick["question"]
        assert q is not None
        assert q.type in adaptive.ALL_TYPES
        assert 1 <= pick["difficulty"] <= 5


def test_adaptive_prefers_unseen_then_weak(bank):
    cid = _new_child()
    rng = random.Random(2)
    # 把 truth_statements 练到很差（全错），其它未练
    truth_qs = [q for q in bank if q.type == "truth_statements"][:8]
    for q in truth_qs:
        progress.record_attempt(cid, q.id, q.type, correct=False)
    # 未练题型应优先被探索
    seen_types = set()
    for _ in range(30):
        pick = adaptive.next_question(cid, rng)
        seen_types.add(pick["qtype"])
    # 练过的 truth 掌握度=0，但未练题型也会被探索到
    assert len(seen_types) >= 2


def test_difficulty_fallbacks_cover_all():
    for d in range(1, 6):
        fb = adaptive._difficulty_fallbacks(d)
        assert fb[0] == d
        assert set(fb) <= {1, 2, 3, 4, 5}
        assert len(fb) == 5
