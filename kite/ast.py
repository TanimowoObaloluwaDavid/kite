"""Kite AST node definitions."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Node:
    line: int = 0
    col: int = 0


# --- expressions ---

@dataclass
class Num(Node):
    value: float = 0


@dataclass
class Str(Node):
    value: str = ""


@dataclass
class StrInterp(Node):
    parts: list = field(default_factory=list)  # str | Node


@dataclass
class Bool(Node):
    value: bool = False


@dataclass
class Nil(Node):
    pass


@dataclass
class Ident(Node):
    name: str = ""


@dataclass
class ListLit(Node):
    items: list = field(default_factory=list)


@dataclass
class MapLit(Node):
    entries: list = field(default_factory=list)  # (key, Node)


@dataclass
class Binary(Node):
    op: str = ""
    left: Node = None
    right: Node = None


@dataclass
class Unary(Node):
    op: str = ""
    operand: Node = None


@dataclass
class Call(Node):
    callee: Node = None
    args: list = field(default_factory=list)
    block: Optional["Block"] = None


@dataclass
class Index(Node):
    obj: Node = None
    index: Node = None


@dataclass
class Attr(Node):
    obj: Node = None
    name: str = ""


@dataclass
class Make(Node):
    params: list = field(default_factory=list)
    body: "Block" = None
    name: Optional[str] = None


# --- statements ---

@dataclass
class Block(Node):
    stmts: list = field(default_factory=list)


@dataclass
class Set(Node):
    name: str = ""
    value: Node = None


@dataclass
class Fix(Node):
    name: str = ""
    value: Node = None


@dataclass
class Assign(Node):
    target: Node = None
    op: str = "="
    value: Node = None


@dataclass
class When(Node):
    cond: Node = None
    then: Block = None
    other: Optional[Node] = None  # Block | When


@dataclass
class While(Node):
    cond: Node = None
    body: Block = None


@dataclass
class Each(Node):
    var: str = ""
    iterable: Node = None
    body: Block = None


@dataclass
class Ret(Node):
    value: Optional[Node] = None


@dataclass
class Break(Node):
    pass


@dataclass
class Continue(Node):
    pass


@dataclass
class ExprStmt(Node):
    expr: Node = None


@dataclass
class State(Node):
    name: str = ""
    value: Node = None


@dataclass
class Screen(Node):
    body: Block = None
    name: str = ""


@dataclass
class Goto(Node):
    target: str = ""


@dataclass
class App(Node):
    name: str = ""
    members: list = field(default_factory=list)  # State | Screen | fun/set decls


@dataclass
class Program(Node):
    stmts: list = field(default_factory=list)
