"""Kite command-line interface.

Usage:
  python -m kite run <file.kite>       interpret
  python -m kite build <file.kite>     compile to Dart/Flutter
  python -m kite ast <file.kite>       print parse tree
"""

import sys
import os

from .lexer import KiteError
from .parser import parse
from .interp import run_program
from .transpile import transpile


def read_source(path):
    if not os.path.exists(path):
        print(f"kite: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return f.read()


def dump_ast(node, indent=0):
    pad = "  " * indent
    label = type(node).__name__
    details = []
    for attr in ("name", "value", "op", "var", "params"):
        v = getattr(node, attr, None)
        if isinstance(v, (str, int, float, bool)):
            details.append(f"{attr}={v!r}")
    line = f"{pad}{label}"
    if details:
        line += " " + " ".join(details)
    print(line)
    for attr in vars(node):
        v = getattr(node, attr)
        if isinstance(v, list):
            for item in v:
                if hasattr(item, "__dataclass_fields__"):
                    dump_ast(item, indent + 1)
                elif isinstance(item, tuple):
                    for x in item:
                        if hasattr(x, "__dataclass_fields__"):
                            dump_ast(x, indent + 1)
        elif hasattr(v, "__dataclass_fields__"):
            dump_ast(v, indent + 1)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    cmd = argv[0]
    if cmd not in ("run", "build", "ast", "check"):
        print(f"kite: unknown command '{cmd}'", file=sys.stderr)
        return 1
    if len(argv) < 2:
        print(f"kite: {cmd} needs a .kite file", file=sys.stderr)
        return 1
    path = argv[1]
    src = read_source(path)
    try:
        program = parse(src)
        if cmd == "ast":
            dump_ast(program)
            return 0
        if cmd == "run":
            run_program(program)
            return 0
        if cmd == "check":
            print(f"{path}: OK")
            return 0
        if cmd == "build":
            dart = transpile(program)
            out = None
            if "-o" in argv:
                out = argv[argv.index("-o") + 1]
            elif len(argv) > 2 and not argv[2].startswith("-"):
                out = argv[2]
            else:
                base = os.path.splitext(os.path.basename(path))[0]
                out = base + ".dart"
            with open(out, "w", encoding="utf-8") as f:
                f.write(dart)
            print(f"wrote {out}")
            print("next: put it in a Flutter project as lib/main.dart "
                  "and run `flutter run`")
            return 0
    except KiteError as e:
        print(f"{path}: error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
