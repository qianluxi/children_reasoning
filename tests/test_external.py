"""外部题库独立存储测试（按来源分目录，与内置题库分开）。"""
import pytest

from logic_kids.bank import external, store
from logic_kids.difficulty import engine, levels
from logic_kids.models import Question, Story, SourceInfo, Provenance


def _ext_q(qid, source_name="BIG-bench", score=3.0):
    return Question(
        id=qid, type="ordering",
        story=Story(title="t", text="t", roles={"A": "a"}),
        entities=["A", "B", "C"],
        variables=[], statements=[], constraints=[], question_prompt="?",
        options=["x", "y"], option_logic=["TRUE", "FALSE"], answer=0,
        hints=[], explanation="",
        difficulty=engine.stars(score),
        difficulty_score=score,
        difficulty_level=levels.level_for_score(score),
        source="bigbench",
        source_info=SourceInfo(type="external", name=source_name,
                               license="Apache-2.0",
                               dataset_id="logical_deduction/three_objects",
                               original_id="0", url="http://example"),
        provenance=Provenance(imported_at="2026-01-01T00:00:00",
                              review_status="approved",
                              logic_validated=True,
                              difficulty_calibrated=True),
        created_at="",
    )


@pytest.fixture(scope="module", autouse=True)
def isolated_external():
    external.clear()
    yield
    external.clear()


def test_slug():
    assert external.source_slug("BIG-bench") == "bigbench"
    assert external.source_slug("LogiQA2.0") == "logiqa20"
    assert external.source_slug("children_reasoning") == "childrenreasoning"


def test_save_and_query_by_source():
    external.save_question(_ext_q("ext_a_1", "BIG-bench", score=1.0))
    external.save_question(_ext_q("ext_a_2", "BIG-bench", score=6.0))
    external.save_question(_ext_q("ext_b_1", "LogiQA2.0", score=8.0))

    assert external.stats()["total"] == 3
    sources = {s["slug"]: s["total"] for s in external.list_sources()}
    assert sources == {"bigbench": 2, "logiqa20": 1}

    # 按来源 + 等级过滤
    lv1 = external.query(slug="bigbench",
                         difficulty_level=levels.level_for_score(1.0))
    assert lv1 == ["ext_a_1"]
    lv4 = external.query(difficulty_level=4)  # 跨来源
    assert lv4 == ["ext_b_1"]

    # 题目可在全部来源中按 id 找到
    q = external.load_question_any("ext_b_1")
    assert q is not None and q.source_info.name == "LogiQA2.0"
    assert external.load_question("bigbench", "ext_b_1") is None


def test_external_separate_from_builtin():
    # 外部库的题不会出现在内置题库里，反之亦然
    assert external.stats()["total"] >= 3
    assert "ext_a_1" not in store.list_ids()
    assert store.load_question("ext_a_1") is None


def test_index_roundtrip_meta():
    q = _ext_q("ext_a_1", score=1.0)  # 与 test_save_and_query_by_source 写入的一致
    idx = external._index("bigbench")
    assert idx["ext_a_1"]["license"] == "Apache-2.0"
    assert idx["ext_a_1"]["difficulty_level"] == q.difficulty_level
