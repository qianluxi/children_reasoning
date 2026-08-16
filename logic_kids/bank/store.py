"""题库存储：每道题一个 JSON 文件 + 轻量索引（专家意见第十二节的文件化实现）。

目录结构：
    data/questions/<id>.json     题目全文
    data/bank_index.json         索引：id -> {type, difficulty, difficulty_score, source}

写入采用"临时文件 + os.replace"原子替换，索引损坏时报错而不是静默当空题库
（专家审查 P1：避免程序中断后 index 与 questions 失同步）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from ..config import QUESTIONS_DIR, BANK_INDEX_PATH, ensure_dirs
from ..difficulty import levels
from ..models import Question, ensure_builtin_source, ensure_taxonomy


def _atomic_write(path: Path, text: str) -> None:
    """临时文件 + os.replace 原子替换，避免写一半留下损坏文件。"""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _index() -> dict:
    if not BANK_INDEX_PATH.exists():
        return {}  # 首次运行，还没有索引
    try:
        return json.loads(BANK_INDEX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        # 索引损坏不能静默当空题库（否则会重新生成并与旧题文件失同步）
        raise RuntimeError(f"题库索引损坏（{BANK_INDEX_PATH}）：{e}") from e
    except OSError:
        return {}


def _save_index(index: dict) -> None:
    ensure_dirs()
    _atomic_write(BANK_INDEX_PATH, json.dumps(index, ensure_ascii=False, indent=2))


def save_question(q: Question) -> None:
    ensure_dirs()
    ensure_builtin_source(q)  # 内置题缺省来源；外部题已有自己的 source_info
    ensure_taxonomy(q)
    path = QUESTIONS_DIR / f"{q.id}.json"
    _atomic_write(path, q.to_json())
    index = _index()
    level = q.difficulty_level or levels.level_for_score(q.difficulty_score)
    index[q.id] = {
        "type": q.type,
        "difficulty": q.difficulty,
        "difficulty_score": q.difficulty_score,
        "difficulty_level": level,
        "source": q.source,
        "title": q.story.title,
        "category": q.category,
        "quality": q.quality or "A",
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


def _meta_level(meta: dict) -> int:
    """索引里的等级；旧索引没有时按评分反算。"""
    lv = meta.get("difficulty_level")
    if lv is None:
        lv = levels.level_for_score(meta.get("difficulty_score", 0.0))
    return lv


def query(qtype: str = None, difficulty: int = None,
          difficulty_level: int = None, source: str = None,
          exclude_ids: set = None, category: str = None) -> list:
    """按条件过滤，返回题目 id 列表。

    difficulty_level 是用户可见等级（1..4），按难度分区间过滤；
    difficulty 是内部星级（1..5）。
    """
    index = _index()
    exclude_ids = exclude_ids or set()
    ids = []
    for qid, meta in index.items():
        if qtype and meta.get("type") != qtype:
            continue
        if difficulty is not None and meta.get("difficulty") != difficulty:
            continue
        if difficulty_level is not None and _meta_level(meta) != difficulty_level:
            continue
        if source is not None and meta.get("source") != source:
            continue
        if category is not None and meta.get("category") != category:
            continue
        if qid in exclude_ids:
            continue
        ids.append(qid)
    return ids


def stats() -> dict:
    """题库统计：按类型、星级、用户等级、来源、能力汇总。"""
    index = _index()
    by_type, by_diff, by_level, by_source, by_category = {}, {}, {}, {}, {}
    for meta in index.values():
        by_type[meta["type"]] = by_type.get(meta["type"], 0) + 1
        by_diff[meta["difficulty"]] = by_diff.get(meta["difficulty"], 0) + 1
        lv = _meta_level(meta)
        by_level[lv] = by_level.get(lv, 0) + 1
        by_source[meta["source"]] = by_source.get(meta["source"], 0) + 1
        cat = meta.get("category") or "deduction"
        by_category[cat] = by_category.get(cat, 0) + 1
    return {"total": len(index), "by_type": by_type,
            "by_difficulty": by_diff, "by_level": by_level,
            "by_source": by_source, "by_category": by_category}


def clear() -> None:
    ensure_dirs()
    for p in QUESTIONS_DIR.glob("*.json"):
        p.unlink()
    _save_index({})
