"""Kite tree-walking interpreter."""

from .lexer import KiteError
from . import ast as A


class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


class KiteFunction:
    def __init__(self, node, env):
        self.node = node
        self.env = env

    def __repr__(self):
        name = self.node.name or "make"
        return f"<fn {name}>"


class Env:
    def __init__(self, parent=None):
        self.vars = {}
        self.consts = set()
        self.parent = parent

    def define(self, name, value, const=False):
        self.vars[name] = value
        if const:
            self.consts.add(name)

    def get(self, name, node=None):
        env = self
        while env:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise KiteError(f"undefined variable '{name}'",
                        getattr(node, "line", 0), getattr(node, "col", 0))

    def assign(self, name, value, node=None):
        env = self
        while env:
            if name in env.vars:
                if name in env.consts:
                    raise KiteError(f"cannot reassign constant '{name}'",
                                    getattr(node, "line", 0),
                                    getattr(node, "col", 0))
                env.vars[name] = value
                return
            env = env.parent
        raise KiteError(f"undefined variable '{name}'",
                        getattr(node, "line", 0), getattr(node, "col", 0))

    def has(self, name):
        env = self
        while env:
            if name in env.vars:
                return True
            env = env.parent
        return False


def is_truthy(v):
    if v is None or v is False:
        return False
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v != 0
    if isinstance(v, (str, list, dict)):
        return len(v) != 0
    return True


