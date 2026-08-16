"""Reasoning Gym 导入适配器（PR2，专家意见第一优先扩容来源）。

Reasoning Gym：程序化、可验证、可调难度的推理任务生成框架（Apache-2.0）。
本适配器只从"适合儿童"的白名单按需生成，不导入全部 100+ 任务。

白名单任务的答案由 reasoning-gym 自带算法验证器保证正确；但题目是
自然语言（英文）、无法转成我们的 DSL，因此走 结构验证 + 人工审核
（experimental / raw 层级），儿童正式训练前需要语言改写与抽检。
"""
from __future__ import annotations

import random
import re

from ..normalizer import NormalizedQuestion
from ..provenance import make_source, make_provenance

SOURCE_NAME = "Reasoning Gym"
LICENSE = "Apache-2.0"
_TRANSLATOR = "reasoning_gym_generator_v1"
_URL = "https://github.com/open-thought/reasoning-gym"

# 儿童任务白名单：任务名 -> (能力, 技能)
TASKS = {
    "knights_knaves": {"category": "deduction",
                       "skills": ["deduction", "negation"]},
    "syllogism": {"category": "deduction",
                  "skills": ["deduction", "quantifier"]},
    "family_relationships": {"category": "relation",
                             "skills": ["relation_reasoning",
                                        "multi_hop_reasoning"]},
    "leg_counting": {"category": "math", "skills": ["counting", "arithmetic"]},
    "letter_counting": {"category": "math", "skills": ["counting"]},
    "rectangle_count": {"category": "math", "skills": ["counting"]},
    "chain_sum": {"category": "math", "skills": ["arithmetic"]},
    "number_sequence": {"category": "pattern",
                        "skills": ["pattern_recognition", "induction"]},
    "arc_1d": {"category": "pattern",
               "skills": ["pattern_recognition", "visual_abstraction"]},
    "maze": {"category": "spatial",
             "skills": ["spatial_reasoning", "planning"]},
    "time_intervals": {"category": "math", "skills": ["arithmetic", "ordering"]},
}

_RELATION_VOCAB = ["father", "mother", "brother", "sister", "son", "daughter",
                   "grandfather", "grandmother", "uncle", "aunt", "cousin",
                   "nephew", "niece", "husband", "wife", "grandchild"]

# 中文翻译词表（机器翻译，状态 machine）
_ZH_ANIMALS = {
    "butterfly": "蝴蝶", "crab": "螃蟹", "sea slug": "海蛞蝓",
    "praying mantis": "螳螂", "giraffe": "长颈鹿", "flatworm": "扁形虫",
    "cockroach": "蟑螂", "dog": "狗", "cat": "猫", "wasp": "黄蜂",
    "spider": "蜘蛛", "ant": "蚂蚁", "bird": "鸟", "centipede": "蜈蚣",
    "millipede": "马陆", "bee": "蜜蜂", "fly": "苍蝇", "ladybug": "瓢虫",
    "mosquito": "蚊子", "snake": "蛇", "frog": "青蛙", "octopus": "章鱼",
    "lobster": "龙虾", "snail": "蜗牛", "worm": "虫子", "elephant": "大象",
    "horse": "马", "pig": "猪", "sheep": "羊", "cow": "牛", "chicken": "鸡",
    "duck": "鸭子", "fish": "鱼", "human": "人", "lion": "狮子",
    "tiger": "老虎", "bear": "熊", "rabbit": "兔子", "mouse": "老鼠",
}
_ZH_TERMS = {
    "altruist": "利他者", "egoist": "利己者", "angel": "天使", "devil": "恶魔",
    "knight": "骑士", "knave": "无赖", "pioneer": "先锋", "laggard": "落后者",
    "truth-teller": "说真话者", "liar": "说谎者", "prophet": "先知",
    "impostor": "冒牌者", "honest": "诚实者", "liar ": "说谎者",
    "sage": "贤者", "fool": "愚者", "truth teller": "说真话者",
    "sages": "贤者", "fools": "愚者",
}
_ZH_RELATIONS = {
    "father": "爸爸", "mother": "妈妈", "brother": "哥哥", "sister": "姐姐",
    "son": "儿子", "daughter": "女儿", "grandfather": "爷爷",
    "grandmother": "奶奶", "uncle": "叔叔", "aunt": "阿姨", "cousin": "表亲",
    "nephew": "侄子", "niece": "侄女", "husband": "丈夫", "wife": "妻子",
    "grandchild": "孙子/孙女",
}


