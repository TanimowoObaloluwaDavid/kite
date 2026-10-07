"""Kite lexer: source text -> tokens."""

from dataclasses import dataclass


class KiteError(Exception):
    def __init__(self, msg, line=0, col=0):
        self.msg, self.line, self.col = msg, line, col
        super().__init__(f"[line {line}:{col}] {msg}")


KEYWORDS = {
    "set", "fix", "make", "ret", "when", "else", "while", "each", "in",
    "break", "continue", "and", "or", "not", "is", "isnt", "nil",
    "true", "false", "app", "state", "screen", "goto",
}

TWO_CHAR = {"+=", "-=", "*=", "/=", "==", "!=", "<=", ">=", ".."}
ONE_CHAR = set("+-*/%=<>()[],.:")


@dataclass
class Token:
    type: str   # NUM STR ID KW OP LBRACE RBRACE LBRACKET RBRACKET EOF
    value: object
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type},{self.value!r})"


def tokenize(src):
    tokens, i, line, col = [], 0, 1, 1
    n = len(src)

    def peek(k=0):
        return src[i + k] if i + k < n else ""

    def emit(type_, value, tline, tcol):
        tokens.append(Token(type_, value, tline, tcol))

    while i < n:
        c = src[i]
        if c == "\n":
            i += 1
            line += 1
            col = 1
            continue
        if c in " \t\r":
            i += 1
            col += 1
            continue
        if c == "/" and peek(1) == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c == "/" and peek(1) == "*":
            start_line, start_col = line, col
            i += 2
            col += 2
            while i < n and not (src[i] == "*" and peek(1) == "/"):
                if src[i] == "\n":
                    line += 1
                    col = 1
                else:
                    col += 1
                i += 1
            if i >= n:
                raise KiteError("unterminated block comment", start_line, start_col)
            i += 2
            col += 2
            continue
        if c == "#":
            if peek(1) == "{":
                emit("MAPSTART", "#{", line, col)
                i += 2
                col += 2
                continue
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c.isdigit() or (c == "." and peek(1).isdigit()):
            j = i
            while j < n and (src[j].isdigit() or src[j] == "."):
                if src[j] == "." and not (src[j + 1].isdigit() if j + 1 < n else False):
                    break
                j += 1
            text = src[i:j]
            if text.count(".") > 1:
                raise KiteError(f"bad number '{text}'", line, col)
            value = float(text) if "." in text else int(text)
            emit("NUM", value, line, col)
            col += j - i
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            word = src[i:j]
            emit("KW" if word in KEYWORDS else "ID", word, line, col)
            col += j - i
            i = j
            continue
        if c == '"':
            tline, tcol = line, col
            i += 1
            col += 1
            buf = []
            while i < n and src[i] != '"':
                if src[i] == "\n":
                    raise KiteError("unterminated string", tline, tcol)
                if src[i] == "\\" and i + 1 < n:
                    esc = src[i + 1]
                    mapped = {"n": "\n", "t": "\t", '"': '"', "\\": "\\",
                              "{": "\x00{", "}": "\x00}"}.get(esc, esc)
                    buf.append(mapped)
                    i += 2
                    col += 2
                    continue
                buf.append(src[i])
                i += 1
                col += 1
            if i >= n:
                raise KiteError("unterminated string", tline, tcol)
            i += 1
            col += 1
            emit("STR", "".join(buf), tline, tcol)
            continue
        two = src[i:i + 2]
        if two in TWO_CHAR:
            emit("OP", two, line, col)
            i += 2
            col += 2
            continue
        if c in "()":
            emit("LP" if c == "(" else "RP", c, line, col)
        elif c in "[":
            emit("LBRACKET", c, line, col)
        elif c in "]":
            emit("RBRACKET", c, line, col)
        elif c == "{":
            emit("LBRACE", c, line, col)
        elif c == "}":
            emit("RBRACE", c, line, col)
        elif c in ONE_CHAR:
            emit("OP", c, line, col)
        else:
            raise KiteError(f"unexpected character {c!r}", line, col)
        i += 1
        col += 1

    tokens.append(Token("EOF", None, line, col))
    return tokens
