#!/usr/bin/env bash
#
# Parse metadata from a Codex JSONL transcript.
#
# Codex transcripts have a compact JSONL shape with a top-level record type and
# a nested payload. Session scalars live in session_meta and turn_context records,
# while useful aggregates (span, user turns, assistant turns, raw role records,
# models, token totals) require a full streaming pass. python3 is already
# required by export-raw-transcript.sh for metadata validation, so use it here
# rather than trying to parse nested JSON with grep/sed.
#
# Output (default --shell): shell-safe codex_* assignments, the same contract as
# parse-claude-transcript.sh, so export-raw-transcript.sh can eval the result.

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
  session scalars: session_id, cli_version, originator, source, thread_source,
                   model_provider, cwd, git commit/remote
  turn context:    turn_id, workspace_root, current_date, timezone, sandbox,
                   approval policy, model, effort, collaboration mode
  aggregates:      records, user_turns, assistant_turns, user_records,
                   assistant_records, models, started_at, ended_at, and token
                   totals from cumulative token_count records
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
command -v python3 >/dev/null 2>&1 || die "python3 is required to parse Codex transcripts"

# The transcript path is passed as argv so nothing from the transcript is
# interpolated into the heredoc. The program streams json.loads one record at a
# time and only emits metadata/aggregate assignments.
python3 - "$TRANSCRIPT" <<'PYEOF'
import json
import sys


def ts_key(ts):
    """Return a lexicographically comparable key for an ISO-8601 timestamp."""
    if not isinstance(ts, str) or not ts:
        return None
    s = ts[:-1] if ts.endswith("Z") else ts
    if "." in s:
        base, frac = s.split(".", 1)
        digits = ""
        for ch in frac:
            if ch.isdigit():
                digits += ch
            else:
                break
        frac = (digits + "000000")[:6]
    else:
        base, frac = s, "000000"
    return base + "." + frac


def as_dict(value):
    return value if isinstance(value, dict) else {}


def as_str(value):
    return value if isinstance(value, str) and value else None


def as_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def first_array_string(value):
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item:
                return item
    return None


def nested_type(value):
    value = as_dict(value)
    return as_str(value.get("type"))


def collaboration_mode(value):
    if isinstance(value, str):
        return value or None
    value = as_dict(value)
    return as_str(value.get("mode"))


