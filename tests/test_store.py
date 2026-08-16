"""题库存储测试（专家审查 P1：索引损坏不静默当空、写入原子性）。"""
import json

import pytest

from logic_kids.bank import store
from logic_kids.config import BANK_INDEX_PATH, QUESTIONS_DIR
from logic_kids.models import Question, Story


def _fake_question(qid="t_abc"):
    return Question(
        id=qid, type="set_logic", story=Story("t", "t", {}), entities=["A"],
        variables=[], statements=[], constraints=[], question_prompt="?",
        options=["x"], option_logic=["TRUE"], answer=0,
        hints=[], explanation="", source="test", created_at="",
    )


def test_save_and_load_roundtrip():
    store.clear()
    q = _fake_question()
    store.save_question(q)
    loaded = store.load_question(q.id)
    assert loaded is not None and loaded.id == q.id
    assert store.stats()["total"] == 1
    # 原子写入不应残留 .tmp 文件
    assert not list(QUESTIONS_DIR.glob("*.tmp"))
    assert not list(QUESTIONS_DIR.glob("bank_index.json.tmp"))


def test_corrupt_index_raises_not_silent_empty():
    """索引 JSON 损坏时必须报错，不能静默当作空题库（否则会重新生成并失同步）。"""
    store.clear()
    BANK_INDEX_PATH.write_text('{"broken": ', encoding="utf-8")
    with pytest.raises(RuntimeError):
        store._index()
    # 正常索引不受影响
    BANK_INDEX_PATH.write_text(json.dumps({"a": {"type": "x"}}), encoding="utf-8")
    assert store._index() == {"a": {"type": "x"}}


def test_missing_index_means_empty_first_run():
    # 首次运行（索引不存在）应视为空题库，而不是报错
    store.clear()
    assert store._index() == {}
    assert store.stats()["total"] == 0
