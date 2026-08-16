"""人工种子题（专家意见第七节 A 类：Static Questions）。

这些是手工整理、并经 Solver 验证过的经典题，作为题库的起点与回归基准。
每道种子题在入库前同样要通过 Validator。
"""
from __future__ import annotations

from ..models import Question, Story, Variable, Statement, Constraint


def seed_mice() -> Question:
    """经典"四只老鼠"真假话题（唯一解变体，已经 Solver 验证）。"""
    codes = ["A", "B", "C", "D"]
    roles = {"A": "小灰", "B": "米粒", "C": "吱吱", "D": "团团"}
    return Question(
        id="seed_truth_mice",
        type="truth_statements",
        story=Story(
            title="四只偷食物的小老鼠",
            text="有四只小老鼠出去偷食物。它们每只都说了一句话，"
                 "但只有一只老鼠说了真话。到底哪些老鼠偷了奶酪呢？",
            roles=roles,
        ),
        entities=codes,
        variables=[Variable(f"{c}_cheese", "boolean") for c in codes],
        statements=[
            Statement(text="我们中有些老鼠没偷奶酪", logic="SOME_NOT(cheese)", speaker="A"),
            Statement(text="至少有一只老鼠偷了奶酪", logic="SOME(cheese)", speaker="B"),
            Statement(text="没有老鼠偷奶酪", logic="NONE(cheese)", speaker="C"),
            Statement(text="只有我偷了奶酪", logic="D_cheese && COUNT(cheese) == 1", speaker="D"),
        ],
        constraints=[Constraint(text="只有一只老鼠说了真话", logic="TRUTH_COUNT == 1")],
        question_prompt="到底哪些老鼠偷了奶酪？",
        options=[
            "所有老鼠都偷了奶酪",
            "有些老鼠没偷奶酪",
            "没有老鼠偷奶酪",
            "只有团团偷了奶酪",
        ],
        option_logic=[
            "ALL(cheese)",
            "SOME_NOT(cheese)",
            "NONE(cheese)",
            "D_cheese && COUNT(cheese) == 1",
        ],
        answer=0,
        hints=[
            "只有一只老鼠说了真话，先假设某只说的是真话试试。",
            "如果团团说的是真话（只有它偷了），那米粒说“至少一只偷了”也会是真的——就有两句真话了，矛盾。",
            "试试假设米粒说的是真话，看看其它三句是不是都成了假话。",
        ],
        explanation=(
            "假设米粒说真话，也就是“至少有一只老鼠偷了奶酪”。\n"
            "· 小灰说“有些没偷”：如果四只都偷了，这句就是假话，符合。\n"
            "· 吱吱说“没有老鼠偷”：和“至少一只偷了”矛盾，是假话，符合。\n"
            "· 团团说“只有我偷了”：若是真的，米粒那句也对了，就有两句真话，所以它是假话，符合。\n"
            "这样恰好只有一句真话，此时四只老鼠都偷了奶酪。答案是：所有老鼠都偷了奶酪。"
        ),
        source="seed",
        created_at="",
    )


def seed_ordering() -> Question:
    """简单排序题。"""
    codes = ["A", "B", "C"]
    roles = {"A": "小明", "B": "小红", "C": "小刚"}
    return Question(
        id="seed_order_height",
        type="ordering",
        story=Story(
            title="谁最高？",
            text="三个小朋友比身高。根据线索，想想谁最高。",
            roles=roles,
        ),
        entities=codes,
        variables=[Variable(f"rank_{c}", "rank") for c in codes],
        statements=[],
        constraints=[
            Constraint(text="小明比小红高", logic="RANK(A) < RANK(B)"),
            Constraint(text="小红比小刚高", logic="RANK(B) < RANK(C)"),
        ],
        question_prompt="谁最高？",
        options=["小明", "小红", "小刚"],
        option_logic=["RANK(A) == 1", "RANK(B) == 1", "RANK(C) == 1"],
        answer=0,
        hints=["把身高关系连成一条链。", "小明比小红高，小红比小刚高，那小明比小刚也高。"],
        explanation="小明比小红高，小红比小刚高，所以小明 > 小红 > 小刚，最高的是小明。",
        source="seed",
        created_at="",
    )


