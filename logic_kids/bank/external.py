"""外部题库独立存储（专家意见第十八节：Level B 开放题库按来源分目录管理）。

与内置题库（data/questions/ + bank_index.json）完全分开：

    data/external/<来源slug>/
        <qid>.json       题目全文
        index.json       该来源索引：id -> {type, difficulty_score, difficulty_level, ...}

审核通过的外部题写入这里，儿童在界面选择"外部题库 → 某来源"后，
QuestionSelector 只从对应来源选题。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from ..config import EXTERNAL_DIR, ensure_dirs
from ..difficulty import levels
from ..models import Question

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def source_slug(source_name: str) -> str:
    """来源名 -> 目录 slug：BIG-bench -> bigbench，LogiQA2.0 -> logiqa20。"""
    return _SLUG_RE.sub("", (source_name or "").lower())


def source_dir(slug: str) -> Path:
    path = EXTERNAL_DIR / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def _index_path(slug: str) -> Path:
    return source_dir(slug) / "index.json"


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _index(slug: str) -> dict:
    path = _index_path(slug)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"外部题库索引损坏（{path}）：{e}") from e


def _save_index(slug: str, index: dict) -> None:
    ensure_dirs()
    _atomic_write(_index_path(slug),
                  json.dumps(index, ensure_ascii=False, indent=2))


def save_question(q: Question) -> None:
    """写入外部题库（按题目 source_info.name 分目录）。"""
    ensure_dirs()
    name = q.source_info.name if q.source_info else "external"
    slug = source_slug(name)
    path = source_dir(slug) / f"{q.id}.json"
    _atomic_write(path, q.to_json())
    index = _index(slug)
    index[q.id] = {
        "type": q.type,
        "difficulty": q.difficulty,
        "difficulty_score": q.difficulty_score,
        "difficulty_level": q.difficulty_level
        or levels.level_for_score(q.difficulty_score),
        "source": name,
        "title": q.story.title,
        "license": (q.source_info.license if q.source_info else ""),
        "category": q.category or "deduction",
        "quality": q.quality or "C",
    }
    _save_index(slug, index)


def load_question(slug: str, qid: str) -> Question | None:
    path = source_dir(slug) / f"{qid}.json"
    if not path.exists():
        return None
    return Question.from_json(path.read_text(encoding="utf-8"))


def load_question_any(qid: str) -> Question | None:
    """在全部外部来源里按 id 查找（判题/提示用）。"""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", qid or ""):
        return None  # 防御：拒绝路径穿越
    ensure_dirs()
    for slug_dir in EXTERNAL_DIR.iterdir():
        if not slug_dir.is_dir():
            continue
        p = slug_dir / f"{qid}.json"
        if p.exists():
            return Question.from_json(p.read_text(encoding="utf-8"))
    return None


def list_sources() -> list:
    """列出外部题库来源（含题数与许可证）。"""
    ensure_dirs()
    result = []
    for slug_dir in sorted(EXTERNAL_DIR.iterdir()):
        if not slug_dir.is_dir():
            continue
        idx = _index(slug_dir.name)
        if not idx:
            continue
        first = next(iter(idx.values()))
        result.append({
            "slug": slug_dir.name,
            "name": first.get("source", slug_dir.name),
            "license": first.get("license", ""),
            "total": len(idx),
        })
    return result


def list_ids(slug: str = None) -> list:
    if slug:
        return list(_index(slug).keys())
    ids = []
    for s in list_sources():
        ids.extend(list(_index(s["slug"]).keys()))
    return ids


def query(slug: str = None, qtype: str = None, difficulty: int = None,
          difficulty_level: int = None, exclude_ids: set = None,
          category: str = None) -> list:
    """按来源/题型/等级过滤外部题，返回 id 列表。"""
    exclude_ids = exclude_ids or set()
    ids = []
    slugs = [slug] if slug else [s["slug"] for s in list_sources()]
    for s in slugs:
        for qid, meta in _index(s).items():
            if qtype and meta.get("type") != qtype:
                continue
            if difficulty is not None and meta.get("difficulty") != difficulty:
                continue
            if difficulty_level is not None:
                lv = meta.get("difficulty_level")
                if lv is None:
                    lv = levels.level_for_score(meta.get("difficulty_score", 0.0))
                if lv != difficulty_level:
                    continue
            if category is not None and meta.get("category") != category:
                continue
            if qid in exclude_ids:
                continue
            ids.append(qid)
    return ids


def stats(slug: str = None) -> dict:
    """外部题库统计（可按来源）。"""
    result = {"total": 0, "by_source": {}, "by_type": {}, "by_level": {},
              "by_category": {}}
    for s in list_sources():
        if slug and s["slug"] != slug:
            continue
        result["total"] += s["total"]
        result["by_source"][s["name"]] = result["by_source"].get(s["name"], 0) \
            + s["total"]
        for meta in _index(s["slug"]).values():
            result["by_type"][meta["type"]] = result["by_type"].get(meta["type"], 0) + 1
            lv = meta.get("difficulty_level")
            if lv is None:
                lv = levels.level_for_score(meta.get("difficulty_score", 0.0))
            result["by_level"][lv] = result["by_level"].get(lv, 0) + 1
            cat = meta.get("category") or "deduction"
            result["by_category"][cat] = result["by_category"].get(cat, 0) + 1
    return result


def clear(slug: str = None) -> None:
    """清空外部题库（测试用）。"""
    ensure_dirs()
    if slug:
        for p in source_dir(slug).glob("*.json"):
            p.unlink()
        _save_index(slug, {})
        return
    for slug_dir in EXTERNAL_DIR.iterdir():
        if slug_dir.is_dir():
            for p in slug_dir.glob("*.json"):
                p.unlink()
