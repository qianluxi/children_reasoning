"""Question Validator（专家意见第六节：不要只验证"答案"，还要验证"题目质量"）。

检查项：
  1. 选项数量合理且互不重复；
  2. 选项逻辑与选项一一对应；
  3. 有解（solutions >= 1）；
  4. 正确选项唯一（恰好一个选项在所有解中为真 —— 被答案蕴含）；
  5. 存储的 answer 与逻辑验证结果一致（文字与逻辑一致性）；
  6. 干扰项合理：每个错误选项至少在某个状态下能成立（不能明显荒谬）；
  7. 陈述句不能是恒真/恒假（要有推理价值）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..logic import solver
from ..models import Question

CONSTANT_LOGIC = {"TRUE"}   # "TRUE" 常量选项（如"无法判断"）是刻意设计的；FALSE 恒为荒谬


@dataclass
class ValidationReport:
    ok: bool = True
    issues: list = field(default_factory=list)
    solution_count: int = 0

    def add(self, issue: str) -> None:
        self.ok = False
        self.issues.append(issue)


def validate(question: Question) -> ValidationReport:
    report = ValidationReport()

    # 1. 选项
    if len(question.options) < 2:
        report.add("选项少于 2 个")
    if len(set(question.options)) != len(question.options):
        report.add("存在重复选项")
    if len(question.option_logic) != len(question.options):
        report.add(f"option_logic 数量({len(question.option_logic)})与选项数量({len(question.options)})不一致")

    # 2. 求解
    try:
        solutions = solver.solve(question)
    except solver.QuestionError as e:
        report.add(f"题目无法建模: {e}")
        return report
    report.solution_count = len(solutions)

    if not solutions:
        report.add("无解（solutions == 0）")

    # 3. 正确选项唯一（被全部解蕴含）
    counts = solver.option_truth_counts(question, solutions)
    entailed = [i for i, c in enumerate(counts) if c > 0 and c == len(solutions)]
    if not entailed:
        report.add("没有任何选项被所有解蕴含（题目无正确答案）")
    elif len(entailed) > 1:
        report.add(f"有 {len(entailed)} 个选项同时成立（多解），违反唯一正确原则: {entailed}")

    # 4. 存储答案与逻辑一致
    if entailed and entailed != [question.answer]:
        report.add(f"answer={question.answer} 与逻辑验证结果 {entailed} 不一致")

    # 5. 干扰项合理性：错误选项必须在某个状态下能成立
    if solutions:
        for i in range(len(question.options)):
            if i == question.answer:
                continue
            logic = question.option_logic[i].strip()
            if logic in CONSTANT_LOGIC:
                continue  # "TRUE" 常量选项（如"无法判断"）是刻意设计的
            plausible = False
            for state in solver._all_states(question):
                try:
                    node = _parse_opt(question, logic)
                    if node.eval_bool(_ctx(state)):
                        plausible = True
                        break
                except solver.QuestionError:
                    break
            if not plausible:
                report.add(f"干扰项[{i}] '{question.options[i]}' 在任何状态下都不成立（明显荒谬）")

    # 6. 陈述句要有推理价值（非恒真恒假）
    if question.statements:
        for s, (true_any, false_any) in zip(question.statements, solver.statement_domain_truth(question)):
            if true_any is not None and not (true_any and false_any):
                report.add(f"陈述句 '{s.text}' 是恒{'真' if true_any else '假'}的，没有推理价值")

    return report


def _parse_opt(question: Question, logic: str):
    from ..logic import dsl
    try:
        return dsl.parse_expr(logic, question.variable_names())
    except dsl.DSLSyntaxError as e:
        raise solver.QuestionError(str(e)) from e


def _ctx(state):
    from ..logic.ast import EvalContext
    return EvalContext(state)
