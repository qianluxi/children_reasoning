"""命令行工具。

用法示例：
    python cli.py seed                 # 载入人工种子题
    python cli.py generate 50          # 生成 50 道题入库
    python cli.py stats                # 题库统计
    python cli.py validate             # 校验题库全部题目
    python cli.py play --child 小明     # 命令行答题演示（自适应出题）
    python cli.py play --child 小明 --level 3   # 固定难度等级 3（困难）
    python cli.py import bigbench --task logical_deduction/three_objects --limit 20
    python cli.py import logiqa --task dev --limit 10
    python cli.py review                # 查看外部题待审队列
    python cli.py review --approve ext_bigbench_logical_deduction_three_objects_0000
    python cli.py external list         # 列出外部题库来源
    python cli.py external stats        # 外部题库统计
    python cli.py external translate    # 给外部题生成中文版（机器翻译）
    python cli.py import-all config/datasets.yaml          # 按配置批量导入
    python cli.py import-all config/datasets.yaml --dry-run
    python cli.py import stats          # 批处理统计
    python cli.py bank check-license    # 许可证合规检查
    python cli.py analyze-bank          # 题库质量分析（能力空缺/难度/层级）
"""
from __future__ import annotations

import argparse
import random
import sys

from logic_kids.bank import store, seed
from logic_kids.difficulty import engine as difficulty_engine
from logic_kids.difficulty import levels as difficulty_levels
from logic_kids.validator.validator import validate
from logic_kids.questions.generator import generate_batch, TYPE_NAMES
from logic_kids.questions.selector import select_question
from logic_kids.progress import store as progress
from logic_kids.engine import adaptive


def cmd_seed(args):
    seeds = seed.validated_seeds()
    for q in seeds:
        difficulty_engine.apply(q)
    store.save_many(seeds)
    print(f"已载入 {len(seeds)} 道种子题（未通过 Validator 的已跳过）。")


def cmd_generate(args):
    batch = generate_batch(args.count, seed=args.seed)
    store.save_many(batch)
    print(f"已生成并入库 {len(batch)} 道题（请求 {args.count} 道）。")
    if len(batch) < args.count:
        # 专家审查 P1：数量不足必须明确报告，不能静默成功
        print(f"[warn] 请求 {args.count} 道，实际生成 {len(batch)} 道，"
              f"不足 {args.count - len(batch)} 道（生成器已尽力尝试）。")
        return 1
    _print_stats()
    return 0


def cmd_stats(args):
    _print_stats()


def _print_stats():
    st = store.stats()
    print(f"\n题库总数: {st['total']}")
    print("按类型:")
    for t, n in sorted(st["by_type"].items()):
        print(f"  {TYPE_NAMES.get(t, t):8s} {n}")
    print("按难度:")
    for d in sorted(st["by_difficulty"]):
        print(f"  {'★'*d:8s} {st['by_difficulty'][d]}")
    print("按用户等级:")
    for lv in sorted(st["by_level"]):
        print(f"  {lv}. {difficulty_levels.name(lv):4s} {st['by_level'][lv]}")
    print("按能力:")
    for cat, n in st["by_category"].items():
        print(f"  {cat:12s} {n}")
    print("按来源:")
    for s, n in st["by_source"].items():
        print(f"  {s:10s} {n}")


def cmd_validate(args):
    ids = store.list_ids()
    ok = bad = 0
    for qid in ids:
        q = store.load_question(qid)
        report = validate(q)
        if report.ok:
            ok += 1
        else:
            bad += 1
            print(f"  ✘ {qid}: {'; '.join(report.issues)}")
    print(f"\n校验完成：通过 {ok}，失败 {bad}（共 {len(ids)}）。")
    return 0 if bad == 0 else 1


