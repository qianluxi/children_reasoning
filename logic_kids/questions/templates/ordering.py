"""题型 ② 顺序排列（Ordering）模板。

模型：N 个角色排成一列（rank 1..N，1=最前/最高/第一）。
约束是若干两两比较或链式比较；目标是唯一确定某个角色的位置或整列顺序。
排列域枚举 n! 状态，Solver 求唯一解。
"""
from __future__ import annotations

import random

from ...logic import solver
from ...models import Question, Story, Variable, Statement, Constraint
from .. import themes
from ._base import new_id, now_iso, shuffle_options

TYPE = "ordering"

# 比较关系的说法（用于排序：谁在谁前面 / 谁比谁高）
RELATIONS = [
    ("排在", "前面", "排在", "后面"),   # (正向动词, 正向方位, 反向动词, 反向方位)
    ("比", "高", "比", "矮"),
    ("比", "跑得快", "比", "跑得慢"),
]


def _pick_relation(rng):
    return rng.choice(RELATIONS)


def _generate_constraints(rng, codes, n):
    """随机生成一组比较约束，返回 [(文字, 逻辑)]。用链式 + 两两混合。"""
    cons = []
    # 生成一条覆盖所有实体的随机全序作为"隐藏真相"，再从中派生约束
    order = list(codes)
    rng.shuffle(order)  # order[0] 是第 1 名
    # 相邻比较（链式）
    for i in range(n - 1):
        a, b = order[i], order[i + 1]
        cons.append((a, b))
    return order, cons


def _build(rng, codes, names, order, cons_pairs, rel):
    code_names = {c: names[i] for i, c in enumerate(codes)}
    n = len(codes)
    fwd_v, fwd_d, back_v, back_d = rel
    # 随机决定用"正向"还是混合表述
    constraints = []
    for a, b in cons_pairs:
        if rng.random() < 0.7:
            constraints.append(Constraint(
                text=f"{code_names[a]}{fwd_v}{code_names[b]}{fwd_d}",
                logic=f"RANK({a}) < RANK({b})"))
        else:
            constraints.append(Constraint(
                text=f"{code_names[b]}{back_v}{code_names[a]}{back_d}",
                logic=f"RANK({a}) < RANK({b})"))

    variables = [Variable(f"rank_{c}", "rank") for c in codes]
    story_title = f"谁{fwd_v}最{fwd_d}？" if fwd_d in ("高",) else f"谁{fwd_d}？"
    story_title = f"排排队：谁在第1？"
    story_text = f"{n}个小伙伴要排成一列。根据下面的线索，你能排出他们的顺序吗？"
    story = Story(title=story_title, text=story_text, roles=code_names)

    # 问题：问某个特定位置是谁，或谁是第一
    target_rank = rng.randint(1, n)
    question_prompt = f"谁排在第 {target_rank} 位？"
    # 正确答案
    correct_code = order[target_rank - 1]
    options = [code_names[c] for c in codes]
    option_logic = [f"RANK({c}) == {target_rank}" for c in codes]
    correct_idx = codes.index(correct_code)
    options, option_logic, answer = shuffle_options(rng, options, option_logic, correct_idx)

    # 解释
    order_text = " → ".join(code_names[c] for c in order)
    explanation = f"完整顺序是：{order_text}。\n所以第 {target_rank} 位是 {code_names[correct_code]}。"
    hints = [
        "先把能确定的相邻关系连起来。",
        "试着把所有人按线索串成一条链。",
        f"数一数：从第1位数到第{target_rank}位，看看是谁。",
    ]

    return Question(
        id=new_id("order"), type=TYPE, story=story, entities=list(codes),
        variables=variables, statements=[], constraints=constraints,
        question_prompt=question_prompt, options=options, option_logic=option_logic,
        answer=answer, hints=hints, explanation=explanation,
        source="generated", created_at=now_iso(),
    )


def generate(rng: random.Random, n_entities: int = None, max_tries: int = 300):
    if n_entities is None:
        n_entities = rng.choice([3, 4, 4, 5])
    chars = themes.pick_characters(n_entities, rng)
    names = [c[0] for c in chars]
    codes = [chr(ord("A") + i) for i in range(n_entities)]
    rel = _pick_relation(rng)

    for _ in range(max_tries):
        order, cons_pairs = _generate_constraints(rng, codes, n_entities)
        q = _build(rng, codes, names, order, cons_pairs, rel)
        try:
            solutions = solver.solve(q)
        except solver.QuestionError:
            continue
        if len(solutions) == 1:
            # 用真实解重建答案（确保与解一致）
            sol = solutions[0]
            true_order = sorted(codes, key=lambda c: sol[f"rank_{c}"])
            target_rank = int(q.question_prompt.split("第 ")[1].split(" ")[0])
            correct_code = true_order[target_rank - 1]
            # 重新定位正确选项
            for i, logic in enumerate(q.option_logic):
                if logic == f"RANK({correct_code}) == {target_rank}":
                    q.answer = i
                    break
            # 更新解释
            code_names = {c: names[i] for i, c in enumerate(codes)}
            order_text = " → ".join(code_names[c] for c in true_order)
            q.explanation = f"完整顺序是：{order_text}。\n所以第 {target_rank} 位是 {code_names[correct_code]}。"
            return q
    return None
