"""图形化渲染测试：迷宫 / ARC 格子 / 长方形计数 → PNG。"""
from logic_kids import visuals
from logic_kids.models import Question, Story, SourceInfo, Provenance


def _visual_q(dataset_id, metadata, story_text="t"):
    return Question(
        id="vq", type="external_text", story=Story("t", story_text, {}),
        entities=[], variables=[], statements=[], constraints=[],
        question_prompt="?", options=["a", "b"], option_logic=[],
        answer=0, hints=[], explanation="", source="reasoning_gym",
        source_info=SourceInfo(type="external", name="Reasoning Gym",
                               license="Apache-2.0", dataset_id=dataset_id),
        provenance=Provenance(review_status="approved"),
        metadata=metadata,
    )


def test_render_maze_png():
    q = _visual_q("task=maze", {
        "grid": ["#####", "#S#G#", "#####"],
        "start": "S", "goal": "G", "wall": "#",
    })
    data = visuals.render_maze(q)
    assert data is not None and data[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_arc_png():
    q = _visual_q("task=arc_1d", {
        "train_examples": [
            {"input": [0, 1, 0], "output": [1, 0, 0]},
            {"input": [0, 2, 0], "output": [2, 0, 0]},
        ],
        "test_example": {"input": [0, 3, 0], "output": [3, 0, 0]},
    })
    assert visuals.render_arc(q)[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_rect_png():
    q = _visual_q("task=rectangle_count", {
        "puzzle": "##\n##",
    })
    assert visuals.render_rect(q)[:8] == b"\x89PNG\r\n\x1a\n"


def test_visual_kind_and_none():
    assert visuals.visual_kind(_visual_q("task=maze", {})) == "maze"
    assert visuals.visual_kind(_visual_q("task=arc_1d", {})) == "arc"
    assert visuals.visual_kind(_visual_q("task=chain_sum", {})) is None
    assert visuals.render_question_png(
        _visual_q("task=chain_sum", {})) is None
    # 没有图形的题：render_question_png 返回 None
    plain = Question(
        id="p", type="ordering", story=Story("t", "t", {}), entities=[],
        variables=[], statements=[], constraints=[], question_prompt="?",
        options=["x", "y"], option_logic=[], answer=0, hints=[], explanation="")
    assert visuals.render_question_png(plain) is None