def cmd_play(args):
    child_id = progress.get_or_create_child(args.child)
    rng = random.Random(args.seed)
    if args.level is not None:
        difficulty_levels.validate_level(args.level)
    print(f"你好，{args.child}！开始答题（输入 q 退出）。\n")
    for round_no in range(1, args.rounds + 1):
        if args.level is not None:
            pick = select_question(difficulty=args.level, child_id=child_id, rng=rng)
        else:
            pick = adaptive.next_question(child_id, rng)
        if pick is None:
            print("题库里没有可用的题目了，请先运行: python cli.py generate 50")
            break
        q = pick["question"]
        lv = (pick.get("difficulty_level") or q.difficulty_level
              or difficulty_levels.level_for_score(q.difficulty_score))
        level_text = f"{lv}. {difficulty_levels.name(lv)}"
        print(f"— 第 {round_no} 题 [{TYPE_NAMES.get(q.type, q.type)} {level_text}] —")
        print(f"《{q.story.title}》 {q.story.text}")
        for s in q.statements:
            print(f"  {q.story.roles.get(s.speaker, s.speaker)}：{s.text}")
        for c in q.constraints:
            if c.text:
                print(f"  · {c.text}")
        print(f"问：{q.question_prompt}")
        for i, opt in enumerate(q.options):
            print(f"  {i+1}. {opt}")
        try:
            choice = input("你的答案(序号): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if choice.lower() == "q":
            break
        if not choice.isdigit() or not (1 <= int(choice) <= len(q.options)):
            print("输入无效，跳过这题。\n")
            continue
        idx = int(choice) - 1
        correct = idx == q.answer
        progress.record_attempt(child_id, q.id, q.type, correct)
        if correct:
            print("✔ 答对啦！真棒！⭐\n")
        else:
            print(f"✘ 再想想～正确答案是：{q.options[q.answer]}")
            print("解释：")
            print(q.explanation + "\n")
    # 打印能力画像
    prof = progress.profile(child_id, list(TYPE_NAMES))
    print("\n=== 能力画像 ===")
    for t, info in prof.items():
        m = info["mastery"]
        bar = "— " if m is None else f"{int(m*100):3d}% "
        print(f"  {TYPE_NAMES.get(t,t):8s} {bar}({info['attempts']} 题)")
    return 0


def cmd_import(args):
    from logic_kids.bank import importer
    from logic_kids.bank.sources import SOURCE_INFO
    if args.source == "stats":
        from logic_kids.bank.import_job import stats_table
        rows = stats_table()
        print(f"{'SOURCE':14s} {'RAW':>8s} {'VALID':>8s} {'REJECT':>8s} "
              f"{'REVIEW':>8s} {'READY':>8s}")
        print("-" * 62)
        for r in rows:
            print(f"{r[0]:14s} {str(r[1]):>8s} {str(r[2]):>8s} "
                  f"{str(r[3]):>8s} {str(r[4]):>8s} {str(r[5]):>8s}")
        return 0
    info = SOURCE_INFO.get(args.source, {})
    license_name = info.get("license", "?")
    print(f"导入源: {args.source}（许可证: {license_name}）")
    if "NC" in license_name:
        print("[warn] 该数据集使用 CC BY-NC-SA（非商业许可），仅限研究/非商业用途！")
    report = importer.import_source(args.source, limit=args.limit,
                                    approve=args.approve, task=args.task,
                                    lang=args.lang, dry_run=args.dry_run,
                                    checkpoint=args.checkpoint,
                                    dedup_enabled=not args.no_dedup,
                                    seed=args.seed)
    print(f"共 {report['total']} 条：转换成功 {report['translated']}，"
          f"跳过 {report['skipped']}，结构不过 {report['failed_schema']}，"
          f"逻辑不过 {report['failed_logic']}，重复 {report['duplicates']}"
          + (f"，断点跳过 {report['checkpoint_skipped']}" if args.checkpoint else "")
          + "。")
    if args.dry_run:
        print(f"[dry-run] 未写入任何队列/题库：有效 {report['valid']} 条。")
        return 0
    print(f"进入待审队列 {report['pending']} 条"
          + (f"，审核入库 {report['approved']} 条" if args.approve else "。"))
    if args.approve and report["approve_failed"]:
        print(f"[warn] 有 {report['approve_failed']} 条未能直接审核入库"
              f"（未通过逻辑验证的题必须人工改写后才能入库）。")
        return 1
    return 0


def cmd_import_all(args):
    from logic_kids.bank.import_job import run_job
    result = run_job(args.config, dry_run=args.dry_run, retry=args.retry,
                     checkpoint=args.checkpoint, dedup_enabled=True)
    errors = [name for name, status in result["summary"] if status == "error"]
    if errors:
        print(f"\n完成（{len(errors)} 个来源失败）：{', '.join(errors)}")
        return 1
    print("\n全部来源导入完成。")
    return 0


def cmd_bank(args):
    from logic_kids.license_policy import check_bank
    counts = check_bank()
    print("许可证合规检查：")
    print(f"  Production-safe : {counts['production']}")
    print(f"  Non-commercial  : {counts['noncommercial']}")
    print(f"  Unknown         : {counts['unknown']}")
    if counts["unknown"]:
        print("[warn] 存在未知许可证题目，进入生产前需人工确认。")
        return 1
    return 0


def cmd_analyze_bank(args):
    from logic_kids.quality.analyzer import report_text
    print(report_text())
    return 0


def cmd_review(args):
    from logic_kids.bank import importer, provenance
    if args.approve_all:
        ok_n, fail_n, failures = importer.approve_all_pending(force=args.force)
        print(f"批量审核：通过 {ok_n}，失败 {fail_n}。")
        for msg in failures[:10]:
            print(f"  ✘ {msg}")
        return 0 if fail_n == 0 else 1
    if args.approve:
        ok, msg = importer.approve_pending(args.approve, force=args.force)
        print(msg)
        return 0 if ok else 1
    if args.reject:
        ok, msg = importer.reject_pending(args.reject)
        print(msg)
        return 0 if ok else 1
    items = provenance.list_pending()
    if not items:
        print("待审队列为空（先运行 python cli.py import ...）。")
        return 0
    marks = {"pending": "⏳", "approved": "✔", "rejected": "✘"}
    for it in items:
        mark = marks.get(it["review_status"], "?")
        lv = "是" if it["logic_validated"] else "否"
        print(f"  {mark} {it['qid']:48s} [{it['source']}] "
              f"{it['title'][:28]:28s} 逻辑验证={lv}")
    print(f"\n共 {len(items)} 条。")
    return 0


def cmd_external(args):
    from logic_kids.bank import external
    if args.action == "translate":
        from logic_kids.bank.sources import SOURCES

        def resolve(src):
            """按 CLI 键名或外部库 slug 找到适配器与外部库 slug。"""
            if src in SOURCES:
                return SOURCES[src], external.source_slug(
                    SOURCES[src].SOURCE_NAME)
            for key, mod in SOURCES.items():
                if external.source_slug(mod.SOURCE_NAME) == src:
                    return mod, src
            return None, None

        targets = [(args.source, *resolve(args.source))] if args.source else [
            (key, mod, external.source_slug(mod.SOURCE_NAME))
            for key, mod in SOURCES.items()
            if hasattr(mod, "zh_translate_question")]
        for key, mod, slug in targets:
            if mod is None or not hasattr(mod, "zh_translate_question"):
                print(f"[skip] {key}：该来源没有中文翻译器")
                continue
            qids = external.list_ids(slug)
            done = 0
            for qid in qids:
                q = external.load_question(slug, qid)
                if q is None:
                    continue
                q.translations = {"zh": mod.zh_translate_question(q)}
                child = getattr(mod, "zh_child_question", None)
                if child is not None:
                    q.translations["zh_child"] = child(q)
                external.save_question(q)
                done += 1
            print(f"已为外部来源 {key} 生成中文版：{done}/{len(qids)} 题"
                  "（机器翻译，建议人工校对后开放给儿童）。")
        return 0
    if args.action == "list":
        sources = external.list_sources()
        if not sources:
            print("外部题库为空（先 import 并 review --approve 后才有题）。")
            return 0
        print("外部题库来源：")
        for s in sources:
            print(f"  {s['slug']:10s} {s['name']:10s} {s['license']:18s} {s['total']} 题")
        return 0
    st = external.stats(args.source)
    print(f"外部题库总数: {st['total']}")
    print("按来源:")
    for s, n in st["by_source"].items():
        print(f"  {s:10s} {n}")
    print("按类型:")
    for t, n in st["by_type"].items():
        print(f"  {TYPE_NAMES.get(t, t):10s} {n}")
    print("按用户等级:")
    for lv in sorted(st["by_level"]):
        print(f"  {lv}. {difficulty_levels.name(lv):4s} {st['by_level'][lv]}")
    print("按能力:")
    for cat, n in st["by_category"].items():
        print(f"  {cat:12s} {n}")
    return 0


def main(argv=None):
    # 题库文案含 emoji（如 🧀），GBK 控制台打印会崩溃；统一用 UTF-8 输出
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="儿童逻辑推理训练软件 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="载入种子题").set_defaults(func=cmd_seed)

    p_gen = sub.add_parser("generate", help="生成题目入库")
    p_gen.add_argument("count", type=int, nargs="?", default=20)
    p_gen.add_argument("--seed", type=int, default=None)
    p_gen.set_defaults(func=cmd_generate)

    sub.add_parser("stats", help="题库统计").set_defaults(func=cmd_stats)
    sub.add_parser("validate", help="校验题库").set_defaults(func=cmd_validate)

    p_play = sub.add_parser("play", help="命令行答题演示")
    p_play.add_argument("--child", default="小朋友")
    p_play.add_argument("--rounds", type=int, default=5)
    p_play.add_argument("--seed", type=int, default=None)
    p_play.add_argument("--level", type=int, default=None,
                        help="固定难度等级 1..4（不指定则走自适应出题）")
    p_play.set_defaults(func=cmd_play)

    p_imp = sub.add_parser("import", help="导入外部题库（先进待审队列）")
    p_imp.add_argument("source",
                       choices=["bigbench", "logiqa", "reasoning_gym",
                                "stats"])
    p_imp.add_argument("--limit", type=int, default=None, help="最多导入条数")
    p_imp.add_argument("--task", default=None,
                       help="BIG-bench: task 路径（默认 logical_deduction/three_objects）；"
                            "LogiQA: split（默认 dev）")
    p_imp.add_argument("--lang", default=None,
                       help="LogiQA: zh（官方中文版，默认）或 en")
    p_imp.add_argument("--seed", type=int, default=None,
                       help="生成随机种子（reasoning_gym 用）")
    p_imp.add_argument("--approve", action="store_true",
                       help="通过四道闸门后直接审核入库")
    p_imp.add_argument("--dry-run", action="store_true",
                       help="只跑管线不入库（统计扫描/转换/有效数）")
    p_imp.add_argument("--checkpoint", action="store_true",
                       help="跳过已入库/待审的题目（断点续导）")
    p_imp.add_argument("--no-dedup", action="store_true",
                       help="关闭文本去重")
    p_imp.set_defaults(func=cmd_import)

    p_all = sub.add_parser("import-all", help="按配置文件批量导入")
    p_all.add_argument("config", help="datasets.yaml 路径")
    p_all.add_argument("--dry-run", action="store_true")
    p_all.add_argument("--retry", action="store_true",
                       help="只重跑上次失败的来源")
    p_all.add_argument("--checkpoint", action="store_true")
    p_all.set_defaults(func=cmd_import_all)

    p_bank = sub.add_parser("bank", help="题库管理")
    p_bank.add_argument("action", choices=["check-license"])
    p_bank.set_defaults(func=cmd_bank)

    sub.add_parser("analyze-bank", help="题库质量分析器").set_defaults(
        func=cmd_analyze_bank)

    p_rev = sub.add_parser("review", help="外部题待审队列管理")
    p_rev.add_argument("--approve", metavar="QID", default=None,
                       help="审核通过某题并移入正式题库")
    p_rev.add_argument("--approve-all", action="store_true",
                       help="批量审核全部待审题")
    p_rev.add_argument("--force", action="store_true",
                       help="无 DSL 的题也允许人工审核入库")
    p_rev.add_argument("--reject", metavar="QID", default=None,
                       help="标记某题 rejected")
    p_rev.set_defaults(func=cmd_review)

    p_ext = sub.add_parser("external", help="外部题库管理（与内置题库分开存储）")
    p_ext.add_argument("action", choices=["list", "stats", "translate"])
    p_ext.add_argument("source", nargs="?", default=None,
                       help="来源 slug（如 bigbench），仅 stats 用")
    p_ext.set_defaults(func=cmd_external)

    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
