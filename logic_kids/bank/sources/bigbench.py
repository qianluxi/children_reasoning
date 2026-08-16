"""BIG-bench logical_deduction 导入适配器（专家意见 Phase 3 首个外部源）。

许可证：Apache-2.0（google/BIG-bench 官方仓库），可商用，优先于 LogiQA。

规则翻译器（translator=bigbench_logical_deduction_rule_v1）：
    - 把 "X is to the left/right of Y" / "X is older than Y" /
      "X finished above Y" 等相对句转为 RANK(X) < RANK(Y)；
    - 把 "X is the leftmost / second from the right / oldest / most expensive"
      等绝对句转为 RANK(X) == k；
    - 每个 example 是一道"某位置是谁"的选择题：选项即 target_scores 的全部候选句。

翻译不了的例句直接跳过并在导入报告里计数，绝不让未解析内容混入题库
（专家意见第九节：不强行转换外部题）。
"""
from __future__ import annotations

import json
import re
import urllib.request

from ..normalizer import NormalizedQuestion
from ..provenance import make_source, make_provenance
from ...models import Variable, Constraint

SOURCE_NAME = "BIG-bench"
LICENSE = "Apache-2.0"

_BASE_URL = ("https://raw.githubusercontent.com/google/BIG-bench/main/"
             "bigbench/benchmark_tasks/{task}/task.json")
_CDN_URL = ("https://cdn.jsdelivr.net/gh/google/BIG-bench@main/"
            "bigbench/benchmark_tasks/{task}/task.json")

# BIG-bench 已于 2026-04-17 归档为只读（专家意见第六节）：
# 固定到归档时的 main commit，避免"永远拉最新"。
BIGBENCH_REF = "092b196c1f8f14a54bbc62f24759d43bde46dd3b"
_TRANSLATOR = "bigbench_logical_deduction_rule_v1"

_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4,
             "fifth": 5, "sixth": 6, "seventh": 7}
_INTRO_RE = re.compile(r"there (are|were|is)|sells", re.I)

_REL_PATTERNS = [
    (re.compile(r"^(.+?)\s+is\s+(?:somewhere\s+)?to\s+the\s+(left|right)\s+of\s+(.+?)$", re.I), "left/right"),
    (re.compile(r"^(.+?)\s+(?:is|are)\s+older\s+than\s+(.+?)$", re.I), "older"),
    (re.compile(r"^(.+?)\s+(?:is|are)\s+newer\s+than\s+(.+?)$", re.I), "newer"),
    (re.compile(r"^(.+?)\s+(?:is|are)\s+more\s+expensive\s+than\s+(.+?)$", re.I), "pricier"),
    (re.compile(r"^(.+?)\s+(?:is|are)\s+less\s+expensive\s+than\s+(.+?)$", re.I), "cheaper"),
    (re.compile(r"^(.+?)\s+(?:is|are)\s+cheaper\s+than\s+(.+?)$", re.I), "cheaper"),
    (re.compile(r"^(.+?)\s+finished\s+above\s+(.+?)$", re.I), "above"),
    (re.compile(r"^(.+?)\s+finished\s+below\s+(.+?)$", re.I), "below"),
]

_ABS_IS_RE = re.compile(
    r"^(.+?)\s+(?:is|are)\s+(?:the\s+)?"
    r"(leftmost|rightmost|first|last|oldest|newest|most expensive|cheapest"
    r"|(?:second|third|fourth|fifth|sixth|seventh)(?:-|\s+)"
    r"(?:from the (?:left|right)|oldest|newest|most expensive|cheapest|to-last))$",
    re.I)
_ABS_FINISHED_RE = re.compile(
    r"^(.+?)\s+finished\s+"
    r"(first|last|second|third|fourth|fifth|sixth|seventh|"
    r"second-to-last|third-to-last|fourth-to-last)$", re.I)

