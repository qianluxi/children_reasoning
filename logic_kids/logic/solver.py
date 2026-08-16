"""Solver：穷举所有状态并过滤约束，得到全部解。

专家意见第五、六节：Solver 是整个系统的裁判 —— 题目生成后不能相信生成器，
必须枚举所有可能状态、检查约束、确认解的数量；只有唯一解的题目才进入正式题库。

支持两类变量域：
  - boolean：2^n 个状态（真假话 / 集合 / 条件推理）
  - rank：n! 个全排列状态（顺序 / 排除），rank 1 = 最高 / 第一
"""
from __future__ import annotations

from itertools import product, permutations

from ..models import Question
from . import dsl
from .ast import EvalContext


class QuestionError(ValueError):
    """题目本身无法建模（DSL 解析失败等）。"""


def _domain_kind(question: Question) -> str:
    kinds = {v.type for v in question.variables}
    if not kinds:
        raise QuestionError(f"题目 {question.id} 没有任何变量")
    if len(kinds) > 1:
        raise QuestionError(f"题目 {question.id} 混合了多种变量类型: {kinds}")
    return kinds.pop()


def _all_states(question: Question) -> list:
    """枚举全部可能状态（不做任何约束过滤）。"""
    kind = _domain_kind(question)
    names = [v.name for v in question.variables]
    if kind == "boolean":
        states = []
        for combo in product((False, True), repeat=len(names)):
            states.append(dict(zip(names, combo)))
        return states
    if kind == "rank":
        n = len(names)
        states = []
        for perm in permutations(range(1, n + 1)):
            states.append(dict(zip(names, perm)))
        return states
    raise QuestionError(f"未知变量类型: {kind}")


def solve(question: Question) -> list:
    """返回满足全部约束的状态列表（每个状态是 {变量名: 值}）。"""
    varnames = question.variable_names()
    try:
        parsed_statements = [dsl.parse_expr(s.logic, varnames) for s in question.statements]
        parsed_constraints = [dsl.parse_constraint(c.logic, varnames) for c in question.constraints]
    except dsl.DSLSyntaxError as e:
        raise QuestionError(f"题目 {question.id} 的 DSL 解析失败: {e}") from e

    solutions = []
    for state in _all_states(question):
        truth = [n.eval_bool(EvalContext(state)) for n in parsed_statements]
        ctx = EvalContext(state, truth)
        if all(c.eval_bool(ctx) for c in parsed_constraints):
            solutions.append(state)
    return solutions


def option_truth_counts(question: Question, solutions: list) -> list:
    """每个选项在全部解中为真的次数（用于验证唯一正确选项）。"""
    varnames = question.variable_names()
    counts = []
    for expr in question.option_logic:
        try:
            node = dsl.parse_expr(expr, varnames)
        except dsl.DSLSyntaxError:
            counts.append(-1)
            continue
        counts.append(sum(1 for s in solutions if node.eval_bool(EvalContext(s))))
    return counts


def statement_domain_truth(question: Question) -> list:
    """每个陈述句在全域中是否为恒真/恒假（用于验证陈述句有推理价值）。"""
    varnames = question.variable_names()
    results = []
    for s in question.statements:
        try:
            node = dsl.parse_expr(s.logic, varnames)
        except dsl.DSLSyntaxError:
            results.append((None, None))
            continue
        true_any = false_any = False
        for state in _all_states(question):
            if node.eval_bool(EvalContext(state)):
                true_any = True
            else:
                false_any = True
            if true_any and false_any:
                break
        results.append((true_any, false_any))
    return results


def domain_size(question: Question) -> int:
    """状态空间大小（难度引擎使用）。"""
    kind = _domain_kind(question)
    n = len(question.variables)
    if kind == "boolean":
        return 2 ** n
    if kind == "rank":
        result = 1
        for i in range(2, n + 1):
            result *= i
        return result
    raise QuestionError(f"未知变量类型: {kind}")
