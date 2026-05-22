---
description: Render an ADP document as human-readable Markdown
argument-hint: [file.adp]
allowed-tools: Bash(adp:*), Bash(uv run adp:*), Read
disable-model-invocation: false
---

Convert ADP to Markdown — one-way, optimized for human reading. Tables
remain tables, multiline strings become fenced code blocks, nested
maps become bullet lists.

```bash
adp to-md < input.adp
```

This is the recommended way to *show* an ADP document to a human.
