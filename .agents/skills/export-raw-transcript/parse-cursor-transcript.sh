#!/usr/bin/env bash
#
# Parse metadata from a Cursor agent JSONL transcript.
#
# Cursor transcripts observed under ~/.cursor/projects/*/agent-transcripts keep a
# compact stream of records such as {"role":"user","message":...},
# {"role":"assistant","message":...}, and {"type":"turn_ended","status":...}.
# Newer/older builds may add richer top-level metadata, so this parser is
# deliberately conservative: it streams each JSONL record with python3, records
# only scalar metadata and aggregate counts, and tolerates missing fields.
#
# Output (default --shell): shell-safe cursor_* assignments, matching the
# parse-claude-transcript.sh / parse-codex-transcript.sh contract so
# export-raw-transcript.sh can eval the result.

set -uo pipefail

prog="parse-cursor-transcript"
die() {
  printf '%s: %s\n' "$prog" "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage:
  bash parse-cursor-transcript.sh [--shell] <cursor-transcript.jsonl>

Outputs shell-safe cursor_* assignments for metadata found in Cursor JSONL
records:
  session scalars: session_id, version/tool info, cwd/entrypoint, title,
                   agent name, bridge/session identifiers when present
  aggregates:      records, user_turns, assistant_turns, user_records,
                   assistant_records, raw role counts, parse_errors, model,
                   models, started_at, ended_at, and token totals when present
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
command -v python3 >/dev/null 2>&1 || die "python3 is required to parse Cursor transcripts"

# The transcript path is passed as argv so nothing from the transcript is
# interpolated into the heredoc. The program streams json.loads one record at a
# time and emits only metadata/aggregate assignments.
python3 - "$TRANSCRIPT" <<'PYEOF'
import json
import os
import sys


def ts_key(value):
    """Return a lexicographically comparable key for an ISO-8601 timestamp."""
    if not isinstance(value, str) or not value:
        return None
    s = value[:-1] if value.endswith("Z") else value
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


def as_list(value):
    return value if isinstance(value, list) else []


def as_str(value):
    return value if isinstance(value, str) and value else None


def as_int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def sh_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def sh_quote(value):
    return "'" + sh_value(value).replace("'", "'\\''") + "'"


def first_string(*values):
    for value in values:
        text = as_str(value)
        if text is not None:
            return text
    return None


def get_path(obj, *path):
    cur = obj
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def iter_dicts(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from iter_dicts(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_dicts(value)


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("parse-cursor-transcript: missing transcript path\n")
        return 2
    path = sys.argv[1]

    # Filename and parent folder are both stable session-id candidates in Cursor's
    # current transcript layout: agent-transcripts/<id>/<id>.jsonl.
    filename_id = os.path.splitext(os.path.basename(path))[0]
    parent_id = os.path.basename(os.path.dirname(path))
    session_id_fallback = filename_id or parent_id

    fields = {
        "session_id": session_id_fallback,
        "conversation_id": None,
        "bridge_session_id": None,
        "version": None,
        "tool_version": None,
        "tool_name": None,
        "cwd": None,
        "entrypoint": None,
        "title": None,
        "agent_name": None,
        "model": None,
        "effort": None,
    }

    def setfirst(key, value):
        if fields[key] is not None:
            return
        text = as_str(value)
        if text is not None:
            fields[key] = text

    records = 0
    parse_errors = 0
    role_counts = {}
    type_counts = {}
    turn_ended = 0
    user_records = 0
    assistant_records = 0
    user_turn_keys = set()
    assistant_turn_keys = set()
    models = []
    seen_models = set()
    started = started_key = None
    ended = ended_key = None
    tokens = {
        "input": 0,
        "output": 0,
        "cache_read": 0,
        "cache_creation": 0,
        "total": 0,
    }
    have_tokens = False

    def add_model(value):
        value = as_str(value)
        if value is None or value in seen_models:
            return
        seen_models.add(value)
        models.append(value)
        setfirst("model", value)

    def update_span(value):
        nonlocal started, started_key, ended, ended_key
        key = ts_key(value)
        if key is None:
            return
        if started_key is None or key < started_key:
            started, started_key = value, key
        if ended_key is None or key > ended_key:
            ended, ended_key = value, key

    def add_usage(node):
        nonlocal have_tokens
        if not isinstance(node, dict):
            return
        input_tokens = as_int(node.get("input_tokens"))
        if input_tokens is None:
            input_tokens = as_int(node.get("prompt_tokens"))
        output_tokens = as_int(node.get("output_tokens"))
        if output_tokens is None:
            output_tokens = as_int(node.get("completion_tokens"))
        cache_read = as_int(node.get("cache_read_input_tokens"))
        if cache_read is None:
            cache_read = as_int(node.get("cached_input_tokens"))
        cache_creation = as_int(node.get("cache_creation_input_tokens"))
        total = as_int(node.get("total_tokens"))
        if any(v is not None for v in (input_tokens, output_tokens, cache_read, cache_creation, total)):
            have_tokens = True
            tokens["input"] += input_tokens or 0
            tokens["output"] += output_tokens or 0
            tokens["cache_read"] += cache_read or 0
            tokens["cache_creation"] += cache_creation or 0
            tokens["total"] += total or 0

    try:
        handle = open(path, "r", encoding="utf-8", errors="replace")
    except OSError as exc:
        sys.stderr.write("parse-cursor-transcript: cannot open %s: %s\n" % (path, exc))
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

            msg = as_dict(rec.get("message"))
            metadata = as_dict(rec.get("metadata"))
            message_metadata = as_dict(msg.get("metadata"))
            tool_input = {}

            role = first_string(rec.get("role"), msg.get("role"), rec.get("type"))
            rec_type = as_str(rec.get("type"))
            if role:
                role_counts[role] = role_counts.get(role, 0) + 1
            if rec_type:
                type_counts[rec_type] = type_counts.get(rec_type, 0) + 1
                if rec_type == "turn_ended":
                    turn_ended += 1

            setfirst("session_id", first_string(
                rec.get("session_id"), rec.get("sessionId"),
                metadata.get("session_id"), metadata.get("sessionId"),
            ))
            setfirst("conversation_id", first_string(
                rec.get("conversation_id"), rec.get("conversationId"),
                rec.get("chat_id"), rec.get("chatId"),
                metadata.get("conversation_id"), metadata.get("conversationId"),
            ))
            setfirst("bridge_session_id", first_string(
                rec.get("bridge_session_id"), rec.get("bridgeSessionId"),
                metadata.get("bridge_session_id"), metadata.get("bridgeSessionId"),
            ))
            setfirst("version", first_string(
                rec.get("version"), rec.get("cli_version"), rec.get("tool_version"),
                metadata.get("version"), metadata.get("cli_version"),
            ))
            setfirst("tool_version", first_string(
                rec.get("tool_version"), rec.get("agent_version"), metadata.get("tool_version"),
            ))
            setfirst("tool_name", first_string(rec.get("tool"), rec.get("tool_name"), metadata.get("tool")))
            setfirst("cwd", first_string(
                rec.get("cwd"), rec.get("working_directory"), rec.get("workspace_root"),
                metadata.get("cwd"), metadata.get("working_directory"),
            ))
            setfirst("entrypoint", first_string(rec.get("entrypoint"), metadata.get("entrypoint")))
            setfirst("title", first_string(rec.get("title"), metadata.get("title")))
            setfirst("agent_name", first_string(rec.get("agent_name"), rec.get("agentName"), metadata.get("agent_name")))
            setfirst("effort", first_string(rec.get("effort"), rec.get("reasoning_effort"), metadata.get("effort")))

            update_span(rec.get("timestamp"))
            update_span(rec.get("created_at"))
            update_span(rec.get("createdAt"))
            update_span(msg.get("timestamp"))
            update_span(message_metadata.get("timestamp"))

            add_model(first_string(
                rec.get("model"), metadata.get("model"), msg.get("model"),
                message_metadata.get("model"), get_path(rec, "request", "model"),
            ))

            content = msg.get("content")
            if role == "user":
                user_records += 1
                mid = first_string(rec.get("id"), msg.get("id"), metadata.get("turn_id"))
                key = mid if mid is not None else "\0rec:%d" % records
                user_turn_keys.add(key)
            elif role == "assistant":
                assistant_records += 1
                mid = first_string(rec.get("id"), msg.get("id"), message_metadata.get("id"))
                key = mid if mid is not None else "\0rec:%d" % records
                assistant_turn_keys.add(key)

            for block in as_list(content):
                if not isinstance(block, dict):
                    continue
                add_model(block.get("model"))
                if block.get("type") == "tool_use":
                    tool_input = as_dict(block.get("input"))
                    # Cursor's current transcripts often lack a session cwd but
                    # shell tool calls carry their working directory. Treat that
                    # as a best-effort fallback only when no explicit cwd exists.
                    setfirst("cwd", tool_input.get("working_directory"))

            for candidate in iter_dicts(rec):
                if "usage" in candidate and isinstance(candidate.get("usage"), dict):
                    add_usage(candidate.get("usage"))
                if "token_usage" in candidate and isinstance(candidate.get("token_usage"), dict):
                    add_usage(candidate.get("token_usage"))
                if "tokenUsage" in candidate and isinstance(candidate.get("tokenUsage"), dict):
                    add_usage(candidate.get("tokenUsage"))

    user_turns = len(user_turn_keys) or user_records
    assistant_turns = turn_ended or len(assistant_turn_keys) or assistant_records

    if have_tokens and tokens["total"] == 0:
        tokens["total"] = tokens["input"] + tokens["output"] + tokens["cache_read"] + tokens["cache_creation"]

    out = []

    def emit(name, value):
        if value is None:
            return
        if isinstance(value, str) and value == "":
            return
        out.append("cursor_%s=%s" % (name, sh_quote(value)))

    for key in fields:
        emit(key, fields[key])

    emit("records", records)
    if parse_errors:
        emit("parse_errors", parse_errors)
    emit("user_turns", user_turns)
    emit("assistant_turns", assistant_turns)
    emit("user_records", user_records)
    emit("assistant_records", assistant_records)
    if turn_ended:
        emit("turn_ended_records", turn_ended)
    if role_counts:
        ordered_roles = sorted(role_counts)
        emit("raw_role_counts", ",".join("%s:%d" % (role, role_counts[role]) for role in ordered_roles))
    if type_counts:
        ordered_types = sorted(type_counts)
        emit("raw_type_counts", ",".join("%s:%d" % (typ, type_counts[typ]) for typ in ordered_types))
    if models:
        emit("models", ",".join(models))
        emit("models_count", len(models))

    emit("started_at", started)
    emit("ended_at", ended)

    if have_tokens:
        emit("input_tokens", tokens["input"])
        emit("output_tokens", tokens["output"])
        emit("cache_read_tokens", tokens["cache_read"])
        emit("cache_creation_tokens", tokens["cache_creation"])
        emit("total_tokens", tokens["total"])

    sys.stdout.write("\n".join(out) + ("\n" if out else ""))
    return 0


sys.exit(main())
PYEOF
