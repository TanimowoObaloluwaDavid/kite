"""Tests for the Kite language. Run: python -m pytest tests/ -q  (or python tests/test_kite.py)"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kite.lexer import tokenize, KiteError
from kite.parser import parse
from kite.interp import run_program, Interpreter, fmt
from kite.transpile import transpile


def run(src, capture=None):
    """Run source, return list of printed lines."""
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        run_program(parse(src))
    return buf.getvalue().splitlines()


def test_lexer_basic():
    toks = tokenize("set x = 42")
    assert [t.type for t in toks] == ["KW", "ID", "OP", "NUM", "EOF"]
    assert toks[3].value == 42


def test_lexer_string_escapes():
    toks = tokenize(r'"a\nb"')
    assert toks[0].value == "a\nb"


def test_arithmetic():
    assert run("print(1 + 2 * 3)") == ["7"]
    assert run("print((1 + 2) * 3)") == ["9"]
    assert run("print(10 / 4)") == ["2.5"]
    assert run("print(10 % 3)") == ["1"]
    assert run("print(-5 + 2)") == ["-3"]


def test_strings():
    assert run('print("hi " + "there")') == ["hi there"]
    assert run('set n = 3\nprint("n is {n}")') == ["n is 3"]
    assert run('print("sum: {1 + 2}")') == ["sum: 3"]


def test_variables():
    assert run("set x = 5\nx += 3\nprint(x)") == ["8"]
    assert run("fix pi = 3\nprint(pi)") == ["3"]


def test_fix_immutable():
    try:
        run("fix x = 1\nx = 2")
        assert False, "should have raised"
    except KiteError as e:
        assert "constant" in str(e)


def test_functions():
    src = """
    make add(a, b) {
      ret a + b
    }
    print(add(2, 3))
    """
    assert run(src) == ["5"]


def test_closures_and_lambda():
    src = """
    set makeAdder = make(n) {
      ret make(x) { ret x + n }
    }
    set add5 = makeAdder(5)
    print(add5(10))
    """
    assert run(src) == ["15"]


def test_when_else():
    assert run("set x = 7\nwhen x > 5 { print(\"big\") } else { print(\"small\") }") == ["big"]
    assert run("set x = 1\nwhen x > 5 { print(\"big\") } else { print(\"small\") }") == ["small"]


def test_when_elif():
    src = """
    set x = 5
    when x > 10 { print("a") }
    else when x > 3 { print("b") }
    else { print("c") }
    """
    assert run(src) == ["b"]


def test_while_loop():
    assert run("set i = 0\nwhile i < 3 { i += 1 }\nprint(i)") == ["3"]


def test_each_list():
    assert run("each x in [1, 2, 3] { print(x) }") == ["1", "2", "3"]


def test_each_range():
    assert run("each i in 0..4 { print(i) }") == ["0", "1", "2", "3"]


def test_break_continue():
    src = """
    each i in 0..10 {
      when i == 2 { continue }
      when i == 5 { break }
      print(i)
    }
    """
    assert run(src) == ["0", "1", "3", "4"]


def test_lists():
    assert run('set l = [1, 2]\nl.push(3)\nprint(l)') == ["[1, 2, 3]"]
    assert run('print([1, 2, 3][1])') == ["2"]
    assert run('print(len([1, 2, 3]))') == ["3"]
    assert run('print([1, 2].contains(2))') == ["true"]


def test_maps():
    src = """
    set m = #{a: 1, b: 2}
    print(m.a)
    print(m["b"])
    m.c = 3
    print(len(m))
    """
    assert run(src) == ["1", "2", "3"]


def test_string_methods():
    assert run('print("hi".upper())') == ["HI"]
    assert run('print("A B".split(" ")[0])') == ["A"]
    assert run('print(" x ".trim())') == ["x"]


def test_logic_ops():
    assert run("print(true and false)") == ["false"]
    assert run("print(true or false)") == ["true"]
    assert run("print(not true)") == ["false"]
    assert run("print(1 is 1)") == ["true"]
    assert run('print("a" isnt "b")') == ["true"]


def test_nested_functions():
    src = """
    make outer() {
      make inner() { ret 42 }
      ret inner()
    }
    print(outer())
    """
    assert run(src) == ["42"]


def test_errors_have_lines():
    try:
        parse("set x = \n")
        assert False
    except KiteError as e:
        assert e.line >= 1


def test_undefined_var():
    try:
        run("print(nope)")
        assert False
    except KiteError as e:
        assert "undefined" in str(e)


def test_transpile_counter():
    src = open(os.path.join(os.path.dirname(__file__), "..",
                            "examples", "counter.kite"), encoding="utf-8").read()
    dart = transpile(parse(src))
    assert "class Counter extends StatefulWidget" in dart
    assert "void main()" in dart
    assert "ElevatedButton" in dart
    assert "setState" in dart


def test_transpile_script_requires_app():
    src = 'print("hi")'
    try:
        transpile(parse(src))
        assert False
    except KiteError as e:
        assert "app" in str(e)


def test_transpile_snippet():
    src = """
    app A {
      state n = 0
      screen {
        col {
          text("n is {n}")
          btn("Go") { n += 1 }
        }
      }
    }
    """
    dart = transpile(parse(src))
    assert "var n = 0;" in dart
    assert "Text(" in dart
    assert "n += 1" in dart


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in fns:
        try:
            fn()
            passed += 1
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