def fetch(task: str = "knights_knaves", limit: int = None, size: int = None,
          seed: int = 42) -> list:
    """按白名单任务生成题目（reasoning-gym 自带验证）。"""
    if task not in TASKS:
        raise ValueError(f"reasoning_gym 白名单外的任务：{task}"
                         f"（可选：{'、'.join(TASKS)}）")
    from reasoning_gym import create_dataset
    n = size or limit or 50
    ds = create_dataset(task, size=n, seed=seed)
    items = []
    for i in range(len(ds)):
        it = ds[i]
        items.append(dict(it, _task=task, _index=i))
        if limit and len(items) >= limit:
            break
    return items


def _numeric_options(item, rng, allow_negative=True):
    ans = str(item.get("answer") or "").strip()
    try:
        correct = float(ans)
    except ValueError:
        return None
    opts = {correct}
    offsets = [-10, -5, -3, -2, -1, 1, 2, 3, 5, 10]
    rng.shuffle(offsets)
    for o in offsets:
        v = correct + o
        if (allow_negative or v >= 0) and v != correct \
                and abs(v - round(v)) < 1e-9:
            opts.add(v)
        if len(opts) >= 4:
            break
    if len(opts) < 2:
        return None
    opts = [int(v) if v.is_integer() else v for v in opts]
    rng.shuffle(opts)
    correct_disp = int(correct) if correct.is_integer() else correct
    return [str(x) for x in opts], opts.index(correct_disp)


def _time_options(ans, rng):
    """解析并生成时间/时长干扰项，支持 "HH:MM[:SS][.mmm]" 与 "N days[, HH:MM[:SS]]"。"""
    m = re.match(r"^(\d+) days(?:, (\d{1,2}):(\d{2})(?::(\d{2}))?)?$", ans)
    if m:
        total = int(m.group(1)) * 86400
        if m.group(2):
            total += int(m.group(2)) * 3600 + int(m.group(3)) * 60 \
                + int(m.group(4) or 0)
        opts = {ans}
        for delta in (60, 600, 3600, 86400, -60, -600, -3600, -86400):
            v = total + delta
            if v <= 0:
                continue
            days, rem = divmod(v, 86400)
            h, rem = divmod(rem, 3600)
            mi, s = divmod(rem, 60)
            if s:
                s_fmt = f"{days} days, {h:02d}:{mi:02d}:{s:02d}"
            else:
                s_fmt = f"{days} days, {h:02d}:{mi:02d}"
            if s_fmt != ans:
                opts.add(s_fmt)
            if len(opts) >= 4:
                break
        if len(opts) < 2:
            return None
        opts = list(opts)
        rng.shuffle(opts)
        return opts, opts.index(ans)

    m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?$", ans)
    if not m:
        return None
    total = int(m.group(1)) * 3600 + int(m.group(2)) * 60 \
        + int(m.group(3) or 0)
    has_sec = m.group(3) is not None
    opts = {ans}
    for delta in (10, 30, 60, 300, 600, 900, -10, -30, -60, -300, -600, -900):
        v = total + delta
        if 0 <= v < 24 * 3600:
            if has_sec:
                s = f"{v // 3600:02d}:{(v // 60) % 60:02d}:{v % 60:02d}"
            else:
                s = f"{v // 3600:02d}:{(v // 60) % 60:02d}"
            if s != ans:
                opts.add(s)
        if len(opts) >= 4:
            break
    if len(opts) < 2:
        return None
    opts = list(opts)
    rng.shuffle(opts)
    return opts, opts.index(ans)


