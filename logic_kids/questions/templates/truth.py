"""题型 ③ 真假话（Truth-Tellers）模板 —— 专家意见的旗舰题型。

模型：N 个角色各说一句关于"谁有某物品"的话，约束"恰好 k 句为真"。
布尔域枚举 2^N 状态，Solver 求唯一解；只有唯一解的实例才被接受。
"""
from __future__ import annotations

import random

from ...logic import solver
from ...logic import dsl
from ...logic.ast import EvalContext
from ...models import Question, Story, Variable, Statement, Constraint
from .. import themes
from ._base import new_id, now_iso, shuffle_options, describe_subset

TYPE = "truth_statements"
VERB = "有"


def _statement_pool(codes: list, prop: str, item_zh: str) -> list:
    """返回 [(文字, 逻辑, 说话者)] 候选池。说话者为实体代号。"""
    n = len(codes)
    pool = []
    group = [
        (f"我们每个人都有{item_zh}", "ALL({p})".format(p=prop)),
        (f"我们谁都没有{item_zh}", "NONE({p})".format(p=prop)),
        (f"我们中至少有一个有{item_zh}", "SOME({p})".format(p=prop)),
        (f"我们中有些人没有{item_zh}", "SOME_NOT({p})".format(p=prop)),
    ]
    for m in range(1, n):
        group.append((f"恰好有{m}个人有{item_zh}", f"COUNT({prop}) == {m}"))
    for m in range(2, n):
        group.append((f"至少有{m}个人有{item_zh}", f"COUNT({prop}) >= {m}"))
    for text, logic in group:
        for c in codes:
            pool.append((text, logic, c))
    for c in codes:
        pool.append((f"我有{item_zh}", f"{c}_{prop}", c))
        pool.append((f"我没有{item_zh}", f"!{c}_{prop}", c))
    for c in codes:
        for other in codes:
            if other == c:
                continue
            pool.append((f"{other}有{item_zh}", f"{other}_{prop}", c))
            pool.append((f"{other}没有{item_zh}", f"!{other}_{prop}", c))
    for c in codes:
        others = [o for o in codes if o != c]
        for i in range(len(others)):
            for j in range(i + 1, len(others)):
                y, z = others[i], others[j]
                pool.append((f"{y}和{z}都有{item_zh}", f"{y}_{prop} && {z}_{prop}", c))
                pool.append((f"{y}或{z}至少有一个有{item_zh}", f"{y}_{prop} || {z}_{prop}", c))
    return pool


def _random_assignment(rng, codes, prop, item_zh):
    pool = _statement_pool(codes, prop, item_zh)
    statements = []
    for c in codes:
        candidates = [p for p in pool if p[2] == c]
        text, logic, _ = rng.choice(candidates)
        statements.append((text, logic, c))
    return statements


def _localize(text: str, code_names: dict) -> str:
    for code, name in code_names.items():
        text = text.replace(code, name)
    return text


def _build_question(rng, codes, names, prop, item_emoji, item_zh, k, statements, solution):
    varnames = [f"{c}_{prop}" for c in codes]
    code_names = {c: names[i] for i, c in enumerate(codes)}
    story_title = f"谁有{item_zh}？"
    story_text = (
        f"{len(codes)}个小伙伴在一起，他们可能藏了{item_emoji}{item_zh}。"
        f"每个人都说了一句话。已知他们里面恰好有 {k} 句是真话。到底谁有{item_zh}呢？"
    )
    story = Story(title=story_title, text=story_text, roles=code_names)
    variables = [Variable(v, "boolean") for v in varnames]
    stmt_objs = [Statement(text=_localize(t, code_names), logic=l, speaker=c)
                 for t, l, c in statements]
    constraint = Constraint(text=f"恰好有 {k} 句是真话", logic=f"TRUTH_COUNT == {k}")

    subset_true = {c for c in codes if solution[f"{c}_{prop}"]}
    opts, logics = [], []
    correct_text, correct_logic = describe_subset(codes, subset_true, prop, VERB, item_zh, code_names)
    opts.append(correct_text)
    logics.append(correct_logic)
    all_subsets = _all_subsets(codes)
    rng.shuffle(all_subsets)
    for sub in all_subsets:
        if sub == subset_true:
            continue
        t, l = describe_subset(codes, sub, prop, VERB, item_zh, code_names)
        if t not in opts:
            opts.append(t)
            logics.append(l)
        if len(opts) >= 4:
            break
    options, option_logic, answer = shuffle_options(rng, opts, logics, 0)

    hints, explanation = _explain(codes, names, prop, item_zh, k, statements, solution, subset_true)

    return Question(
        id=new_id("truth"), type=TYPE, story=story, entities=list(codes),
        variables=variables, statements=stmt_objs, constraints=[constraint],
        question_prompt=f"到底谁有{item_zh}？", options=options,
        option_logic=option_logic, answer=answer, hints=hints,
        explanation=explanation, source="generated", created_at=now_iso(),
    )


