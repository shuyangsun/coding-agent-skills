#!/usr/bin/env bash
#
# export-raw-transcript.sh — copy the CURRENT coding-agent session's RAW transcript
# file (verbatim, byte-for-byte) into ~/Downloads/transcripts/<YYYYMMDD>/ and write
# a rich JSON metadata sidecar next to it.
#
# Bundled with the `export-raw-transcript` skill. Repo-agnostic: it detects the
# operating system, detects the active agent (Claude Code, Codex, Cursor,
# Antigravity, Gemini CLI), locates that agent's current session transcript,
# resolves the working repo on its own, and creates the destination directory if
# missing.
#
# It NEVER reads transcript *contents* into the agent. For Codex, Claude, and Cursor, a
# companion parser streams the raw JSONL in a subprocess so model/version/cwd,
# session span, turn counts, model list, and token totals can be captured
# accurately without surfacing transcript bytes to the agent. The script also
# copies bytes and stats the file (size / line count / sha256). Transcripts can
# be huge, so the agent must not cat/open them; this script does everything
# mechanical.
#
# Usage:
#   bash export-raw-transcript.sh --detect [--tool SLUG]
#       Print what WOULD be exported (OS, agent, source file, size) and exit
#       without writing anything. Run this first to confirm the right session.
#
#   bash export-raw-transcript.sh [options] <short-name>
#       Copy the transcript to
#         ~/Downloads/transcripts/<YYYYMMDD>/<utc-ts>-<short-name>.<ext>
#       and write the metadata sidecar
#         ~/Downloads/transcripts/<YYYYMMDD>/<utc-ts>-<short-name>-metadata.json
#       <short-name> is a short kebab-case slug describing the session.
#
# Options:
#   --tool <slug>     Force the agent: claude | codex | cursor | antigravity |
#                     gemini. Default: auto-detect (env markers, then newest
#                     transcript across all known stores).
#   --title <str>     Concise session title for the metadata (kept short for the
#                     gem card; trimmed to 70 chars at a word boundary).
#   --summary <str>   Concise one/two-sentence summary (trimmed to 160 chars at a
#                     word boundary so it fits the card's clamped summary).
#   --model <str>     Exact model + variant the agent ran, e.g.
#                     "Claude Opus 4.8 (1M context)". The running agent knows
#                     this even though the environment usually doesn't.
#   --issue <ref>     An issue/bug the session referenced, as "<url> [title...]".
#                     Repeatable. The URL is parsed for key/tracker (GitHub,
#                     GitLab, Jira, Linear, Buganizer).
#   --change <ref>    A PR/MR/CL the session referenced, as "<url> [title...]".
#                     Repeatable. The URL is parsed for number/host/repo (GitHub,
#                     GitLab, Gerrit).
#   --tag <str>       A short topic tag for the gem card. Repeatable. --tags
#                     <a,b,c> adds several comma-separated tags at once.
#   --asset-original <path>
#                     A known original absolute path for an asset attached in the
#                     session (repeatable). Claude verifies it against embedded
#                     bytes before mirroring that path; Codex copies it when the
#                     file exists because Codex usually stores only disk refs.
#                     Attachments are auto-extracted even without this when the
#                     transcript exposes enough local-file evidence. See ASSETS.md.
#   --out-root <dir>  Destination root. Default: ~/Downloads/transcripts
#   -h, --help        Show this help.
#
# Timestamps and the dated folder are UTC, derived from one instant so the
# <utc-ts> prefix always matches its <YYYYMMDD> folder.

set -uo pipefail

prog="export-raw-transcript"
msg() { printf '%s: %s\n' "$prog" "$*"; }
die() {
  printf '%s: %s\n' "$prog" "$*" >&2
  exit 1
}

usage() {
  sed -n '2,/^set -uo/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//; s/^#$//' | sed '$d'
}

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------
DETECT_ONLY=""
FORCE_TOOL=""
TITLE=""
SUMMARY=""
MODEL=""
OUT_ROOT="${HOME}/Downloads/transcripts"
SHORT_NAME_RAW=""
# Repeatable reference/tag inputs, accumulated as newline-delimited strings so the
# script stays bash-3.2 safe (no `"${arr[@]}"` expansion of an empty array under
# `set -u`). Each --issue/--change value is "<url> [optional title words...]".
ISSUE_SPECS=""
CHANGE_SPECS=""
TAGS_RAW=""
# Known original absolute paths for attached assets (newline-delimited, like the
# specs above). See ASSETS.md for per-agent behavior.
ASSET_ORIGINALS=""

# Append one newline-delimited record to a variable (blank leading line is fine;
# the python normalizers skip empty lines).
add_line() { printf '%s\n%s' "$1" "$2"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --detect) DETECT_ONLY=1 ;;
    --tool) FORCE_TOOL="${2:-}"; shift ;;
    --tool=*) FORCE_TOOL="${1#*=}" ;;
    --title) TITLE="${2:-}"; shift ;;
    --title=*) TITLE="${1#*=}" ;;
    --summary) SUMMARY="${2:-}"; shift ;;
    --summary=*) SUMMARY="${1#*=}" ;;
    --model) MODEL="${2:-}"; shift ;;
    --model=*) MODEL="${1#*=}" ;;
    --issue) ISSUE_SPECS="$(add_line "$ISSUE_SPECS" "${2:-}")"; shift ;;
    --issue=*) ISSUE_SPECS="$(add_line "$ISSUE_SPECS" "${1#*=}")" ;;
    --change) CHANGE_SPECS="$(add_line "$CHANGE_SPECS" "${2:-}")"; shift ;;
    --change=*) CHANGE_SPECS="$(add_line "$CHANGE_SPECS" "${1#*=}")" ;;
    --tag) TAGS_RAW="$(add_line "$TAGS_RAW" "${2:-}")"; shift ;;
    --tag=*) TAGS_RAW="$(add_line "$TAGS_RAW" "${1#*=}")" ;;
    --tags) TAGS_RAW="$(add_line "$TAGS_RAW" "${2:-}")"; shift ;;
    --tags=*) TAGS_RAW="$(add_line "$TAGS_RAW" "${1#*=}")" ;;
    --asset-original) ASSET_ORIGINALS="$(add_line "$ASSET_ORIGINALS" "${2:-}")"; shift ;;
    --asset-original=*) ASSET_ORIGINALS="$(add_line "$ASSET_ORIGINALS" "${1#*=}")" ;;
    --out-root) OUT_ROOT="${2:-}"; shift ;;
    --out-root=*) OUT_ROOT="${1#*=}" ;;
    -h | --help) usage; exit 0 ;;
    --*) die "unknown option: $1 (try --help)" ;;
    *)
      if [ -n "$SHORT_NAME_RAW" ]; then die "unexpected extra argument: $1"; fi
      SHORT_NAME_RAW="$1"
      ;;
  esac
  shift