def _options_for(item, task):
    rng = random.Random(f"{task}:{item.get('_index', 0)}")
    ans = str(item.get("answer") or "").strip()
    md = item.get("metadata") or {}

    if task in ("leg_counting", "letter_counting", "rectangle_count",
                "maze"):
        return _numeric_options(item, rng, allow_negative=False)
    if task in ("chain_sum", "number_sequence"):
        return _numeric_options(item, rng, allow_negative=True)

    if task == "syllogism":
        opts = ["Yes", "No"]
        rng.shuffle(opts)
        return opts, opts.index(ans) if ans in opts else None

    if task == "knights_knaves":
        names = md.get("names") or []
        sol = md.get("solution") or []
        if not names or len(names) > 3 or len(names) != len(sol):
            return None
        terms = md.get("knight_knave_terms") or {}
        a_knight = terms.get("a_knight", "a knight")
        a_knave = terms.get("a_knave", "a knave")
        combos = []
        for bits in range(1 << len(names)):
            desc = ", ".join(
                f"{names[i]} is {a_knight if (bits >> i) & 1 else a_knave}"
                for i in range(len(names)))
            combos.append(desc)
        correct = ", ".join(
            f"{names[i]} is {a_knight if sol[i] else a_knave}"
            for i in range(len(names)))
        if correct not in combos:
            return None
        rng.shuffle(combos)
        return combos, combos.index(correct)

    if task == "family_relationships":
        vocab = [v for v in _RELATION_VOCAB if v != ans.lower()]
        rng.shuffle(vocab)
        opts = [ans] + vocab[:3]
        rng.shuffle(opts)
        return opts, opts.index(ans)

    if task == "arc_1d":
        cells = ans.split()
        if len(cells) < 3:
            return None
        opts = {ans}
        for _ in range(30):
            cand = list(cells)
            a, b = rng.sample(range(len(cand)), 2)
            cand[a], cand[b] = cand[b], cand[a]
            if rng.random() < 0.4:
                i = rng.randrange(len(cand))
                cand[i] = str((int(cand[i]) + 1) % 10)
            s = " ".join(cand)
            if s != ans:
                opts.add(s)
            if len(opts) >= 4:
                break
        opts = list(opts)
        rng.shuffle(opts)
        return opts, opts.index(ans)

    if task == "time_intervals":
        return _time_options(ans, rng)

    return None


def _level_for(item, task) -> int:
    md = item.get("metadata") or {}
    d = md.get("difficulty") or {}

    def num(v, default=2):
        """兼容 difficulty 里可能是区间 [min, max] 的写法。"""
        if isinstance(v, (list, tuple)):
            return v[0]
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    if task == "number_sequence":
        # 序列复杂度 1~3 -> 等级 1~3（配合项数分布）
        return max(1, min(4, num(md.get("complexity"), 2)))
    if task == "maze":
        g = num(md.get("grid_size"), 7)
        return 2 if g <= 7 else (3 if g <= 11 else 4)
    if task == "family_relationships":
        fs = num(d.get("family_size") or md.get("family_size"), 5)
        return 2 if fs <= 5 else (3 if fs <= 7 else 4)
    if task == "arc_1d":
        sz = num(md.get("size"), 15)
        return 2 if sz <= 15 else (3 if sz <= 25 else 4)
    if task == "knights_knaves":
        return 2 if len(md.get("names") or []) <= 2 else 3
    if task == "chain_sum":
        nt = num(d.get("num_terms"), 3)
        nd = num(d.get("num_digits"), 2)
        return min(4, 1 + (1 if nt >= 4 else 0) + (1 if nd >= 3 else 0))
    if task == "leg_counting":
        na = num(d.get("num_animals") or md.get("num_animals"), 5)
        return 1 if na <= 4 else (2 if na <= 7 else 3)
    if task == "time_intervals":
        # 秒级 -> 2，天级（答案含 days）-> 3
        ans = str(item.get("answer") or "")
        return 3 if "days" in ans.lower() else 2
    if task == "letter_counting":
        return 1
    if task == "rectangle_count":
        return 2
    if task == "syllogism":
        return 2
    return 2