def sh_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def sh_quote(value):
    return "'" + sh_value(value).replace("'", "'\\''") + "'"


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("parse-codex-transcript: missing transcript path\n")
        return 2
    path = sys.argv[1]

    fields = {
        "session_id": None,
        "session_id_alias": None,
        "session_started_at": None,
        "cwd": None,
        "originator": None,
        "cli_version": None,
        "source": None,
        "thread_source": None,
        "model_provider": None,
        "git_commit": None,
        "git_remote": None,
        "turn_id": None,
        "turn_cwd": None,
        "workspace_root": None,
        "current_date": None,
        "timezone": None,
        "approval_policy": None,
        "sandbox_policy_type": None,
        "permission_profile_type": None,
        "model": None,
        "settings_model": None,
        "comp_hash": None,
        "personality": None,
        "collaboration_mode": None,
        "reasoning_effort": None,
        "multi_agent_version": None,
        "realtime_active": None,
        "effort": None,
        "summary": None,
    }

    def setfirst(key, value):
        if fields[key] is not None:
            return
        if isinstance(value, bool):
            fields[key] = value
            return
        value = as_str(value)
        if value is not None:
            fields[key] = value

    records = 0
    parse_errors = 0
    started = started_key = None
    ended = ended_key = None
    user_turns = 0
    turn_contexts = 0
    agent_message_events = 0
    user_records = 0
    assistant_records = 0
    assistant_turn_keys = set()
    models = []
    seen_models = set()
    cumulative_tokens = None
    summed_last_tokens = {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }
    have_last_tokens = False

    def add_model(value):
        value = as_str(value)
        if value is None or value in seen_models:
            return
        seen_models.add(value)
        models.append(value)

    def update_span(value):
        nonlocal started, started_key, ended, ended_key
        key = ts_key(value)
        if key is None:
            return
        if started_key is None or key < started_key:
            started, started_key = value, key
        if ended_key is None or key > ended_key:
            ended, ended_key = value, key

    def update_token_counts(payload):
        nonlocal cumulative_tokens, have_last_tokens
        info = as_dict(payload.get("info"))
        total_usage = as_dict(info.get("total_token_usage"))
        if total_usage:
            cumulative_tokens = total_usage
        last_usage = as_dict(info.get("last_token_usage"))
        if last_usage:
            have_last_tokens = True
            for key in summed_last_tokens:
                value = as_int(last_usage.get(key))
                if value is not None:
                    summed_last_tokens[key] += value

    try:
        handle = open(path, "r", encoding="utf-8", errors="replace")
    except OSError as exc:
        sys.stderr.write("parse-codex-transcript: cannot open %s: %s\n" % (path, exc))
        return 1

    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records += 1
            try:
                rec = json.loads(line)
            except Exception:
                parse_errors += 1
                continue
            if not isinstance(rec, dict):
                continue

            payload = as_dict(rec.get("payload"))
            rec_type = as_str(rec.get("type"))
            payload_type = as_str(payload.get("type"))

            update_span(rec.get("timestamp"))
            update_span(payload.get("timestamp"))

            if rec_type == "session_meta":
                setfirst("session_id", payload.get("session_id") or rec.get("session_id"))
                setfirst("session_id_alias", payload.get("id") or rec.get("id"))
                setfirst("session_started_at", payload.get("timestamp") or rec.get("timestamp"))
                setfirst("cwd", payload.get("cwd") or rec.get("cwd"))
                setfirst("originator", payload.get("originator") or rec.get("originator"))
                setfirst("cli_version", payload.get("cli_version") or rec.get("cli_version"))
                setfirst("source", payload.get("source") or rec.get("source"))
                setfirst("thread_source", payload.get("thread_source") or rec.get("thread_source"))
                setfirst("model_provider", payload.get("model_provider") or rec.get("model_provider"))
                git = as_dict(payload.get("git"))
                setfirst("git_commit", git.get("commit_hash"))
                setfirst("git_remote", git.get("repository_url"))
            elif rec_type == "turn_context":
                turn_contexts += 1
                setfirst("turn_id", payload.get("turn_id"))
                setfirst("turn_cwd", payload.get("cwd"))
                setfirst("workspace_root", first_array_string(payload.get("workspace_roots")))
                setfirst("current_date", payload.get("current_date"))
                setfirst("timezone", payload.get("timezone"))
                setfirst("approval_policy", payload.get("approval_policy"))
                setfirst("sandbox_policy_type", nested_type(payload.get("sandbox_policy")))
                setfirst("permission_profile_type", nested_type(payload.get("permission_profile")))
                setfirst("model", payload.get("model"))
                setfirst("settings_model", payload.get("model"))
                add_model(payload.get("model"))
                setfirst("comp_hash", payload.get("comp_hash"))
                setfirst("personality", payload.get("personality"))
                setfirst("collaboration_mode", collaboration_mode(payload.get("collaboration_mode")))
                setfirst("reasoning_effort", payload.get("reasoning_effort"))
                setfirst("multi_agent_version", payload.get("multi_agent_version"))
                if isinstance(payload.get("realtime_active"), bool):
                    setfirst("realtime_active", payload.get("realtime_active"))
                setfirst("effort", payload.get("effort"))
                setfirst("summary", payload.get("summary"))

            if payload_type == "user_message":
                user_turns += 1
            elif payload_type == "agent_message":
                agent_message_events += 1
            elif payload_type == "token_count":
                update_token_counts(payload)

            if payload_type == "message":
                role = as_str(payload.get("role"))
                if role == "user":
                    user_records += 1
                elif role == "assistant":
                    assistant_records += 1
                    message_id = as_str(payload.get("id"))
                    key = message_id if message_id is not None else "\0rec:%d" % records
                    assistant_turn_keys.add(key)

    if user_turns == 0 and turn_contexts:
        user_turns = turn_contexts
    assistant_turns = len(assistant_turn_keys) or agent_message_events
    token_source = cumulative_tokens
    if token_source is None and have_last_tokens:
        token_source = summed_last_tokens

    out = []

    def emit(name, value):
        if value is None:
            return
        if isinstance(value, str) and value == "":
            return
        out.append("codex_%s=%s" % (name, sh_quote(value)))

    for key in fields:
        emit(key, fields[key])

    emit("records", records)
    if parse_errors:
        emit("parse_errors", parse_errors)
    emit("user_turns", user_turns)
    emit("assistant_turns", assistant_turns)
    emit("user_records", user_records)
    emit("assistant_records", assistant_records)
    if models:
        emit("models", ",".join(models))
        emit("models_count", len(models))

    emit("started_at", started or fields["session_started_at"])
    emit("ended_at", ended or started or fields["session_started_at"])

    if token_source is not None:
        token_total = as_int(token_source.get("total_tokens"))
        input_tokens = as_int(token_source.get("input_tokens"))
        output_tokens = as_int(token_source.get("output_tokens"))
        cache_read = as_int(token_source.get("cached_input_tokens"))
        cache_creation = as_int(token_source.get("cache_creation_input_tokens"))
        if token_total is None and input_tokens is not None and output_tokens is not None:
            token_total = input_tokens + output_tokens

        emit("input_tokens", input_tokens)
        emit("output_tokens", output_tokens)
        emit("cache_read_tokens", cache_read)
        emit("cache_creation_tokens", cache_creation)
        emit("total_tokens", token_total)

    sys.stdout.write("\n".join(out) + ("\n" if out else ""))
    return 0


sys.exit(main())
PYEOF
