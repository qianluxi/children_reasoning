"""Difficulty Scoring Engine（专家意见第四节）。

难度不要人工简单标成 1、2、3，而是根据题目结构自动评分：

    difficulty_score =
        变量数量          （题目规模）
      + 事实/条件数量     （信息量）
      + 逻辑嵌套深度      （表达式复杂度）
      + 推理链长度        （链式比较 RANK(A)<RANK(B)<RANK(C) 的长度）
      + 干扰项数量        （选项数 - 2）
      + 解空间大小        （log10(2^n) 或 log10(n!)）
      + 真假话约束加分    （TRUTH_COUNT 是额外推理负担）

然后映射为星级：
    0 ~ 2   ★
    2 ~ 4   ★★
    4 ~ 6   ★★★
    6 ~ 8   ★★★★
    8 ~ 10  ★★★★★
"""
from __future__ import annotations

import math

from ..logic import dsl, solver
from ..models import Question

# 权重（启发式，可在数据积累后校准）
W_VARS = 0.45      # 每个变量
W_FACTS = 0.35     # 每条陈述/约束
W_DEPTH = 0.70     # 每层嵌套
W_CHAIN = 0.75     # 每节推理链
W_OPTIONS = 0.15   # 每多出的一个选项（干扰项）
W_SPACE = 0.20     # 解空间 log10
W_TRUTH = 0.80     # 每个 TRUTH_COUNT 约束
OFFSET = 2.4       # 基线（简单题的低分）


def score(question: Question) -> float:
    """返回 0..10 的难度分。"""
    varnames = question.variable_names()
    n_vars = len(question.variables)
    n_facts = len(question.statements) + len(question.constraints)

    all_logics = (
        [s.logic for s in question.statements]
        + [c.logic for c in question.constraints]
        + list(question.option_logic)
    )
    depth = dsl.max_depth(all_logics, varnames)
    chain = dsl.chain_length([c.logic for c in question.constraints], varnames)
    n_truth = sum(1 for c in question.constraints if c.logic.strip().startswith("TRUTH_COUNT"))

    try:
        space = math.log10(max(solver.domain_size(question), 1))
    except solver.QuestionError:
        space = 0.0

    s = (
        W_VARS * n_vars
        + W_FACTS * n_facts
        + W_DEPTH * depth
        + W_CHAIN * chain
        + W_OPTIONS * max(len(question.options) - 2, 0)
        + W_SPACE * space
        + W_TRUTH * n_truth
        - OFFSET
    )
    return round(min(max(s, 0.3), 10.0), 2)


def stars(score_value: float) -> int:
    if score_value < 2:
        return 1
    if score_value < 4:
        return 2
    if score_value < 6:
        return 3
    if score_value < 8:
        return 4
    return 5


def apply(question: Question) -> Question:
    """计算难度并写回题目对象。"""
    s = score(question)
    question.difficulty_score = s
    question.difficulty = stars(s)
    return question
