#!/usr/bin/env bash
#
# Tear down harness sandboxes safely. Everything the harness makes lives under
# one disposable work area, and a round dir holds its repo, every per-agent
# workspace, and the briefs together — so removing the dir removes the whole
# round (no `git worktree remove` / `jj workspace forget` dance needed).
#
# Guard rails: this only ever deletes paths *inside* the harness work area, and a
# single-round delete additionally requires the round's manifest.env to be
# present — so it can never be aimed at a real repository.
#
# Usage:
#   rm-sandbox.sh <round-dir>     # remove one round (must contain manifest.env)
#   rm-sandbox.sh --all           # remove the entire work area (all rounds + metrics)
#   rm-sandbox.sh --workdir DIR <as above>
set -euo pipefail

workdir="${VCS_HARNESS_DIR:-${TMPDIR:-/tmp}/vcs-harness}"
target=""
all=0
die() {
  echo "rm-sandbox.sh: $*" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all) all=1; shift ;;
    --workdir) workdir="${2:?}"; shift 2 ;;
    -h | --help)
      grep -E '^# (Usage|  )' "$0" | sed 's/^# //'
      exit 0
      ;;
    -*) die "unknown arg: $1" ;;
    *) target="$1"; shift ;;
  esac
done

# Absolutize without requiring the path to still exist after we resolve parents.
abspath() (
  d="$(cd "$(dirname "$1")" 2>/dev/null && pwd)" || return 1
  printf '%s/%s' "${d%/}" "$(basename "$1")"
)

workdir_abs="$(cd "$workdir" 2>/dev/null && pwd || echo "$workdir")"
case "$workdir_abs" in
  "" | "/" | "$HOME") die "refusing: unsafe work area '$workdir_abs'" ;;
esac

if [[ "$all" -eq 1 ]]; then
  [[ -d "$workdir_abs" ]] || {
    echo "nothing to remove: $workdir_abs"
    exit 0
  }
  rm -rf "$workdir_abs"
  echo "removed harness work area: $workdir_abs"
  exit 0
fi

[[ -n "$target" ]] || die "give a <round-dir> or --all"
target_abs="$(abspath "$target")"
case "$target_abs/" in
  "$workdir_abs"/*) : ;;
  *) die "refusing: '$target_abs' is not inside the harness work area '$workdir_abs'" ;;
esac
[[ -f "$target_abs/manifest.env" ]] ||
  die "refusing: '$target_abs' has no manifest.env — not a harness round dir"

rm -rf "$target_abs"
echo "removed round dir: $target_abs"
