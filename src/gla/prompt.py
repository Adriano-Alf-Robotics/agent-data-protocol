"""System prompt template + few-shot examples for instructing LLM agents on GLA."""

from __future__ import annotations

from typing import Any


SYSTEM_PROMPT = """You communicate with other AI agents using GLA — Goal Language Agents — a token-efficient lossless format. ALWAYS reply in GLA when talking to another agent. Use prose only when talking to a human.

GLA SYNTAX (strict):
- A document is a sequence of records: &name:value&&name2:value2&
- name = identifier: [A-Za-z_][A-Za-z0-9_-]*
- Primitives:
    integer:  42, -7
    float:    3.14, -0.5, 1.0e3
    boolean:  1 = true, 0 = false
    null:     ~
    int 0/1 disambiguation: write 0i or 1i (otherwise 0/1 = bool)
- Strings:
    bare (no quotes) only if matches [A-Za-z_][A-Za-z0-9_.-]* and is not a reserved literal
    quoted: "..." — escape only \\" and \\\\ — newlines INSIDE the quotes are literal, no \\n needed
- List: [v,v,v]   (empty: [])
- Map:  {k=v;k=v} (empty: {})
- Table (for homogeneous list of dicts): #h1,h2,h3|r1c1,r1c2,r1c3|r2c1,r2c2,r2c3
- No whitespace required between tokens; only inside quoted strings.

RULES:
- Be terse. Never wrap GLA in markdown code fences.
- Never explain GLA syntax in replies — just emit GLA.
- If asked for prose, emit prose (not GLA).
- Lossless: every value must round-trip with no data loss.
"""


_FEW_SHOT_PAIRS: list[tuple[dict[str, Any], str]] = [
    (
        {"user": {"id": 42, "name": "Adriano", "active": True}},
        "&user:{id=42;name=Adriano;active=1}&",
    ),
    (
        {"tags": ["admin", "root", "user con spazio"]},
        '&tags:[admin,root,"user con spazio"]&',
    ),
    (
        {
            "metrics": [
                {"id": 1, "value": 42.0, "unit": "kg"},
                {"id": 2, "value": 3.14, "unit": "m"},
            ]
        },
        "&metrics:#id,value,unit|1i,42.0,kg|2,3.14,m&",
    ),
    (
        {"report": "Riga 1\nRiga 2 con \"virgolette\" e \\backslash\nRiga 3"},
        '&report:"Riga 1\nRiga 2 con \\"virgolette\\" e \\\\backslash\nRiga 3"&',
    ),
    (
        {"task": {"intent": "review", "items": [], "owner": None}},
        "&task:{intent=review;items=[];owner=~}&",
    ),
]


def system_prompt() -> str:
    """Return the GLA system prompt for instructing an LLM agent."""
    return SYSTEM_PROMPT


def few_shot_examples() -> list[tuple[dict[str, Any], str]]:
    """Return canonical (python_obj, gla_string) pairs for few-shot prompting."""
    return list(_FEW_SHOT_PAIRS)


def few_shot_block() -> str:
    """Render few-shot examples as a single text block for prompt injection."""
    import json as _json

    lines: list[str] = ["EXAMPLES (Python dict on the left, GLA on the right):", ""]
    for obj, gla in _FEW_SHOT_PAIRS:
        lines.append("INPUT:")
        lines.append(_json.dumps(obj, indent=2, ensure_ascii=False))
        lines.append("OUTPUT:")
        lines.append(gla)
        lines.append("")
    return "\n".join(lines)
