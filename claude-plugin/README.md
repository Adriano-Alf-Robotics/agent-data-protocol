# ADP Plugin for Claude Code

Plugin that integrates **ADP** (Adriano Dal Pastro format) into Claude Code:
skill, slash commands, dedicated subagent, contextual hook.

ADP is a lossless, token-efficient text serialization format for
communication between AI agents. See the [main README](../README.md)
for the spec, benchmarks, and APIs.

> Italian version: [README.it.md](../README.it.md)

## What the plugin provides

| Component | What it activates | Location |
|---|---|---|
| **Skill `adp`** | contextual instruction: when serializing structured data use ADP, not JSON | `skills/adp/SKILL.md` |
| **Subagent `adp-agent`** | delegatable task that *always* replies in ADP | `agents/adp-agent.md` |
| **9 slash commands** | `/adp-encode`, `/adp-decode`, `/adp-to-md`, `/adp-to-html`, `/adp-bench`, `/adp-sign`, `/adp-verify`, `/adp-serve`, `/adp-prompt` | `commands/*.md` |
| **Hook SessionStart** | annotates ADP projects at session start | `hooks/session-start.sh` |

## Prerequisites

The `adp` CLI must be installed and reachable. Two options:

```bash
# Option A: within the same repo
cd /path/to/GoalLanguageAgents
uv sync --all-extras
# commands will use: uv run --directory /path/to/GoalLanguageAgents adp ...

# Option B: global via pip / pipx
pipx install /path/to/GoalLanguageAgents
# commands will use: adp ...
```

## Plugin installation

### Method 1 — symbolic link (development)

```bash
mkdir -p ~/.claude/plugins/cache/local
ln -sf /path/to/GoalLanguageAgents/claude-plugin \
       ~/.claude/plugins/cache/local/adp
```

Edit `~/.claude/plugins/installed_plugins.json` by adding:

```json
{
  "local/adp": "0.3.5"
}
```

### Method 2 — direct copy

```bash
mkdir -p ~/.claude/plugins/cache/adp/0.3.5
cp -r /path/to/GoalLanguageAgents/claude-plugin/* \
      ~/.claude/plugins/cache/adp/0.3.5/
```

### Method 3 — automated script

```bash
bash /path/to/GoalLanguageAgents/claude-plugin/install.sh
```

## Verification

Open a new Claude Code session and check:

```
/adp-encode    # should appear among the available commands
```

Or ask Claude Code:

> Show me the `adp` skill and the `adp-agent` agent.

## Uninstallation

```bash
rm ~/.claude/plugins/cache/local/adp        # if symbolic link
# or
rm -rf ~/.claude/plugins/cache/adp           # if direct copy
```

Also remove the entry from `~/.claude/plugins/installed_plugins.json`.

## Updates

If you installed via symbolic link (method 1), simply update the
ADP repository — the plugin follows automatically.

For a direct copy, re-run `install.sh` or update manually.

## Typical use case

```
> Extract from the file customers.csv a list of users with id, name, email,
> in ADP.

Claude Code → invokes the adp-agent subagent →
adp-agent returns:
  users=#id,name,email|1i,Alice,alice@x.io|2,Bob,bob@x.io|3,Carla,carla@x.io

Claude Code → displays the string, suggests saving it with Write or
              decoding it with /adp-decode.
```

## License

MIT, see `LICENSE` in the main repository.
