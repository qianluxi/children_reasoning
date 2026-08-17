"""批处理基础设施测试（PR1）：许可证策略 / 儿童适配 / 去重 / 批量配置 / 综合训练。"""
import random
import shutil

import pytest
import yaml

from logic_kids import child_suitability, dedup, license_policy
from logic_kids.bank import external, importer, import_job, provenance, store
from logic_kids.config import IMPORTS_DIR, ensure_dirs
from logic_kids.difficulty import engine
from logic_kids.models import (Question, Story, Constraint, SourceInfo,
                               Provenance)
from logic_kids.questions.selector import select_question


def _ext_q(translated=True, dsl=True, category="deduction"):
    return Question(
        id="ext_pr1_q", type="ordering",
        story=Story("t", "t", {}), entities=["A", "B"],
        variables=[], statements=[], constraints=[
            Constraint("x", "RANK(A) < RANK(B)")] if dsl else [],
        question_prompt="?", options=["a", "b"],
        option_logic=["RANK(A) == 1", "RANK(B) == 1"] if dsl else [],
        answer=0, hints=[], explanation="",
        difficulty=1, difficulty_score=1.0, difficulty_level=1,
        source="bigbench",
        source_info=SourceInfo(type="external", name="BIG-bench",
                               license="Apache-2.0"),
        provenance=Provenance(review_status="approved",
                              logic_validated=dsl),
        translations={"zh": {"status": "machine", "story_title": "t",
                             "story_text": "t", "constraints": ["x"],
                             "options": ["a", "b"],
                             "question_prompt": "?", "explanation": ""}}
        if translated else None,
        category=category, skills=["deduction"],
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


def test_license_classify():
    assert license_policy.classify("Apache-2.0") == "production"
    assert license_policy.classify("MIT") == "production"
    assert license_policy.classify("CC-BY-NC-SA-4.0") == "noncommercial"
    assert license_policy.classify("CC-BY-NC-4.0") == "noncommercial"
    assert license_policy.classify("WTFPL") == "unknown"
    assert license_policy.classify("") == "unknown"


def test_child_suitability_scores():
    q = _ext_q(translated=True)
    engine.apply(q)
    ev = q.child_suitability
    for k in ("reading_level", "language_complexity", "abstractness",
              "reasoning_depth", "calculation_load", "cultural_dependency",
              "suitable"):
        assert k in ev
    assert ev["suitable"] is True
    # 未翻译的英文外部题：文化依赖高 -> 不适合直接给儿童
    q2 = _ext_q(translated=False)
    engine.apply(q2)
    assert q2.child_suitability["cultural_dependency"] >= 4
    assert q2.child_suitability["suitable"] is False


def test_dedup_hashes():
    q1 = _ext_q()
    q2 = _ext_q()
    assert dedup.text_hash(q1) == dedup.text_hash(q2)
    assert dedup.logic_signature(q1) == dedup.logic_signature(q2)
    q3 = _ext_q(dsl=False)
    assert dedup.logic_signature(q3) is None  # 无 DSL 无法做结构签名


def test_quality_grading():
    builtin = Question(
        id="b", type="ordering", story=Story("t", "t", {}), entities=[],
        variables=[], statements=[], constraints=[], question_prompt="?",
        options=["x", "y"], option_logic=[], answer=0, hints=[], explanation="")
    assert importer.grade_quality(builtin) == "A"
    ext_dsl = _ext_q(translated=True)
    assert importer.grade_quality(ext_dsl) == "B"  # 机器翻译未人工审核
    ext_adapted = _ext_q(translated=True)
    ext_adapted.translations["zh"]["status"] = "child_adapted"
    assert importer.grade_quality(ext_adapted) == "A"
    ext_nodsl = _ext_q(dsl=False, translated=False)
    assert importer.grade_quality(ext_nodsl) == "C"
    # 儿童化改写：无 DSL 的题升级到 B
    ext_child = _ext_q(dsl=False, translated=True)
    ext_child.translations["zh"]["status"] = "child_adapted"
    assert importer.grade_quality(ext_child) == "B"


def test_import_job_config_dry_run_ledger(monkeypatch, tmp_path):
    def fake_import_source(name, **kw):
        assert kw.get("dry_run") is True
        return {"total": 10, "translated": 8, "skipped": 2,
                "failed_schema": 1, "failed_logic": 0, "pending": 0,
                "approved": 0, "approve_failed": 0, "duplicates": 1,
                "checkpoint_skipped": 0, "valid": 6}

    monkeypatch.setattr(importer, "import_source", fake_import_source)
    cfg = tmp_path / "datasets.yaml"
    cfg.write_text(yaml.safe_dump({"sources": {
        "bigbench": {"enabled": True, "limit": 5, "tasks": ["x"]}}}),
        encoding="utf-8")

    plans = import_job.load_config(str(cfg))
    assert plans[0]["name"] == "bigbench"

    import_job.run_job(str(cfg), dry_run=True)
    ledger = import_job.load_ledger()
    assert ledger["bigbench"]["raw"] == 10
    assert ledger["bigbench"]["valid"] == 6
    assert ledger["bigbench"]["reject"] == 1

    # retry 模式：上次成功的来源跳过
    import_job.run_job(str(cfg), retry=True)
    assert import_job.load_ledger()["bigbench"]["raw"] == 10


def test_stats_table_shape():
    rows = import_job.stats_table()
    assert rows[0][0] == "builtin"
    assert len(rows[0]) == 6


def test_mixed_selector_uses_both_banks():
    store.clear()
    external.clear()
    bq = Question(
        id="mix_builtin", type="matching", story=Story("t", "t", {}),
        entities=[], variables=[], statements=[], constraints=[],
        question_prompt="?", options=["x", "y"],
        option_logic=["TRUE", "FALSE"], answer=0, hints=[], explanation="",
        difficulty=1, difficulty_score=1.0, difficulty_level=1,
        source="generated", category="relation", skills=["relation_reasoning"],
        age_range="A", quality="A")
    store.save_question(bq)
    eq = _ext_q(category="deduction")
    eq.id = "mix_ext"
    external.save_question(eq)

    seen = set()
    rng = random.Random(7)
    for _ in range(60):
        pick = select_question(mixed=True, rng=rng)
        assert pick is not None
        seen.add(pick["question"].id)
    assert seen >= {"mix_builtin", "mix_ext"}


def test_selector_exclude_prevents_repeat():
    from logic_kids.questions.selector import select_question
    store.clear()
    external.clear()
    for i in range(2):
        eq = _ext_q(category="deduction")
        eq.id = f"ext_sel_{i}"
        external.save_question(eq)
    seen = set()
    rng = random.Random(3)
    for _ in range(2):
        pick = select_question(external_bank=True, source="bigbench",
                               exclude_ids=seen, rng=rng)
        assert pick is not None
        assert pick["question"].id not in seen
        seen.add(pick["question"].id)


def test_quota_balance_suggestions():
    from logic_kids.quality import quota
    a = {"total_active": 100,
         "by_ability": {"deduction": 60, "spatial": 1},
         "by_level": {4: 1}, "by_age": {"A": 1},
         "machine_only": 10, "no_proof": 5,
         "structure_duplicates": 3}
    b = quota.balance(a)
    texts = " ".join(b["suggestions"])
    assert "暂停导入 deduction" in texts
    assert "增加 spatial" in texts
    assert "Level 4" in texts
    assert "机器翻译" in texts
    assert "proof" in texts


def test_mixed_selector_category_filter():
    from logic_kids.questions.selector import select_question
    store.clear()
    external.clear()
    bq = Question(
        id="mix_cat_builtin", type="matching", story=Story("t", "t", {}),
        entities=[], variables=[], statements=[], constraints=[],
        question_prompt="?", options=["x", "y"],
        option_logic=["TRUE", "FALSE"], answer=0, hints=[], explanation="",
        difficulty=1, difficulty_score=1.0, difficulty_level=1,
        source="generated", category="relation", skills=["relation_reasoning"],
        age_range="A", quality="A")
    store.save_question(bq)
    eq = _ext_q(category="deduction")
    eq.id = "mix_cat_ext"
    external.save_question(eq)
    for _ in range(10):
        pick = select_question(mixed=True, category="relation",
                               rng=random.Random(2))
        assert pick is not None
        assert pick["question"].category == "relation"
