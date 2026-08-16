"""难度引擎测试：结构越复杂分数越高，星级映射正确。"""
from logic_kids.difficulty import levels
from logic_kids.difficulty import engine
from logic_kids.models import Question, Story, Variable, Statement, Constraint
from tests.test_solver import make_question, mice_question


def star_of(**kw):
    q = make_question(**kw)
    s = engine.score(q)
    return s, engine.stars(s)


def test_simple_vs_hard_truth():
    simple = mice_question()  # 4 变量、4 陈述、1 约束
    hard = make_question(
        entities=["A", "B", "C", "D", "E"],
        variables=[Variable(f"{e}_cheese", "boolean") for e in "ABCDE"],
        statements=[
            Statement("我们都偷了", "ALL(cheese)", "A"),
            Statement("我没偷", "!B_cheese", "B"),
            Statement("至少有两只偷了", "COUNT(cheese) >= 2", "C"),
            Statement("只有我偷了", "D_cheese && COUNT(cheese) == 1", "D"),
            Statement("有些没偷", "SOME_NOT(cheese)", "E"),
        ],
        constraints=[Constraint("只有两句真话", "TRUTH_COUNT == 2")],
    )
    assert engine.score(hard) > engine.score(simple)


def test_ordering_scale():
    easy = make_question(
        type="ordering", entities=["A", "B", "C"],
        variables=[Variable(f"rank_{e}", "rank") for e in "ABC"],
        constraints=[Constraint("A比B高", "RANK(A) < RANK(B)"),
                     Constraint("B比C高", "RANK(B) < RANK(C)")],
    )
    hard = make_question(
        type="ordering", entities=["A", "B", "C", "D", "E"],
        variables=[Variable(f"rank_{e}", "rank") for e in "ABCDE"],
        constraints=[Constraint("排序", "ORDER(A, B, C, D, E)"),
                     Constraint("E不在最后", "RANK(E) != 5")],
    )
    assert engine.score(hard) > engine.score(easy)


def test_star_mapping():
    assert engine.stars(0.5) == 1
    assert engine.stars(1.9) == 1
    assert engine.stars(2.0) == 2
    assert engine.stars(3.9) == 2
    assert engine.stars(4.0) == 3
    assert engine.stars(5.9) == 3
    assert engine.stars(6.0) == 4
    assert engine.stars(7.9) == 4
    assert engine.stars(8.0) == 5
    assert engine.stars(9.5) == 5


def test_score_in_range():
    q = mice_question()
    s = engine.score(q)
    assert 0.3 <= s <= 10.0
    assert engine.stars(s) in (1, 2, 3, 4, 5)


def test_apply_writes_back():
    q = mice_question()
    engine.apply(q)
    assert q.difficulty_score == engine.score(q)
    assert q.difficulty == engine.stars(q.difficulty_score)
    assert q.difficulty_level == levels.level_for_score(q.difficulty_score)


def test_metrics_structure():
    q = mice_question()
    m = engine.metrics(q)
    for key in ("entity_count", "constraint_count", "chain_length",
                "negation_count", "conjunction_count", "quantifier_complexity",
                "solution_space", "minimum_reasoning_steps", "truth_count"):
        assert key in m
    assert m["entity_count"] == 4
    assert m["minimum_reasoning_steps"] >= 1


def test_negation_increases_score():
    base = make_question(
        entities=["A", "B", "C"],
        variables=[Variable(f"{e}_x", "boolean") for e in "ABC"],
        constraints=[Constraint("A有x", "A_x")])
    neg = make_question(
        entities=["A", "B", "C"],
        variables=[Variable(f"{e}_x", "boolean") for e in "ABC"],
        constraints=[Constraint("A没有x", "!A_x")])
    assert engine.score(neg) > engine.score(base)


def test_level_from_score_roundtrip():
    for s in (0.0, 2.4, 2.5, 4.9, 5.0, 7.4, 7.5, 10.0):
        lv = levels.level_for_score(s)
        assert 1 <= lv <= 4
