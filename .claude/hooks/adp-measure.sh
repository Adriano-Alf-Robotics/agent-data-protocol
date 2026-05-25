#!/usr/bin/env bash
# PostToolUse hook on Bash. Misura risparmio reale quando viene eseguito `adp encode`.
# - Estrae ADP output da tool_response.stdout
# - Decodifica per ottenere JSON originale (ADP è lossless)
# - Esegue `adp bench` per calcolare token JSON vs ADP
# - Appende riga a ~/.claude/adp-savings.tsv
# - Emette systemMessage con risparmio reale
set -uo pipefail

input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')

# match solo encode (decode è il caso opposto, niente risparmio da segnalare)
printf '%s' "$cmd" | grep -qE 'adp[[:space:]]+encode' || exit 0

adp_out=$(printf '%s' "$input" | jq -r '.tool_response.stdout // .tool_response.content // ""')
[[ -z "$adp_out" ]] && exit 0

ADP_BIN="${ADP_BIN:-adp}"
command -v "$ADP_BIN" >/dev/null 2>&1 || ADP_BIN="/home/adriano/Documenti/Git_XYZ/agent-data-protocol/.venv/bin/adp"

bench=$(printf '%s' "$adp_out" | "$ADP_BIN" decode 2>/dev/null | "$ADP_BIN" bench 2>/dev/null) || exit 0

adp_t=$(printf '%s' "$bench" | grep -oP 'ADP tokens:\s*\K[0-9]+' | head -1)
json_t=$(printf '%s' "$bench" | grep -oP 'JSON minified:\s*\K[0-9]+' | head -1)
[[ -z "$adp_t" || -z "$json_t" || "$json_t" == "0" ]] && exit 0

saved=$((json_t - adp_t))
pct=$(awk "BEGIN{printf \"%.1f\", ($saved/$json_t)*100}")

log="$HOME/.claude/adp-savings.tsv"
mkdir -p "$(dirname "$log")"
[[ -f "$log" ]] || printf "ts\tevent\tjson_tokens\tadp_tokens\tsaved\tsaved_pct\n" > "$log"
printf "%s\tencode\t%s\t%s\t%s\t%s\n" "$(date -Iseconds)" "$json_t" "$adp_t" "$saved" "$pct" >> "$log"

jq -nc --arg m "[plugin adp] encode → risparmio reale: ${saved} token (${pct}%) — JSON=${json_t} → ADP=${adp_t}" '{systemMessage:$m}'
