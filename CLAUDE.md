# Project CLAUDE.md — ADP (Agent Data Protocol)

Token-efficient lossless serialization library for LLM agent-to-agent
communication. Python 3.11+, zero runtime deps in core. Version: **0.3.5**.

## What ADP is

- Textual format alternative to JSON, optimized for LLM tokenizers
- Lossless round-trip on dict/list/scalar/bytes
- Beats TOON (best competitor) by 11–61% tokens depending on workload
- Killer features: dynamic LUT (HPACK-style) + differential encoding +
  capability negotiation + tokenizer-aware cost + pre-warm + TPD promotion

## Documentation map

- `README.md` — primary public entry point (English, ~290 lines, slim)
- `README.it.md` — Italian translation (fallback)
- `docs/dynamic-lut.md` — full ADPSession reference + extensions
- `docs/benchmarks.md` — token reduction tables + side-by-side
- `docs/claude-code.md` — Claude Code integration + A/B real result
- `docs/images.md` — `adp.image` API + 7 compression strategies
- `docs/integrity.md` — sign/verify (CRC32/SHA-256/HMAC)
- `docs/live-viewer.md` — `adp serve` SSE viewer
- `docs/superpowers/specs/` — design specs (snapshot, not for users)
- `docs/superpowers/plans/` — implementation plans (snapshot)
- `claude-plugin/README.md` — CC plugin setup/install/uninstall

## Architecture cheat sheet

```
src/adp/
├── parser.py       ADP → Python (recursive-descent, zero deps)
├── serializer.py   Python → ADP
├── converters.py   JSON / Markdown / HTML
├── prompt.py       system prompt + few-shot for LLMs
├── lut.py          static LUT (DEFAULT_AGENT_LUT) + apply_lut_updates,
│                   encode_with_dyn_lut (stateless helpers)
├── tpd.py          phrase dictionary + learn_lut
├── db.py           ADPStore (content-addressed blob store)
├── image.py        7 image compression strategies for LLM
├── integrity.py    sign/verify (CRC32/SHA-256/HMAC)
├── serve.py        live HTML viewer (SSE, append-only)
├── cli.py          CLI (encode/decode/sign/verify/serve/bench/prompt/...)
├── cost.py         TokenizerCostEstimator (tiktoken-aware, optional dep)
├── diff.py         compute_diff / apply_diff (set + del operations)
└── session.py      ADPSession — dynamic LUT, diff, caps, warmup, TPD (~800 LOC)
```

## Development conventions

- **Package manager:** `uv`. Use `uv run pytest`, `uv run python -m benchmarks.bench_dynamic_lut`, etc.
- **Testing:** `pytest`, TDD strongly preferred. Suite **244 tests**, must stay green.
  - Run all: `uv run pytest -q`
  - Run one: `uv run pytest tests/test_session.py::test_xxx -v`
- **Optional extras:**
  - `[dev]` — pytest, tiktoken
  - `[bench]` — imagehash, msgpack, pyyaml, tomli-w, Pillow
  - `[tokenizer]` — tiktoken (for ADPSession cost-aware mode)
- **Style:** existing code style (no formatter enforced). Italian-friendly identifier ok in tests, but public API in English. Docstrings: Italian for internal, English for user-facing.
- **No new dependencies** in `src/adp/` core without explicit discussion. `cost.py` and `session.py` import tiktoken with `try/except ImportError` fallback.
- **Workflow:** for non-trivial features, use `docs/superpowers/specs/<date>-<topic>-design.md` for design + `docs/superpowers/plans/<date>-<topic>.md` for tasks (follow existing structure).

## ADPSession at a glance

