"""外部题库导入管线（专家意见第十一节：四道闸门，第十二节：难度由自家引擎决定）。

流程：
    下载 → ① Schema Validation → ② Logic Validation → ③ Unique Solution
          → ④ Difficulty Calibration → 待审队列（data/imports/）→ 审核 → 正式题库

原则：
    · 外部题默认只进"待审队列"，绝不直接进正式题库；
    · 只有能转成 DSL 并通过 Solver/Validator（唯一解）的题才能被审核入库；
    · 难度一律由本项目的 Difficulty Engine 重新校准，不信外部数据集自己的难度标签。
"""
from __future__ import annotations

import re

from ..config import ensure_dirs
from ..difficulty import engine as difficulty_engine, levels
from .. import child_suitability, dedup
from ..validator.validator import validate
from . import external, provenance, sources
from .normalizer import NormalizedQuestion

_QID_CLEAN = re.compile(r"[^A-Za-z0-9_-]+")


def make_qid(source_name: str, dataset_id: str, original_id) -> str:
    """外部题 id：ext_<源>_<数据集>_<原始id>，只保留安全字符。"""
    raw = f"ext_{source_name}_{dataset_id}_{original_id}"
    return _QID_CLEAN.sub("_", raw).strip("_")


def schema_validate(n: NormalizedQuestion) -> list:
    """闸门①：结构检查（题干/选项/答案/ID/来源与许可证）。"""
    issues = []
    if not n.source or not n.source.name or not n.source.license:
        issues.append("source/license 缺失")
    if not n.source.original_id:
        issues.append("original_id 缺失")
    if not n.category:
        issues.append("能力分类(category)缺失")
    if not n.question_prompt and not n.story_text:
        issues.append("题干与问题都缺失")
    if len(n.options) < 2:
        issues.append("选项少于 2 个")
    if len(set(n.options)) != len(n.options):
        issues.append("存在重复选项")
    if not (0 <= n.answer < len(n.options)):
        issues.append("answer 越界")
    return issues


def logic_validate(q) -> tuple:
    """闸门②③：逻辑验证 + 唯一解。

    能转 DSL 的走 Solver/Validator 全套；不能转的（如 LogiQA 自然语言题）
    返回 (True, []) 但 logic_validated=False，只能停留在待审队列。
    """
    has_dsl = any(c.logic for c in q.constraints) or any(q.option_logic)
    if not has_dsl:
        return True, []
    report = validate(q)
    return report.ok, report.issues


def calibrate_difficulty(q) -> bool:
    """闸门④：难度校准（专家意见第十二节：难度必须由自家引擎决定）。"""
    has_dsl = any(c.logic for c in q.constraints) or any(q.option_logic)
    if has_dsl:
        difficulty_engine.apply(q)
        q.provenance.difficulty_calibrated = True
        return True
    # 适配器自带难度等级（如 Reasoning Gym 的元数据启发）：保留并映射分数
    if q.difficulty_level in (1, 2, 3, 4):
        mid = {1: 1.2, 2: 3.7, 3: 6.2, 4: 8.7}[q.difficulty_level]
        q.difficulty_score = mid
        q.difficulty = difficulty_engine.stars(mid)
        q.difficulty_profile = difficulty_engine.difficulty_profile(q)
        q.age_range = difficulty_engine.age_for(q)
        q.child_suitability = child_suitability.evaluate(q)
        q.provenance.difficulty_calibrated = False
        return False
    # 无 DSL：结构启发式兜底，明确标记"未校准"，等待人工改写后重算
    n = max(len(q.entities), len(q.options), 1)
    score = round(min(10.0, max(0.5, 1.2 + 0.35 * n + 0.15 * len(q.constraints))), 2)
    q.difficulty_score = score
    q.difficulty_level = levels.level_for_score(score)
    q.difficulty = difficulty_engine.stars(score)
    q.difficulty_profile = difficulty_engine.difficulty_profile(q)
    q.age_range = difficulty_engine.age_for(q)
    q.child_suitability = child_suitability.evaluate(q)
    q.provenance.difficulty_calibrated = False
    return False


def grade_quality(q) -> str:
    """质量分级（专家意见第十八节）：A/B/C/rejected。

    A：Solver 验证 + 儿童语言已审核（child_adapted）或内置中文原创
    B：逻辑正确但儿童语言未人工审核（机器翻译）
    C：只有外部答案、无法形式化验证（人工抽检后可用）
    """
    if not (q.source_info and q.source_info.type == "external"):
        return "A"
    tr = (q.translations or {}).get("zh_child") \
        or (q.translations or {}).get("zh") or {}
    child_adapted = tr.get("status") == "child_adapted"
    if not q.provenance.logic_validated:
        return "B" if child_adapted else "C"
    return "A" if child_adapted else "B"


