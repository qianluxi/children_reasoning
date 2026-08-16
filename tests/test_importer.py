"""外部题库导入管线测试（专家意见第十一节：四道闸门 + 待审队列）。

全部使用离线 fixture，不访问网络；数据目录由 conftest 隔离到临时目录。
"""
import shutil

import pytest

from logic_kids.bank import external, importer, provenance, store
from logic_kids.bank.normalizer import NormalizedQuestion
from logic_kids.bank.sources import bigbench, logiqa
from logic_kids.config import IMPORTS_DIR, ensure_dirs
from logic_kids.validator.validator import validate


FIXTURE_TASK = {
    "examples": [
        {
            "input": ("On a shelf, there are three books: a black book, an orange book, "
                      "and a blue book. The blue book is to the right of the orange book. "
                      "The orange book is to the right of the black book."),
            "target_scores": {
                "The black book is the leftmost.": 1,
                "The orange book is the leftmost.": 0,
                "The blue book is the leftmost.": 0,
            },
        },
        {
            "input": ("On a branch, there are three birds: a falcon, a raven, and a crow. "
                      "The falcon is to the left of the raven. The raven is to the left of the crow."),
            "target_scores": {
                "The falcon is the rightmost.": 0,
                "The raven is the rightmost.": 0,
                "The crow is the rightmost.": 1,
            },
        },
        {
            "input": ("In a race, there were three golfers: Ana, Bob, and Cid. "
                      "Ana finished above Bob. Cid finished above Ana."),
            "target_scores": {
                "Ana finished last.": 0,
                "Bob finished last.": 1,
                "Cid finished last.": 0,
            },
        },
    ]
}


def _items():
    return [dict(ex, _task="logical_deduction/three_objects", _index=i)
            for i, ex in enumerate(FIXTURE_TASK["examples"])]


@pytest.fixture(scope="module", autouse=True)
def isolated_data():
    """隔离：测试开始与结束时清空正式题库与待审队列。"""
    ensure_dirs()
    store.clear()
    external.clear()
    shutil.rmtree(IMPORTS_DIR, ignore_errors=True)
    ensure_dirs()
    yield
    shutil.rmtree(IMPORTS_DIR, ignore_errors=True)
    store.clear()
    external.clear()


def test_bigbench_translate_to_dsl():
    n = bigbench.normalize(_items()[0])
    assert n is not None
    assert n.qtype == "ordering"
    assert len(n.options) == 3 and n.answer == 0
    logics = [c.logic for c in n.constraints]
    assert "RANK(B) > RANK(A)" in logics   # orange 在 black 右边
    assert "RANK(C) > RANK(B)" in logics   # blue 在 orange 右边
    assert n.option_logic == ["RANK(A) == 1", "RANK(B) == 1", "RANK(C) == 1"]
    assert n.source.license == "Apache-2.0"
    assert n.provenance.translator == "bigbench_logical_deduction_rule_v1"
    assert n.has_dsl


def test_bigbench_race_domain():
    n = bigbench.normalize(_items()[2])
    assert n is not None and n.answer == 1  # Bob finished last
    assert "RANK(A) < RANK(B)" in [c.logic for c in n.constraints]
    assert "RANK(C) < RANK(A)" in [c.logic for c in n.constraints]


def test_bigbench_zh_translation():
    n = bigbench.normalize(_items()[0])
    q = n.to_question("ext_zh_test")
    zh = bigbench.zh_translate_question(q)
    assert "书架" in zh["story_text"]
    assert "右边" in " ".join(zh["constraints"])
    assert zh["options"][0].startswith("黑色的书")
    assert "最左边" in zh["options"][0]


def test_import_stores_zh_translations():
    report = importer.import_items("bigbench", _items(), bigbench.normalize,
                                   translate=bigbench.zh_translate_question,
                                   limit=1)
    assert report["pending"] == 1
    q = provenance.load_pending("ext_bigbench_logical_deduction_three_objects_0")
    assert q is not None
    assert q.translations and "zh" in q.translations
    assert q.translations["zh"]["options"][0].startswith("黑色的书")


def test_bigbench_unparsable_rejected():
    bad = {
        "input": ("On a shelf, there are two books: a red book and a blue book. "
                  "The red book is somewhere mysterious."),
        "target_scores": {
            "The red book is the leftmost.": 1,
            "The blue book is the leftmost.": 0,
        },
        "_task": "x", "_index": 9,
    }
    assert bigbench.normalize(bad) is None


def test_logiqa_normalize_no_dsl():
    raw = {"id": 218, "answer": 3, "text": "Jupiter is large.",
           "question": "Which supports?", "options": ["a", "b", "c", "d"],
           "_split": "dev"}
    n = logiqa.normalize(raw)
    assert n is not None
    assert n.answer == 3 and len(n.options) == 4
    assert not n.has_dsl
    assert n.source.license == "CC-BY-NC-SA-4.0"


