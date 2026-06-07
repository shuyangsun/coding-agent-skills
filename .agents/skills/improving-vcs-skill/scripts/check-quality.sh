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
# Separately, hygiene/lifecycle metrics are reported (not folded into the
# correctness RESULT): branch/bookmark cleanup (`STALE_REFS`), jj default
# workspace readiness (`DEFAULT_OK`), and retired jj workspace teardown
# (`ORPHAN_WS` / `ORPHAN_DIRS`). The exit bar (METRICS.md) wants all of them clean.
#
# Usage: check-quality.sh <round-dir>
# Exit:  0 = PASS, 1 = FAIL, 2 = usage / setup error.  (RESULT = correctness only;
#        hygiene/lifecycle metrics are reported for the metrics layer to record.)
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
# the latest integration state. Use --ignore-working-copy so a deliberately stale
# default workspace does not prevent the correctness oracle from inspecting main;
# default readiness is scored separately below.
if [[ "$MODE" == "jj" && -d "$repo/.jj" ]]; then
  jj -R "$repo" --ignore-working-copy git export >/dev/null 2>&1 || true
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
  moved="$(jj -R "$repo" --ignore-working-copy op log --no-graph -T 'description.first_line() ++ "\n"' 2>/dev/null |
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
  conflicted="$(jj -R "$repo" --ignore-working-copy log --no-graph -r "::$ref" -T 'if(conflict, "x", "")' 2>/dev/null | tr -d '\n')"
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

# 6. branch/bookmark hygiene (stale-ref metric) -----------------------------
# After a clean integration each agent's `agent-K` branch/bookmark is merged into
# main and redundant; vcs tells the agent to delete it UNLESS it backs an open PR
# (listed in PR_BACKED — kept on purpose). We report this as its own metric
# (STALE_REFS=N + a HYGIENE verdict), independent of the correctness RESULT above,
# so resolution quality and repo hygiene stay separable on the scoreboard.
#
# Scan local agent-* refs in the repo's own .git. jj is colocated and we ran
# `jj git export` up top, so a deleted bookmark has no ref here either — the same
# git-ref scan is authoritative in both modes.
pr_backed=" ${PR_BACKED:-} "
surviving=()
while IFS= read -r b; do
  [[ -n "$b" ]] && surviving+=("$b")
done < <(git --git-dir="$repo/.git" for-each-ref --format='%(refname:short)' 'refs/heads/agent-*' 2>/dev/null |
  grep -E '^agent-[0-9]+$' || true)
stale=0 kept_pr=0 missing_pr=0
stale_list="" missing_list=""
for b in "${surviving[@]:-}"; do
  [[ -n "$b" ]] || continue
  k="${b#agent-}"
  if [[ "$pr_backed" == *" $k "* ]]; then
    kept_pr=$((kept_pr + 1))
  else
    stale=$((stale + 1)); stale_list="${stale_list:+$stale_list }$b"
  fi
done
for k in ${PR_BACKED:-}; do
  printf '%s\n' "${surviving[@]:-}" | grep -qxF "agent-$k" ||
    { missing_pr=$((missing_pr + 1)); missing_list="${missing_list:+$missing_list }agent-$k"; }
done
echo "  -- branch/bookmark hygiene (stale-ref metric) --"
echo "  STALE_REFS=$stale"
echo "  STALE_LIST=$stale_list"  # machine-readable: which agent-K were left behind
if [[ "$stale" -eq 0 && "$missing_pr" -eq 0 ]]; then
  echo "  HYGIENE: PASS — no merged agent-* ref left behind${PR_BACKED:+ ($kept_pr PR-backed ref(s) correctly kept)}"
else
  [[ "$stale" -gt 0 ]] && echo "  HYGIENE: FAIL — $stale merged branch/bookmark(s) not deleted: $stale_list"
  [[ "$missing_pr" -gt 0 ]] && echo "  HYGIENE: FAIL — PR-backed ref(s) wrongly deleted: $missing_list"
fi