def normalize(item) -> NormalizedQuestion | None:
    if not isinstance(item, dict):
        return None
    task = item.get("_task", "")
    if task not in TASKS:
        return None
    q_text = (item.get("question") or "").strip()
    ans = (item.get("answer") or "").strip()
    if not q_text or not ans:
        return None
    res = _options_for(item, task)
    if not res:
        return None
    options, answer = res
    if not options or answer is None or len(set(options)) < 2:
        return None
    cfg = TASKS[task]
    source = make_source(name=SOURCE_NAME, license=LICENSE,
                         dataset_id=f"task={task}",
                         original_id=str(item.get("_index", 0)), url=_URL)
    prov = make_provenance(translator=_TRANSLATOR, modified=True)
    return NormalizedQuestion(
        source=source,
        provenance=prov,
        qtype="external_text",
        category=cfg["category"],
        skills=cfg["skills"],
        difficulty_level=_level_for(item, task),
        metadata=dict(item.get("metadata") or {}),
        story_title=f"Reasoning Gym · {task}",
        story_text=q_text,
        question_prompt="请选择正确答案：",
        options=options,
        answer=answer,
        explanation=("由 reasoning-gym 生成器算法验证（Apache-2.0），"
                     "未经儿童化改写，建议人工抽检后再开放。"),
    )


# ---------- 中文翻译（机器翻译，状态 machine） ----------

def _zh_animal(name: str) -> str:
    n = str(name).strip().lower()
    if n in _ZH_ANIMALS:
        return _ZH_ANIMALS[n]
    if n.endswith("s") and n[:-1] in _ZH_ANIMALS:
        return _ZH_ANIMALS[n[:-1]]
    return str(name)


def _zh_term(word: str) -> str:
    key = word.strip().lower()
    if key.endswith("s") and key[:-1] in _ZH_TERMS:
        return _ZH_TERMS[key[:-1]]
    return _ZH_TERMS.get(key, word)


def _zh_relation(word: str) -> str:
    return _ZH_RELATIONS.get(word.strip().lower(), word)


def _zh_knights_story(text: str, md: dict) -> str:
    # 常见句式：inhabited only by A and B. A always tell the truth, and B always lie.
    m = re.search(r"inhabited only by (\w+) and (\w+)\.?\s*"
                  r"\1[a-z]* always tell the truth, and \2[a-z]* always lie[.]?",
                  text, re.I)
    if m:
        a, b = m.group(1), m.group(2)
        head = (f"有一座小岛，岛上只有{_zh_term(a)}和{_zh_term(b)}。"
                f"{_zh_term(a)}总说真话，{_zh_term(b)}总说假话。")
        text = text[:m.start()] + head + text[m.end():]
    text = text.replace("You meet ", "你遇到了 ").replace(" inhabitants: ", " 个居民：")
    text = text.replace("You hear:", "你听到他们说：")

    def _stmt(mo):
        s = mo.group(0)
        s = re.sub(r" is (?:a|an) ", " 是", s)
        s = re.sub(r" if and only if ", " 当且仅当 ", s)
        s = re.sub(r"\bif ", "如果 ", s)
        s = re.sub(r"\band\b", "并且", s)
        s = re.sub(r"\bor\b", "或者", s)
        s = re.sub(r"\bnot\b", "不是", s)
        s = re.sub(r"\b(\w+)\b", lambda mm: _zh_term(mm.group(1)), s)
        return s

    text = re.sub(r'"[^"]+"', _stmt, text)
    text = text.replace("Who is a ", "谁是")
    text = text.replace(" and who is a ", "？谁又是")
    text = text.replace("?", "？")
    return text


def _zh_knights_option(opt: str, md: dict) -> str:
    # "X is a pioneer, Y is a laggard" -> "X 是先锋，Y 是落后者"
    parts = [p.strip() for p in str(opt).split(",")]
    out = []
    for p in parts:
        m = re.match(r"(.+?) is (?:a|an) (.+)$", p)
        if m:
            out.append(f"{m.group(1).strip()} 是{_zh_term(m.group(2))}")
        else:
            out.append(p)
    return "，".join(out)


def _zh_syllogism(text: str) -> str:
    replaces = [
        ("Consider these statements:", "已知以下陈述："),
        ("Does it logically follow that:", "那么，下面这个结论是否必然成立："),
        ("(Answer Yes or No)", "（回答“是”或“否”）"),
    ]
    for en, zh in replaces:
        text = text.replace(en, zh)
    text = text.replace("All ", "所有 ").replace("No ", "没有 ")
    text = text.replace("Some ", "有些 ").replace(" are ", " 都是 ")
    text = text.replace("? ", "？ ")
    return text


