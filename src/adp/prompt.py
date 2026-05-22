"""System prompt + few-shot examples for instructing LLM agents on ADP."""

from __future__ import annotations

from typing import Any


SYSTEM_PROMPT = """You communicate with other AI agents using ADP — a token-efficient lossless format. ALWAYS reply in ADP. Never wrap in code fences. Never explain syntax.

ADP SYNTAX (strict, v0.2):
- Document = pairs separated by ';' :  name=value;name=value;name=value
- name = identifier: [A-Za-z_][A-Za-z0-9_-]*
- Primitives:
    integer  : 42, -7
    float    : 3.14, -0.5, 1.0e3
    boolean  : 1 = true, 0 = false
    null     : ~
    int 0/1  : use 0i / 1i to disambiguate from boolean
- Strings:
    bare (no quotes) when matches [A-Za-z_][A-Za-z0-9_.\\-/@+*?<>%()$]*
    quoted: "..."  -- escape only \\" and \\\\  -- newlines inside the quotes are literal (no \\n needed)
- Bytes: b!<base64>   (standard alphabet; example: b!aGVsbG8=)
- List: [v,v,v]      (empty: [])
- Map:  {k=v;k=v}    (empty: {})
- Table for homogeneous list of dicts: #h1,h2,h3|r1c1,r1c2,r1c3|r2c1,r2c2,r2c3
    Cells may be primitives, strings, lists, or maps (no nested table inside a cell).
- No whitespace required between tokens; only inside quoted strings.
"""


_FEW_SHOT_PAIRS: list[tuple[dict[str, Any], str]] = [
    (
        {"user": {"id": 42, "name": "Adriano", "active": True}},
        "user={id=42;name=Adriano;active=1}",
    ),
    (
        {"tags": ["admin", "root", "user con spazio"]},
        'tags=[admin,root,"user con spazio"]',
    ),
    (
        {
            "metrics": [
                {"id": 1, "value": 42.0, "unit": "kg"},
                {"id": 2, "value": 3.14, "unit": "m"},
            ]
        },
        "metrics=#id,value,unit|1i,42.0,kg|2,3.14,m",
    ),
    (
        {"report": "Riga 1\nRiga 2 con \"virgolette\" e \\backslash\nRiga 3"},
        'report="Riga 1\nRiga 2 con \\"virgolette\\" e \\\\backslash\nRiga 3"',
    ),
    (
        {"task": {"intent": "review", "items": [], "owner": None}},
        "task={intent=review;items=[];owner=~}",
    ),
    (
        {"contact": {"email": "ops@acme.example", "url": "https://acme.example/api/v2"}},
        "contact={email=ops@acme.example;url=https://acme.example/api/v2}",
    ),
    (
        {"users_with_roles": [
            {"id": 1, "name": "alice", "roles": ["admin", "ops"]},
            {"id": 2, "name": "bob", "roles": ["dev"]},
        ]},
        "users_with_roles=#id,name,roles|1i,alice,[admin,ops]|2,bob,[dev]",
    ),
    (
        {"avatar": b"hello"},
        "avatar=b!aGVsbG8=",
    ),
]


def system_prompt() -> str:
    """Return the ADP system prompt for instructing an LLM agent."""
    return SYSTEM_PROMPT


def few_shot_examples() -> list[tuple[dict[str, Any], str]]:
    """Return canonical (python_obj, adp_string) pairs for few-shot prompting."""
    return list(_FEW_SHOT_PAIRS)


def few_shot_block() -> str:
    """Render few-shot examples as a single text block for prompt injection."""
    import json as _json
    import base64 as _b64

    def _default(obj):
        if isinstance(obj, (bytes, bytearray)):
            return {"_adp_bytes": _b64.b64encode(bytes(obj)).decode("ascii")}
        raise TypeError

    lines: list[str] = ["EXAMPLES (Python dict on the left, ADP on the right):", ""]
    for obj, adp_str in _FEW_SHOT_PAIRS:
        lines.append("INPUT:")
        lines.append(_json.dumps(obj, indent=2, ensure_ascii=False, default=_default))
        lines.append("OUTPUT:")
        lines.append(adp_str)
        lines.append("")
    return "\n".join(lines)
