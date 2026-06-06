#!/usr/bin/env bash
#
# Objectively score the INTEGRATED result of one harness round, independent of
# what the sub-agents claim. Reads the round's manifest.env + spec.json (written
# by new-sandbox.sh) and inspects the `main` integration ref.
#
# Because every agent's change was pre-made deterministically, the CORRECT merged
# result is deterministic too — so this does more than "no markers": it verifies
# the resolution is actually right.
#
# VCS-level checks (this script):
#   1. mode integrity   — a Git-only sandbox must contain no .jj (the agent must
#                         not have reached for jj); a jj sandbox must keep .jj.
#   2. no conflict markers on `main` (Git AND jj both fence with <<<<<<< / >>>>>>>).
#   3. no unresolved    — Git: the integration tree has no marker (a conflicted
#                         merge can't be published); jj: no conflicted commit in
#                         `::main` (jj will happily COMMIT a conflict).
#   4. every sentinel ticket present on `main` (quick lost-work tripwire).
#
# Resolution-quality oracle (scenario.py check): union preserved with no dups or
# lost work, the same-line tie-break resolved to the correct value, structured
# files (JSON / Python / YAML) still parse, and files no agent touched are
# byte-identical to baseline (catches "extra work" / clobber).
#
# The round PASSES only if every check AND the oracle pass.
#
# Usage: check-quality.sh <round-dir>
# Exit:  0 = PASS, 1 = FAIL, 2 = usage / setup error.
set -uo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
scenario="$here/scenario.py"

round_dir="${1:-}"
[[ -n "$round_dir" && -f "$round_dir/manifest.env" ]] ||
  {
    echo "usage: check-quality.sh <round-dir>  (a dir containing manifest.env)" >&2
    exit 2
  }
# shellcheck disable=SC1091
source "$round_dir/manifest.env"
repo="$REPO"
gitdir="${SCORE_GITDIR:-$repo/.git}"
ref="${SCORE_REF:-${INTEGRATION_REF:-main}}"
spec="${SPEC:-$round_dir/spec.json}"

fail=0
note_fail() {
  echo "  FAIL: $*"
  fail=1
}
echo "== quality report: round $ROUND ($MODE, ${DIFFICULTY:-?}) =="

# jj is colocated; force its bookmarks out to Git refs so the Git-based scans see
# the latest integration state.
if [[ "$MODE" == "jj" && -d "$repo/.jj" ]]; then
  jj -R "$repo" git export >/dev/null 2>&1 || true
fi

git --git-dir="$gitdir" rev-parse --verify -q "$ref" >/dev/null 2>&1 ||
  {
    echo "  FAIL: integration ref '$ref' does not exist in $gitdir"
    echo "RESULT: FAIL"
    exit 1
  }

# Materialize the integrated tree once; all content scans read from here.
tree="$(mktemp -d)"
trap 'rm -rf "$tree"' EXIT
git --git-dir="$gitdir" archive --format=tar "$ref" | tar -x -C "$tree" 2>/dev/null ||
  note_fail "could not materialize tree at $ref"

# 1. mode integrity ---------------------------------------------------------
if [[ "$MODE" == "git" ]]; then
  if [[ -e "$repo/.jj" ]]; then
    note_fail "Git-only sandbox contains .jj — an agent wrongly reached for jj."
  else
    echo "  ok: Git-only sandbox, no .jj present."
  fi
else
  if [[ -d "$repo/.jj" ]]; then
    echo "  ok: jj sandbox retains .jj."
  else
    note_fail "jj sandbox lost its .jj directory."
  fi
fi

# 1b. jj WORKFLOW integrity (verify, don't assert) --------------------------
# .jj surviving is necessary but NOT sufficient: in a colocated repo plain git
# also "works", so an agent can integrate with git and leave .jj untouched and
# the Git-ref scans below would still pass — a false success that hides a mode
# violation. Advancing `main` THROUGH jj always records a "point/move bookmark
# main" operation in the op log; the seed creates `main` once but never moves
# it, and a pure-git integration only triggers benign import/export/snapshot
# ops. So the absence of any main-advancing jj op means git was used where jj
# was required. (This assumes the seed never moves `main` — keep it that way.)
if [[ "$MODE" == "jj" && -d "$repo/.jj" ]]; then
  moved="$(jj -R "$repo" op log --no-graph -T 'description.first_line() ++ "\n"' 2>/dev/null |
    grep -cE '(point|move) bookmark main\b' || true)"
  if [[ "${moved:-0}" -gt 0 ]]; then
    echo "  ok: 'main' advanced through jj ($moved bookmark op(s)) — jj workflow used."
  else
    note_fail "jj round not integrated through jj: 'main' never advanced via a jj operation (git was used in the colocated repo)."
  fi
fi

# 2. conflict markers on the integrated tree --------------------------------
markers="$(grep -rnE '^(<<<<<<<|>>>>>>>|\|\|\|\|\|\|\|)' "$tree" 2>/dev/null || true)"
if [[ -n "$markers" ]]; then
  note_fail "conflict markers left on $ref:"
  printf '%s\n' "$markers" | sed "s#$tree/##; s/^/        /" | head -20
else
  echo "  ok: no conflict markers on $ref."
fi

# 3. unresolved conflicts ---------------------------------------------------
if [[ "$MODE" == "git" ]]; then
  # A conflicted Git merge cannot be published to the shared ref; leftover
  # markers (check 2) are the observable failure. Report the primary worktree's
  # index state too, in case a half-finished merge was left behind locally.
  unmerged="$(git -C "$repo" ls-files -u 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "$unmerged" != "0" ]]; then
    echo "  note: primary worktree has $unmerged unmerged index entry(ies) (local, not on $ref)."
  fi
  echo "  ok: integration ref published without conflict markers."
else
  conflicted="$(jj -R "$repo" log --no-graph -r "::$ref" -T 'if(conflict, "x", "")' 2>/dev/null | tr -d '\n')"
  if [[ -n "$conflicted" ]]; then
    note_fail "jj history reaching $ref contains ${#conflicted} conflicted commit(s)."
  else
    echo "  ok: no conflicted commits in ::$ref."
  fi
fi

# 4. quick lost-work tripwire (independent of the oracle) -------------------
missing=""
for tok in $TOKENS; do
  grep -rqF "$tok" "$tree" 2>/dev/null || missing="${missing:+$missing }$tok"
done
if [[ -n "$missing" ]]; then
  note_fail "sentinel(s) absent from $ref (clobbered or never integrated): $missing"
else
  echo "  ok: all ${AGENTS} agent sentinels present on $ref."
fi

# 5. resolution-quality oracle ----------------------------------------------
echo "  -- resolution oracle (scenario.py check) --"
if [[ -f "$spec" ]]; then
  if python3 "$scenario" check --dir "$tree" --spec "$spec" | sed 's/^/  /'; then
    :
  else
    note_fail "resolution oracle reported defects (see above)."
  fi
else
  note_fail "spec.json not found at $spec — cannot run the resolution oracle."
fi

# history shape (informational) ---------------------------------------------
commits="$(git --git-dir="$gitdir" rev-list --count "$ref" 2>/dev/null || echo '?')"
merges="$(git --git-dir="$gitdir" rev-list --count --merges "$ref" 2>/dev/null || echo '?')"
echo "  info: $ref has $commits commit(s), $merges merge(s)."

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "RESULT: PASS"
  exit 0
else
  echo "RESULT: FAIL"
  exit 1
fi
