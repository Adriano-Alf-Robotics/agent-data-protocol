# ADP — Agent Data Protocol

![License: MIT](https://img.shields.io/badge/license-MIT-blue)
![Python ≥3.11](https://img.shields.io/badge/python-%E2%89%A53.11-blue)

> 🇮🇹 Per la versione italiana: [README.it.md](README.it.md)

**A lossless, aggressively token-efficient text format for communication between AI agents.**

ADP is a Python library that defines a small serialization language designed for
message exchange between language models. It reduces the tokens agents spend
communicating with each other while preserving all structural information —
nested maps, lists, typed tables, multiline text, bytes — without data loss.

**Token savings vs JSON-min (cl100k_base):**

| Payload | JSON-min | ADP | Δ |
|---|---:|---:|---:|
| Homogeneous table (it) | 333 | 164 | **+50.8%** |
| 20-msg agent conversation (full stack) | 2079 | **908** | **+56.3%** |
| vs TOON (best competitor, full stack) | 2249 | **908** | **+59.6%** |

Full stack = `ADPSession` with dynamic LUT + differential encoding + static LUT.
See [docs/dynamic-lut.md](docs/dynamic-lut.md) and [docs/benchmarks.md](docs/benchmarks.md).

## Table of Contents

1. [Why ADP](#why-adp)
2. [Installation](#installation)
3. [Quickstart](#quickstart)
4. [When to use what](#when-to-use-what)
5. [Syntax cheat sheet](#syntax-cheat-sheet)
6. [Converters](#converters)
7. [AI agent integration](#ai-agent-integration)
8. [Project structure](#project-structure)
9. [Development and testing](#development-and-testing)
10. [Roadmap](#roadmap)
11. [Documentation](#documentation)
12. [License](#license)

---

## Why ADP

JSON is verbose for LLM tokenizers: every key is quoted, `true` costs more than
`1`, homogeneous tables repeat keys on every row, and binary bytes cannot be
represented natively.

ADP makes the design decisions that JSON could not afford:

- no mandatory quotes around keys or simple strings;
- `1`/`0` in place of `true`/`false`, `~` in place of `null`;
- literal newlines inside strings (no `\n` escape sequences);
- a dedicated table notation for lists of homogeneous dictionaries,
  supporting **nested cells** (lists and maps);
- extended bare strings for URLs, emails, paths — without quotes;
- native `bytes` via the `b!` prefix + standard base64;
- top-level without wrappers (`name=value;name=value`).

The trade-off is direct human readability, but the library's Markdown converter
always reconstructs a readable version and the JSON converter restores a
machine-readable structure.

## Installation

> **⚠️ Not on PyPI.** A `pip install adp` package exists on PyPI but is unrelated to this project. Install from source only.

**Option 1 — development (recommended, requires [uv](https://docs.astral.sh/uv/)):**

```bash
git clone https://github.com/AdrianoDalPastro/agent-data-protocol.git
cd agent-data-protocol
uv sync --all-extras
```

**Option 2 — pip from local clone or GitHub:**

```bash
pip install -e .
# or directly from GitHub (no local clone needed):
pip install git+https://github.com/AdrianoDalPastro/agent-data-protocol.git
```

Requirements: Python 3.11 or higher. Works on Linux, macOS and Windows.

## Quickstart

```python
import adp

payload = {
    "user": {"id": 42, "name": "Adriano", "active": True, "email": "adp@example.com"},
    "users": [
        {"id": 1, "name": "alice", "roles": ["admin", "ops"]},
        {"id": 2, "name": "bob",   "roles": ["dev"]},
    ],
    "thumbnail": b"\x89PNG\r\n\x1a\n...",
    "report": "Riga 1\nRiga 2 con \"virgolette\"",
}

s = adp.encode(payload)
assert adp.decode(s) == payload   # round-trip lossless, bytes inclusi

print(adp.to_json(s))      # JSON canonico per macchine non-AI
print(adp.to_markdown(s))  # Markdown leggibile per umani
```

From the command line:

```bash
echo '{"user":{"id":42,"name":"Adriano"}}' | uv run adp encode
# user={id=42;name=Adriano}

echo 'user={id=42;name=Adriano}' | uv run adp decode
# {"user": {"id": 42, "name": "Adriano"}}

uv run adp bench < payload.json    # confronto token ADP vs JSON
uv run adp prompt --few-shot       # stampa il prompt di sistema per LLM
```

## When to use what

| Scenario | Recommended configuration |
|---|---|
| Single message, uncoordinated agents | ADP base |
| Free-prose text (logs, narratives) | JSON or plain text — ADP saves little |
| Agents sharing a codebase (pre-shared LUT) | ADP + static LUT (`DEFAULT_AGENT_LUT`) |
| Long session, domain-specific vocabulary | ADP + dynamic LUT |
| Request/reply pattern, similar payloads | ADP + diff encoding |
| **Mixed workload, maximum savings** | **`ADPSession` full stack** |
| Images inline | `adp.image` lossy strategies (−67% to −99%) |
| Recurring images (icons, avatars) | `ADPStore` + `^id` references |
| LLM in the middle (integrity needed) | `adp.integrity.sign()` SHA-256 or HMAC |

## Syntax cheat sheet

| Element | Syntax | Example |
|---|---|---|
| Top-level | `name=value;name=value` | `id=42;ok=1` |
| Integer | bare | `42`, `-7` |
| Integer 0 or 1 (disambiguation) | suffix `i` | `0i`, `1i` |
| Float | with decimal point | `3.14`, `-0.5` |
| Boolean | `1` / `0` | `1` = true |
| Null | `~` | `~` |
| Bytes | `b!<base64>` | `b!aGVsbG8=` |
| Bare string | without quotes | `Adriano`, `ops@acme.example`, `https://x.y/api` |
| Quoted string | within `"..."` | `"with space"` |
| Escape inside string | only `\"` and `\\` | `"says \"hello\""` |
| List | `[a,b,c]` | `[admin,root]` |
| Map | `{k=v;k=v}` | `{id=1;qty=2}` |
| Table | `#h1,h2\|r1c1,r1c2\|...` | `#id,unit\|1i,kg\|2,m` |
| Table with nested cells | `#h\|[a,b]\|{k=v}` | `#id,tags\|1i,[a,b]\|2,[c]` |

A string needs quotes only if it contains spaces, newlines, syntactic
delimiters (`,;=[]{}|"#&~`), or if it looks like a number.

Full grammar: [`docs/superpowers/specs/2026-05-22-adp-design.md`](docs/superpowers/specs/2026-05-22-adp-design.md).

## Converters

| Direction | Function | Round-trip | Typical use |
|---|---|:---:|---|
| Python → ADP | `adp.encode(obj)` | ✓ | serialization |
| ADP → Python | `adp.decode(s)` | ✓ | deserialization |
| ADP → JSON | `adp.to_json(s)` | ✓ | non-AI machines |
| JSON → ADP | `adp.from_json(s)` | ✓ | import from JSON |
| ADP → Markdown | `adp.to_markdown(s)` | ✗ (one-way) | human reading |
| ADP → HTML | `adp.to_html(s)` | ✗ (one-way) | dashboards, browser |

Standalone HTML with automatic dark mode:

```python
html_page = adp.to_html(adp_msg, title="Report Q1")
Path("report.html").write_text(html_page)
```

For streaming agent output, `adp serve` opens a live SSE page that appends
records in real time — see [docs/live-viewer.md](docs/live-viewer.md).

## AI agent integration

### 1. System prompt

```python
import adp
from anthropic import Anthropic

client = Anthropic()
resp = client.messages.create(
    model="claude-opus-4-7",
    system=adp.system_prompt(),
    messages=[{"role": "user", "content": "Restituisci un report con id 42 e due metriche."}],
    max_tokens=1024,
)
data = adp.decode(resp.content[0].text)
```

The `adp.prompt` module exposes `system_prompt()`, `few_shot_examples()`,
`few_shot_block()`.

### 2. Validator-with-retry

```python
def chat_in_adp(prompt: str, max_retries: int = 2) -> dict:
    history = [{"role": "user", "content": prompt}]
    for _ in range(max_retries + 1):
        out = llm_call(system=adp.system_prompt(), messages=history)
        try:
            return adp.decode(out)
        except adp.ADPParseError as e:
            history.append({"role": "assistant", "content": out})
            history.append({"role": "user", "content": f"Errore: {e}. Riemetti SOLO ADP valido."})
    raise RuntimeError("ADP non valido dopo retry")
```

### 3. Session (dynamic LUT + diff encoding)

```python
session = adp.ADPSession()   # carica/crea ~/.adp/lut_state.json
msg = session.encode({"task_id": "t1", "user": {"id": 42, "role": "admin"}})
obj = session.decode(msg)
```

`ADPSession` achieves up to 56% token reduction on multi-turn workloads.
Full reference: [docs/dynamic-lut.md](docs/dynamic-lut.md).

> **Note:** dynamic LUT aliases use the reserved `_N` pattern (underscore + digits). Payload keys or values matching `_\d+` (e.g. `{"_0": "literal"}`) will raise `ADPLUTSyncError` on decode.

## Project structure

```
agent-data-protocol/
├── src/adp/
│   ├── __init__.py        API pubblica
│   ├── parser.py          ADP → Python (recursive-descent, zero deps)
│   ├── serializer.py      Python → ADP
│   ├── converters.py      JSON / Markdown / HTML
│   ├── prompt.py          system prompt + few-shot pairs
│   ├── lut.py             LUT condivisa (DEFAULT_AGENT_LUT)
│   ├── session.py         ADPSession (dynamic LUT + diff encoding)
│   ├── tpd.py             Token-aware Phrase Dictionary
│   ├── db.py              ADPStore: persistent blob DB
│   ├── image.py           7 image compression strategies
│   ├── integrity.py       sign / verify (CRC32, SHA-256, HMAC)
│   ├── serve.py           live HTML viewer via SSE
│   └── cli.py             CLI (encode/decode/sign/verify/serve/...)
├── tests/                 244 tests
├── benchmarks/            payloads, encoders, results
├── docs/                  extended documentation (see below)
├── examples/              quickstart.py, two_agents_db.py
├── claude-plugin/         ready-made Claude Code plugin
└── pyproject.toml
```

## Development and testing

```bash
uv sync --all-extras
uv run pytest                                # 244 tests
uv run pytest --cov=adp                      # with coverage
uv run python -m benchmarks.compare_formats  # regenerate benchmarks
uv run adp bench < tests/fixtures/example.json
```

The core library has no runtime dependencies beyond the standard library.

### Test results

| Module | Tests | Status |
|---|---:|---|
| `test_roundtrip.py` | 49 | ✅ |
| `test_session.py` | 35 | ✅ |
| `test_diff.py` | 31 | ✅ |
| `test_v02_features.py` | 26 | ✅ |
| `test_cost.py` | 15 | ✅ |
| `test_integrity.py` | 14 | ✅ |
| `test_tpd_promotion.py` | 14 | ✅ |
| `test_caps.py` | 13 | ✅ |
| `test_tpd_db.py` | 12 | ✅ |
| `test_warmup.py` | 12 | ✅ |
| `test_lut.py` | 9 | ✅ |
| `test_image.py` | 9 | ✅ |
| `test_converters.py` | 5 | ✅ |
| **Total** | **244** | **✅ all passing** |

*Python 3.11, pytest 9.0, Linux — last run: 2026-05-25.*

## Roadmap

- **v0.3.5 (current)** — complete `ADPSession`: dynamic LUT HPACK-style, differential encoding, capability negotiation, tokenizer-aware cost, TPD auto-promotion. ~60% fewer tokens vs TOON.
- **v0.4** — optional envelope (`from`, `to`, `id`, `intent`, `reply_to`) for explicit inter-agent protocols.
- **v0.5** — optional schema/contract, Pydantic codegen.
- **v0.6** — reference implementation in TypeScript.

## Documentation

Extended documentation lives in `docs/`:

| File | Contents |
|---|---|
| [docs/dynamic-lut.md](docs/dynamic-lut.md) | `ADPSession` full reference: static LUT, dynamic HPACK-style LUT, differential encoding, sync/recovery, all parameters |
| [docs/benchmarks.md](docs/benchmarks.md) | Detailed token reduction tables, side-by-side format comparisons, 7-workload comprehensive benchmark, billing notes |
| [docs/images.md](docs/images.md) | `adp.image` module: 7 lossy strategies, ADP-DB for recurring assets, decision tree |
| [docs/integrity.md](docs/integrity.md) | `adp.integrity` module: CRC32 / SHA-256 / HMAC, CLI usage, LLM-in-the-middle threat model |
| [docs/claude-code.md](docs/claude-code.md) | Claude Code integration: A/B test result, ready-made plugin, 6 manual setup modes |
| [docs/live-viewer.md](docs/live-viewer.md) | `adp serve` SSE live viewer: features, usage, typical use cases |

## License

MIT.
