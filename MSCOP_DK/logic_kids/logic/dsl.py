"""Logic DSL：词法分析 + 递归下降解析（专家意见第十一节，简化版）。

语法：
    expr      := or_expr
    or_expr   := and_expr ('||' and_expr)*
    and_expr  := not_expr ('&&' not_expr)*
    not_expr  := '!' not_expr | cmp_expr
    cmp_expr  := operand (cmp_op (NUMBER | RANK '(' IDENT ')'))*    # 支持链式比较
    operand   := primary | RANK '(' IDENT ')' | COUNT '(' prop ')'
    primary   := 'TRUE' | 'FALSE' | IDENT | '(' expr ')'
               | ALL '(' prop ')' | SOME '(' prop ')' | NONE '(' prop ')'
               | NOT_ALL '(' prop ')' | SOME_NOT '(' prop ')'  # SOME_NOT 是旧别名
               | EXACTLY '(' NUMBER ',' expr (',' expr)* ')'

约束（constraint）额外支持：
    TRUTH_COUNT cmp NUMBER     # 恰好/至少…句陈述为真
    ORDER(A, B, C, …)          # RANK(A) < RANK(B) < RANK(C) < …

量词按变量名后缀展开：ALL(cheese) 覆盖所有以 "_cheese" 结尾的布尔变量。

量词语义（专家审查 P1，避免儿童语言歧义）：
  · ALL(prop)      所有都有
  · NONE(prop)     谁都没有
  · SOME(prop)     至少一个有
  · NOT_ALL(prop)  不是所有都有（= 至少一个没有；SOME_NOT 是它的旧名）
  · "有些人有，有些人没有" 应写成 SOME(prop) && NOT_ALL(prop)
"""
from __future__ import annotations

import re

from . import ast

# ---------- 词法 ----------

_TOKEN_RE = re.compile(
    r"\s*(?:(?P<kw>TRUTH_COUNT|ORDER|RANK|COUNT|ALL|NOT_ALL|SOME_NOT|SOME|NONE|EXACTLY|TRUE|FALSE)"
    r"|(?P<op>&&|\|\||==|!=|<=|>=|<|>|!|\(|\)|,)"
    r"|(?P<num>\d+)"
    r"|(?P<id>[A-Za-z_][A-Za-z0-9_]*))"
)

_CMP_OPS = {"==", "!=", "<", "<=", ">", ">="}


class DSLSyntaxError(ValueError):
    pass


def _tokenize(text: str) -> list:
    tokens, pos = [], 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            # 剩余部分全是空白（尾随空格/换行）是合法的，正常结束
            if not text[pos:].strip():
                break
            raise DSLSyntaxError(f"无法解析的位置 {pos}: {text[pos:pos+10]!r}（原文：{text}）")
        pos = m.end()
        if m.group("kw"):
            tokens.append(("KW", m.group("kw")))
        elif m.group("op"):
            tokens.append(("OP", m.group("op")))
        elif m.group("num") is not None:
            tokens.append(("NUM", int(m.group("num"))))
        else:
            tokens.append(("ID", m.group("id")))
    tokens.append(("EOF", None))
    return tokens


# ---------- 解析器 ----------

