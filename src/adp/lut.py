"""LUT (Look-Up Table) — sigle condivise tra agenti per chiavi ricorrenti.

Un agente può condividere una LUT con un altro per ridurre i token su
nomi di campo ripetuti. La LUT mappa nome lungo → sigla.

Esempio:
    LUT = {"user": "u", "id": "i", "name": "n", "email": "e"}
    adp.encode({"user": {"id": 42, "name": "Adriano", "email": "a@b.c"}}, key_lut=LUT)
    # u={i=42;n=Adriano;e=a@b.c}        (vs user={id=42;...} senza LUT)

    adp.decode(s, key_lut=LUT)
    # {"user": {"id": 42, "name": "Adriano", "email": "a@b.c"}}

La LUT è applicata ricorsivamente a tutti i dizionari (mappe + cells di
tabella). Le chiavi non presenti in LUT restano invariate.

DEFAULT_AGENT_LUT è una LUT pre-confezionata per nomi tipici nei
messaggi inter-agente. Le sigle scelte sono identificatori validi e
non collidono con i letterali riservati ADP (~, 0, 1, 0i, 1i).
"""

from __future__ import annotations

import re
from typing import Any


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
_RESERVED = {"~", "1", "0", "1i", "0i"}


DEFAULT_AGENT_LUT: dict[str, str] = {
    # message envelope
    "msg_id": "mi",
    "from_agent": "fa",
    "to_agent": "ta",
    "intent": "it",
    "action": "ac",
    "reply_to": "rt",
    "timestamp": "ts",
    # generic content
    "id": "i",
    "name": "nm",
    "type": "ty",
    "status": "st",
    "role": "r",
    "roles": "rs",
    "error": "er",
    "message": "ms",
    "content": "ct",
    "data": "d",
    "result": "rl",
    "value": "v",
    "payload": "pl",
    "items": "im",
    "items_count": "ic",
    "key": "k",
    "code": "cd",
    "ok": "o",
    "active": "ac2",
    "description": "ds",
    "category": "ca",
    "tags": "tg",
    # task related
    "task_id": "ti",
    "step": "sp",
    "tool": "tl",
    "command": "cm",
    "timeout_s": "to",
    "context": "cx",
    "constraints": "cs",
    "previous_outputs": "po",
    "expected_reply": "ex",
    # user/contact
    "user": "u",
    "users": "us",
    "email": "em",
    "url": "ur",
    "phone": "ph",
    "country": "co",
    "homepage": "hp",
    # tabular common
    "department": "dp",
    "salary": "sl",
    # data shapes
    "metrics": "mt",
    "unit": "un",
    "report": "rp",
}


def validate_lut(lut: dict[str, str]) -> None:
    """Validate a LUT: keys/values are valid identifiers, no collisions."""
    sigle: set[str] = set()
    for k, v in lut.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ValueError(f"LUT keys and values must be strings: {k!r} -> {v!r}")
        if not _IDENT_RE.match(k):
            raise ValueError(f"LUT key {k!r} is not a valid identifier")
        if not _IDENT_RE.match(v):
            raise ValueError(f"LUT alias {v!r} is not a valid identifier")
        if v in _RESERVED:
            raise ValueError(f"LUT alias {v!r} collides with reserved literal")
        if v in sigle:
            raise ValueError(f"duplicate LUT alias {v!r}")
        sigle.add(v)


def apply_encode(obj: Any, lut: dict[str, str]) -> Any:
    """Recursively replace dict keys using the LUT before encoding."""
    if isinstance(obj, dict):
        return {lut.get(k, k): apply_encode(v, lut) for k, v in obj.items()}
    if isinstance(obj, list):
        return [apply_encode(v, lut) for v in obj]
    if isinstance(obj, tuple):
        return tuple(apply_encode(v, lut) for v in obj)
    return obj


def apply_decode(obj: Any, lut: dict[str, str]) -> Any:
    """Recursively replace dict keys after decoding, using the inverted LUT."""
    inv = {v: k for k, v in lut.items()}
    return _apply_with(obj, inv)


def _apply_with(obj: Any, inv: dict[str, str]) -> Any:
    if isinstance(obj, dict):
        return {inv.get(k, k): _apply_with(v, inv) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_apply_with(v, inv) for v in obj]
    return obj
