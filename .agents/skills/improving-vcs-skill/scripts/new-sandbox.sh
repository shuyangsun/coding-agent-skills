#!/usr/bin/env bash
#
# Provision ONE round's isolated VCS sandbox for the improving-vcs-skill harness.
#
# The harness tests ONLY the version-control aspect of multi-agent collaboration:
# can many agents integrate each other's work and resolve merge conflicts cleanly
# and fast? To remove the variance of agents authoring code, every agent's change
# is PRE-MADE deterministically (by scenario.py) and PRE-COMMITTED on that agent's
# own branch/bookmark (`agent-K`) — a realistic "finished PR". The sub-agent's
# only job is to INTEGRATE `agent-K` onto the shared `main`, resolving the
# conflicts that arise because teammates touched the same files/lines. Because
# every change is deterministic, the correct merged result is deterministic too,
# so check-quality.sh can score resolution quality objectively.
#
# Modes (mode detection is the core thing `vcs` must get right):
#   --mode git   plain Git, no .jj. Per-agent isolation via `git worktree`; the
#                shared integration point is a bare `origin` the agents push to
#                (models Git + worktree and the cloud/PR publish flow).
#   --mode jj    Jujutsu on a Git backend, colocated (.git + .jj; git AND jj both
#                work — so a naive check picks git; `vcs` must prefer jj). Per-agent
#                isolation via `jj workspace add`; shared `main` bookmark, local.
#
# Difficulty ladder (escalating conflict pressure; realistic shapes):
#   --difficulty easy    ~one small union conflict (CHANGELOG) + a disjoint file.
#   --difficulty medium  CHANGELOG + JSON plugin array + handler list (all union)
#                        + a same-line `version` tie-break among a subset.
#   --difficulty hard    all of the above for EVERY agent PLUS a large multi-line
#                        block every agent inserts at the same marker — big,
#                        overlapping, multi-file conflicts with many parallel
#                        agents. This is the stress tier.
#
# Everything lives under one disposable work area outside any real repo
# ($VCS_HARNESS_DIR, default $TMPDIR/vcs-harness), so the harness never pollutes
# the project under test. Tear a round down with rm-sandbox.sh. No paths,
# usernames, or emails are hardcoded to a real person.
#
# Usage:
#   new-sandbox.sh --mode git|jj [--difficulty easy|medium|hard]
#                  [--agents N] [--round N] [--workdir DIR]
#                  [--pr-backed "K K ..."]
#
# --pr-backed lists agent numbers whose branch backs an OPEN remote PR, so its
# local ref must be KEPT after merge (the hygiene metric's carve-out). Git mode
# only: each listed agent-K is pushed to the shared origin to model the PR head;
# jj sandboxes are local (no remote) so the flag is ignored there.
#
# Prints a manifest (also written to <round>/manifest.txt and a shell-sourceable
# <round>/manifest.env that check-quality.sh / rm-sandbox.sh consume).
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
scenario="$here/scenario.py"

# --- args ------------------------------------------------------------------
mode=""
difficulty="medium"
agents=""
round=""
pr_backed=""
workdir="${VCS_HARNESS_DIR:-${TMPDIR:-/tmp}/vcs-harness}"

die() {
  echo "new-sandbox.sh: $*" >&2
  exit 2
}
usage() {
  grep -E '^# (Usage|  )' "$0" | sed 's/^# //'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode) mode="${2:-}"; shift 2 ;;
    --difficulty) difficulty="${2:-}"; shift 2 ;;
    --agents) agents="${2:-}"; shift 2 ;;
    --round) round="${2:-}"; shift 2 ;;
    --pr-backed) pr_backed="${2:-}"; shift 2 ;;
    --workdir) workdir="${2:-}"; shift 2 ;;
    -h | --help) usage 0 ;;
    *) die "unknown arg: $1 (try --help)" ;;
  esac
done

[[ "$mode" == "git" || "$mode" == "jj" ]] || die "--mode must be git or jj"
case "$difficulty" in easy | medium | hard) : ;; *) die "--difficulty must be easy, medium, or hard" ;; esac
command -v python3 >/dev/null 2>&1 || die "python3 required (drives the deterministic content engine)"
[[ -f "$scenario" ]] || die "content engine not found: $scenario"
if [[ "$mode" == "jj" ]] && ! command -v jj >/dev/null 2>&1; then
  die "jj not installed but --mode jj requested"
fi

# Default agent count scales with difficulty (override with --agents).
if [[ -z "$agents" ]]; then
  case "$difficulty" in easy) agents=3 ;; medium) agents=4 ;; hard) agents=6 ;; esac
fi
[[ "$agents" =~ ^[1-9][0-9]*$ ]] || die "--agents must be a positive integer"