class _Parser:
    def __init__(self, text: str, varnames: list):
        self.tokens = _tokenize(text)
        self.pos = 0
        self.varnames = set(varnames)

    # -- 基础工具 --
    def peek(self):
        return self.tokens[self.pos]

    def next(self):
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def expect_op(self, op: str):
        t = self.next()
        if t != ("OP", op):
            raise DSLSyntaxError(f"期望 '{op}'，实际是 {t[1]}")

    def expect_kw(self, kw: str):
        t = self.next()
        if t != ("KW", kw):
            raise DSLSyntaxError(f"期望 {kw}，实际是 {t[1]}")

    def expect_id(self) -> str:
        t = self.next()
        if t[0] != "ID":
            raise DSLSyntaxError(f"期望标识符，实际是 {t[1]}")
        return t[1]

    def at_op(self, op: str) -> bool:
        return self.peek() == ("OP", op)

    def at_kw(self, kw: str) -> bool:
        return self.peek() == ("KW", kw)

    # -- 量词展开：prop -> 匹配 "_prop" 后缀的变量名 --
    def _resolve_prop(self, prop: str) -> list:
        suffix = f"_{prop}"
        names = sorted(n for n in self.varnames if n.endswith(suffix))
        if not names:
            raise DSLSyntaxError(f"没有找到属性 '{prop}' 对应的变量")
        return names

    # -- 语法 --
    def _expect_eof(self):
        """表达式解析完成后必须到结尾；DSL 是裁判语言，不能静默忽略尾随内容。"""
        if self.peek()[0] != "EOF":
            raise DSLSyntaxError(f"表达式后有未解析的内容: {self.peek()[1]!r}")

    def parse_expr(self) -> ast.LogicNode:
        node = self._or()
        self._expect_eof()
        return node

    def _or(self) -> ast.LogicNode:
        children = [self._and()]
        while self.at_op("||"):
            self.next()
            children.append(self._and())
        return children[0] if len(children) == 1 else ast.OrNode(children)

    def _and(self) -> ast.LogicNode:
        children = [self._not()]
        while self.at_op("&&"):
            self.next()
            children.append(self._not())
        return children[0] if len(children) == 1 else ast.AndNode(children)

    def _not(self) -> ast.LogicNode:
        if self.at_op("!"):
            self.next()
            return ast.NotNode(self._not())
        return self._cmp()

    def _cmp(self) -> ast.LogicNode:
        """比较层：支持 RANK(A) < RANK(B) < 3 的链式比较；普通布尔原子直接返回。"""
        first = self._primary()
        if self.at_cmp() and not isinstance(first, (ast.RankNode, ast.CountNode)):
            raise DSLSyntaxError("布尔表达式不能参与大小比较")
        compares = []
        while self.at_cmp():
            op = self.next()[1]
            rhs = self._cmp_operand()
            compares.append(ast.CompareNode(first, op, rhs))
            first = rhs  # 链式：A < B < C 等价于 (A<B) && (B<C)
        if isinstance(first, (ast.RankNode, ast.CountNode)) and not compares:
            raise DSLSyntaxError("RANK/COUNT 必须用于比较")
        if not compares:
            return first
        return compares[0] if len(compares) == 1 else ast.AndNode(compares)

    def at_cmp(self) -> bool:
        return self.peek()[0] == "OP" and self.peek()[1] in _CMP_OPS

    def _cmp_operand(self):
        if self.peek()[0] == "NUM":
            return self.next()[1]
        if self.at_kw("RANK"):
            return self._rank()
        if self.at_kw("COUNT"):
            return self._count()
        # 括号内的表达式再作为操作数（如 (COUNT(x) >= 1) 已在 primary 层处理）
        raise DSLSyntaxError(f"比较右侧必须是数字或 RANK/COUNT：{self.peek()[1]}")

    def _rank(self) -> ast.RankNode:
        self.expect_kw("RANK")
        self.expect_op("(")
        code = self.expect_id()
        self.expect_op(")")
        var = f"rank_{code}"
        if var not in self.varnames:
            raise DSLSyntaxError(f"未知实体: {code}（题目没有变量 {var}）")
        return ast.RankNode(var)

    def _count(self) -> ast.CountNode:
        self.expect_kw("COUNT")
        self.expect_op("(")
        prop = self.expect_id()
        self.expect_op(")")
        return ast.CountNode(self._resolve_prop(prop))

    def _primary(self) -> ast.LogicNode:
        t = self.peek()
        if t == ("KW", "TRUE"):
            self.next()
            return ast.ConstNode(True)
        if t == ("KW", "FALSE"):
            self.next()
            return ast.ConstNode(False)
        if self.at_kw("RANK"):
            return self._rank()
        if self.at_kw("COUNT"):
            return self._count()
        if self.at_op("("):
            self.next()
            node = self._or()
            self.expect_op(")")
            return node
        if self.at_op("!"):
            raise DSLSyntaxError("'!' 不能出现在这里")
        if t[0] == "ID":
            self.next()
            name = t[1]
            if name not in self.varnames:
                raise DSLSyntaxError(f"未知变量: {name}")
            return ast.BoolVarNode(name)
        if t[0] == "KW" and t[1] in ("ALL", "SOME", "NONE", "SOME_NOT", "NOT_ALL"):
            self.next()
            # SOME_NOT 是 NOT_ALL 的旧别名，语义相同（"不是所有"）
            kind = {"ALL": "all", "SOME": "some", "NONE": "none",
                    "NOT_ALL": "not_all", "SOME_NOT": "not_all"}[t[1]]
            self.expect_op("(")
            prop = self.expect_id()
            self.expect_op(")")
            return ast.QuantifierNode(kind, self._resolve_prop(prop))
        if t == ("KW", "EXACTLY"):
            self.next()
            self.expect_op("(")
            k = self.next()[1]
            if not isinstance(k, int):
                raise DSLSyntaxError("EXACTLY 的第一个参数必须是数字")
            self.expect_op(",")
            children = [self._or()]
            while self.at_op(","):
                self.next()
                children.append(self._or())
            self.expect_op(")")
            return ast.ExactlyNode(k, children)
        raise DSLSyntaxError(f"意外的记号: {t[1]}")

    # -- 约束 --
    def parse_constraint(self) -> ast.LogicNode:
        if self.at_kw("TRUTH_COUNT"):
            self.next()
            op = self.next()
            if op[0] != "OP" or op[1] not in _CMP_OPS:
                raise DSLSyntaxError("TRUTH_COUNT 后必须是比较运算符")
            num = self.next()
            if num[0] != "NUM":
                raise DSLSyntaxError("TRUTH_COUNT 比较的右边必须是数字")
            node = _TruthCountNode(op[1], num[1])
        elif self.at_kw("ORDER"):
            self.next()
            self.expect_op("(")
            codes = [self.expect_id()]
            while self.at_op(","):
                self.next()
                codes.append(self.expect_id())
            self.expect_op(")")
            if len(codes) < 2:
                raise DSLSyntaxError("ORDER 至少需要两个实体")
            for code in codes:
                if f"rank_{code}" not in self.varnames:
                    raise DSLSyntaxError(f"未知实体: {code}（题目没有变量 rank_{code}）")
            compares = [
                ast.CompareNode(ast.RankNode(f"rank_{a}"), "<", ast.RankNode(f"rank_{b}"))
                for a, b in zip(codes, codes[1:])
            ]
            node = ast.AndNode(compares)
        else:
            node = self.parse_expr()
        self._expect_eof()
        return node


