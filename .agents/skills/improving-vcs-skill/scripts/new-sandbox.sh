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
# Tasks (--task):
#   integrate (default)  the scenario above: pre-committed agent-K, agent lands it
#                        on main and resolves conflicts. Scored by check-quality.sh.
#   start                the SESSION-START bookend: the agent is dropped into a
#                        shared repo and asked to do one tiny, fully-specified new
#                        edit, then land it on main. What's under test is whether
#                        the agent ISOLATES first — carves out its own worktree
#                        (git) / workspace (jj) + branch/bookmark instead of
#                        working directly in the shared checkout — so co-located
#                        agents don't trample each other. Scored by
#                        check-isolation.sh (the work content + cleanup are still
#                        scored by check-quality.sh). Single-agent per round.
#     --start-from main      (default) the agent starts in the primary checkout,
#                            sitting on `main` — correct behavior is to isolate.
#     --start-from worktree  the agent is GIVEN its own worktree/workspace already
#                            — correct behavior is to work in place and NOT create
#                            a redundant nested one (the don't-double-isolate
#                            conditional).
#     --start-from wrong-cwd the agent is ASSIGNED its own worktree/workspace but
#                            launched from the shared primary checkout by mistake;
#                            correct behavior is to move to the assigned path
#                            before any edit or VCS write.
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
#                  [--task integrate|start] [--start-from main|worktree]
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
task="integrate"
start_from="main"
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
    --task) task="${2:-}"; shift 2 ;;
    --start-from) start_from="${2:-}"; shift 2 ;;
    --agents) agents="${2:-}"; shift 2 ;;
    --round) round="${2:-}"; shift 2 ;;
    --pr-backed) pr_backed="${2:-}"; shift 2 ;;
    --workdir) workdir="${2:-}"; shift 2 ;;
    -h | --help) usage 0 ;;
    *) die "unknown arg: $1 (try --help)" ;;
  esac
done

[[ "$mode" == "git" || "$mode" == "jj" ]] || die "--mode must be git or jj"
case "$task" in integrate | start) : ;; *) die "--task must be integrate or start" ;; esac
case "$difficulty" in easy | medium | hard) : ;; *) die "--difficulty must be easy, medium, or hard" ;; esac
command -v python3 >/dev/null 2>&1 || die "python3 required (drives the deterministic content engine)"
[[ -f "$scenario" ]] || die "content engine not found: $scenario"
if [[ "$mode" == "jj" ]] && ! command -v jj >/dev/null 2>&1; then
  die "jj not installed but --mode jj requested"
fi

# The start task measures a PER-AGENT property (does this agent isolate before
# starting work), so it is single-agent and difficulty-independent — the work is
# always the one trivial `easy` edit. Cover tiers/modes/arms by running several
# start rounds, exactly as the integration side covers its matrix across rounds.
if [[ "$task" == "start" ]]; then
  case "$start_from" in main | worktree | wrong-cwd) : ;; *) die "--start-from must be main, worktree, or wrong-cwd" ;; esac
  [[ -z "$agents" || "$agents" == "1" ]] || die "--task start is single-agent (isolation is per-agent); omit --agents or pass 1"
  agents=1
  [[ "$difficulty" == "easy" ]] || echo "new-sandbox.sh: note: --task start ignores --difficulty (work is always the easy edit); using easy" >&2
  difficulty="easy"
  [[ -z "$pr_backed" ]] || { echo "new-sandbox.sh: note: --pr-backed ignored for --task start" >&2; pr_backed=""; }
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

