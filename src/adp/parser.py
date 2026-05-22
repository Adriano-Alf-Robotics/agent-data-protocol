"""ADP parser. Recursive-descent, zero dependencies.

Parses an ADP document into a Python dict.

Document syntax (v0.2):
    document    := pair (';' pair)* ';'?
    pair        := IDENT '=' value
    value       := primitive | string | bytes | list | map | table
    primitive   := integer | float | boolean | null
    boolean     := '1' | '0'
    null        := '~'
    integer     := -?[0-9]+         ;  use suffix 'i' to disambiguate 0/1 from bool
    float       := -?[0-9]+'.'[0-9]+ (e[+-]?[0-9]+)?
    string      := bare | quoted
    bare        := [A-Za-z_][A-Za-z0-9_.\\-/@+*?<>%():$]*
    quoted      := '"' (ESC | NON_QUOTE)* '"'
    ESC         := '\\"' | '\\\\'
    bytes       := 'b!' BASE64_CHARS
    list        := '[' (value (',' value)*)? ']'
    map         := '{' (entry (';' entry)*)? '}'
    entry       := IDENT '=' value
    table       := '#' header ('|' row)+
    header      := IDENT (',' IDENT)*
    row         := value (',' value)*

Public API:
    decode(s: str) -> dict
    ADPParseError
"""

from __future__ import annotations

import base64
import re
from typing import Any


class ADPParseError(ValueError):
    """Raised when an ADP document cannot be parsed."""


_SEPS = ",;]}|\n\r"  # characters that terminate a scalar token at top level / inside containers
_NUM_RE = re.compile(r"^-?\d+(\.\d+)?([eE][+-]?\d+)?$")
_BASE64_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")


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
            raise ADPParseError(
                f"expected {ch!r} at pos {self.pos} (got {self.s[self.pos : self.pos + len(ch)]!r})"
            )
        self.pos += len(ch)

    def _skip_ws(self) -> None:
        while self.pos < self.n and self.s[self.pos] in " \t\n\r":
            self.pos += 1

    def parse_document(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        self._skip_ws()
        if self.pos >= self.n:
            return out
        while True:
            name = self._parse_name()
            self._expect("=")
            value = self._parse_value()
            out[name] = value
            self._skip_ws()
            if self.pos >= self.n:
                return out
            if self._peek() == ";":
                self.pos += 1
                self._skip_ws()
                if self.pos >= self.n:
                    return out
                continue
            raise ADPParseError(
                f"expected ';' or end-of-input after value at pos {self.pos} (got {self._peek()!r})"
            )

    def _parse_name(self) -> str:
        start = self.pos
        while self.pos < self.n:
            c = self.s[self.pos]
            if c.isalnum() or c in "_-":
                self.pos += 1
            else:
                break
        if start == self.pos:
            raise ADPParseError(f"expected identifier at pos {self.pos}")
        return self.s[start : self.pos]

    def _parse_value(self) -> Any:
        if self.pos >= self.n:
            raise ADPParseError(f"unexpected EOF at pos {self.pos}")
        c = self.s[self.pos]
        if c == '"':
            return self._parse_quoted_string()
        if c == "[":
            return self._parse_list()
        if c == "{":
            return self._parse_map()
        if c == "#":
            return self._parse_table()
        # bytes prefix b!
        if c == "b" and self.s[self.pos : self.pos + 2] == "b!":
            return self._parse_bytes()
        return self._parse_scalar_or_bare()

    def _parse_quoted_string(self) -> str:
        self._expect('"')
        out: list[str] = []
        while self.pos < self.n:
            c = self.s[self.pos]
            if c == "\\":
                if self.pos + 1 >= self.n:
                    raise ADPParseError(f"dangling escape at pos {self.pos}")
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
        raise ADPParseError("unterminated quoted string")

    def _parse_bytes(self) -> bytes:
        self.pos += 2  # skip 'b!'
        start = self.pos
        while self.pos < self.n and self.s[self.pos] in _BASE64_CHARS:
            self.pos += 1
        b64 = self.s[start : self.pos]
        try:
            return base64.b64decode(b64.encode("ascii"), validate=True)
        except Exception as e:
            raise ADPParseError(f"invalid base64 at pos {start}: {e}")

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
            raise ADPParseError(f"expected ',' or ']' in list at pos {self.pos}")

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
            raise ADPParseError(f"expected ';' or '}}' in map at pos {self.pos}")

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
                raise ADPParseError(
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
    if _NUM_RE.match(tok):
        if "." in tok or "e" in tok or "E" in tok:
            return float(tok)
        return int(tok)
    return tok


def decode(s: str, *, key_lut: dict[str, str] | None = None) -> dict[str, Any]:
    """Decode an ADP document string into a Python dict.

    key_lut: same LUT used by the sender (encode). Keys are expanded back
    to their long form after parsing.

    Raises ADPParseError on malformed input.
    """
    out = _Parser(s).parse_document()
    if key_lut:
        from adp.lut import apply_decode, validate_lut
        validate_lut(key_lut)
        out = apply_decode(out, key_lut)
    return out
