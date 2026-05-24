#!/usr/bin/env bash
# Install the ADP plugin into the user's Claude Code plugin cache.
#
# Strategy: symlink at ~/.claude/plugins/cache/local/adp -> this plugin.
# Updates ~/.claude/plugins/installed_plugins.json if necessary.

set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_NAME="adp"
PLUGIN_VERSION="0.2.0"

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

# Update installed_plugins.json (best-effort, preserves other entries)
if [ ! -f "${INSTALLED_JSON}" ]; then
    cat > "${INSTALLED_JSON}" <<EOF
{
  "local/${PLUGIN_NAME}": "${PLUGIN_VERSION}"
}
EOF
    echo "Created ${INSTALLED_JSON}"
else
    python3 - <<PYEOF
import json
from pathlib import Path
p = Path("${INSTALLED_JSON}")
data = json.loads(p.read_text())
data["local/${PLUGIN_NAME}"] = "${PLUGIN_VERSION}"
p.write_text(json.dumps(data, indent=2) + "\n")
print(f"Updated {p}")
PYEOF
fi

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