# Validate --pr-backed (space-separated agent numbers within range). jj is local
# (no remote PR concept here), so the flag is ignored in jj mode.
if [[ -n "$pr_backed" ]]; then
  for k in $pr_backed; do
    [[ "$k" =~ ^[1-9][0-9]*$ ]] || die "--pr-backed values must be positive integers (got '$k')"
    ((k <= agents)) || die "--pr-backed agent $k exceeds --agents $agents"
  done
  if [[ "$mode" == "jj" ]]; then
    echo "new-sandbox.sh: note: --pr-backed ignored in jj mode (local repo, no remote PR)" >&2
    pr_backed=""
  fi
fi

# Neutral sandbox identity (NOT a real person); also feeds the vcs skill's
# Author-trailer logic, which reads user.name / user.email from the repo.
owner_name="Sandbox Owner"
owner_email="owner@sandbox.invalid"

mkdir -p "$workdir"

# Auto-pick the next round number if not given (max existing round-* + 1).
if [[ -z "$round" ]]; then
  max=0
  for d in "$workdir"/round-*; do
    [[ -d "$d" ]] || continue
    n="${d##*/round-}"
    [[ "$n" =~ ^[0-9]+$ ]] && ((10#$n > max)) && max="$((10#$n))"
  done
  round="$((max + 1))"
fi
[[ "$round" =~ ^[0-9]+$ ]] || die "--round must be an integer"

round_dir="$workdir/round-$round"
[[ -e "$round_dir" ]] && die "round dir already exists: $round_dir (pick another --round or rm-sandbox.sh it)"
repo="$round_dir/repo"
mkdir -p "$repo" "$round_dir/briefs"

# --- deterministic content: seed baseline + write the plan ------------------
python3 "$scenario" seed --repo "$repo" --difficulty "$difficulty"
python3 "$scenario" spec --difficulty "$difficulty" --agents "$agents" --round "$round" \
  --out "$round_dir/spec.json"

# --- per-agent briefs (INTEGRATION ONLY — no code authoring) ----------------
feature_for() { # mirror scenario.py FEATURES order (feature label)
  local feats=("streaming export" "input validation" "registry refresh" \
    "retry backoff" "audit logging" "rate limiting" "cache warmup" "schema migration")
  echo "${feats[$((($1 - 1) % ${#feats[@]}))]}"
}
slug_for() { # mirror scenario.py FEATURES order (commit scope)
  local slugs=("streaming" "validation" "registry" "retry" "audit" "ratelimit" "cache" "schema")
  echo "${slugs[$((($1 - 1) % ${#slugs[@]}))]}"
}

write_brief() {
  local k="$1" ticket="$2" feature="$3" brief="$round_dir/briefs/agent-$k.md"
  cat >"$brief" <<EOF
# Ticket $ticket — land "$feature"

Your change for this ticket is **already written and committed**. In your
workspace it is recorded as \`agent-$k\` (your team labels each person's finished
work that way). You do **not** need to write any code for this ticket.

Several teammates finished their own tickets at the same time and are landing
them on the shared \`main\` line concurrently. Your one job: get your committed
work (\`agent-$k\`) onto \`main\` so mainline history contains it alongside
everyone else's, using your team's standard version-control workflow.

Because teammates touched the same files and lines, you will hit merge conflicts
when you integrate. Resolve them by **union — keep everyone's work**: preserve
every teammate's additive change (every changelog entry, every list/array
element, every code block someone added — never drop one). If a single-valued
field (such as a version number) was set differently by two teammates, keep the
**higher** value. Leave no conflict markers.

**This is a version-control exercise, not a coding one.** To keep the test
focused on integration quality:

- Do **not** write new code, add or modify tests, or "improve" anything.
- Do **not** run the app, a build, formatters, or any test suite to verify it.
- Do **not** amend the contents of your committed change.

Follow your version-control guidance all the way through to a clean finished
state — integrate, resolve every conflict by union, publish onto \`main\`, and do
whatever end-of-integration tidy-up that guidance calls for — then **stop**. You
are measured on a fast, correct integration; there is no coding work to do
afterward.
EOF
  echo "$brief"
}

# --- build the repo in the requested mode -----------------------------------
manifest_env="$round_dir/manifest.env"
{
  echo "# sourced by check-quality.sh and rm-sandbox.sh"
  echo "MODE=$mode"
  echo "DIFFICULTY=$difficulty"
  echo "ROUND=$round"
  echo "ROUND_DIR=$round_dir"
  echo "REPO=$repo"
  echo "INTEGRATION_REF=main"
  echo "AGENTS=$agents"
  echo "PR_BACKED=\"$pr_backed\""
  echo "SPEC=$round_dir/spec.json"
} >"$manifest_env"

# commit message for a pre-made agent change (COMMITS.md-shaped; it's test data).
agent_msg() {
  local slug="$1" feature="$2"
  cat <<EOF
feat($slug): $feature

Author: $owner_name <$owner_email>
EOF
}

if [[ "$mode" == "git" ]]; then
  git -C "$repo" init -q -b main
  git -C "$repo" config user.name "$owner_name"
  git -C "$repo" config user.email "$owner_email"
  git -C "$repo" add -A
  git -C "$repo" commit -q -m "chore: baseline sandbox fixtures (VCS-0000)"

  # Shared integration point: a bare origin the agents publish onto.
  bare="$round_dir/remote.git"
  git init -q --bare -b main "$bare"
  git -C "$repo" remote add origin "$bare"
  git -C "$repo" push -q origin main

  for ((k = 1; k <= agents; k++)); do
    ws="$round_dir/ws-agent-$k"
    feature="$(feature_for "$k")"
    git -C "$repo" worktree add -q "$ws" -b "agent-$k" main
    python3 "$scenario" apply --dir "$ws" --difficulty "$difficulty" --agent "$k" --ticket "VCS-$round-$k"
    git -C "$ws" add -A
    git -C "$ws" commit -q -F <(agent_msg "$(slug_for "$k")" "$feature")
  done
  # PR-backed agents: publish their branch to the shared origin so it looks like
  # an open PR head. The agent must KEEP its local agent-K (a remote branch backs
  # it); every other agent-K is merged-and-orphaned and must be deleted.
  for k in $pr_backed; do
    git -C "$repo" push -q origin "agent-$k"
  done
  echo "SCORE_GITDIR=$bare" >>"$manifest_env"
  echo "SCORE_REF=main" >>"$manifest_env"
  echo "REMOTE_URL=$bare" >>"$manifest_env"
else
  jj git init "$repo" >/dev/null 2>&1 # colocated: .git + .jj
  jj --repository "$repo" config set --repo user.name "$owner_name" 2>/dev/null
  jj --repository "$repo" config set --repo user.email "$owner_email" 2>/dev/null
  jj --repository "$repo" describe -m "chore: baseline sandbox fixtures (VCS-0000)" >/dev/null 2>&1
  jj --repository "$repo" bookmark create main -r @ >/dev/null 2>&1
  jj --repository "$repo" new >/dev/null 2>&1 # leave the repo working-copy clean on top of main

  for ((k = 1; k <= agents; k++)); do
    ws="$round_dir/ws-agent-$k"
    feature="$(feature_for "$k")"
    jj --repository "$repo" workspace add --name "agent-$k" -r main "$ws" >/dev/null 2>&1
    python3 "$scenario" apply --dir "$ws" --difficulty "$difficulty" --agent "$k" --ticket "VCS-$round-$k"
    # The edit auto-amends this workspace's working-copy commit; message it,
    # pin it with the agent-K bookmark, then start a clean empty change on top.
    jj --repository "$ws" describe -m "$(agent_msg "$(slug_for "$k")" "$feature")" >/dev/null 2>&1
    jj --repository "$ws" bookmark create "agent-$k" -r @ >/dev/null 2>&1
    jj --repository "$ws" new >/dev/null 2>&1
  done
  jj --repository "$repo" git export >/dev/null 2>&1 || true
  echo "SCORE_GITDIR=$repo/.git" >>"$manifest_env"
  echo "SCORE_REF=main" >>"$manifest_env"
fi

# --- briefs + tokens --------------------------------------------------------
tokens=""
for ((k = 1; k <= agents; k++)); do
  ticket="VCS-$round-$k"
  tokens="${tokens:+$tokens }$ticket"
  brief="$(write_brief "$k" "$ticket" "$(feature_for "$k")")"
  {
    echo "WS_$k=$round_dir/ws-agent-$k"
    echo "BRIEF_$k=$brief"
    echo "TICKET_$k=$ticket"
  } >>"$manifest_env"
done
echo "TOKENS=\"$tokens\"" >>"$manifest_env"

# --- human-readable manifest + stdout --------------------------------------
manifest_txt="$round_dir/manifest.txt"
{
  echo "round     : $round"
  echo "mode      : $mode"
  echo "difficulty: $difficulty"
  echo "repo      : $repo"
  echo "integrate : main"
  echo "agents    : $agents"
  echo "pr-backed : ${pr_backed:-<none>}  (these agent-K must be KEPT after merge; the rest deleted)"
  echo "tokens    : $tokens"
  echo ""
  echo "per-agent (work is PRE-COMMITTED on agent-K; the agent only integrates it):"
  for ((k = 1; k <= agents; k++)); do
    echo "  agent-$k  ws=$round_dir/ws-agent-$k  brief=$round_dir/briefs/agent-$k.md  branch/bookmark=agent-$k  ticket=VCS-$round-$k"
  done
} >"$manifest_txt"

cat "$manifest_txt"
echo ""
echo "next: hand each agent its brief + the vcs skill (and ONLY the vcs skill),"
echo "      have it integrate agent-K onto main in its workspace, then run:"
echo "      bash \"$here/check-quality.sh\" \"$round_dir\""
