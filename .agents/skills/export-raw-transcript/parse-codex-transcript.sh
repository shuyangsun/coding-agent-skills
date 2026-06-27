#!/usr/bin/env bash
#
# Parse small metadata-bearing records from a Codex JSONL transcript.
#
# This intentionally avoids jq/python so it can run in the same minimal
# environments as export-raw-transcript.sh. It reads until it has seen
# session_meta and the first turn_context, then emits shell-safe assignments by
# default. The parser is targeted to Codex's compact JSONL transcript shape.

set -uo pipefail

prog="parse-codex-transcript"
die() {
  printf '%s: %s\n' "$prog" "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage:
  bash parse-codex-transcript.sh [--shell] <codex-rollout.jsonl>

Outputs shell-safe codex_* assignments for metadata found in Codex transcript
records:
  session_meta: session id, cli version, originator, source, model provider, cwd
  turn_context: model, effort, collaboration mode, timezone, sandbox, turn id
EOF
}

MODE="shell"
TRANSCRIPT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --shell) MODE="shell" ;;
    -h | --help) usage; exit 0 ;;
    --*) die "unknown option: $1" ;;
    *)
      [ -z "$TRANSCRIPT" ] || die "unexpected extra argument: $1"
      TRANSCRIPT="$1"
      ;;
  esac
  shift
done

[ "$MODE" = "shell" ] || die "unsupported output mode: $MODE"
[ -n "$TRANSCRIPT" ] || die "missing transcript path"
[ -f "$TRANSCRIPT" ] || die "not a file: $TRANSCRIPT"

session_meta_line=""
turn_context_line=""
while IFS= read -r line; do
  case "$line" in
    *'"type":"session_meta"'*)
      [ -n "$session_meta_line" ] || session_meta_line="$line"
      ;;
    *'"type":"turn_context"'*)
      turn_context_line="$line"
      break
      ;;
  esac
done <"$TRANSCRIPT"

json_string_field() {
  # json_string_field <line> <field-name>
  # Extracts a simple JSON string field from Codex's single-line compact JSON.
  # It handles escaped quotes in the value well enough to avoid premature stops.
  local line="$1" field="$2"
  printf '%s\n' "$line" |
    sed -nE 's/.*"'"$field"'"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)".*/\1/p' |
    sed -n '1p'
}

json_bool_field() {
  local line="$1" field="$2"
  printf '%s\n' "$line" |
    sed -nE 's/.*"'"$field"'"[[:space:]]*:[[:space:]]*(true|false).*/\1/p' |
    sed -n '1p'
}

json_nested_type() {
  # json_nested_type <line> <object-field>
  local line="$1" field="$2"
  printf '%s\n' "$line" |
    sed -nE 's/.*"'"$field"'"[[:space:]]*:[[:space:]]*\{[^}]*"type"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)".*/\1/p' |
    sed -n '1p'
}

json_first_array_string() {
  local line="$1" field="$2"
  printf '%s\n' "$line" |
    sed -nE 's/.*"'"$field"'"[[:space:]]*:[[:space:]]*\[[[:space:]]*"(([^"\\]|\\.)*)".*/\1/p' |
    sed -n '1p'
}

shell_quote() {
  # Single-quote for POSIX shell assignment output.
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

emit() {
  local name="$1" value="${2:-}"
  [ -n "$value" ] || return 0
  printf 'codex_%s=' "$name"
  shell_quote "$value"
  printf '\n'
}

turn_prefix="$turn_context_line"
case "$turn_context_line" in
  *'"collaboration_mode"'*) turn_prefix="${turn_context_line%%\"collaboration_mode\"*}" ;;
esac

emit session_id "$(json_string_field "$session_meta_line" "session_id")"
emit session_id_alias "$(json_string_field "$session_meta_line" "id")"
emit session_started_at "$(json_string_field "$session_meta_line" "timestamp")"
emit cwd "$(json_string_field "$session_meta_line" "cwd")"
emit originator "$(json_string_field "$session_meta_line" "originator")"
emit cli_version "$(json_string_field "$session_meta_line" "cli_version")"
emit source "$(json_string_field "$session_meta_line" "source")"
emit thread_source "$(json_string_field "$session_meta_line" "thread_source")"
emit model_provider "$(json_string_field "$session_meta_line" "model_provider")"

emit turn_id "$(json_string_field "$turn_context_line" "turn_id")"
emit turn_cwd "$(json_string_field "$turn_context_line" "cwd")"
emit workspace_root "$(json_first_array_string "$turn_context_line" "workspace_roots")"
emit current_date "$(json_string_field "$turn_context_line" "current_date")"
emit timezone "$(json_string_field "$turn_context_line" "timezone")"
emit approval_policy "$(json_string_field "$turn_context_line" "approval_policy")"
emit sandbox_policy_type "$(json_nested_type "$turn_context_line" "sandbox_policy")"
emit permission_profile_type "$(json_nested_type "$turn_context_line" "permission_profile")"
emit model "$(json_string_field "$turn_prefix" "model")"
emit settings_model "$(json_string_field "$turn_context_line" "model")"
emit comp_hash "$(json_string_field "$turn_context_line" "comp_hash")"
emit personality "$(json_string_field "$turn_context_line" "personality")"
emit collaboration_mode "$(json_string_field "$turn_context_line" "mode")"
emit reasoning_effort "$(json_string_field "$turn_context_line" "reasoning_effort")"
emit multi_agent_version "$(json_string_field "$turn_context_line" "multi_agent_version")"
emit realtime_active "$(json_bool_field "$turn_context_line" "realtime_active")"
emit effort "$(json_string_field "$turn_context_line" "effort")"
emit summary "$(json_string_field "$turn_context_line" "summary")"
