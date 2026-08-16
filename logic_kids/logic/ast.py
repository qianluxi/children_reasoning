"""Logic DSL 的 AST 节点与求值器。

每个节点实现 eval_bool(ctx) / eval_int(ctx)，以及 depth()（供难度引擎使用）。
ctx 是 EvalContext，包含：
  - vars:            变量名 -> bool | int 的赋值
  - statement_truth: 各陈述句的真假列表（供 TRUTH_COUNT 约束使用）
"""
from __future__ import annotations

from typing import Optional


class EvalContext:
    def __init__(self, variables: dict, statement_truth: Optional[list] = None):
        self.vars = variables
        self.statement_truth = statement_truth or []


class LogicNode:
    type_ = "bool"  # "bool" | "int"

    def eval_bool(self, ctx: EvalContext) -> bool:
        raise NotImplementedError

    def eval_int(self, ctx: EvalContext) -> int:
        raise NotImplementedError

    def depth(self) -> int:
        raise NotImplementedError


class ConstNode(LogicNode):
    """TRUE / FALSE 常量。"""

    def __init__(self, value: bool):
        self.value = value

    def eval_bool(self, ctx: EvalContext) -> bool:
        return self.value

    def eval_int(self, ctx: EvalContext) -> int:
        return 1 if self.value else 0

    def depth(self) -> int:
        return 1


class BoolVarNode(LogicNode):
    """布尔变量，如 A_cheese。"""

    def __init__(self, name: str):
        self.name = name

    def eval_bool(self, ctx: EvalContext) -> bool:
        if self.name not in ctx.vars:
            raise KeyError(f"未知变量: {self.name}")
        return bool(ctx.vars[self.name])

    def eval_int(self, ctx: EvalContext) -> int:
        return 1 if self.eval_bool(ctx) else 0

    def depth(self) -> int:
        return 1


class NotNode(LogicNode):
    def __init__(self, child: LogicNode):
        self.child = child

    def eval_bool(self, ctx: EvalContext) -> bool:
        return not self.child.eval_bool(ctx)

    def eval_int(self, ctx: EvalContext) -> int:
        return 1 if self.eval_bool(ctx) else 0

    def depth(self) -> int:
        return 1 + self.child.depth()


class AndNode(LogicNode):
    def __init__(self, children: list):
        self.children = children

    def eval_bool(self, ctx: EvalContext) -> bool:
        return all(c.eval_bool(ctx) for c in self.children)

    def eval_int(self, ctx: EvalContext) -> int:
        return 1 if self.eval_bool(ctx) else 0

    def depth(self) -> int:
        return 1 + max((c.depth() for c in self.children), default=0)


class OrNode(LogicNode):
    def __init__(self, children: list):
        self.children = children

    def eval_bool(self, ctx: EvalContext) -> bool:
        return any(c.eval_bool(ctx) for c in self.children)

    def eval_int(self, ctx: EvalContext) -> int:
        return 1 if self.eval_bool(ctx) else 0

    def depth(self) -> int:
        return 1 + max((c.depth() for c in self.children), default=0)


class RankNode(LogicNode):
    """排列变量 RANK(A)，求值返回 int。"""

    type_ = "int"

    def __init__(self, var_name: str):
        self.var_name = var_name  # 形如 "rank_A"

    def eval_bool(self, ctx: EvalContext) -> bool:
        raise TypeError("RANK 节点不能直接当布尔值使用")

    def eval_int(self, ctx: EvalContext) -> int:
        if self.var_name not in ctx.vars:
            raise KeyError(f"未知变量: {self.var_name}")
        return int(ctx.vars[self.var_name])

    def depth(self) -> int:
        return 1


class CountNode(LogicNode):
    """COUNT(prop)：统计拥有该属性的实体数量，求值返回 int。"""

    type_ = "int"

    def __init__(self, var_names: list):
        self.var_names = var_names

    def eval_bool(self, ctx: EvalContext) -> bool:
        raise TypeError("COUNT 节点不能直接当布尔值使用")

    def eval_int(self, ctx: EvalContext) -> int:
        return sum(1 for n in self.var_names if bool(ctx.vars[n]))

    def depth(self) -> int:
        return 1


class CompareNode(LogicNode):
    """数值比较：RANK(A) < 2、COUNT(cheese) >= 1、RANK(A) != RANK(B) 等。"""

    def __init__(self, lhs, op: str, rhs):
        self.lhs = lhs          # RankNode | CountNode | int
        self.op = op
        self.rhs = rhs

    def _value(self, node, ctx: EvalContext) -> int:
        return node if isinstance(node, int) else node.eval_int(ctx)

    def eval_bool(self, ctx: EvalContext) -> bool:
        a, b = self._value(self.lhs, ctx), self._value(self.rhs, ctx)
        if self.op == "==":
            return a == b
        if self.op == "!=":
            return a != b
        if self.op == "<":
            return a < b
        if self.op == "<=":
            return a <= b
        if self.op == ">":
            return a > b
        if self.op == ">=":
            return a >= b
        raise ValueError(f"未知比较运算符: {self.op}")

    def eval_int(self, ctx: EvalContext) -> int:
        return 1 if self.eval_bool(ctx) else 0

    def depth(self) -> int:
        return 1


class QuantifierNode(LogicNode):
    """量词：ALL(prop) 所有 / SOME(prop) 有些 / NONE(prop) 没有 / SOME_NOT(prop) 有些没。"""

    def __init__(self, kind: str, var_names: list):
        self.kind = kind
        self.var_names = var_names

    def eval_bool(self, ctx: EvalContext) -> bool:
        values = [bool(ctx.vars[n]) for n in self.var_names]
        if self.kind == "all":
            return all(values)
        if self.kind == "some":
            return any(values)
        if self.kind == "none":
            return not any(values)
        if self.kind == "some_not":
            return not all(values)
        raise ValueError(f"未知量词: {self.kind}")

    def eval_int(self, ctx: EvalContext) -> int:
        return 1 if self.eval_bool(ctx) else 0

    def depth(self) -> int:
        return 1


class ExactlyNode(LogicNode):
    """EXACTLY(k, e1, e2, …)：恰好有 k 个表达式为真。"""

    def __init__(self, k: int, children: list):
        self.k = k
        self.children = children

    def eval_bool(self, ctx: EvalContext) -> bool:
        return sum(1 for c in self.children if c.eval_bool(ctx)) == self.k

    def eval_int(self, ctx: EvalContext) -> int:
        return 1 if self.eval_bool(ctx) else 0

    def depth(self) -> int:
        return 1 + max((c.depth() for c in self.children), default=0)
