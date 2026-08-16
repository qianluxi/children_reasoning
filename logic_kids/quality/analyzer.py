"""题库质量分析器（专家意见第十四节）。

输出题库的能力/难度/层级/许可证分布，并给出能力空缺警告——
"下一步应该引入什么数据集"由数据说话，而不是凭感觉。

三层题库（专家意见第二节）映射：
    production    A 级（已验证 + 儿童语言审核）→ 儿童正常训练
    experimental  B 级（逻辑正确但机器翻译）→ 开发者测试
    raw           C 级 / 待审队列 → 永远不直接给儿童
"""
from __future__ import annotations

from .. import taxonomy
from ..bank import external, provenance, store

TIER_NAMES = {
    "production": "production（A 级，儿童可用）",
    "experimental": "experimental（B 级，实验）",
    "raw": "raw（C 级/待审，原始）",
}


def _tier_of(quality: str, review_pending: bool = False) -> str:
    if review_pending:
        return "raw"
    return {"A": "production", "B": "experimental"}.get(quality, "raw")


def analyze() -> dict:
    """扫描内置 + 外部 + 待审队列，返回完整画像。"""
    abilities = {}
    levels = {}
    tiers = {"production": 0, "experimental": 0, "raw": 0}
    licenses = {"production": 0, "noncommercial": 0, "unknown": 0}
    sources = {}
    total = 0

    def _add(meta, tier, source, license_name):
        nonlocal total
        total += 1
        cat = meta.get("category") or "deduction"
        abilities[cat] = abilities.get(cat, 0) + 1
        lv = meta.get("difficulty_level")
        if lv is None:
            from ..difficulty import levels as lvmod
            lv = lvmod.level_for_score(meta.get("difficulty_score", 0.0))
        levels[lv] = levels.get(lv, 0) + 1
        tiers[tier] = tiers.get(tier, 0) + 1
        sources[source] = sources.get(source, 0) + 1
        from ..license_policy import classify
        key = classify(license_name)
        licenses[key] = licenses.get(key, 0) + 1

    # 内置题库
    for qid, meta in store._index().items():
        _add(meta, "production", "builtin", "MIT")
    # 外部题库（按来源）
    for s in external.list_sources():
        for qid, meta in external._index(s["slug"]).items():
            _add(meta, _tier_of(meta.get("quality", "C"), False),
                 s["name"], meta.get("license", ""))
    # 待审队列（raw）
    for p in provenance.list_pending():
        if p["review_status"] != "pending":
            continue
        _add({"category": p.get("category", "deduction"),
              "difficulty_level": 2,
              "quality": p.get("quality", "C")},
             "raw", p["source"], p.get("license", ""))

    warnings = _warnings(total, abilities, levels, tiers, licenses)
    return {
        "total": total,
        "by_ability": abilities,
        "by_level": levels,
        "by_tier": tiers,
        "by_license": licenses,
        "by_source": sources,
        "warnings": warnings,
    }


def _warnings(total, abilities, levels, tiers, licenses) -> list:
    warns = []
    if total == 0:
        return ["⚠ 题库为空"]
    # 能力覆盖：低于 3%（且不足 5 道）的能力视为空缺
    for ability in taxonomy.ABILITIES:
        n = abilities.get(ability, 0)
        if n < max(5, int(total * 0.03)):
            warns.append(f"⚠ {taxonomy.ability_label(ability)}题不足（仅 {n} 道）")
    # 占比失衡
    ded = abilities.get("deduction", 0)
    if total and ded / total > 0.55:
        warns.append(f"⚠ 演绎逻辑占比过高（{ded * 100 // total}%）")
    # 高难度
    hard = levels.get(4, 0)
    if total and hard / total < 0.05:
        warns.append(f"⚠ 高难度（挑战级）题不足（仅 {hard} 道）")
    # 层级健康度
    raw = tiers.get("raw", 0)
    if total and raw / total > 0.4:
        warns.append(f"⚠ 待审/原始题占比过高（{raw * 100 // total}%）")
    # 许可证
    if licenses.get("unknown", 0):
        warns.append(f"⚠ 存在未知许可证题 {licenses['unknown']} 道，需人工确认")
    return warns


def report_text() -> str:
    """生成给 CLI 的可读报告。"""
    r = analyze()
    lines = [f"题库总数：{r['total']}"]
    lines.append("")
    lines.append("按能力：")
    for ability in sorted(r["by_ability"], key=lambda a: -r["by_ability"][a]):
        n = r["by_ability"][ability]
        lines.append(f"  {taxonomy.ability_label(ability):12s} {n}")
    lines.append("")
    lines.append("按难度等级：")
    from ..difficulty import levels as lvmod
    for lv in sorted(r["by_level"]):
        lines.append(f"  {lvmod.label(lv):12s} {r['by_level'][lv]}")
    lines.append("")
    lines.append("按层级：")
    for tier in ("production", "experimental", "raw"):
        lines.append(f"  {TIER_NAMES[tier]:32s} {r['by_tier'][tier]}")
    lines.append("")
    lines.append("按许可证：")
    lines.append(f"  Production-safe : {r['by_license']['production']}")
    lines.append(f"  Non-commercial  : {r['by_license']['noncommercial']}")
    lines.append(f"  Unknown         : {r['by_license']['unknown']}")
    lines.append("")
    lines.append("问题：")
    if r["warnings"]:
        for w in r["warnings"]:
            lines.append("  " + w)
    else:
        lines.append("  （无，能力分布健康）")
    return "\n".join(lines)