# 儿童友好的常见词汇（机器翻译词典，覆盖 BIG-bench logical_deduction 常用词）
_ZH_WORDS = {
    # 颜色
    "black": "黑色", "white": "白色", "red": "红色", "orange": "橙色",
    "yellow": "黄色", "green": "绿色", "blue": "蓝色", "purple": "紫色",
    "gray": "灰色", "grey": "灰色", "brown": "棕色", "pink": "粉色",
    # 物品
    "book": "书", "ball": "球", "bird": "鸟", "car": "汽车", "truck": "卡车",
    "bus": "公交车", "van": "面包车", "sedan": "轿车", "hatchback": "掀背车",
    "station wagon": "旅行车", "motorcycle": "摩托车", "tractor": "拖拉机",
    # 水果
    "fruit": "水果", "apple": "苹果", "orange": "橙子", "kiwi": "猕猴桃",
    "pear": "梨", "peach": "桃子", "plum": "李子", "loquat": "枇杷",
    "mango": "芒果", "watermelon": "西瓜", "cantaloupe": "哈密瓜",
    "grapefruit": "柚子", "grapes": "葡萄", "banana": "香蕉", "berries": "浆果",
    "pineapple": "菠萝", "lemon": "柠檬", "cherries": "樱桃",
    # 鸟类
    "raven": "乌鸦", "falcon": "猎鹰", "crow": "乌鸦", "cardinal": "红衣凤头鸟",
    "hawk": "鹰", "owl": "猫头鹰", "robin": "知更鸟", "hummingbird": "蜂鸟",
    "sparrow": "麻雀", "eagle": "鹰", "quail": "鹌鹑", "goose": "鹅",
    "duck": "鸭子", "pigeon": "鸽子", "swallow": "燕子", "parrot": "鹦鹉",
    "woodpecker": "啄木鸟", "heron": "鹭", "flamingo": "火烈鸟", "crane": "鹤",
    "wren": "鹪鹩", "bluebird": "蓝知更鸟", "dove": "鸽子", "turkey": "火鸡",
}


def _zh_name(name: str) -> str:
    """英文实体名 -> 中文（词典翻译；人名/未知词保留原文）。"""
    n = re.sub(r"^(the|a|an)\s+", "", (name or "").strip(), flags=re.I).lower()
    if n in _ZH_WORDS:
        return _ZH_WORDS[n]
    words = n.split()
    if len(words) == 2 and words[0] in _ZH_WORDS and words[1] in _ZH_WORDS:
        return _ZH_WORDS[words[0]] + "的" + _ZH_WORDS[words[1]]
    if len(words) == 1:
        if words[0] in _ZH_WORDS:
            return _ZH_WORDS[words[0]]
        if words[0].endswith("s") and words[0][:-1] in _ZH_WORDS:
            return _ZH_WORDS[words[0][:-1]]
    return name.strip()


def _zh_predicate(phrase: str) -> str | None:
    """位置/结果短语 -> 中文谓语（如 "排在最左边"、"最年长"）。"""
    p = re.sub(r"^(?:the\s+)?", "", (phrase or "").strip().lower())
    base = {
        "leftmost": "排在最左边", "rightmost": "排在最右边",
        "first": "得了第一名", "last": "得了最后一名",
        "oldest": "最年长", "newest": "最新",
        "most expensive": "最贵", "cheapest": "最便宜",
    }
    if p in base:
        return base[p]
    m = re.fullmatch(r"(second|third|fourth|fifth|sixth|seventh)(?:-|\s+)(.+)", p)
    if not m:
        return None
    k = _ORDINALS[m.group(1)]
    rest = m.group(2)
    if rest == "to-last":
        return f"得了倒数第 {k} 名"
    if rest.startswith("from the left"):
        return f"排在从左数第 {k} 位"
    if rest.startswith("from the right"):
        return f"排在从右数第 {k} 位"
    if rest == "oldest":
        return f"排第 {k} 年长"
    if rest == "newest":
        return f"排第 {k} 新"
    if rest == "most expensive":
        return f"排第 {k} 贵"
    if rest == "cheapest":
        return f"排第 {k} 便宜"
    return None


