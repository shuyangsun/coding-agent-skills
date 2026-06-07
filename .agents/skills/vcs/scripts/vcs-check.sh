#!/usr/bin/env bash
#
# Guard checks for vcs helpers and agent hooks.
set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=vcs-state.sh
. "$script_dir/vcs-state.sh"

cmd="${1:-}"
[[ $# -gt 0 ]] && shift || true
helper=""
agent="agent"
hook_mode=0

usage() {
  cat <<'EOF'
usage:
  vcs-check.sh pre-edit
  vcs-check.sh pre-vcs-write [--helper isolate|integrate|session-start|rename-work] [work-ref]
  vcs-check.sh pre-publish [--helper integrate] [work-ref]
  vcs-check.sh assert-owner <work-ref>
  vcs-check.sh hook [--agent codex|claude|cursor]

The hook form reads a Codex/Claude-style hook JSON object on stdin and exits 2
to block risky default-workspace edits or raw VCS writes. Cursor hooks should
call cursor-hook.sh, which adapts Cursor payloads and emits Cursor JSON.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --helper)
      [[ $# -ge 2 ]] || {
        echo "vcs-check: --helper requires a value" >&2
        exit 3
      }
      helper="$2"
      shift 2
      ;;
    --agent)
      [[ $# -ge 2 ]] || {
        echo "vcs-check: --agent requires a value" >&2
        exit 3
      }
      agent="$2"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      break
      ;;
  esac
done

ref="${1:-}"

deny() {
  local reason="$1"
  local dir="$PWD"
  while [[ "$dir" != "/" && -n "$dir" ]]; do
    if [[ -f "$dir/manifest.env" ]]; then
      printf '%s\t%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$reason" >>"$dir/guard-blocks.log" 2>/dev/null || true
      break
    fi
    dir="$(dirname "$dir")"
  done
  printf 'vcs-check: %s\n' "$reason" >&2
  if [[ "$hook_mode" -eq 1 ]]; then
    exit 2
  fi
  exit 3
}

current_mode() {
  vcs_detect_mode 2>/dev/null || true
}

current_shared_reason() {
  local mode current
  mode="$(current_mode)"
  case "$mode" in
    jj)
      current="$(vcs_jj_workspace_name 2>/dev/null || true)"
      [[ "$current" == "default" ]] && {
        printf "current cwd is the shared jj default workspace"
        return 0
      }
      ;;
    git)
      if ! vcs_git_is_linked_worktree; then
        printf "current cwd is the shared primary git checkout"
        return 0
      fi
      ;;
  esac
  return 1
}

ensure_not_shared() {
  local action="$1" reason
  reason="$(current_shared_reason || true)"
  [[ -z "$reason" ]] || deny "$action refused: $reason. Run session-start.sh or isolate.sh, cd to NEXT_CWD, then retry."
}

ensure_owner_marker() {
  local expected="${1:-}"
  vcs_current_marker_matches "$expected" || {
    if [[ -n "$expected" ]]; then
      deny "owner check refused: no matching session owner marker for '$expected' in this workspace"
    else
      deny "owner check refused: no session owner marker for this workspace"
    fi
  }
}

is_helper_name() {
  case "$1" in
    isolate | integrate | session-start | rename-work) return 0 ;;
    *) return 1 ;;
  esac
}

check_pre_edit() {
  [[ "${VCS_GUARD_ALLOW_SHARED:-}" == "1" ]] && return 0
  ensure_not_shared "edit"
}

check_pre_vcs_write() {
  [[ "${VCS_GUARD_ALLOW_SHARED:-}" == "1" ]] && return 0
  if is_helper_name "$helper"; then
    case "$helper" in
      isolate | session-start | rename-work)
        return 0
        ;;
      integrate)
        ensure_not_shared "integration"
        return 0
        ;;
    esac
  fi
  ensure_not_shared "VCS write"
  ensure_owner_marker "$ref"
}

check_pre_publish() {
  [[ "${VCS_GUARD_ALLOW_SHARED:-}" == "1" ]] && return 0
  if [[ "$helper" == "integrate" ]]; then
    ensure_not_shared "publish"
    return 0
  fi
  ensure_not_shared "publish"
  ensure_owner_marker "$ref"
}

is_vetted_helper_command() {
  local c="$1"
  [[ "$c" == *".agents/skills/vcs/scripts/isolate.sh"* ||
    "$c" == *".agents/skills/vcs/scripts/integrate.sh"* ||
    "$c" == *".agents/skills/vcs/scripts/session-start.sh"* ||
    "$c" == *".agents/skills/vcs/scripts/rename-work.sh"* ]]
}