| Feature | Param | Default | What |
|---|---|---|---|
| Core dynamic LUT | `max_entries`, `k_threshold` | 256, 2 | LRU bounded, sync via `_lut_add` |
| Persistence | `path`, `auto_save` | `~/.adp/lut_state.json`, True | flock + atomic write |
| Differential encoding | `enable_diff`, `diff_threshold` | True, 0.7 | `_base=ID;_diff={set;del}` |
| Capability negotiation | `announce_caps`, `caps_timeout_msgs` | True, 3 | `_caps=` + auto-degrade |
| Tokenizer cost | `cost_estimator` | None (char fallback) | TokenizerCostEstimator |
| Pre-warm | `session.warmup(messages)` | — | Pre-populate from log |
| TPD auto-promotion | `tpd_promote_every`, `tpd_promote_max_per_run` | 10, 10 | `0` to disable |

Full reference: `docs/dynamic-lut.md`.

## Benchmarks

- `benchmarks/bench_dynamic_lut.py` — single 20-msg workload, fast (~5s)
- `benchmarks/bench_comprehensive.py` — 7 workloads × 4 lengths × 6 encoders + latency + $ pricing. Generates `comprehensive_results.json` and `comprehensive_report.md`. Slower (~30–60s).

```bash
uv run --with toon-py --with tiktoken python -m benchmarks.bench_dynamic_lut
uv run --with toon-py --with tiktoken python -m benchmarks.bench_comprehensive
```

Top result @ 100 msg agent conversation:
- ADP full stack: 897 token vs TOON 2249 (+60.1%)
- A/B test in real Claude Code session: −38.5% subagent report tokens (JSON 766 → ADP 471)

## Known gotchas (current)

1. **`_N` namespace is reserved** for dynamic LUT aliases. User payloads
   with keys or values matching `_\d+` (e.g. `{"_0": "literal"}`) raise
   `ADPLUTSyncError` on decode. Documented in README and
   `src/adp/session.py` docstring.

2. **TPD promotion overhead on short workloads**: header cost of promoted
   entries doesn't amortize when occurrences are few. Set
   `tpd_promote_every=0` for sessions < 50 messages, or accept slight
   overhead.

3. **`DEFAULT_AGENT_LUT` design constraint (resolved 2026-05-25):** the
   collision risk with common payload keys (`to`, `it`, `us`) was fixed by
   renaming to `tmo`, `itn`, `uss`. A guard test in
   `tests/test_lut.py::test_default_agent_lut_no_common_word_aliases`
   prevents regression. Still recommend NOT passing
   `static_lut=DEFAULT_AGENT_LUT` to `ADPSession` for generic
   user-defined payloads — the LUT is tuned for inter-agent vocabulary.

4. **Windows not supported**: `session.py` uses `fcntl.flock` (POSIX
   only). macOS and Linux fine. Not documented in README yet.

## Plugin (`claude-plugin/`)

Full Claude Code integration: skill `adp`, subagent `adp-agent`, 9
slash commands (`/adp-encode`, `/adp-decode`, `/adp-to-md`,
`/adp-to-html`, `/adp-bench`, `/adp-sign`, `/adp-verify`,
`/adp-serve`, `/adp-prompt`), SessionStart hook.

- Install: `bash claude-plugin/install.sh`
- Uninstall: `bash claude-plugin/uninstall.sh`

Both scripts are idempotent and write to
`~/.claude/plugins/installed_plugins.json` using the CC v2 nested
format. Plugin currently **installed globally** as `adp@local v0.3.5`.

## When working in this repo

- Run `uv run pytest -q` before committing (must stay green).
- For new features in `ADPSession`: extend `src/adp/session.py`, add
  tests in `tests/test_<feature>.py`, follow TDD (red → green → refactor
  with frequent commits).
- For changes touching public API: also update `docs/dynamic-lut.md`
  parameter table.
- README updates: edit `README.md` (EN) first; if change is significant
  also sync `README.it.md` (currently lags ~3 fixes — full re-translation
  pending).
- Benchmarks: re-run after encoder/decoder/session logic changes; commit
  updated `benchmarks/comprehensive_results.json` if numbers shift more
  than ~2%.

## Tokenizer convention

All benchmarks use `cl100k_base` (Claude 3.x / GPT-4 family). For
`o200k_base` (GPT-4o), expect numbers ~5–10% different but same
direction of effects.
