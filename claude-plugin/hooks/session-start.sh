#!/usr/bin/env bash
# ADP plugin SessionStart hook
#
# Prints a contextual note at the start of a Claude Code session in
# a project that declares it uses ADP. The signal is the presence of
# a `.adp-project` file in the project root OR the import of the adp
# library in pyproject.toml.
#
# Minimal output: one line. For the full prompt the user invokes
# /adp-prompt explicitly.

set -euo pipefail

# Look for markers in the current directory
if [ -f ".adp-project" ] || grep -q '"adp"' pyproject.toml 2>/dev/null; then
    cat <<'EOF'
ADP plugin: this project uses ADP format for inter-agent serialization.
Use `adp.encode/decode` (Python) or the commands /adp-encode,
/adp-decode, /adp-to-md, /adp-to-html, /adp-bench, /adp-sign, /adp-verify.
For the full skill reference: see the `adp` skill in this plugin.
EOF
fi
