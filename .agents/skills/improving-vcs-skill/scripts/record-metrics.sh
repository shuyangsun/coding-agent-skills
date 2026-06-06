#!/usr/bin/env bash
#
# Append one measurement row to the harness metrics log (TSV). One row per agent
# per round is the norm; call it once for each sub-agent after it finishes. The
# orchestrator fills the timing/retry fields from the sub-agent's structured
# report (see METRICS.md) and the quality field from check-quality.sh.
#
# Two dimensions matter beyond the raw numbers:
#   --difficulty  easy|medium|hard — which conflict-pressure tier this was.
#   --tier        the sub-agent's MODEL capability tier, vendor-agnostic:
#                 large (frontier), mid (workhorse), or small (fast/cheap).
#                 Different-sized models behave very differently on big
#                 conflicts, so scoreboard.sh breaks results down by tier — a
#                 vcs revision that only works for large models has NOT met the
#                 bar. Use these three labels so the breakdown stays comparable.
#
# Usage:
#   record-metrics.sh --round N --agent LABEL --mode git|jj \
#     [--difficulty easy|medium|hard] [--tier large|mid|small] [--env ENV] \
#     [--total SECONDS] [--conflict SECONDS] [--retries N] [--stalls N] \
#     [--quality pass|fail|partial] [--notes "..."] [--file PATH]
#
# Default log: $VCS_HARNESS_DIR/metrics.tsv (same work area new-sandbox.sh uses),
# so it persists across rounds for scoreboard.sh to compare.
set -euo pipefail

round="" agent="" mode="" difficulty="-" tier="-" env="-"
total=0 conflict=0 retries=0 stalls=0 quality="-" notes="-"
file="${VCS_HARNESS_DIR:-${TMPDIR:-/tmp}/vcs-harness}/metrics.tsv"

die() {
  echo "record-metrics.sh: $*" >&2
  exit 2
}
clean() { printf '%s' "${1//[$'\t\n']/ }"; } # strip tabs/newlines (TSV-safe)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --round) round="$2"; shift 2 ;;
    --agent) agent="$2"; shift 2 ;;
    --mode) mode="$2"; shift 2 ;;
    --difficulty) difficulty="$2"; shift 2 ;;
    --tier) tier="$2"; shift 2 ;;
    --env) env="$2"; shift 2 ;;
    --total) total="$2"; shift 2 ;;
    --conflict) conflict="$2"; shift 2 ;;
    --retries) retries="$2"; shift 2 ;;
    --stalls) stalls="$2"; shift 2 ;;
    --quality) quality="$2"; shift 2 ;;
    --notes) notes="$2"; shift 2 ;;
    --file) file="$2"; shift 2 ;;
    -h | --help)
      grep -E '^# (Usage|  )' "$0" | sed 's/^# //'
      exit 0
      ;;
    *) die "unknown arg: $1" ;;
  esac
done

[[ -n "$round" && -n "$agent" && -n "$mode" ]] || die "--round, --agent, --mode are required"
[[ "$mode" == "git" || "$mode" == "jj" ]] || die "--mode must be git or jj"
case "$difficulty" in easy | medium | hard | -) : ;; *) die "--difficulty must be easy, medium, or hard" ;; esac
for n in "$round" "$total" "$conflict" "$retries" "$stalls"; do
  [[ "$n" =~ ^[0-9]+([.][0-9]+)?$ ]] || die "numeric field expected, got: $n"
done

mkdir -p "$(dirname "$file")"
if [[ ! -f "$file" ]]; then
  printf 'round\tagent\tmode\tdifficulty\ttier\tenv\ttotal_s\tconflict_s\tretries\tstalls\tquality\tnotes\n' >"$file"
fi
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
  "$round" "$(clean "$agent")" "$mode" "$difficulty" "$(clean "$tier")" "$(clean "$env")" \
  "$total" "$conflict" "$retries" "$stalls" "$quality" "$(clean "$notes")" >>"$file"

echo "recorded round $round / $agent ($mode, ${difficulty}, tier=${tier}) -> $file"
