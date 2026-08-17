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
      + 否定/合取数量     （专家指标：转换负担）
      + 最小推理步数      （专家指标：minimum_reasoning_steps，启发式代理）

连续分 → 用户可见等级由 difficulty/levels.py 统一映射（1..4），
星级（1..5）保留为内部粗分带，供自适应引擎等内部逻辑使用。
"""
from __future__ import annotations

import math

from ..logic import dsl, solver, ast
from ..models import Question
from .. import taxonomy
from .. import child_suitability
from . import levels

# 权重（启发式，可在数据积累后校准）
W_VARS = 0.45       # 每个变量
W_FACTS = 0.35      # 每条陈述/约束
W_DEPTH = 0.70      # 每层嵌套
W_CHAIN = 0.75      # 每节推理链
W_OPTIONS = 0.15    # 每多出的一个选项（干扰项）
W_SPACE = 0.20      # 解空间 log10
W_TRUTH = 0.80      # 每个 TRUTH_COUNT 约束
W_NEG = 0.18        # 每处否定（"反过来想"负担）
W_AND = 0.10        # 每处合取（同时成立负担）
W_STEPS = 0.05      # 每个最小推理步数（专家最看重的指标）
OFFSET = 2.4        # 基线（简单题的低分）

# 题型校准：结构公式对某些"直观题型"会系统性高估（如颜色规律题里
# 否定算子数量虚高，但儿童实际只是"找循环"）。这里的修正值来自人工校准，
# 属于难度引擎的一部分（专家意见第十六节：难度 = 多维而非单一公式）。
_TYPE_ADJUST = {
    "color_pattern": -5.5,
}


def _parsed_nodes(question: Question) -> list:
    """解析全部逻辑表达式（陈述/约束/选项），解析失败的静默跳过。"""
    varnames = question.variable_names()
    texts = (
        [s.logic for s in question.statements]
        + [c.logic for c in question.constraints]
        + list(question.option_logic)
    )
    nodes = []
    for text in texts:
        try:
            nodes.append(dsl.parse_constraint(text, varnames))
        except dsl.DSLSyntaxError:
            continue
    return nodes


def _walk(node):
    """遍历 AST 节点（含 And/Or/Exactly 的 children、Not 的子节点、比较的操作数）。"""
    yield node
    children = getattr(node, "children", None)
    if children:
        for c in children:
            if isinstance(c, ast.LogicNode):
                yield from _walk(c)
    if isinstance(node, ast.NotNode):
        yield from _walk(node.child)
    if isinstance(node, ast.CompareNode):
        for operand in (node.lhs, node.rhs):
            if isinstance(operand, ast.LogicNode):
                yield from _walk(operand)


def _min_steps(question: Question, chain: int, neg: int, conj: int,
               quant: int, n_truth: int) -> int:
    """最小推理步数的启发式代理。

    真实"最少推理步数"需要证明搜索；这里用结构代理并保证随复杂度单调：
      · 每条事实/约束至少 1 步消化；
      · 链式排序每多一节 +1 步；
      · 每处否定/合取/量词各 +1 步转换负担；
      · 真假话 TRUTH_COUNT 需要把每句话逐个假设检验。
    """
    n_facts = len(question.statements) + len(question.constraints)
    steps = n_facts + max(chain - 1, 0) + neg + conj + quant
    if n_truth:
        steps += max(len(question.statements) - 1, 0)
    return max(steps, 1)


def metrics(question: Question) -> dict:
    """结构化难度指标（专家意见第四节列出的可扩展指标）。"""
    varnames = question.variable_names()
    nodes = _parsed_nodes(question)
    all_nodes = [n for node in nodes for n in _walk(node)]
    neg = sum(1 for n in all_nodes if isinstance(n, ast.NotNode))
    conj = sum(1 for n in all_nodes if isinstance(n, ast.AndNode))
    quant = sum(1 for n in all_nodes if isinstance(n, ast.QuantifierNode))
    chain = dsl.chain_length([c.logic for c in question.constraints], varnames)
    depth = dsl.max_depth(
        [s.logic for s in question.statements]
        + [c.logic for c in question.constraints]
        + list(question.option_logic),
        varnames,
    )
    n_truth = sum(1 for c in question.constraints
                  if c.logic.strip().startswith("TRUTH_COUNT"))
    try:
        space = math.log10(max(solver.domain_size(question), 1))
    except solver.QuestionError:
        space = 0.0
    steps = _min_steps(question, chain, neg, conj, quant, n_truth)
    return {
        "entity_count": len(question.entities),
        "constraint_count": len(question.statements) + len(question.constraints),
        "chain_length": chain,
        "max_depth": depth,
        "negation_count": neg,
        "conjunction_count": conj,
        "quantifier_complexity": quant,
        "solution_space": round(space, 3),
        "truth_count": n_truth,
        "minimum_reasoning_steps": steps,
    }


def score(question: Question) -> float:
    """返回 0..10 的难度分。"""
    n_vars = len(question.variables)
    m = metrics(question)
    s = (
        W_VARS * n_vars
        + W_FACTS * m["constraint_count"]
        + W_DEPTH * m["max_depth"]
        + W_CHAIN * m["chain_length"]
        + W_OPTIONS * max(len(question.options) - 2, 0)
        + W_SPACE * m["solution_space"]
        + W_TRUTH * m["truth_count"]
        + W_NEG * m["negation_count"]
        + W_AND * m["conjunction_count"]
        + W_STEPS * m["minimum_reasoning_steps"]
        - OFFSET
    )
    s += _TYPE_ADJUST.get(question.type, 0.0)
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


def difficulty_profile(question: Question) -> dict:
    """二维难度（专家意见第十六节）：5 个维度的 1..5 分。

    两个难度相同的问题，对儿童的"困难点"可能完全不同：
    逻辑难语言简单 vs 语言难逻辑简单。这里把难度拆开描述。
    """
    m = metrics(question)

    def _clamp(v: float) -> int:
        return max(1, min(5, int(round(v))))

    # 推理深度：链长 + 真假话假设 + 否定转换
    reasoning_depth = _clamp(
        1.0 + 0.6 * m["chain_length"] + 0.5 * m["truth_count"]
        + 0.3 * m["negation_count"])
    # 认知负荷：实体/条件/嵌套
    cognitive_load = _clamp(
        1.0 + 0.3 * m["entity_count"] + 0.2 * m["constraint_count"]
        + 0.3 * m["max_depth"])
    # 语言负担：题干/约束/选项的平均长度；外部未翻译英文 +1
    texts = [question.story.text, question.question_prompt]
    texts += [c.text for c in question.constraints]
    texts += list(question.options)
    avg_len = sum(len(t) for t in texts) / max(len(texts), 1)
    language = _clamp(1.0 + avg_len / 40.0)
    if question.source_info and question.source_info.type == "external" \
            and not question.translations:
        language = min(5, language + 1)
    # 干扰强度：选项越多越容易混淆（后续可加选项相似度）
    distractor = _clamp(1.0 + max(len(question.options) - 3, 0) * 0.8)
    # 计算负担：数学/应用题类更高（当前内置题型基本为 1）
    computation = 3 if question.type in ("math_word", "arithmetic") else 1
    return {
        "cognitive_load": cognitive_load,
        "reasoning_depth": reasoning_depth,
        "language_complexity": language,
        "distractor_strength": distractor,
        "computation_load": computation,
    }


def age_for(question: Question) -> str:
    """按难度等级 + 题型/来源推断建议年龄分级（A..D）。"""
    lv = question.difficulty_level or levels.level_for_score(question.difficulty_score)
    age = taxonomy.LEVEL_AGE.get(lv, "B")
    rank = {"A": 0, "B": 1, "C": 2, "D": 3}
    # 外部未翻译/阅读负担重的题，年龄下限提高一档
    if question.type == "external_text" and rank[age] < 3:
        age = "D"
    # 直观/低龄友好能力（模式、关系、分类）：难度再高也控制在 C 以内
    if question.category in ("pattern", "relation", "classification") \
            and rank[age] > 2:
        age = "C"
    return age


def apply(question: Question) -> Question:
    """计算难度并写回题目对象（连续分 + 用户可见等级 + 内部星级）。"""
    s = score(question)
    question.difficulty_score = s
    question.difficulty_level = levels.level_for_score(s)
    question.difficulty = stars(s)
    question.difficulty_profile = difficulty_profile(question)
    question.age_range = age_for(question)
    question.child_suitability = child_suitability.evaluate(question)
    return question
