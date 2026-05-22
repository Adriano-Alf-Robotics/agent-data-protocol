---
description: Measure token saving of ADP vs JSON on a given payload
argument-hint: [file.json] [--tokenizer cl100k_base|o200k_base]
allowed-tools: Bash(adp:*), Bash(uv run adp:*), Read
disable-model-invocation: false
---

Benchmark a JSON payload: encode it as ADP and compare token counts.
Useful to decide whether ADP brings significant saving on a specific
shape of data.

```bash
adp bench < payload.json
# or with a specific tokenizer:
adp bench --tokenizer o200k_base < payload.json
```

Default tokenizer is `cl100k_base` (Claude 3.x / GPT-4). Use
`o200k_base` for GPT-4o, Claude 4.x, Opus 4.7.

Output:
- Tokens in JSON minified
- Tokens in JSON pretty
- Tokens in ADP
- Saving percentage vs JSON minified
