---
description: Print the ADP system prompt for instructing an LLM agent
argument-hint: [--few-shot]
allowed-tools: Bash(adp:*), Bash(uv run adp:*)
disable-model-invocation: false
---

Print the canonical system prompt for instructing an LLM agent to
reply in ADP format. Useful when bootstrapping a new agent, MCP server,
or external service that needs to speak ADP.

```bash
adp prompt              # system prompt only
adp prompt --few-shot   # system prompt + 8 (Python dict ↔ ADP) examples
```

Pipe to `xclip` / `pbcopy` to put it on the clipboard, or include
directly into your `system=` parameter when calling the Anthropic or
OpenAI SDK.
