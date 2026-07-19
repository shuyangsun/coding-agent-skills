#!/usr/bin/env bash
#
# Parse metadata from a Cursor agent JSONL transcript, enriched from Cursor's
# local composer store when available.
#
# Cursor agent-transcripts JSONL is intentionally sparse: typically
# {"role":"user"|"assistant","message":...} plus {"type":"turn_ended",...}.
# User turns often embed a wall-clock stamp as <timestamp>...</timestamp> in
# the text. Richer session scalars (title, model, effort, cwd, span) live in
# Cursor's local SQLite composer store (state.vscdb → composerData:<id>).
# This parser streams the JSONL with python3, then best-effort reads that
# store by session id — never dumping bubble bodies into the agent context.
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
  bash parse-cursor-transcript.sh [--shell] [--session-id <uuid>] <cursor-transcript.jsonl>

Outputs shell-safe cursor_* assignments for metadata found in Cursor JSONL
records and, when present, the local Cursor composer store (state.vscdb):
  session scalars: session_id, version/tool info, cwd/entrypoint, title,
                   agent name, bridge/session identifiers, model, effort
  aggregates:      records, user_turns, assistant_turns, user_records,
                   assistant_records, raw role counts, parse_errors, models,
                   started_at, ended_at, and token totals when present

--session-id overrides the session id inferred from the transcript path. Use it
when parsing a renamed export copy so composer-store enrichment still works.
EOF
}

MODE="shell"
TRANSCRIPT=""
SESSION_ID_OVERRIDE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --shell) MODE="shell" ;;
    --session-id)
      shift
      [ $# -gt 0 ] || die "--session-id requires a value"
      SESSION_ID_OVERRIDE="$1"
      ;;
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

# Paths/ids are passed as argv so nothing from the transcript is interpolated
# into the heredoc. The program streams json.loads one record at a time, then
# optionally opens the local composer DB read-only for missing fields.
python3 - "$TRANSCRIPT" "$SESSION_ID_OVERRIDE" <<'PYEOF'
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone


MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

TIMESTAMP_TAG_RE = re.compile(r"<timestamp>\s*(.*?)\s*</timestamp>", re.I | re.S)
CURSOR_WALL_RE = re.compile(
    r"^[A-Za-z]+,\s+([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4}),\s+"
    r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)\s*\(UTC([+-]\d{1,2})(?::?(\d{2}))?\)$",
    re.I,
)


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


def ms_to_utc(ms):
    ms = as_int(ms)
    if ms is None:
        return None
    # Cursor stores composer created/updated as unix milliseconds.
    dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(ms % 1000):03d}Z"


def parse_cursor_wall_clock(text):
    """Parse Cursor's embedded wall-clock stamp into an ISO UTC string."""
    text = as_str(text)
    if text is None:
        return None
    text = " ".join(text.split())
    match = CURSOR_WALL_RE.match(text)
    if not match:
        return None
    mon_s, day_s, year_s, hour_s, minute_s, second_s, ampm, off_h, off_m = match.groups()
    month = MONTHS.get(mon_s[:3].lower())
    if month is None:
        return None
    hour = int(hour_s)
    minute = int(minute_s)
    second = int(second_s or "0")
    ampm = ampm.upper()
    if ampm == "PM" and hour != 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    offset = timedelta(hours=int(off_h), minutes=int(off_m or "0"))
    local = datetime(int(year_s), month, int(day_s), hour, minute, second, tzinfo=timezone(offset))
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_embedded_timestamps(text):
    text = as_str(text)
    if text is None:
        return
    for match in TIMESTAMP_TAG_RE.finditer(text):
        iso = parse_cursor_wall_clock(match.group(1))
        if iso is not None:
            yield iso


