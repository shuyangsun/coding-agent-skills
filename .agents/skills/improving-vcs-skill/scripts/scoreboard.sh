#!/usr/bin/env bash
#
# Aggregate the metrics log into a per-round scoreboard so you can SEE whether a
# vcs-skill revision actually moved the numbers. The two first-class costs the
# loop drives down — batch wall-clock and, above all, conflict-resolution time —
# are shown with their round-over-round delta (▼ = improved, ▲ = regressed).
#
# Batch wall-clock is the MAX per-agent total in a round (a parallel batch is done
# only when its slowest agent is), which is exactly the cost the harness targets.
#
# Portable: no gawk extensions (asort/gensub) — runs under macOS BSD awk too.
#
# Usage: scoreboard.sh [--file PATH]
set -euo pipefail
file="${VCS_HARNESS_DIR:-${TMPDIR:-/tmp}/vcs-harness}/metrics.tsv"
[[ "${1:-}" == "--file" ]] && file="${2:?--file needs a path}"
[[ -f "$file" ]] || {
  echo "no metrics yet at $file (record some with record-metrics.sh)" >&2
  exit 1
}

awk -F'\t' '
NR==1 { next }                                  # skip header
{
  r=$1; tot=$5+0; conf=$6+0; ret=$7+0; stl=$8+0; q=$9
  if (!(r in seen)) { seen[r]=1; rounds[++nr]=r }
  n[r]++; sumt[r]+=tot; sumc[r]+=conf; sumret[r]+=ret; sumstl[r]+=stl
  if (tot>maxt[r]) maxt[r]=tot
  if (conf>maxc[r]) maxc[r]=conf
  if (q=="pass") pass[r]++
}
END {
  # sort round labels numerically (insertion sort; BSD-awk safe)
  for (i=2;i<=nr;i++){ k=rounds[i]; j=i-1; while(j>=1 && rounds[j]+0>k+0){rounds[j+1]=rounds[j];j--} rounds[j+1]=k }
  printf "%-6s %4s %6s %10s %9s %13s %9s %8s %7s\n",
         "round","n","pass%","wall(max)","mean_tot","conflict(max)","mean_cnf","retries","stalls"
  printf "%s\n", "----------------------------------------------------------------------------------------"
  pmw=-1; pmc=-1
  for (i=1;i<=nr;i++){
    r=rounds[i]; cnt=n[r]
    mt=sumt[r]/cnt; mc=sumc[r]/cnt; pr=(pass[r]+0)/cnt*100
    # round-over-round delta for the two headline costs (negative = faster = better)
    dwall=(i==1)?"" :sprintf(" %+.0f", maxt[r]-pmw)
    dconf=(i==1)?"" :sprintf(" %+.0f", maxc[r]-pmc)
    printf "%-6s %4d %5.0f%% %7.0f%-3s %8.0f %9.0f%-4s %8.0f %8d %7d\n",
           r, cnt, pr, maxt[r], dwall, mt, maxc[r], dconf, mc, sumret[r], sumstl[r]
    pmw=maxt[r]; pmc=maxc[r]
  }
  print ""
  print "wall(max) = batch wall-clock (slowest agent finishing); conflict(max) = worst conflict time."
  print "The +/- after wall(max) and conflict(max) is the change vs the previous round: NEGATIVE = faster = better."
}' "$file"
