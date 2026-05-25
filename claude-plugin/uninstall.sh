#!/usr/bin/env bash
# Uninstall the ADP plugin from the user's Claude Code plugin cache.
#
# Removes the symlink at ~/.claude/plugins/cache/local/adp
# and the corresponding entry in installed_plugins.json.

set -euo pipefail

PLUGIN_NAME="adp"

CLAUDE_PLUGINS="${HOME}/.claude/plugins"
LOCAL_DIR="${CLAUDE_PLUGINS}/cache/local"
TARGET="${LOCAL_DIR}/${PLUGIN_NAME}"
INSTALLED_JSON="${CLAUDE_PLUGINS}/installed_plugins.json"

removed_any=0

# Remove symlink / directory
if [ -L "${TARGET}" ] || [ -d "${TARGET}" ]; then
    rm -rf "${TARGET}"
    echo "Removed ${TARGET}"
    removed_any=1
else
    echo "No installation found at ${TARGET}"
fi

# Remove entry from installed_plugins.json (best-effort, preserves other entries)
if [ -f "${INSTALLED_JSON}" ]; then
    python3 - <<PYEOF
import json
from pathlib import Path

p = Path("${INSTALLED_JSON}")
data = json.loads(p.read_text())
changed = False

# Cleanup entry v2 nested format
if "plugins" in data and "${PLUGIN_NAME}@local" in data.get("plugins", {}):
    del data["plugins"]["${PLUGIN_NAME}@local"]
    changed = True
    print(f"Removed ${PLUGIN_NAME}@local entry from plugins")

# Cleanup eventuale entry legacy top-level
legacy_key = "local/${PLUGIN_NAME}"
if legacy_key in data:
    del data[legacy_key]
    changed = True
    print(f"Removed legacy {legacy_key} entry")

if changed:
    p.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Updated {p}")
else:
    print(f"No ${PLUGIN_NAME} entries found in {p}")
PYEOF
    removed_any=1
else
    echo "No ${INSTALLED_JSON} found, nothing to clean"
fi

echo ""
if [ "${removed_any}" -eq 1 ]; then
    echo "ADP plugin uninstalled. Restart Claude Code to deactivate it."
else
    echo "Nothing to uninstall."
fi
