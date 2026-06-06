#!/usr/bin/env bash
#
# Provision ONE round's isolated VCS sandbox for the improving-vcs-skill harness.
#
# Creates a throwaway repo seeded with conflict-prone fixtures, an integration
# point (the `main` branch/bookmark), one workspace per simulated agent, and a
# realistic per-agent task brief that drives the agents into overlapping edits.
# Each agent also makes an *additive*, sentinel-bearing change (a CHANGELOG entry
# tagged with a unique ticket id) so check-quality.sh can later prove no agent's
# work was clobbered during integration.
#
#   --mode git        plain Git repo (no .jj) — the "Git only / worktree" path.
#   --mode jj         Jujutsu on a Git backend (colocated: both .git and .jj) —
#                     the "jj present, must use jj" path. Per-agent isolation via
#                     `jj workspace add`.
#
# EVERYTHING lives under one disposable work area outside any real repo, so the
# harness never pollutes the project under test. Tear a round down with
# rm-sandbox.sh. No paths, usernames, or emails are hardcoded to a real person;
# the sandbox identity is a neutral placeholder that doubles as test data for the
# vcs skill's Author-trailer logic.
#
# Usage:
#   new-sandbox.sh --mode git|jj [--agents N] [--round N] [--workdir DIR] [--remote]
#
# Prints a manifest (also written to <round>/manifest.txt and a shell-sourceable
# <round>/manifest.env that check-quality.sh / rm-sandbox.sh consume).
set -euo pipefail

# --- args ------------------------------------------------------------------
mode=""
agents=3
round=""
remote=0
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
    --agents) agents="${2:-}"; shift 2 ;;
    --round) round="${2:-}"; shift 2 ;;
    --workdir) workdir="${2:-}"; shift 2 ;;
    --remote) remote=1; shift ;;
    -h | --help) usage 0 ;;
    *) die "unknown arg: $1 (try --help)" ;;
  esac
done

[[ "$mode" == "git" || "$mode" == "jj" ]] || die "--mode must be git or jj"
[[ "$agents" =~ ^[1-9][0-9]*$ ]] || die "--agents must be a positive integer"
if [[ "$mode" == "jj" ]] && ! command -v jj >/dev/null 2>&1; then
  die "jj not installed but --mode jj requested"
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

# --- fixtures: a tiny project with several deliberately hot regions ---------
seed_fixtures() {
  mkdir -p "$repo/app" "$repo/docs"

  cat >"$repo/docs/CHANGELOG.md" <<'EOF'
# Changelog

## Unreleased

- baseline scaffolding (VCS-0000)

## 1.4.0

- first cut
EOF

  cat >"$repo/app/config.yaml" <<'EOF'
name: demo
version: 1.4.0
log_level: info
max_retries: 3
EOF

  cat >"$repo/app/pipeline.py" <<'EOF'
def transform(records):
    result = []
    for r in records:
        # >>> pipeline steps <<<
        result.append(r)
    return result
EOF

  cat >"$repo/app/feature_flags.py" <<'EOF'
FLAGS = {
    "beta_ui": False,
    "csv_export": False,
}
EOF

  cat >"$repo/app/registry.json" <<'EOF'
{
  "plugins": [
    { "id": "core", "summary": "core plugin", "enabled": true }
  ]
}
EOF
}

