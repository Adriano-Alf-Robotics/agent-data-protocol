# ADP Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `adp dashboard` CLI command that generates a standalone HTML page with inline SVG charts showing per-session token savings, LUT statistics, encode/decode latency, and cost estimates per LLM provider.

**Architecture:** Two-layer design. (1) Extend `ADPSession` to collect per-message metrics in a `_history` list (token counts for ADP vs JSON, encode/decode timing, LUT state snapshots) and persist them alongside the LUT state. (2) New `dashboard.py` module reads the persisted metrics and renders a self-contained HTML page with inline SVG charts and the shared `_HTML_CSS` from `converters.py`. The CLI wires them together via `adp dashboard`.

**Tech Stack:** Python stdlib only (no chart library). SVG generated server-side as template strings. Reuses `_HTML_CSS` for dark mode. `cost.py.estimate_cost` for token counting. `benchmarks/pricing.py` for $ estimates.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/adp/session.py` | Modify | Add `_history` list, record per-message metrics in `encode()`/`decode()`, persist/load history in `save()`/`_load()`, expose `history` property |
| `src/adp/dashboard.py` | Create | `render_dashboard(history, stats, path) -> str` — takes metrics, returns standalone HTML with SVG charts |
| `src/adp/cli.py` | Modify | Add `adp dashboard` subcommand |
| `tests/test_dashboard.py` | Create | Tests for metrics collection and HTML rendering |

---

### Task 1: Extend ADPSession with per-message metrics collection

**Files:**
- Modify: `src/adp/session.py:131-135` (init stats), `src/adp/session.py:317-373` (encode), `src/adp/session.py:573-640` (decode), `src/adp/session.py:167-218` (_load/save), `src/adp/session.py:812-820` (stats)
- Test: `tests/test_dashboard.py`

Each history entry is a dict with this shape:

```python
{
    "direction": "encode" | "decode",
    "ts": float,              # time.time()
    "tokens_adp": int,        # token count of the ADP message
    "tokens_json": int,       # token count of equivalent JSON
    "bytes_adp": int,         # len(adp_msg)
    "bytes_json": int,        # len(json_msg)
    "elapsed_ms": float,      # wall-clock encode/decode time
    "lut_entries": int,       # snapshot of entries_count at that moment
    "lut_hits": int,          # cumulative hit_count
    "lut_misses": int,        # cumulative miss_count
    "used_diff": bool,        # whether diff encoding was used (encode only)
}
```

- [ ] **Step 1: Write failing tests for metrics collection**

Create `tests/test_dashboard.py`:

```python
"""Tests for ADPSession per-message metrics (dashboard feature)."""
import json
import time
from pathlib import Path

import adp
from adp.session import ADPSession
from adp.cost import estimate_cost


def test_encode_records_history_entry():
    """After encode(), session.history has one entry with expected fields."""
    s = ADPSession(path=None, announce_caps=False)
    s.encode({"task": "hello", "value": 42})
    assert len(s.history) == 1
    entry = s.history[0]
    assert entry["direction"] == "encode"
    assert entry["tokens_adp"] > 0
    assert entry["tokens_json"] > 0
    assert entry["tokens_adp"] <= entry["tokens_json"]
    assert entry["bytes_adp"] > 0
    assert entry["bytes_json"] > 0
    assert entry["elapsed_ms"] >= 0
    assert "lut_entries" in entry
    assert "lut_hits" in entry
    assert "lut_misses" in entry
    assert isinstance(entry["used_diff"], bool)
    assert isinstance(entry["ts"], float)


def test_decode_records_history_entry():
    """After decode(), session.history has one entry for the decode."""
    s = ADPSession(path=None, announce_caps=False)
    msg = s.encode({"x": 1})
    s2 = ADPSession(path=None, announce_caps=False)
    s2.decode(msg)
    assert len(s2.history) == 1
    entry = s2.history[0]
    assert entry["direction"] == "decode"
    assert entry["tokens_adp"] > 0
    assert entry["elapsed_ms"] >= 0


