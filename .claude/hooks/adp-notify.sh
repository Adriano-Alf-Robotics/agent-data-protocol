#!/usr/bin/env bash
# PreToolUse hook su Skill|Agent. Notifica uso plugin adp + storico cumulativo.
set -uo pipefail

input=$(cat)
tool=$(printf '%s' "$input" | jq -r '.tool_name // ""')

case "$tool" in
  Skill)
    skill=$(printf '%s' "$input" | jq -r '.tool_input.skill // ""')
    [[ "$skill" =~ adp ]] || exit 0
    label="Skill: $skill"
    ;;
  Agent)
    sub=$(printf '%s' "$input" | jq -r '.tool_input.subagent_type // ""')
    [[ "$sub" =~ adp ]] || exit 0
    desc=$(printf '%s' "$input" | jq -r '.tool_input.description // ""')
    label="Agent: $sub — $desc"
    ;;
  *) exit 0 ;;
esac

log="$HOME/.claude/adp-savings.tsv"
totals=""
if [[ -f "$log" ]]; then
  stats=$(awk -F'\t' 'NR>1 {n++; s+=$5; j+=$3} END {if(n>0) printf "%d %d %d", n, s, j}' "$log")
  if [[ -n "$stats" ]]; then
    read -r N SAVED JSON_TOT <<< "$stats"
    avg_pct=$(awk "BEGIN{printf \"%.1f\", ($SAVED/$JSON_TOT)*100}")
    totals=" | storico: ${N} encode · ${SAVED} token salvati (${avg_pct}% media)"
  fi
fi

msg="[plugin adp] $label | stima ADP vs JSON minified: ~30-70% (cl100k_base)${totals}"
jq -nc --arg m "$msg" '{systemMessage:$m}'