class _TruthCountNode(ast.LogicNode):
    """TRUTH_COUNT op n：真假话问题的核心约束。"""

    def __init__(self, op: str, num: int):
        self.op, self.num = op, num

    def eval_bool(self, ctx: ast.EvalContext) -> bool:
        count = sum(1 for v in ctx.statement_truth if v)
        if self.op == "==":
            return count == self.num
        if self.op == "!=":
            return count != self.num
        if self.op == "<":
            return count < self.num
        if self.op == "<=":
            return count <= self.num
        if self.op == ">":
            return count > self.num
        if self.op == ">=":
            return count >= self.num
        raise ValueError(f"未知比较运算符: {self.op}")

    def eval_int(self, ctx: ast.EvalContext) -> int:
        return 1 if self.eval_bool(ctx) else 0

    def depth(self) -> int:
        return 1


# ---------- 对外接口 ----------

def parse_expr(text: str, varnames: list) -> ast.LogicNode:
    """解析表达式（陈述句逻辑 / 选项逻辑）。"""
    return _Parser(text, list(varnames)).parse_expr()


def parse_constraint(text: str, varnames: list) -> ast.LogicNode:
    """解析约束（规则 / 事实）。"""
    return _Parser(text, list(varnames)).parse_constraint()


def max_depth(expr_texts: list, varnames: list) -> int:
    """多个表达式中的最大嵌套深度（供难度引擎使用）。"""
    best = 0
    for text in expr_texts:
        try:
            node = parse_constraint(text, varnames)
        except DSLSyntaxError:
            continue
        best = max(best, node.depth())
    return best


def chain_length(constraint_texts: list, varnames: list) -> int:
    """约束中最长链式比较的长度（如 RANK(A)<RANK(B)<RANK(C) 长度为 2）。"""
    best = 0
    for text in constraint_texts:
        try:
            node = parse_constraint(text, varnames)
        except DSLSyntaxError:
            continue
        if isinstance(node, ast.CompareNode):
            best = max(best, 1)
        elif isinstance(node, ast.AndNode):
            n = sum(1 for c in node.children if isinstance(c, ast.CompareNode))
            best = max(best, n)
    return best