is_read_only_command() {
  local c="$1"
  c="${c#"${c%%[![:space:]]*}"}"
  case "$c" in
    "" | pwd | "pwd "* | ls | "ls "* | date | "date "* | true | "true "* | false | "false "*)
      return 0
      ;;
    rg | "rg "* | grep | "grep "* | "sed -n "* | cat | "cat "* | head | "head "* | tail | "tail "* | wc | "wc "* | find | "find "*)
      return 0
      ;;
    "git status"* | "git log"* | "git diff"* | "git show"* | "git branch --show-current"* | "git rev-parse"* | "git remote get-url"* | "git ls-remote"* | "git worktree list"*)
      return 0
      ;;
    "jj status"* | "jj st"* | "jj log"* | "jj diff"* | "jj show"* | "jj root"* | "jj workspace list"* | "jj bookmark list"* | "jj resolve --list"* | "jj git remote list"*)
      return 0
      ;;
    "bash "*"/scripts/"*" --help"* | "bash "*"/scripts/"*" -h"*)
      return 0
      ;;
  esac
  return 1
}

is_publish_command() {
  local c="$1"
  [[ "$c" =~ (^|[[:space:];|&])git[[:space:]]+push([[:space:]]|$) ||
    "$c" =~ (^|[[:space:];|&])jj[[:space:]]+git[[:space:]]+push([[:space:]]|$) ]]
}

is_vcs_mutating_command() {
  local c="$1"
  [[ "$c" =~ (^|[[:space:];|&])jj[[:space:]]+(describe|commit|new|rebase|squash|split|abandon)([[:space:]]|$) ||
    "$c" =~ (^|[[:space:];|&])jj[[:space:]]+bookmark[[:space:]]+(set|create|delete|move|rename)([[:space:]]|$) ||
    "$c" =~ (^|[[:space:];|&])jj[[:space:]]+workspace[[:space:]]+(add|forget|rename|update-stale)([[:space:]]|$) ||
    "$c" =~ (^|[[:space:];|&])jj[[:space:]]+git[[:space:]]+(push|export|import)([[:space:]]|$) ||
    "$c" =~ (^|[[:space:];|&])git[[:space:]]+(add|commit|merge|rebase|reset|checkout|switch)([[:space:]]|$) ||
    "$c" =~ (^|[[:space:];|&])git[[:space:]]+branch[[:space:]]+(-D|-d)([[:space:]]|$) ||
    "$c" =~ (^|[[:space:];|&])git[[:space:]]+worktree[[:space:]]+(add|remove|prune)([[:space:]]|$) ]]
}

is_file_mutating_command() {
  local c="$1"
  [[ "$c" =~ (^|[[:space:];|&])(rm|mv|cp|touch|mkdir|rmdir)([[:space:]]|$) ||
    "$c" == *" >"* ||
    "$c" == *">>"* ||
    "$c" =~ (^|[[:space:];|&])tee([[:space:]]|$) ||
    "$c" =~ (^|[[:space:];|&])sed[[:space:]]+-i ||
    "$c" =~ (^|[[:space:];|&])perl[[:space:]]+-pi ||
    "$c" == *" --write"* ||
    "$c" == *" run format"* ]]
}

json_field() {
  local input="$1" field="$2"
  [[ -n "$input" ]] || return 0
  command -v python3 >/dev/null 2>&1 || return 0
  python3 -c 'import json, sys
field = sys.argv[1]
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
cur = data
for part in field.split("."):
    if isinstance(cur, dict):
        cur = cur.get(part)
    else:
        cur = None
        break
if cur is not None:
    print(cur)
' "$field" <<<"$input" 2>/dev/null || true
}

hook_warn_if_shared() {
  local event="$1" reason
  reason="$(current_shared_reason || true)"
  [[ -n "$reason" ]] || return 0
  cat <<EOF
vcs guard: $event is running from a shared checkout ($reason).
Before editing or publishing, run:
  bash <skill-dir>/scripts/session-start.sh
Then cd to NEXT_CWD and continue there.
EOF
}

check_hook() {
  hook_mode=1
  local input event tool command
  input="$(cat 2>/dev/null || true)"
  event="$(json_field "$input" hook_event_name)"
  tool="$(json_field "$input" tool_name)"
  command="$(json_field "$input" tool_input.command)"

  case "$event" in
    SubagentStart | CwdChanged)
      hook_warn_if_shared "$event"
      return 0
      ;;
  esac

  case "$tool" in
    apply_patch | Edit | Write | MultiEdit | NotebookEdit)
      check_pre_edit
      return 0
      ;;
    Bash)
      if is_vetted_helper_command "$command"; then
        return 0
      fi
      if is_read_only_command "$command"; then
        return 0
      fi
      if is_publish_command "$command"; then
        check_pre_publish
        return 0
      fi
      if is_vcs_mutating_command "$command" || is_file_mutating_command "$command" || current_shared_reason >/dev/null 2>&1; then
        check_pre_vcs_write
        return 0
      fi
      ;;
  esac
}

case "$cmd" in
  pre-edit)
    check_pre_edit
    ;;
  pre-vcs-write)
    check_pre_vcs_write
    ;;
  pre-publish)
    check_pre_publish
    ;;
  assert-owner)
    [[ -n "$ref" ]] || deny "assert-owner requires a work ref"
    ensure_owner_marker "$ref"
    ;;
  hook)
    check_hook
    ;;
  -h | --help | "")
    usage
    [[ -n "$cmd" ]] && exit 0 || exit 3
    ;;
  *)
    deny "unknown command: $cmd"
    ;;
esac
