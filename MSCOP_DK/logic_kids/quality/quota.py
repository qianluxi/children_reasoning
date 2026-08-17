"""题库配额系统（专家意见第十四节：balance-bank）。

按 production_quota 计算各能力"目标 vs 当前"，并给出下一批应该
生成/导入什么的建议。
"""
from __future__ import annotations

import yaml

from ..config import BASE_DIR

_QUOTA_PATH = BASE_DIR / "config" / "quota.yaml"


def load_quota() -> dict:
    if not _QUOTA_PATH.exists():
        return {}
    with open(_QUOTA_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def balance(analysis: dict) -> dict:
    """输入 analyze() 结果，输出能力配额表 + 建议。"""
    quota = load_quota().get("production_quota") or {}
    total = analysis["total_active"]
    if total <= 0:
        return {"rows": [], "suggestions": ["⚠ 题库为空"]}
    rows = []
    for ability, target in sorted(quota.items()):
        cur = analysis["by_ability"].get(ability, 0) / total * 100
        diff = cur - target
        status = "✓" if abs(diff) <= 2 else ("⚠" if diff > 0 else "▲")
        rows.append({
            "ability": ability,
            "target": target,
            "current": round(cur, 1),
            "diff": round(diff, 1),
            "status": status,
        })
    suggestions = _suggestions(analysis, quota, rows)
    return {"rows": rows, "suggestions": suggestions}


def _suggestions(analysis, quota, rows) -> list:
    sugg = []
    total = analysis["total_active"]
    for r in rows:
        if r["diff"] <= -2:
            sugg.append(f"增加 {r['ability']} 数据源/生成（当前 "
                        f"{r['current']}%，目标 {r['target']}%）")
        elif r["diff"] >= 2:
            sugg.append(f"暂停导入 {r['ability']}（当前 {r['current']}%，"
                        f"超出目标 {r['target']}%）")
    cfg = load_quota()
    if total and analysis["by_level"].get(4, 0) / total * 100 < cfg.get(
            "min_level4_ratio", 5):
        sugg.append("补充 Level 4（挑战级）题目")
    if total and analysis["by_age"].get("A", 0) / total * 100 < cfg.get(
            "min_age_a_ratio", 10):
        sugg.append("补充低龄（A 级 5-7 岁）题目")
    if analysis.get("machine_only", 0):
        sugg.append(f"将 {analysis['machine_only']} 道仅机器翻译题提交儿童人工审核")
    if analysis.get("no_proof", 0):
        sugg.append(f"为 {analysis['no_proof']} 道无真实 proof 的题补验证"
                    "（Solver/生成器）")
    if analysis.get("structure_duplicates", 0):
        sugg.append(f"对逻辑结构重复的 {analysis['structure_duplicates']} 道题"
                    "运行去重/控制比例")
    return sugg
