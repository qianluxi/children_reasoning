"""三层去重（专家意见第十七节）。

Level 1：source + original_id（已有 qid 保证，导入时按 qid 跳过）
Level 2：文本 Hash（story/约束/选项/问题归一化后 SHA256）
Level 3：逻辑结构 Hash（排序后的 DSL 约束 + 选项逻辑）

文本去重默认开启；逻辑结构去重默认只统计不删除（同一结构换实体名的题
对儿童仍是不同内容），可用 --dedup-logic 开启硬删除。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .config import DATA_DIR, ensure_dirs

_DEDUP_PATH = DATA_DIR / "dedup" / "index.json"


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def text_hash(question) -> str:
    """题目内容哈希：题干 + 约束文字 + 选项 + 问题。"""
    parts = [question.story.text, question.question_prompt]
    parts += [c.text for c in question.constraints]
    parts += list(question.options)
    blob = "|".join(_normalize_text(p) for p in parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def logic_signature(question) -> str | None:
    """逻辑结构哈希：排序后的约束 DSL + 选项 DSL（仅限可 DSL 的题）。"""
    logics = [c.logic for c in question.constraints if c.logic] \
        + [o for o in question.option_logic if o]
    if not logics:
        return None
    blob = "|".join(sorted(logics))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _index() -> dict:
    ensure_dirs()
    if not _DEDUP_PATH.exists():
        return {"by_text": {}, "by_logic": {}}
    try:
        return json.loads(_DEDUP_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"by_text": {}, "by_logic": {}}


def _save(index: dict) -> None:
    ensure_dirs()
    _DEDUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _DEDUP_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    import os
    os.replace(tmp, _DEDUP_PATH)


def check(question) -> dict:
    """返回 {text_dup: bool, logic_dup: bool, logic_dup_qid}。"""
    idx = _index()
    th = text_hash(question)
    ls = logic_signature(question)
    text_dup = th in idx.get("by_text", {})
    logic_dup = bool(ls) and ls in idx.get("by_logic", {})
    return {
        "text_dup": text_dup,
        "logic_dup": logic_dup,
        "logic_dup_qid": idx.get("by_logic", {}).get(ls) if ls else None,
    }


def register(question) -> None:
    """题目入库后登记哈希。"""
    idx = _index()
    th = text_hash(question)
    ls = logic_signature(question)
    idx.setdefault("by_text", {})[th] = question.id
    if ls:
        idx.setdefault("by_logic", {})[ls] = question.id
    _save(idx)


def clear() -> None:
    _DEDUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    _save({"by_text": {}, "by_logic": {}})


def duplicate_report() -> dict:
    """分级去重报告（专家意见第十一节）：
    文本完全重复 / 逻辑结构重复 / 各题型模板数量。"""
    from . import taxonomy
    from .bank import external, store
    from collections import Counter
    texts = Counter()
    sigs = Counter()
    archs = Counter()
    for qid in store.list_ids():
        q = store.load_question(qid)
        if q is None:
            continue
        texts[text_hash(q)] += 1
        sig = logic_signature(q)
        if sig:
            sigs[sig] += 1
        archs[q.archetype or "generic"] += 1
    for s in external.list_sources():
        for qid in external.list_ids(s["slug"]):
            q = external.load_question(s["slug"], qid)
            if q is None:
                continue
            texts[text_hash(q)] += 1
            sig = logic_signature(q)
            if sig:
                sigs[sig] += 1
            archs[q.archetype or "generic"] += 1
    return {
        "exact_text_duplicates": sum(n - 1 for n in texts.values() if n > 1),
        "structure_duplicates": sum(n - 1 for n in sigs.values() if n > 1),
        "by_archetype": {a: n for a, n in archs.most_common()},
    }


def report_text() -> str:
    r = duplicate_report()
    from . import taxonomy
    lines = [f"文本完全重复（应删除）: {r['exact_text_duplicates']}",
             f"逻辑结构重复（建议控制比例）: {r['structure_duplicates']}",
             "按题型模板（archetype）分布:"]
    for a, n in r["by_archetype"].items():
        lines.append(f"  {taxonomy.archetype_label(a):14s} {n}")
    return "\n".join(lines)
