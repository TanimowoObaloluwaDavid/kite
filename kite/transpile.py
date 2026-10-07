"""Kite -> Dart/Flutter transpiler."""

from .lexer import KiteError
from . import ast as A

WIDGETS = {"col", "row", "text", "btn", "input", "img", "spacer", "bar"}

def dart_color(s):
    """'#ff5f57' -> Color(0xFFff5f57)."""
    h = s.lstrip("#").lstrip("0x")
    if len(h) == 6:
        h = "FF" + h
    return f"Color(0x{h})"

IND = "  "


def P(ind):
    return IND * ind


def dart_str(s):
    out = s.replace("\\", "\\\\").replace('"', '\\"')
    out = out.replace("$", "\\$")
    out = out.replace("\n", "\\n").replace("\t", "\\t")
    return f'"{out}"'


def esc_interpolated_expr(expr):
    return expr.replace("\\", "\\\\")


class Transpiler:
    def __init__(self):
        self.app_count = 0

    def transpile(self, program):
        lines = ["import 'package:flutter/material.dart';", ""]
        body = []
        for stmt in program.stmts:
            body.extend(self.stmt(stmt))
        if self.app_count == 0:
            raise KiteError(
                "no 'app' block found — a mobile app must declare `app Name { ... }`",
                1, 1)
        lines.extend(body)
        return "\n".join(lines) + "\n"

    # --- statements: return list of dart lines (unindented) ---

    def stmt(self, node, ind=0):
        m = getattr(self, "s_" + type(node).__name__, None)
        if m is None:
            raise KiteError(f"cannot compile {type(node).__name__}",
                            node.line, node.col)
        return m(node, ind)

    def s_Program(self, node, ind):
        out = []
        for s in node.stmts:
            out.extend(self.stmt(s, ind))
        return out

    def s_Block(self, node, ind):
        out = []
        for s in node.stmts:
            out.extend(self.stmt(s, ind))
        return out

    def s_Set(self, node, ind):
        return [f"{P(ind)}dynamic {node.name} = {self.expr(node.value)};"]

    def s_Fix(self, node, ind):
        return [f"{P(ind)}final {node.name} = {self.expr(node.value)};"]

    def s_Assign(self, node, ind):
        target = self.expr(node.target)
        value = self.expr(node.value)
        if node.op == "=":
            return [f"{P(ind)}{target} = {value};"]
        return [f"{P(ind)}{target} {node.op} {value};"]

    def s_Make(self, node, ind):
        name = node.name or "_"
        params = ", ".join(f"var {p}" for p in node.params)
        out = [f"{P(ind)}dynamic {name}({params}) {{"]
        body = []
        for s in node.body.stmts:
            body.extend(self.stmt(s, ind + 1))
        out.extend(body)
        out.append(f"{P(ind)}}}")
        return out

    def s_When(self, node, ind):
        out = [f"{P(ind)}if ({self.expr(node.cond)}) {{"]
        out.extend(self.s_Block(node.then, ind + 1))
        if node.other is not None:
            if isinstance(node.other, A.When):
                rest = self.s_When(node.other, ind)
                rest[0] = f"{P(ind)}}} else {rest[0].lstrip()}"
                out.extend(rest)
            else:
                out.append(f"{P(ind)}}} else {{")
                out.extend(self.s_Block(node.other, ind + 1))
                out.append(f"{P(ind)}}}")
                return out
        out.append(f"{P(ind)}}}")
        return out

    def s_While(self, node, ind):
        out = [f"{P(ind)}while ({self.expr(node.cond)}) {{"]
        out.extend(self.s_Block(node.body, ind + 1))
        out.append(f"{P(ind)}}}")
        return out

    def s_Each(self, node, ind):
        it = node.iterable
        if isinstance(it, A.Binary) and it.op == "..":
            start = self.expr(it.left)
            end = self.expr(it.right)
            out = [
                f"{P(ind)}for (var {node.var} = {start}; "
                f"{node.var} < {end}; {node.var}++) {{"
            ]
        else:
            out = [f"{P(ind)}for (final {node.var} in {self.expr(it)}) {{"]
        out.extend(self.s_Block(node.body, ind + 1))
        out.append(f"{P(ind)}}}")
        return out

    def s_Ret(self, node, ind):
        if node.value is None:
            return [f"{P(ind)}return;"]
        return [f"{P(ind)}return {self.expr(node.value)};"]

    def s_Break(self, node, ind):
        return [f"{P(ind)}break;"]

    def s_Continue(self, node, ind):
        return [f"{P(ind)}continue;"]

    def s_ExprStmt(self, node, ind):
        if isinstance(node.expr, A.Call):
            callee = node.expr.callee
            if isinstance(callee, A.Ident) and callee.name == "print":
                args = ", ".join(self.expr(a, ind, False) for a in node.expr.args)
                return [f"{P(ind)}debugPrint({args});"]
            if isinstance(callee, A.Ident) and callee.name in WIDGETS:
                return [f"{P(ind)}{self.expr(node.expr, ind, True)};"]
        return [f"{P(ind)}{self.expr(node.expr, ind, False)};"]

    # --- app / state / screen ---

    def screen_expr(self, screen, ind):
        """Compile a screen body into one widget expression."""
        stmts = screen.body.stmts
        if len(stmts) == 1 and isinstance(stmts[0], A.ExprStmt):
            return self.expr(stmts[0].expr, ind=ind, in_widget=True)
        elems = self.collection_elems(stmts, ind + 1)
        inner = (",\n" + P(ind + 2)).join(elems)
        return (f"Column(\n{P(ind + 1)}children: [\n"
                f"{P(ind + 2)}{inner},\n"
                f"{P(ind + 1)}],\n{P(ind)})")

    def s_App(self, node, ind):
        self.app_count += 1
        is_main = self.app_count == 1
        states = [m for m in node.members if isinstance(m, A.State)]
        screens = [m for m in node.members if isinstance(m, A.Screen)]
        others = [m for m in node.members
                  if not isinstance(m, (A.State, A.Screen))]
        if not screens:
            raise KiteError(f"app '{node.name}' has no screen {{ }} block",
                            node.line, node.col)
        names = []
        for i, s in enumerate(screens):
            nm = s.name or ("Main" if len(screens) == 1 else f"Screen{i}")
            if nm in names:
                raise KiteError(f"duplicate screen name '{nm}'",
                                s.line, s.col)
            names.append(nm)
            s.name = nm
        self.screen_names = set(names)
        cls = node.name
        multi = len(screens) > 1
        out = []
        out.append(f"{P(ind)}class {cls} extends StatefulWidget {{")
        out.append(f"{P(ind + 1)}const {cls}({{super.key}});")
        out.append(f"{P(ind + 1)}@override")
        out.append(f"{P(ind + 1)}State<{cls}> createState() => _{cls}State();")
        out.append(f"{P(ind)}}}")
        out.append("")
        out.append(f"{P(ind)}class _{cls}State extends State<{cls}> {{")
        if multi:
            out.append(f'{P(ind + 1)}dynamic __nav = "{names[0]}";')
        for s in states:
            out.append(f"{P(ind + 1)}dynamic {s.name} = {self.expr(s.value)};")
        for s in others:
            for line in self.stmt(s, ind + 1):
                out.append(line)
        out.append(f"{P(ind + 1)}@override")
        out.append(f"{P(ind + 1)}Widget build(BuildContext context) {{")
        if multi:
            out.append(f"{P(ind + 2)}Widget body;")
            for i, s in enumerate(screens):
                kw = "if" if i == 0 else "else if"
                out.append(f'{P(ind + 2)}{kw} (__nav == "{s.name}") {{')
                out.append(f"{P(ind + 3)}body = "
                           f"{self.screen_expr(s, ind + 4)};")
                out.append(f"{P(ind + 2)}}}")
            out.append(f"{P(ind + 2)}else {{")
            out.append(f"{P(ind + 3)}body = "
                       f"{self.screen_expr(screens[-1], ind + 4)};")
            out.append(f"{P(ind + 2)}}}")
            child = "body"
        else:
            child = None
        w = child or self.screen_expr(screens[0], ind + 4)
        out.append(f"{P(ind + 2)}return Scaffold(")
        out.append(f"{P(ind + 3)}body: SafeArea(")
        out.append(f"{P(ind + 4)}child: {w},")
        out.append(f"{P(ind + 3)}),")
        out.append(f"{P(ind + 2)});")
        out.append(f"{P(ind + 1)}}}")
        out.append(f"{P(ind)}}}")
        out.append("")
        if is_main:
            out.append(f"void main() => runApp(const KiteApp());")
            out.append("")
            out.append("class KiteApp extends StatelessWidget {")
            out.append("  const KiteApp({super.key});")
            out.append("  @override")
            out.append("  Widget build(BuildContext context) {")
            out.append("    return const MaterialApp(")
            out.append("      debugShowCheckedModeBanner: false,")
            out.append(f"      home: {cls}(),")
            out.append("    );")
            out.append("  }")
            out.append("}")
        return out

    def s_Goto(self, node, ind):
        names = getattr(self, "screen_names", None) or set()
        if node.target not in names:
            known = ", ".join(sorted(names)) or "(none)"
            raise KiteError(
                f"unknown screen '{node.target}' — app declares: {known}",
                node.line, node.col)
        return [f'{P(ind)}__nav = "{node.target}";']

    def s_State(self, node, ind):
        return [f"{P(ind)}dynamic {node.name} = {self.expr(node.value)};"]

    def s_Screen(self, node, ind):
        raise KiteError("screen can only appear inside an app block",
                        node.line, node.col)

    # --- expressions ---

    def expr(self, node, ind=0, in_widget=False, wrap_actions=True):
        m = getattr(self, "e_" + type(node).__name__, None)
        if m is None:
            raise KiteError(f"cannot compile expression "
                            f"{type(node).__name__}",
                            getattr(node, "line", 0),
                            getattr(node, "col", 0))
        return m(node, ind, in_widget)

    def e_Num(self, node, ind, w):
        v = node.value
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v)

    def e_Str(self, node, ind, w):
        return dart_str(node.value)

    def e_StrInterp(self, node, ind, w):
        parts = []
        for p in node.parts:
            if isinstance(p, str):
                parts.append(p.replace("\\", "\\\\").replace('"', '\\"')
                             .replace("$", "\\$").replace("\n", "\\n"))
            else:
                parts.append("${" + self.expr(p, ind, False) + "}")
        return '"' + "".join(parts) + '"'

    def e_Bool(self, node, ind, w):
        return "true" if node.value else "false"

    def e_Nil(self, node, ind, w):
        return "null"

    def e_Ident(self, node, ind, w):
        return node.name

    def e_ListLit(self, node, ind, w):
        return "[" + ", ".join(self.expr(i, ind, False) for i in node.items) + "]"

    def e_MapLit(self, node, ind, w):
        entries = ", ".join(
            f"{dart_str(k)}: {self.expr(v, ind, False)}"
            for k, v in node.entries)
        return "{" + entries + "}"

    def e_Unary(self, node, ind, w):
        if node.op == "not":
            return f"!({self.expr(node.operand, ind, False)})"
        return f"-({self.expr(node.operand, ind, False)})"

    def e_Binary(self, node, ind, w):
        opmap = {"is": "==", "isnt": "!=", "and": "&&", "or": "||"}
        op = opmap.get(node.op, node.op)
        if node.op == "..":
            a = self.expr(node.left, ind, False)
            b = self.expr(node.right, ind, False)
            return f"[for (var i = {a}; i < {b}; i++) i]"
        return (f"({self.expr(node.left, ind, False)} {op} "
                f"{self.expr(node.right, ind, False)})")

    def e_Index(self, node, ind, w):
        return (f"{self.expr(node.obj, ind, False)}"
                f"[{self.expr(node.index, ind, False)}]")

    def e_Attr(self, node, ind, w):
        return (f"{self.expr(node.obj, ind, False)}"
                f"[{dart_str(node.name)}]")

    def e_Make(self, node, ind, w):
        params = ", ".join(node.params)
        body_lines = []
        for s in node.body.stmts:
            body_lines.extend(self.stmt(s, ind + 1))
        body = "\n".join(body_lines)
        return f"(({params}) => {{\n{body}\n{P(ind)}}})"

    def e_Call(self, node, ind, w):
        callee = node.callee
        name = callee.name if isinstance(callee, A.Ident) else None

        if name == "print":
            args = ", ".join(self.expr(a, ind, False) for a in node.args)
            return f"debugPrint({args})"
        if name == "len":
            return f"({self.expr(node.args[0], ind, False)}).length"
        if name == "str":
            return f"({self.expr(node.args[0], ind, False)}).toString()"
        if name == "type":
            return f"({self.expr(node.args[0], ind, False)}).runtimeType.toString()"
        if name == "num":
            return f"num.parse({self.expr(node.args[0], ind, False)})"
        if name == "range":
            if len(node.args) == 1:
                return f"[for (var i = 0; i < {self.expr(node.args[0], ind, False)}; i++) i]"
            return (f"[for (var i = {self.expr(node.args[0], ind, False)}; "
                    f"i < {self.expr(node.args[1], ind, False)}; i++) i]")

        if name in WIDGETS:
            return self.widget_call(name, node, ind)

        # method calls: x.push(...) -> x.add(...)
        if isinstance(callee, A.Attr):
            obj = self.expr(callee.obj, ind, False)
            m = callee.name
            method_map = {"push": "add", "pop": "removeLast",
                          "upper": "toUpperCase", "lower": "toLowerCase",
                          "trim": "trim", "split": "split",
                          "contains": "contains", "replace": "replaceAll",
                          "keys": "keys.toList", "values": "values.toList",
                          "has": "containsKey", "join": "join",
                          "starts": "startsWith", "ends": "endsWith",
                          "put": "addAll", "first": "first",
                          "last": "last"}
            args = ", ".join(self.expr(a, ind, False) for a in node.args)
            if m == "push":
                return f"{obj}.add({args})"
            if m == "remove":
                return f"{obj}.remove({args})"
            if m == "clear":
                return f"{obj}.clear()"
            if m == "get":
                return f"{obj}[{args}]"
            if m == "put":
                k, v = (self.expr(a, ind, False) for a in node.args)
                return f"{obj}[{k}] = {v}"
            if m == "floor":
                return f"{obj}.floor()"
            dm = method_map.get(m, m)
            return f"{obj}.{dm}({args})"

        args = ", ".join(self.expr(a, ind, False) for a in node.args)
        if node.block is not None:
            raise KiteError("trailing block is only supported on widgets "
                            "(col, row, btn, ...)", node.line, node.col)
        return f"{self.expr(callee, ind, False)}({args})"

    # --- widgets ---

    def collection_elems(self, stmts, ind):
        """Compile statements inside a widget children list into Dart
        collection elements (widgets, collection-for, collection-if)."""
        elems = []
        for s in stmts:
            if isinstance(s, A.ExprStmt):
                if isinstance(s.expr, A.Call):
                    callee = s.expr.callee
                    if isinstance(callee, A.Ident) and callee.name == "print":
                        args = ", ".join(self.expr(a, ind, False)
                                         for a in s.expr.args)
                        elems.append(f"Builder(builder: (_) {{ "
                                     f"debugPrint({args}); return const "
                                     f"SizedBox.shrink(); }})")
                        continue
                elems.append(self.expr(s.expr, ind, True))
            elif isinstance(s, A.Each):
                if isinstance(s.iterable, A.Binary) and s.iterable.op == "..":
                    head = (f"for (var {s.var} = "
                            f"{self.expr(s.iterable.left, ind, False)}; "
                            f"{s.var} < {self.expr(s.iterable.right, ind, False)}; "
                            f"{s.var}++)")
                else:
                    head = (f"for (final {s.var} in "
                            f"{self.expr(s.iterable, ind, False)})")
                body = self.collection_elems(s.body.stmts, ind + 1)
                elems.append(self.nest_elems(head, body, ind))
            elif isinstance(s, A.When):
                then = self.collection_elems(s.then.stmts, ind + 1)
                cond = self.expr(s.cond, ind, False)
                if s.other is None:
                    elems.append(self.nest_elems(f"if ({cond})", then, ind))
                elif isinstance(s.other, A.When):
                    els = self.collection_elems([s.other], ind + 1)
                    elems.append(self.nest_elems(f"if ({cond})", then, ind,
                                                 f"else {els[0]}"))
                else:
                    els = self.collection_elems(s.other.stmts, ind + 1)
                    elems.append(self.nest_elems(f"if ({cond})", then, ind,
                                                 self.nest_elems("else", els,
                                                                 ind)))
            else:
                raise KiteError(
                    "only widgets, 'when', and 'each' can appear directly "
                    "inside col/row — put state changes inside a btn { } block",
                    s.line, s.col)
        return elems

    def nest_elems(self, head, body, ind, tail=""):
        """Attach a collection-for/if head to its element(s)."""
        if not body:
            return f"{head} const SizedBox.shrink(){tail}"
        if len(body) == 1:
            return f"{head} {body[0]}{tail}"
        joined = (",\n" + P(ind + 2)).join(body)
        return (f"{head} ...[\n{P(ind + 2)}{joined},\n"
                f"{P(ind + 1)}]{tail}")

    def widget_call(self, name, node, ind):
        args = [self.expr(a, ind, False) for a in node.args]
        inner_ind = ind + 2
        if name == "col" or name == "row":
            children = []
            if node.block:
                children = self.collection_elems(node.block.stmts, inner_ind + 1)
            widget = "Column" if name == "col" else "Row"
            if not children:
                return f"{widget}(children: const [])"
            kids = (",\n" + IND * (inner_ind + 1)).join(children)
            return (f"{widget}(\n"
                    f"{IND * (inner_ind)}children: [\n"
                    f"{IND * (inner_ind + 1)}{kids},\n"
                    f"{IND * inner_ind}],\n"
                    f"{IND * (ind + 1)})")
        if name == "text":
            label = args[0] if args else '""'
            extra = ""
            if len(args) >= 2 and args[1] != "null":
                style = f"fontSize: {args[1]}"
                if len(args) >= 3 and args[2] not in ("null", ""):
                    style += f", color: {dart_color(args[2].strip(chr(34)))}"
                extra = f",\n{IND * inner_ind}style: TextStyle({style})"
            return f"Text({label}{extra})"
        if name == "btn":
            label = args[0] if args else '"?"'
            style = ""
            if len(args) >= 2 and args[1] not in ("null", ""):
                style = (f"\n{IND * inner_ind}style: ElevatedButton.styleFrom("
                         f"backgroundColor: {dart_color(args[1].strip(chr(34)))}),")
            body = []
            if node.block:
                for s in node.block.stmts:
                    body.extend(self.stmt(s, inner_ind + 1))
            body_text = "\n".join(body) if body else f"{IND * (inner_ind + 1)}//"
            return (f"ElevatedButton(\n"
                    f"{IND * (inner_ind)}onPressed: () {{\n"
                    f"{IND * (inner_ind + 1)}setState(() {{\n"
                    f"{body_text}\n"
                    f"{IND * (inner_ind + 1)}}});\n"
                    f"{IND * inner_ind}}},\n"
                    f"{IND * (inner_ind)}child: Text({label}),{style}\n"
                    f"{IND * (ind + 1)})")
        if name == "bar":
            value = args[0] if args else "0"
            return (f"LinearProgressIndicator(\n"
                    f"{IND * (inner_ind)}value: ({value}).clamp(0.0, 1.0)"
                    f".toDouble(),\n"
                    f"{IND * (ind + 1)})")
        if name == "input":
            hint = args[0] if args else '""'
            return (f"TextField(\n"
                    f"{IND * (inner_ind)}decoration: InputDecoration("
                    f"border: const OutlineInputBorder(), "
                    f"hintText: {hint}),\n"
                    f"{IND * (ind + 1)})")
        if name == "img":
            src = args[0] if args else '""'
            return f"Image.network({src})"
        if name == "spacer":
            n = args[0] if args else "8"
            return f"SizedBox(height: {n})"
        raise KiteError(f"unknown widget '{name}'", node.line, node.col)


def transpile(program):
    return Transpiler().transpile(program)
