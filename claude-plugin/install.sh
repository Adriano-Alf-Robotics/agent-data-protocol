#!/usr/bin/env bash
# Install the ADP plugin into the user's Claude Code plugin cache.
# Delegates to install.py for cross-platform compatibility.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "${SCRIPT_DIR}/install.py" "$@"
