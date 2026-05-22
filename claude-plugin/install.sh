#!/usr/bin/env bash
# Install the ADP plugin into the user's Claude Code plugin cache.
#
# Strategia: symlink in ~/.claude/plugins/cache/local/adp -> questo plugin.
# Aggiorna ~/.claude/plugins/installed_plugins.json se necessario.

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
    echo "Errore: ${CLAUDE_PLUGINS} non esiste. Claude Code installato?" >&2
    exit 1
fi
if [ ! -f "${PLUGIN_DIR}/.claude-plugin/plugin.json" ]; then
    echo "Errore: plugin.json non trovato in ${PLUGIN_DIR}" >&2
    exit 1
fi

mkdir -p "${LOCAL_DIR}"

# Crea o aggiorna il symlink
if [ -e "${TARGET}" ] || [ -L "${TARGET}" ]; then
    echo "Rimuovo installazione esistente in ${TARGET}"
    rm -rf "${TARGET}"
fi
ln -s "${PLUGIN_DIR}" "${TARGET}"
echo "Symlink creato: ${TARGET} -> ${PLUGIN_DIR}"

# Aggiorna installed_plugins.json (best-effort, mantiene altre voci)
if [ ! -f "${INSTALLED_JSON}" ]; then
    cat > "${INSTALLED_JSON}" <<EOF
{
  "local/${PLUGIN_NAME}": "${PLUGIN_VERSION}"
}
EOF
    echo "Creato ${INSTALLED_JSON}"
else
    python3 - <<PYEOF
import json
from pathlib import Path
p = Path("${INSTALLED_JSON}")
data = json.loads(p.read_text())
data["local/${PLUGIN_NAME}"] = "${PLUGIN_VERSION}"
p.write_text(json.dumps(data, indent=2) + "\n")
print(f"Aggiornato {p}")
PYEOF
fi

echo ""
echo "ADP plugin installato. Riavvia Claude Code per attivarlo."
echo ""
echo "Verifica:"
echo "  ls -la ${TARGET}"
echo "  cat ${INSTALLED_JSON}"
echo ""
echo "Comandi disponibili nelle prossime sessioni:"
echo "  /adp-encode, /adp-decode, /adp-to-md, /adp-to-html,"
echo "  /adp-bench, /adp-sign, /adp-verify, /adp-serve, /adp-prompt"