done

if [ -n "$FORCE_TOOL" ]; then
  case "$FORCE_TOOL" in
    claude | codex | cursor | antigravity | gemini) ;;
    *) die "--tool must be one of: claude codex cursor antigravity gemini" ;;
  esac
fi

# ---------------------------------------------------------------------------
# OS detection (macOS vs Linux) — drives stat/date/sha portability and metadata
# ---------------------------------------------------------------------------
kernel="$(uname -s 2>/dev/null || echo unknown)"
case "$kernel" in
  Darwin) platform="macos" ;;
  Linux) platform="linux" ;;
  *) platform="$(printf '%s' "$kernel" | tr '[:upper:]' '[:lower:]')" ;;
esac
arch="$(uname -m 2>/dev/null || echo unknown)"
host="$(uname -n 2>/dev/null || echo '')"

# ---------------------------------------------------------------------------
# Portable helpers (BSD / macOS and GNU / Linux; bash 3.2 safe)
# ---------------------------------------------------------------------------
shopt -s nullglob
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

file_mtime_epoch() {
  if [ "$kernel" = "Darwin" ]; then
    stat -f %m "$1" 2>/dev/null
  else
    stat -c %Y "$1" 2>/dev/null
  fi
}

fmt_epoch() { # fmt_epoch <epoch> <strftime-fmt>  -> formats in UTC
  if [ "$kernel" = "Darwin" ]; then
    date -u -r "$1" +"$2" 2>/dev/null
  else
    date -u -d "@$1" +"$2" 2>/dev/null
  fi
}

fmt_epoch_local() { # fmt_epoch_local <epoch> <strftime-fmt>  -> formats in local time
  if [ "$kernel" = "Darwin" ]; then
    date -r "$1" +"$2" 2>/dev/null
  else
    date -d "@$1" +"$2" 2>/dev/null
  fi
}

# Resolve the machine's IANA timezone name (e.g. America/New_York), best-effort.
local_tz_name() {
  if [ -n "${TZ:-}" ]; then printf '%s' "$TZ"; return; fi
  local link
  link="$(readlink /etc/localtime 2>/dev/null || true)"
  case "$link" in
    */zoneinfo/*) printf '%s' "${link#*/zoneinfo/}"; return ;;
  esac
  if command -v timedatectl >/dev/null 2>&1; then
    timedatectl show -p Timezone --value 2>/dev/null || true
  fi
}

sha256_of() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" 2>/dev/null | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" 2>/dev/null | awk '{print $1}'
  fi
}

# newest_file <file>...  -> prints the path with the newest mtime
newest_file() {
  local newest="" newest_m=-1 f m
  for f in "$@"; do
    [ -f "$f" ] || continue
    m="$(file_mtime_epoch "$f")"
    [ -n "$m" ] || continue
    if [ "$m" -gt "$newest_m" ]; then
      newest_m="$m"
      newest="$f"
    fi
  done
  printf '%s' "$newest"
}

# collect_find <dir> <find-args...>  -> fills global array FOUND with matches
collect_find() {
  FOUND=()
  local d="$1"
  shift
  [ -d "$d" ] || return 0
  local f
  while IFS= read -r -d '' f; do
    FOUND+=("$f")
  done < <(find "$d" "$@" -type f -print0 2>/dev/null)
}

newest_from_find() { # newest_from_find <dir> <find-args...>
  collect_find "$@"
  if [ "${#FOUND[@]}" -gt 0 ]; then newest_file "${FOUND[@]}"; fi
}

# ---------------------------------------------------------------------------
# Per-tool locators — each prints the current session's raw transcript path (or
# nothing). They prefer an exact "this session" signal, then fall back to the
# newest matching file by mtime (the live session is the one being appended to).
# ---------------------------------------------------------------------------
locate_claude() {
  local base="$HOME/.claude/projects" sid="${CLAUDE_CODE_SESSION_ID:-}" enc dir hit
  # 1) Exact current-session file, named <session-id>.jsonl, anywhere under projects.
  if [ -n "$sid" ]; then
    hit="$(newest_from_find "$base" -name "$sid.jsonl")"
    if [ -n "$hit" ]; then printf '%s' "$hit"; return; fi
  fi
  # 2) Encode the launch cwd to its project folder, newest .jsonl there.
  enc="$(printf '%s' "$PWD" | sed 's/[^a-zA-Z0-9]/-/g')"
  dir="$base/$enc"
  if [ -d "$dir" ]; then
    local cands=("$dir"/*.jsonl)
    if [ "${#cands[@]}" -gt 0 ]; then newest_file "${cands[@]}"; return; fi
  fi
  # 3) Last resort: newest .jsonl across every project.
  newest_from_find "$base" -name '*.jsonl'
}

locate_codex() {
  # Per-session rollout transcript: $CODEX_HOME/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl
  local home="${CODEX_HOME:-$HOME/.codex}"
  newest_from_find "$home/sessions" -name 'rollout-*.jsonl'
}

locate_cursor() {
  # Cursor IDE and cursor-agent both write per-session JSONL under
  # ~/.cursor/projects/<project>/agent-transcripts/<id>/<id>.jsonl. Prefer the
  # live conversation id when the agent injects it; otherwise newest parent
  # transcript (never a subagent sidecar).
  local id="${CURSOR_CONVERSATION_ID:-}" hit
  if [ -n "$id" ]; then
    hit="$(newest_from_find "$HOME/.cursor/projects" \
      -path "*/agent-transcripts/$id/$id.jsonl")"
    if [ -n "$hit" ]; then printf '%s' "$hit"; return; fi
  fi
  newest_from_find "$HOME/.cursor/projects" \
    -path '*/agent-transcripts/*/*.jsonl' \
    ! -path '*/subagents/*' \
    -name '*.jsonl'
}

locate_antigravity() {
  # Prefer the untruncated transcript; CLI store first, then the IDE store.
  local r hit
  for r in "$HOME/.gemini/antigravity-cli" "$HOME/.gemini/antigravity"; do
    hit="$(newest_from_find "$r/brain" -name 'transcript_full.jsonl')"
    if [ -n "$hit" ]; then printf '%s' "$hit"; return; fi
  done
  for r in "$HOME/.gemini/antigravity-cli" "$HOME/.gemini/antigravity"; do
    hit="$(newest_from_find "$r/brain" -name 'transcript.jsonl')"
    if [ -n "$hit" ]; then printf '%s' "$hit"; return; fi
  done
}

locate_gemini() {
  # Gemini CLI per-session chat file (.json now, migrating to .jsonl).
  local root="${GEMINI_CLI_HOME:-$HOME}/.gemini"
  newest_from_find "$root/tmp" -path '*/chats/*' '(' -name '*.json' -o -name '*.jsonl' ')'
}

locate_for_tool() {
  case "$1" in
    claude) locate_claude ;;
    codex) locate_codex ;;
    cursor) locate_cursor ;;
    antigravity) locate_antigravity ;;
    gemini) locate_gemini ;;
  esac
}

