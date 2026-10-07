"""Kite parser: tokens -> AST (Pratt expression parsing)."""

from .lexer import tokenize, KiteError, Token
from . import ast as A

PREC = {
    "or": 1,
    "and": 2,
    "not": 3,
    "==": 4, "!=": 4, "is": 4, "isnt": 4, "<": 4, "<=": 4, ">": 4, ">=": 4,
    "..": 5,
    "+": 6, "-": 6,
    "*": 7, "/": 7, "%": 7,
}
UNARY_PREC = 8
POSTFIX_PREC = 9

ASSIGN_OPS = {"=", "+=", "-=", "*=", "/="}
EXPR_START = {"NUM", "STR", "ID", "LP", "LBRACKET", "MAPSTART",
              "KW:make", "KW:not", "KW:true", "KW:false", "KW:nil"}


class Parser:
    def __init__(self, tokens, src_name="<kite>"):
        self.toks = tokens
        self.pos = 0
        self.src_name = src_name

    # --- token helpers ---

    def peek(self, k=0):
        return self.toks[min(self.pos + k, len(self.toks) - 1)]

    def next(self):
        t = self.toks[self.pos]
        if t.type != "EOF":
            self.pos += 1
        return t

    def at(self, type_, value=None):
        t = self.peek()
        return t.type == type_ and (value is None or t.value == value)

    def at_kw(self, kw):
        return self.peek().type == "KW" and self.peek().value == kw

    def expect(self, type_, value=None, what=None):
        t = self.peek()
        if t.type != type_ or (value is not None and t.value != value):
            want = what or (value if value is not None else type_.lower())
            got = t.value if t.value is not None else t.type
            raise KiteError(f"expected {want}, got {got!r}", t.line, t.col)
        return self.next()

    def at_expr_start(self):
        t = self.peek()
        if t.type == "KW":
            return f"KW:{t.value}" in EXPR_START
        return t.type in EXPR_START

    # --- entry ---

    def parse(self):
        stmts = []
        while not self.at("EOF"):
            stmts.append(self.statement())
        return A.Program(stmts=stmts, line=1, col=1)

    # --- statements ---

    def block(self):
        start = self.expect("LBRACE", what="'{'")
        stmts = []
        while not self.at("RBRACE"):
            if self.at("EOF"):
                raise KiteError("expected '}' before end of file", start.line, start.col)
            stmts.append(self.statement())
        self.expect("RBRACE", what="'}'")
        return A.Block(stmts=stmts, line=start.line, col=start.col)

    def statement(self):
        t = self.peek()
        if t.type == "KW":
            if t.value == "set":
                return self.set_stmt()
            if t.value == "fix":
                return self.fix_stmt()
            if t.value == "make":
                if self.peek(1).type == "ID" and self.peek(2).type == "LP":
                    return self.make_stmt()
            if t.value == "ret":
                return self.ret_stmt()
            if t.value == "when":
                return self.when_stmt()
            if t.value == "while":
                return self.while_stmt()
            if t.value == "each":
                return self.each_stmt()
            if t.value == "break":
                self.next()
                return A.Break(line=t.line, col=t.col)
            if t.value == "continue":
                self.next()
                return A.Continue(line=t.line, col=t.col)
            if t.value == "app":
                return self.app_stmt()
            if t.value == "state":
                return self.state_stmt()
            if t.value == "goto":
                self.next()
                target = self.expect("ID", what="screen name")
                return A.Goto(target=target.value, line=t.line, col=t.col)
            if t.value == "screen":
                self.next()
                name = ""
                if self.at("ID"):
                    name = self.next().value
                b = self.block()
                return A.Screen(body=b, name=name, line=t.line, col=t.col)
        return self.expr_stmt()

    def set_stmt(self):
        t = self.next()
        name = self.expect("ID", what="variable name")
        self.expect("OP", "=", what="'='")
        value = self.expr(allow_block=False)
        return A.Set(name=name.value, value=value, line=t.line, col=t.col)

    def fix_stmt(self):
        t = self.next()
        name = self.expect("ID", what="constant name")
        self.expect("OP", "=", what="'='")
        value = self.expr(allow_block=False)
        return A.Fix(name=name.value, value=value, line=t.line, col=t.col)

    def state_stmt(self):
        t = self.next()
        name = self.expect("ID", what="state name")
        self.expect("OP", "=", what="'='")
        value = self.expr(allow_block=False)
        return A.State(name=name.value, value=value, line=t.line, col=t.col)

    def make_stmt(self):
        t = self.next()  # 'make'
        name = self.expect("ID", what="function name")
        params = self.param_list()
        body = self.block()
        return A.Make(params=params, body=body, name=name.value,
                      line=t.line, col=t.col)

    def param_list(self):
        self.expect("LP", what="'('")
        params = []
        if not self.at("RP"):
            while True:
                p = self.expect("ID", what="parameter name")
                params.append(p.value)
                if self.at("OP", ","):
                    self.next()
                else:
                    break
        self.expect("RP", what="')'")
        return params

    def ret_stmt(self):
        t = self.next()
        value = None
        if self.at_expr_start():
            value = self.expr(allow_block=True)
        return A.Ret(value=value, line=t.line, col=t.col)

    def when_stmt(self):
        t = self.next()
        cond = self.expr(allow_block=False)
        then = self.block()
        other = None
        if self.at_kw("else"):
            self.next()
            if self.at_kw("when"):
                other = self.when_stmt()
            else:
                other = self.block()
        return A.When(cond=cond, then=then, other=other, line=t.line, col=t.col)

    def while_stmt(self):
        t = self.next()
        cond = self.expr(allow_block=False)
        body = self.block()
        return A.While(cond=cond, body=body, line=t.line, col=t.col)

    def each_stmt(self):
        t = self.next()
        var = self.expect("ID", what="loop variable")
        self.expect("KW", "in", what="'in'")
        it = self.expr(allow_block=False)
        body = self.block()
        return A.Each(var=var.value, iterable=it, body=body,
                      line=t.line, col=t.col)

    def app_stmt(self):
        t = self.next()
        name = self.expect("ID", what="app name")
        self.expect("LBRACE", what="'{'")
        members = []
        while not self.at("RBRACE"):
            if self.at("EOF"):
                raise KiteError("expected '}' before end of file", t.line, t.col)
            members.append(self.statement())
        self.expect("RBRACE", what="'}'")
        return A.App(name=name.value, members=members, line=t.line, col=t.col)

    def expr_stmt(self):
        t = self.peek()
        expr = self.expr(allow_block=True)
        if self.peek().type == "OP" and self.peek().value in ASSIGN_OPS:
            op = self.next().value
            value = self.expr(allow_block=False)
            if not isinstance(expr, (A.Ident, A.Index, A.Attr)):
                raise KiteError("invalid assignment target", t.line, t.col)
            return A.Assign(target=expr, op=op, value=value, line=t.line, col=t.col)
        return A.ExprStmt(expr=expr, line=t.line, col=t.col)

    # --- expressions ---

    def expr(self, min_prec=1, allow_block=True):
        left = self.unary(allow_block)
        while True:
            t = self.peek()
            if t.type == "OP":
                op = t.value
            elif t.type == "KW" and t.value in ("and", "or", "is", "isnt"):
                op = t.value
            else:
                break
            prec = PREC.get(op, -1)
            if prec < min_prec:
                break
            self.next()
            right = self.expr(prec + 1, allow_block)
            left = A.Binary(op=op, left=left, right=right, line=t.line, col=t.col)
        return left

    def unary(self, allow_block):
        t = self.peek()
        if t.type == "OP" and t.value == "-":
            self.next()
            operand = self.expr(UNARY_PREC, allow_block)
            return A.Unary(op="-", operand=operand, line=t.line, col=t.col)
        if t.type == "KW" and t.value == "not":
            self.next()
            operand = self.expr(3, allow_block)
            return A.Unary(op="not", operand=operand, line=t.line, col=t.col)
        if t.type == "KW" and t.value == "make":
            return self.make_expr()
        return self.postfix(allow_block)

    def make_expr(self):
        t = self.next()  # 'make'
        params = self.param_list()
        body = self.block()
        return A.Make(params=params, body=body, name=None, line=t.line, col=t.col)

    def postfix(self, allow_block):
        node = self.primary()
        while True:
            t = self.peek()
            if t.type == "LP":
                self.next()
                args = []
                if not self.at("RP"):
                    while True:
                        args.append(self.expr(allow_block=False))
                        if self.at("OP", ","):
                            self.next()
                        else:
                            break
                        if self.at("RP"):
                            break
                self.expect("RP", what="')'")
                node = A.Call(callee=node, args=args, line=t.line, col=t.col)
            elif t.type == "LBRACKET":
                self.next()
                idx = self.expr(allow_block=False)
                self.expect("RBRACKET", what="']'")
                node = A.Index(obj=node, index=idx, line=t.line, col=t.col)
            elif t.type == "OP" and t.value == ".":
                self.next()
                name = self.expect("ID", what="property name")
                node = A.Attr(obj=node, name=name.value, line=t.line, col=t.col)
            elif t.type == "LBRACE" and allow_block:
                if isinstance(node, A.Call) and node.block is None:
                    node.block = self.block()
                elif isinstance(node, A.Ident):
                    b = self.block()
                    node = A.Call(callee=node, args=[], block=b,
                                  line=t.line, col=t.col)
                else:
                    break
            else:
                break
        return node

    def primary(self):
        t = self.peek()
        if t.type == "NUM":
            self.next()
            return A.Num(value=t.value, line=t.line, col=t.col)
        if t.type == "STR":
            self.next()
            return self.string_literal(t)
        if t.type == "ID":
            self.next()
            return A.Ident(name=t.value, line=t.line, col=t.col)
        if t.type == "LP":
            self.next()
            e = self.expr(allow_block=False)
            self.expect("RP", what="')'")
            return e
        if t.type == "LBRACKET":
            return self.list_literal()
        if t.type == "MAPSTART":
            return self.map_literal()
        if t.type == "KW":
            if t.value == "true":
                self.next()
                return A.Bool(value=True, line=t.line, col=t.col)
            if t.value == "false":
                self.next()
                return A.Bool(value=False, line=t.line, col=t.col)
            if t.value == "nil":
                self.next()
                return A.Nil(line=t.line, col=t.col)
            if t.value == "make":
                return self.make_expr()
            if t.value == "not":
                self.next()
                operand = self.expr(3, allow_block)
                return A.Unary(op="not", operand=operand, line=t.line, col=t.col)
        raise KiteError(f"unexpected {t.value!r}", t.line, t.col)

    def list_literal(self):
        start = self.expect("LBRACKET", what="'['")
        items = []
        if not self.at("RBRACKET"):
            while True:
                items.append(self.expr(allow_block=False))
                if self.at("OP", ","):
                    self.next()
                else:
                    break
                if self.at("RBRACKET"):
                    break
        self.expect("RBRACKET", what="']'")
        return A.ListLit(items=items, line=start.line, col=start.col)

    def map_literal(self):
        start = self.expect("MAPSTART", what="'#{'")
        entries = []
        if not self.at("RBRACE"):
            while True:
                key = self.expect("ID", what="map key")
                self.expect("OP", ":", what="':'")
                val = self.expr(allow_block=False)
                entries.append((key.value, val))
                if self.at("OP", ","):
                    self.next()
                else:
                    break
                if self.at("RBRACE"):
                    break
        self.expect("RBRACE", what="'}'")
        return A.MapLit(entries=entries, line=start.line, col=start.col)

    def string_literal(self, tok):
        raw = tok.value
        if "{" not in raw:
            return A.Str(value=raw, line=tok.line, col=tok.col)
        parts = []
        buf = []
        i = 0
        n = len(raw)
        while i < n:
            c = raw[i]
            if c == "\x00":
                if i + 1 < n:
                    buf.append(raw[i + 1])
                i += 2
                continue
            if c == "{":
                depth = 1
                j = i + 1
                while j < n:
                    if raw[j] == "\x00":
                        j += 2
                        continue
                    if raw[j] == "{":
                        depth += 1
                    elif raw[j] == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                if j >= n:
                    raise KiteError("unterminated '{' in string",
                                    tok.line, tok.col)
                if buf:
                    parts.append("".join(buf))
                    buf = []
                expr_src = raw[i + 1:j].replace("\x00", "")
                sub = tokenize(expr_src)
                p = Parser(sub, self.src_name)
                try:
                    parts.append(p.expr(allow_block=False))
                except KiteError as e:
                    raise KiteError(f"in string interpolation: {e.msg}",
                                    tok.line, tok.col)
                i = j + 1
                continue
            buf.append(c)
            i += 1
        if buf:
            parts.append("".join(buf))
        if len(parts) == 1 and isinstance(parts[0], str):
            return A.Str(value=parts[0], line=tok.line, col=tok.col)
        return A.StrInterp(parts=parts, line=tok.line, col=tok.col)


def parse(src):
    return Parser(tokenize(src)).parse()
