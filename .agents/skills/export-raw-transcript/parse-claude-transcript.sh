#!/usr/bin/env bash
#
# Parse metadata from a Claude Code JSONL transcript.
#
# Companion to parse-codex-transcript.sh, but Claude transcripts need a real JSON
# engine where Codex could get by on sed/grep:
#   * Record key order is NOT stable. Control records start with {"type":...} but
#     message records (user/assistant/system/attachment) start with
#     {"parentUuid":...} and bury "type" deep in the line, so substring matching
#     mis-detects record types.
#   * The interesting facts (turn counts, distinct models, session span, token
#     totals) require a full pass over every record, and a record's nested
#     content can contain the exact substrings a regex would key on (e.g. an
#     assistant message that quotes "type":"user" or "model":"...").
# So the JSON engine is python3 — which export-raw-transcript.sh already requires
# for schema validation, so this adds no new dependency. python streams the file
# one line at a time (json.loads per record); it never loads the whole transcript
# into memory and never surfaces transcript contents to the model.
#
# Output (default --shell): shell-safe claude_* assignments, the same contract as
# parse-codex-transcript.sh, so export-raw-transcript.sh can `eval` the result.

set -uo pipefail

prog="parse-claude-transcript"
die() {
  printf '%s: %s\n' "$prog" "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage:
  bash parse-claude-transcript.sh [--shell] <claude-transcript.jsonl>

Outputs shell-safe claude_* assignments for metadata found in a Claude Code
JSONL transcript:
  session scalars: session_id, version (CLI version), git_branch, cwd,
                   entrypoint, user_type, permission_mode, bridge_session_id,
                   custom_title, ai_title, agent_name
  aggregates:      records (total JSONL records),
                   user_turns (human INPUT turns — messages the person actually
                     sent: excludes tool results, injected meta/compact-summary
                     records, and sub-agent traffic),
                   assistant_turns (main-agent turn count — distinct assistant
                     message ids, excluding sub-agent (sidechain) and synthetic
                     messages; one API response logged as several records counts
                     once),
                   user_records / assistant_records (raw type=user / type=assistant
                     record counts — the pre-collapse numbers),
                   parse_errors, system_turns, summary_turns, sidechain_turns,
                   model (primary), models (csv), models_count, started_at,
                   ended_at, and assistant token totals: input_tokens,
                   output_tokens, cache_read_tokens, cache_creation_tokens,
                   total_tokens
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
command -v python3 >/dev/null 2>&1 || die "python3 is required to parse Claude transcripts"

# The transcript path is passed as argv so nothing is interpolated into the
# (single-quoted) heredoc; the program reads it with sys.argv[1].
python3 - "$TRANSCRIPT" <<'PYEOF'
import json
import sys


def ts_key(ts):
    """Lexicographically-comparable key for an ISO-8601 UTC timestamp.

    Claude writes millisecond precision with a trailing 'Z' (e.g.
    2026-06-26T03:21:33.941Z), but normalize fractional seconds to a fixed width
    so timestamps of differing precision still order correctly.
    """
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


def as_int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else 0


def sh_quote(s):
    return "'" + str(s).replace("'", "'\\''") + "'"


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("parse-claude-transcript: missing transcript path\n")
        return 2
    path = sys.argv[1]

    # First non-empty value wins for session scalars (control records such as
    # "mode"/"last-prompt" omit cwd/version, so this naturally skips them).
    fields = {
        "session_id": None, "version": None, "git_branch": None, "cwd": None,
        "entrypoint": None, "user_type": None, "permission_mode": None,
        "bridge_session_id": None, "custom_title": None, "ai_title": None,
        "agent_name": None,
    }
    records = 0
    parse_errors = 0
    counts = {}
    sidechain = 0
    user_input_turns = 0  # real human messages (not tool results / injected / sub-agent)
    main_turn_keys = set()  # distinct main-agent assistant message ids = real turns
    models = {}
    started = started_key = None
    ended = ended_key = None
    tok = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    have_tokens = False

    def setfirst(key, val):
        if fields[key] is None and isinstance(val, str) and val != "":
            fields[key] = val

    try:
        fh = open(path, "r", encoding="utf-8", errors="replace")
    except OSError as exc:
        sys.stderr.write("parse-claude-transcript: cannot open %s: %s\n" % (path, exc))
        return 1

    with fh:
        for line in fh:
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

            t = rec.get("type")
            if isinstance(t, str):
                counts[t] = counts.get(t, 0) + 1

            setfirst("session_id", rec.get("sessionId"))
            setfirst("version", rec.get("version"))
            setfirst("git_branch", rec.get("gitBranch"))
            setfirst("cwd", rec.get("cwd"))
            setfirst("entrypoint", rec.get("entrypoint"))
            setfirst("user_type", rec.get("userType"))
            setfirst("permission_mode", rec.get("permissionMode"))
            if t == "bridge-session":
                setfirst("bridge_session_id", rec.get("bridgeSessionId"))
            elif t == "custom-title":
                setfirst("custom_title", rec.get("customTitle"))
            elif t == "ai-title":
                setfirst("ai_title", rec.get("aiTitle"))
            elif t == "agent-name":
                setfirst("agent_name", rec.get("agentName"))

            if rec.get("isSidechain") is True:
                sidechain += 1

            ts = rec.get("timestamp")
            if isinstance(ts, str) and ts:
                k = ts_key(ts)
                if started_key is None or k < started_key:
                    started, started_key = ts, k
                if ended_key is None or k > ended_key:
                    ended, ended_key = ts, k

            if t == "user":
                # A human input turn is a message the person actually sent. The
                # transcript records tool results as type=user too, and injects
                # meta/compact-summary records and sub-agent (sidechain) traffic;
                # none of those are turns. What remains — a typed message or a
                # slash command — is one input turn.
                if (rec.get("isSidechain") is not True
                        and rec.get("isMeta") is not True
                        and rec.get("isCompactSummary") is not True
                        and rec.get("isVisibleInTranscript") is not False):
                    msg = rec.get("message")
                    is_tool_result = False
                    if isinstance(msg, dict):
                        content = msg.get("content")
                        if isinstance(content, list):
                            for block in content:
                                if (isinstance(block, dict)
                                        and block.get("type") == "tool_result"):
                                    is_tool_result = True
                                    break
                        if not is_tool_result:
                            user_input_turns += 1
            elif t == "assistant":
                msg = rec.get("message")
                if isinstance(msg, dict):
                    m = msg.get("model")
                    # "<synthetic>" marks harness-injected (e.g. API-error)
                    # messages, not a model the user actually ran.
                    synthetic = m == "<synthetic>"
                    if isinstance(m, str) and m and not synthetic:
                        models[m] = models.get(m, 0) + 1
                    # One assistant API response (one message id) is logged as
                    # several records — a text block, then a record per tool_use —
                    # so collapse by id to count real main-agent turns; drop
                    # sub-agent (sidechain) and synthetic records. A record with no
                    # id falls back to a per-record key so it still counts once.
                    if rec.get("isSidechain") is not True and not synthetic:
                        mid = msg.get("id")
                        key = mid if isinstance(mid, str) and mid else "\0rec:%d" % records
                        main_turn_keys.add(key)
                    u = msg.get("usage")
                    if isinstance(u, dict):
                        tok["input"] += as_int(u.get("input_tokens"))
                        tok["output"] += as_int(u.get("output_tokens"))
                        tok["cache_read"] += as_int(u.get("cache_read_input_tokens"))
                        tok["cache_creation"] += as_int(u.get("cache_creation_input_tokens"))
                        have_tokens = True

    out = []

    def emit(name, val):
        if val is None:
            return
        if isinstance(val, str) and val == "":
            return
        out.append("claude_%s=%s" % (name, sh_quote(val)))

    for key in ("session_id", "version", "git_branch", "cwd", "entrypoint",
                "user_type", "permission_mode", "bridge_session_id",
                "custom_title", "ai_title", "agent_name"):
        emit(key, fields[key])

    emit("records", records)
    if parse_errors:
        emit("parse_errors", parse_errors)
    emit("user_turns", user_input_turns)
    emit("assistant_turns", len(main_turn_keys))
    emit("user_records", counts.get("user", 0))
    emit("assistant_records", counts.get("assistant", 0))
    emit("system_turns", counts.get("system", 0))
    if counts.get("summary", 0):
        emit("summary_turns", counts.get("summary", 0))
    if sidechain:
        emit("sidechain_turns", sidechain)

    if models:
        ordered = sorted(models.keys(), key=lambda name: (-models[name], name))
        emit("model", ordered[0])
        emit("models", ",".join(ordered))
        emit("models_count", len(ordered))

    emit("started_at", started)
    emit("ended_at", ended)

    if have_tokens:
        total = tok["input"] + tok["output"] + tok["cache_read"] + tok["cache_creation"]
        emit("input_tokens", tok["input"])
        emit("output_tokens", tok["output"])
        emit("cache_read_tokens", tok["cache_read"])
        emit("cache_creation_tokens", tok["cache_creation"])
        emit("total_tokens", total)

    sys.stdout.write("\n".join(out) + ("\n" if out else ""))
    return 0


sys.exit(main())
PYEOF
