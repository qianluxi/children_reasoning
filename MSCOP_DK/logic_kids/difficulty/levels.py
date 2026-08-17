"""难度等级映射（专家意见第二节：difficulty_score 与 difficulty_level 分离）。

设计原则：
    · difficulty_score 是连续评分（0..10），由 Difficulty Engine 计算；
    · difficulty_level 是用户可见的离散等级（1..4：简单/普通/困难/挑战）；
    · 分界线只允许在这里定义。模板、生成器、选择器、UI 一律引用本模块，
      以后调整分界线（例如把评分制切到 0..100）不会影响题目生成器。

分界线（对应专家建议的 0~100 分制按 10 倍缩放，区间连续覆盖，
避免四舍五入后的分数落到两档之间的缝隙）：
    0.00 ~ 2.49 → 1 🌱 简单
    2.50 ~ 4.99 → 2 ⭐ 普通
    5.00 ~ 7.49 → 3 🚀 困难
    7.50 ~ 10.0 → 4 🧠 挑战
"""
from __future__ import annotations

MAX_LEVEL = 4

LEVELS = {
    1: {"min": 0.0, "max": 2.49, "name": "简单", "emoji": "🌱", "tagline": "入门热身"},
    2: {"min": 2.5, "max": 4.99, "name": "普通", "emoji": "⭐", "tagline": "基础训练"},
    3: {"min": 5.0, "max": 7.49, "name": "困难", "emoji": "🚀", "tagline": "动动脑筋"},
    4: {"min": 7.5, "max": 10.0, "name": "挑战", "emoji": "🧠", "tagline": "高难度"},
}

ALL_LEVELS = sorted(LEVELS)


def level_for_score(score: float) -> int:
    """连续难度分 -> 等级（1..4）。越界按最近等级钳制。"""
    for level in ALL_LEVELS[::-1]:  # 从高到低，命中第一个 min <= score 的等级
        if score >= LEVELS[level]["min"]:
            return level
    return ALL_LEVELS[0]


def validate_level(level) -> int:
    """校验用户输入的等级必须是 1..4 的整数（拒绝 bool）。"""
    if isinstance(level, bool) or not isinstance(level, int) or level not in LEVELS:
        raise ValueError(f"难度等级必须是 1..{MAX_LEVEL} 的整数，收到 {level!r}")
    return level


def name(level: int) -> str:
    return LEVELS[level]["name"]


def label(level: int) -> str:
    """儿童友好的等级名，如 "🚀 困难"。"""
    return f"{LEVELS[level]['emoji']} {LEVELS[level]['name']}"


def score_range(level: int) -> tuple:
    """该等级对应的 difficulty_score 区间 [min, max]。"""
    band = LEVELS[level]
    return (band["min"], band["max"])


def adjacent_levels(level: int, max_gap: int = 3) -> list:
    """从目标等级向两侧扩散的搜索顺序（先精确匹配，再逐步放宽）。"""
    order = [level]
    for delta in range(1, max_gap + 1):
        for nd in (level + delta, level - delta):
            if nd in LEVELS and nd not in order:
                order.append(nd)
    return order


def public_levels() -> list:
    """给前端用的等级清单（不含评分，儿童只看得到等级名）。"""
    return [
        {
            "level": lv,
            "name": LEVELS[lv]["name"],
            "emoji": LEVELS[lv]["emoji"],
            "tagline": LEVELS[lv]["tagline"],
            "label": label(lv),
        }
        for lv in ALL_LEVELS
    ]
