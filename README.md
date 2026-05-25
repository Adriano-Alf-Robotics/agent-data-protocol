# ADP — Agent Data Protocol

![License: MIT](https://img.shields.io/badge/license-MIT-blue)
![Python ≥3.11](https://img.shields.io/badge/python-%E2%89%A53.11-blue)
![CI](https://github.com/AdrianoDalPastro/agent-data-protocol/actions/workflows/ci.yml/badge.svg)

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
8. [Claude Code plugin](#claude-code-plugin)
9. [Dashboard](#dashboard)
10. [Project structure](#project-structure)
11. [Development and testing](#development-and-testing)
12. [Roadmap](#roadmap)
13. [Documentation](#documentation)
14. [License](#license)

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

## Claude Code plugin

ADP ships with a ready-made Claude Code plugin that provides automatic
project detection, nine slash commands, a dedicated subagent, and a
SessionStart hook for metrics tracking.

### Installation

Cross-platform (Linux, macOS, Windows):

```bash
python3 claude-plugin/install.py
```

On Linux/macOS the convenience wrapper also works:

```bash
bash claude-plugin/install.sh
```

Restart Claude Code after installation. The plugin self-heals: if the
cache link is lost (e.g. after a plugin cache cleanup), the SessionStart
hook recreates it automatically on the next session start.

### Uninstallation

```bash
python3 claude-plugin/uninstall.py
```

### What you get

| Feature | Description |
|---|---|
| **Slash commands** | `/adp-encode`, `/adp-decode`, `/adp-to-md`, `/adp-to-html`, `/adp-bench`, `/adp-sign`, `/adp-verify`, `/adp-serve`, `/adp-prompt`, `/adp-dashboard` |
| **Subagent** | `adp-agent` — responds in ADP format, useful for structured extractions |
| **Skill** | `adp` — teaches Claude when and how to use ADP in agent communication |
| **SessionStart hook** | Auto-detects ADP projects (via `.adp-project` file or `pyproject.toml` dependency), exports `ADP_PROJECT` env var, enables per-project metrics |
| **Permission allowlist** | Pre-configured `Bash(uv run adp:*)` rules to avoid confirmation prompts |

### Project detection

The hook looks for two markers in the working directory:

1. A `.adp-project` file (content = project name, or empty = use directory name)
2. `"adp"` in `pyproject.toml` dependencies

When detected, the hook sets `ADP_PROJECT` and prints available commands.
Metrics accumulate in `~/.adp/projects/<name>/` and can be visualized
with `/adp-dashboard`.

### Manual setup (alternative)

If you prefer to configure without the packaged plugin, six integration
modes are available — from simplest to most powerful. See
[docs/claude-code.md](docs/claude-code.md) for detailed instructions
covering CLAUDE.md snippets, custom slash commands, subagent setup, MCP
server, SessionStart hooks, and permission allowlists.

## Dashboard

ADP includes a built-in dashboard that generates a standalone HTML page
with interactive SVG charts showing token savings, LUT statistics,
encode/decode latency, and cost estimates per LLM provider.

### Per-project sessions

`ADPSession` supports per-project tracking. Pass a `project` name and
metrics are stored separately under `~/.adp/projects/<name>/`:

```python
session = adp.ADPSession(project="my-api")
msg = session.encode({"task": "deploy", "version": "2.1.0"})
# Metrics saved to ~/.adp/projects/my-api/lut_state.json
```

### Generate a dashboard

From the command line:

```bash
# All projects at once (discovers ~/.adp/projects/*)
uv run adp dashboard -o dashboard.html

# Single project
uv run adp dashboard --project my-api -o dashboard.html

# From a specific session file
uv run adp dashboard --path ./custom_lut.json -o dashboard.html
```

Or from Python:

```python
import adp
from pathlib import Path

session = adp.ADPSession(project="my-api")
# ... encode/decode messages ...
html = adp.render_dashboard(session.history, title="My API savings")
Path("dashboard.html").write_text(html)
```

The generated page includes:

- **Summary cards** — total messages, tokens saved, average saving %, LUT hit rate
- **Bar chart** — per-message token comparison (ADP vs JSON)
- **Cumulative savings** — running total of tokens saved over time
- **Cost estimates** — savings in $ per LLM provider (Claude, GPT-4o, etc.)
- **Latency table** — encode/decode avg/min/max in milliseconds
- **LUT gauge** — hit rate visualization with entry statistics

Multi-project mode adds a comparison table across all discovered projects
with per-project drill-down sections.

No external dependencies. Auto dark mode. Works in any browser.

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

### Benchmark results — token savings @ 100 messages

`ADPSession` full stack vs JSON-minified and TOON (best competitor).
Tokenizer: `cl100k_base`.

| Workload | JSON | TOON | ADP full | Δ vs JSON | Δ vs TOON |
|---|---:|---:|---:|---:|---:|
| status_polling | 7,523 | 8,503 | 3,308 | **−56.0%** | **−61.1%** |
| tool_use | 4,246 | 4,154 | 3,519 | −17.1% | −15.3% |
| long_narrative | 7,748 | 7,448 | 7,348 | −5.2% | −1.3% |
| etl_pipeline | 116,647 | 144,647 | 57,583 | **−50.6%** | **−60.2%** |
| multi_agent_broadcast | 4,600 | 4,520 | 4,009 | −12.8% | −11.3% |
| db_query_response | 29,565 | 20,215 | 16,420 | **−44.5%** | −18.8% |
| mixed | 24,519 | 27,939 | 14,012 | **−42.9%** | **−49.8%** |

Full results across 4 session lengths: [docs/benchmarks.md](docs/benchmarks.md).

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
