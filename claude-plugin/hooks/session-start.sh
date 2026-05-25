#!/usr/bin/env bash
# ADP plugin SessionStart hook
#
# 1. Detects whether the current project uses ADP (via .adp-project
#    file or pyproject.toml dependency).
# 2. Auto-detects project name from directory and exports ADP_PROJECT.
# 3. Prints a contextual note with tracking status.

set -euo pipefail

# Look for markers in the current directory
if [ -f ".adp-project" ] || grep -q '"adp"' pyproject.toml 2>/dev/null; then
    # Auto-detect project name: .adp-project content > directory name
    if [ -f ".adp-project" ] && [ -s ".adp-project" ]; then
        ADP_PROJECT="$(head -1 .adp-project | tr -d '[:space:]')"
    else
        ADP_PROJECT="$(basename "$(pwd)")"
    fi
    export ADP_PROJECT

    cat <<EOF
ADP plugin active (project: ${ADP_PROJECT}).
Metrics tracked in ~/.adp/projects/${ADP_PROJECT}/.
When serializing data between agents, use:
  session = adp.ADPSession(project="${ADP_PROJECT}")
Commands: /adp-encode, /adp-decode, /adp-bench, /adp-dashboard.
EOF
fi
