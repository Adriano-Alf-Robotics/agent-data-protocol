"""GLA parser. Recursive-descent, zero dependencies.

Parses a GLA document (sequence of `&name:value&` records) into a Python dict.

Public API:
    decode(s: str) -> dict
    GLAParseError
"""

from __future__ import annotations

from typing import Any


class GLAParseError(ValueError):
    """Raised when a GLA document cannot be parsed."""


_SEPS = ",;]}|&\n\r"


class _Parser:
    __slots__ = ("s", "pos", "n")

    def __init__(self, s: str) -> None:
        self.s = s
        self.pos = 0
        self.n = len(s)

    def _peek(self, k: int = 1) -> str:
        return self.s[self.pos : self.pos + k]

    def _expect(self, ch: str) -> None:
        if self.s[self.pos : self.pos + len(ch)] != ch:
            raise GLAParseError(
                f"expected {ch!r} at pos {self.pos} (got {self.s[self.pos : self.pos + len(ch)]!r})"
            )
        self.pos += len(ch)

    def _skip_ws(self) -> None:
        while self.pos < self.n and self.s[self.pos] in " \t\n\r":
            self.pos += 1

    def parse_document(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        self._skip_ws()
        while self.pos < self.n:
            name, value = self._parse_record()
            out[name] = value
            self._skip_ws()
        return out

    def _parse_record(self) -> tuple[str, Any]:
        self._expect("&")
        name = self._parse_name()
        self._expect(":")
        value = self._parse_value()
        self._expect("&")
        return name, value

    def _parse_name(self) -> str:
        start = self.pos
        while self.pos < self.n:
            c = self.s[self.pos]
            if c.isalnum() or c in "_-":
                self.pos += 1
            else:
                break
        if start == self.pos:
            raise GLAParseError(f"expected identifier at pos {self.pos}")
        return self.s[start : self.pos]

    def _parse_value(self) -> Any:
        if self.pos >= self.n:
            raise GLAParseError(f"unexpected EOF at pos {self.pos}")
        c = self.s[self.pos]
        if c == '"':
            return self._parse_quoted_string()
        if c == "[":
            return self._parse_list()
        if c == "{":
            return self._parse_map()
        if c == "#":
            return self._parse_table()
        return self._parse_scalar_or_bare()

    def _parse_quoted_string(self) -> str:
        self._expect('"')
        out: list[str] = []
        while self.pos < self.n:
            c = self.s[self.pos]
            if c == "\\":
                if self.pos + 1 >= self.n:
                    raise GLAParseError(f"dangling escape at pos {self.pos}")
                nxt = self.s[self.pos + 1]
                if nxt == '"':
                    out.append('"')
                elif nxt == "\\":
                    out.append("\\")
                else:
                    out.append(nxt)
                self.pos += 2
            elif c == '"':
                self.pos += 1
                return "".join(out)
            else:
                out.append(c)
                self.pos += 1
        raise GLAParseError("unterminated quoted string")

    def _parse_list(self) -> list[Any]:
        self._expect("[")
        out: list[Any] = []
        if self._peek() == "]":
            self.pos += 1
            return out
        while True:
            out.append(self._parse_value())
            c = self._peek()
            if c == ",":
                self.pos += 1
                continue
            if c == "]":
                self.pos += 1
                return out
            raise GLAParseError(f"expected ',' or ']' in list at pos {self.pos}")

    def _parse_map(self) -> dict[str, Any]:
        self._expect("{")
        out: dict[str, Any] = {}
        if self._peek() == "}":
            self.pos += 1
            return out
        while True:
            name = self._parse_name()
            self._expect("=")
            value = self._parse_value()
            out[name] = value
            c = self._peek()
            if c == ";":
                self.pos += 1
                continue
            if c == "}":
                self.pos += 1
                return out
            raise GLAParseError(f"expected ';' or '}}' in map at pos {self.pos}")

    def _parse_table(self) -> list[dict[str, Any]]:
        self._expect("#")
        headers: list[str] = [self._parse_name()]
        while self._peek() == ",":
            self.pos += 1
            headers.append(self._parse_name())
        rows: list[dict[str, Any]] = []
        while self._peek() == "|":
            self.pos += 1
            row_vals: list[Any] = [self._parse_value()]
            while self._peek() == ",":
                self.pos += 1
                row_vals.append(self._parse_value())
            if len(row_vals) != len(headers):
                raise GLAParseError(
                    f"row width {len(row_vals)} != header width {len(headers)} at pos {self.pos}"
                )
            rows.append(dict(zip(headers, row_vals)))
        return rows

    def _parse_scalar_or_bare(self) -> Any:
        start = self.pos
        while self.pos < self.n and self.s[self.pos] not in _SEPS:
            self.pos += 1
        tok = self.s[start : self.pos]
        return _interpret_token(tok)


def _interpret_token(tok: str) -> Any:
    if tok == "":
        return ""
    if tok == "~":
        return None
    if tok == "1":
        return True
    if tok == "0":
        return False
    if tok == "1i":
        return 1
    if tok == "0i":
        return 0
    try:
        return int(tok)
    except ValueError:
        pass
    try:
        return float(tok)
    except ValueError:
        pass
    return tok


def decode(s: str) -> dict[str, Any]:
    """Decode a GLA document string into a Python dict.

    Raises GLAParseError on malformed input.
    """
    return _Parser(s).parse_document()