# ---------------------------------------------------------------------------
# Agent / tool detection
# ---------------------------------------------------------------------------
TOOL=""
DETECTED_VIA=""
SRC=""

infer_tool_by_newest() {
  local t src m best_tool="" best_src="" best_m=-1
  for t in claude codex cursor antigravity gemini; do
    src="$(locate_for_tool "$t")"
    [ -n "$src" ] || continue
    m="$(file_mtime_epoch "$src")"
    [ -n "$m" ] || continue
    if [ "$m" -gt "$best_m" ]; then
      best_m="$m"
      best_tool="$t"
      best_src="$src"
    fi
  done
  TOOL="$best_tool"
  SRC="$best_src"
  DETECTED_VIA="inferred:newest-mtime"
}

detect_tool() {
  if [ -n "$FORCE_TOOL" ]; then
    TOOL="$FORCE_TOOL"
    DETECTED_VIA="flag:--tool"
    return
  fi
  # Authoritative env markers the running agent injects into shell commands.
  if [ -n "${CLAUDECODE:-}" ] || [ -n "${CLAUDE_CODE_SESSION_ID:-}" ]; then
    TOOL="claude"
    DETECTED_VIA="env:CLAUDECODE"
    return
  fi
  if [ "${GEMINI_CLI:-}" = "1" ]; then
    TOOL="gemini"
    DETECTED_VIA="env:GEMINI_CLI"
    return
  fi
  if [ -n "${CURSOR_AGENT:-}" ]; then
    TOOL="cursor"
    DETECTED_VIA="env:CURSOR_AGENT"
    return
  fi
  if [ -n "${CODEX_HOME:-}" ] && [ -d "${CODEX_HOME}/sessions" ]; then
    TOOL="codex"
    DETECTED_VIA="env:CODEX_HOME"
    return
  fi
  # Codex and Antigravity expose no session env var (verified open feature
  # requests). Infer by the most recently written transcript across all stores —
  # the live session's file is being appended to right now.
  infer_tool_by_newest
}

detect_tool
[ -n "$TOOL" ] || die "could not detect a coding-agent transcript store. Pass --tool <slug> explicitly."

# Locate the source (infer_tool_by_newest already cached SRC; otherwise locate now).
if [ -z "$SRC" ]; then
  SRC="$(locate_for_tool "$TOOL")"
fi

if [ -z "$SRC" ] || [ ! -f "$SRC" ]; then
  if [ "$TOOL" = "cursor" ]; then
    die "no Cursor agent transcript found under ~/.cursor/projects/*/agent-transcripts/<id>/<id>.jsonl.
The IDE also keeps a live composer store in state.vscdb (used only to enrich
metadata — title, model, effort, cwd, span); the raw export still needs the
per-session JSONL. Confirm this chat has an agent-transcripts file, or pass
--tool cursor after the first agent turn has flushed one."
  fi
  die "could not locate a current transcript for '$TOOL'. Pass --tool / --out-root, or check the agent is the one running this."
fi

