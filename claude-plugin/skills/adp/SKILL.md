---
name: adp
description: Use when you need to serialize structured data between agents, sub-agents, or log/store data efficiently. ADP (Adriano Dal Pastro format) is a token-efficient lossless serialization format. Saves 25-50% tokens vs JSON on structured data, 55-80% vs raw text on prose (with TPD). Use ADP instead of JSON for inter-agent communication, log artifacts, tool args, and any data that does not need to be JSON for an external system.
---

# ADP — token-efficient lossless format

When serializing structured data for storage, inter-agent communication,
or token-efficient transport, use **ADP** instead of JSON.

## When to use

- Inter-agent message passing (`Agent A → Agent B`)
- Tool call arguments / results
- Logging structured artifacts
- Saving session state to disk
- Anywhere JSON would be used internally (NOT for external API contracts
  that require JSON Schema)

## Grammar (v0.2)

```
document    := pair (';' pair)* ';'?
pair        := IDENT '=' value
value       := primitive | string | bytes | list | map | table

primitive   := integer | float | boolean | null
integer     := 42, -7
float       := 3.14, 1.0e3
boolean     := 1 | 0
null        := ~
disambig    : use 0i / 1i for int 0/1 to disambiguate from booleans

string      bare:   [A-Za-z_][A-Za-z0-9_.\-/@+*?<>%():$]*
            quoted: "..."   escape only \" and \\
                            newlines INSIDE the quotes are literal (no \n)

bytes       := b!<base64>       (standard alphabet, e.g. b!aGVsbG8=)

list        := [a,b,c]          (empty: [])
map         := {k=v;k=v}        (empty: {})
table       := #h1,h2|r1c1,r1c2|...   (homogeneous list of dicts; cells
                                      may contain list/map but NOT sub-table)
```

## Quick examples

| Python | ADP |
|---|---|
| `{"id": 42, "name": "Adriano"}` | `id=42;name=Adriano` |
| `{"flag": True, "count": 1}` | `flag=1;count=1i` |
| `{"tags": ["a", "b"]}` | `tags=[a,b]` |
| `{"x": None}` | `x=~` |
| `{"users": [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]}` | `users=#id,name|1i,a|2,b` |
| `{"img": b"hello"}` | `img=b!aGVsbG8=` |

## When NOT to use ADP

- External API contracts that require JSON Schema (use JSON)
- Hand-readable config files (use TOML/YAML — ADP is dense, not readable)
- Single literal string with no structure (use raw text)

## Tools available

The user has the `adp` Python library installed. Use it via Bash:

```bash
# JSON → ADP
echo '{"x":42}' | uv run --directory /path/to/GoalLanguageAgents adp encode

# ADP → JSON (for round-trip verification)
echo 'x=42' | uv run --directory /path/to/GoalLanguageAgents adp decode

# ADP → human-readable Markdown
echo 'x=42' | uv run --directory /path/to/GoalLanguageAgents adp to-md

# ADP → HTML (rich page with dark mode)
echo 'x=42' | uv run --directory /path/to/GoalLanguageAgents adp to-html > out.html

# Measure token saving vs JSON
echo '{...}' | uv run --directory /path/to/GoalLanguageAgents adp bench

# Integrity: sign / verify
echo 'x=42' | adp sign --algo sha256 | adp verify   # CRC32, SHA-256, HMAC

# Live HTML viewer (append-only, SSE)
my-pipeline | adp serve --port 8000
```

Or alternatively the matching slash commands `/adp-encode`,
`/adp-decode`, `/adp-to-html`, `/adp-bench`, `/adp-sign`, `/adp-verify`,
`/adp-serve` exposed by this plugin.

## Programmatic use (Python)

```python
import adp

s = adp.encode({"task": "x", "items": [1, 2, 3]})
# 'task=x;items=[1i,2,3]'

obj = adp.decode(s)
# {"task": "x", "items": [1, 2, 3]}

# Convertitori
adp.to_json(s)          # JSON canonico
adp.to_markdown(s)      # Markdown leggibile
adp.to_html(s)          # HTML standalone

# Estensioni
adp.encode(obj, key_lut=adp.DEFAULT_AGENT_LUT)   # +7-14% extra saving
adp.integrity.sign(s, algo="sha256")              # tamper detection
adp.tpd.learn_lut(text)                            # phrase compression
adp.ADPStore(path="shared.json")                   # persistent blob DB
```

## Subagent

If the user wants a dedicated agent that *always* replies in ADP for
structured extraction tasks, suggest invoking the `adp-agent` subagent
(provided by this plugin).