def _zh_family(text: str) -> str:
    text = text.replace("Respond only with the word that describes their "
                        "relationship.", "")
    text = text.replace("Respond only with the word that describes the "
                        "relationship.", "")
    def rel(m):
        return f"{m.group(1)} 是 {m.group(3)} 的{_zh_relation(m.group(2))}。"

    text = re.sub(r"(.+?) is (?:the )?(father|mother|brother|sister|son|"
                  r"daughter|grandfather|grandmother|uncle|aunt|cousin|"
                  r"nephew|niece|husband|wife|grandchild) of (.+?)[.]",
                  rel, text, flags=re.I)
    text = re.sub(r"(.+?) is married to (.+?)[.]",
                  r"\1 和 \2 结婚了。", text, flags=re.I)
    text = re.sub(r"They have a child called (.+?)[.]",
                  r"他们有个孩子叫 \1。", text)
    text = re.sub(r"They have children called (.+?) and (.+?)[.]",
                  r"他们有孩子叫 \1 和 \2。", text)
    text = re.sub(r"How is (.+?) related to (.+?)[?]",
                  r"\1 和 \2 是什么关系？", text)
    text = re.sub(r"What is (.+?) to (.+?)[?]",
                  r"\1 和 \2 是什么关系？", text)
    text = re.sub(r"What relation is (.+?) to (.+?)[?]",
                  r"\1 和 \2 是什么关系？", text)
    text = re.sub(r"Answer with (?:a single|one) word[.]?", "", text)
    return text


def _zh_arc(text: str) -> str:
    replaces = [
        ("Find the common rule that maps an input grid to an output grid, "
         "given the examples below.",
         "观察下面的例子，找出输入格子变成输出格子的规律。"),
        ("Example", "例子"), ("Input:", "输入："), ("Output:", "输出："),
        ("What is the output for the final test input?",
         "最后这个测试输入对应的输出是什么？"),
        ("Below is a test input grid. Predict the corresponding output grid "
         "by applying the rule you found.",
         "下面是一个测试输入格子。请用你找到的规律，预测它对应的输出格子。"),
        ("Describe how you derived the rule and your overall reasoning "
         "process in detail before you submit your answer.",
         "直接给出输出格子即可，不用描述推理过程。"),
        ("Your final answer should be just the test output grid itself.",
         "你的最终答案就是那个输出格子。"),
    ]
    for en, zh in replaces:
        text = text.replace(en, zh)
    return text


