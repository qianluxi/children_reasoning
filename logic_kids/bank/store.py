"""题库存储：每道题一个 JSON 文件 + 轻量索引（专家意见第十二节的文件化实现）。

目录结构：
    data/questions/<id>.json     题目全文
    data/bank_index.json         索引：id -> {type, difficulty, difficulty_score, source}
"""
from __future__ import annotations

import json
from pathlib import Path

from ..config import QUESTIONS_DIR, BANK_INDEX_PATH, ensure_dirs
from ..models import Question


def _index() -> dict:
    if BANK_INDEX_PATH.exists():
        try:
            return json.loads(BANK_INDEX_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_index(index: dict) -> None:
    ensure_dirs()
    BANK_INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def save_question(q: Question) -> None:
    ensure_dirs()
    path = QUESTIONS_DIR / f"{q.id}.json"
    path.write_text(q.to_json(), encoding="utf-8")
    index = _index()
    index[q.id] = {
        "type": q.type,
        "difficulty": q.difficulty,
        "difficulty_score": q.difficulty_score,
        "source": q.source,
        "title": q.story.title,
    }
    _save_index(index)


def save_many(questions: list) -> int:
    n = 0
    for q in questions:
        save_question(q)
        n += 1
    return n


def load_question(qid: str) -> Question | None:
    path = QUESTIONS_DIR / f"{qid}.json"
    if not path.exists():
        return None
    return Question.from_json(path.read_text(encoding="utf-8"))


def list_ids() -> list:
    return list(_index().keys())


def query(qtype: str = None, difficulty: int = None, source: str = None) -> list:
    """按条件过滤，返回题目 id 列表。"""
    index = _index()
    ids = []
    for qid, meta in index.items():
        if qtype and meta.get("type") != qtype:
            continue
        if difficulty and meta.get("difficulty") != difficulty:
            continue
        if source and meta.get("source") != source:
            continue
        ids.append(qid)
    return ids


def stats() -> dict:
    """题库统计：按类型、难度、来源汇总。"""
    index = _index()
    by_type, by_diff, by_source = {}, {}, {}
    for meta in index.values():
        by_type[meta["type"]] = by_type.get(meta["type"], 0) + 1
        by_diff[meta["difficulty"]] = by_diff.get(meta["difficulty"], 0) + 1
        by_source[meta["source"]] = by_source.get(meta["source"], 0) + 1
    return {"total": len(index), "by_type": by_type,
            "by_difficulty": by_diff, "by_source": by_source}


def clear() -> None:
    ensure_dirs()
    for p in QUESTIONS_DIR.glob("*.json"):
        p.unlink()
    _save_index({})