def import_items(source_name: str, raw_items: list, normalize,
                 limit: int = None, approve: bool = False,
                 translate=None, dry_run: bool = False,
                 checkpoint: bool = False, dedup_enabled: bool = True,
                 dedup_logic: bool = False, translate_child=None) -> dict:
    """把一批原始题跑完四道闸门，写入待审队列（可选直接审核入库）。"""
    ensure_dirs()
    report = {"total": 0, "translated": 0, "skipped": 0,
              "failed_schema": 0, "failed_logic": 0,
              "pending": 0, "approved": 0, "approve_failed": 0,
              "duplicates": 0, "checkpoint_skipped": 0, "valid": 0}
    seen_qids = set()
    existing = set()
    if checkpoint:
        existing = set(external.list_ids())
        existing |= {p["qid"] for p in provenance.list_pending()}
    items = raw_items[:limit] if limit is not None else raw_items
    for item in items:
        report["total"] += 1
        n = normalize(item)
        if n is None:
            report["skipped"] += 1
            continue
        report["translated"] += 1
        issues = schema_validate(n)
        qid = make_qid(source_name, n.source.dataset_id, n.source.original_id)
        if qid in seen_qids:
            report["failed_schema"] += 1
            continue
        seen_qids.add(qid)
        if checkpoint and qid in existing:
            report["checkpoint_skipped"] += 1
            continue
        if issues:
            report["failed_schema"] += 1
            continue
        q = n.to_question(qid)
        # 可选：生成中文版文本（如 BIG-bench 规则翻译器）
        if translate is not None:
            try:
                q.translations = {"zh": translate(q)}
            except Exception:
                q.translations = None
        if translate_child is not None and q.translations:
            try:
                q.translations["zh_child"] = translate_child(q)
            except Exception:
                pass
        ok, logic_issues = logic_validate(q)
        if not ok:
            report["failed_logic"] += 1
            continue
        q.provenance.logic_validated = any(c.logic for c in q.constraints) \
            or any(q.option_logic)
        calibrate_difficulty(q)
        q.quality = grade_quality(q)
        if dedup_enabled:
            dup = dedup.check(q)
            if dup["text_dup"] or (dedup_logic and dup["logic_dup"]):
                report["duplicates"] += 1
                continue
        report["valid"] += 1
        if dry_run:
            continue
        q.provenance.review_status = provenance.REVIEW_PENDING
        provenance.save_pending(q)
        if dedup_enabled:
            dedup.register(q)
        report["pending"] += 1
        if approve:
            ok_approve, _ = approve_pending(qid)
            if ok_approve:
                report["approved"] += 1
            else:
                report["approve_failed"] += 1
    return report


def import_source(source_name: str, limit: int = None, approve: bool = False,
                  task: str = None, lang: str = None, dry_run: bool = False,
                  checkpoint: bool = False, dedup_enabled: bool = True,
                  dedup_logic: bool = False, seed: int = None) -> dict:
    """下载指定外部源并导入（CLI/Web 统一入口）。"""
    adapter = sources.get(source_name)
    kw = {"task": task}
    if lang is not None:
        kw["lang"] = lang
    if seed is not None:
        kw["seed"] = seed
    items = adapter.fetch(**kw)
    translate = getattr(adapter, "zh_translate_question", None)
    translate_child = getattr(adapter, "zh_child_question", None)
    return import_items(source_name, items, adapter.normalize,
                        limit=limit, approve=approve, translate=translate,
                        translate_child=translate_child,
                        dry_run=dry_run, checkpoint=checkpoint,
                        dedup_enabled=dedup_enabled, dedup_logic=dedup_logic)


def approve_pending(qid: str, force: bool = False) -> tuple:
    """审核通过：复验四道闸门后移入外部题库。

    未通过逻辑验证（无 DSL）的题默认禁止入库（专家意见：Solver 是裁判）；
    成熟人工数据集经人工抽检后，可用 force=True 显式放行（保留未验证标记）。
    """
    q = provenance.load_pending(qid)
    if q is None:
        return False, f"待审队列中没有 {qid}"
    if not q.provenance.logic_validated:
        if not force:
            return False, (f"{qid} 未通过逻辑验证（无 DSL）；"
                           f"人工抽检认可后可加 --force 入库")
    else:
        report = validate(q)
        if not report.ok:
            return False, f"{qid} 复验失败：{'；'.join(report.issues)}"
    q.provenance.review_status = provenance.REVIEW_APPROVED
    external.save_question(q)
    provenance.save_pending(q)
    name = q.source_info.name if q.source_info else "external"
    return True, f"{qid} 已通过审核并移入外部题库（{name}）"


def approve_all_pending(force: bool = False) -> tuple:
    """把待审队列里所有 pending 的题批量审核（人工抽检后的批量放行）。"""
    ok_n = fail_n = 0
    failures = []
    for it in provenance.list_pending():
        if it["review_status"] != provenance.REVIEW_PENDING:
            continue
        okq, msg = approve_pending(it["qid"], force=force)
        if okq:
            ok_n += 1
        else:
            fail_n += 1
            failures.append(msg)
    return ok_n, fail_n, failures


def reject_pending(qid: str) -> tuple:
    q = provenance.load_pending(qid)
    if q is None:
        return False, f"待审队列中没有 {qid}"
    q.provenance.review_status = provenance.REVIEW_REJECTED
    provenance.save_pending(q)
    return True, f"{qid} 已标记为 rejected"
