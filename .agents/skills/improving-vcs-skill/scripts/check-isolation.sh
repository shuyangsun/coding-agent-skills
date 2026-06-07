#!/usr/bin/env bash
#
# Objectively score SESSION-START ISOLATION for one `--task start` harness round,
# independent of what the sub-agent claims. The start task drops an agent into a
# SHARED repo and asks it to author one tiny change and land it on `main`; what's
# under test is whether the agent ISOLATED first — did its work in its OWN
# worktree (git) / workspace (jj) instead of the shared primary checkout — so
# co-located agents on one machine don't trample each other.
#
# This scorer is SEPARATE from check-quality.sh (which scores that the change and
# the branch cleanup landed correctly). Run BOTH on a start round. Like the
# hygiene metric, isolation is reported as its own line so "did the work, but in
# the shared checkout" reads as an isolation miss, not a correctness one.
#
# The signals are DURABLE (survive the agent's own cleanup — worktree removal,
# branch/bookmark deletion, `jj workspace forget`):
#   git: the PRIMARY worktree's HEAD reflog (`$REPO/.git/logs/HEAD`) line count.
#        If the agent worked in its own worktree it stays at the seed value
#        (SEED_HEAD_LINES); if it committed/switched in the shared primary
#        checkout it grows. (Verified: `worktree add`, the agent's commits in the
#        new worktree, worktree removal, and branch -d all leave it untouched.)
#   jj:  the op log's `add workspace '<name>'` entries (append-only). The seed
#        only ever adds the names in SEED_WS; any OTHER workspace-add is the agent
#        carving out its own working copy.
#
# Two arms (manifest START_FROM):
#   main      the agent began in the shared primary checkout → it MUST isolate.
#   worktree  the agent was GIVEN its own worktree/workspace already → it must
#             work in place and NOT create a redundant nested one (over-isolate).
#
# Usage: check-isolation.sh <round-dir>
# Exit:  0 = ISOLATED pass, 1 = fail, 2 = usage / not a start round.
#        (Prints ISOLATED / ISO_FS / OVER_ISOLATE lines for the metrics layer.)
set -uo pipefail

here="$(cd "$(dirname "$0")" && pwd)"

round_dir="${1:-}"
[[ -n "$round_dir" && -f "$round_dir/manifest.env" ]] ||
  {
    echo "usage: check-isolation.sh <round-dir>  (a dir containing manifest.env)" >&2
    exit 2
  }
# shellcheck disable=SC1091
source "$round_dir/manifest.env"

[[ "${TASK:-integrate}" == "start" ]] ||
  {
    echo "check-isolation.sh: round ${ROUND:-?} is TASK=${TASK:-integrate}, not 'start' — nothing to score." >&2
    echo "ISOLATED=n/a"
    exit 2
  }

repo="$REPO"
gitdir="${SCORE_GITDIR:-$repo/.git}"
ref="${SCORE_REF:-${INTEGRATION_REF:-main}}"
arm="${START_FROM:-main}"

echo "== isolation report: round $ROUND ($MODE, start-from $arm) =="

# jj is colocated; export so the git-ref scans see the latest state.
if [[ "$MODE" == "jj" && -d "$repo/.jj" ]]; then
  jj -R "$repo" git export >/dev/null 2>&1 || true
fi

# --- did the work actually land on main? (sentinel tripwire) ----------------
work_landed="no"
if git --git-dir="$gitdir" rev-parse --verify -q "$ref" >/dev/null 2>&1; then
  tree="$(mktemp -d)"
  trap 'rm -rf "$tree"' EXIT
  if git --git-dir="$gitdir" archive --format=tar "$ref" 2>/dev/null | tar -x -C "$tree" 2>/dev/null; then
    work_landed="yes"
    for tok in ${TOKENS:-}; do
      grep -rqF "$tok" "$tree" 2>/dev/null || work_landed="no"
    done
  fi
fi

iso_fs="n/a"
over_isolate="n/a"
verdict_fail=0
detail=()