# --- per-agent task briefs --------------------------------------------------
# The universal conflict generator is the CHANGELOG: every agent inserts a line
# at the SAME top-of-list position, so any N >= 2 collide there. Each agent ALSO
# gets a "converging" edit assigned round-robin across three hot regions, adding
# same-line and insertion conflict classes when >= 2 agents share a group. The
# CHANGELOG entry is the additive sentinel that must survive integration.
tokens=""
write_brief() {
  local k="$1" ticket="$2" brief="$round_dir/briefs/agent-$k.md"
  local feature group_task
  case "$((k % 3))" in
    1)
      feature="streaming export"
      group_task=$(
        cat <<EOF
2. In \`app/config.yaml\`, bump the \`version\` field to \`1.5.$k\` (this ships a
   new minor feature).
EOF
      )
      ;;
    2)
      feature="input validation"
      group_task=$(
        cat <<EOF
2. In \`app/pipeline.py\`, add one processing step on the line immediately after
   the \`# >>> pipeline steps <<<\` marker, inside \`transform()\`:
   \`        r = validate(r)  # $ticket\`
EOF
      )
      ;;
    0)
      feature="registry refresh"
      group_task=$(
        cat <<EOF
2. In \`app/registry.json\`, update the \`core\` plugin's \`summary\` to
   \`"core plugin ($ticket)"\`, and flip \`csv_export\` to \`True\` in
   \`app/feature_flags.py\`.
EOF
      )
      ;;
  esac

  cat >"$brief" <<EOF
# Ticket $ticket — ship "$feature"

You are picking up a small change in the repository at the path you were given
as your workspace. Other teammates are landing their own tickets in this same
repository at the same time.

Make exactly these edits, then commit and integrate them onto the shared
\`main\` line so they are part of the project's mainline history:

1. Add a CHANGELOG entry. At the TOP of the \`## Unreleased\` list in
   \`docs/CHANGELOG.md\` (above the existing first bullet), add:
   \`- $feature ($ticket)\`
$group_task

Then publish your work onto \`main\`. Teammates are touching the same files and
lines, so you will likely hit conflicts when you integrate: resolve them
properly — keep everyone's CHANGELOG entries, do not drop or clobber a
teammate's change, and leave no conflict markers behind. The history should end
up clean.

Use your team's standard version-control workflow and etiquette throughout.
EOF
  echo "$brief"
}

# --- build the repo in the requested mode -----------------------------------
seed_fixtures

manifest_env="$round_dir/manifest.env"
{
  echo "# sourced by check-quality.sh and rm-sandbox.sh"
  echo "MODE=$mode"
  echo "ROUND=$round"
  echo "ROUND_DIR=$round_dir"
  echo "REPO=$repo"
  echo "INTEGRATION_REF=main"
  echo "AGENTS=$agents"
  echo "REMOTE=$remote"
} >"$manifest_env"

if [[ "$mode" == "git" ]]; then
  git -C "$repo" init -q -b main
  git -C "$repo" config user.name "$owner_name"
  git -C "$repo" config user.email "$owner_email"
  git -C "$repo" add -A
  git -C "$repo" commit -q -m "chore: baseline sandbox fixtures (VCS-0000)"
  for ((k = 1; k <= agents; k++)); do
    ws="$round_dir/ws-agent-$k"
    git -C "$repo" worktree add -q "$ws" -b "agent-$k" main
  done
else
  jj git init "$repo" >/dev/null 2>&1 # colocated: .git + .jj
  jj --repository "$repo" config set --repo user.name "$owner_name" 2>/dev/null
  jj --repository "$repo" config set --repo user.email "$owner_email" 2>/dev/null
  jj --repository "$repo" describe -m "chore: baseline sandbox fixtures (VCS-0000)" >/dev/null 2>&1
  jj --repository "$repo" bookmark create main -r @ >/dev/null 2>&1
  for ((k = 1; k <= agents; k++)); do
    ws="$round_dir/ws-agent-$k"
    jj --repository "$repo" workspace add --name "agent-$k" -r main "$ws" >/dev/null 2>&1
  done
fi

# Optional shared remote (models the PR / cloud-publish flow).
if [[ "$remote" -eq 1 ]]; then
  bare="$round_dir/remote.git"
  git init -q --bare -b main "$bare"
  git -C "$repo" remote add origin "$bare"
  git -C "$repo" push -q origin main
  echo "REMOTE_URL=$bare" >>"$manifest_env"
fi

# --- briefs + tokens --------------------------------------------------------
for ((k = 1; k <= agents; k++)); do
  ticket="VCS-$round-$k"
  tokens="${tokens:+$tokens }$ticket"
  brief="$(write_brief "$k" "$ticket")"
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
  echo "round    : $round"
  echo "mode     : $mode$([[ $remote -eq 1 ]] && echo ' (+remote)')"
  echo "repo     : $repo"
  echo "integrate: main"
  echo "agents   : $agents"
  echo "tokens   : $tokens"
  echo ""
  echo "per-agent:"
  for ((k = 1; k <= agents; k++)); do
    echo "  agent-$k  ws=$round_dir/ws-agent-$k  brief=$round_dir/briefs/agent-$k.md  ticket=VCS-$round-$k"
  done
} >"$manifest_txt"

cat "$manifest_txt"
echo ""
echo "next: hand each agent its brief + the vcs skill (and ONLY the vcs skill),"
echo "      have them work in their workspace and integrate onto main, then run:"
echo "      bash \"\$(dirname \"\$0\")/check-quality.sh\" \"$round_dir\""