vendor=""; tool_name=""; tool_version=""; effort=""; entrypoint=""; session_id=""; session_cwd=""
src_base="$(basename "$SRC")"
case "$TOOL" in
  claude)
    vendor="anthropic"; tool_name="claude-code"
    entrypoint="${CLAUDE_CODE_ENTRYPOINT:-}"
    effort="${CLAUDE_EFFORT:-}"
    session_id="${CLAUDE_CODE_SESSION_ID:-}"
    if [ -n "${CLAUDE_CODE_EXECPATH:-}" ]; then tool_version="$(basename "$CLAUDE_CODE_EXECPATH")"; fi
    # Read authoritative metadata straight from the transcript records (the real
    # CLI version, session id, entrypoint, models, span, turn counts, tokens).
    # The transcript is the source of truth; env vars are only the fallback.
    claude_parser="$script_dir/parse-claude-transcript.sh"
    if [ -f "$claude_parser" ]; then
      claude_meta="$(bash "$claude_parser" --shell "$SRC" 2>/dev/null || true)"
      if [ -n "$claude_meta" ]; then
        eval "$claude_meta"
        [ -n "${claude_version:-}" ] && tool_version="$claude_version"
        [ -n "${claude_session_id:-}" ] && session_id="$claude_session_id"
        [ -n "${claude_entrypoint:-}" ] && entrypoint="$claude_entrypoint"
        [ -n "${claude_cwd:-}" ] && session_cwd="$claude_cwd"
        # --model (a human label like "Claude Opus 4.8 (1M context)") wins; the
        # transcript's raw model id is only a fallback when none was passed.
        [ -z "$MODEL" ] && [ -n "${claude_model:-}" ] && MODEL="$claude_model"
      fi
    fi
    ;;
  codex)
    vendor="openai"; tool_name="codex-cli"
    # rollout-<timestamp>-<uuid>.jsonl -> trailing uuid
    session_id="$(printf '%s' "$src_base" | sed -E 's/\.jsonl$//; s/.*-([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$/\1/')"
    codex_parser="$script_dir/parse-codex-transcript.sh"
    if [ -f "$codex_parser" ]; then
      codex_meta="$(bash "$codex_parser" --shell "$SRC" 2>/dev/null || true)"
      if [ -n "$codex_meta" ]; then
        eval "$codex_meta"
        [ -n "${codex_model_provider:-}" ] && vendor="$codex_model_provider"
        [ -n "${codex_cli_version:-}" ] && tool_version="$codex_cli_version"
        [ -n "${codex_originator:-}" ] && entrypoint="$codex_originator"
        [ -n "${codex_session_id:-}" ] && session_id="$codex_session_id"
        [ -n "${codex_model:-}" ] && MODEL="$codex_model"
        [ -n "${codex_effort:-}" ] && effort="$codex_effort"
        [ -z "$effort" ] && [ -n "${codex_reasoning_effort:-}" ] && effort="$codex_reasoning_effort"
        [ -n "${codex_turn_cwd:-}" ] && session_cwd="$codex_turn_cwd"
        [ -z "$session_cwd" ] && [ -n "${codex_cwd:-}" ] && session_cwd="$codex_cwd"
      fi
    fi
    ;;
  cursor)
    vendor="anysphere"; tool_name="cursor-agent"
    session_id="${CURSOR_CONVERSATION_ID:-}"
    [ -n "$session_id" ] || session_id="$(printf '%s' "$src_base" | sed -E 's/\.[^.]*$//')"
    # IDE agent shells set CURSOR_AGENT=1; treat that as the entrypoint when the
    # transcript/composer store do not record one (CLI runs usually omit it).
    [ -n "${CURSOR_AGENT:-}" ] && entrypoint="ide"
    cursor_parser="$script_dir/parse-cursor-transcript.sh"
    if [ -f "$cursor_parser" ]; then
      cursor_meta="$(bash "$cursor_parser" --shell "$SRC" 2>/dev/null || true)"
      if [ -n "$cursor_meta" ]; then
        eval "$cursor_meta"
        [ -n "${cursor_tool_name:-}" ] && tool_name="$cursor_tool_name"
        [ -n "${cursor_tool_version:-}" ] && tool_version="$cursor_tool_version"
        [ -z "$tool_version" ] && [ -n "${cursor_version:-}" ] && tool_version="$cursor_version"
        [ -n "${cursor_entrypoint:-}" ] && entrypoint="$cursor_entrypoint"
        [ -n "${cursor_session_id:-}" ] && session_id="$cursor_session_id"
        [ -n "${cursor_conversation_id:-}" ] && [ -z "$session_id" ] && session_id="$cursor_conversation_id"
        # Prefer an explicit --model human label (e.g. "Grok 4.5"); the
        # composer/transcript model id still lands in session.models.
        [ -z "$MODEL" ] && [ -n "${cursor_model:-}" ] && MODEL="$cursor_model"
        [ -n "${cursor_effort:-}" ] && effort="$cursor_effort"
        [ -n "${cursor_cwd:-}" ] && session_cwd="$cursor_cwd"
      fi
    fi
    ;;
  antigravity)
    vendor="google"; tool_name="antigravity"
    # brain/<conversation-id>/.system_generated/logs/transcript*.jsonl
    session_id="$(basename "$(dirname "$(dirname "$(dirname "$SRC")")")")"
    ;;
  gemini)
    vendor="google"; tool_name="gemini-cli"
    session_id="$(printf '%s' "$src_base" | sed -E 's/\.[^.]*$//')"
    ;;
esac

# Source file facts (computed by the script — the agent never reads contents).
case "$src_base" in
  *.*) ext="${src_base##*.}" ;;
  *) ext="" ;;
esac
src_bytes="$(wc -c <"$SRC" 2>/dev/null | tr -d ' ')"
src_mtime_epoch="$(file_mtime_epoch "$SRC")"
src_mtime_iso=""
[ -n "$src_mtime_epoch" ] && src_mtime_iso="$(fmt_epoch "$src_mtime_epoch" '%Y-%m-%dT%H:%M:%SZ')"

