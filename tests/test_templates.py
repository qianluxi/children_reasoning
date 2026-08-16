"""题型模板与生成器测试：每个模板都能稳定产出通过 Validator 的唯一解题。"""
import pytest
import random

from logic_kids.questions import generator
from logic_kids.questions.templates import (truth, ordering, conditional,
                                            set_logic, exclusion, matching)
from logic_kids.validator.validator import validate
from logic_kids.difficulty import engine
from logic_kids.logic import solver

TEMPLATES = {
    "truth_statements": truth.generate,
    "ordering": ordering.generate,
    "conditional": conditional.generate,
    "set_logic": set_logic.generate,
    "exclusion": exclusion.generate,
    "matching": matching.generate,
}


@pytest.mark.parametrize("qtype", list(TEMPLATES.keys()))
def test_template_generates_valid_questions(qtype):
    rng = random.Random(123)
    made = 0
    for _ in range(15):
        q = TEMPLATES[qtype](rng)
        assert q is not None, f"{qtype} 生成失败"
        report = validate(q)
        assert report.ok, f"{qtype} 验证失败: {report.issues}"
        engine.apply(q)
        assert q.difficulty in (1, 2, 3, 4, 5)
        made += 1
    assert made == 15


@pytest.mark.parametrize("qtype", ["truth_statements", "ordering", "exclusion"])
def test_unique_solution_for_deterministic_types(qtype):
    """真假话/排序/排除应有唯一解（或答案被唯一确定）。"""
    rng = random.Random(7)
    q = TEMPLATES[qtype](rng)
    solutions = solver.solve(q)
    assert len(solutions) >= 1
    if qtype in ("truth_statements", "ordering"):
        assert len(solutions) == 1


def test_conditional_modes_all_work():
    """条件推理的三种模式（肯定/否定/不明）都应能生成。"""
    rng = random.Random(5)
    answers_seen = set()
    for _ in range(60):
        q = conditional.generate(rng)
        answers_seen.add(q.options[q.answer])
        assert validate(q).ok
    # 三种答案类型都应出现
    assert "一定会发生" in answers_seen
    assert "一定不会发生" in answers_seen
    assert "无法确定" in answers_seen


def test_generate_batch_distribution():
    batch = generator.generate_batch(25, seed=99)
    assert len(batch) == 25
    types = {q.type for q in batch}
    # 六种题型都应覆盖
    assert len(types) == 6
    # 全部通过验证
    for q in batch:
        assert validate(q).ok


def test_matching_both_forms():
    """配对推理的两种问法（谁喜欢某物 / 某小朋友喜欢什么）都应能生成。"""
    rng = random.Random(21)
    prompts = set()
    for _ in range(60):
        q = matching.generate(rng)
        assert q is not None
        assert validate(q).ok
        prompts.add(q.question_prompt)
    assert any("谁喜欢" in p for p in prompts)
    assert any(p.endswith("喜欢什么？") for p in prompts)


def test_no_duplicate_options_in_batch():
    rng = random.Random(2024)
    for qtype, gen in TEMPLATES.items():
        for _ in range(20):
            q = gen(rng)
            assert len(set(q.options)) == len(q.options), f"{qtype} 出现重复选项"
            assert len(q.option_logic) == len(q.options)
            assert 0 <= q.answer < len(q.options)


def test_ordering_story_prompt_semantics_match():
    """顺序题的题干/故事/线索必须与关系场景一致（专家审查 P0）。

    排队 → 问"第 X 位"；身高 → 问"第 X 高"；比赛 → 问"第 X 名"，
    三者绝不能混用（例如"比身高"却问"谁排在第 X 位"）。
    """
    rng = random.Random(42)
    for _ in range(60):
        q = ordering.generate(rng)
        prompt = q.question_prompt
        story = q.story.title + q.story.text
        cons = "".join(c.text for c in q.constraints)
        if "位" in prompt:      # 排队场景
            assert "排" in story and "排" in cons, f"排队题语义不符: {prompt} / {story}"
        elif "高" in prompt:    # 身高场景
            assert "身高" in story, f"身高题故事不符: {story}"
            assert "高" in cons or "矮" in cons, f"身高题线索不符: {cons}"
        elif "名" in prompt:    # 比赛场景
            assert "比赛" in story, f"比赛题故事不符: {story}"
            assert "跑" in cons, f"比赛题线索不符: {cons}"
        else:
            pytest.fail(f"未知提问形式: {prompt}")


def test_seeds_are_valid():
    from logic_kids.bank.seed import all_seeds
    for q in all_seeds():
        report = validate(q)
        assert report.ok, f"种子题 {q.id} 验证失败: {report.issues}"
