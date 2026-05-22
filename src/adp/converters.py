"""Convertitori ADP <-> JSON e ADP -> Markdown.

JSON conversion handles bytes by base64-encoding them in a tagged string:
    {"_adp_bytes": "<base64>"} on output, recognized on input.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from adp.parser import decode
from adp.serializer import encode


_BYTES_TAG = "_adp_bytes"


def _bytes_to_json_safe(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {_BYTES_TAG: base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, dict):
        return {k: _bytes_to_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_bytes_to_json_safe(v) for v in value]
    return value


def _json_safe_to_bytes(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value.keys()) == {_BYTES_TAG} and isinstance(value[_BYTES_TAG], str):
            return base64.b64decode(value[_BYTES_TAG].encode("ascii"))
        return {k: _json_safe_to_bytes(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe_to_bytes(v) for v in value]
    return value


def to_json(s: str, *, indent: int | None = 2, ensure_ascii: bool = False) -> str:
    """Convert an ADP document into canonical JSON.

    Round-trip safe: from_json(to_json(adp)) == decode(adp).
    Bytes are encoded as {"_adp_bytes": "<base64>"} to preserve them losslessly.
    """
    obj = decode(s)
    obj = _bytes_to_json_safe(obj)
    return json.dumps(obj, indent=indent, ensure_ascii=ensure_ascii, sort_keys=False)


def from_json(s: str) -> str:
    """Convert a JSON string into an ADP document.

    Top-level JSON must be an object (mapping).
    Recognizes {"_adp_bytes": "<base64>"} as bytes payload.
    """
    obj = json.loads(s)
    if not isinstance(obj, dict):
        raise ValueError(
            "top-level JSON must be an object to convert to ADP"
        )
    obj = _json_safe_to_bytes(obj)
    return encode(obj)


def to_markdown(s: str) -> str:
    """Convert an ADP document into a human-readable Markdown string.

    One-way: not a round-trip. Markdown is for humans, not for re-parsing.
    """
    obj = decode(s)
    blocks: list[str] = []
    for name, value in obj.items():
        blocks.append(f"## {name}\n\n{_md_value(value, level=0)}".rstrip())
    return "\n\n".join(blocks) + "\n"


def _md_value(value: Any, *, level: int) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        b = bytes(value)
        b64 = base64.b64encode(b).decode("ascii")
        if len(b64) <= 64:
            return f"`<bytes {len(b)} B: {b64}>`"
        return f"`<bytes {len(b)} B: {b64[:48]}…>`"
    if isinstance(value, str):
        return _md_string(value)
    if isinstance(value, dict):
        return _md_dict(value, level=level)
    if isinstance(value, list):
        return _md_list(value, level=level)
    return repr(value)


def _md_string(s: str) -> str:
    if "\n" in s:
        return "```\n" + s + "\n```"
    return s


def _md_dict(d: dict[str, Any], *, level: int) -> str:
    if not d:
        return "_empty_"
    lines: list[str] = []
    indent = "  " * level
    for k, v in d.items():
        if isinstance(v, (dict, list)) and v:
            lines.append(f"{indent}- **{k}**:")
            lines.append(_md_value(v, level=level + 1))
        else:
            rendered = _md_value(v, level=level)
            if "\n" in rendered:
                lines.append(f"{indent}- **{k}**:")
                for ln in rendered.splitlines():
                    lines.append(f"{indent}  {ln}")
            else:
                lines.append(f"{indent}- **{k}**: {rendered}")
    return "\n".join(lines)


def _md_list(lst: list[Any], *, level: int) -> str:
    if not lst:
        return "_empty_"
    if _is_uniform_table(lst):
        return _md_table(lst)
    indent = "  " * level
    lines: list[str] = []
    for item in lst:
        rendered = _md_value(item, level=level + 1)
        if "\n" in rendered:
            lines.append(f"{indent}-")
            for ln in rendered.splitlines():
                lines.append(f"{indent}  {ln}")
        else:
            lines.append(f"{indent}- {rendered}")
    return "\n".join(lines)


def _is_uniform_table(lst: list[Any]) -> bool:
    if len(lst) < 1:
        return False
    if not all(isinstance(x, dict) for x in lst):
        return False
    first_keys = tuple(lst[0].keys())
    if not first_keys:
        return False
    for row in lst[1:]:
        if tuple(row.keys()) != first_keys:
            return False
    for row in lst:
        for v in row.values():
            if isinstance(v, (dict, list)):
                return False
    return True


def _md_table(lst: list[dict[str, Any]]) -> str:
    headers = list(lst[0].keys())
    head_line = "| " + " | ".join(headers) + " |"
    sep_line = "|" + "|".join(["---"] * len(headers)) + "|"
    rows = []
    for row in lst:
        cells = []
        for h in headers:
            v = row[h]
            if v is None:
                cells.append("—")
            elif isinstance(v, bool):
                cells.append("true" if v else "false")
            else:
                cells.append(str(v).replace("|", "\\|"))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([head_line, sep_line, *rows])
