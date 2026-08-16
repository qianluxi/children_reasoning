"""题库质量分析器测试（V2.5）。"""
import shutil

import pytest

from logic_kids import dedup
from logic_kids.bank import external, provenance, store
from logic_kids.config import IMPORTS_DIR, ensure_dirs
from logic_kids.models import (Question, Story, SourceInfo, Provenance)
from logic_kids.quality import analyzer


def _q(qid, quality="A", category="deduction", source="generated",
        external_src=None, license_name="MIT"):
    return Question(
        id=qid, type="ordering", story=Story("t", "t", {}),
        entities=[], variables=[], statements=[], constraints=[],
        question_prompt="?", options=["x", "y"],
        option_logic=["TRUE", "FALSE"], answer=0, hints=[], explanation="",
        difficulty=1, difficulty_score=1.5, difficulty_level=1,
        source=source, category=category, skills=["deduction"],
        age_range="B", quality=quality,
        source_info=SourceInfo(type="external" if external_src else "builtin",
                               name=external_src or "children_reasoning",
                               license=license_name)
        if external_src else None,
        provenance=Provenance(review_status="approved",
                              logic_validated=True)
        if external_src else None,
    )


@pytest.fixture(scope="module", autouse=True)
def isolated():
    ensure_dirs()
    store.clear()
    external.clear()
    dedup.clear()
    shutil.rmtree(IMPORTS_DIR, ignore_errors=True)
    ensure_dirs()
    yield
    shutil.rmtree(IMPORTS_DIR, ignore_errors=True)
    store.clear()
    external.clear()
    dedup.clear()


def test_analyzer_tiers_and_counts():
    store.save_question(_q("b_1", quality="A", category="deduction"))
    store.save_question(_q("b_2", quality="A", category="ordering"))
    external.save_question(
        _q("e_1", quality="B", category="relation",
           external_src="BIG-bench", license_name="Apache-2.0"))
    external.save_question(
        _q("e_2", quality="C", category="math",
           external_src="Reasoning Gym", license_name="Apache-2.0"))
    # 待审队列：raw 层
    pending = _q("p_1", quality="C", category="pattern",
                 external_src="Reasoning Gym", license_name="Apache-2.0")
    pending.provenance.review_status = "pending"
    provenance.save_pending(pending)

    r = analyzer.analyze()
    assert r["total"] == 5
    assert r["by_ability"]["deduction"] == 1
    assert r["by_tier"]["production"] == 2
    assert r["by_tier"]["experimental"] == 1
    assert r["by_tier"]["raw"] == 2
    assert r["by_license"]["production"] == 5  # 2 builtin + 2 apache + 1 pending


def test_analyzer_warnings_for_gaps():
    r = analyzer.analyze()
    # 只有 4 种能力，其余 6 类应为空缺警告
    assert any("题不足" in w for w in r["warnings"])
    assert any("高难度" in w for w in r["warnings"])


def test_report_text_contains_sections():
    text = analyzer.report_text()
    for marker in ("题库总数", "按能力", "按难度等级", "按层级", "按许可证", "问题"):
        assert marker in text