def seed_conditional() -> Question:
    """条件推理（肯定前件）。"""
    return Question(
        id="seed_cond_rain",
        type="conditional",
        story=Story(
            title="想一想，会发生吗？",
            text="根据规则判断事情会不会一定发生。",
            roles={},
        ),
        entities=[],
        variables=[Variable("e0", "boolean"), Variable("e1", "boolean"), Variable("e2", "boolean")],
        statements=[],
        constraints=[
            Constraint(text="如果下雨了，那么地面会变湿", logic="!e0 || e1"),
            Constraint(text="如果地面会变湿，那么小草会喝饱水", logic="!e1 || e2"),
            Constraint(text="现在：下雨了", logic="e0"),
        ],
        question_prompt="那么，“小草会喝饱水”一定会发生吗？",
        options=["一定会发生", "一定不会发生", "其实没有下雨"],
        option_logic=["e2", "!e2", "!e0"],
        answer=0,
        hints=["从“下雨了”开始往下推。", "下雨 → 地面湿 → 小草喝饱水。"],
        explanation="下雨了，所以地面会变湿；地面变湿，所以小草会喝饱水。一定会发生。",
        source="seed",
        created_at="",
    )


def seed_set_logic() -> Question:
    """集合关系题。"""
    codes = ["A", "B", "C"]
    roles = {"A": "小猫", "B": "小狗", "C": "小兔"}
    return Question(
        id="seed_set_pets",
        type="set_logic",
        story=Story(
            title="谁有鱼？",
            text="看看下面的情况，哪句话是对的？",
            roles=roles,
        ),
        entities=codes,
        variables=[Variable(f"{c}_fish", "boolean") for c in codes],
        statements=[],
        constraints=[
            Constraint(text="小猫有🐟鱼", logic="A_fish"),
            Constraint(text="小狗有🐟鱼", logic="B_fish"),
            Constraint(text="小兔没有🐟鱼", logic="!C_fish"),
        ],
        question_prompt="关于鱼，下面哪句话是对的？",
        options=[
            "所有人都有鱼",
            "谁都没有鱼",
            "有些人有鱼，有些人没有",
        ],
        option_logic=["ALL(fish)", "NONE(fish)", "SOME(fish) && SOME_NOT(fish)"],
        answer=2,
        hints=["数一数有几个有鱼。", "小猫小狗有，小兔没有。"],
        explanation="小猫和小狗有鱼，小兔没有，所以是“有些人有，有些人没有”。",
        source="seed",
        created_at="",
    )


def seed_exclusion() -> Question:
    """排除推理题。"""
    codes = ["A", "B", "C"]
    roles = {"A": "小鹿", "B": "小马", "C": "小羊"}
    return Question(
        id="seed_excl_race",
        type="exclusion",
        story=Story(
            title="跑步比赛的名次",
            text="三个小伙伴跑步比赛。用排除法想想：小羊是第几名？",
            roles=roles,
        ),
        entities=codes,
        variables=[Variable(f"rank_{c}", "rank") for c in codes],
        statements=[],
        constraints=[
            Constraint(text="小鹿不是第1名", logic="RANK(A) != 1"),
            Constraint(text="小羊不是第1名", logic="RANK(C) != 1"),
            Constraint(text="小鹿在小羊前面", logic="RANK(A) < RANK(C)"),
        ],
        question_prompt="小羊是第几名？",
        options=["第1名", "第2名", "第3名"],
        option_logic=["RANK(C) == 1", "RANK(C) == 2", "RANK(C) == 3"],
        answer=2,
        hints=["谁可能是第1名？", "小鹿不是第1，小羊不是第1，那第1只能是小马。", "小鹿在小羊前面，想想小羊排第几。"],
        explanation="小鹿和小羊都不是第1名，所以第1名是小马；小鹿在小羊前面，所以小鹿第2、小羊第3名。",
        source="seed",
        created_at="",
    )


def all_seeds() -> list:
    return [seed_mice(), seed_ordering(), seed_conditional(), seed_set_logic(), seed_exclusion()]
