"""GLA serializer. Python dict -> GLA document string.

Rules:
    - top-level must be a dict whose keys are valid GLA identifiers
    - bool -> '1' / '0'
    - int 0 / 1 -> '0i' / '1i' (disambiguates from bool); other ints bare
    - float -> always with decimal point
    - None -> '~'
    - str -> bare if matches identifier-like pattern AND not reserved, else quoted
    - list -> '[v,v,...]' OR table if homogeneous list of dicts
    - dict -> '{k=v;k=v}'
"""

from __future__ import annotations

import re
from typing import Any


_BARE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
_RESERVED_STRINGS = {"~", "1", "0", "1i", "0i"}


def encode(obj: dict[str, Any], *, prefer_tables: bool = True) -> str:
    """Encode a Python dict into a GLA document string.

    Top-level must be a dict with identifier-compatible keys.
    """
    if not isinstance(obj, dict):
        raise TypeError(
            f"encode requires a dict at top level, got {type(obj).__name__}"
        )
    parts: list[str] = []
    for k, v in obj.items():
        _check_ident(k)
        parts.append(f"&{k}:{_encode_value(v, prefer_tables=prefer_tables)}&")
    return "".join(parts)


def _check_ident(name: str) -> None:
    if not _IDENT_RE.match(name):
        raise ValueError(
            f"invalid GLA identifier: {name!r} (must match [A-Za-z_][A-Za-z0-9_-]*)"
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
        return _encode_as_table(lst, prefer_tables=prefer_tables)
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
    for row in lst:
        for v in row.values():
            if isinstance(v, (dict, list, tuple)):
                return False
    return True


def _encode_as_table(lst: list[dict[str, Any]], *, prefer_tables: bool) -> str:
    headers = list(lst[0].keys())
    head_str = ",".join(headers)
    row_strs: list[str] = []
    for row in lst:
        cells = [_encode_value(row[h], prefer_tables=prefer_tables) for h in headers]
        row_strs.append(",".join(cells))
    return "#" + head_str + "|" + "|".join(row_strs)
