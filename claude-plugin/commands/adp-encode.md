---
description: Convert JSON to ADP (token-efficient lossless format)
argument-hint: [file.json | --from-clipboard]
allowed-tools: Bash(adp:*), Bash(uv run adp:*), Read
disable-model-invocation: false
---

The user wants to encode JSON to ADP. Read input from `$ARGUMENTS` (file
path) or stdin/clipboard, then run:

```bash
adp encode < input.json
```

Show the resulting ADP string and the token count comparison.

If `adp` is not on PATH, fall back to:
```bash
uv run --directory <ADP-repo-path> adp encode < input.json
```

After encoding, optionally suggest `/adp-bench` to see the saving percent.