def candidate_state_db_paths():
    home = os.path.expanduser("~")
    return [
        os.path.join(home, "Library", "Application Support", "Cursor", "User", "globalStorage", "state.vscdb"),
        os.path.join(home, ".config", "Cursor", "User", "globalStorage", "state.vscdb"),
        os.path.join(home, ".cursor", "User", "globalStorage", "state.vscdb"),
    ]


def candidate_app_package_paths():
    home = os.path.expanduser("~")
    return [
        "/Applications/Cursor.app/Contents/Resources/app/package.json",
        os.path.join(home, "Applications", "Cursor.app", "Contents", "Resources", "app", "package.json"),
        "/usr/share/cursor/resources/app/package.json",
        os.path.join(home, ".local", "share", "cursor", "resources", "app", "package.json"),
    ]


def read_cursor_app_version():
    for path in candidate_app_package_paths():
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError, TypeError):
            continue
        version = as_str(data.get("version")) if isinstance(data, dict) else None
        if version is not None:
            return version
    return None


def open_state_db():
    for path in candidate_state_db_paths():
        if not os.path.isfile(path):
            continue
        try:
            # Read-only URI so a live Cursor IDE lock cannot block export.
            return sqlite3.connect(f"file:{path}?mode=ro", uri=True), path
        except sqlite3.Error:
            continue
    return None, None


def load_json_blob(raw):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def effort_from_model_config(model_config):
    model_config = as_dict(model_config)
    for selected in as_list(model_config.get("selectedModels")):
        selected = as_dict(selected)
        for param in as_list(selected.get("parameters")):
            param = as_dict(param)
            if as_str(param.get("id")) == "effort":
                value = param.get("value")
                if isinstance(value, bool):
                    continue
                text = as_str(value) if not isinstance(value, (int, float)) else str(value)
                if text is not None:
                    return text
    return first_string(model_config.get("effort"), model_config.get("reasoningEffort"))


def enrich_from_composer(session_id, fields, add_model, update_span):
    """Fill missing scalars from Cursor's composerData / composerHeaders."""
    if not session_id:
        return False
    con, _path = open_state_db()
    if con is None:
        return False
    found = False
    try:
        cur = con.cursor()
        row = cur.execute(
            "SELECT value FROM cursorDiskKV WHERE key = ?",
            ("composerData:%s" % session_id,),
        ).fetchone()
        data = load_json_blob(row[0]) if row else None
        if data is None:
            header = cur.execute(
                "SELECT createdAt, lastUpdatedAt, value FROM composerHeaders WHERE composerId = ?",
                (session_id,),
            ).fetchone()
            if header is None:
                return False
            data = load_json_blob(header[2]) or {}
            if fields["title"] is None:
                fields["title"] = first_string(data.get("name"), data.get("title"))
            update_span(ms_to_utc(header[0]))
            update_span(ms_to_utc(header[1]))
            cwd = first_string(
                get_path(data, "workspaceIdentifier", "uri", "fsPath"),
                get_path(data, "workspaceIdentifier", "uri", "path"),
            )
            if fields["cwd"] is None and cwd is not None:
                fields["cwd"] = cwd
            found = True
        else:
            found = True
            if fields["title"] is None:
                fields["title"] = first_string(data.get("name"), data.get("title"))
            model_config = as_dict(data.get("modelConfig"))
            add_model(first_string(model_config.get("modelName"), model_config.get("modelId")))
            for selected in as_list(model_config.get("selectedModels")):
                add_model(as_dict(selected).get("modelId"))
            if fields["effort"] is None:
                fields["effort"] = effort_from_model_config(model_config)
            cwd = first_string(
                get_path(data, "workspaceIdentifier", "uri", "fsPath"),
                get_path(data, "workspaceIdentifier", "uri", "path"),
            )
            if fields["cwd"] is None and cwd is not None:
                fields["cwd"] = cwd
            if fields["entrypoint"] is None:
                # Composer rows only exist for the IDE/agent UI path.
                fields["entrypoint"] = "ide"
            update_span(ms_to_utc(data.get("createdAt")))
            update_span(ms_to_utc(data.get("lastUpdatedAt")))
            for header in as_list(data.get("fullConversationHeadersOnly")):
                header = as_dict(header)
                update_span(header.get("createdAt"))

        # conversation-search title is a useful fallback when composer name is empty.
        if fields["title"] is None:
            for search_db in (
                os.path.join(os.path.dirname(p), "conversation-search.db")
                for p in candidate_state_db_paths()
            ):
                if not os.path.isfile(search_db):
                    continue
                try:
                    scon = sqlite3.connect(f"file:{search_db}?mode=ro", uri=True)
                except sqlite3.Error:
                    continue
                try:
                    srow = scon.execute(
                        "SELECT title FROM conversations WHERE id = ?",
                        (session_id,),
                    ).fetchone()
                finally:
                    scon.close()
                if srow and as_str(srow[0]):
                    fields["title"] = as_str(srow[0])
                    break
    finally:
        con.close()
    return found


