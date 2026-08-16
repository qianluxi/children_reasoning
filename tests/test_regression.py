"""回归测试（专家审查 §十八）：固定"四只老鼠"两道题的行为。

1. 原题（A 全偷 / B 只偷一颗樱桃 / C 没偷 / D 有些人没偷）是**多解题**，
   这正是当初必须换成唯一解变体的原因 —— 此测试把它的解数量固定下来，
   以后改动 Solver / DSL 时若行为变化，测试会立刻报警。
2. 当前种子题（唯一解变体）的行为同样固定：唯一解、答案选项、Validator 通过。
"""
from logic_kids.logic import solver
from logic_kids.models import Question, Story, Variable, Statement, Constraint
from logic_kids.validator.validator import validate
from logic_kids.bank.seed import seed_mice


def original_mice() -> Question:
    """专家意见里的"四只老鼠"原题（多解，不能入库）。

    B 的话"我只偷了一颗樱桃"建模为樱桃变量 B_cherry；
    D 的话"有些人没偷奶酪"按无歧义语义建模为 NOT_ALL(cheese)。
    """
    codes = "ABCD"
    return Question(
        id="regression_original_mice",
        type="truth_statements",
        story=Story(title="四只老鼠（原题）",
                    text="四只老鼠各说了一句话，只有一句是真的。",
                    roles={c: c for c in codes}),
        entities=list(codes),
        variables=[Variable(f"{c}_cheese", "boolean") for c in codes]
                  + [Variable(f"{c}_cherry", "boolean") for c in codes],
        statements=[
            Statement("我们每个人都偷了奶酪", "ALL(cheese)", "A"),
            Statement("我只偷了一颗樱桃", "B_cherry", "B"),
            Statement("我没偷奶酪", "!C_cheese", "C"),
            Statement("有些人没偷奶酪", "NOT_ALL(cheese)", "D"),
        ],
        constraints=[Constraint("只有一只老鼠说了真话", "TRUTH_COUNT == 1")],
        question_prompt="哪些老鼠偷了奶酪？",
        options=["x"], option_logic=["TRUE"], answer=0,
        hints=[], explanation="", source="regression", created_at="",
    )


def test_original_mice_is_multi_solution():
    """原题有 64 个解 → Validator 拒绝 → 证明当年换题是必要的。"""
    solutions = solver.solve(original_mice())
    assert len(solutions) == 64
    report = validate(original_mice())
    assert not report.ok


def test_seed_mice_still_unique_and_correct():
    """当前种子题行为固定：唯一解（全部偷了）、答案选项 0、Validator 通过。"""
    q = seed_mice()
    solutions = solver.solve(q)
    assert len(solutions) == 1
    s = solutions[0]
    assert all(s[f"{e}_cheese"] for e in "ABCD")  # 唯一解：所有老鼠都偷了
    assert q.answer == 0
    assert validate(q).ok