# 7. jj default workspace lifecycle + retired workspace cleanup --------------
# These are measured separately from content correctness for the multi-workspace
# failure mode documented in docs/issues/0001:
#   - DEFAULT_OK: the `default` workspace is usable at the end, not stale, and is
#     parked on latest `main` (the consolidate-and-push starting point).
#   - ORPHAN_WS / ORPHAN_DIRS: retired per-agent jj workspaces were forgotten and
#     their on-disk directories removed once their work landed.
if [[ "$MODE" == "jj" && -d "$repo/.jj" && "${TASK:-integrate}" == "integrate" ]]; then
  default_ok="fail"
  default_status="error"
  default_parent="unknown"
  default_detail=""

  if default_out="$(jj -R "$repo" st 2>&1)"; then
    default_status="usable"
  elif printf '%s\n' "$default_out" | grep -qi 'working copy is stale'; then
    default_status="stale"
    default_detail="default workspace is still stale; run jj workspace update-stale there"
  else
    default_status="error"
    default_detail="$(printf '%s\n' "$default_out" | head -1)"
  fi

  main_id="$(jj -R "$repo" --ignore-working-copy log --no-graph -r main -T 'commit_id ++ "\n"' 2>/dev/null | head -1)"
  parent_ids="$(jj -R "$repo" --ignore-working-copy log --no-graph -r 'default@-' -T 'commit_id ++ "\n"' 2>/dev/null || true)"
  parent_count="$(printf '%s\n' "$parent_ids" | sed '/^$/d' | wc -l | tr -d ' ')"
  if [[ -n "$main_id" && "$parent_count" == "1" ]] && printf '%s\n' "$parent_ids" | grep -qxF "$main_id"; then
    default_parent="main"
  else
    default_parent="other"
    [[ -z "$default_detail" ]] && default_detail="default workspace is not parked on main; run jj new main after stale recovery"
  fi
  if [[ "$default_status" == "usable" && "$default_parent" == "main" ]]; then
    default_ok="pass"
    default_detail="default usable and parked on main"
  fi

  echo "  -- jj default workspace lifecycle --"
  echo "  DEFAULT_OK=$default_ok"
  echo "  DEFAULT_STATUS=$default_status"
  echo "  DEFAULT_PARENT=$default_parent"
  echo "  DEFAULT_DETAIL=$default_detail"

  orphan_ws=0
  orphan_dirs=0
  orphan_ws_list=""
  orphan_dir_list=""
  ws_listing="$(jj -R "$repo" --ignore-working-copy workspace list -T 'name ++ "\t" ++ root ++ "\n"' 2>/dev/null || true)"
  for ((k = 1; k <= AGENTS; k++)); do
    name="agent-$k"
    if printf '%s\n' "$ws_listing" | cut -f1 | grep -qxF "$name"; then
      orphan_ws=$((orphan_ws + 1))
      orphan_ws_list="${orphan_ws_list:+$orphan_ws_list }$name"
    fi
    ws_var="WS_$k"
    ws_path="${!ws_var:-}"
    if [[ -n "$ws_path" && "$ws_path" != "$repo" && -d "$ws_path" ]]; then
      orphan_dirs=$((orphan_dirs + 1))
      orphan_dir_list="${orphan_dir_list:+$orphan_dir_list }$name"
    fi
  done
  echo "  -- jj retired workspace hygiene --"
  echo "  ORPHAN_WS=$orphan_ws"
  echo "  ORPHAN_WS_LIST=$orphan_ws_list"
  echo "  ORPHAN_DIRS=$orphan_dirs"
  echo "  ORPHAN_DIR_LIST=$orphan_dir_list"

  # Orphan empty side-heads (docs/issues/0007): anonymous empty, description-less
  # commits with no bookmark, not on main, that no live workspace's working copy
  # points at — cleanup residue from a forgotten workspace whose empty commit was
  # pinned by a since-deleted bookmark. Same conservative predicate the vcs helper
  # uses to abandon them, so a clean finish reports 0 here.
  orphan_empty=0
  orphan_empty_list=""
  wc_set=""
  for ws in $(jj -R "$repo" --ignore-working-copy workspace list -T 'name ++ "\n"' 2>/dev/null); do
    cid="$(jj -R "$repo" --ignore-working-copy log --no-graph -r "${ws}@" -T 'commit_id ++ "\n"' 2>/dev/null | head -1)"
    [[ -n "$cid" ]] && wc_set="$wc_set $cid "
  done
  while IFS=$'\t' read -r cid flags; do
    [[ -n "$cid" ]] || continue
    [[ "$flags" == "Ex" ]] || continue
    [[ "$wc_set" == *" $cid "* ]] && continue
    orphan_empty=$((orphan_empty + 1))
    orphan_empty_list="${orphan_empty_list:+$orphan_empty_list }${cid:0:12}"
  done < <(jj -R "$repo" --ignore-working-copy log --no-graph \
    -r 'heads(all()) ~ ::main ~ bookmarks()' \
    -T 'commit_id ++ "\t" ++ if(empty,"E","x") ++ if(description,"D","x") ++ "\n"' 2>/dev/null)
  echo "  ORPHAN_EMPTY_HEADS=$orphan_empty"
  echo "  ORPHAN_EMPTY_LIST=$orphan_empty_list"

  if [[ "$orphan_ws" -eq 0 && "$orphan_dirs" -eq 0 && "$orphan_empty" -eq 0 ]]; then
    echo "  WORKSPACE_HYGIENE: PASS — no retired agent workspace entry, directory, or orphan empty side-head left behind"
  else
    [[ "$orphan_ws" -gt 0 ]] && echo "  WORKSPACE_HYGIENE: FAIL — workspace entries still registered: $orphan_ws_list"
    [[ "$orphan_dirs" -gt 0 ]] && echo "  WORKSPACE_HYGIENE: FAIL — workspace directories still on disk: $orphan_dir_list"
    [[ "$orphan_empty" -gt 0 ]] && echo "  WORKSPACE_HYGIENE: FAIL — orphan empty side-head(s) left in jj log: $orphan_empty_list"
  fi
else
  echo "  DEFAULT_OK=n/a"
  echo "  ORPHAN_WS=0"
  echo "  ORPHAN_WS_LIST="
  echo "  ORPHAN_DIRS=0"
  echo "  ORPHAN_DIR_LIST="
  echo "  ORPHAN_EMPTY_HEADS=0"
  echo "  ORPHAN_EMPTY_LIST="
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
