#!/usr/bin/env bash
# Install the ADP plugin into the user's Claude Code plugin cache.
#
# Strategy: symlink at ~/.claude/plugins/cache/local/adp -> this plugin.
# Updates ~/.claude/plugins/installed_plugins.json if necessary.

set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_NAME="adp"
PLUGIN_VERSION="0.3.5"

CLAUDE_PLUGINS="${HOME}/.claude/plugins"
CACHE_DIR="${CLAUDE_PLUGINS}/cache"
LOCAL_DIR="${CACHE_DIR}/local"
TARGET="${LOCAL_DIR}/${PLUGIN_NAME}"
INSTALLED_JSON="${CLAUDE_PLUGINS}/installed_plugins.json"

# Sanity checks
if [ ! -d "${CLAUDE_PLUGINS}" ]; then
    echo "Error: ${CLAUDE_PLUGINS} does not exist. Is Claude Code installed?" >&2
    exit 1
fi
if [ ! -f "${PLUGIN_DIR}/.claude-plugin/plugin.json" ]; then
    echo "Error: plugin.json not found in ${PLUGIN_DIR}" >&2
    exit 1
fi

mkdir -p "${LOCAL_DIR}"

# Create or update the symlink
if [ -e "${TARGET}" ] || [ -L "${TARGET}" ]; then
    echo "Removing existing installation at ${TARGET}"
    rm -rf "${TARGET}"
fi
ln -s "${PLUGIN_DIR}" "${TARGET}"
echo "Symlink created: ${TARGET} -> ${PLUGIN_DIR}"

# Update installed_plugins.json (v2 nested format, preserves other entries)
python3 - <<PYEOF
import json
from datetime import datetime
from pathlib import Path

p = Path("${INSTALLED_JSON}")
now_iso = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"
entry = {
    "scope": "user",
    "installPath": "${TARGET}",
    "version": "${PLUGIN_VERSION}",
    "installedAt": now_iso,
    "lastUpdated": now_iso,
}

if p.exists():
    data = json.loads(p.read_text())
    # Migra eventuali entry vecchio formato top-level
    legacy_key = "local/${PLUGIN_NAME}"
    if legacy_key in data:
        del data[legacy_key]
    data.setdefault("version", 2)
    data.setdefault("plugins", {})
else:
    data = {"version": 2, "plugins": {}}

data["plugins"]["${PLUGIN_NAME}@local"] = [entry]
p.write_text(json.dumps(data, indent=2) + "\n")
print(f"Updated {p}")
PYEOF

echo ""
echo "ADP plugin installed. Restart Claude Code to activate it."
echo ""
echo "Verification:"
echo "  ls -la ${TARGET}"
echo "  cat ${INSTALLED_JSON}"
echo ""
echo "Commands available in future sessions:"
echo "  /adp-encode, /adp-decode, /adp-to-md, /adp-to-html,"
echo "  /adp-bench, /adp-sign, /adp-verify, /adp-serve, /adp-prompt"
