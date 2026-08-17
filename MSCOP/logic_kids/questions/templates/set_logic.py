"""题型 ⑤ 集合关系（Set Logic：所有/有些/没有）模板。

模型：直接给出每个角色是否有某物品的事实约束（唯一确定世界状态），
问哪一个量化描述正确。三个选项互斥且穷尽：所有 / 都没有 / 部分有。
"""
from __future__ import annotations

import random

from ...models import Question, Story, Variable, Constraint
from .. import themes
from ._base import new_id, now_iso, shuffle_options

TYPE = "set_logic"


def generate(rng: random.Random, n_entities: int = None, max_tries: int = 100):
    if n_entities is None:
        n_entities = rng.choice([3, 4, 4, 5])
    chars = themes.pick_characters(n_entities, rng)
    names = [c[0] for c in chars]
    codes = [chr(ord("A") + i) for i in range(n_entities)]
    code_names = {c: names[i] for i, c in enumerate(codes)}
    item_emoji, item_zh, prop = themes.pick_item(rng)

    subset_true = {c for c in codes if rng.random() < 0.5}

    constraints = []
    for c in codes:
        has = c in subset_true
        constraints.append(Constraint(
            text=f"{code_names[c]}{'有' if has else '没有'}{item_emoji}{item_zh}",
            logic=f"{c}_{prop}" if has else f"!{c}_{prop}"))

    variables = [Variable(f"{c}_{prop}", "boolean") for c in codes]
    story = Story(
        title=f"谁有{item_zh}？",
        text="看看下面的情况，想一想：哪一句话是对的？",
        roles=code_names,
    )
    question_prompt = f"关于{item_zh}，下面哪句话是对的？"

    # 三个互斥且穷尽的量化描述
    opts = [
        f"所有人都有{item_zh}",
        f"谁都没有{item_zh}",
        f"有些人有{item_zh}，有些人没有",
    ]
    logics = [f"ALL({prop})", f"NONE({prop})", f"SOME({prop}) && NOT_ALL({prop})"]
    if len(subset_true) == len(codes):
        correct_idx = 0
    elif len(subset_true) == 0:
        correct_idx = 1
    else:
        correct_idx = 2
    options, option_logic, answer = shuffle_options(rng, opts, logics, correct_idx)

    explanation = _explain(codes, subset_true, item_zh, code_names, options[answer])
    hints = [
        "先数一数：一共有几个人有" + item_zh + "。",
        "“所有”表示一个不少；“都没有”表示一个也没有。",
        "只要有人有、也有人没有，那就是“有些人有，有些人没有”。",
    ]

    return Question(
        id=new_id("set"), type=TYPE, story=story, entities=list(codes),
        variables=variables, statements=[], constraints=constraints,
        question_prompt=question_prompt, options=options, option_logic=option_logic,
        answer=answer, hints=hints, explanation=explanation,
        source="generated", created_at=now_iso(),
    )


def _explain(codes, subset, item_zh, code_names, correct_text):
    have = [code_names[c] for c in codes if c in subset]
    lack = [code_names[c] for c in codes if c not in subset]
    parts = []
    if have:
        parts.append(f"有{item_zh}的是：{'、'.join(have)}")
    if lack:
        parts.append(f"没有{item_zh}的是：{'、'.join(lack)}")
    return "；".join(parts) + f"。\n所以“{correct_text}”是对的。"
