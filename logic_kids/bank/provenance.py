"""题目溯源与外部题审核队列（专家意见第八节、第十一节）。

外部题不能直接进正式题库：先写入 data/imports/<source>/ 审核队列，
审核通过后才由 importer.approve_pending() 移入正式题库。
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from ..config import IMPORTS_DIR, ensure_dirs
from ..models import SourceInfo, Provenance

REVIEW_PENDING = "pending"
REVIEW_APPROVED = "approved"
REVIEW_REJECTED = "rejected"

# 外部题 id 白名单（与 web 的 _QID_RE 一致，防止路径穿越）
_QID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def make_source(name: str, license: str, dataset_id: str = "",
                original_id: str = "", url: str = "",
                source_type: str = "external") -> SourceInfo:
    return SourceInfo(type=source_type, name=name, license=license,
                      dataset_id=dataset_id, original_id=original_id, url=url)


def make_provenance(translator: str = "", modified: bool = False,
                    review_status: str = REVIEW_PENDING) -> Provenance:
    return Provenance(imported_at=now_iso(), modified=modified,
                      translator=translator, review_status=review_status)


def source_dir(source_name: str) -> Path:
    """某个外部源的审核队列目录。"""
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", source_name)
    path = IMPORTS_DIR / safe
    path.mkdir(parents=True, exist_ok=True)
    return path


def pending_path(source_name: str, qid: str) -> Path:
    return source_dir(source_name) / f"{qid}.json"


def save_pending(q) -> None:
    """外部题写入待审队列（review_status=pending），不进正式题库。"""
    ensure_dirs()
    src = q.source_info.name if q.source_info else "external"
    if q.provenance is not None and not q.provenance.review_status:
        q.provenance.review_status = REVIEW_PENDING
    path = pending_path(src, q.id)
    path.write_text(q.to_json(), encoding="utf-8")


def list_pending(source_name: str = None) -> list:
    """列出待审队列（可按来源过滤）。"""
    ensure_dirs()
    if source_name:
        roots = [source_dir(source_name)]
    else:
        roots = [p for p in IMPORTS_DIR.iterdir() if p.is_dir()]
    items = []
    for root in roots:
        for p in sorted(root.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            items.append({
                "qid": data.get("id"),
                "source": data.get("source_info", {}).get("name", root.name),
                "title": data.get("story", {}).get("title", ""),
                "review_status": data.get("provenance", {}).get("review_status", ""),
                "logic_validated": data.get("provenance", {}).get("logic_validated", False),
                "quality": data.get("quality", "C"),
                "category": data.get("category", "deduction"),
                "license": data.get("source_info", {}).get("license", ""),
                "imported_at": data.get("provenance", {}).get("imported_at", ""),
                "path": str(p),
            })
    return items


def load_pending(qid: str) -> "Question | None":
    """按 id 在全部来源的待审队列中查找题目。"""
    ensure_dirs()
    if not _QID_RE.fullmatch(qid):
        return None
    from ..models import Question
    for root in IMPORTS_DIR.iterdir():
        if not root.is_dir():
            continue
        p = root / f"{qid}.json"
        if p.exists():
            return Question.from_json(p.read_text(encoding="utf-8"))
    return None


def mark_review_status(qid: str, status: str) -> bool:
    """更新待审队列中某题的审核状态。"""
    q = load_pending(qid)
    if q is None:
        return False
    q.provenance.review_status = status
    path = pending_path(q.source_info.name, q.id)
    path.write_text(q.to_json(), encoding="utf-8")
    return True
