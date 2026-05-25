#!/usr/bin/env bash
# Uninstall the ADP plugin from the user's Claude Code plugin cache.
# Delegates to uninstall.py for cross-platform compatibility.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "${SCRIPT_DIR}/uninstall.py" "$@"