def zh_translate_question(q) -> dict:
    """给已转换的 Reasoning Gym 题生成中文版文本（机器翻译）。"""
    task = (q.source_info.dataset_id or "").replace("task=", "")
    story = q.story.text
    md = q.metadata or {}
    options_zh = list(q.options)
    prompt_zh = "请选择正确答案："

    if task == "number_sequence":
        nums = re.findall(r"-?\d+", story)
        story = "找规律：" + "，".join(nums[:5]) + "，？"
    elif task == "chain_sum":
        m = re.search(r"problem:\s*(.+?)=\s*$", story, re.I)
        if m:
            story = f"计算下面这个算式的结果：{m.group(1).strip()} ="
    elif task == "letter_counting":
        m = re.match(r'How many times does the letter "(\w)" appear in the '
                     r'text: "(.*)"', story, re.S | re.I)
        if m:
            story = (f"字母 “{m.group(1)}” 在下面这段文字里出现了多少次？\n"
                     f"“{m.group(2)}”")
    elif task == "time_intervals":
        m = re.search(r"started at (.+?) and ended at (.+?)[.]", story, re.I)
        if m:
            story = (f"一个任务从 {m.group(1)} 开始，到 {m.group(2)} 结束，"
                     f"一共持续了多久？")
        m2 = re.search(r"Calculate the time difference between ([\d:.]+) "
                       r"and ([\d:.]+)", story, re.I)
        if m2:
            story = f"计算 {m2.group(1)} 到 {m2.group(2)} 之间相差多长时间？"
        m3 = re.search(r"What is the duration between ([\d:.]+) and "
                       r"([\d:.]+)[?]", story, re.I)
        if m3:
            story = f"从 {m3.group(1)} 到 {m3.group(2)} 一共持续了多久？"
        story = re.sub(r"Answer in [\w:.]+[.]?", "（答案格式见选项）", story)
        story = re.sub(r"Express the result in [\w:.]+[.]?",
                       "（答案格式见选项）", story)
        story = re.sub(r"Please answer in [\w:.]+[.]?",
                       "（答案格式见选项）", story)
    elif task == "leg_counting":
        animals = md.get("animals") or {}
        if animals:
            parts = [f"{cnt} 只{_zh_animal(name)}"
                     for name, cnt in animals.items()]
            story = f"数一数：{'、'.join(parts)}，这些动物一共有多少条腿？"
        else:
            # 老题没有 metadata：直接从题面解析 "if you have N X, M Y ..."
            seg = re.search(r"if you have (.+?)[?]?$", story, re.I)
            if seg:
                pairs = re.findall(r"(\d+)\s+([a-zA-Z][a-zA-Z ]*?)"
                                   r"(?:,| and |\?|$)", seg.group(1) + " ")
                parts = [f"{n} 只{_zh_animal(name.strip())}"
                         for n, name in pairs]
                if parts:
                    story = (f"数一数：{'、'.join(parts)}，"
                             f"这些动物一共有多少条腿？")
    elif task == "maze":
        story = re.sub(r"Navigate from '([^']+)' \(start\) to '([^']+)' \(goal\):",
                       r"从 '\1'（起点）走到 '\2'（终点）：", story)
        story = re.sub(r"Legend: '([^']+)' = Wall, '([^']+)' = Passage",
                       r"说明：'\1' 是墙，'\2' 是通道", story)
        story = re.sub(r"What is the minimum number of steps (?:required )?"
                       r"to reach the goal[?]",
                       "最少需要走多少步才能到达终点？", story)
        story = story.replace("What is the minimum number of steps required?",
                              "最少需要走多少步？")
        story = story.replace("Give only the number of steps", "只回答步数")
    elif task == "rectangle_count":
        story = (story
                 .replace("Your task is to count how many rectangles are "
                          "present in an ASCII grid.",
                          "数一数下面的图形里一共有多少个长方形。")
                 .replace("Single rectangles are outlined with a '#'",
                          "单个长方形用 '#' 围成")
                 .replace("overlapping rectangles (max 2) are shown with '█'",
                          "重叠的长方形用 '█' 表示"))
    elif task == "syllogism":
        story = _zh_syllogism(story)
        options_zh = ["是", "否"]
    elif task == "knights_knaves":
        story = _zh_knights_story(story, md)
        options_zh = [_zh_knights_option(o, md) for o in q.options]
    elif task == "family_relationships":
        story = _zh_family(story)
        options_zh = [_zh_relation(o) for o in q.options]
    elif task == "arc_1d":
        story = _zh_arc(story)
    elif task == "basic_arithmetic" or "arithmetic" in task:
        m = re.search(r"(?:problem|solve):\s*(.+?)=\s*$", story, re.I)
        if m:
            story = f"计算：{m.group(1).strip()} ="

    return {
        "status": "machine",
        "story_title": q.story.title,
        "story_text": story,
        "constraints": [c.text for c in q.constraints],
        "options": options_zh,
        "question_prompt": prompt_zh,
        "explanation": q.explanation,
    }


# ---------- 儿童化改写（status=child_adapted） ----------

def _render_stmt(node, names, honest, liar) -> str:
    """把 knights_knaves 的结构化陈述渲染成儿童中文。"""
    if isinstance(node, str):
        return node
    op = node[0]
    if op == "telling-truth":
        return f"{names[node[1]]}是{honest}"
    if op == "lying":
        return f"{names[node[1]]}是{liar}"
    if op == "not":
        return f"不是（{_render_stmt(node[1], names, honest, liar)}）"
    if op == "and":
        return ("（" + _render_stmt(node[1], names, honest, liar)
                + "）并且（" + _render_stmt(node[2], names, honest, liar) + "）")
    if op == "or":
        return ("（" + _render_stmt(node[1], names, honest, liar)
                + "）或者（" + _render_stmt(node[2], names, honest, liar) + "）")
    if op == "->":
        return ("如果（" + _render_stmt(node[1], names, honest, liar)
                + "）那么（" + _render_stmt(node[2], names, honest, liar) + "）")
    if op == "iff":
        return ("（" + _render_stmt(node[1], names, honest, liar)
                + "）当且仅当（" + _render_stmt(node[2], names, honest, liar) + "）")
    return str(node)


