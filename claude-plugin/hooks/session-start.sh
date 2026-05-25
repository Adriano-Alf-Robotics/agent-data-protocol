#!/usr/bin/env bash
# ADP plugin SessionStart hook
#
# 0. Self-heals the plugin symlink if it was removed (cache cleanup, etc.).
# 1. Detects whether the current project uses ADP (via .adp-project
#    file or pyproject.toml dependency).
# 2. Auto-detects project name from directory and exports ADP_PROJECT.
# 3. Prints a contextual note with tracking status.

set -euo pipefail

# --- Self-heal: ensure the plugin cache link exists (cross-platform) ---
PLUGIN_SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "${PLUGIN_SOURCE}" <<'PYEOF'
import sys, os, shutil, platform
from pathlib import Path
source = Path(sys.argv[1])
target = Path.home() / ".claude" / "plugins" / "cache" / "local" / "adp"
if not target.exists():
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.symlink_to(source, target_is_directory=True)
    except OSError:
        if platform.system() == "Windows":
            shutil.copytree(source, target)
        else:
            raise
PYEOF

# Look for markers in the current directory
if [ -f ".adp-project" ] || grep -q '"adp"' pyproject.toml 2>/dev/null; then
    # Auto-detect project name: .adp-project content > directory name
    if [ -f ".adp-project" ] && [ -s ".adp-project" ]; then
        ADP_PROJECT="$(head -1 .adp-project | tr -d '[:space:]')"
    else
        ADP_PROJECT="$(basename "$(pwd)")"
    fi
    export ADP_PROJECT

    # Auto-initialize session (creates lut_state.json if missing)
    python3 -c "
from pathlib import Path
import json, os
proj = os.environ.get('ADP_PROJECT', '')
if proj:
    p = Path.home() / '.adp' / 'projects' / proj / 'lut_state.json'
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            'version': 1, 'project': proj,
            'entries': {}, 'lru_order': [], 'next_alias_id': 0,
            'stats': {'hit_count': 0, 'miss_count': 0, 'evictions': 0},
            'history': []
        }, indent=2), encoding='utf-8')
" 2>/dev/null || true

    cat <<EOF
ADP plugin active (project: ${ADP_PROJECT}).
Metrics tracked in ~/.adp/projects/${ADP_PROJECT}/.
When serializing data between agents, use:
  session = adp.ADPSession(project="${ADP_PROJECT}")
Commands: /adp-encode, /adp-decode, /adp-bench, /adp-dashboard.
EOF
fi