class Interpreter:
    def __init__(self):
        self.globals = Env()
        self.install_builtins()

    # --- builtins ---

    def install_builtins(self):
        g = self.globals

        def b_print(*args):
            print(*[fmt(a) for a in args])
            return None

        def b_len(x):
            if isinstance(x, (str, list, dict)):
                return len(x)
            raise KiteError("len() expects a string, list, or map", 0, 0)

        def b_str(x):
            return fmt(x)

        def b_num(x):
            try:
                return float(x) if isinstance(x, str) and "." in x else int(x)
            except (ValueError, TypeError):
                try:
                    return float(x)
                except (ValueError, TypeError):
                    raise KiteError(f"cannot convert {x!r} to num", 0, 0)

        def b_type(x):
            if x is None:
                return "nil"
            if isinstance(x, bool):
                return "bool"
            if isinstance(x, (int, float)):
                return "num"
            if isinstance(x, str):
                return "str"
            if isinstance(x, list):
                return "list"
            if isinstance(x, dict):
                return "map"
            if isinstance(x, KiteFunction):
                return "fn"
            return "unknown"

        def b_range(a, b=None):
            if b is None:
                return list(range(int(a)))
            return list(range(int(a), int(b)))

        for name, fn in [("print", b_print), ("len", b_len), ("str", b_str),
                         ("num", b_num), ("type", b_type), ("range", b_range)]:
            g.define(name, fn)

    # --- entry ---

    def run(self, program):
        for stmt in program.stmts:
            self.exec(stmt, self.globals)

    # --- statements ---

    def exec(self, node, env):
        method = getattr(self, "exec_" + type(node).__name__, None)
        if method is None:
            raise KiteError(f"cannot execute {type(node).__name__}",
                            node.line, node.col)
        return method(node, env)

    def exec_Program(self, node, env):
        for s in node.stmts:
            self.exec(s, env)

    def exec_Block(self, node, env):
        for s in node.stmts:
            self.exec(s, env)

    def exec_Set(self, node, env):
        env.define(node.name, self.eval(node.value, env))

    def exec_Fix(self, node, env):
        env.define(node.name, self.eval(node.value, env), const=True)

    def exec_Assign(self, node, env):
        value = self.eval(node.value, env)
        t = node.target
        if isinstance(t, A.Ident):
            if node.op == "=":
                env.assign(t.name, value, node)
            else:
                old = env.get(t.name, node)
                value = self.binop(node.op[0], old, value, node)
                env.assign(t.name, value, node)
        elif isinstance(t, A.Index):
            obj = self.eval(t.obj, env)
            idx = self.eval(t.index, env)
            if not isinstance(obj, list) or not isinstance(idx, int):
                raise KiteError("invalid index assignment", node.line, node.col)
            if node.op == "=":
                obj[idx] = value
            else:
                obj[idx] = self.binop(node.op[0], obj[idx], value, node)
        elif isinstance(t, A.Attr):
            obj = self.eval(t.obj, env)
            if not isinstance(obj, dict):
                raise KiteError("cannot set property on non-map",
                                node.line, node.col)
            if node.op == "=":
                obj[t.name] = value
            else:
                obj[t.name] = self.binop(node.op[0], obj.get(t.name), value, node)
        else:
            raise KiteError("invalid assignment target", node.line, node.col)

    def exec_Make(self, node, env):
        env.define(node.name, KiteFunction(node, env))

    def exec_When(self, node, env):
        if is_truthy(self.eval(node.cond, env)):
            self.exec(node.then, Env(env))
        elif node.other is not None:
            self.exec(node.other, Env(env))

    def exec_While(self, node, env):
        while is_truthy(self.eval(node.cond, env)):
            try:
                self.exec(node.body, Env(env))
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def exec_Each(self, node, env):
        it = self.eval(node.iterable, env)
        if isinstance(it, dict):
            it = list(it.keys())
        if isinstance(it, (str, list)):
            items = list(it)
        elif isinstance(it, range):
            items = list(it)
        else:
            raise KiteError(f"cannot iterate over {type_name(it)}",
                            node.line, node.col)
        for item in items:
            loop_env = Env(env)
            loop_env.define(node.var, item)
            try:
                self.exec(node.body, loop_env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def exec_Ret(self, node, env):
        value = self.eval(node.value, env) if node.value is not None else None
        raise ReturnSignal(value)

    def exec_Break(self, node, env):
        raise BreakSignal()

    def exec_Continue(self, node, env):
        raise ContinueSignal()

    def exec_ExprStmt(self, node, env):
        self.eval(node.expr, env)

    # --- app preview (terminal) ---

    def exec_App(self, node, env):
        states = [m for m in node.members if isinstance(m, A.State)]
        screens = [m for m in node.members if isinstance(m, A.Screen)]
        for m in node.members:
            if not isinstance(m, (A.State, A.Screen)):
                self.exec(m, env)
        app_env = Env(env)
        for s in states:
            app_env.define(s.name, self.eval(s.value, app_env))
        print(f"--- app {node.name} (preview) ---")
        for s in screens:
            for stmt in s.body.stmts:
                tree = self.preview_stmt(stmt, app_env, "  ")
                if tree:
                    print(tree)
        print("--- end preview ---")

    def preview_stmt(self, stmt, env, pad):
        if not isinstance(stmt, A.ExprStmt):
            self.exec(stmt, env)
            return None
        return self.preview_expr(stmt.expr, env, pad)

    def preview_expr(self, expr, env, pad):
        if not isinstance(expr, A.Call):
            return None
        callee = expr.callee
        name = callee.name if isinstance(callee, A.Ident) else None
        if name == "text":
            val = self.eval(expr.args[0], env) if expr.args else ""
            return f"{pad}text: {fmt(val)}"
        if name == "btn":
            label = self.eval(expr.args[0], env) if expr.args else "?"
            return f"{pad}btn: {fmt(label)}"
        if name == "input":
            hint = self.eval(expr.args[0], env) if expr.args else ""
            return f"{pad}input: {fmt(hint)}"
        if name == "img":
            src = self.eval(expr.args[0], env) if expr.args else ""
            return f"{pad}img: {fmt(src)}"
        if name == "spacer":
            n = self.eval(expr.args[0], env) if expr.args else 8
            return f"{pad}spacer: {n}"
        if name in ("col", "row"):
            lines = [f"{pad}{name} {{"]
            if expr.block:
                for s in expr.block.stmts:
                    if isinstance(s, A.ExprStmt):
                        t = self.preview_expr(s.expr, env, pad + "  ")
                        if t:
                            lines.append(t)
                    elif isinstance(s, A.Each):
                        it = self.eval(s.iterable, env)
                        if isinstance(it, dict):
                            it = list(it.keys())
                        for item in it:
                            loop_env = Env(env)
                            loop_env.define(s.var, item)
                            for bs in s.body.stmts:
                                if isinstance(bs, A.ExprStmt):
                                    t = self.preview_expr(bs.expr, loop_env,
                                                          pad + "  ")
                                    if t:
                                        lines.append(t)
                    elif isinstance(s, A.When):
                        if is_truthy(self.eval(s.cond, env)):
                            for bs in s.then.stmts:
                                if isinstance(bs, A.ExprStmt):
                                    t = self.preview_expr(bs.expr, env,
                                                          pad + "  ")
                                    if t:
                                        lines.append(t)
                    elif isinstance(s, (A.Set, A.Assign, A.Fix)):
                        self.exec(s, env)
            lines.append(f"{pad}}}")
            return "\n".join(lines)
        return None

    # --- expressions ---

    def eval(self, node, env):
        method = getattr(self, "eval_" + type(node).__name__, None)
        if method is None:
            raise KiteError(f"cannot evaluate {type(node).__name__}",
                            node.line, node.col)
        return method(node, env)

    def eval_Num(self, node, env):
        return node.value

    def eval_Str(self, node, env):
        return node.value

    def eval_StrInterp(self, node, env):
        out = []
        for p in node.parts:
            v = self.eval(p, env) if not isinstance(p, str) else p
            out.append(fmt(v))
        return "".join(out)

    def eval_Bool(self, node, env):
        return node.value

    def eval_Nil(self, node, env):
        return None

    def eval_Make(self, node, env):
        return KiteFunction(node, env)

    def eval_Ident(self, node, env):
        return env.get(node.name, node)

    def eval_ListLit(self, node, env):
        return [self.eval(i, env) for i in node.items]

    def eval_MapLit(self, node, env):
        return {k: self.eval(v, env) for k, v in node.entries}

    def eval_Unary(self, node, env):
        v = self.eval(node.operand, env)
        if node.op == "-":
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise KiteError(f"cannot negate {type_name(v)}",
                                node.line, node.col)
            return -v
        if node.op == "not":
            return not is_truthy(v)
        raise KiteError(f"unknown unary op {node.op}", node.line, node.col)

    def eval_Binary(self, node, env):
        op = node.op
        if op == "and":
            left = self.eval(node.left, env)
            return self.eval(node.right, env) if is_truthy(left) else left
        if op == "or":
            left = self.eval(node.left, env)
            return left if is_truthy(left) else self.eval(node.right, env)
        left = self.eval(node.left, env)
        right = self.eval(node.right, env)
        return self.binop(op, left, right, node)

    def binop(self, op, a, b, node):
        try:
            if op in ("+", "-", "*", "/", "%"):
                if op == "+" and isinstance(a, str) and isinstance(b, str):
                    return a + b
                if op == "+" and isinstance(a, list) and isinstance(b, list):
                    return a + b
                if op in ("+", "-", "*", "/", "%"):
                    if not numlike(a) or not numlike(b):
                        raise KiteError(
                            f"unsupported operand types for '{op}': "
                            f"{type_name(a)} and {type_name(b)}",
                            node.line, node.col)
                    if op == "+":
                        return a + b
                    if op == "-":
                        return a - b
                    if op == "*":
                        return a * b
                    if op == "/":
                        if b == 0:
                            raise KiteError("division by zero",
                                            node.line, node.col)
                        return a / b
                    if b == 0:
                        raise KiteError("modulo by zero", node.line, node.col)
                    return a % b
            if op in ("==", "is"):
                return a == b
            if op in ("!=", "isnt"):
                return a != b
            if op == "<":
                return a < b
            if op == "<=":
                return a <= b
            if op == ">":
                return a > b
            if op == ">=":
                return a >= b
            if op == "..":
                if not (numlike(a) and numlike(b)):
                    raise KiteError("range bounds must be numbers",
                                    node.line, node.col)
                return list(range(int(a), int(b)))
        except KiteError:
            raise
        except TypeError:
            raise KiteError(f"cannot apply '{op}' to {type_name(a)} and "
                            f"{type_name(b)}", node.line, node.col)
        raise KiteError(f"unknown operator '{op}'", node.line, node.col)

    def eval_Call(self, node, env):
        callee = self.eval(node.callee, env)
        args = [self.eval(a, env) for a in node.args]
        if isinstance(callee, KiteFunction):
            if len(args) != len(callee.node.params):
                raise KiteError(
                    f"{callee.node.name or 'make'} expects "
                    f"{len(callee.node.params)} args, got {len(args)}",
                    node.line, node.col)
            fn_env = Env(callee.env)
            for p, a in zip(callee.node.params, args):
                fn_env.define(p, a)
            try:
                self.exec(callee.node.body, fn_env)
            except ReturnSignal as r:
                return r.value
            return None
        if callable(callee):
            try:
                return callee(*args)
            except TypeError:
                raise KiteError("wrong number of arguments to builtin",
                                node.line, node.col)
        raise KiteError(f"{type_name(callee)} is not callable",
                        node.line, node.col)

    def eval_Index(self, node, env):
        obj = self.eval(node.obj, env)
        idx = self.eval(node.index, env)
        if isinstance(obj, list):
            if not isinstance(idx, int) or isinstance(idx, bool):
                raise KiteError("list index must be a num",
                                node.line, node.col)
            if idx < 0:
                idx += len(obj)
            if idx < 0 or idx >= len(obj):
                raise KiteError(f"index {idx} out of range (len {len(obj)})",
                                node.line, node.col)
            return obj[idx]
        if isinstance(obj, dict):
            if idx not in obj:
                raise KiteError(f"map has no key {idx!r}",
                                node.line, node.col)
            return obj[idx]
        if isinstance(obj, str):
            if not isinstance(idx, int) or isinstance(idx, bool):
                raise KiteError("string index must be a num",
                                node.line, node.col)
            return obj[idx]
        raise KiteError(f"cannot index {type_name(obj)}",
                        node.line, node.col)

    def eval_Attr(self, node, env):
        obj = self.eval(node.obj, env)
        name = node.name
        if isinstance(obj, dict):
            if name in obj:
                return obj[name]
            m = self.map_method(obj, name, node)
            if m is not None:
                return m
            raise KiteError(f"map has no key '{name}'", node.line, node.col)
        if isinstance(obj, list):
            m = self.list_method(obj, name, node)
            if m is not None:
                return m
        if isinstance(obj, str):
            m = self.str_method(obj, name, node)
            if m is not None:
                return m
        if numlike(obj):
            m = self.num_method(obj, name, node)
            if m is not None:
                return m
        raise KiteError(f"{type_name(obj)} has no property '{name}'",
                        node.line, node.col)

    # bound methods: returning closures that take args

    def list_method(self, lst, name, node):
        if name == "push":
            return lambda *a: (lst.append(a[0]), len(lst))[1]
        if name == "pop":
            return lambda: lst.pop() if lst else None
        if name == "contains":
            return lambda x: x in lst
        if name == "join":
            return lambda sep=",": sep.join(fmt(x) for x in lst)
        if name == "first":
            return lambda: lst[0] if lst else None
        if name == "last":
            return lambda: lst[-1] if lst else None
        if name == "remove":
            def rm(x):
                if x in lst:
                    lst.remove(x)
                    return True
                return False
            return rm
        if name == "clear":
            return lambda: lst.clear()
        return None

    def str_method(self, s, name, node):
        if name == "upper":
            return lambda: s.upper()
        if name == "lower":
            return lambda: s.lower()
        if name == "trim":
            return lambda: s.strip()
        if name == "split":
            return lambda sep=" ": s.split(sep)
        if name == "contains":
            return lambda x: x in s
        if name == "replace":
            return lambda a, b: s.replace(a, b)
        if name == "starts":
            return lambda x: s.startswith(x)
        if name == "ends":
            return lambda x: s.endswith(x)
        return None

    def num_method(self, n, name, node):
        if name == "round":
            return lambda: round(n)
        if name == "floor":
            import math
            return lambda: math.floor(n)
        if name == "abs":
            return lambda: abs(n)
        if name == "min":
            return lambda o: min(n, o)
        if name == "max":
            return lambda o: max(n, o)
        return None

    def map_method(self, m, name, node):
        if name == "keys":
            return lambda: list(m.keys())
        if name == "values":
            return lambda: list(m.values())
        if name == "has":
            return lambda k: k in m
        if name == "get":
            return lambda k, d=None: m.get(k, d)
        if name == "put":
            def put(k, v):
                m[k] = v
                return m
            return put
        return None


def numlike(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def type_name(v):
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "num"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        return "list"
    if isinstance(v, dict):
        return "map"
    if isinstance(v, KiteFunction):
        return "fn"
    if callable(v):
        return "builtin"
    return type(v).__name__


def fmt(v):
    if v is None:
        return "nil"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, list):
        return "[" + ", ".join(fmt(x) for x in v) + "]"
    if isinstance(v, dict):
        return "#{" + ", ".join(f"{k}: {fmt(x)}" for k, x in v.items()) + "}"
    if isinstance(v, KiteFunction):
        return repr(v)
    if callable(v):
        return "<builtin>"
    return str(v)


def run_program(program):
    interp = Interpreter()
    interp.run(program)
    return interp