# ---------------------------------------------------------------------------
# --detect: print findings and stop (no writes).
# ---------------------------------------------------------------------------
if [ -n "$DETECT_ONLY" ]; then
  printf 'os:            %s (%s, %s)\n' "$platform" "$kernel" "$arch"
  printf 'agent:         %s  [%s]\n' "$tool_name" "$DETECTED_VIA"
  [ -n "$tool_version" ] && printf 'agent version: %s\n' "$tool_version"
  [ -n "$entrypoint" ] && printf 'entrypoint:    %s\n' "$entrypoint"
  [ -n "$MODEL" ] && printf 'model:         %s\n' "$MODEL"
  [ -n "$effort" ] && printf 'effort:        %s\n' "$effort"
  [ -n "$session_id" ] && printf 'session id:    %s\n' "$session_id"
  [ -n "$session_cwd" ] && printf 'session cwd:   %s\n' "$session_cwd"
  detect_models="${claude_models:-${codex_models:-${cursor_models:-}}}"
  detect_records="${claude_records:-${codex_records:-${cursor_records:-}}}"
  detect_user_records="${claude_user_records:-${codex_user_records:-${cursor_user_records:-?}}}"
  detect_assistant_records="${claude_assistant_records:-${codex_assistant_records:-${cursor_assistant_records:-?}}}"
  detect_user_turns="${claude_user_turns:-${codex_user_turns:-${cursor_user_turns:-}}}"
  detect_assistant_turns="${claude_assistant_turns:-${codex_assistant_turns:-${cursor_assistant_turns:-?}}}"
  detect_started="${claude_started_at:-${codex_started_at:-${cursor_started_at:-}}}"
  detect_ended="${claude_ended_at:-${codex_ended_at:-${cursor_ended_at:-?}}}"
  [ -n "$detect_models" ] && printf 'models:        %s\n' "$detect_models"
  [ -n "$detect_records" ] && printf 'records:       %s total (%s user / %s assistant)\n' "$detect_records" "$detect_user_records" "$detect_assistant_records"
  [ -n "$detect_user_turns" ] && printf 'turns:         %s input / %s agent\n' "$detect_user_turns" "$detect_assistant_turns"
  [ -n "$detect_started" ] && printf 'span:          %s .. %s\n' "$detect_started" "$detect_ended"
  printf 'source:        %s\n' "$SRC"
  printf 'format/ext:    %s\n' "${ext:-<none>}"
  printf 'size:          %s bytes\n' "${src_bytes:-?}"
  if command -v python3 >/dev/null 2>&1; then
    detect_extractor=""
    case "$TOOL" in
      claude) detect_extractor="$script_dir/extract-claude-assets.py" ;;
      codex) detect_extractor="$script_dir/extract-codex-assets.py" ;;
      cursor) detect_extractor="$script_dir/extract-cursor-assets.py" ;;
    esac
    if [ -n "$detect_extractor" ] && [ -f "$detect_extractor" ]; then
      detect_inv="$(python3 "$detect_extractor" --emit inventory "$SRC" 2>/dev/null | head -1 || true)"
      [ -n "$detect_inv" ] && printf '%s\n' "$detect_inv"
    fi
  fi
  printf '\nReady. Re-run with a short-name to export, e.g.:\n'
  printf '  bash %s --tool %s --title "..." --summary "..." --model "..." <short-name>\n' "${BASH_SOURCE[0]}" "$TOOL"
  exit 0
fi

# ---------------------------------------------------------------------------
# Export: validate the short-name, compute paths, copy, write metadata.
# ---------------------------------------------------------------------------
[ -n "$SHORT_NAME_RAW" ] || die "a <short-name> is required to export (or pass --detect to preview). Try --help."

SHORT_NAME="$(printf '%s' "$SHORT_NAME_RAW" \
  | tr '[:upper:]' '[:lower:]' \
  | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' \
  | cut -c1-60 | sed -E 's/-+$//')"
[ -n "$SHORT_NAME" ] || die "short-name '$SHORT_NAME_RAW' has no usable [a-z0-9-] characters."

# One UTC instant drives both the folder and the filename prefix.
now_epoch="$(date -u +%s)"
now_iso="$(fmt_epoch "$now_epoch" '%Y-%m-%dT%H:%M:%SZ')"
ts="$(fmt_epoch "$now_epoch" '%Y%m%dT%H%M%SZ')"
date_dir="$(fmt_epoch "$now_epoch" '%Y%m%d')"

# Local-time + timezone context for the same instant (so a UTC stamp can be read
# back as a wall-clock time). Offset %z is normalized from -0400 to -04:00.
tz_offset="$(fmt_epoch_local "$now_epoch" '%z')"
case "$tz_offset" in
  [+-][0-9][0-9][0-9][0-9]) tz_offset="${tz_offset:0:3}:${tz_offset:3:2}" ;;
esac
tz_abbr="$(fmt_epoch_local "$now_epoch" '%Z')"
tz_name="$(local_tz_name)"
now_local="$(fmt_epoch_local "$now_epoch" '%Y-%m-%dT%H:%M:%S')"
[ -n "$now_local" ] && now_local="$now_local$tz_offset"

dest_dir="$OUT_ROOT/$date_dir"
mkdir -p "$dest_dir" || die "could not create destination dir: $dest_dir"

out_base="$ts-$SHORT_NAME${ext:+.$ext}"
meta_base="$ts-$SHORT_NAME-metadata.json"
out_path="$dest_dir/$out_base"
meta_path="$dest_dir/$meta_base"

cp "$SRC" "$out_path" || die "copy failed: $SRC -> $out_path"

# Stats over the copied bytes.
src_lines="$(wc -l <"$out_path" 2>/dev/null | tr -d ' ')"
src_sha="$(sha256_of "$out_path")"
fmt="$ext"
[ "$ext" = "vscdb" ] && fmt="sqlite"

# Repo / author context (best-effort; from the directory the agent ran in).
repo_root=""; repo_vcs=""; repo_ref=""; repo_commit=""; repo_rev=""; repo_remote=""
author_name=""; author_email=""
repo_probe_dir="$PWD"
if ! (cd "$repo_probe_dir" && { git rev-parse --show-toplevel >/dev/null 2>&1 || { command -v jj >/dev/null 2>&1 && jj root >/dev/null 2>&1; }; }); then
  if [ -n "$session_cwd" ] && [ -d "$session_cwd" ]; then repo_probe_dir="$session_cwd"; fi
fi
if (cd "$repo_probe_dir" && git rev-parse --show-toplevel >/dev/null 2>&1); then
  repo_root="$(cd "$repo_probe_dir" && git rev-parse --show-toplevel 2>/dev/null)"
  repo_ref="$(cd "$repo_probe_dir" && git rev-parse --abbrev-ref HEAD 2>/dev/null)"
  repo_commit="$(cd "$repo_probe_dir" && git rev-parse HEAD 2>/dev/null)"
  repo_remote="$(cd "$repo_probe_dir" && git config --get remote.origin.url 2>/dev/null)"
