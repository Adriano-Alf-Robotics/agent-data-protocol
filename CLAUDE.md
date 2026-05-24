# Project CLAUDE.md — ADP (Adriano Dal Pastro format)

Token-efficient lossless serialization library for LLM agent-to-agent
communication. Written in Python 3.11+, zero runtime deps in core.

## What ADP is

- Textual format alternative to JSON, optimized for LLM tokenizers
- Lossless round-trip on dict/list/scalar/bytes
- Beats TOON (best competitor) by 11-61% tokens depending on workload
- Killer features: dynamic LUT (HPACK-style) + differential encoding +
  capability negotiation + tokenizer-aware cost + pre-warm + TPD promotion

Public docs: `README.md` (EN, primary), `README.it.md` (IT translation).

## Architecture cheat sheet

```
src/adp/
├── parser.py       ADP → Python (recursive-descent, zero deps)
├── serializer.py   Python → ADP
├── converters.py   JSON / Markdown / HTML
├── prompt.py       system prompt + few-shot for LLMs
├── lut.py          static LUT (DEFAULT_AGENT_LUT) — KNOWN COLLISION ISSUE (see below)
├── tpd.py          phrase dictionary + learn_lut
├── db.py           ADPStore (content-addressed blob store)
├── image.py        7 image compression strategies for LLM
├── integrity.py    sign/verify (CRC32/SHA-256/HMAC)
├── serve.py        live HTML viewer (SSE, append-only)
├── cli.py          CLI (encode/decode/sign/verify/serve/bench/prompt/...)
├── cost.py         TokenizerCostEstimator (tiktoken-aware, optional dep)
├── diff.py         compute_diff / apply_diff (set + del operations)
└── session.py      ADPSession — dynamic LUT, diff, caps, warmup, TPD
```

## Development conventions

- **Package manager:** `uv`. Use `uv run pytest`, `uv run python -m benchmarks.bench_dynamic_lut`, etc.
- **Testing:** `pytest`, TDD strongly preferred. Suite ≥ 242 tests, must stay green.
  - Run all: `uv run pytest -q`
  - Run one: `uv run pytest tests/test_session.py::test_xxx -v`
- **Optional extras:**
  - `[dev]` — pytest, tiktoken
  - `[bench]` — imagehash, msgpack, pyyaml, tomli-w
  - `[tokenizer]` — tiktoken (for ADPSession cost-aware mode)
- **Style:** existing code style (no formatter enforced). Italian-friendly identifier ok in tests, but public API in English. Docstrings: prefer Italian for internal modules, English for user-facing.
- **No new dependencies** in `src/adp/` core without explicit discussion. `cost.py` and `session.py` import tiktoken with `try/except ImportError` fallback.

## Recent major work (2026-05-22 → 2026-05-24)

`ADPSession` (`src/adp/session.py`, ~880 LOC) implements dynamic LUT
adaptive HPACK-style + 5 extensions, all completed and shipping in v0.3.5:

| Feature | Param | Default | What |
|---|---|---|---|
| Core dynamic LUT | `max_entries`, `k_threshold` | 256, 2 | LRU bounded, sync via `_lut_add` |
| Persistence | `path`, `auto_save` | `~/.adp/lut_state.json`, True | flock + atomic write |
| Differential encoding | `enable_diff`, `diff_threshold` | True, 0.7 | `_base=ID;_diff={set;del}` |
| Capability negotiation | `announce_caps`, `caps_timeout_msgs` | True, 3 | `_caps=` + auto-degrade |
| Tokenizer cost | `cost_estimator` | None (char fallback) | TokenizerCostEstimator |
| Pre-warm | `session.warmup(messages)` | — | Pre-populate from log |
| TPD auto-promotion | `tpd_promote_every`, `tpd_promote_max_per_run` | 10, 10 | `0` to disable |

Specs and plans are in `docs/superpowers/specs/` and `docs/superpowers/plans/`.

## Benchmarks

- `benchmarks/bench_dynamic_lut.py` — single 20-msg workload, fast (~5s)
- `benchmarks/bench_comprehensive.py` — 7 workloads × 4 lengths × 6 encoders + latency + $ pricing. Generates `comprehensive_results.json` and `comprehensive_report.md`. Slower (~30-60s).

Run with:
```bash
uv run --with toon-py --with tiktoken python -m benchmarks.bench_dynamic_lut
uv run --with toon-py --with tiktoken python -m benchmarks.bench_comprehensive
```

Top result @ 100 msg agent conversation:
- ADP full stack: 897 token vs TOON 2249 (+60.1%)
- A/B test in real Claude Code session: -38.5% subagent report tokens (JSON 766 → ADP 471)

## Known issues / gotchas

1. **`DEFAULT_AGENT_LUT` aggressive aliases** (`src/adp/lut.py`): `"timeout_s" → "to"` and similar short aliases collide with common user keys named `to`, `id`, etc. Causes round-trip failure when payload uses those keys. **Workaround:** don't pass `static_lut=DEFAULT_AGENT_LUT` to `ADPSession` for generic workloads. Comprehensive bench omits it for this reason. Real fix: redesign static LUT aliases (separate spec needed).

2. **TPD promotion overhead on short workloads**: header cost of promoted entries doesn't amortize when occurrences are few. Set `tpd_promote_every=0` for workloads < 50 messages, or accept slight overhead.

3. **`_N` namespace is reserved** for dynamic LUT aliases. User payloads with keys/values matching `_\d+` (e.g. `{"_0": "literal"}`) will raise `ADPLUTSyncError` on decode. Documented in `src/adp/session.py` module docstring.

## Plugin (`claude-plugin/`)

Full Claude Code integration: skill, subagent `adp-agent`, 9 slash commands, SessionStart hook, install script. Setup: `bash claude-plugin/install.sh`. See `claude-plugin/README.md`.

## When working in this repo

- Run `uv run pytest -q` before committing.
- For new features in `ADPSession`: extend in `src/adp/session.py`, add tests in `tests/test_<feature>.py`, follow TDD pattern (red→green→refactor with frequent commits).
- For spec/plan-driven changes: use `docs/superpowers/specs/<date>-<topic>-design.md` for design, `docs/superpowers/plans/<date>-<topic>.md` for implementation tasks. Both already used heavily — follow existing structure.
- README updates: keep `README.md` (EN) primary, `README.it.md` (IT) in sync when significant changes happen.
- Benchmarks: re-run after any change to encoder/decoder/session logic and commit updated `benchmarks/comprehensive_results.json` if numbers change.

## Tokenizer convention

All benchmarks use `cl100k_base` (Claude 3.x / GPT-4 family). For `o200k_base` (GPT-4o), expect numbers ~5-10% different but same direction of effects.
