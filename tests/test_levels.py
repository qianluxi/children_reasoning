"""难度等级映射测试（专家意见第二节：score → level 分离，映射只在此处定义）。"""
import pytest

from logic_kids.difficulty import levels


def test_boundaries():
    assert levels.level_for_score(0.0) == 1
    assert levels.level_for_score(2.4) == 1
    assert levels.level_for_score(2.49) == 1
    assert levels.level_for_score(2.5) == 2
    assert levels.level_for_score(4.9) == 2
    assert levels.level_for_score(4.97) == 2
    assert levels.level_for_score(4.99) == 2
    assert levels.level_for_score(5.0) == 3
    assert levels.level_for_score(7.4) == 3
    assert levels.level_for_score(7.49) == 3
    assert levels.level_for_score(7.5) == 4
    assert levels.level_for_score(10.0) == 4


def test_out_of_range_clamped():
    assert levels.level_for_score(-5) == 1
    assert levels.level_for_score(99) == 4


def test_labels():
    assert levels.label(1) == "🌱 简单"
    assert levels.label(2) == "⭐ 普通"
    assert levels.label(3) == "🚀 困难"
    assert levels.label(4) == "🧠 挑战"


def test_validate_level():
    for lv in (1, 2, 3, 4):
        assert levels.validate_level(lv) == lv
    for bad in (0, 5, -1, 2.0, "3", True, None):
        with pytest.raises(ValueError):
            levels.validate_level(bad)


def test_score_range():
    assert levels.score_range(1) == (0.0, 2.49)
    assert levels.score_range(3) == (5.0, 7.49)
    assert levels.score_range(4) == (7.5, 10.0)


def test_score_never_falls_between_bands():
    """引擎产出的两位小数分数都应落在其等级的 [min, max] 内（区间连续）。"""
    for s in (0.3, 2.49, 2.50, 4.98, 5.00, 7.43, 7.49, 7.50, 9.99):
        lv = levels.level_for_score(s)
        lo, hi = levels.score_range(lv)
        assert lo <= s <= hi, f"score={s} level={lv} 不在 {lo}..{hi}"


def test_adjacent_levels():
    assert levels.adjacent_levels(2)[0] == 2
    assert set(levels.adjacent_levels(2)) == {1, 2, 3, 4}
    assert levels.adjacent_levels(1) == [1, 2, 3, 4]
    assert levels.adjacent_levels(4) == [4, 3, 2, 1]


def test_public_levels():
    pl = levels.public_levels()
    assert [p["level"] for p in pl] == [1, 2, 3, 4]
    assert all(p["label"].startswith(p["emoji"]) for p in pl)
    # 儿童界面不暴露评分
    assert all("score" not in p for p in pl)
