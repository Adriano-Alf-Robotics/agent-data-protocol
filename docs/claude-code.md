# Using ADP in Claude Code

> Purpose: full setup guide for integrating ADP into Claude Code sessions — plugin, manual setup, and A/B test results showing 38.5% token savings on subagent reports.
> Back to [main README](../README.md)

---

## Real A/B result: subagent report JSON vs ADP

Test conducted directly inside a Claude Code session, dispatching two subagents
(model `claude-haiku-4-5`) with IDENTICAL instructions on the same task —
analyze `src/adp/` and report for each module the name, lines, exported symbols,
description — asking one for the report in **JSON** and the other in **ADP**
(the ADP `prompt` module provides few-shot instructions to the agent).

| Output format | Tokens (cl100k_base) | Bytes |
|---|---:|---:|
| JSON | 766 | 2,696 |
| **ADP** | **471** | **1,717** |

**ADP saves 38.5% of tokens** (295 fewer tokens) and 36.3% of bytes on a single
subagent report.

**Typical economic impact:** a Claude Code session that dispatches 50 subagents
with structured reporting consumes approximately 25,000 input tokens in JSON
versus 15,400 in ADP toward the orchestrator. On Opus 4.7 ($15/Mtok input):

| Configuration | Subagent report cost / session | $/year (100 sessions/day) |
|---|---:|---:|
| Subagents in JSON | $0.375 | $13,700 |
| Subagents in ADP | $0.231 | $8,430 |
| **Savings** | **$0.144 (−38%)** | **$5,260** |

The savings per single turn are modest in absolute value, but they scale
linearly with the number of subagents dispatched. Typical orchestration workloads
(planner → executor → reviewer, parallel analysis fan-out, multi-file search)
produce dozens of subagent reports per session: ADP becomes an economically
significant choice.

---

## Ready-made plugin (recommended)

The repository contains `claude-plugin/`, a complete Claude Code plugin with
skills, an `adp-agent` subagent, nine slash commands, a contextual hook, and
an installation script. One-line setup:

```bash
bash /path/to/GoalLanguageAgents/claude-plugin/install.sh
# Riavvia Claude Code: /adp-encode, /adp-decode, /adp-bench, ... attivi
```

See [`claude-plugin/README.md`](../claude-plugin/README.md) for details,
uninstallation, and customizations.

---

## Manual setup (alternative)

If you prefer to configure manually without the packaged plugin, six integration
modes are available, from simplest to most powerful.

### 1. Project CLAUDE.md

Add to the repository's `CLAUDE.md` (or create `.claude/CLAUDE.md`):

```markdown
In questo repo gli agenti comunicano in **ADP** (vedi docs/superpowers/specs).
Quando serializzi dati strutturati tra subagent / log / artefatti:
- usa `adp.encode(obj)` invece di `json.dumps(obj)`
- usa `adp.decode(s)` invece di `json.loads(s)`
- per umani: `adp.to_markdown(s)` o `adp.to_html(s)`
```

Effect: Claude Code is aware of ADP from the start of the session.

### 2. Custom `/adp` slash command

Create `.claude/commands/adp.md`:

```markdown
---
description: Encode/decode/bench ADP da stdin
argument-hint: <encode|decode|to-md|to-html|sign|verify|bench> [opts]
---

Esegui `uv run --directory /path/to/GoalLanguageAgents adp $ARGUMENTS`.
```

In session: `/adp encode < input.json`, `/adp serve --port 8000`, etc.

### 3. Dedicated subagent

Create `.claude/agents/adp-agent.md` with the instruction to always respond
in ADP. Useful for extractions, classifications, and reports.

### 4. MCP server

Exposes ADP as a native MCP tool:

```python
# mcp-adp/server.py
from mcp.server.fastmcp import FastMCP
import adp

mcp = FastMCP("adp")

@mcp.tool()
def adp_encode(json_str: str) -> str:
    return adp.from_json(json_str)

@mcp.tool()
def adp_decode(adp_str: str) -> str:
    return adp.to_json(adp_str)

@mcp.tool()
def adp_to_html(adp_str: str) -> str:
    return adp.to_html(adp_str)

if __name__ == "__main__":
    mcp.run()
```

Register in `~/.claude/.mcp.json`:

```json
{
  "mcpServers": {
    "adp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/GoalLanguageAgents",
               "python", "mcp-adp/server.py"]
    }
  }
}
```

Restart Claude Code → it now has `mcp__adp__encode/decode/to_html/...` as
native tools.

### 5. SessionStart hook to pre-load the prompt

In `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "uv run --directory /path/to/GoalLanguageAgents adp prompt"
      }]
    }]
  }
}
```

Effect: the ADP system prompt is already in context when the session starts.

### 6. Permission allowlist

To avoid manual confirmations on every invocation, add to
`.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(uv run adp:*)",
      "Bash(uv run --directory * adp:*)"
    ]
  }
}
```

---

## Verify complete setup

```bash
uv run adp --version           # libreria raggiungibile
claude mcp list 2>&1 | grep adp  # se hai impostato MCP server
ls .claude/commands/adp.md     # slash command attivo
ls .claude/agents/adp-agent.md # subagent attivo
```
