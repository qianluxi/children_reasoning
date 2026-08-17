#!/usr/bin/env python3
"""重新平衡题库脚本。

目标：每个能力类别约 50-80 题（总数 ~700-800）
执行方式：python scripts/rebalance_bank.py

流程：
  Phase 1: 内部生成 — matching（扩展 relation 类）
  Phase 2: Reasoning Gym 批量导入（直接调用 library，非 subprocess）
  Phase 3: BigBench ordering 裁剪（125→~75）
  Phase 4: 统一 zh_child 翻译 + 审核入库
  Phase 5: 最终统计展示
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from logic_kids.questions.generator import generate_batch
from logic_kids.bank import store, external, provenance
from logic_kids.bank.sources import reasoning_gym as rg_source


def phase1_generate_matching():
    """扩展 matching 题型以充实 relation 类别。"""
    print("=" * 60)
    print("Phase 1: 内部生成 — matching (关系推理)")
    print("=" * 60)

    import glob
    current_matching = len(glob.glob(str(PROJECT_ROOT / "data/questions" / "match_*.json")))
    target_matching = 80
    needed = max(0, target_matching - current_matching)

    if needed <= 0:
        print(f"  matching 已有 {current_matching} >= {target_matching}，跳过。")
        return []

    print(f"  需要生成 {needed} 道 matching 题（当前 {current_matching}，目标 {target_matching}）")
    
    # Use matching-only generation with fresh seed
    batch = generate_batch(count=needed, seed=20250901, types=["matching"])
    saved = store.save_many(batch)
    
    print(f"  ✓ 生成了 {len(batch)} 道，成功入库 {saved} 道")
    return [q.id for q in batch]


def _import_rg_task_direct(task_name: str, limit: int, seed: int):
    """直接调用 reasoning_gym adapter 导入单个 task。"""
    from logic_kids.bank import importer
    
    print(f"\n  ── 导入 reasoning_gym/{task_name} (limit={limit}, seed={seed}) ...")
    
    report = importer.import_source(
        source_name="reasoning_gym",
        limit=limit,
        task=task_name,
        seed=seed,
        approve=True,       # auto-approve after passing pipeline
        checkpoint=False,   # don't skip anything
        dedup_enabled=True,
        dry_run=False,
    )
    
    total = report["total"]
    translated = report["translated"]
    pending = report["pending"]
    approved = report.get("approved", 0)
    
    print(f"    total={total}, valid={report['valid']}, pending={pending}, approved={approved}")
    if report.get("skipped"):
        print(f"    skipped={report['skipped']}")
    if report.get("duplicates"):
        print(f"    duplicates={report['duplicates']}")
    
    return report


def phase2_import_reasoning_gym():
    """批量导入 Reasoning Gym 各 task。"""
    print("\n" + "=" * 60)
    print("Phase 2: Reasoning Gym 批量导入")
    print("=" * 60)

    tasks = [
        ("family_relationships", 40, 100),     # relation (multi-hop)
        ("knights_knaves", 25, 200),           # deduction (已有~100，少补)
        ("syllogism", 25, 300),                # deduction
        ("leg_counting", 50, 400),             # math (从零起步)
        ("letter_counting", 30, 500),          # math
        ("rectangle_count", 30, 600),          # math  
        ("chain_sum", 30, 700),               # math
        ("time_intervals", 20, 800),          # math
        ("arc_1d", 50, 900),                  # pattern (替代颜色规律)
        ("maze", 30, 1000),                   # spatial (从零起步)
    ]

    failed_tasks = []
    for task_name, limit, seed in tasks:
        try:
            _import_rg_task_direct(task_name, limit, seed)
        except Exception as e:
            print(f"  ✘ Error importing {task_name}: {e}")
            failed_tasks.append(task_name)

    if failed_tasks:
        print(f"\n  ⚠️ 以下 task 导入失败: {', '.join(failed_tasks)}")
        print("  可手动重试:")
        for name in failed_tasks:
            print(f'    python cli.py import reasoning_gym --task {name} --limit 50 --seed <N> --approve')

    return failed_tasks


def phase3_prune_ordering():
    """BigBench ordering 裁剪：从 ~125 降到 ~75。"""
    print("\n" + "=" * 60)
    print("Phase 3: BigBench ordering 裁剪 (125 → 75)")
    print("=" * 60)

    slug = "bigbench"
    source_path = external.source_dir(slug)
    idx_path = source_path / "index.json"

    if not idx_path.exists():
        print("  index.json 不存在，跳过裁剪。")
        return 0

    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    total = len(idx)
    target = 75
    to_remove = total - target

    if to_remove <= 0:
        print(f"  已有 {total} <= {target}，无需裁剪。")
        return total

    # Sort by qid to deterministically remove first ones (oldest)
    sorted_ids = sorted(idx.keys())
    to_delete = set(sorted_ids[:to_remove])

    deleted_count = 0
    for qid in to_delete:
        fpath = source_path / f"{qid}.json"
        if fpath.exists():
            fpath.unlink()
            deleted_count += 1

    # Rebuild index (keep only surviving entries)
    new_idx = {k: v for k, v in idx.items() if k not in to_delete}
    external._save_index(slug, new_idx)

    print(f"  删除 {deleted_count}/{to_remove} 道题（索引重建为 {len(new_idx)} 条）")
    return len(new_idx)


def phase4_translate_and_approve():
    """为新导入的外部题生成 zh_child 翻译并审核入库。"""
    print("\n" + "=" * 60)
    print("Phase 4: zh_child 翻译 + 审核入库")
    print("=" * 60)

    from logic_kids.bank.sources import SOURCES

    slug = "reasoninggym"
    source_path = external.source_dir(slug)

    if not source_path.exists():
        print(f"  [{slug}] 目录不存在，跳过。")
        return

    # Load all questions from this source
    qids = external.list_ids(slug)
    print(f"  [{slug}] 共有 {len(qids)} 道题待处理")

    # Check which already have zh_child
    need_zh_child = []
    for qid in qids:
        q = external.load_question(slug, qid)
        if q and (q.translations or {}).get("zh_child"):
            continue
        need_zh_child.append((qid, q))

    print(f"  需要 zh_child 翻译: {len(need_zh_child)} 题")

    if need_zh_child:
        # Find the RG adapter
        adapter = None
        for key, mod in SOURCES.items():
            if hasattr(mod, "SOURCE_NAME"):
                slug_from_name = external.source_slug(mod.SOURCE_NAME)
                if slug_from_name == slug:
                    adapter = mod
                    break
        
        if adapter and hasattr(adapter, "zh_child_question"):
            updated = 0
            for i, (qid, q) in enumerate(need_zh_child):
                try:
                    child = adapter.zh_child_question(q)
                    q.translations["zh_child"] = child
                    external.save_question(q)
                    updated += 1
                except Exception as e:
                    if (i + 1) % 10 == 0:
                        print(f"    [{i+1}/{len(need_zh_child)}] 翻译中...")
            
            print(f"  {slug}: 已完成 {updated} 题的 zh_child 翻译")
        else:
            print(f"  [skip] 未找到带 zh_child_question 方法的适配器")

    # Approve pending items with force flag (non-DSL items)
    from logic_kids.bank import importer as imp
    
    pending_items = provenance.list_pending("Reasoning_Gym")
    existing_external = set(external.list_ids(slug))
    
    to_approve = [it for it in pending_items 
                  if it["qid"] not in existing_external]
    
    if to_approve:
        print(f"\n  --- 批量审核 {len(to_approve)} 道待审题 (force=True) ---")
        ok_n, fail_n, failures = imp.approve_all_pending(force=True)
        print(f"  ✓ 通过 {ok_n}，失败 {fail_n}")
        for msg in failures[:5]:
            print(f"    ✘ {msg}")
    else:
        print("\n  无待审题目。")

    print("\n  Phase 4 完成。")


def phase5_stats():
    """最终统计展示。"""
    print("\n" + "=" * 60)
    print("【最终统计】")
    print("=" * 60)

    # Internal stats (production only)
    internal_stats = store.stats()
    print(f"\n📦 内部题库 (生产): {internal_stats['total']} 题")
    print("  按能力:")
    cat_map = {
        "deduction": "演绎逻辑",
        "ordering": "排序与约束", 
        "pattern": "模式与规律",
        "relation": "关系推理",
    }
    for cat, n in sorted(internal_stats.get("by_category", {}).items(), key=lambda x: -x[1]):
        label = cat_map.get(cat, cat)
        print(f"    {label}: {n}")
    
    # External stats
    print(f"\n🌐 外部题库:")
    for s in external.list_sources():
        print(f"    {s['name']}: {s['total']} 题 ({s['license']})")
    
    total_ext = sum(s["total"] for s in external.list_sources())
    
    # Total across all tiers (approximate from files on disk)
    import glob
    all_q_files = list(glob.glob(str(PROJECT_ROOT / "data/questions" / "*.json")))
    ext_all_files = 0
    for d in Path("data/external").iterdir():
        if d.is_dir():
            ext_all_files += len(list(d.glob("*.json")))
    
    total_approx = len(all_q_files) + ext_all_files
    
    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"文件总计(含实验/原始): ~{total_approx} 题")
    print(f"  内部文件: ~{len(all_q_files)}")
    print(f"  外部文件: ~{ext_all_files}")
    print(f"  生产内部: {internal_stats['total']} (已验证)")
    print(f"  生产外部: {sum(s['total'] for s in external.list_sources())} (已审核)")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


def main():
    print("🚀 题库重新平衡脚本 v1.0")
    print(f"项目根目录: {PROJECT_ROOT}\n")
    
    # Phase 1: Internal generation
    phase1_generate_matching()
    
    # Phase 2: External imports
    phase2_import_reasoning_gym()
    
    # Phase 3: Prune ordering
    phase3_prune_ordering()
    
    # Phase 4: zh_child translations + approve
    phase4_translate_and_approve()
    
    # Phase 5: Stats
    phase5_stats()
    
    print("\n✅ 全部完成！请重启 web 服务器使数据生效。")
    print("   python app.py")
    print("   然后运行 python cli.py analyze-bank 查看完整分析。")


if __name__ == "__main__":
    main()