fi
if command -v jj >/dev/null 2>&1 && (cd "$repo_probe_dir" && jj root >/dev/null 2>&1); then
  repo_vcs="jujutsu"
  [ -z "$repo_root" ] && repo_root="$(cd "$repo_probe_dir" && jj root 2>/dev/null)"
  # jj workspaces aren't always colocated git working trees, so fill the bits
  # git couldn't: the working-copy commit id and the nearest ancestor bookmark.
  [ -z "$repo_commit" ] && repo_commit="$(cd "$repo_probe_dir" && jj log -r @ -n1 --no-graph --no-pager -T 'commit_id' 2>/dev/null | tr -d '\n')"
  [ -z "$repo_ref" ] && repo_ref="$(cd "$repo_probe_dir" && jj log -r '::@ & bookmarks()' -n1 --no-graph --no-pager -T 'bookmarks' 2>/dev/null | tr -d '\n' | sed 's/  */ /g; s/^ //; s/ *$//')"
  # Jujutsu's stable change id (the lower-case k-z alphabet) — distinct from the
  # Git commit id above, and preserved across rewrites. Guard the output so only a
  # real change id (never a stray git hash or error text) reaches repo.rev.
  repo_rev="$(cd "$repo_probe_dir" && jj log -r @ -n1 --no-graph --no-pager -T 'change_id' 2>/dev/null | tr -d '[:space:]')"
  case "$repo_rev" in
    *[!k-z]* | '') repo_rev="" ;;
  esac
elif [ -n "$repo_root" ]; then
  repo_vcs="git"
fi
# Fall back to the branch the transcript itself recorded (parsed from the JSONL)
# when the live probe yields nothing useful — e.g. a detached HEAD reports as
# "HEAD", but the log kept the real branch name. Also recovers a ref when the
# original repo path no longer exists to probe (archived/cleaned-up worktrees).
if { [ -z "$repo_ref" ] || [ "$repo_ref" = "HEAD" ]; } \
  && [ -n "${claude_git_branch:-}" ] && [ "${claude_git_branch}" != "HEAD" ]; then
  repo_ref="$claude_git_branch"
fi
[ -z "$repo_commit" ] && [ -n "${codex_git_commit:-}" ] && repo_commit="$codex_git_commit"
[ -z "$repo_remote" ] && [ -n "${codex_git_remote:-}" ] && repo_remote="$codex_git_remote"
if [ -z "$repo_vcs" ] && { [ -n "$repo_commit" ] || [ -n "$repo_remote" ]; }; then
  repo_vcs="git"
fi
author_name="$(cd "$repo_probe_dir" && git config user.name 2>/dev/null)"
author_email="$(cd "$repo_probe_dir" && git config user.email 2>/dev/null)"
if [ -z "$author_name" ] && command -v jj >/dev/null 2>&1; then author_name="$(cd "$repo_probe_dir" && jj config get user.name 2>/dev/null)"; fi
if [ -z "$author_email" ] && command -v jj >/dev/null 2>&1; then author_email="$(cd "$repo_probe_dir" && jj config get user.email 2>/dev/null)"; fi

# Title precedence: an explicit --title, then a title the agent recorded in the
# transcript (Claude's user-set custom title, else its auto-generated one), then
# a slug-derived default.
[ -n "$TITLE" ] || TITLE="${claude_custom_title:-}"
[ -n "$TITLE" ] || TITLE="${claude_ai_title:-}"
[ -n "$TITLE" ] || TITLE="${cursor_title:-}"
[ -n "$TITLE" ] || TITLE="$(printf '%s' "$SHORT_NAME" | tr '-' ' ')"

# JSON helpers (no jq dependency).
json_escape() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  s="${s//$'\r'/\\r}"
  s="${s//$'\t'/\\t}"
  printf '%s' "$s"
}
jstr() { if [ -z "${1:-}" ]; then printf 'null'; else printf '"%s"' "$(json_escape "$1")"; fi; }
jnum() { if [ -z "${1:-}" ]; then printf 'null'; else printf '%s' "$1"; fi; }
# Render a comma-separated list as a JSON array of strings ([] when empty).
jarr() {
  local csv="${1:-}" out="" first=1 item IFS=','
  [ -n "$csv" ] || { printf '[]'; return; }
  for item in $csv; do
    [ -n "$item" ] || continue
    if [ "$first" = 1 ]; then first=0; else out="$out, "; fi
    out="$out$(jstr "$item")"
  done
  printf '[%s]' "$out"
}

# clip_text <text> <max-chars> — collapse whitespace to single spaces and trim to
# <max-chars> code points at a word boundary (a … is appended when trimmed). Uses
# python3 (already required) so multibyte text is measured by code point and never
# cut mid-glyph. Empty input yields empty output (rendered as JSON null upstream).
clip_text() {
  [ -n "${1:-}" ] || { printf ''; return; }
  python3 - "$1" "$2" <<'PYEOF'
import sys
text = " ".join(sys.argv[1].split())
limit = int(sys.argv[2])
if len(text) > limit:
    cut = text[: limit - 1].rstrip()
    space = cut.rfind(" ")
    if space >= int(limit * 0.6):
        cut = cut[:space].rstrip()
    text = cut + "…"
sys.stdout.write(text)
PYEOF
}

