"""题型 ⑥ 配对推理（Matching）—— 专家未来题型表 ⑦"配对问题"。

模型：N 个小朋友各自"喜欢"一种点心/物品，且每种只有一个人喜欢（一一对应）。
用 rank 域表达配对：rank_<child> = 物品编号（1..N），排列域天然保证
"每种物品恰好被一个人喜欢"，等价于一个双射。

两种问法（交替出现，增加变化）：
  A. 谁喜欢某物？          选项 = 小朋友名字
  B. 某小朋友喜欢什么？    选项 = 物品名字

线索 = 若干正向确定（"小明喜欢奶酪"）+ 若干负向排除（"小红不喜欢苹果"），
是否唯一解一律交给 Solver 判定，不唯一就重新生成。
"""
from __future__ import annotations

import random

from ...logic import solver
from ...models import Question, Story, Variable, Constraint
from .. import themes
from ._base import new_id, now_iso, shuffle_options

TYPE = "matching"
VERB = "喜欢"


def _build(rng, codes, names, items, assignment, ask_form):
    """assignment: {code: 物品编号(1..n)}。"""
    n = len(codes)
    code_names = {c: names[i] for i, c in enumerate(codes)}
    item_emoji = [it[0] for it in items]
    item_zh = [it[1] for it in items]
    variables = [Variable(f"rank_{c}", "rank") for c in codes]

    # 线索：n-1 条正向确定 + 其余孩子的负向排除
    constraints = []
    pos = list(codes)[:-1]
    rng.shuffle(pos)
    for c in pos:
        idx = assignment[c]
        constraints.append(Constraint(
            text=f"{code_names[c]}{VERB}{item_emoji[idx-1]}{item_zh[idx-1]}",
            logic=f"RANK({c}) == {idx}"))
    for c in codes:
        if c in pos:
            continue
        others = [i for i in range(1, n + 1) if i != assignment[c]]
        idx = rng.choice(others)
        constraints.append(Constraint(
            text=f"{code_names[c]}不{VERB}{item_emoji[idx-1]}{item_zh[idx-1]}",
            logic=f"RANK({c}) != {idx}"))

    story = Story(
        title="谁喜欢什么？",
        text=(f"{n}个小伙伴，每人{VERB}一种点心，"
              f"而且每种点心只有一个人{VERB}。根据下面的线索，想想谁{VERB}什么。"),
        roles=code_names,
    )

    hints = [
        "先把“确定喜欢”的配对找出来。",
        "每个小朋友只能喜欢一种，每种点心也只有一个人喜欢，用排除法试试。",
    ]
    order_text = "；".join(
        f"{code_names[c]}{VERB}{item_emoji[assignment[c]-1]}{item_zh[assignment[c]-1]}"
        for c in codes)
    explanation = f"按线索一一配对：{order_text}。"

    if ask_form == "who_likes_item":
        target_item = rng.randint(1, n)
        question_prompt = f"谁{VERB}{item_emoji[target_item-1]}{item_zh[target_item-1]}？"
        options = [code_names[c] for c in codes]
        option_logic = [f"RANK({c}) == {target_item}" for c in codes]
        correct_idx = codes.index(
            next(c for c in codes if assignment[c] == target_item))
        options, option_logic, answer = shuffle_options(
            rng, options, option_logic, correct_idx)
    else:
        target_child = rng.choice(codes)
        question_prompt = f"{code_names[target_child]}{VERB}什么？"
        options = [f"{e}{zh}" for e, zh in zip(item_emoji, item_zh)]
        option_logic = [f"RANK({target_child}) == {i+1}" for i in range(n)]
        options, option_logic, answer = shuffle_options(
            rng, options, option_logic, assignment[target_child] - 1)

    return Question(
        id=new_id("match"), type=TYPE, story=story, entities=list(codes),
        variables=variables, statements=[], constraints=constraints,
        question_prompt=question_prompt, options=options,
        option_logic=option_logic, answer=answer, hints=hints,
        explanation=explanation, source="generated", created_at=now_iso(),
    )


def generate(rng: random.Random, n_entities: int = None, max_tries: int = 300):
    """随机生成一道配对推理题；Solver 验证唯一解，失败返回 None。"""
    if n_entities is None:
        n_entities = rng.choice([3, 3, 4])
    chars = themes.pick_characters(n_entities, rng)
    names = [c[0] for c in chars]
    codes = [chr(ord("A") + i) for i in range(n_entities)]
    items = rng.sample(themes.ITEMS, n_entities)

    for _ in range(max_tries):
        perm = list(range(1, n_entities + 1))
        rng.shuffle(perm)
        assignment = {codes[i]: perm[i] for i in range(n_entities)}
        ask_form = rng.choice(["who_likes_item", "what_child_likes"])
        q = _build(rng, codes, names, items, assignment, ask_form)
        try:
            solutions = solver.solve(q)
        except solver.QuestionError:
            continue
        if len(solutions) == 1:
            return q
    return None
