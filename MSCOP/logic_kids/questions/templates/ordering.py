"""题型 ② 顺序排列（Ordering）模板。

模型：N 个角色有一个明确排序（排队位置 / 身高 / 比赛名次），rank 1 = 最前 / 最高 / 第 1 名。
约束是若干两两比较或链式比较；目标是唯一确定某个角色的位置。
排列域枚举 n! 状态，Solver 求唯一解。

语义一致性（专家审查 P0）：关系类型与故事、提问必须配套 ——
  · queue  → 排队：故事"排成一列"，问"谁排在第 X 位"
  · height → 身高：故事"比身高"，问"谁是第 X 高"
  · race   → 比赛：故事"跑步比赛"，问"谁获得第 X 名"
"""
from __future__ import annotations

import random

from ...logic import solver
from ...models import Question, Story, Variable, Statement, Constraint
from .. import themes
from ._base import new_id, now_iso, shuffle_options

TYPE = "ordering"

# 三种关系场景：每种都有配套的故事、提问、解释与提示用词，保证文字与逻辑一致
SCENARIOS = {
    "queue": {
        "rel": ("排在", "前面", "排在", "后面"),   # (正向动词, 正向方位, 反向动词, 反向方位)
        "title": "排排队：谁在第 1？",
        "story": "{n}个小伙伴要排成一列。根据下面的线索，你能排出他们的顺序吗？",
        "ask": "谁排在第 {k} 位？",
        "explain_order": "完整顺序是：{order}。",
        "explain_rank": "所以排在第 {k} 位的是 {who}。",
        "hint_count": "数一数：从第 1 位一路数到第 {k} 位，看看是谁。",
    },
    "height": {
        "rel": ("比", "高", "比", "矮"),
        "title": "谁最高？",
        "story": "{n}个小伙伴在比身高。根据下面的线索，你能排出谁高谁矮吗？",
        "ask": "谁是第 {k} 高？",
        "explain_order": "从高到矮的顺序是：{order}。",
        "explain_rank": "所以第 {k} 高的是 {who}。",
        "hint_count": "数一数：从最高的开始数，第 {k} 个是谁？",
    },
    "race": {
        "rel": ("比", "跑得快", "比", "跑得慢"),
        "title": "谁跑得最快？",
        "story": "{n}个小伙伴参加跑步比赛。根据下面的线索，你能排出比赛名次吗？",
        "ask": "谁获得第 {k} 名？",
        "explain_order": "比赛名次是：{order}。",
        "explain_rank": "所以获得第 {k} 名的是 {who}。",
        "hint_count": "数一数：从第 1 名一路数到第 {k} 名，看看是谁。",
    },
}


def _pick_scenario(rng):
    return rng.choice(list(SCENARIOS.values()))


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


def _build(rng, codes, names, order, cons_pairs, scenario):
    """按场景构造题目；返回 (Question, target_rank)。"""
    code_names = {c: names[i] for i, c in enumerate(codes)}
    n = len(codes)
    fwd_v, fwd_d, back_v, back_d = scenario["rel"]
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
    story = Story(title=scenario["title"],
                  text=scenario["story"].format(n=n), roles=code_names)

    # 问题：问某个特定位置是谁
    target_rank = rng.randint(1, n)
    question_prompt = scenario["ask"].format(k=target_rank)
    correct_code = order[target_rank - 1]
    options = [code_names[c] for c in codes]
    option_logic = [f"RANK({c}) == {target_rank}" for c in codes]
    correct_idx = codes.index(correct_code)
    options, option_logic, answer = shuffle_options(rng, options, option_logic, correct_idx)

    # 解释与提示（与场景用词一致）
    order_text = " → ".join(code_names[c] for c in order)
    explanation = (scenario["explain_order"].format(order=order_text)
                   + scenario["explain_rank"].format(k=target_rank,
                                                     who=code_names[correct_code]))
    hints = [
        "先把能确定的相邻关系连起来。",
        "试着把所有人按线索串成一条链。",
        scenario["hint_count"].format(k=target_rank),
    ]

    return Question(
        id=new_id("order"), type=TYPE, story=story, entities=list(codes),
        variables=variables, statements=[], constraints=constraints,
        question_prompt=question_prompt, options=options, option_logic=option_logic,
        answer=answer, hints=hints, explanation=explanation,
        source="generated", created_at=now_iso(),
    ), target_rank


def generate(rng: random.Random, n_entities: int = None, max_tries: int = 300):
    if n_entities is None:
        n_entities = rng.choice([3, 4, 4, 5])
    chars = themes.pick_characters(n_entities, rng)
    names = [c[0] for c in chars]
    codes = [chr(ord("A") + i) for i in range(n_entities)]
    scenario = _pick_scenario(rng)

    for _ in range(max_tries):
        order, cons_pairs = _generate_constraints(rng, codes, n_entities)
        q, target_rank = _build(rng, codes, names, order, cons_pairs, scenario)
        try:
            solutions = solver.solve(q)
        except solver.QuestionError:
            continue
        if len(solutions) == 1:
            # 用真实解重建答案（确保与解一致）
            sol = solutions[0]
            true_order = sorted(codes, key=lambda c: sol[f"rank_{c}"])
            correct_code = true_order[target_rank - 1]
            # 重新定位正确选项
            for i, logic in enumerate(q.option_logic):
                if logic == f"RANK({correct_code}) == {target_rank}":
                    q.answer = i
                    break
            # 更新解释
            code_names = {c: names[i] for i, c in enumerate(codes)}
            order_text = " → ".join(code_names[c] for c in true_order)
            q.explanation = (scenario["explain_order"].format(order=order_text)
                             + scenario["explain_rank"].format(k=target_rank,
                                                               who=code_names[correct_code]))
            return q
    return None
