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
    """扫描内置 + 外部 + 待审队列，返回完整画像（含诊断）。"""
    abilities = {}
    levels = {}
    ages = {}
    archetypes = {}
    qualities = {}
    tiers = {"production": 0, "experimental": 0, "raw": 0}
    licenses = {"production": 0, "noncommercial": 0, "unknown": 0}
    sources = {}
    total = 0
    total_active = 0
    machine_only = 0
    no_proof = 0

    def _add(meta, tier, source, license_name, verified_by="",
             child_adapted=False, has_translation=False):
        nonlocal total
        nonlocal total_active
        nonlocal machine_only
        nonlocal no_proof
        total += 1
        if tier != "raw":
            total_active += 1
        cat = meta.get("category") or "deduction"
        abilities[cat] = abilities.get(cat, 0) + 1
        lv = meta.get("difficulty_level")
        if lv is None:
            from ..difficulty import levels as lvmod
            lv = lvmod.level_for_score(meta.get("difficulty_score", 0.0))
        levels[lv] = levels.get(lv, 0) + 1
        age = meta.get("age_range") or "B"
        ages[age] = ages.get(age, 0) + 1
        arch = meta.get("archetype") or "generic"
        archetypes[arch] = archetypes.get(arch, 0) + 1
        q = meta.get("quality") or "C"
        qualities[q] = qualities.get(q, 0) + 1
        tiers[tier] = tiers.get(tier, 0) + 1
        sources[source] = sources.get(source, 0) + 1
        if tier != "raw" and has_translation and not child_adapted:
            machine_only += 1
        if tier != "raw" and not verified_by:
            no_proof += 1
        from ..license_policy import classify
        key = classify(license_name)
        licenses[key] = licenses.get(key, 0) + 1

    # 内置题库
    for qid, meta in store._index().items():
        _add(meta, "production", "builtin", "MIT",
             verified_by=meta.get("verified_by", ""),
             child_adapted=meta.get("child_adapted", False),
             has_translation=meta.get("has_translation", False))
    # 外部题库（按来源）
    for s in external.list_sources():
        for qid, meta in external._index(s["slug"]).items():
            _add(meta, _tier_of(meta.get("quality", "C"), False),
                 s["name"], meta.get("license", ""),
                 verified_by=meta.get("verified_by", ""),
                 child_adapted=meta.get("child_adapted", False),
                 has_translation=meta.get("has_translation", False))
    # 待审队列（raw）
    for p in provenance.list_pending():
        if p["review_status"] != "pending":
            continue
        _add({"category": p.get("category", "deduction"),
              "difficulty_level": 2,
              "age_range": "B", "archetype": "generic",
              "quality": p.get("quality", "C")},
             "raw", p["source"], p.get("license", ""),
             verified_by="dataset")

    structure_dups = _structure_duplicates()
    warnings = _warnings(total, total_active, abilities, levels, tiers,
                         licenses, machine_only, no_proof, structure_dups)
    return {
        "total": total,
        "total_active": total_active,
        "by_ability": abilities,
        "by_level": levels,
        "by_age": ages,
        "by_archetype": archetypes,
        "by_quality": qualities,
        "by_tier": tiers,
        "by_license": licenses,
        "by_source": sources,
        "machine_only": machine_only,
        "no_proof": no_proof,
        "structure_duplicates": structure_dups,
        "warnings": warnings,
    }


def _structure_duplicates() -> int:
    """统计逻辑结构重复（同一 DSL 签名出现多次）的外部题数量。"""
    from ..bank import external
    from ..dedup import logic_signature
    sigs = {}
    dup = 0
    for s in external.list_sources():
        for qid in external.list_ids(s["slug"]):
            q = external.load_question(s["slug"], qid)
            if q is None:
                continue
            sig = logic_signature(q)
            if sig:
                sigs[sig] = sigs.get(sig, 0) + 1
    for n in sigs.values():
        dup += max(n - 1, 0)
    return dup


def _warnings(total, total_active, abilities, levels, tiers, licenses,
              machine_only, no_proof, structure_dups) -> list:
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
    elif total_active and ded / total_active > 0.35:
        warns.append(f"⚠ 演绎逻辑占活跃题库 {ded * 100 // total_active}%，偏高")
    # 高难度
    hard = levels.get(4, 0)
    if total and hard / total < 0.05:
        warns.append(f"⚠ 高难度（挑战级）题不足（仅 {hard} 道）")
    # 低龄
    if total and levels and levels.get(1, 0) / total < 0.1:
        warns.append("⚠ 低龄（简单级）题目不足")
    # 层级健康度
    raw = tiers.get("raw", 0)
    if total and raw / total > 0.4:
        warns.append(f"⚠ 待审/原始题占比过高（{raw * 100 // total}%）")
    # 许可证
    if licenses.get("unknown", 0):
        warns.append(f"⚠ 存在未知许可证题 {licenses['unknown']} 道，需人工确认")
    if machine_only:
        warns.append(f"⚠ {machine_only} 道题仅有机器翻译，未经儿童化改写")
    if no_proof:
        warns.append(f"⚠ {no_proof} 道题没有真实 proof（未验证）")
    if structure_dups:
        warns.append(f"⚠ {structure_dups} 道题逻辑结构重复（可运行去重/控制比例）")
    return warns


def report_text() -> str:
    """生成给 CLI 的可读报告。"""
    r = analyze()
    lines = [f"题库总数：{r['total']}"]
    lines.append("")
    lines.append("质量：")
    for q in ("A", "B", "C", "rejected"):
        lines.append(f"  {q:8s} {r['by_quality'].get(q, 0)}")
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
    lines.append("按年龄：")
    for age in sorted(r["by_age"]):
        lines.append(f"  {age}（{taxonomy.age_label(age)}）   "
                     f"{r['by_age'][age]}")
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
    lines.append("")
    lines.append("建议：")
    from .quota import balance
    sugg = balance(r)["suggestions"]
    if sugg:
        for s in sugg:
            lines.append("  " + s)
    else:
        lines.append("  （分布健康，无需调整）")
    return "\n".join(lines)
