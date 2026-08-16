"""题型 ④ 条件推理（Conditional / 如果…那么…）模板。

模型：一条因果链 e0 -> e1 -> ... -> en（蕴含约束 !e_i || e_{i+1}）+ 一个已知事实。
  · 正向（肯定起点）：问后面某事件，答案"一定发生"（肯定前件）
  · 逆向（否定终点）：问前面某事件，答案"一定不发生"（否定后件）
  · 不明（肯定终点）：问前面某事件，答案"无法确定"
布尔域求解；正确选项必须是被所有解唯一蕴含的那一个。
"""
from __future__ import annotations

import random

from ...models import Question, Story, Variable, Constraint
from .. import themes
from ._base import new_id, now_iso, shuffle_options

TYPE = "conditional"

# 连通的因果链（每个元素是一段完整链条）
CHAINS = [
    ["下雨了", "地面会变湿", "小草喝饱了水", "小草长高了"],
    ["太阳出来了", "雪慢慢融化了", "小河的水变多了", "小鱼更开心了"],
    ["小明按了开关", "灯亮起来了", "房间变亮了", "他能看清书上的字了"],
    ["小红给花浇了水", "花喝饱了水", "花开了", "蜜蜂飞来了"],
    ["闹钟响了", "小分起床了", "小分刷了牙", "小分出门上学了"],
    ["风吹得很大", "树叶飘落下来", "地上铺满了落叶", "小蚂蚁有了新被子"],
    ["天气变冷了", "大家穿上了外套", "大家戴上了手套", "小手不冷了"],
]


def generate(rng: random.Random, chain_len: int = None, max_tries: int = 100):
    if chain_len is None:
        chain_len = rng.choice([2, 3, 3])
    chain = rng.choice(CHAINS)
    # 取链条的一段（保证连通）
    max_start = len(chain) - (chain_len + 1)
    start = rng.randint(0, max(0, max_start))
    events = chain[start:start + chain_len + 1]
    n_vars = len(events)
    varnames = [f"e{i}" for i in range(n_vars)]

    constraints = [
        Constraint(text=f"如果{events[i]}，那么{events[i+1]}", logic=f"!e{i} || e{i+1}")
        for i in range(n_vars - 1)
    ]

    mode = rng.choice(["affirm", "negate", "undetermined"])
    if mode == "affirm":
        constraints.append(Constraint(text=f"现在：{events[0]}", logic="e0"))
        ask_idx = rng.randint(1, n_vars - 1)
        answer_kind = "yes"
    elif mode == "negate":
        constraints.append(Constraint(text=f"现在：“{events[-1]}”这件事没有发生", logic=f"!e{n_vars-1}"))
        ask_idx = rng.randint(0, n_vars - 2)
        answer_kind = "no"
    else:  # undetermined：肯定终点，推不回起点
        constraints.append(Constraint(text=f"现在：{events[-1]}", logic=f"e{n_vars-1}"))
        ask_idx = rng.randint(0, n_vars - 2)
        answer_kind = "unknown"

    variables = [Variable(v, "boolean") for v in varnames]
    story = Story(
        title="想一想，会发生吗？",
        text="根据下面的规则，判断问题里的事情会不会一定发生。",
        roles={},
    )
    question_prompt = f"那么，“{events[ask_idx]}”一定会发生吗？"

    if answer_kind == "yes":
        options = ["一定会发生", "一定不会发生", f"其实“{events[0]}”没有发生"]
        option_logic = [f"e{ask_idx}", f"!e{ask_idx}", "!e0"]
        correct_idx = 0
    elif answer_kind == "no":
        options = ["一定会发生", "一定不会发生", f"其实“{events[-1]}”发生了"]
        option_logic = [f"e{ask_idx}", f"!e{ask_idx}", f"e{n_vars-1}"]
        correct_idx = 1
    else:
        options = ["一定会发生", "一定不会发生", "无法确定"]
        option_logic = [f"e{ask_idx}", f"!e{ask_idx}", "TRUE"]
        correct_idx = 2
    options, option_logic, answer = shuffle_options(rng, options, option_logic, correct_idx)

    explanation = _explain(mode, events, ask_idx, answer_kind)
    hints = [
        "先找到题目告诉你的那个已知事实。",
        "顺着“如果…那么…”一步一步推。",
        "注意：只有前面的事发生了，后面的事才一定发生；反过来不一定。",
    ]

    return Question(
        id=new_id("cond"), type=TYPE, story=story, entities=[],
        variables=variables, statements=[], constraints=constraints,
        question_prompt=question_prompt, options=options, option_logic=option_logic,
        answer=answer, hints=hints, explanation=explanation,
        source="generated", created_at=now_iso(),
    )


def _explain(mode, events, ask_idx, answer_kind):
    if mode == "affirm":
        steps = [f"已知：{events[0]}。"]
        for i in range(ask_idx):
            steps.append(f"因为“如果{events[i]}，那么{events[i+1]}”，所以{events[i+1]}。")
        return "\n".join(steps) + f"\n所以“{events[ask_idx]}”一定会发生。"
    if mode == "negate":
        steps = [f"已知：{events[-1]}没有发生。"]
        for i in range(n := len(events) - 2, ask_idx - 1, -1):
            steps.append(f"要是{events[i]}发生了，{events[i+1]}就会发生；可{events[i+1]}没发生，所以{events[i]}也没发生。")
        return "\n".join(steps) + f"\n所以“{events[ask_idx]}”一定不会发生。"
    return (f"我们知道“{events[-1]}”发生了，但它可能是由别的原因造成的，"
            f"光凭这些规则推不出“{events[ask_idx]}”一定发生或一定不发生，所以无法确定。")
