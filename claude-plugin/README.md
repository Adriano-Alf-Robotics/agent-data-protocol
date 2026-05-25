# ADP Plugin for Claude Code

Plugin that integrates **ADP** (Agent Data Protocol) into Claude Code:
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
| **10 slash commands** | `/adp-encode`, `/adp-decode`, `/adp-to-md`, `/adp-to-html`, `/adp-bench`, `/adp-sign`, `/adp-verify`, `/adp-serve`, `/adp-prompt`, `/adp-dashboard` | `commands/*.md` |
| **Hook SessionStart** | annotates ADP projects at session start | `hooks/session-start.sh` |

## Prerequisites

The `adp` CLI must be installed and reachable. Two options:

```bash
# Option A: within the same repo
cd /path/to/agent-data-protocol
uv sync --all-extras
# commands will use: uv run --directory /path/to/agent-data-protocol adp ...

# Option B: global via pip / pipx
pipx install /path/to/agent-data-protocol
# commands will use: adp ...
```

## Plugin installation

### Recommended — cross-platform script

Works on Linux, macOS, and Windows:

```bash
python3 /path/to/agent-data-protocol/claude-plugin/install.py
```

On Linux/macOS the bash wrapper also works:

```bash
bash /path/to/agent-data-protocol/claude-plugin/install.sh
```

The installer creates a symbolic link (preferred) or a directory copy
(fallback on Windows without Developer Mode) at
`~/.claude/plugins/cache/local/adp`, and registers the plugin in
`installed_plugins.json`.

The plugin includes a **self-healing** mechanism: if the cache link is
lost (e.g. after a plugin cache cleanup), the SessionStart hook
automatically recreates it on the next session start.

### Alternative — manual symbolic link

```bash
mkdir -p ~/.claude/plugins/cache/local
ln -sf /path/to/agent-data-protocol/claude-plugin \
       ~/.claude/plugins/cache/local/adp
```

Then add the entry to `~/.claude/plugins/installed_plugins.json` manually.

## Verification

Open a new Claude Code session and check:

```
/adp-encode    # should appear among the available commands
```

Or ask Claude Code:

> Show me the `adp` skill and the `adp-agent` agent.

## Uninstallation

Cross-platform:

```bash
python3 /path/to/agent-data-protocol/claude-plugin/uninstall.py
```

Or via bash wrapper:

```bash
bash /path/to/agent-data-protocol/claude-plugin/uninstall.sh
```

Both remove the cache link and clean the entry from
`installed_plugins.json`. Restart Claude Code afterwards.

## Updates

If installed via symbolic link (the default on Linux/macOS), simply
update the ADP repository — the plugin follows automatically.

On Windows (directory copy fallback), re-run `install.py` to refresh.

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
