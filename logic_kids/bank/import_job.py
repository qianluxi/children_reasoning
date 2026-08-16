"""批量导入平台（PR 1：ImportConfig / dry-run / 批处理统计 / retry / checkpoint）。

用法（专家意见第十二、十三、十四节）：
    python cli.py import-all config/datasets.yaml
    python cli.py import-all config/datasets.yaml --dry-run
    python cli.py import-all config/datasets.yaml --retry --checkpoint
    python cli.py import stats
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import yaml

from ..config import DATA_DIR, ensure_dirs
from . import external, importer, provenance, store

_LEDGER_PATH = DATA_DIR / "import_stats.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_ledger() -> dict:
    ensure_dirs()
    if not _LEDGER_PATH.exists():
        return {}
    try:
        return json.loads(_LEDGER_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_ledger(ledger: dict) -> None:
    ensure_dirs()
    tmp = _LEDGER_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    import os
    os.replace(tmp, _LEDGER_PATH)


def record_source(name: str, report: dict = None, error: str = None) -> None:
    """把一次导入结果累计进账本（RAW/VALID/REJECT/…）。"""
    ledger = load_ledger()
    row = ledger.get(name, {"raw": 0, "valid": 0, "reject": 0,
                            "duplicates": 0, "pending": 0, "approved": 0,
                            "last_run": "", "last_error": None})
    if report is not None:
        row["raw"] += report["total"]
        row["reject"] += report["failed_schema"] + report["failed_logic"]
        row["duplicates"] += report["duplicates"]
        row["valid"] += max(report["translated"] - report["failed_schema"]
                            - report["failed_logic"] - report["duplicates"]
                            - report["checkpoint_skipped"], 0)
        row["pending"] += report["pending"]
        row["approved"] += report["approved"]
        row["last_run"] = _now()
        row["last_error"] = None
    if error is not None:
        row["last_error"] = str(error)[:300]
    ledger[name] = row
    save_ledger(ledger)


def stats_table() -> list:
    """返回 [(SOURCE, RAW, VALID, REJECT, REVIEW, READY)]。"""
    ledger = load_ledger()
    st = store.stats()
    rows = [("builtin", st["total"], st["total"], 0, 0, st["total"])]

    # 实时 REVIEW（待审队列 pending 数）与 READY（外部库题数）按来源名归并
    review_by_src = {}
    for p in provenance.list_pending():
        if p["review_status"] == "pending":
            review_by_src[p["source"]] = review_by_src.get(p["source"], 0) + 1
    ready_by_name = {s["name"]: s["total"] for s in external.list_sources()}

    for name in sorted(ledger):
        row = ledger[name]
        display = row.get("display", name)
        rows.append((
            display,
            row["raw"], row["valid"], row["reject"],
            review_by_src.get(display, 0),
            ready_by_name.get(display, row["approved"]),
        ))
    # 已有外部库数据但还没跑过新账本的来源，也展示出来
    for s in external.list_sources():
        if s["name"] not in ledger and s["name"] not in {r[0] for r in rows}:
            rows.append((s["name"], "-", "-", "-",
                         review_by_src.get(s["name"], 0), s["total"]))
    return rows


def load_config(config_path) -> list:
    """读取 datasets.yaml，返回启用来源的计划列表。"""
    path = Path(config_path)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    plans = []
    for name, cfg in (data.get("sources") or {}).items():
        if not cfg.get("enabled", True):
            continue
        plans.append({"name": name, **cfg})
    return plans


def run_job(config_path: str, dry_run: bool = False, retry: bool = False,
            checkpoint: bool = False, dedup_enabled: bool = True,
            dedup_logic: bool = False) -> dict:
    """按配置批量导入；某个来源失败不阻断其它来源。"""
    plans = load_config(config_path)
    summary = []
    for plan in plans:
        name = plan["name"]
        ledger = load_ledger()
        if retry and not ledger.get(name, {}).get("last_error"):
            print(f"[skip] {name}：上次导入成功，--retry 模式下跳过")
            continue
        tasks = plan.get("tasks") or ([plan["task"]] if plan.get("task") else [None])
        try:
            agg = {"total": 0, "translated": 0, "skipped": 0,
                   "failed_schema": 0, "failed_logic": 0, "pending": 0,
                   "approved": 0, "approve_failed": 0, "duplicates": 0,
                   "checkpoint_skipped": 0, "valid": 0}
            for task in tasks:
                rep = importer.import_source(
                    name, limit=plan.get("limit"),
                    approve=bool(plan.get("approve", False)), task=task,
                    lang=plan.get("lang"), dry_run=dry_run,
                    checkpoint=checkpoint, dedup_enabled=dedup_enabled,
                    dedup_logic=dedup_logic, seed=plan.get("seed"))
                for k in agg:
                    agg[k] += rep.get(k, 0)
                print(f"[{name}] task={task} "
                      f"raw={rep['total']} valid={rep['valid']} "
                      f"reject={rep['failed_schema'] + rep['failed_logic']} "
                      f"dup={rep['duplicates']} review={rep['pending']} "
                      f"ready={rep['approved']}")
            record_source(name, agg, error=None)
            summary.append((name, "ok"))
        except Exception as e:
            record_source(name, None, error=str(e))
            print(f"[error] {name}：{e}")
            summary.append((name, "error"))
    return {"summary": summary}
