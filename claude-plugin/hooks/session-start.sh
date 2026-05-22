#!/usr/bin/env bash
# ADP plugin SessionStart hook
#
# Stampa una nota contestuale all'avvio di una sessione Claude Code in
# un progetto che dichiara di usare ADP. Il segnale e' la presenza di
# un file `.adp-project` nella root del progetto OPPURE l'import della
# libreria adp in pyproject.toml.
#
# Output minimal: una riga. Per il prompt completo l'utente invoca
# /adp-prompt esplicitamente.

set -euo pipefail

# Cerca i marcatori nella directory corrente
if [ -f ".adp-project" ] || grep -q '"adp"' pyproject.toml 2>/dev/null; then
    cat <<'EOF'
ADP plugin: questo progetto usa il formato ADP per la serializzazione
inter-agente. Usa `adp.encode/decode` (Python) o i comandi /adp-encode,
/adp-decode, /adp-to-md, /adp-to-html, /adp-bench, /adp-sign, /adp-verify.
Per la skill completa: vedi `adp` skill in questo plugin.
EOF
fi
