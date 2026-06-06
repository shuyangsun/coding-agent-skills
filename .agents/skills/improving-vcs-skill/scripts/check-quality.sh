#!/usr/bin/env bash
#
# Objectively score the INTEGRATED result of one harness round, independent of
# what the sub-agents claim. Reads the round's manifest.env (written by
# new-sandbox.sh) and inspects the `main` integration ref of the sandbox repo.
#
# Four objective checks — the round PASSES only if all hold:
#   1. mode integrity   — a Git-only sandbox must contain no .jj (the agent must
#                         not have reached for jj); a jj sandbox must keep .jj.
#   2. no conflict markers on `main` — catches conflicts silenced into the tree
#                         (Git AND jj both fence conflicts with <<<<<<< / >>>>>>>).
#   3. no lost work     — every agent's sentinel ticket (TOKENS) must survive on
#                         `main`; a missing one means a teammate's change was
#                         clobbered or never integrated.
#   4. no unresolved    — Git: no unmerged index entries; jj: no conflicted commit
#                         in `::main`.
# History shape (commit / merge counts) is printed for human judgment.
#
# Works in both modes: the jj sandbox is colocated, so `main` is also a Git ref
# and the content scans go through Git in both cases (after a jj ref export).
#
# Usage: check-quality.sh <round-dir>
# Exit:  0 = PASS, 1 = FAIL, 2 = usage / setup error.
set -uo pipefail

round_dir="${1:-}"
[[ -n "$round_dir" && -f "$round_dir/manifest.env" ]] ||
  {
    echo "usage: check-quality.sh <round-dir>  (a dir containing manifest.env)" >&2
    exit 2
  }
# shellcheck disable=SC1091
source "$round_dir/manifest.env"
repo="$REPO"
ref="${INTEGRATION_REF:-main}"

fail=0
note_fail() {
  echo "  FAIL: $*"
  fail=1
}
echo "== quality report: round $ROUND ($MODE) =="

# jj is colocated; force its bookmarks out to Git refs so the Git-based scans
# below see the latest integration state.
if [[ "$MODE" == "jj" && -d "$repo/.jj" ]]; then
  jj -R "$repo" git export >/dev/null 2>&1 || true
fi

git -C "$repo" rev-parse --verify -q "$ref" >/dev/null 2>&1 ||
  {
    echo "  FAIL: integration ref '$ref' does not exist in $repo"
    echo "RESULT: FAIL"
    exit 1
  }

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

# 2. conflict markers on `main` --------------------------------------------
# <<<<<<< / >>>>>>> fence conflicts in both Git and jj's materialized form.
markers="$(git -C "$repo" grep -nE '^(<<<<<<<|>>>>>>>)' "$ref" -- . 2>/dev/null || true)"
if [[ -n "$markers" ]]; then
  note_fail "conflict markers left on $ref:"
  printf '%s\n' "$markers" | sed 's/^/        /' | head -20
else
  echo "  ok: no conflict markers on $ref."
fi

# 3. lost work: every sentinel ticket must survive on `main` -----------------
missing=""
for tok in $TOKENS; do
  git -C "$repo" grep -qF "$tok" "$ref" -- . 2>/dev/null || missing="${missing:+$missing }$tok"
done
if [[ -n "$missing" ]]; then
  note_fail "sentinel(s) absent from $ref (clobbered or never integrated): $missing"
else
  echo "  ok: all ${AGENTS} agent sentinels present on $ref."
fi

# 4. unresolved conflicts ---------------------------------------------------
if [[ "$MODE" == "git" ]]; then
  unmerged="$(git -C "$repo" ls-files -u 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "$unmerged" != "0" ]]; then
    note_fail "Git index has unmerged entries ($unmerged)."
  else
    echo "  ok: Git index has no unmerged entries."
  fi
else
  conflicted="$(jj -R "$repo" log --no-graph -r "::$ref" -T 'if(conflict, "x", "")' 2>/dev/null | tr -d '\n')"
  if [[ -n "$conflicted" ]]; then
    note_fail "jj history reaching $ref contains ${#conflicted} conflicted commit(s)."
  else
    echo "  ok: no conflicted commits in ::$ref."
  fi
fi

# history shape (informational) ---------------------------------------------
commits="$(git -C "$repo" rev-list --count "$ref" 2>/dev/null || echo '?')"
merges="$(git -C "$repo" rev-list --count --merges "$ref" 2>/dev/null || echo '?')"
echo "  info: $ref has $commits commit(s), $merges merge(s)."

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "RESULT: PASS"
  exit 0
else
  echo "RESULT: FAIL"
  exit 1
fi
