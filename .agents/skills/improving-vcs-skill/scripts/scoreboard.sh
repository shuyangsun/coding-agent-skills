#!/usr/bin/env bash
#
# Aggregate the metrics log so you can SEE whether a vcs-skill revision moved the
# numbers. Prints three views:
#
#   1. BY ROUND (trend) — the two first-class costs the loop drives down, batch
#      wall-clock and (above all) conflict-resolution time, with the
#      round-over-round delta (- = improved). Batch wall-clock is the MAX
#      per-agent total in a round (a parallel batch is done when its slowest
#      agent is).
#   2. BY MODEL TIER — pass%, mean/worst time, and conflict cost per capability
#      tier (large / mid / small). Different-sized models behave very differently
#      on big conflicts; a vcs revision that only works for large models has NOT
#      met the bar. This view is how you tell.
#   3. DIFFICULTY x TIER pass-rate matrix — where exactly things break (e.g.
#      small models pass easy but fail hard).
#
# Usage: scoreboard.sh [--file PATH]
set -euo pipefail
file="${VCS_HARNESS_DIR:-${TMPDIR:-/tmp}/vcs-harness}/metrics.tsv"
[[ "${1:-}" == "--file" ]] && file="${2:?--file needs a path}"
[[ -f "$file" ]] || {
  echo "no metrics yet at $file (record some with record-metrics.sh)" >&2
  exit 1
}
command -v python3 >/dev/null 2>&1 || {
  echo "scoreboard.sh: python3 required" >&2
  exit 2
}

python3 - "$file" <<'PY'
import sys, csv

rows = []
with open(sys.argv[1], newline="") as fh:
    for r in csv.DictReader(fh, delimiter="\t"):
        rows.append(r)
if not rows:
    print("metrics file has no data rows yet.")
    sys.exit(0)

def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0

def rkey(r):
    try:
        return int(r["round"])
    except (TypeError, ValueError):
        return 0

def iso_cell(group):
    # session-start isolation: '-' if not measured in this group (integration
    # rounds), else the COUNT of isolation failures (want 0).
    measured = [x for x in group if x.get("isolate") in ("pass", "fail", "partial")]
    if not measured:
        return "-"
    return str(sum(1 for x in measured if x.get("isolate") != "pass"))

# ---- 1. by round (trend) ---------------------------------------------------
rounds = {}
for r in rows:
    rounds.setdefault(r["round"], []).append(r)

print("== BY ROUND (trend: lower is better; delta vs previous round) ==")
print(f"{'round':<6}{'diff':<8}{'n':>3}{'pass%':>7}{'wall(max)':>11}{'d':>6}"
      f"{'mean_tot':>10}{'conf(max)':>11}{'d':>6}{'mean_cnf':>10}{'mean_tok':>10}"
      f"{'stale':>6}{'iso':>5}{'retr':>6}{'stall':>6}")
print("-" * 117)
prev_w = prev_c = None
for rd in sorted(rounds, key=lambda x: int(x) if x.isdigit() else 0):
    g = rounds[rd]
    n = len(g)
    diffs = sorted({x["difficulty"] for x in g if x.get("difficulty", "-") != "-"})
    diff = ",".join(diffs) if diffs else "-"
    passes = sum(1 for x in g if x["quality"] == "pass")
    tot = [num(x["total_s"]) for x in g]
    cnf = [num(x["conflict_s"]) for x in g]
    tok = [num(x.get("tokens", 0)) for x in g]
    stale = sum(num(x.get("stale_refs", 0)) for x in g)
    wmax, cmax = max(tot), max(cnf)
    dw = "" if prev_w is None else f"{wmax - prev_w:+.0f}"
    dc = "" if prev_c is None else f"{cmax - prev_c:+.0f}"
    print(f"{rd:<6}{diff:<8}{n:>3}{passes / n * 100:>6.0f}%{wmax:>11.0f}{dw:>6}"
          f"{sum(tot) / n:>10.0f}{cmax:>11.0f}{dc:>6}{sum(cnf) / n:>10.0f}{sum(tok) / n:>10.0f}"
          f"{stale:>6.0f}{iso_cell(g):>5}{sum(num(x['retries']) for x in g):>6.0f}{sum(num(x['stalls']) for x in g):>6.0f}")
    prev_w, prev_c = wmax, cmax

# ---- 2. by model tier ------------------------------------------------------
tiers = {}
for r in rows:
    tiers.setdefault(r.get("tier", "-") or "-", []).append(r)
order = {"large": 0, "mid": 1, "small": 2}
print("\n== BY MODEL TIER (vendor-agnostic capability tier) ==")
print(f"{'tier':<8}{'n':>3}{'pass%':>7}{'mean_tot':>10}{'conf(max)':>11}{'mean_cnf':>10}"
      f"{'mean_tok':>10}{'stale':>6}{'iso':>5}{'retr':>6}{'stall':>6}")
print("-" * 82)
for t in sorted(tiers, key=lambda x: (order.get(x, 9), x)):
    g = tiers[t]
    n = len(g)
    passes = sum(1 for x in g if x["quality"] == "pass")
    tot = [num(x["total_s"]) for x in g]
    cnf = [num(x["conflict_s"]) for x in g]
    tok = [num(x.get("tokens", 0)) for x in g]
    stale = sum(num(x.get("stale_refs", 0)) for x in g)
    print(f"{t:<8}{n:>3}{passes / n * 100:>6.0f}%{sum(tot) / n:>10.0f}"
          f"{max(cnf):>11.0f}{sum(cnf) / n:>10.0f}{sum(tok) / n:>10.0f}{stale:>6.0f}{iso_cell(g):>5}"
          f"{sum(num(x['retries']) for x in g):>6.0f}{sum(num(x['stalls']) for x in g):>6.0f}")

# ---- 3. difficulty x tier pass-rate matrix ---------------------------------
cell = {}
diffs_seen, tiers_seen = set(), set()
for r in rows:
    d = r.get("difficulty", "-") or "-"
    t = r.get("tier", "-") or "-"
    diffs_seen.add(d)
    tiers_seen.add(t)
    c = cell.setdefault((d, t), [0, 0])
    c[1] += 1
    if r["quality"] == "pass":
        c[0] += 1
dorder = {"easy": 0, "medium": 1, "hard": 2}
torder = {"large": 0, "mid": 1, "small": 2}
dcols = sorted(diffs_seen, key=lambda x: (dorder.get(x, 9), x))
trows = sorted(tiers_seen, key=lambda x: (torder.get(x, 9), x))
print("\n== PASS-RATE MATRIX (rows = model tier, cols = difficulty) ==")
corner = "tier\\diff"
print(f"{corner:<10}" + "".join(f"{d:>10}" for d in dcols))
print("-" * (10 + 10 * len(dcols)))
for t in trows:
    line = f"{t:<10}"
    for d in dcols:
        c = cell.get((d, t))
        line += f"{(str(round(c[0] / c[1] * 100)) + '%' if c else '-'):>10}"
    print(line)

print("\nwall(max)=batch wall-clock (slowest agent); conf(max)=worst conflict time.")
print("mean_tok=mean output tokens/agent (efficiency; lower=better). stale=merged")
print("agent-* refs left undeleted across the group (branch/bookmark hygiene; want 0).")
print("iso=session-start isolation failures in the group (start rounds only; want 0;")
print("'-' = not measured, i.e. integration rounds). Round delta 'd': NEGATIVE =")
print("faster = better. Watch conf(max) above all. If a tier or a difficulty x tier")
print("cell lags, that is where vcs must improve.")
PY
