"""模板共用工具：选项打乱、子集描述、题目装配。"""
from __future__ import annotations

import random
import uuid
from datetime import datetime

from ...models import Question, Story


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def shuffle_options(rng: random.Random, options: list, logics: list, correct_idx: int):
    """把选项与逻辑一起打乱，返回 (options, logics, new_correct_idx)。"""
    order = list(range(len(options)))
    rng.shuffle(order)
    new_options = [options[i] for i in order]
    new_logics = [logics[i] for i in order]
    new_correct = order.index(correct_idx)
    return new_options, new_logics, new_correct


def describe_subset(entities: list, subset: set, prop_zh: str, have_verb: str, item_zh: str,
                    code_names: dict = None) -> tuple:
    """描述"恰好是 subset 中的角色{have}{item}"，返回 (文字, 逻辑)。

    entities: 实体代号列表（A/B/C…）。subset: 拥有该属性的代号集合。
    code_names: 代号->显示名映射；提供时文字用显示名。
    """
    def disp(code):
        return code_names.get(code, code) if code_names else code

    codes = list(entities)
    n = len(codes)
    if not subset:
        return f"谁都没有{have_verb}{item_zh}", "NONE({p})".format(p=prop_zh)
    if len(subset) == n:
        return f"所有人都{have_verb}{item_zh}", "ALL({p})".format(p=prop_zh)
    if len(subset) == 1:
        code = next(iter(subset))
        return (
            f"只有{disp(code)}{have_verb}{item_zh}",
            f"{code}_{prop_zh} && COUNT({prop_zh}) == 1",
        )
    # 多个：明确列出谁有、谁没有，保证唯一对应这个子集
    have = [f"{c}_{prop_zh}" for c in codes if c in subset]
    lack = [f"!{c}_{prop_zh}" for c in codes if c not in subset]
    text_have = "、".join(disp(c) for c in codes if c in subset)
    text = f"只有{text_have}{have_verb}{item_zh}"
    logic = " && ".join(have + lack)
    return text, logic
