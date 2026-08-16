"""Logic DSL 解析与求值测试。"""
import pytest

from logic_kids.logic import dsl
from logic_kids.logic.ast import EvalContext

VARS = ["A_cheese", "B_cheese", "C_cheese", "D_cheese", "rank_A", "rank_B", "rank_C"]


def eval_expr(text, state):
    node = dsl.parse_expr(text, VARS)
    return node.eval_bool(EvalContext(state))


def test_basic_operators():
    assert eval_expr("A_cheese && B_cheese", {"A_cheese": True, "B_cheese": True})
    assert not eval_expr("A_cheese && B_cheese", {"A_cheese": True, "B_cheese": False})
    assert eval_expr("A_cheese || B_cheese", {"A_cheese": False, "B_cheese": True})
    assert eval_expr("!C_cheese", {"C_cheese": False})
    assert not eval_expr("!C_cheese", {"C_cheese": True})


def test_precedence():
    # ! 高于 && 高于 ||
    # (!A && B) || C ：A=T,B=T,C=F -> (F&&T)||F = F
    assert not eval_expr("!A_cheese && B_cheese || C_cheese", {"A_cheese": True, "B_cheese": True, "C_cheese": False})
    # A || (B && C) ：A=T,B=F,C=F -> T （若误解析成 (A||B)&&C 则得 F）
    assert eval_expr("A_cheese || B_cheese && C_cheese", {"A_cheese": True, "B_cheese": False, "C_cheese": False})
    # 同上，用 C=F 区分 (A||B)&&C
    assert not eval_expr("(A_cheese || B_cheese) && C_cheese", {"A_cheese": True, "B_cheese": False, "C_cheese": False})


def test_parentheses():
    assert not eval_expr("!(A_cheese && B_cheese)", {"A_cheese": True, "B_cheese": True})
    assert eval_expr("(A_cheese || B_cheese) && C_cheese", {"A_cheese": False, "B_cheese": True, "C_cheese": True})


def test_quantifiers():
    # ALL(cheese) 覆盖 A/B/C/D 四个 _cheese 变量，需给齐
    s = {"A_cheese": True, "B_cheese": True, "C_cheese": False, "D_cheese": True}
    assert not eval_expr("ALL(cheese)", s)
    assert eval_expr("SOME(cheese)", s)
    assert not eval_expr("NONE(cheese)", s)
    assert eval_expr("SOME_NOT(cheese)", s)
    assert eval_expr("ALL(cheese)", {**s, "C_cheese": True})
    assert eval_expr("NONE(cheese)", {"A_cheese": False, "B_cheese": False, "C_cheese": False, "D_cheese": False})


def test_not_all_quantifier():
    # NOT_ALL = "不是所有"（至少一个没有）；SOME_NOT 是它的旧别名，语义相同
    s = {"A_cheese": True, "B_cheese": True, "C_cheese": False, "D_cheese": True}
    assert eval_expr("NOT_ALL(cheese)", s)
    assert not eval_expr("NOT_ALL(cheese)", {**s, "C_cheese": True})
    assert eval_expr("NOT_ALL(cheese)", {"A_cheese": False, "B_cheese": False,
                                         "C_cheese": False, "D_cheese": False})
    assert eval_expr("SOME_NOT(cheese)", s) == eval_expr("NOT_ALL(cheese)", s)
    # "有些人有，有些人没有" = SOME && NOT_ALL（至少要有一个有）
    s2 = {"A_cheese": True, "B_cheese": False, "C_cheese": False, "D_cheese": False}
    assert eval_expr("SOME(cheese) && NOT_ALL(cheese)", s2)
    assert not eval_expr("SOME(cheese) && NOT_ALL(cheese)",
                         {"A_cheese": False, "B_cheese": False, "C_cheese": False, "D_cheese": False})


def test_count():
    s = {"A_cheese": True, "B_cheese": True, "C_cheese": False, "D_cheese": False}
    assert eval_expr("COUNT(cheese) >= 2", s)
    assert eval_expr("COUNT(cheese) == 2", s)
    assert not eval_expr("COUNT(cheese) == 3", s)
    assert eval_expr("COUNT(cheese) <= 2", s)


def test_exactly():
    assert eval_expr("EXACTLY(1, A_cheese, B_cheese)", {"A_cheese": True, "B_cheese": False})
    assert not eval_expr("EXACTLY(1, A_cheese, B_cheese)", {"A_cheese": True, "B_cheese": True})


def test_rank_comparison():
    s = {"rank_A": 1, "rank_B": 2, "rank_C": 3}
    assert eval_expr("RANK(A) < RANK(B)", s)
    assert eval_expr("RANK(A) < RANK(B) < RANK(C)", s)
    assert eval_expr("RANK(A) == 1", s)
    assert not eval_expr("RANK(A) == 2", s)
    assert eval_expr("RANK(C) != RANK(A)", s)


def test_truth_count_constraint():
    node = dsl.parse_constraint("TRUTH_COUNT == 1", VARS)
    assert node.eval_bool(EvalContext({}, [True, False, False]))
    assert not node.eval_bool(EvalContext({}, [True, True, False]))
    node2 = dsl.parse_constraint("TRUTH_COUNT >= 1", VARS)
    assert node2.eval_bool(EvalContext({}, [False, False, True]))


def test_order_constraint():
    node = dsl.parse_constraint("ORDER(A, B, C)", VARS)
    assert node.eval_bool(EvalContext({"rank_A": 1, "rank_B": 2, "rank_C": 3}))
    assert not node.eval_bool(EvalContext({"rank_A": 2, "rank_B": 1, "rank_C": 3}))


def test_syntax_errors():
    with pytest.raises(dsl.DSLSyntaxError):
        dsl.parse_expr("A_cheese &&", VARS)
    with pytest.raises(dsl.DSLSyntaxError):
        dsl.parse_expr("UNKNOWN_var", VARS)
    with pytest.raises(dsl.DSLSyntaxError):
        dsl.parse_expr("ALL(nothing_matches)", VARS)
    with pytest.raises(dsl.DSLSyntaxError):
        dsl.parse_expr("A_cheese < 2", VARS)  # 布尔变量不能比较


def test_chain_length_and_depth():
    assert dsl.chain_length(["RANK(A) < RANK(B) < RANK(C)"], VARS) == 2
    assert dsl.chain_length(["RANK(A) < RANK(B)"], VARS) == 1
    assert dsl.chain_length(["A_cheese"], VARS) == 0
    # !(!A && B)：外层! + && + 内层! + 叶子 = 深度 4
    assert dsl.max_depth(["!(!A_cheese && B_cheese)"], VARS) == 4