def _all_subsets(codes):
    from itertools import combinations
    subs = []
    for r in range(len(codes) + 1):
        for combo in combinations(codes, r):
            subs.append(set(combo))
    return subs


def _explain(codes, names, prop, item_zh, k, statements, solution, subset_true):
    code_names = {c: names[i] for i, c in enumerate(codes)}
    ctx = EvalContext(solution)
    lines, true_speakers = [], []
    for text, logic, c in statements:
        node = dsl.parse_expr(logic, list(solution.keys()))
        truth = node.eval_bool(ctx)
        mark = "真话 ✔" if truth else "假话 ✘"
        lines.append(f"· {code_names[c]} 说“{_localize(text, code_names)}”——这是{mark}")
        if truth:
            true_speakers.append(code_names[c])
    if subset_true:
        who = "、".join(code_names[c] for c in codes if c in subset_true)
        conclusion = f"所以有{item_zh}的是：{who}。"
    else:
        conclusion = f"所以其实谁都没有{item_zh}。"
    explanation = "\n".join(lines) + f"\n正好有 {k} 句真话（{('、'.join(true_speakers)) or '无'}），{conclusion}"
    hints = [
        f"先数一数：题目说恰好有 {k} 句是真话。",
        "试着假设某句话是真的，看看其它话会不会矛盾。",
        f"把每句话的真假列出来，凑出恰好 {k} 句真话的那种情况就是答案。",
    ]
    return hints, explanation


def generate(rng: random.Random, n_entities: int = None, max_tries: int = 400):
    """随机生成一道真假话题；保证唯一解。失败返回 None。"""
    if n_entities is None:
        n_entities = rng.choice([3, 4, 4, 5])
    chars = themes.pick_characters(n_entities, rng)
    names = [c[0] for c in chars]
    codes = [chr(ord("A") + i) for i in range(n_entities)]
    item_emoji, item_zh, prop = themes.pick_item(rng)
    k = rng.randint(1, n_entities - 1)
    if rng.random() < 0.15:
        k = rng.choice([0, n_entities])

    for _ in range(max_tries):
        statements = _random_assignment(rng, codes, prop, item_zh)
        variables = [Variable(f"{c}_{prop}", "boolean") for c in codes]
        stmt_objs = [Statement(text=t, logic=l, speaker=c) for t, l, c in statements]
        tmp = Question(
            id="tmp", type=TYPE, story=Story("t", "t", {}), entities=list(codes),
            variables=variables, statements=stmt_objs,
            constraints=[Constraint("", f"TRUTH_COUNT == {k}")],
            question_prompt="", options=["x"], option_logic=["TRUE"], answer=0,
            hints=[], explanation="",
        )
        try:
            solutions = solver.solve(tmp)
        except solver.QuestionError:
            continue
        if len(solutions) == 1:
            return _build_question(rng, codes, names, prop, item_emoji, item_zh,
                                   k, statements, solutions[0])
    return None
