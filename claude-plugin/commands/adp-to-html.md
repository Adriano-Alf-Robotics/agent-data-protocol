---
description: Render an ADP document as a standalone HTML5 page (rich CSS, auto dark mode)
argument-hint: '[file.adp] [--out path.html] [--title "..."]'
allowed-tools: Bash(adp:*), Bash(uv run adp:*), Read, Write
disable-model-invocation: false
---

Produce a complete HTML5 document with embedded CSS, auto-switching
between light and dark mode via `prefers-color-scheme`. Tables are
bordered with alternating row colors, multiline strings rendered as
code blocks, bytes shown as truncated chips with full base64 in tooltip.

```bash
adp to-html < input.adp > report.html
# or with custom title:
adp to-html --title "Q1 Report" < input.adp > report.html
```

For embedding into another page (no `<!DOCTYPE>` wrapper), add
`--fragment`.

After generation, ask the user if they want to open the file in a
browser, or use `/adp-serve` for live updates.
