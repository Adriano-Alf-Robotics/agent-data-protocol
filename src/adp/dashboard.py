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


def render_dashboard(
    history: list[dict],
    title: str = "ADP Dashboard",
) -> str:
    """Render a standalone HTML dashboard from session history metrics."""
    if not history:
        return _render_empty(title)

    total_msgs = len(history)
    encode_entries = [e for e in history if e["direction"] == "encode"]
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
        f'<div class="label">{lab}</div></div>'
        for v, lab in cards
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
            f'<rect x="{x}" y="{y_json:.1f}" width="{bar_w}" '
            f'height="{h_json:.1f}" fill="{_CHART_COLORS["json"]}" opacity="0.7">'
            f'<title>#{i+1} JSON: {e["tokens_json"]} tok</title></rect>'
        )
        bars.append(
            f'<rect x="{x + bar_w}" y="{y_adp:.1f}" width="{bar_w}" '
            f'height="{h_adp:.1f}" fill="{_CHART_COLORS["adp"]}" opacity="0.9">'
            f'<title>#{i+1} ADP: {e["tokens_adp"]} tok</title></rect>'
        )

    legend = (
        f'<rect x="{margin_left}" y="{h - 15}" width="10" height="10" fill="{_CHART_COLORS["json"]}" opacity="0.7"/>'
        f'<text x="{margin_left + 14}" y="{h - 6}" fill="currentColor" font-size="11">JSON</text>'
        f'<rect x="{margin_left + 55}" y="{h - 15}" width="10" height="10" fill="{_CHART_COLORS["adp"]}" opacity="0.9"/>'
        f'<text x="{margin_left + 69}" y="{h - 6}" fill="currentColor" font-size="11">ADP</text>'
    )

    svg_w = max(w, margin_left + n * (group_w + gap) + 10)
    svg = (
        f'<svg viewBox="0 0 {svg_w} {h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;height:auto;">\n'
        f'{"".join(bars)}\n{legend}\n</svg>'
    )

    return (
        f'<div class="dash-section"><h2>Token per message — JSON vs ADP</h2>'
        f'<div class="dash-chart">{svg}</div></div>'
    )