def _zh_constraint(sentence: str) -> str:
    """把一条英文约束句翻译成中文；翻译不了保留原文。"""
    s = sentence.strip()
    m = re.match(r"^(.+?)\s+is\s+(?:somewhere\s+)?to\s+the\s+(left|right)\s+of\s+(.+?)$",
                 s, re.I)
    if m:
        d = "左边" if m.group(2) == "left" else "右边"
        return f"{_zh_name(m.group(1))} 在 {_zh_name(m.group(3))} 的{d}。"
    for pattern, zh in [
        (r"^(.+?)\s+(?:is|are)\s+older\s+than\s+(.+?)$", "{a} 比 {b} 年长。"),
        (r"^(.+?)\s+(?:is|are)\s+newer\s+than\s+(.+?)$", "{a} 比 {b} 更新。"),
        (r"^(.+?)\s+(?:is|are)\s+more\s+expensive\s+than\s+(.+?)$", "{a} 比 {b} 更贵。"),
        (r"^(.+?)\s+(?:is|are)\s+(?:less\s+expensive|cheaper)\s+than\s+(.+?)$", "{a} 比 {b} 更便宜。"),
        (r"^(.+?)\s+finished\s+above\s+(.+?)$", "{a} 的名次在 {b} 前面。"),
        (r"^(.+?)\s+finished\s+below\s+(.+?)$", "{a} 的名次在 {b} 后面。"),
    ]:
        m = re.match(pattern, s, re.I)
        if m:
            return zh.format(a=_zh_name(m.group(1)), b=_zh_name(m.group(2)))
    m = _ABS_IS_RE.match(s) or _ABS_FINISHED_RE.match(s)
    if m:
        pred = _zh_predicate(m.group(2))
        if pred:
            return f"{_zh_name(m.group(1))}{pred}。"
    return sentence


def _zh_story(intro: str, names_zh: list, n: int) -> str:
    """故事开头 -> 中文（按场景模板翻译）。"""
    low = (intro or "").lower()
    if "on a shelf" in low:
        ctx = "书架上"
    elif "on a branch" in low:
        ctx = "树枝上"
    elif "fruit stand" in low or "sells" in low:
        ctx = "水果摊上"
    elif "race" in low or "tournament" in low:
        ctx = "比赛里"
    else:
        ctx = "题目里"
    return f"在{ctx}有 {n} 个：{'、'.join(names_zh)}。"


def zh_translate_question(q) -> dict:
    """给已转换的 BIG-bench 题生成中文版文本（story/constraints/options）。"""
    names_zh = [_zh_name(q.story.roles.get(c, c)) for c in q.entities]
    return {
        "status": "machine",
        "story_title": q.story.title,
        "story_text": _zh_story(q.story.text, names_zh, len(q.entities)),
        "constraints": [_zh_constraint(c.text) for c in q.constraints],
        "options": [_zh_option(o) for o in q.options],
        "question_prompt": q.question_prompt,
        "explanation": q.explanation,
    }


def _zh_option(opt: str) -> str:
    """选项句 -> 中文（"The X is the leftmost." -> "X 排在最左边。"）。"""
    stmt = opt.strip().rstrip(".")
    m = _ABS_IS_RE.match(stmt) or _ABS_FINISHED_RE.match(stmt)
    if m:
        pred = _zh_predicate(m.group(2))
        if pred:
            return f"{_zh_name(m.group(1))}{pred}。"
    return opt


def fetch(task: str = "logical_deduction/three_objects", limit: int = None) -> list:
    """拉取 BIG-bench task.json（固定版本，jsDelivr CDN 优先，GitHub raw 兜底）。"""
    import os
    ref = os.environ.get("BIGBENCH_REF", BIGBENCH_REF)
    urls = [
        _CDN_URL.replace("@main", f"@{ref}").format(task=task),
        _BASE_URL.replace("/main/", f"/{ref}/").format(task=task),
    ]
    last_err = None
    for url in urls:
        for _ in range(3):  # 每个镜像重试 3 次
            try:
                with urllib.request.urlopen(url, timeout=45) as r:
                    data = json.load(r)
                break
            except Exception as e:  # 网络抖动：换镜像/重试
                last_err = e
        else:
            continue
        break
    else:
        raise RuntimeError(f"BIG-bench 下载失败：{last_err}") from last_err
    items = [dict(ex, _task=task, _index=i)
             for i, ex in enumerate(data.get("examples", []))]
    return items[:limit] if limit is not None else items