def test_logiqa_zh_normalize():
    """LogiQA 官方中文版：example_id 字段 + 中文内容。"""
    raw = {"example_id": 9775, "answer": 2,
           "text": "经济学家的结论基于下列哪个假设之一。",
           "question": "经济学家的结论基于下列哪个假设之一？",
           "options": ["甲", "乙", "丙", "丁"], "_split": "dev", "_lang": "zh"}
    n = logiqa.normalize(raw)
    assert n is not None
    assert n.answer == 2 and len(n.options) == 4
    assert n.source.original_id == "9775"
    assert "lang=zh" in n.source.dataset_id
    assert not n.has_dsl


def test_schema_validation():
    n = bigbench.normalize(_items()[0])
    assert importer.schema_validate(n) == []
    bad = NormalizedQuestion(source=n.source, provenance=n.provenance,
                             options=["a", "a"], answer=5,
                             question_prompt="?", story_text="?")
    assert importer.schema_validate(bad)


def test_logic_gate_rejects_wrong_answer():
    n = bigbench.normalize(_items()[0])
    q = n.to_question("ext_test_wrong_answer")
    q.answer = 1  # 正确答案是 0
    ok, issues = importer.logic_validate(q)
    assert not ok and issues


def test_pipeline_pending_then_approve():
    report = importer.import_items("bigbench", _items(), bigbench.normalize)
    assert report["total"] == 3
    assert report["translated"] == 3
    assert report["pending"] == 3
    # 只进待审队列，不进正式题库
    assert len(provenance.list_pending()) == 3
    assert store.stats()["total"] == 0

    qid = "ext_bigbench_logical_deduction_three_objects_0"
    ok, msg = importer.approve_pending(qid)
    assert ok, msg
    # 审核通过后进入"外部题库"（按来源分目录），内置题库保持为空
    assert external.stats()["total"] == 1
    assert external.list_sources()[0]["slug"] == "bigbench"
    assert store.stats()["total"] == 0
    q = external.load_question("bigbench", qid)
    assert q is not None
    assert validate(q).ok
    assert q.provenance.review_status == "approved"
    assert q.provenance.logic_validated
    assert q.provenance.difficulty_calibrated
    assert 1 <= q.difficulty_level <= 4
    assert q.difficulty_score > 0
    # 未审核的仍留在队列里
    pending = [p for p in provenance.list_pending() if p["review_status"] == "pending"]
    assert len(pending) == 2


def test_non_dsl_cannot_approve():
    before = store.stats()["total"]
    ext_before = external.stats()["total"]
    raw = {"id": 99, "answer": 0, "text": "Some logic context.",
           "question": "Which is right?", "options": ["a", "b"], "_split": "dev"}
    report = importer.import_items("logiqa", [raw], logiqa.normalize, approve=True)
    assert report["pending"] == 1
    assert report["approved"] == 0
    assert report["approve_failed"] == 1
    assert store.stats()["total"] == before  # 无 DSL 的题绝不能进内置题库
    assert external.stats()["total"] == ext_before  # 也不能进外部题库
    # 手动审核也会被拒绝
    ok, msg = importer.approve_pending("ext_logiqa_split_dev_99")
    assert not ok


def test_non_dsl_force_approve():
    """人工抽检后 force=True 可放行无 DSL 题（保留未验证标记）。"""
    before = external.stats()["total"]
    raw = {"id": 100, "answer": 0, "text": "Some logic context.",
           "question": "Which is right?", "options": ["a", "b"], "_split": "dev"}
    importer.import_items("logiqa", [raw], logiqa.normalize)
    n = logiqa.normalize(raw)
    qid = importer.make_qid("logiqa", n.source.dataset_id, n.source.original_id)
    ok, msg = importer.approve_pending(qid, force=True)
    assert ok, msg
    q = external.load_question_any(qid)
    assert q is not None
    assert q.provenance.logic_validated is False
    assert q.provenance.difficulty_calibrated is False
    assert external.stats()["total"] == before + 1


def test_make_qid_sanitizes():
    assert importer.make_qid("bigbench",
                             "logical_deduction/three_objects", 0) == \
        "ext_bigbench_logical_deduction_three_objects_0"


def test_heuristic_difficulty_flags_uncalibrated():
    raw = {"id": 7, "answer": 1, "text": "ctx", "question": "q?",
           "options": ["a", "b", "c"], "_split": "dev"}
    n = logiqa.normalize(raw)
    q = n.to_question("ext_logiqa_7")
    calibrated = importer.calibrate_difficulty(q)
    assert not calibrated
    assert q.provenance.difficulty_calibrated is False
    assert q.difficulty_score > 0
