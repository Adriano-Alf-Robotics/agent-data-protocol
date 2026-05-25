# Changelog

All notable changes to this project are documented in this file.
Format inspired by [Keep a Changelog](https://keepachangelog.com/).

## [0.3.5] — 2026-05-25

### Added
- `ADPSession`: dynamic LUT (HPACK-style, RFC 7541), differential
  encoding, capability negotiation with auto-degrade, tokenizer-aware
  cost estimation, pre-warm from corpus, TPD auto-promotion.
- `TokenizerCostEstimator` and `estimate_cost` for tiktoken-based
  cost-benefit analysis.
- `compute_diff` / `apply_diff` for set+del differential encoding.
- Capability negotiation: `_caps=` announcement and auto-degrade after
  timeout.
- TPD auto-promotion: learns frequent phrases during session and
  promotes them to dynamic LUT entries.
- Comprehensive benchmark suite: 7 workloads × 4 lengths × 6 encoders,
  with latency and pricing estimates.
- Claude Code plugin (`claude-plugin/`): skill, subagent, 9 slash
  commands, SessionStart hook, install/uninstall scripts.
- Cross-platform file locking: Windows support via no-op fallback when
  `fcntl` is unavailable.

### Changed
- `DEFAULT_AGENT_LUT` aliases renamed (`to`→`tmo`, `it`→`itn`,
  `us`→`uss`) to avoid collision with common payload keys.

## [0.2.0] — 2026-05-22

### Added
- Aggressive bare-string economy: URLs, emails, paths without quotes.
- Native `bytes` support via `b!` prefix + base64.
- Table notation with nested cells (lists and maps inside table rows).
- `adp.image` module: 7 lossy compression strategies for LLM
  consumption (thumbnail_jpeg, thumbnail_webp, perceptual_hash,
  bitmap_8x8, caption, hybrid, passthrough).
- `ADPStore`: content-addressed persistent blob database.
- `adp.integrity`: sign/verify with CRC32, SHA-256, HMAC.
- `adp serve`: live SSE HTML viewer for streaming agent output.
- `to_html` converter with auto dark mode.
- Static LUT support (`DEFAULT_AGENT_LUT`) for key shortening.
- Token Phrase Dictionary (`tpd.py`) with `learn_lut`.

### Changed
- Renamed from GLA to ADP (Agent Data Protocol).
- Grammar v0.2 breaks v0.1 compatibility intentionally.

## [0.1.0] — 2026-05-20

### Added
- Initial release as GLA (Goal Language for Agents).
- `encode` / `decode` with lossless round-trip.
- `to_json` / `from_json` / `to_markdown` converters.
- `system_prompt` and `few_shot_examples` for LLM integration.
- CLI: `encode`, `decode`, `bench`, `prompt`.
- Recursive-descent parser, zero runtime dependencies.