def looks_like_uuid(value):
    value = as_str(value)
    if value is None:
        return False
    parts = value.split("-")
    if len(parts) != 5:
        return False
    return all(all(c in "0123456789abcdefABCDEF" for c in part) for part in parts) and \
        [len(p) for p in parts] == [8, 4, 4, 4, 12]


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("parse-cursor-transcript: missing transcript path\n")
        return 2
    path = sys.argv[1]
    session_id_override = as_str(sys.argv[2]) if len(sys.argv) > 2 else None

    # Filename and parent folder are both stable session-id candidates in Cursor's
    # current transcript layout: agent-transcripts/<id>/<id>.jsonl. Renamed export
    # copies need --session-id (or a UUID parent folder) to hit the composer store.
    filename_id = os.path.splitext(os.path.basename(path))[0]
    parent_id = os.path.basename(os.path.dirname(path))
    if session_id_override:
        session_id_fallback = session_id_override
    elif looks_like_uuid(filename_id):
        session_id_fallback = filename_id
    elif looks_like_uuid(parent_id):
        session_id_fallback = parent_id
    else:
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
    embedded_started = embedded_started_key = None
    embedded_ended = embedded_ended_key = None
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

    def update_embedded_span(value):
        # Minute-rounded wall-clock stamps from <timestamp> tags are a fallback
        # only — composer/JSONL ISO stamps with seconds win when present.
        nonlocal embedded_started, embedded_started_key, embedded_ended, embedded_ended_key
        key = ts_key(value)
        if key is None:
            return
        if embedded_started_key is None or key < embedded_started_key:
            embedded_started, embedded_started_key = value, key
        if embedded_ended_key is None or key > embedded_ended_key:
            embedded_ended, embedded_ended_key = value, key

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
                text = block.get("text")
                if isinstance(text, str) and text:
                    for iso in extract_embedded_timestamps(text):
                        update_embedded_span(iso)

            for candidate in iter_dicts(rec):
                if "usage" in candidate and isinstance(candidate.get("usage"), dict):
                    add_usage(candidate.get("usage"))
                if "token_usage" in candidate and isinstance(candidate.get("token_usage"), dict):
                    add_usage(candidate.get("token_usage"))
                if "tokenUsage" in candidate and isinstance(candidate.get("tokenUsage"), dict):
                    add_usage(candidate.get("tokenUsage"))

    # Composer store fills the scalars JSONL omits (title/model/effort/cwd/span).
    enrich_from_composer(fields["session_id"], fields, add_model, update_span)
    if started is None:
        update_span(embedded_started)
    if ended is None:
        update_span(embedded_ended)

    if fields["tool_version"] is None and fields["version"] is None:
        app_version = read_cursor_app_version()
        if app_version is not None:
            fields["tool_version"] = app_version
            fields["version"] = app_version

    if fields["entrypoint"] is None and os.environ.get("CURSOR_AGENT"):
        fields["entrypoint"] = "ide"

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
