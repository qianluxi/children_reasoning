"""许可证策略（专家意见第十九节）。

license 不只是记录，还要参与选题：production 允许、noncommercial 仅研究、
unknown 需要人工确认。`bank check-license` 输出三种分类的统计。
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .config import BASE_DIR

_POLICY_PATH = BASE_DIR / "config" / "license_policy.yaml"


def _policy() -> dict:
    if not _POLICY_PATH.exists():
        return {"production": ["MIT", "Apache-2.0"], "noncommercial": []}
    with open(_POLICY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def classify(license_name: str) -> str:
    """返回 production / noncommercial / unknown。"""
    if not license_name:
        return "unknown"
    p = _policy()
    if license_name in p.get("production", []):
        return "production"
    if license_name in p.get("noncommercial", []):
        return "noncommercial"
    return "unknown"


def check_bank() -> dict:
    """统计内置 + 外部题库按许可证分类的数量。"""
    from .bank import external, store
    counts = {"production": 0, "noncommercial": 0, "unknown": 0}
    seen = set()
    for meta in store._index().values():
        pass  # 内置库索引不含 license，统一按内置来源处理
    # 内置题全部是 children_reasoning(MIT) —— production
    counts["production"] += store.stats()["total"]
    seen.update(store.list_ids())
    for s in external.list_sources():
        for qid, meta in external._index(s["slug"]).items():
            if qid in seen:
                continue
            seen.add(qid)
            counts[classify(meta.get("license", ""))] += 1
    return counts