# refs_to_json <issue|change> — read one reference per line on stdin, formatted
# "<url> [optional title words...]", and print a JSON array of normalized objects.
# The URL is parsed for the structured fields the gem card shows: for issues the
# tracker + display key (GitHub, GitLab, Jira, Linear, Buganizer); for changes the
# host, number and owner/repo (GitHub, GitLab, Gerrit). Unrecognized URLs still
# record the url and title with null structure. Live status/state is intentionally
# NOT captured here — it is enriched by the downstream processing job.
refs_to_json() {
  python3 - "$1" "${2:-}" <<'PYEOF'
import sys, json, re

kind = sys.argv[1]
blob = sys.argv[2] if len(sys.argv) > 2 else ""


def clip(s, n=120):
    if s is None:
        return None
    s = " ".join(s.split())
    if not s:
        return None
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def looks_url(s):
    return bool(re.match(r"[a-z][a-z0-9+.-]*://", s, re.I)) or bool(re.match(r"b/\d+$", s))


def parse_change(url):
    m = re.match(r"https?://github\.com/([^/\s]+/[^/\s]+?)/pull/(\d+)", url, re.I)
    if m:
        return "github", int(m.group(2)), m.group(1)
    m = re.match(r"https?://[^/\s]+/(.+?)/-/merge_requests/(\d+)", url, re.I)
    if m:
        return "gitlab", int(m.group(2)), m.group(1)
    m = re.match(r"https?://[^/\s]+/c/(.+?)/\+/(\d+)", url, re.I)  # modern Gerrit
    if m:
        return "gerrit", int(m.group(2)), m.group(1)
    m = re.match(r"https?://[^/\s]+/(?:#/)?c/(\d+)", url, re.I)    # legacy Gerrit
    if m:
        return "gerrit", int(m.group(1)), None
    return None, None, None


def parse_issue(url):
    m = re.match(r"https?://github\.com/([^/\s]+/[^/\s]+?)/issues/(\d+)", url, re.I)
    if m:
        return "github", "#" + m.group(2)
    m = re.match(r"https?://[^/\s]+/.+?/-/issues/(\d+)", url, re.I)
    if m:
        return "gitlab", "#" + m.group(1)
    m = re.match(r"https?://[^/\s]+\.atlassian\.net/browse/([A-Za-z][A-Za-z0-9]+-\d+)", url, re.I)
    if m:
        return "jira", m.group(1).upper()
    m = re.match(r"https?://linear\.app/[^/\s]+/issue/([A-Za-z0-9]+-\d+)", url, re.I)
    if m:
        return "linear", m.group(1).upper()
    m = re.match(r"https?://(?:issuetracker\.google\.com|b\.corp\.google\.com|buganizer\.corp\.google\.com)/issues/(\d+)", url, re.I)
    if m:
        return "buganizer", "b/" + m.group(1)
    m = re.match(r"b/(\d+)$", url)
    if m:
        return "buganizer", "b/" + m.group(1)
    return None, None


out, seen = [], set()
for line in blob.splitlines():
    line = line.strip()
    if not line:
        continue
    parts = line.split(None, 1)
    first = parts[0]
    rest = parts[1] if len(parts) > 1 else None
    if looks_url(first):
        url, title = first, clip(rest)
    else:
        url, title = None, clip(line)
    if url is not None and url in seen:
        continue
    if url is not None:
        seen.add(url)
    if kind == "issue":
        tracker, key = parse_issue(url) if url else (None, None)
        out.append({"key": key, "title": title, "url": url, "tracker": tracker})
    else:
        host, number, repo = parse_change(url) if url else (None, None, None)
        out.append({"number": number, "title": title, "url": url, "host": host, "repo": repo})

sys.stdout.write(json.dumps(out, ensure_ascii=False, separators=(", ", ": ")))
PYEOF
}

# tags_to_json — read tags on stdin (one per line; each line may itself be a
# comma-separated list) and print a JSON array: trimmed, de-duplicated
# case-insensitively (first spelling wins), each clipped to 32 chars.
tags_to_json() {
  python3 - "${1:-}" <<'PYEOF'
import sys, json

blob = sys.argv[1] if len(sys.argv) > 1 else ""
seen, out = set(), []
for line in blob.splitlines():
    for raw in line.split(","):
        tag = " ".join(raw.split())
        if not tag:
            continue
        if len(tag) > 32:
            tag = tag[:32].rstrip()
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(tag)
sys.stdout.write(json.dumps(out, ensure_ascii=False, separators=(", ", ": ")))
PYEOF
}

# Session-level facts from the transcript parser (Claude Code, Codex, and Cursor;
# empty for agents without a parser). The record count falls back to the copied
# file's line count so it is always present.
sess_started="${claude_started_at:-${codex_started_at:-${cursor_started_at:-}}}"
sess_ended="${claude_ended_at:-${codex_ended_at:-${cursor_ended_at:-}}}"
sess_records="${claude_records:-${codex_records:-${cursor_records:-$src_lines}}}"
sess_user_turns="${claude_user_turns:-${codex_user_turns:-${cursor_user_turns:-}}}"
sess_assistant_turns="${claude_assistant_turns:-${codex_assistant_turns:-${cursor_assistant_turns:-}}}"
sess_user_records="${claude_user_records:-${codex_user_records:-${cursor_user_records:-}}}"
sess_assistant_records="${claude_assistant_records:-${codex_assistant_records:-${cursor_assistant_records:-}}}"
sess_models_csv="${claude_models:-${codex_models:-${cursor_models:-}}}"
sess_tok_in="${claude_input_tokens:-${codex_input_tokens:-${cursor_input_tokens:-}}}"
sess_tok_out="${claude_output_tokens:-${codex_output_tokens:-${cursor_output_tokens:-}}}"
sess_tok_cache_read="${claude_cache_read_tokens:-${codex_cache_read_tokens:-${cursor_cache_read_tokens:-}}}"
sess_tok_cache_creation="${claude_cache_creation_tokens:-${codex_cache_creation_tokens:-${cursor_cache_creation_tokens:-}}}"
sess_tok_total="${claude_total_tokens:-${codex_total_tokens:-${cursor_total_tokens:-}}}"
sess_title="${claude_custom_title:-}"; [ -n "$sess_title" ] || sess_title="${claude_ai_title:-}"
[ -n "$sess_title" ] || sess_title="${cursor_title:-}"
sess_agent_name="${claude_agent_name:-${cursor_agent_name:-}}"
sess_bridge_id="${claude_bridge_session_id:-${cursor_bridge_session_id:-}}"

# Keep the card-facing strings concise and single-line, and bound auto/fallback
# titles, by trimming to the schema's limits at a word boundary.
TITLE="$(clip_text "$TITLE" 70)"
[ -n "$SUMMARY" ] && SUMMARY="$(clip_text "$SUMMARY" 160)"

# Card content the agent supplied: tags, plus the issues/bugs and PR/MR/CL refs
# the session touched ([] when none were passed). A session may reference several.
tags_json="$(tags_to_json "$TAGS_RAW")"; [ -n "$tags_json" ] || tags_json="[]"
issues_json="$(refs_to_json issue "$ISSUE_SPECS")"; [ -n "$issues_json" ] || issues_json="[]"
changes_json="$(refs_to_json change "$CHANGE_SPECS")"; [ -n "$changes_json" ] || changes_json="[]"

