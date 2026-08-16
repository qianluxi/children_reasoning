"""Validator 测试：好的题目通过，坏的题目被拒绝。"""
import pytest

from logic_kids.models import Question, Story, Variable, Statement, Constraint
from logic_kids.validator.validator import validate
from tests.test_solver import make_question, mice_question


def test_good_mice_passes():
    q = mice_question()
    q.options = ["所有老鼠都偷了奶酪", "有些老鼠没偷奶酪", "没有老鼠偷奶酪"]
    q.option_logic = ["ALL(cheese)", "SOME_NOT(cheese)", "NONE(cheese)"]
    q.answer = 0
    report = validate(q)
    assert report.ok, report.issues


def test_no_solution_rejected():
    q = mice_question()
    q.constraints = [Constraint("所有人说假话", "TRUTH_COUNT == 0")]
    report = validate(q)
    assert not report.ok
    assert any("无解" in i for i in report.issues)


def test_two_correct_options_rejected():
    q = make_question(
        entities=["A", "B"], variables=[Variable("A_cheese", "boolean")],
        statements=[Statement("我偷了", "A_cheese", "A")],
        constraints=[Constraint("说真话的只有一只", "TRUTH_COUNT == 1")],
        options=["选项A", "选项B"], option_logic=["TRUE", "A_cheese"], answer=0,
    )
    report = validate(q)
    assert not report.ok
    assert any("多解" in i for i in report.issues)


def test_answer_mismatch_rejected():
    q = mice_question()
    q.options = ["所有老鼠都偷了奶酪", "有些老鼠没偷奶酪"]
    q.option_logic = ["ALL(cheese)", "SOME_NOT(cheese)"]
    q.answer = 1  # 故意标错
    report = validate(q)
    assert not report.ok
    assert any("不一致" in i for i in report.issues)


def test_absurd_distractor_rejected():
    q = mice_question()
    q.options = ["所有老鼠都偷了奶酪", "B和C都偷了奶酪"]
    q.option_logic = ["ALL(cheese)", "B_cheese && C_cheese && !A_cheese && !D_cheese"]
    q.answer = 0
    # 干扰项"B和C偷了、A和D没偷"在唯一解下为假，但它在全域中存在（不荒谬）——先通过；
    # 换一个真正荒谬的：恒假选项
    q.option_logic = ["ALL(cheese)", "FALSE"]
    report = validate(q)
    assert not report.ok
    assert any("荒谬" in i for i in report.issues)


def test_constant_option_allowed_as_correct():
    # 条件推理"无法判断"：选项逻辑 TRUE 被所有解蕴含，是合法的正确答案
    q = make_question(
        type="conditional", entities=[],
        variables=[Variable("p", "boolean"), Variable("q", "boolean")],
        constraints=[Constraint("如果p那么q", "!p || q"), Constraint("q发生了", "q")],
        options=["p发生了", "p没发生", "无法判断"],
        option_logic=["p", "!p", "TRUE"], answer=2,
    )
    report = validate(q)
    assert report.ok, report.issues


def test_statement_without_reasoning_value_rejected():
    q = mice_question()
    q.statements = [
        Statement("我们每个人都偷了奶酪", "ALL(cheese)", "A"),
        Statement("至少一只老鼠偷了奶酪", "SOME(cheese)", "B"),  # 恒真？不，SOME 可假
        Statement("我没偷奶酪", "!C_cheese", "C"),
    ]
    # 把 A 的话换成恒真的
    q.statements[0] = Statement("所有老鼠要么偷了要么没偷", "A_cheese || !A_cheese", "A")
    report = validate(q)
    assert not report.ok
    assert any("恒" in i for i in report.issues)


def test_duplicate_options_rejected():
    q = mice_question()
    q.options = ["一样", "一样"]
    q.option_logic = ["TRUE", "FALSE"]
    report = validate(q)
    assert not report.ok
