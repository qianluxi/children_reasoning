"""Solver 测试：四只老鼠种子题 + 典型题型建模。"""
from logic_kids.logic import solver
from logic_kids.models import Question, Story, Variable, Statement, Constraint


def make_question(**kw):
    defaults = dict(
        id="t", type="truth_statements", story=Story("t", "t", {"A": "A"}),
        entities=["A", "B", "C", "D"], variables=[], statements=[], constraints=[],
        question_prompt="?", options=["x"], option_logic=["TRUE"], answer=0,
        hints=[], explanation="",
    )
    defaults.update(kw)
    return Question(**defaults)


# "四只老鼠"种子题（经 Solver 验证的唯一解变体，见 bank/seed.py）
def mice_question():
    return make_question(
        id="mice",
        variables=[Variable(n, "boolean") for n in
                   ["A_cheese", "B_cheese", "C_cheese", "D_cheese"]],
        statements=[
            Statement("有些老鼠没偷奶酪", "SOME_NOT(cheese)", "A"),
            Statement("至少一只老鼠偷了奶酪", "SOME(cheese)", "B"),
            Statement("没有老鼠偷奶酪", "NONE(cheese)", "C"),
            Statement("只有我偷了奶酪", "D_cheese && COUNT(cheese) == 1", "D"),
        ],
        constraints=[Constraint("只有一只老鼠说真话", "TRUTH_COUNT == 1")],
    )


def test_mice_unique_solution():
    solutions = solver.solve(mice_question())
    assert len(solutions) == 1
    s = solutions[0]
    assert all(s[f"{e}_cheese"] for e in "ABCD")  # 唯一解：所有老鼠都偷了奶酪


def test_ordering_unique():
    q = make_question(
        type="ordering", entities=["A", "B", "C"],
        variables=[Variable(f"rank_{e}", "rank") for e in "ABC"],
        constraints=[
            Constraint("A比B高", "RANK(A) < RANK(B)"),
            Constraint("B比C高", "RANK(B) < RANK(C)"),
        ],
    )
    solutions = solver.solve(q)
    assert len(solutions) == 1
    assert solutions[0]["rank_A"] == 1


def test_conditional_entailed():
    # 如果 p 那么 q，p 发生了 -> q 一定发生（modus ponens，唯一解）
    q = make_question(
        type="conditional", entities=[],
        variables=[Variable("p", "boolean"), Variable("q", "boolean")],
        constraints=[
            Constraint("如果p那么q", "!p || q"),
            Constraint("p发生了", "p"),
        ],
    )
    solutions = solver.solve(q)
    assert len(solutions) == 1
    assert solutions[0] == {"p": True, "q": True}


def test_conditional_not_entailed():
    # 如果 p 那么 q，q 发生了 -> p 无法判断（两个解）
    q = make_question(
        type="conditional", entities=[],
        variables=[Variable("p", "boolean"), Variable("q", "boolean")],
        constraints=[
            Constraint("如果p那么q", "!p || q"),
            Constraint("q发生了", "q"),
        ],
    )
    solutions = solver.solve(q)
    assert len(solutions) == 2
    assert {s["p"] for s in solutions} == {True, False}


def test_set_logic():
    q = make_question(
        type="set_logic", entities=["A", "B", "C"],
        variables=[Variable(f"{e}_fish", "boolean") for e in "ABC"],
        constraints=[
            Constraint("小猫吃鱼", "A_fish"),
            Constraint("小狗吃鱼", "B_fish"),
            Constraint("小兔不吃鱼", "!C_fish"),
        ],
    )
    solutions = solver.solve(q)
    assert len(solutions) == 1
    assert solutions[0] == {"A_fish": True, "B_fish": True, "C_fish": False}


def test_domain_size():
    q = mice_question()
    assert solver.domain_size(q) == 16
    q2 = make_question(type="ordering", variables=[Variable(f"rank_{e}", "rank") for e in "ABCDE"],
                       constraints=[])
    assert solver.domain_size(q2) == 120


def test_option_truth_counts():
    q = mice_question()
    q.options = ["所有老鼠都偷了奶酪", "有些老鼠没偷奶酪", "没有老鼠偷奶酪"]
    q.option_logic = ["ALL(cheese)", "SOME_NOT(cheese)", "NONE(cheese)"]
    q.answer = 0
    solutions = solver.solve(q)
    counts = solver.option_truth_counts(q, solutions)
    assert counts == [1, 0, 0]
