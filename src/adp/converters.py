"""Convertitori ADP <-> JSON, ADP -> Markdown, ADP -> HTML.

JSON conversion handles bytes by base64-encoding them in a tagged string:
    {"_adp_bytes": "<base64>"} on output, recognized on input.

HTML conversion produces a standalone HTML5 document with embedded CSS
that auto-switches between light and dark mode via prefers-color-scheme.
"""

from __future__ import annotations

import base64
import html as _html
import json
from typing import Any

from adp.parser import decode
from adp.serializer import encode


_BYTES_TAG = "_adp_bytes"


def _bytes_to_json_safe(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {_BYTES_TAG: base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, dict):
        return {k: _bytes_to_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_bytes_to_json_safe(v) for v in value]
    return value


def _json_safe_to_bytes(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value.keys()) == {_BYTES_TAG} and isinstance(value[_BYTES_TAG], str):
            return base64.b64decode(value[_BYTES_TAG].encode("ascii"))
        return {k: _json_safe_to_bytes(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe_to_bytes(v) for v in value]
    return value


def to_json(s: str, *, indent: int | None = 2, ensure_ascii: bool = False) -> str:
    """Convert an ADP document into canonical JSON.

    Round-trip safe: from_json(to_json(adp)) == decode(adp).
    Bytes are encoded as {"_adp_bytes": "<base64>"} to preserve them losslessly.
    """
    obj = decode(s)
    obj = _bytes_to_json_safe(obj)
    return json.dumps(obj, indent=indent, ensure_ascii=ensure_ascii, sort_keys=False)


def from_json(s: str) -> str:
    """Convert a JSON string into an ADP document.

    Top-level JSON must be an object (mapping).
    Recognizes {"_adp_bytes": "<base64>"} as bytes payload.
    """
    obj = json.loads(s)
    if not isinstance(obj, dict):
        raise ValueError(
            "top-level JSON must be an object to convert to ADP"
        )
    obj = _json_safe_to_bytes(obj)
    return encode(obj)


def to_markdown(s: str) -> str:
    """Convert an ADP document into a human-readable Markdown string.

    One-way: not a round-trip. Markdown is for humans, not for re-parsing.
    """
    obj = decode(s)
    blocks: list[str] = []
    for name, value in obj.items():
        blocks.append(f"## {name}\n\n{_md_value(value, level=0)}".rstrip())
    return "\n\n".join(blocks) + "\n"


def _md_value(value: Any, *, level: int) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        b = bytes(value)
        b64 = base64.b64encode(b).decode("ascii")
        if len(b64) <= 64:
            return f"`<bytes {len(b)} B: {b64}>`"
        return f"`<bytes {len(b)} B: {b64[:48]}…>`"
    if isinstance(value, str):
        return _md_string(value)
    if isinstance(value, dict):
        return _md_dict(value, level=level)
    if isinstance(value, list):
        return _md_list(value, level=level)
    return repr(value)


def _md_string(s: str) -> str:
    if "\n" in s:
        return "```\n" + s + "\n```"
    return s


def _md_dict(d: dict[str, Any], *, level: int) -> str:
    if not d:
        return "_empty_"
    lines: list[str] = []
    indent = "  " * level
    for k, v in d.items():
        if isinstance(v, (dict, list)) and v:
            lines.append(f"{indent}- **{k}**:")
            lines.append(_md_value(v, level=level + 1))
        else:
            rendered = _md_value(v, level=level)
            if "\n" in rendered:
                lines.append(f"{indent}- **{k}**:")
                for ln in rendered.splitlines():
                    lines.append(f"{indent}  {ln}")
            else:
                lines.append(f"{indent}- **{k}**: {rendered}")
    return "\n".join(lines)


def _md_list(lst: list[Any], *, level: int) -> str:
    if not lst:
        return "_empty_"
    if _is_uniform_table(lst):
        return _md_table(lst)
    indent = "  " * level
    lines: list[str] = []
    for item in lst:
        rendered = _md_value(item, level=level + 1)
        if "\n" in rendered:
            lines.append(f"{indent}-")
            for ln in rendered.splitlines():
                lines.append(f"{indent}  {ln}")
        else:
            lines.append(f"{indent}- {rendered}")
    return "\n".join(lines)


def _is_uniform_table(lst: list[Any]) -> bool:
    if len(lst) < 1:
        return False
    if not all(isinstance(x, dict) for x in lst):
        return False
    first_keys = tuple(lst[0].keys())
    if not first_keys:
        return False
    for row in lst[1:]:
        if tuple(row.keys()) != first_keys:
            return False
    for row in lst:
        for v in row.values():
            if isinstance(v, (dict, list)):
                return False
    return True


def _md_table(lst: list[dict[str, Any]]) -> str:
    headers = list(lst[0].keys())
    head_line = "| " + " | ".join(headers) + " |"
    sep_line = "|" + "|".join(["---"] * len(headers)) + "|"
    rows = []
    for row in lst:
        cells = []
        for h in headers:
            v = row[h]
            if v is None:
                cells.append("—")
            elif isinstance(v, bool):
                cells.append("true" if v else "false")
            else:
                cells.append(str(v).replace("|", "\\|"))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([head_line, sep_line, *rows])


# ---------------------------------------------------------------------------
# HTML converter (standalone, rich CSS, auto dark mode)
# ---------------------------------------------------------------------------

_HTML_CSS = """
:root {
  --bg: #ffffff;
  --fg: #1a1a1a;
  --muted: #6b7280;
  --border: #e5e7eb;
  --accent: #2563eb;
  --code-bg: #f4f4f5;
  --code-fg: #18181b;
  --row-alt: #fafafa;
  --table-head: #f3f4f6;
  --shadow: 0 1px 2px rgba(0,0,0,0.04);
  --radius: 6px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f1115;
    --fg: #e5e7eb;
    --muted: #9ca3af;
    --border: #2a2f3a;
    --accent: #60a5fa;
    --code-bg: #1a1d24;
    --code-fg: #e5e7eb;
    --row-alt: #14171d;
    --table-head: #1a1d24;
    --shadow: 0 1px 2px rgba(0,0,0,0.4);
  }
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--bg); color: var(--fg); }
body {
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 15px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}
main {
  max-width: 980px;
  margin: 0 auto;
  padding: 40px 24px 80px;
}
header.adp-header {
  border-bottom: 1px solid var(--border);
  padding-bottom: 16px;
  margin-bottom: 32px;
}
header.adp-header h1 {
  font-size: 22px;
  margin: 0 0 4px;
  font-weight: 600;
}
header.adp-header .meta {
  color: var(--muted);
  font-size: 13px;
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
section.adp-section {
  margin-bottom: 32px;
}
section.adp-section > h2 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 12px;
  padding-bottom: 6px;
  border-bottom: 2px solid var(--accent);
  display: inline-block;
}
.adp-kv {
  list-style: none;
  margin: 0;
  padding: 0;
}
.adp-kv > li {
  display: flex;
  gap: 12px;
  padding: 6px 0;
  border-bottom: 1px solid var(--border);
}
.adp-kv > li:last-child { border-bottom: none; }
.adp-kv .k {
  font-weight: 600;
  color: var(--muted);
  min-width: 140px;
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  font-size: 13px;
}
.adp-kv .v {
  flex: 1;
  word-break: break-word;
}
.adp-nested { margin-left: 16px; padding-left: 12px; border-left: 2px solid var(--border); }
.adp-list { margin: 0; padding-left: 20px; }
.adp-list > li { padding: 2px 0; }
.adp-table {
  width: 100%;
  border-collapse: collapse;
  margin: 4px 0;
  font-size: 13px;
  box-shadow: var(--shadow);
  border-radius: var(--radius);
  overflow: hidden;
}
.adp-table thead { background: var(--table-head); }
.adp-table th, .adp-table td {
  border: 1px solid var(--border);
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
}
.adp-table th {
  font-weight: 600;
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.adp-table tbody tr:nth-child(even) { background: var(--row-alt); }
.adp-null { color: var(--muted); font-style: italic; }
.adp-bool-true { color: #16a34a; font-weight: 600; }
.adp-bool-false { color: #dc2626; font-weight: 600; }
.adp-num { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; color: var(--accent); }
.adp-text-block {
  background: var(--code-bg);
  color: var(--code-fg);
  padding: 12px 14px;
  border-radius: var(--radius);
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  font-size: 13px;
  white-space: pre-wrap;
  overflow-x: auto;
  border: 1px solid var(--border);
}
.adp-bytes {
  display: inline-block;
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  font-size: 12px;
  background: var(--code-bg);
  color: var(--code-fg);
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid var(--border);
  cursor: help;
}
footer.adp-footer {
  margin-top: 60px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 12px;
  text-align: center;
}
""".strip()


def to_html(s: str, *, title: str = "ADP document", standalone: bool = True) -> str:
    """Convert an ADP document into a standalone HTML5 page.

    Includes embedded CSS with auto light/dark mode (prefers-color-scheme),
    rich tables, code-styled bytes/text-blocks, and semantic markup.

    One-way conversion (HTML cannot round-trip back to ADP).

    Args:
        s: ADP document string.
        title: <title> tag for the HTML document (only with standalone=True).
        standalone: if True (default), wrap output in a complete <!DOCTYPE> +
                    <html> + <head>(css) + <body>; otherwise return only the
                    inner content (suitable for embedding in another page).
    """
    obj = decode(s)
    body_parts: list[str] = ['<main>']
    body_parts.append(
        f'<header class="adp-header"><h1>{_html.escape(title)}</h1>'
        f'<div class="meta">{len(obj)} fields, {len(s):,} chars</div></header>'
    )
    for name, value in obj.items():
        body_parts.append('<section class="adp-section">')
        body_parts.append(f'<h2>{_html.escape(name)}</h2>')
        body_parts.append(_html_value(value))
        body_parts.append('</section>')
    body_parts.append(
        '<footer class="adp-footer">Generated by '
        '<a href="https://github.com/adrianodalpastro/agent-data-protocol" '
        'style="color: inherit;">ADP</a> &middot; '
        'lossless &middot; token-efficient'
        '</footer>'
    )
    body_parts.append('</main>')
    body = "".join(body_parts)
    if not standalone:
        return body
    return (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{_html.escape(title)}</title>\n'
        f'<style>{_HTML_CSS}</style>\n'
        '</head>\n'
        '<body>\n'
        f'{body}\n'
        '</body>\n'
        '</html>\n'
    )


def _html_value(value: Any) -> str:
    if value is None:
        return '<span class="adp-null">null</span>'
    if isinstance(value, bool):
        cls = "adp-bool-true" if value else "adp-bool-false"
        return f'<span class="{cls}">{"true" if value else "false"}</span>'
    if isinstance(value, (int, float)):
        return f'<span class="adp-num">{value}</span>'
    if isinstance(value, (bytes, bytearray, memoryview)):
        b = bytes(value)
        b64 = base64.b64encode(b).decode("ascii")
        preview = b64[:48] + ("…" if len(b64) > 48 else "")
        tooltip = f"{len(b)} bytes, base64: {b64}" if len(b64) <= 200 else f"{len(b)} bytes (b64 troncato)"
        return f'<span class="adp-bytes" title="{_html.escape(tooltip)}">b!{_html.escape(preview)}</span>'
    if isinstance(value, str):
        return _html_string(value)
    if isinstance(value, dict):
        return _html_dict(value)
    if isinstance(value, list):
        return _html_list(value)
    return _html.escape(repr(value))


def _html_string(s: str) -> str:
    if "\n" in s:
        return f'<pre class="adp-text-block">{_html.escape(s)}</pre>'
    return _html.escape(s)


def _html_dict(d: dict[str, Any]) -> str:
    if not d:
        return '<span class="adp-null">empty</span>'
    items: list[str] = ['<ul class="adp-kv">']
    for k, v in d.items():
        rendered = _html_value(v)
        if isinstance(v, (dict, list)) and v:
            items.append(
                f'<li><span class="k">{_html.escape(k)}</span>'
                f'<div class="v"><div class="adp-nested">{rendered}</div></div></li>'
            )
        else:
            items.append(
                f'<li><span class="k">{_html.escape(k)}</span>'
                f'<span class="v">{rendered}</span></li>'
            )
    items.append('</ul>')
    return "".join(items)


def _html_list(lst: list[Any]) -> str:
    if not lst:
        return '<span class="adp-null">empty</span>'
    if _is_html_table(lst):
        return _html_table(lst)
    items = ['<ul class="adp-list">']
    for x in lst:
        items.append(f'<li>{_html_value(x)}</li>')
    items.append('</ul>')
    return "".join(items)


def _is_html_table(lst: list[Any]) -> bool:
    if len(lst) < 1 or not all(isinstance(x, dict) for x in lst):
        return False
    first_keys = tuple(lst[0].keys())
    if not first_keys:
        return False
    for row in lst[1:]:
        if tuple(row.keys()) != first_keys:
            return False
    # Accept simple cell values (no deeply nested) so the table stays readable
    for row in lst:
        for v in row.values():
            if isinstance(v, (dict, list)) and v:
                return False
    return True


def _html_table(lst: list[dict[str, Any]]) -> str:
    headers = list(lst[0].keys())
    out = ['<table class="adp-table"><thead><tr>']
    for h in headers:
        out.append(f'<th>{_html.escape(h)}</th>')
    out.append('</tr></thead><tbody>')
    for row in lst:
        out.append('<tr>')
        for h in headers:
            out.append(f'<td>{_html_value(row[h])}</td>')
        out.append('</tr>')
    out.append('</tbody></table>')
    return "".join(out)
