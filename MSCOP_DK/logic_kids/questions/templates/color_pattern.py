"""题型 ⑦ 颜色规律（Pattern）—— 能力：模式与规律 / 归纳推理。

给出一串两种颜色的序列（🔴🔵…），请推断下一个颜色。
规律只使用两种可验证的模式：
  · 交替（period 2）：红蓝红蓝…
  · 成对（period 4）：红红蓝蓝红红蓝蓝…

用布尔变量 c1..c6（is_red）表达整条规律，Solver 穷举验证"下一个颜色唯一确定"。
规律约束只用于验证，不显示给儿童（否则等于把答案写出来）。
"""
from __future__ import annotations

import random

from ...logic import solver
from ...models import Question, Story, Variable, Constraint
from ._base import new_id, now_iso

TYPE = "color_pattern"

COLORS = [("🔴", "红色", True), ("🔵", "蓝色", False)]


def _eq(a: str, b: str) -> str:
    """布尔等价：c_a == c_b。"""
    return f"({a} && {b}) || (!{a} && !{b})"


def _neq(a: str, b: str) -> str:
    """布尔不等：c_a != c_b。"""
    return f"({a} && !{b}) || (!{a} && {b})"


def _build(rng, pattern: str):
    """pattern: "alternate" | "pairs"。生成 c1..c6 的真值。"""
    c = [True] * 6
    if pattern == "alternate":
        for i in range(1, 6):
            c[i] = not c[i - 1]
    else:  # pairs: 红红蓝蓝红红
        c = [True, True, False, False, True, True]

    names = [f"c{i}" for i in range(1, 7)]
    vars_ = [Variable(n, "boolean") for n in names]
    constraints = []
    if pattern == "alternate":
        constraints.append(Constraint(text="", logic="c1"))
        for i in range(2, 7):
            constraints.append(Constraint(text="", logic=_neq(f"c{i}", f"c{i-1}")))
    else:
        constraints.append(Constraint(text="", logic="c1 && c2"))
        constraints.append(Constraint(text="", logic=_neq("c3", "c1")))
        constraints.append(Constraint(text="", logic=_eq("c4", "c3")))
        constraints.append(Constraint(text="", logic=_eq("c5", "c1")))
        constraints.append(Constraint(text="", logic=_eq("c6", "c2")))

    shown = [COLORS[0][0] if v else COLORS[1][0] for v in c[:5]]
    story = Story(
        title="颜色排队",
        text="小圆片按规律排成一排，看看下一个是什么颜色："
             + "".join(shown) + " _",
        roles={},
    )
    question_prompt = "下一个（第 6 个）圆片是什么颜色？"
    options = ["红色", "蓝色"]
    option_logic = ["c6", "!c6"]
    answer = 0 if c[5] else 1
    desc = ("红色和蓝色交替出现" if pattern == "alternate"
            else "两个红色、两个蓝色不断重复")
    explanation = f"规律是{desc}，所以第 6 个圆片是{'红色' if c[5] else '蓝色'}。"
    hints = ["先看看颜色是怎么重复的。", "把前面几个连起来读一读，找出循环。"]

    return Question(
        id=new_id("colorpat"), type=TYPE, story=story, entities=[],
        variables=vars_, statements=[], constraints=constraints,
        question_prompt=question_prompt, options=options,
        option_logic=option_logic, answer=answer, hints=hints,
        explanation=explanation, source="generated", created_at=now_iso(),
    )


def generate(rng: random.Random, max_tries: int = 50):
    """随机生成一道颜色规律题；Solver 验证唯一解。"""
    for _ in range(max_tries):
        pattern = rng.choice(["alternate", "pairs"])
        q = _build(rng, pattern)
        try:
            solutions = solver.solve(q)
        except solver.QuestionError:
            continue
        if len(solutions) == 1:
            return q
    return None