def _extract_entities(intro: str) -> list | None:
    if ":" not in intro:
        return None
    tail = intro.split(":", 1)[1]
    parts = []
    for chunk in re.split(r",\s*", tail.strip()):
        # 兼容 "and a blue book"（and 位于段首）与 "A and B"（and 在中间）
        for p in re.split(r"\band\b", chunk, flags=re.I):
            p = p.strip()
            if p:
                parts.append(p)
    names = []
    for p in parts:
        p = re.sub(r"^(a|an|the)\s+", "", p, flags=re.I).strip()
        if p:
            names.append(p)
    return names or None


def _position_rank(phrase: str, n: int) -> int | None:
    """位置短语 -> rank（1 = 最左/第一/最老/最贵）。"""
    p = re.sub(r"^(?:the\s+)?", "", phrase.strip().lower())
    base = {"leftmost": 1, "first": 1, "oldest": 1, "most expensive": 1,
            "rightmost": n, "last": n, "newest": n, "cheapest": n}
    if p in base:
        return base[p]
    m = re.fullmatch(r"(second|third|fourth|fifth|sixth|seventh)(?:-|\s+)(.+)", p)
    if not m:
        return None
    k = _ORDINALS[m.group(1)]
    rest = m.group(2)
    if rest == "to-last":
        return n - k + 1
    if rest.startswith("from the left"):
        return k
    if rest.startswith("from the right"):
        return n - k + 1
    if rest in ("oldest", "most expensive"):
        return k
    if rest in ("newest", "cheapest"):
        return n - k + 1
    return None


def _prompt_zh(phrase: str, rank: int, n: int) -> str:
    p = re.sub(r"^(?:the\s+)?", "", phrase.strip().lower())
    base = {
        "leftmost": "谁排在最左边？", "rightmost": "谁排在最右边？",
        "first": "谁是第 1 名？", "last": "谁是最后一名？",
        "oldest": "谁最年长？", "newest": "谁最新？",
        "most expensive": "谁最贵？", "cheapest": "谁最便宜？",
    }
    if p in base:
        return base[p]
    m = re.fullmatch(r"(second|third|fourth|fifth|sixth|seventh)(?:-|\s+)(.+)", p)
    if not m:
        return None
    k = _ORDINALS[m.group(1)]
    rest = m.group(2)
    if rest == "to-last":
        return f"谁排倒数第 {k} 名？"
    if rest.startswith("from the left"):
        return f"谁排在从左数第 {k} 位？"
    if rest.startswith("from the right"):
        return f"谁排在从右数第 {k} 位？"
    if rest == "oldest":
        return f"谁排第 {k} 年长？"
    if rest == "newest":
        return f"谁排第 {k} 新？"
    if rest == "most expensive":
        return f"谁排第 {k} 贵？"
    if rest == "cheapest":
        return f"谁排第 {k} 便宜？"
    return None


def _parse_relative(sentence: str):
    for pat, kind in _REL_PATTERNS:
        m = pat.match(sentence)
        if not m:
            continue
        if kind == "left/right":
            x, d, y = m.group(1).strip(), m.group(2), m.group(3).strip()
            return x, y, d == "left"
        x, y = m.group(1).strip(), m.group(2).strip()
        lt = kind in ("older", "above", "pricier")  # 更老/更靠前/更贵 -> rank 更小
        return x, y, lt
    return None


def _parse_absolute(sentence: str):
    m = _ABS_IS_RE.match(sentence) or _ABS_FINISHED_RE.match(sentence)
    if not m:
        return None
    return m.group(1).strip(), m.group(2).strip()


def _find_code(entity_name: str, lower_to_code: dict) -> str | None:
    key = re.sub(r"^(the|a|an)\s+", "", entity_name.strip(),
                 flags=re.I).lower()
    return lower_to_code.get(key)


