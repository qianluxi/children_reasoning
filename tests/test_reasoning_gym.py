"""Reasoning Gym 适配器测试（PR2）。"""
import pytest

pytest.importorskip("reasoning_gym")

from logic_kids.bank.sources import reasoning_gym as rg


def test_whitelist_tasks():
    for task, cfg in rg.TASKS.items():
        assert cfg["category"]
        assert cfg["skills"]


def test_invalid_task_rejected():
    with pytest.raises(ValueError):
        rg.fetch(task="codeio")


@pytest.mark.parametrize("task", ["knights_knaves", "family_relationships",
                                  "number_sequence", "syllogism"])
def test_normalize_produces_valid_options(task):
    items = rg.fetch(task=task, limit=8, seed=11)
    assert items, f"{task} 未生成题目"
    for it in items:
        n = rg.normalize(it)
        assert n is not None, f"{task} 转换失败"
        assert len(n.options) >= 2
        assert len(set(n.options)) == len(n.options)
        assert 0 <= n.answer < len(n.options)
        assert n.category and n.skills
        assert 1 <= n.difficulty_level <= 4
        assert n.source.license == "Apache-2.0"
        assert n.source.name == "Reasoning Gym"


def test_answer_is_correct_option():
    for task in ("leg_counting", "number_sequence", "family_relationships"):
        items = rg.fetch(task=task, limit=10, seed=3)
        for it in items:
            n = rg.normalize(it)
            assert n is not None
            # 正确选项就是 reasoning-gym 的答案
            correct = str(it["answer"]).strip()
            assert n.options[n.answer].strip() == correct \
                or correct in n.options[n.answer]


@pytest.mark.parametrize("task", ["chain_sum", "number_sequence",
                                  "leg_counting", "syllogism",
                                  "knights_knaves", "family_relationships"])
def test_zh_translate_question(task):
    items = rg.fetch(task=task, limit=3, seed=9)
    n = rg.normalize(items[0])
    assert n is not None
    q = n.to_question("ext_rg_zh_test")
    zh = rg.zh_translate_question(q)
    assert zh["status"] == "machine"
    assert zh["story_text"]
    assert len(zh["options"]) == len(q.options)
    assert zh["question_prompt"] == "请选择正确答案："
    if task == "syllogism":
        assert zh["options"] == ["是", "否"]
    if task == "chain_sum":
        assert "计算" in zh["story_text"]
    if task == "leg_counting":
        assert "腿" in zh["story_text"]
    if task == "knights_knaves":
        assert any("是" in o for o in zh["options"])
    if task == "family_relationships":
        assert any(o in "爸爸妈妈哥哥姐姐" for o in zh["options"])


@pytest.mark.parametrize("task", ["number_sequence", "leg_counting", "maze",
                                  "time_intervals", "knights_knaves",
                                  "syllogism"])
def test_zh_child_question(task):
    items = rg.fetch(task=task, limit=3, seed=9)
    n = rg.normalize(items[0])
    q = n.to_question("ext_rg_child_test")
    child = rg.zh_child_question(q)
    assert child["status"] == "child_adapted"
    assert child["story_text"]
    assert child["question_prompt"]
    assert len(child["options"]) == len(q.options)
    if task == "number_sequence":
        assert "找规律" in child["story_text"]
    if task == "leg_counting":
        assert "条腿" in child["story_text"]
    if task == "syllogism":
        assert child["options"] == ["对", "不对"]