def zh_child_question(q) -> dict:
    """儿童化改写：用元数据重建完整中文题面（儿童语言）。"""
    task = (q.source_info.dataset_id or "").replace("task=", "")
    md = q.metadata or {}
    options_zh = list(q.options)

    if task == "number_sequence":
        seq = md.get("sequence") or []
        story = ("小动物排队找规律：数字 " + "，".join(str(x) for x in seq)
                 + "，？")
        prompt_zh = "下一个数是多少？"
    elif task == "chain_sum":
        expr = (md.get("expression") or "").strip()
        story = f"算一算：{expr} = ？"
        prompt_zh = "这个算式的结果是多少？"
    elif task == "leg_counting":
        animals = md.get("animals") or {}
        parts = [f"{cnt} 只{_zh_animal(name)}" for name, cnt in animals.items()]
        story = f"数一数下面这些动物一共有多少条腿：{'、'.join(parts)}。"
        prompt_zh = "这些动物一共有多少条腿？"
    elif task == "maze":
        grid = md.get("grid") or []
        start, goal = md.get("start", "O"), md.get("goal", "@")
        maze_txt = "\n".join(grid)
        story = (f"小蚂蚁要从 '{start}'（起点）走到 '{goal}'（终点），"
                 f"只能走通道。迷宫是这样的：\n{maze_txt}")
        prompt_zh = "最少要走多少步才能到终点？"
    elif task == "time_intervals":
        st = str(md.get("start_time") or "")
        en = str(md.get("end_time") or "")
        st_t = st.split(" ")[-1] if " " in st else st
        en_t = en.split(" ")[-1] if " " in en else en
        story = f"小闹钟从 {st_t} 走到 {en_t}，一共过了多久？"
        prompt_zh = "一共过了多长时间？"
    elif task == "letter_counting":
        span = md.get("span") or []
        letter = md.get("target_letter", "?")
        story = (f"下面这段话里，字母 “{letter}” 一共出现了几次？\n"
                 + " ".join(str(w) for w in span))
        prompt_zh = f"字母 “{letter}” 出现了几次？"
    elif task == "knights_knaves":
        names = md.get("names") or []
        stmts = md.get("statements") or []
        terms = md.get("knight_knave_terms") or {}
        honest = _zh_term(terms.get("a_knight", "a knight").replace("a ", ""))
        liar = _zh_term(terms.get("a_knave", "a knave").replace("a ", ""))
        head = (f"有一座小岛，岛上住着诚实的人（{honest}）和爱说谎的人"
                f"（{liar}）。诚实的人只说真话，爱说谎的人只说假话。"
                f"你遇到了 {len(names)} 个小朋友：{'、'.join(names)}。他们说：")
        lines = [head]
        for i, stmt in enumerate(stmts):
            lines.append(f"{names[i]} 说：“{_render_stmt(stmt, names, honest, liar)}”")
        story = "\n".join(lines)
        prompt_zh = "谁是诚实的人，谁又是爱说谎的人？"
        options_zh = [_zh_knights_option(o, md) for o in q.options]
    elif task == "syllogism":
        p1 = _zh_syllogism(str(md.get("premise1") or ""))
        p2 = _zh_syllogism(str(md.get("premise2") or ""))
        concl = _zh_syllogism(str(md.get("conclusion") or ""))
        story = f"小侦探推理：\n1. {p1}\n2. {p2}\n\n那么，“{concl}”对不对？"
        prompt_zh = "这个结论成立吗？"
        options_zh = ["对", "不对"]
    elif task == "family_relationships":
        story = _zh_family(q.story.text).strip()
        prompt_zh = "他们是什么关系？"
        options_zh = [_zh_relation(o) for o in q.options]
    elif task == "rectangle_count":
        story = zh_translate_question(q)["story_text"]  # 保留 ASCII 图形
        prompt_zh = "一共有几个长方形？"
    elif task == "arc_1d":
        story = _zh_arc(q.story.text)
        prompt_zh = "请选择正确的输出格子："
    else:
        story = q.story.text
        prompt_zh = "请选择正确答案："

    return {
        "status": "child_adapted",
        "story_title": q.story.title,
        "story_text": story,
        "constraints": [c.text for c in q.constraints],
        "options": options_zh,
        "question_prompt": prompt_zh,
        "explanation": q.explanation,
    }