def test_history_grows_with_messages():
    """Multiple encode/decode calls accumulate history entries."""
    s = ADPSession(path=None, announce_caps=False)
    for i in range(5):
        s.encode({"i": i})
    assert len(s.history) == 5


def test_diff_flag_in_history():
    """When diff encoding kicks in, used_diff is True."""
    s = ADPSession(path=None, announce_caps=False, enable_diff=True)
    s.encode({"task": "t1", "user": {"id": 42, "role": "administrator"}})
    s.encode({"task": "t2", "user": {"id": 42, "role": "administrator"}})
    assert s.history[0]["used_diff"] is False
    # Second message may or may not use diff depending on threshold;
    # at minimum the flag is a bool
    assert isinstance(s.history[1]["used_diff"], bool)


def test_history_persisted_and_loaded(tmp_path):
    """History survives save/load cycle."""
    p = tmp_path / "lut_state.json"
    s = ADPSession(path=str(p), auto_save=False, announce_caps=False)
    s.encode({"a": 1})
    s.encode({"b": 2})
    s.save()

    s2 = ADPSession(path=str(p), auto_save=False, announce_caps=False)
    assert len(s2.history) == 2
    assert s2.history[0]["direction"] == "encode"


def test_history_in_stats():
    """stats() includes message_count."""
    s = ADPSession(path=None, announce_caps=False)
    s.encode({"x": 1})
    st = s.stats()
    assert st["message_count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dashboard.py -v`
Expected: FAIL — `ADPSession` has no `history` attribute.

- [ ] **Step 3: Add `_history` list and `history` property to `ADPSession.__init__`**

In `src/adp/session.py`, add to `__init__` after line 135 (`"evictions": 0,`):

```python
        self._history: list[dict] = []
```

Add the `history` property next to the existing `stats` property (after line 820):

```python
    @property
    def history(self) -> list[dict]:
        """Per-message metrics history for dashboard."""
        return list(self._history)
```

Update `stats()` to include `message_count`:

```python
    def stats(self) -> dict:
        """Dict diagnostico."""
        return {
            "entries_count": len(self._entries),
            "max_entries": self._max_entries,
            "hit_count": self._stats["hit_count"],
            "miss_count": self._stats["miss_count"],
            "evictions": self._stats["evictions"],
            "message_count": len(self._history),
        }
```

- [ ] **Step 4: Instrument `encode()` to record metrics**

In `src/adp/session.py`, at the top of the file add `import time` (after `import tempfile`).

Wrap the `encode()` method body. Right after `def encode(self, obj, *, no_lut=False):` and the docstring, insert timing start. Before each `return` in `encode()`, record the history entry. The key change pattern:

```python
    def encode(self, obj: Any, *, no_lut: bool = False) -> str:
        # ... existing docstring ...
        _t0 = time.perf_counter()
        _used_diff = False

        # ... existing encode logic (unchanged) ...
        # At the point where diff_msg is chosen over full_msg, set:
        #     _used_diff = True

        # Before EACH return statement in encode(), insert:
        #     self._record_history("encode", final_msg, obj, _t0, _used_diff)

        return final_msg
```

Add the `_record_history` helper method:

```python
    def _record_history(self, direction: str, adp_msg: str, obj: Any,
                        t0: float, used_diff: bool = False) -> None:
        """Append a metrics entry to _history."""
        import json as _json
        elapsed = (time.perf_counter() - t0) * 1000  # ms
        json_str = _json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        if self._cost_estimator is not None:
            tokens_adp = self._cost_estimator.estimate(adp_msg)
            tokens_json = self._cost_estimator.estimate(json_str)
        else:
            tokens_adp = max(1, len(adp_msg) // 4)
            tokens_json = max(1, len(json_str) // 4)
        self._history.append({
            "direction": direction,
            "ts": time.time(),
            "tokens_adp": tokens_adp,
            "tokens_json": tokens_json,
            "bytes_adp": len(adp_msg),
            "bytes_json": len(json_str),
            "elapsed_ms": round(elapsed, 3),
            "lut_entries": len(self._entries),
            "lut_hits": self._stats["hit_count"],
            "lut_misses": self._stats["miss_count"],
            "used_diff": used_diff,
        })
```

Concrete insertion points in `encode()`:

1. **After the `if effective_no_lut:` branch**, before `return final_msg` (around line 350):
   ```python
           self._record_history("encode", final_msg, obj, _t0, False)
           return final_msg
   ```

2. **At the end of the normal path** (around line 373), before `return final_msg`:
   ```python
       _used_diff = diff_msg is not None
       self._record_history("encode", final_msg, obj, _t0, _used_diff)
       return final_msg
   ```

- [ ] **Step 5: Instrument `decode()` to record metrics**

In `decode()`, wrap similarly:

```python
    def decode(self, msg: str) -> Any:
        # ... existing docstring ...
        _t0 = time.perf_counter()

        # ... existing decode logic (unchanged) ...
        # result = ... (the final decoded object)

        self._record_history("decode", msg, result, _t0, False)
        return result
```

The decode method has multiple return paths (diff path and normal path). Add `_record_history` before each return that yields the final decoded object. There are two:

1. After diff is applied and result expanded (around line 630):
   ```python
           self._record_history("decode", msg, result, _t0, False)
           return result
   ```

2. After normal decode path (around line 650):
   ```python
       self._record_history("decode", msg, result, _t0, False)
       return result
   ```

- [ ] **Step 6: Persist and load history in save()/_load()**

In `save()`, add `"history"` to the `data` dict (after `"stats"`):

```python
        data = {
            "version": SCHEMA_VERSION,
            "entries": dict(self._entries),
            "lru_order": list(self._lru_order),
            "next_alias_id": self._next_alias_id,
            "stats": dict(self._stats),
            "history": self._history,
        }
```

In `_load()`, after loading stats (after line 190):

```python
        self._history = list(data.get("history", []))
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_dashboard.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 8: Run full suite for regression**

Run: `uv run pytest -q`
Expected: 244+ passed (existing 244 + 7 new).

- [ ] **Step 9: Commit**

```bash
git add src/adp/session.py tests/test_dashboard.py
git commit -m "feat(session): add per-message metrics history for dashboard"
```

---

### Task 2: Create dashboard.py — HTML renderer with SVG charts

**Files:**
- Create: `src/adp/dashboard.py`
- Test: `tests/test_dashboard.py` (append)

The dashboard page has four sections:
1. **Summary cards** — total messages, total tokens saved, avg saving %, estimated $ saved
2. **Token savings bar chart** — per-message ADP vs JSON tokens (SVG bars)
3. **Cumulative savings line chart** — running total of tokens saved (SVG polyline)
4. **LUT & performance table** — hit rate gauge, entries over time, latency stats

All SVG is generated server-side as Python f-strings. No JavaScript needed.

- [ ] **Step 1: Write failing tests for dashboard rendering**

Append to `tests/test_dashboard.py`:

```python
from adp.dashboard import render_dashboard


def _make_history(n: int = 10) -> list[dict]:
    """Generate synthetic history entries for testing."""
    history = []
    for i in range(n):
        history.append({
            "direction": "encode" if i % 2 == 0 else "decode",
            "ts": 1716600000.0 + i * 60,
            "tokens_adp": 50 + i,
            "tokens_json": 80 + i,
            "bytes_adp": 200 + i * 10,
            "bytes_json": 350 + i * 10,
            "elapsed_ms": 0.03 + i * 0.001,
            "lut_entries": min(i, 5),
            "lut_hits": i * 2,
            "lut_misses": i,
            "used_diff": i > 3,
        })
    return history


def test_render_dashboard_returns_html():
    """render_dashboard produces a valid HTML document."""
    html = render_dashboard(_make_history())
    assert "<!DOCTYPE html>" in html
    assert "<svg" in html
    assert "</svg>" in html
    assert "ADP Dashboard" in html


def test_render_dashboard_empty_history():
    """Empty history produces a page with a 'no data' message."""
    html = render_dashboard([])
    assert "<!DOCTYPE html>" in html
    assert "no data" in html.lower() or "nessun dato" in html.lower()


def test_render_dashboard_summary_cards():
    """Summary section shows total messages and savings."""
    html = render_dashboard(_make_history(20))
    assert "20" in html  # total messages


def test_render_dashboard_has_dark_mode():
    """CSS includes prefers-color-scheme media query."""
    html = render_dashboard(_make_history())
    assert "prefers-color-scheme" in html


def test_render_dashboard_cost_estimate():
    """Cost section shows dollar estimates."""
    html = render_dashboard(_make_history())
    assert "$" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dashboard.py::test_render_dashboard_returns_html -v`
Expected: FAIL — `ImportError: cannot import name 'render_dashboard' from 'adp.dashboard'`

- [ ] **Step 3: Create `src/adp/dashboard.py` with full implementation**

```python
"""ADP Dashboard — standalone HTML report with SVG charts.

Generates a self-contained HTML5 page showing token savings, LUT
statistics, encode/decode latency, and cost estimates from an
ADPSession's per-message history.

Usage:
    from adp.dashboard import render_dashboard
    html = render_dashboard(session.history)
    Path("dashboard.html").write_text(html)
"""
from __future__ import annotations

import html as _html
from typing import Any

from adp.converters import _HTML_CSS


# Provider pricing ($/Mtok input) — subset of benchmarks/pricing.py
_PRICING = {
    "Claude Opus 4.7": 15.00,
    "Claude Sonnet 4.6": 3.00,
    "Claude Haiku 4.5": 0.80,
    "GPT-4o": 2.50,
    "GPT-4o mini": 0.15,
}

_CHART_COLORS = {
    "adp": "#2563eb",
    "json": "#9ca3af",
    "saving": "#16a34a",
    "diff": "#f59e0b",
}

_DARK_CHART_COLORS = {
    "adp": "#60a5fa",
    "json": "#6b7280",
    "saving": "#4ade80",
    "diff": "#fbbf24",
}


def render_dashboard(
    history: list[dict],
    title: str = "ADP Dashboard",
) -> str:
    if not history:
        return _render_empty(title)

    total_msgs = len(history)
    encode_entries = [e for e in history if e["direction"] == "encode"]
    decode_entries = [e for e in history if e["direction"] == "decode"]
    total_tok_adp = sum(e["tokens_adp"] for e in history)
    total_tok_json = sum(e["tokens_json"] for e in history)
    total_saved = total_tok_json - total_tok_adp
    avg_saving_pct = (total_saved / total_tok_json * 100) if total_tok_json > 0 else 0
    diff_count = sum(1 for e in encode_entries if e.get("used_diff"))

    last = history[-1]
    hit_rate = (
        last["lut_hits"] / (last["lut_hits"] + last["lut_misses"]) * 100
        if (last["lut_hits"] + last["lut_misses"]) > 0
        else 0
    )

    latencies = [e["elapsed_ms"] for e in history if e["elapsed_ms"] > 0]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0

    summary_html = _render_summary_cards(
        total_msgs, total_saved, avg_saving_pct, hit_rate,
        last["lut_entries"], diff_count, avg_latency,
    )
    bar_chart = _render_bar_chart(history)
    cumulative_chart = _render_cumulative_chart(history)
    cost_table = _render_cost_table(total_tok_json, total_tok_adp)
    latency_section = _render_latency_section(history)
    lut_section = _render_lut_section(history)

    body = (
        f'<header class="adp-header">'
        f'<h1>{_html.escape(title)}</h1>'
        f'<div class="meta">{total_msgs} messages</div>'
        f'</header>\n'
        f'{summary_html}\n'
        f'{bar_chart}\n'
        f'{cumulative_chart}\n'
        f'{cost_table}\n'
        f'{latency_section}\n'
        f'{lut_section}\n'
    )

    return _wrap_page(title, body)


def _render_empty(title: str) -> str:
    body = (
        f'<header class="adp-header">'
        f'<h1>{_html.escape(title)}</h1>'
        f'</header>\n'
        f'<p style="text-align:center;color:var(--muted);padding:80px 0;">'
        f'Nessun dato disponibile. Usa ADPSession per generare metriche.</p>\n'
    )
    return _wrap_page(title, body)


def _wrap_page(title: str, body: str) -> str:
    return (
        f'<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        f'<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{_html.escape(title)}</title>\n'
        f'<style>{_HTML_CSS}\n{_DASHBOARD_CSS}</style>\n'
        f'</head>\n<body>\n<main>\n{body}</main>\n</body>\n</html>'
    )


_DASHBOARD_CSS = """
.dash-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}
.dash-card {
  background: var(--code-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  text-align: center;
}
.dash-card .value {
  font-size: 28px;
  font-weight: 700;
  color: var(--accent);
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
.dash-card .label {
  font-size: 12px;
  color: var(--muted);
  margin-top: 4px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.dash-section {
  margin-bottom: 40px;
}
.dash-section h2 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 16px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 8px;
}
.dash-chart {
  background: var(--code-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  overflow-x: auto;
}
.dash-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
.dash-table th, .dash-table td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  text-align: right;
}
.dash-table th {
  text-align: left;
  font-weight: 600;
  background: var(--table-head);
}
.dash-table td:first-child, .dash-table th:first-child {
  text-align: left;
}
.dash-table tr:nth-child(even) td {
  background: var(--row-alt);
}
"""


def _render_summary_cards(
    total_msgs: int,
    total_saved: int,
    avg_saving_pct: float,
    hit_rate: float,
    lut_entries: int,
    diff_count: int,
    avg_latency: float,
) -> str:
    cards = [
        (f"{total_msgs}", "messages"),
        (f"{total_saved:,}", "tokens saved"),
        (f"{avg_saving_pct:.1f}%", "avg saving"),
        (f"{hit_rate:.0f}%", "LUT hit rate"),
        (f"{lut_entries}", "LUT entries"),
        (f"{diff_count}", "diff encodes"),
        (f"{avg_latency:.2f}ms", "avg latency"),
    ]
    items = "\n".join(
        f'<div class="dash-card"><div class="value">{v}</div>'
        f'<div class="label">{l}</div></div>'
        for v, l in cards
    )
    return f'<div class="dash-cards">{items}</div>'


def _render_bar_chart(history: list[dict]) -> str:
    w, h = 800, 250
    margin_left, margin_bottom = 50, 30
    chart_w = w - margin_left - 10
    chart_h = h - margin_bottom - 10

    max_tok = max(max(e["tokens_json"], e["tokens_adp"]) for e in history)
    if max_tok == 0:
        max_tok = 1
    n = len(history)
    bar_w = max(2, min(20, chart_w // (n * 2 + n)))
    gap = max(1, bar_w // 3)
    group_w = bar_w * 2 + gap

    bars = []
    for i, e in enumerate(history):
        x = margin_left + i * (group_w + gap)
        h_json = e["tokens_json"] / max_tok * chart_h
        h_adp = e["tokens_adp"] / max_tok * chart_h
        y_json = chart_h - h_json + 10
        y_adp = chart_h - h_adp + 10
        bars.append(
            f'<rect x="{x}" y="{y_json}" width="{bar_w}" '
            f'height="{h_json}" fill="var(--chart-json)" opacity="0.7">'
            f'<title>#{i+1} JSON: {e["tokens_json"]} tok</title></rect>'
        )
        bars.append(
            f'<rect x="{x + bar_w}" y="{y_adp}" width="{bar_w}" '
            f'height="{h_adp}" fill="var(--chart-adp)" opacity="0.9">'
            f'<title>#{i+1} ADP: {e["tokens_adp"]} tok</title></rect>'
        )

    legend = (
        f'<rect x="{margin_left}" y="{h - 15}" width="10" height="10" fill="var(--chart-json)" opacity="0.7"/>'
        f'<text x="{margin_left + 14}" y="{h - 6}" fill="var(--fg)" font-size="11">JSON</text>'
        f'<rect x="{margin_left + 55}" y="{h - 15}" width="10" height="10" fill="var(--chart-adp)" opacity="0.9"/>'
        f'<text x="{margin_left + 69}" y="{h - 6}" fill="var(--fg)" font-size="11">ADP</text>'
    )

    svg_w = max(w, margin_left + n * (group_w + gap) + 10)
    svg = (
        f'<svg viewBox="0 0 {svg_w} {h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;height:auto;--chart-adp:{_CHART_COLORS["adp"]};'
        f'--chart-json:{_CHART_COLORS["json"]};">\n'
        f'{"".join(bars)}\n{legend}\n</svg>'
    )

    return (
        f'<div class="dash-section"><h2>Token per message — JSON vs ADP</h2>'
        f'<div class="dash-chart">{svg}</div></div>'
    )


def _render_cumulative_chart(history: list[dict]) -> str:
    w, h = 800, 200
    margin_left, margin_bottom = 50, 30
    chart_w = w - margin_left - 10
    chart_h = h - margin_bottom - 10

    cumulative = []
    total = 0
    for e in history:
        total += e["tokens_json"] - e["tokens_adp"]
        cumulative.append(total)

    max_val = max(cumulative) if cumulative else 1
    if max_val == 0:
        max_val = 1
    n = len(cumulative)

    points = []
    for i, val in enumerate(cumulative):
        x = margin_left + (i / max(1, n - 1)) * chart_w if n > 1 else margin_left + chart_w / 2
        y = chart_h - (val / max_val * chart_h) + 10
        points.append(f"{x:.1f},{y:.1f}")

    polyline = f'<polyline points="{" ".join(points)}" fill="none" stroke="var(--chart-saving)" stroke-width="2.5"/>'

    fill_points = f"{points[0].split(',')[0]},{chart_h + 10} " + " ".join(points) + f" {points[-1].split(',')[0]},{chart_h + 10}"
    fill_poly = f'<polyline points="{fill_points}" fill="var(--chart-saving)" opacity="0.1" stroke="none"/>'

    end_label = f'<text x="{margin_left + chart_w + 5}" y="20" fill="var(--chart-saving)" font-size="12" font-weight="600">{cumulative[-1]:,}</text>' if cumulative else ""

    svg = (
        f'<svg viewBox="0 0 {w + 60} {h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;height:auto;--chart-saving:{_CHART_COLORS["saving"]};">\n'
        f'{fill_poly}\n{polyline}\n{end_label}\n</svg>'
    )

    return (
        f'<div class="dash-section"><h2>Cumulative tokens saved</h2>'
        f'<div class="dash-chart">{svg}</div></div>'
    )


def _render_cost_table(total_json: int, total_adp: int) -> str:
    saved = total_json - total_adp
    rows = []
    for provider, rate in _PRICING.items():
        cost_json = total_json * rate / 1_000_000
        cost_adp = total_adp * rate / 1_000_000
        cost_saved = saved * rate / 1_000_000
        rows.append(
            f'<tr><td>{_html.escape(provider)}</td>'
            f'<td>${rate:.2f}</td>'
            f'<td>${cost_json:.4f}</td>'
            f'<td>${cost_adp:.4f}</td>'
            f'<td style="color:var(--chart-saving);--chart-saving:{_CHART_COLORS["saving"]}">'
            f'${cost_saved:.4f}</td></tr>'
        )

    return (
        f'<div class="dash-section"><h2>Estimated cost savings per provider</h2>'
        f'<table class="dash-table">'
        f'<thead><tr><th>Provider</th><th>$/Mtok</th><th>JSON cost</th>'
        f'<th>ADP cost</th><th>Saved</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def _render_latency_section(history: list[dict]) -> str:
    encode_lat = [e["elapsed_ms"] for e in history if e["direction"] == "encode"]
    decode_lat = [e["elapsed_ms"] for e in history if e["direction"] == "decode"]

    def _stats(vals: list[float]) -> tuple[float, float, float]:
        if not vals:
            return 0, 0, 0
        avg = sum(vals) / len(vals)
        mn = min(vals)
        mx = max(vals)
        return avg, mn, mx

    e_avg, e_min, e_max = _stats(encode_lat)
    d_avg, d_min, d_max = _stats(decode_lat)

    return (
        f'<div class="dash-section"><h2>Encode / decode latency (ms)</h2>'
        f'<table class="dash-table">'
        f'<thead><tr><th>Direction</th><th>Count</th><th>Avg</th><th>Min</th><th>Max</th></tr></thead>'
        f'<tbody>'
        f'<tr><td>encode</td><td>{len(encode_lat)}</td><td>{e_avg:.3f}</td><td>{e_min:.3f}</td><td>{e_max:.3f}</td></tr>'
        f'<tr><td>decode</td><td>{len(decode_lat)}</td><td>{d_avg:.3f}</td><td>{d_min:.3f}</td><td>{d_max:.3f}</td></tr>'
        f'</tbody></table></div>'
    )


def _render_lut_section(history: list[dict]) -> str:
    last = history[-1]
    total_lookups = last["lut_hits"] + last["lut_misses"]
    hit_rate = last["lut_hits"] / total_lookups * 100 if total_lookups > 0 else 0

    # Mini gauge SVG
    gauge_w, gauge_h = 120, 120
    r = 45
    cx, cy = gauge_w // 2, gauge_h // 2 + 10
    circumference = 2 * 3.14159 * r
    arc = circumference * 0.75  # 270 degrees
    filled = arc * hit_rate / 100

    gauge = (
        f'<svg viewBox="0 0 {gauge_w} {gauge_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:120px;height:120px;">\n'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
        f'stroke="var(--border)" stroke-width="8" '
        f'stroke-dasharray="{arc} {circumference}" '
        f'stroke-dashoffset="0" transform="rotate(135 {cx} {cy})"/>\n'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
        f'stroke="{_CHART_COLORS["saving"]}" stroke-width="8" '
        f'stroke-dasharray="{filled} {circumference}" '
        f'stroke-dashoffset="0" transform="rotate(135 {cx} {cy})"/>\n'
        f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" '
        f'font-size="18" font-weight="700" fill="var(--fg)">{hit_rate:.0f}%</text>\n'
        f'</svg>'
    )

    return (
        f'<div class="dash-section"><h2>LUT statistics</h2>'
        f'<div style="display:flex;align-items:center;gap:32px;">'
        f'<div style="text-align:center;">{gauge}<div style="font-size:12px;color:var(--muted);">hit rate</div></div>'
        f'<table class="dash-table" style="flex:1;">'
        f'<tbody>'
        f'<tr><td>Entries</td><td>{last["lut_entries"]}</td></tr>'
        f'<tr><td>Hits</td><td>{last["lut_hits"]}</td></tr>'
        f'<tr><td>Misses</td><td>{last["lut_misses"]}</td></tr>'
        f'<tr><td>Total lookups</td><td>{total_lookups}</td></tr>'
        f'</tbody></table></div></div>'
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dashboard.py -v`
Expected: all 12 tests PASS.

- [ ] **Step 5: Run full suite for regression**

Run: `uv run pytest -q`
Expected: all tests pass (244 existing + 12 new).

- [ ] **Step 6: Commit**

```bash
git add src/adp/dashboard.py tests/test_dashboard.py
git commit -m "feat: add dashboard.py — HTML report with SVG charts"
```

---

### Task 3: Wire up `adp dashboard` CLI command

**Files:**
- Modify: `src/adp/cli.py`
- Test: `tests/test_dashboard.py` (append)

- [ ] **Step 1: Write failing test for CLI command**

Append to `tests/test_dashboard.py`:

```python
from click.testing import CliRunner
from adp.cli import main


def test_cli_dashboard_generates_html(tmp_path):
    """adp dashboard --path <lut_file> writes HTML to stdout."""
    # Create a session with history, save to file
    p = tmp_path / "lut_state.json"
    s = ADPSession(path=str(p), auto_save=False, announce_caps=False)
    for i in range(5):
        s.encode({"task": f"t{i}", "value": i})
    s.save()

    runner = CliRunner()
    result = runner.invoke(main, ["dashboard", "--path", str(p)])
    assert result.exit_code == 0
    assert "<!DOCTYPE html>" in result.output
    assert "<svg" in result.output


def test_cli_dashboard_output_file(tmp_path):
    """adp dashboard --output writes to file instead of stdout."""
    p = tmp_path / "lut_state.json"
    s = ADPSession(path=str(p), auto_save=False, announce_caps=False)
    s.encode({"x": 1})
    s.save()

    out = tmp_path / "report.html"
    runner = CliRunner()
    result = runner.invoke(main, ["dashboard", "--path", str(p), "--output", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    content = out.read_text()
    assert "<!DOCTYPE html>" in content


def test_cli_dashboard_no_history(tmp_path):
    """adp dashboard with no history shows empty state."""
    p = tmp_path / "lut_state.json"
    s = ADPSession(path=str(p), auto_save=False, announce_caps=False)
    s.save()

    runner = CliRunner()
    result = runner.invoke(main, ["dashboard", "--path", str(p)])
    assert result.exit_code == 0
    assert "nessun dato" in result.output.lower() or "no data" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dashboard.py::test_cli_dashboard_generates_html -v`
Expected: FAIL — `Error: No such command 'dashboard'.`

- [ ] **Step 3: Add dashboard command to cli.py**

Add at the end of `src/adp/cli.py`, before `if __name__ == "__main__":`:

```python
@main.command("dashboard")
@click.option("--path", default=None, type=click.Path(),
              help="Path to lut_state.json (default: ~/.adp/lut_state.json)")
@click.option("--output", "-o", default=None, type=click.Path(),
              help="Write HTML to file instead of stdout")
@click.option("--title", default="ADP Dashboard", help="Page title")
def cmd_dashboard(path: str | None, output: str | None, title: str) -> None:
    """Generate a standalone HTML dashboard from session metrics."""
    from pathlib import Path as P
    from adp.session import ADPSession, DEFAULT_PATH

    lut_path = P(path) if path else DEFAULT_PATH
    if not lut_path.exists():
        raise click.ClickException(
            f"Session file not found: {lut_path}\n"
            f"Use ADPSession to generate metrics first."
        )

    session = ADPSession(path=str(lut_path), auto_save=False, announce_caps=False)
    from adp.dashboard import render_dashboard
    html = render_dashboard(session.history, title=title)

    if output:
        out_path = P(output)
        out_path.write_text(html, encoding="utf-8")
        click.echo(f"Dashboard written to {out_path}", err=True)
    else:
        sys.stdout.write(html)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dashboard.py -v`
Expected: all 15 tests PASS.

- [ ] **Step 5: Run full suite for regression**

Run: `uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/adp/cli.py tests/test_dashboard.py
git commit -m "feat(cli): add 'adp dashboard' command"
```

---

### Task 4: Export dashboard in `__init__.py` and update docs

**Files:**
- Modify: `src/adp/__init__.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add dashboard import to `__init__.py`**

In `src/adp/__init__.py`, after the `integrity` imports, add:

```python
from adp.dashboard import render_dashboard
```

Add `"render_dashboard"` to `__all__`.

- [ ] **Step 2: Update CLAUDE.md architecture section**

Add `dashboard.py` to the architecture cheat sheet in `CLAUDE.md`:

```
├── dashboard.py    HTML dashboard with SVG charts (token savings, LUT, latency, cost)
```

Update the test count from 244 to the new total.

- [ ] **Step 3: Run full suite one final time**

Run: `uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/adp/__init__.py CLAUDE.md
git commit -m "feat: export render_dashboard + update docs"
```
