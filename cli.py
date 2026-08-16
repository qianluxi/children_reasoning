"""命令行工具。

用法示例：
    python cli.py seed                 # 载入人工种子题
    python cli.py generate 50          # 生成 50 道题入库
    python cli.py stats                # 题库统计
    python cli.py validate             # 校验题库全部题目
    python cli.py play --child 小明     # 命令行答题演示（自适应出题）
"""
from __future__ import annotations

import argparse
import random
import sys

from logic_kids.bank import store, seed
from logic_kids.difficulty import engine as difficulty_engine
from logic_kids.validator.validator import validate
from logic_kids.questions.generator import generate_batch, TYPE_NAMES
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
    print(f"你好，{args.child}！开始答题（输入 q 退出）。\n")
    for round_no in range(1, args.rounds + 1):
        pick = adaptive.next_question(child_id, rng)
        if pick is None:
            print("题库里没有可用的题目了，请先运行: python cli.py generate 50")
            break
        q = pick["question"]
        print(f"— 第 {round_no} 题 [{TYPE_NAMES.get(q.type, q.type)} {'★'*q.difficulty}] —")
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


def main(argv=None):
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
    p_play.set_defaults(func=cmd_play)

    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
