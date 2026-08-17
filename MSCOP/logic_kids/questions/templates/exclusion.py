"""题型 ⑥ 排除推理（Exclusion）模板。

模型：N 个角色争夺名次（rank 域）。给出若干约束：直接名次、不等名次、
相对顺序；这些约束不足以定出全序，但足以唯一确定所问的那一项。
考察"排除不可能的情况"的推理能力。
"""
from __future__ import annotations

import random

from ...logic import solver
from ...models import Question, Story, Variable, Constraint
from .. import themes
from ._base import new_id, now_iso, shuffle_options

TYPE = "exclusion"

CONTEXTS = [
    ("跑步比赛", "跑第", "名"),
    ("唱歌比赛", "唱第", "名"),
    ("排队领点心", "排第", "个"),
    ("跳绳比赛", "跳第", "名"),
]


def generate(rng: random.Random, n_entities: int = None, max_tries: int = 500):
    if n_entities is None:
        n_entities = rng.choice([3, 4, 4, 5])
    chars = themes.pick_characters(n_entities, rng)
    names = [c[0] for c in chars]
    codes = [chr(ord("A") + i) for i in range(n_entities)]
    code_names = {c: names[i] for i, c in enumerate(codes)}
    ctx_name, rank_verb, unit = rng.choice(CONTEXTS)

    # 先随机一个"真相"全序，约束必须与它一致（保证至少有一个解）
    true_order = list(codes)
    rng.shuffle(true_order)  # true_order[0] 是第 1 名
    true_rank = {c: i + 1 for i, c in enumerate(true_order)}

    variables = [Variable(f"rank_{c}", "rank") for c in codes]

    # 要问的目标：某个角色是第几名（答案必须被约束唯一确定）
    ask_code = rng.choice(codes)
    answer_rank = true_rank[ask_code]

    # 约束候选池（只放与真相全序一致的约束，保证真相永远是一个解）
    pool = []
    for c in codes:
        if true_rank[c] != 1:
            pool.append((f"{code_names[c]}不是第1{unit}", f"RANK({c}) != 1"))
        if true_rank[c] != n_entities:
            pool.append((f"{code_names[c]}不是最后一名", f"RANK({c}) != {n_entities}"))
        for r in range(1, n_entities + 1):
            if r != true_rank[c]:
                pool.append((f"{code_names[c]}不是第{r}{unit}", f"RANK({c}) != {r}"))
    for i in range(n_entities):
        for j in range(i + 1, n_entities):
            a, b = true_order[i], true_order[j]
            pool.append((f"{code_names[a]}在{code_names[b]}前面", f"RANK({a}) < RANK({b})"))
            pool.append((f"{code_names[a]}比{code_names[b]}名次好", f"RANK({a}) < RANK({b})"))
    rng.shuffle(pool)

    question_prompt = f"{code_names[ask_code]}是第几{unit}？"
    options = [f"第{r}{unit}" for r in range(1, n_entities + 1)]
    option_logic = [f"RANK({ask_code}) == {r}" for r in range(1, n_entities + 1)]
    correct_idx = answer_rank - 1

    story = Story(
        title=f"{ctx_name}的名次",
        text=f"{n_entities}个小伙伴参加{ctx_name}。根据下面的线索，"
             f"用排除法想想：{code_names[ask_code]}是第几{unit}？",
        roles=code_names,
    )

    # 逐步加入约束，直到 RANK(ask_code) 被唯一确定
    chosen = []
    result = None
    for text, logic in pool:
        trial = chosen + [(text, logic)]
        cons = [Constraint(text=t, logic=l) for t, l in trial]
        tmp = Question(
            id="tmp", type=TYPE, story=Story("t", "t", {}), entities=list(codes),
            variables=variables, statements=[], constraints=cons,
            question_prompt="", options=["x"], option_logic=["TRUE"], answer=0,
            hints=[], explanation="",
        )
        try:
            solutions = solver.solve(tmp)
        except solver.QuestionError:
            continue
        if not solutions:
            continue  # 与真相矛盾的约束不会出现，这里保险跳过
        ranks = {s[f"rank_{ask_code}"] for s in solutions}
        if len(ranks) == 1:
            chosen = trial
            result = solutions
            break
        chosen = trial

    if result is None:
        return None

    # 检查约束数量合理（至少2条），否则题目太裸
    if len(chosen) < 2:
        return None

    constraints = [Constraint(text=t, logic=l) for t, l in chosen]
    # 先打乱选项，再由逻辑反查正确下标（避免与答案错位）
    shuffled_options, shuffled_logic, _ = shuffle_options(rng, options, option_logic, correct_idx)
    answer = shuffled_logic.index(f"RANK({ask_code}) == {answer_rank}")
    options, option_logic = shuffled_options, shuffled_logic

    # 解释：列出排除过程
    others = [f"第{r}{unit}" for r in range(1, n_entities + 1) if r != answer_rank]
    explanation = (
        f"把线索一条条对：{code_names[ask_code]}不可能是{'、'.join(others)}，"
        f"剩下的只能是第{answer_rank}{unit}。"
    )
    hints = [
        "先看看哪些名次被明确排除了。",
        "把不可能的名次一个个划掉。",
        f"最后只剩下一个名次，那就是{code_names[ask_code]}的。",
    ]

    return Question(
        id=new_id("excl"), type=TYPE, story=story, entities=list(codes),
        variables=variables, statements=[], constraints=constraints,
        question_prompt=question_prompt, options=options, option_logic=option_logic,
        answer=answer, hints=hints, explanation=explanation,
        source="generated", created_at=now_iso(),
    )
