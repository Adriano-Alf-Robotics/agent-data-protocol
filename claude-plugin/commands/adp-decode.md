---
description: Convert ADP to JSON (lossless round-trip)
argument-hint: [file.adp]
allowed-tools: Bash(adp:*), Bash(uv run adp:*), Read
disable-model-invocation: false
---

Decode an ADP document back to JSON. The user wants to read or verify
the structured content.

```bash
adp decode < input.adp
```

Output is canonical JSON with `_adp_bytes` tags for any binary fields,
preserving lossless round-trip.

Use `/adp-to-md` instead if the user wants a human-friendly Markdown
view, or `/adp-to-html` for a styled HTML page.