def normalize(item: dict) -> NormalizedQuestion | None:
    """把一个 BIG-bench example 转换为统一题目；翻译不了返回 None。"""
    if not isinstance(item, dict):
        return None
    text = (item.get("input") or "").strip()
    scores = item.get("target_scores") or {}
    task = item.get("_task", "")
    idx = item.get("_index", 0)

    sentences = [s.strip() for s in text.split(".") if s.strip()]
    intro = next((s for s in sentences if _INTRO_RE.search(s)), None)
    if intro is None:
        return None
    names = _extract_entities(intro)
    if not names:
        return None
    if len(set(n.lower() for n in names)) != len(names):
        return None  # 实体重名无法可靠建模
    n = len(names)
    codes = [chr(ord("A") + i) for i in range(n)]
    lower_to_code = {nm.lower(): code for nm, code in zip(names, codes)}
    roles = {code: nm for code, nm in zip(codes, names)}

    # ---- 约束（相对 + 绝对） ----
    constraints = []
    for s in sentences:
        if _INTRO_RE.search(s):
            continue
        rel = _parse_relative(s)
        if rel is not None:
            x, y, x_lt_y = rel
            cx, cy = _find_code(x, lower_to_code), _find_code(y, lower_to_code)
            if cx is None or cy is None:
                return None
            op = "<" if x_lt_y else ">"
            constraints.append(Constraint(
                text=s,
                logic=f"RANK({cx}) {op} RANK({cy})"))
            continue
        abs_ = _parse_absolute(s)
        if abs_ is not None:
            x, phrase = abs_
            cx = _find_code(x, lower_to_code)
            if cx is None:
                return None
            rank = _position_rank(phrase, n)
            if rank is None:
                return None
            constraints.append(Constraint(
                text=s,
                logic=f"RANK({cx}) == {rank}"))
            continue
        return None  # 有句子翻译不了 -> 整例跳过，绝不半截入库

    if not constraints:
        return None

    # ---- 选项与答案 ----
    correct = [k for k, v in scores.items() if v == 1]
    if len(correct) != 1:
        return None
    options = list(scores.keys())
    try:
        answer = options.index(correct[0])
    except ValueError:
        return None
    ans_stmt = options[answer].lower()
    ans_stmt = correct[0].strip().rstrip(".")
    phrase_match = _ABS_IS_RE.match(ans_stmt) or _ABS_FINISHED_RE.match(ans_stmt)
    if phrase_match is None:
        return None
    pos_phrase = phrase_match.group(2).strip()
    rank = _position_rank(pos_phrase, n)
    if rank is None:
        return None
    prompt = _prompt_zh(pos_phrase, rank, n)
    if prompt is None:
        return None

    # 每个选项都是"某实体 = 该位置"的陈述
    option_logic = []
    for stmt in options:
        hit = None
        for nm, code in zip(names, codes):
            if re.search(r"\b" + re.escape(nm.lower()) + r"\b", stmt.lower()):
                if hit is not None:
                    return None  # 一个选项里出现多个实体名，无法可靠定位
                hit = code
        if hit is None:
            return None
        option_logic.append(f"RANK({hit}) == {rank}")

    variables = [Variable(f"rank_{c}", "rank") for c in codes]
    source = make_source(name=SOURCE_NAME, license=LICENSE,
                         dataset_id=task, original_id=str(idx),
                         url=_BASE_URL.format(task=task))
    prov = make_provenance(translator=_TRANSLATOR, modified=True)

    return NormalizedQuestion(
        source=source,
        provenance=prov,
        qtype="ordering",
        category="ordering",
        skills=["ordering", "transitive_reasoning", "deduction"],
        story_title=f"BIG-bench 逻辑推理 · {task}",
        story_text=intro,
        entities=codes,
        roles=roles,
        variables=variables,
        constraints=constraints,
        question_prompt=prompt,
        options=options,
        option_logic=option_logic,
        answer=answer,
        hints=["把每条线索先翻译成“谁在谁前面/后面”。",
               "把能确定的位置先固定下来，再继续推。"],
        explanation=(f"来自 BIG-bench logical_deduction 第 {idx} 例，"
                     f"由规则翻译器转换（{LICENSE}），未经人工改写。"),
    )
