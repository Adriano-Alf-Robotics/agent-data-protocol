"""ADP serializer. Python dict -> ADP document string.

Rules (v0.2):
    - top-level dict is rendered as 'k=v;k=v' (no & wrappers)
    - bool -> '1' / '0'
    - int 0 / 1 -> '0i' / '1i' (disambiguates from bool); other ints bare
    - float -> always with decimal point
    - None -> '~'
    - bytes -> 'b!' + base64
    - str -> bare if matches ample identifier-like pattern AND not reserved/numeric;
             else quoted ('"..."', only \\" and \\\\ escaped, newlines literal)
    - list -> '[v,v,...]' OR table if homogeneous list of dicts
    - dict -> '{k=v;k=v}'
"""

from __future__ import annotations

import base64
import re
from typing import Any


# Ample bare-string set: alphanumerics + safe punctuation that doesn't collide
# with any ADP delimiter (& : ; , = [ ] { } | " # ~) or with numeric prefixes.
# Start char restricted to [A-Za-z_] to avoid ambiguity with numbers.
_BARE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-/@+*?<>%():$]*$")
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
_NUM_RE = re.compile(r"^-?\d+(\.\d+)?([eE][+-]?\d+)?$")
_RESERVED_STRINGS = {"~", "1", "0", "1i", "0i"}


def encode(
    obj: dict[str, Any],
    *,
    prefer_tables: bool = True,
    key_lut: dict[str, str] | None = None,
) -> str:
    """Encode a Python dict into an ADP document string.

    Top-level must be a dict with identifier-compatible keys.

    key_lut: optional mapping {long_name: short_alias} that renames keys
    recursively before encoding. Sender and receiver must share the same
    LUT. See adp.lut for helpers and DEFAULT_AGENT_LUT.
    """
    if not isinstance(obj, dict):
        raise TypeError(
            f"encode requires a dict at top level, got {type(obj).__name__}"
        )
    if key_lut:
        from adp.lut import apply_encode, validate_lut
        validate_lut(key_lut)
        obj = apply_encode(obj, key_lut)
    parts: list[str] = []
    for k, v in obj.items():
        _check_ident(k)
        parts.append(f"{k}={_encode_value(v, prefer_tables=prefer_tables)}")
    return ";".join(parts)


def _check_ident(name: str) -> None:
    if not _IDENT_RE.match(name):
        raise ValueError(
            f"invalid ADP identifier: {name!r} (must match [A-Za-z_][A-Za-z0-9_-]*)"
        )


def _encode_value(v: Any, *, prefer_tables: bool) -> str:
    if v is None:
        return "~"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        if v == 0:
            return "0i"
        if v == 1:
            return "1i"
        return str(v)
    if isinstance(v, float):
        s = repr(v)
        if "." not in s and "e" not in s and "n" not in s:
            s += ".0"
        return s
    if isinstance(v, (bytes, bytearray, memoryview)):
        return "b!" + base64.b64encode(bytes(v)).decode("ascii")
    if isinstance(v, str):
        return _encode_string(v)
    if isinstance(v, dict):
        return _encode_map(v, prefer_tables=prefer_tables)
    if isinstance(v, (list, tuple)):
        return _encode_list(list(v), prefer_tables=prefer_tables)
    raise TypeError(f"cannot encode value of type {type(v).__name__}: {v!r}")


def _encode_string(s: str) -> str:
    if s == "":
        return '""'
    if s in _RESERVED_STRINGS:
        return _quote(s)
    if _NUM_RE.match(s):
        return _quote(s)
    if _BARE_RE.match(s):
        return s
    return _quote(s)


def _quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _encode_map(d: dict[str, Any], *, prefer_tables: bool) -> str:
    if not d:
        return "{}"
    items: list[str] = []
    for k, v in d.items():
        _check_ident(k)
        items.append(f"{k}={_encode_value(v, prefer_tables=prefer_tables)}")
    return "{" + ";".join(items) + "}"


def _encode_list(lst: list[Any], *, prefer_tables: bool) -> str:
    if not lst:
        return "[]"
    if prefer_tables and _is_table_candidate(lst):
        return _encode_as_table(lst)
    return "[" + ",".join(_encode_value(v, prefer_tables=prefer_tables) for v in lst) + "]"


def _is_table_candidate(lst: list[Any]) -> bool:
    if len(lst) < 2:
        return False
    if not all(isinstance(x, dict) for x in lst):
        return False
    first_keys = tuple(lst[0].keys())
    if not first_keys:
        return False
    for k in first_keys:
        if not _IDENT_RE.match(k):
            return False
    for row in lst[1:]:
        if tuple(row.keys()) != first_keys:
            return False
    return True


def _encode_as_table(lst: list[dict[str, Any]]) -> str:
    headers = list(lst[0].keys())
    head_str = ",".join(headers)
    row_strs: list[str] = []
    for row in lst:
        cells = [_encode_value(row[h], prefer_tables=False) for h in headers]
        row_strs.append(",".join(cells))
    return "#" + head_str + "|" + "|".join(row_strs)