cat >"$meta_path" <<EOF
{
  "schema_version": 3,
  "title": $(jstr "$TITLE"),
  "short_name": $(jstr "$SHORT_NAME"),
  "summary": $(jstr "$SUMMARY"),
  "tags": $tags_json,
  "issues": $issues_json,
  "changes": $changes_json,
  "exported_at_utc": $(jstr "$now_iso"),
  "exported_at_unix": $(jnum "$now_epoch"),
  "exported_at_local": $(jstr "$now_local"),
  "timezone": {
    "name": $(jstr "$tz_name"),
    "abbreviation": $(jstr "$tz_abbr"),
    "utc_offset": $(jstr "$tz_offset")
  },
  "agent": {
    "vendor": $(jstr "$vendor"),
    "tool": $(jstr "$tool_name"),
    "tool_version": $(jstr "$tool_version"),
    "model": $(jstr "$MODEL"),
    "effort": $(jstr "$effort"),
    "entrypoint": $(jstr "$entrypoint"),
    "session_id": $(jstr "$session_id"),
    "detected_via": $(jstr "$DETECTED_VIA")
  },
  "os": {
    "kernel": $(jstr "$kernel"),
    "platform": $(jstr "$platform"),
    "arch": $(jstr "$arch"),
    "hostname": $(jstr "$host")
  },
  "repo": {
    "root": $(jstr "$repo_root"),
    "vcs": $(jstr "$repo_vcs"),
    "ref": $(jstr "$repo_ref"),
    "commit": $(jstr "$repo_commit"),
    "rev": $(jstr "$repo_rev"),
    "remote": $(jstr "$repo_remote")
  },
  "author": {
    "name": $(jstr "$author_name"),
    "email": $(jstr "$author_email")
  },
  "source": {
    "path": $(jstr "$SRC"),
    "filename": $(jstr "$src_base"),
    "format": $(jstr "$fmt"),
    "extension": $(jstr "$ext"),
    "bytes": $(jnum "$src_bytes"),
    "lines": $(jnum "$src_lines"),
    "sha256": $(jstr "$src_sha"),
    "modified_utc": $(jstr "$src_mtime_iso")
  },
  "session": {
    "started_utc": $(jstr "$sess_started"),
    "ended_utc": $(jstr "$sess_ended"),
    "records": $(jnum "$sess_records"),
    "user_turns": $(jnum "$sess_user_turns"),
    "assistant_turns": $(jnum "$sess_assistant_turns"),
    "user_records": $(jnum "$sess_user_records"),
    "assistant_records": $(jnum "$sess_assistant_records"),
    "models": $(jarr "$sess_models_csv"),
    "tokens": {
      "input": $(jnum "$sess_tok_in"),
      "output": $(jnum "$sess_tok_out"),
      "cache_read": $(jnum "$sess_tok_cache_read"),
      "cache_creation": $(jnum "$sess_tok_cache_creation"),
      "total": $(jnum "$sess_tok_total")
    },
    "title": $(jstr "$sess_title"),
    "agent_name": $(jstr "$sess_agent_name"),
    "bridge_session_id": $(jstr "$sess_bridge_id")
  },
  "export": {
    "transcript_file": $(jstr "$out_base"),
    "metadata_file": $(jstr "$meta_base"),
    "dest_dir": $(jstr "$dest_dir")
  }
}
EOF

schema_path="$script_dir/metadata.schema.json"
validator_path="$script_dir/validate-metadata.py"
[ -f "$schema_path" ] || die "metadata schema not found: $schema_path"
[ -f "$validator_path" ] || die "metadata validator not found: $validator_path"
if command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
else
  die "python3 is required to validate metadata JSON against $schema_path"
fi
"$python_cmd" "$validator_path" "$schema_path" "$meta_path" || die "metadata JSON failed schema validation: $meta_path"

# ---------------------------------------------------------------------------
# Assets: extract any files/images attached in the session into a sibling
# "<prefix>-assets/" directory carrying its own _manifest.json. Decoupled from the
# metadata sidecar (the dir is discovered by the shared <prefix>); extraction runs
# against the copied snapshot so re-exports are reproducible. See ASSETS.md.
# ---------------------------------------------------------------------------
assets_base="$ts-$SHORT_NAME-assets"
assets_dir="$dest_dir/$assets_base"
assets_line=""
extractor=""
case "$TOOL" in
  claude) extractor="$script_dir/extract-claude-assets.py" ;;
  codex) extractor="$script_dir/extract-codex-assets.py" ;;
  cursor) extractor="$script_dir/extract-cursor-assets.py" ;;
esac
if [ -n "$extractor" ] && [ -f "$extractor" ]; then
  orig_file=""
  if [ -n "$ASSET_ORIGINALS" ]; then
    orig_file="$(mktemp 2>/dev/null || printf '%s' "${TMPDIR:-/tmp}/era-orig.$$")"
    # Drop the leading blank line add_line() leaves; keep paths verbatim.
    printf '%s' "$ASSET_ORIGINALS" | sed '/^$/d' >"$orig_file"
  fi
  # Non-fatal: the transcript + metadata (the critical outputs) are already
  # written, so a failed extraction must not abort the export — but let the
  # extractor's warnings reach stderr rather than swallowing them.
  assets_line="$("$python_cmd" "$extractor" --emit inventory --manifest \
    --out-dir "$assets_dir" --dir-name "$assets_base" \
    ${orig_file:+--originals-file "$orig_file"} "$out_path" || true)"
  [ -n "$orig_file" ] && rm -f "$orig_file"
fi

msg "exported $tool_name session ($DETECTED_VIA)"
printf '  transcript: %s  (%s bytes)\n' "$out_path" "${src_bytes:-?}"
printf '  metadata:   %s\n' "$meta_path"
if [ -d "$assets_dir" ]; then
  printf '  assets:     %s/\n' "$assets_dir"
  [ -n "$assets_line" ] && printf '%s\n' "$assets_line" | sed 's/^/    /'
fi