def _render_cumulative_chart(history: list[dict]) -> str:
    w, h = 800, 200
    margin_left = 50
    chart_w = w - margin_left - 10
    chart_h = h - 40

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

    polyline = f'<polyline points="{" ".join(points)}" fill="none" stroke="{_CHART_COLORS["saving"]}" stroke-width="2.5"/>'

    fill_points = f"{points[0].split(',')[0]},{chart_h + 10} " + " ".join(points) + f" {points[-1].split(',')[0]},{chart_h + 10}"
    fill_poly = f'<polyline points="{fill_points}" fill="{_CHART_COLORS["saving"]}" opacity="0.1" stroke="none"/>'

    end_label = (
        f'<text x="{margin_left + chart_w + 5}" y="20" '
        f'fill="{_CHART_COLORS["saving"]}" font-size="12" font-weight="600">'
        f'{cumulative[-1]:,}</text>'
    ) if cumulative else ""

    svg = (
        f'<svg viewBox="0 0 {w + 60} {h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;height:auto;">\n'
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
            f'<td style="color:{_CHART_COLORS["saving"]}">'
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
            return 0.0, 0.0, 0.0
        return sum(vals) / len(vals), min(vals), max(vals)

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


def discover_projects(projects_dir: str | None = None) -> list[tuple[str, list[dict]]]:
    """Scan the projects directory and return (name, history) for each project."""
    import json
    from pathlib import Path
    base = Path(projects_dir or "~/.adp/projects").expanduser()
    if not base.is_dir():
        return []
    results = []
    for d in sorted(base.iterdir()):
        lut_file = d / "lut_state.json"
        if d.is_dir() and lut_file.exists():
            try:
                data = json.loads(lut_file.read_text(encoding="utf-8"))
                history = data.get("history", [])
                if history:
                    results.append((d.name, history))
            except (json.JSONDecodeError, OSError):
                continue
    return results


def render_multi_dashboard(
    projects: list[tuple[str, list[dict]]],
    title: str = "ADP Dashboard",
) -> str:
    """Render a dashboard showing multiple projects."""
    if not projects:
        return _render_empty(title)

    # Summary comparison table across projects
    summary_rows = []
    for name, history in projects:
        total_adp = sum(e["tokens_adp"] for e in history)
        total_json = sum(e["tokens_json"] for e in history)
        saved = total_json - total_adp
        pct = (saved / total_json * 100) if total_json > 0 else 0
        msgs = len(history)
        summary_rows.append(
            f'<tr><td><a href="#{_html.escape(name)}">{_html.escape(name)}</a></td>'
            f'<td>{msgs}</td><td>{total_adp:,}</td><td>{total_json:,}</td>'
            f'<td>{saved:,}</td><td>{pct:.1f}%</td></tr>'
        )

    comparison = (
        f'<div class="dash-section"><h2>Projects overview</h2>'
        f'<table class="dash-table">'
        f'<thead><tr><th>Project</th><th>Messages</th><th>ADP tokens</th>'
        f'<th>JSON tokens</th><th>Saved</th><th>Saving %</th></tr></thead>'
        f'<tbody>{"".join(summary_rows)}</tbody></table></div>'
    )

    # Per-project sections
    sections = []
    for name, history in projects:
        section_html = (
            f'<div id="{_html.escape(name)}" style="margin-top:48px;">'
            f'<h1 style="font-size:20px;border-bottom:2px solid var(--accent);'
            f'padding-bottom:8px;margin-bottom:24px;">{_html.escape(name)}</h1>'
        )
        total_msgs = len(history)
        encode_entries = [e for e in history if e["direction"] == "encode"]
        total_tok_adp = sum(e["tokens_adp"] for e in history)
        total_tok_json = sum(e["tokens_json"] for e in history)
        total_saved = total_tok_json - total_tok_adp
        avg_saving_pct = (total_saved / total_tok_json * 100) if total_tok_json > 0 else 0
        diff_count = sum(1 for e in encode_entries if e.get("used_diff"))
        last = history[-1]
        hit_rate = (
            last["lut_hits"] / (last["lut_hits"] + last["lut_misses"]) * 100
            if (last["lut_hits"] + last["lut_misses"]) > 0 else 0
        )
        latencies = [e["elapsed_ms"] for e in history if e["elapsed_ms"] > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0

        section_html += _render_summary_cards(
            total_msgs, total_saved, avg_saving_pct, hit_rate,
            last["lut_entries"], diff_count, avg_latency,
        )
        section_html += _render_bar_chart(history)
        section_html += _render_cumulative_chart(history)
        section_html += _render_cost_table(total_tok_json, total_tok_adp)
        section_html += '</div>'
        sections.append(section_html)

    body = (
        f'<header class="adp-header">'
        f'<h1>{_html.escape(title)}</h1>'
        f'<div class="meta">{len(projects)} projects</div>'
        f'</header>\n'
        f'{comparison}\n'
        f'{"".join(sections)}\n'
    )
    return _wrap_page(title, body)


def _render_lut_section(history: list[dict]) -> str:
    last = history[-1]
    total_lookups = last["lut_hits"] + last["lut_misses"]
    hit_rate = last["lut_hits"] / total_lookups * 100 if total_lookups > 0 else 0

    r = 45
    cx, cy = 60, 70
    circumference = 2 * 3.14159 * r
    arc = circumference * 0.75
    filled = arc * hit_rate / 100

    gauge = (
        f'<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:120px;height:120px;">\n'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
        f'stroke="var(--border)" stroke-width="8" '
        f'stroke-dasharray="{arc:.1f} {circumference:.1f}" '
        f'stroke-dashoffset="0" transform="rotate(135 {cx} {cy})"/>\n'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
        f'stroke="{_CHART_COLORS["saving"]}" stroke-width="8" '
        f'stroke-dasharray="{filled:.1f} {circumference:.1f}" '
        f'stroke-dashoffset="0" transform="rotate(135 {cx} {cy})"/>\n'
        f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" '
        f'font-size="18" font-weight="700" fill="currentColor">{hit_rate:.0f}%</text>\n'
        f'</svg>'
    )

    return (
        f'<div class="dash-section"><h2>LUT statistics</h2>'
        f'<div style="display:flex;align-items:center;gap:32px;">'
        f'<div style="text-align:center;">{gauge}'
        f'<div style="font-size:12px;color:var(--muted);">hit rate</div></div>'
        f'<table class="dash-table" style="flex:1;">'
        f'<tbody>'
        f'<tr><td>Entries</td><td>{last["lut_entries"]}</td></tr>'
        f'<tr><td>Hits</td><td>{last["lut_hits"]}</td></tr>'
        f'<tr><td>Misses</td><td>{last["lut_misses"]}</td></tr>'
        f'<tr><td>Total lookups</td><td>{total_lookups}</td></tr>'
        f'</tbody></table></div></div>'
    )
