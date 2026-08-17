"""主题词库（专家意见第十八节：自动变体生成的素材来源）。

每个主题提供：角色、物品、场景、动作等可随机替换的词汇池，
以及用于渲染故事的模板。变体生成时随机挑选主题并替换，
替换完成后必须重新经过 Solver 验证才能入库。
"""
from __future__ import annotations

import random

# 角色池：(emoji, [名字...])
CHARACTERS = [
    ("🐭", ["小灰", "米粒", "吱吱", "团团", "豆豆", "点点"]),
    ("🐰", ["小白兔", "跳跳", "雪儿", "圆圆", "茸茸", "棉棉"]),
    ("🐱", ["小猫咪", "咪咪", "花花", "虎斑", "奶糖", "布丁"]),
    ("🐶", ["小狗", "旺旺", "点点", "大黄", "贝贝", "球球"]),
    ("🐦", ["小鸟", "啾啾", "蓝蓝", "云云", "飞飞", "乐乐"]),
    ("🐻", ["小熊", "壮壮", "憨憨", "圆圆", "大力", "毛毛"]),
]

# 物品池（用于"偷了/拿了/有"类属性）：(emoji, 中文名, DSL属性名)
ITEMS = [
    ("🧀", "奶酪", "cheese"), ("🍒", "樱桃", "cherry"), ("🍎", "苹果", "apple"),
    ("🍞", "面包", "bread"), ("🥕", "胡萝卜", "carrot"), ("🍪", "饼干", "cookie"),
    ("🐟", "小鱼", "fish"), ("🍬", "糖果", "candy"),
]

# 场景/动作（用于排序、配对题）
PLACES = ["公园", "学校", "家里", "超市", "森林", "海边"]
TIMES = ["早上", "中午", "下午", "傍晚"]

EMOJI_BY_NAME = {}
for emoji, names in CHARACTERS:
    for n in names:
        EMOJI_BY_NAME[n] = n  # 占位，下面会被角色 emoji 覆盖


def pick_characters(n: int, rng: random.Random) -> list:
    """挑选 n 个互不重名的角色，返回 [(名字, emoji), ...]。"""
    pool = [(name, emoji) for emoji, names in CHARACTERS for name in names]
    # 按名字去重（不同动物池可能有同名角色），保留首次出现
    seen, uniq = set(), []
    for name, emoji in pool:
        if name not in seen:
            seen.add(name)
            uniq.append((name, emoji))
    return rng.sample(uniq, n)


def pick_item(rng: random.Random):
    """返回 (emoji, 中文名, DSL属性名)。"""
    return rng.choice(ITEMS)


def pick_place(rng: random.Random) -> str:
    return rng.choice(PLACES)


def pick_time(rng: random.Random) -> str:
    return rng.choice(TIMES)
