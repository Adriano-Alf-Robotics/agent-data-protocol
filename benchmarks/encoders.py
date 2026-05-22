"""Encoder/decoder adapters for all benchmarked formats.

Each encoder returns the textual representation (str). Binary formats are
base64-encoded so they can be transferred as text and counted as tokens —
this reflects how an LLM would actually receive them.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import xml.etree.ElementTree as ET
from typing import Any, Callable

import msgpack
import tomli_w
import yaml

from adp import encode as adp_encode, decode as adp_decode, DEFAULT_AGENT_LUT


# ---------- ADP ----------

def gla_enc(obj: dict[str, Any]) -> str:
    return adp_encode(obj)


def gla_dec(s: str) -> dict[str, Any]:
    return adp_decode(s)


# ---------- ADP + LUT ----------

def adp_lut_enc(obj: dict[str, Any]) -> str:
    return adp_encode(obj, key_lut=DEFAULT_AGENT_LUT)


def adp_lut_dec(s: str) -> dict[str, Any]:
    return adp_decode(s, key_lut=DEFAULT_AGENT_LUT)


# ---------- JSON ----------

def json_min_enc(obj: dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def json_pretty_enc(obj: dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def json_dec(s: str) -> dict[str, Any]:
    return json.loads(s)


# ---------- YAML ----------

def yaml_enc(obj: dict[str, Any]) -> str:
    return yaml.safe_dump(obj, allow_unicode=True, default_flow_style=False, sort_keys=False)


def yaml_dec(s: str) -> dict[str, Any]:
    return yaml.safe_load(s)


# ---------- TOML ----------
# TOML cannot represent every JSON structure (lists of mixed types, null).
# We test it only where it works and mark unsupported elsewhere.

def toml_enc(obj: dict[str, Any]) -> str:
    return tomli_w.dumps(obj)


def toml_dec(s: str) -> dict[str, Any]:
    # Python 3.11+ has tomllib in stdlib
    import tomllib
    return tomllib.loads(s)


# ---------- MessagePack (base64 for text channel) ----------

def msgpack_b64_enc(obj: dict[str, Any]) -> str:
    binary = msgpack.packb(obj, use_bin_type=True)
    return base64.b64encode(binary).decode("ascii")


def msgpack_b64_dec(s: str) -> dict[str, Any]:
    binary = base64.b64decode(s.encode("ascii"))
    return msgpack.unpackb(binary, raw=False)


# ---------- XML (best-effort) ----------

def xml_enc(obj: dict[str, Any]) -> str:
    root = ET.Element("root")
    _xml_build(root, obj)
    return ET.tostring(root, encoding="unicode")


def _xml_build(parent: ET.Element, value: Any) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            safe_k = k if k[0].isalpha() else f"_{k}"
            child = ET.SubElement(parent, safe_k)
            _xml_build(child, v)
    elif isinstance(value, list):
        for item in value:
            child = ET.SubElement(parent, "item")
            _xml_build(child, item)
    elif value is None:
        parent.set("nil", "true")
    else:
        parent.text = str(value)


def xml_dec(s: str) -> dict[str, Any]:
    # Best-effort: not lossless for general structure.
    raise NotImplementedError("XML decode not implemented (best-effort encoder only)")


# ---------- CSV (only flat tabular) ----------

def csv_enc(obj: dict[str, Any]) -> str:
    if len(obj) != 1:
        raise ValueError("CSV needs exactly one top-level key with a list of rows")
    rows = next(iter(obj.values()))
    if not (isinstance(rows, list) and rows and all(isinstance(r, dict) for r in rows)):
        raise ValueError("CSV needs a list of dicts")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue()


def csv_dec(s: str) -> dict[str, Any]:
    reader = csv.DictReader(io.StringIO(s))
    rows = list(reader)
    return {"rows": rows}


# ---------- registry ----------

FormatSpec = tuple[
    str,                              # display name
    Callable[[dict[str, Any]], str],  # encoder
    Callable[[str], dict[str, Any]] | None,  # decoder (None if not implemented)
    bool,                             # lossless?
]


def all_formats() -> list[FormatSpec]:
    return [
        ("ADP",            gla_enc,         gla_dec,         True),
        ("ADP+LUT",        adp_lut_enc,     adp_lut_dec,     True),
        ("JSON-min",       json_min_enc,    json_dec,        True),
        ("JSON-pretty",    json_pretty_enc, json_dec,        True),
        ("YAML",           yaml_enc,        yaml_dec,        True),
        ("TOML",           toml_enc,        toml_dec,        True),
        ("MsgPack-b64",    msgpack_b64_enc, msgpack_b64_dec, True),
        ("XML",            xml_enc,         None,            False),
        ("CSV",            csv_enc,         csv_dec,         False),
    ]