write_start_brief() {
  # $1=k  $2=ticket  $3=feature  $4=start path (where the agent begins)  $5=start_from  $6=assigned path
  local k="$1" ticket="$2" feature="$3" startpath="$4" from="$5"
  local assignedpath="${6:-}"
  local brief="$round_dir/briefs/agent-$k.md"
  local instructions
  instructions="$(python3 "$scenario" start-instructions --round "$round" --agent "$k")"
  local context naming
  if [[ "$from" == "main" ]]; then
    context="Your starting point is the repository at:

    $startpath

This repository is **shared**: several teammates are each picking up their own
ticket on this same machine right now and will be working at the same time. The
checkout you are looking at sits on the team's mainline."
    # Deliberately do NOT prescribe a name — how the agent labels/names its own
    # in-flight work (branch/bookmark, and any working copy it carves out) is
    # exactly what its version-control guidance must decide. check-isolation.sh
    # measures whether that name follows the convention the guidance teaches.
    naming="If your version-control workflow has you set up a place to work and/or a
branch/bookmark for this ticket, name it however that guidance tells you to."
  elif [[ "$from" == "worktree" ]]; then
    context="Your starting point is your own working area at:

    $startpath

Your teammates each have their own separate working area on this machine and are
working on their own tickets at the same time; this one is yours."
    naming="Your working area is already set up for this ticket; do the work there."
  else
    context="Your assigned working area is:

    $assignedpath

The process was launched from this shared host checkout by mistake:

    $startpath

Several teammates are using the host checkout on this machine. Move to your
assigned working area before any edit, commit, branch/bookmark change, or
publish. If a guard blocks a command from the host checkout, treat that as the
expected signal that you are in the wrong cwd and continue from the assigned
working area. After any required timing command, your next filesystem or VCS
action must be from the assigned working area; do not run isolation helpers or
manual workspace/worktree creation from the host checkout."
    naming="Your working area is already set up for this ticket; do the work there."
  fi
  cat >"$brief" <<EOF
# Ticket $ticket — implement "$feature"

You are picking up a fresh ticket. Nothing is written yet — you author this one
small change yourself, then land it on the shared \`main\` line using your team's
standard version-control workflow.

$context

## The change to make

$instructions

$naming

## What to do

Using your team's standard version-control workflow from start to finish:
implement the change above, commit it, get it onto the shared \`main\` so mainline
history contains it, and do whatever end-of-work tidy-up that guidance calls for.
Then **stop**.

**Stay disciplined about scope** — this is a version-control exercise:

- Make **only** the one change described above. Do **not** edit, "improve", or
  reformat any other file or line.
- Do **not** add or modify tests, and do **not** run the app, a build, a
  formatter, or any test suite to verify it.

You are measured on a fast, clean change landed the right way — there is no other
work to do.
EOF
  echo "$brief"
}

# --- build the repo in the requested mode -----------------------------------
manifest_env="$round_dir/manifest.env"
{
  echo "# sourced by check-quality.sh, check-isolation.sh and rm-sandbox.sh"
  echo "MODE=$mode"
  echo "DIFFICULTY=$difficulty"
  echo "TASK=$task"
  echo "START_FROM=$start_from"
  echo "ROUND=$round"
  echo "ROUND_DIR=$round_dir"
  echo "REPO=$repo"
  echo "INTEGRATION_REF=main"
  echo "AGENTS=$agents"
  echo "PR_BACKED=\"$pr_backed\""
  echo "SPEC=$round_dir/spec.json"
  echo "DEFAULT_STALE_SEEDED=0"
  echo "GUARD_LOG=$round_dir/guard-blocks.log"
} >"$manifest_env"
: >"$round_dir/guard-blocks.log"

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

  if [[ "$task" == "integrate" ]]; then
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
  else
    # start task: NO pre-committed work — the agent authors the edit itself.
    if [[ "$start_from" == "worktree" || "$start_from" == "wrong-cwd" ]]; then
      # Hand the agent an isolated worktree on its own branch already (the
      # don't-double-isolate / wrong-cwd arm). No commit: the agent does the work here.
      git -C "$repo" worktree add -q "$round_dir/ws-agent-1" -b "agent-1" main
      echo "GIVEN_WS=$round_dir/ws-agent-1" >>"$manifest_env"
      echo "ASSIGNED_WS=$round_dir/ws-agent-1" >>"$manifest_env"
      echo "GIVEN_BRANCH=agent-1" >>"$manifest_env"
    fi
    # Durable filesystem-isolation baseline: the primary worktree's HEAD reflog
    # line count right now. If the agent isolates (works in its OWN worktree) this
    # stays put; if it works in the shared primary checkout it grows. `worktree
    # add` above does NOT touch the primary's HEAD log, so this is the seed value
    # in both arms. check-isolation.sh compares against it (teardown-robust).
    echo "SEED_HEAD_LINES=$(wc -l <"$repo/.git/logs/HEAD" 2>/dev/null | tr -d ' ')" >>"$manifest_env"
    # Durable capture of the NAME the agent gives its own branch/worktree. Git
    # keeps no teardown-robust record of a branch name (`git branch -d` deletes
    # its reflog; `git worktree remove` deletes the worktree), so we install a
    # reference-transaction hook in the shared .git: it fires for every branch
    # CREATE — including those done from a linked worktree, which run hooks from
    # the common dir — and appends the new branch's short name to a log OUTSIDE
    # the repo, where it survives any cleanup. Installed AFTER the seed refs
    # (main, and the worktree-arm agent-1) already exist, so only the agent's own
    # `switch -c` / `worktree add -b` names land here. jj needs no equivalent —
    # its op log's `add workspace '<name>'` entries are already durable.
    created_log="$round_dir/created-refs.log"
    : >"$created_log"
    hook="$repo/.git/hooks/reference-transaction"
    cat >"$hook" <<HOOK
#!/bin/sh
# harness: log newly-created local branch names (durably, for the name metric)
[ "\$1" = committed ] || exit 0
while read -r old new ref; do
  case "\$ref" in refs/heads/*) : ;; *) continue ;; esac
  case "\$old" in *[!0]*) continue ;; esac   # non-zero old = update/delete, not create
  printf '%s\n' "\${ref#refs/heads/}" >>"$created_log"
done
exit 0
HOOK
    chmod +x "$hook"
    echo "CREATED_REFS_LOG=$created_log" >>"$manifest_env"
  fi
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

  if [[ "$task" == "integrate" ]]; then
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
    # Make the documented default-workspace lifecycle failure deterministic:
    # rewriting default@ from a sibling workspace leaves the default working copy
    # stale until someone runs `jj workspace update-stale` there. This exercises
    # the consolidate-in-default bookend without changing the shared main line.
    # Seed an orphan empty side-head (docs/issues/0007): a bookmark pinned on an
    # empty workspace commit survives `jj workspace forget`; deleting the bookmark
    # afterward strands that empty commit as an anonymous, unreferenced side-head
    # (jj only auto-abandons an empty working copy that NO bookmark pinned). It is
    # cleanup residue from a prior workspace/bookmark lifecycle — not on main, not
    # any agent's work. A clean vcs finish must sweep it (the integrate helper
    # abandons repo-wide orphan empty heads); check-quality.sh's ORPHAN_EMPTY_HEADS
    # measures whether the agent's run left it behind. Seed it BEFORE making the
    # default workspace stale (below), so `jj workspace add` runs against a clean
    # default.
    orphan_seed_ws="$round_dir/ws-orphan-seed"
    jj --repository "$repo" workspace add --name orphan-seed -r main "$orphan_seed_ws" >/dev/null 2>&1
    (cd "$orphan_seed_ws" && jj bookmark create orphan-seed -r @ >/dev/null 2>&1)
    jj --repository "$repo" workspace forget orphan-seed >/dev/null 2>&1
    rm -rf "$orphan_seed_ws"
    jj --repository "$repo" bookmark delete orphan-seed >/dev/null 2>&1
    echo "ORPHAN_SEEDED=1" >>"$manifest_env"

    jj --repository "$round_dir/ws-agent-1" rebase -r 'default@' -d 'agent-1' >/dev/null 2>&1
    echo "DEFAULT_STALE_SEEDED=1" >>"$manifest_env"
    seed_ws="default"
  else
    # start task: NO pre-committed work. The durable filesystem-isolation signal
    # for jj is the op log's `add workspace '<name>'` entries (append-only,
    # survives `workspace forget`). The seed always adds `default`; in the
    # worktree arm we also hand the agent one named workspace. check-isolation.sh
    # flags any workspace-add NOT in SEED_WS as agent-created.
    seed_ws="default"
    echo "SEED_DEFAULT_COMMIT=$(jj --repository "$repo" --ignore-working-copy log --no-graph -r 'default@' -T 'commit_id ++ "\n"' 2>/dev/null | head -1)" >>"$manifest_env"
    if [[ "$start_from" == "worktree" || "$start_from" == "wrong-cwd" ]]; then
      jj --repository "$repo" workspace add --name "agent-1" -r main "$round_dir/ws-agent-1" >/dev/null 2>&1
      echo "GIVEN_WS=$round_dir/ws-agent-1" >>"$manifest_env"
      echo "ASSIGNED_WS=$round_dir/ws-agent-1" >>"$manifest_env"
      echo "GIVEN_BRANCH=agent-1" >>"$manifest_env"
      seed_ws="default agent-1"
    fi
  fi
  jj --repository "$repo" git export >/dev/null 2>&1 || true
  [[ "$task" == "start" ]] && echo "SEED_WS=\"$seed_ws\"" >>"$manifest_env"
  echo "SCORE_GITDIR=$repo/.git" >>"$manifest_env"
  echo "SCORE_REF=main" >>"$manifest_env"
fi

# --- briefs + tokens --------------------------------------------------------
# Where each agent BEGINS. integrate: its own pre-made workspace ws-agent-K.
# start/main: the shared primary checkout (it must isolate itself from there).
# start/worktree: the one isolated workspace it was handed.
ws_path_for() {
  if [[ "$task" == "start" && ( "$start_from" == "main" || "$start_from" == "wrong-cwd" ) ]]; then
    echo "$repo"
  else
    echo "$round_dir/ws-agent-$1"
  fi
}

tokens=""
for ((k = 1; k <= agents; k++)); do
  ticket="VCS-$round-$k"
  tokens="${tokens:+$tokens }$ticket"
  ws_k="$(ws_path_for "$k")"
  if [[ "$task" == "start" ]]; then
    brief="$(write_start_brief "$k" "$ticket" "$(feature_for "$k")" "$ws_k" "$start_from" "${ASSIGNED_WS:-$round_dir/ws-agent-$k}")"
  else
    brief="$(write_brief "$k" "$ticket" "$(feature_for "$k")")"
  fi
  {
    echo "WS_$k=$ws_k"
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
  if [[ "$task" == "start" ]]; then echo "task      : start (start-from: $start_from)"; else echo "task      : integrate"; fi
  echo "repo      : $repo"
  echo "integrate : main"
  echo "agents    : $agents"
  echo "pr-backed : ${pr_backed:-<none>}  (these agent-K must be KEPT after merge; the rest deleted)"
  echo "tokens    : $tokens"
  echo ""
  if [[ "$task" == "start" ]]; then
    echo "per-agent (NO pre-committed work — the agent authors one tiny edit and lands it):"
    for ((k = 1; k <= agents; k++)); do
      if [[ "$start_from" == "wrong-cwd" ]]; then
        echo "  agent-$k  start=$(ws_path_for "$k")  assigned=$round_dir/ws-agent-$k  brief=$round_dir/briefs/agent-$k.md  branch/bookmark=agent-$k  ticket=VCS-$round-$k"
      else
        echo "  agent-$k  start=$(ws_path_for "$k")  brief=$round_dir/briefs/agent-$k.md  branch/bookmark=agent-$k  ticket=VCS-$round-$k"
      fi
    done
  else
    echo "per-agent (work is PRE-COMMITTED on agent-K; the agent only integrates it):"
    for ((k = 1; k <= agents; k++)); do
      echo "  agent-$k  ws=$round_dir/ws-agent-$k  brief=$round_dir/briefs/agent-$k.md  branch/bookmark=agent-$k  ticket=VCS-$round-$k"
    done
  fi
} >"$manifest_txt"

cat "$manifest_txt"
echo ""
if [[ "$task" == "start" ]]; then
  echo "next: hand the agent its brief + the vcs skill (and ONLY the vcs skill),"
  echo "      starting it at the 'start=' path above; have it author + land its"
  echo "      change on main, then score with BOTH:"
  echo "        bash \"$here/check-isolation.sh\" \"$round_dir\"   # session-start isolation"
  echo "        bash \"$here/check-quality.sh\"   \"$round_dir\"   # the change + cleanup landed right"
else
  echo "next: hand each agent its brief + the vcs skill (and ONLY the vcs skill),"
  echo "      have it integrate agent-K onto main in its workspace, then run:"
  echo "      bash \"$here/check-quality.sh\" \"$round_dir\""
fi