if [[ "$MODE" == "git" ]]; then
  # Filesystem isolation = the agent did NOT touch the shared primary checkout.
  # The primary HEAD reflog only grows on HEAD-MUTATING ops there — commit,
  # switch/checkout, reset — every one of which disturbs the shared working copy a
  # co-located peer relies on, so flagging them is intended, not a false fail.
  # Read-only sync (git fetch, status, log, diff) does NOT touch this reflog, so
  # the canonical isolate flow (fetch in primary, then `git worktree add`) scores
  # pass — vcs's ISOLATE.md guidance and this check agree. (A `git gc`/reflog
  # expire empties the log to 0, which is != the seed count, so it still fails.)
  seed_lines="${SEED_HEAD_LINES:-1}"
  cur_lines="$(wc -l <"$repo/.git/logs/HEAD" 2>/dev/null | tr -d ' ')"
  cur_lines="${cur_lines:-0}"
  wt_count="$(git -C "$repo" worktree list --porcelain 2>/dev/null | grep -c '^worktree ')"
  branches="$(git --git-dir="$repo/.git" for-each-ref --format='%(refname:short)' 'refs/heads/*' 2>/dev/null | tr '\n' ' ')"

  if [[ "$cur_lines" == "$seed_lines" ]]; then
    iso_fs="pass"
    detail+=("primary checkout untouched (HEAD reflog $cur_lines == seed $seed_lines): work was done in a separate worktree")
  else
    iso_fs="fail"
    detail+=("primary checkout WAS used (HEAD reflog grew $seed_lines -> $cur_lines): agent worked in the shared checkout, not its own worktree")
  fi
  detail+=("live worktrees: $wt_count; local branches: ${branches:-<none>}")

  if [[ "$arm" == "worktree" ]]; then
    # It was handed exactly one worktree (primary + ws-agent-1 = 2). A 3rd is
    # redundant nested isolation. Branches beyond {main, GIVEN_BRANCH} corroborate.
    given_branch="${GIVEN_BRANCH:-agent-1}"
    extra_b=""
    for b in $branches; do
      [[ "$b" == "main" || "$b" == "$given_branch" ]] && continue
      extra_b="${extra_b:+$extra_b }$b"
    done
    if [[ "$wt_count" -gt 2 || -n "$extra_b" ]]; then
      over_isolate="yes"
      detail+=("OVER-ISOLATED: created a redundant worktree/branch though it was already given one (worktrees=$wt_count, extra branches: ${extra_b:-none})")
    else
      over_isolate="no"
    fi
  fi
else
  # jj: filesystem isolation = an `add workspace` for a name not seeded.
  seed_ws=" ${SEED_WS:-default} "
  adds="$(jj -R "$repo" op log --no-graph -T 'description.first_line() ++ "\n"' 2>/dev/null |
    sed -n "s/^add workspace '\(.*\)'.*/\1/p")"
  agent_ws=""
  for w in $adds; do
    [[ "$seed_ws" == *" $w "* ]] && continue
    agent_ws="${agent_ws:+$agent_ws }$w"
  done

  if [[ "$arm" == "main" ]]; then
    if [[ -n "$agent_ws" ]]; then
      iso_fs="pass"
      detail+=("agent created its own workspace(s): $agent_ws (op log 'add workspace')")
    else
      iso_fs="fail"
      detail+=("no agent workspace-add in the op log: agent worked in the shared 'default' workspace")
    fi
  else
    # worktree arm: handed 'agent-1' already; any further add is over-isolation.
    if [[ -n "$agent_ws" ]]; then
      over_isolate="yes"
      detail+=("OVER-ISOLATED: added workspace(s) $agent_ws though it was already given one (seed workspaces: ${SEED_WS:-default})")
    else
      over_isolate="no"
      detail+=("stayed in the workspace it was given (no extra 'add workspace' ops)")
    fi
  fi
fi

# --- overall verdict --------------------------------------------------------
# pass requires: the change landed, AND (on-main) the agent isolated, AND
# (worktree) it did not redundantly over-isolate.
[[ "$work_landed" == "yes" ]] || verdict_fail=1
if [[ "$arm" == "main" ]]; then
  [[ "$iso_fs" == "pass" ]] || verdict_fail=1
else
  [[ "$over_isolate" == "no" ]] || verdict_fail=1
  [[ "$iso_fs" == "fail" ]] && verdict_fail=1 # touched the shared primary checkout
fi

for d in "${detail[@]:-}"; do [[ -n "$d" ]] && echo "  - $d"; done
echo "  WORK_LANDED=$work_landed"
echo "  ISO_FS=$iso_fs"
echo "  OVER_ISOLATE=$over_isolate"
if [[ "$verdict_fail" -eq 0 ]]; then
  echo "  ISOLATED=pass"
  exit 0
else
  echo "  ISOLATED=fail"
  exit 1
fi
