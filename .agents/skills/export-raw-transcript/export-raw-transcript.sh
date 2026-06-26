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
# It NEVER reads transcript *contents* into the agent — it only copies bytes and
# stats the file (size / line count / sha256). Transcripts can be huge, so the
# agent must not cat/open them; this script does everything mechanical.
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
#   --title <str>     Human-readable session title for the metadata.
#   --summary <str>   One-line summary of the session for the metadata.
#   --model <str>     Exact model + variant the agent ran, e.g.
#                     "Claude Opus 4.8 (1M context)". The running agent knows
#                     this even though the environment usually doesn't.
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
  # cursor-agent CLI per-session JSONL transcripts are the true raw transcript.
  # (The Cursor IDE keeps chat in a live SQLite state.vscdb, not a single-file
  # per-session transcript — handled with a clear message at the call site.)
  newest_from_find "$HOME/.cursor/projects" -path '*/agent-transcripts/*' -name '*.jsonl'
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
    die "no cursor-agent CLI transcript found under ~/.cursor/projects/*/agent-transcripts/.
The Cursor IDE stores chat in a live SQLite DB instead
(~/Library/Application Support/Cursor/User/globalStorage/state.vscdb on macOS,
~/.config/Cursor/User/globalStorage/state.vscdb on Linux), which is not a
single-file per-session transcript this skill can copy faithfully. Use the
cursor-agent CLI to produce a JSONL transcript, or export markdown instead."
  fi
  die "could not locate a current transcript for '$TOOL'. Pass --tool / --out-root, or check the agent is the one running this."
fi

vendor=""; tool_name=""; tool_version=""; effort=""; entrypoint=""; session_id=""
src_base="$(basename "$SRC")"
case "$TOOL" in
  claude)
    vendor="anthropic"; tool_name="claude-code"
    entrypoint="${CLAUDE_CODE_ENTRYPOINT:-}"
    effort="${CLAUDE_EFFORT:-}"
    session_id="${CLAUDE_CODE_SESSION_ID:-}"
    if [ -n "${CLAUDE_CODE_EXECPATH:-}" ]; then tool_version="$(basename "$CLAUDE_CODE_EXECPATH")"; fi
    ;;
  codex)
    vendor="openai"; tool_name="codex-cli"
    # rollout-<timestamp>-<uuid>.jsonl -> trailing uuid
    session_id="$(printf '%s' "$src_base" | sed -E 's/\.jsonl$//; s/.*-([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$/\1/')"
    ;;
  cursor)
    vendor="anysphere"; tool_name="cursor-agent"
    session_id="$(printf '%s' "$src_base" | sed -E 's/\.[^.]*$//')"
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
  [ -n "$session_id" ] && printf 'session id:    %s\n' "$session_id"
  printf 'source:        %s\n' "$SRC"
  printf 'format/ext:    %s\n' "${ext:-<none>}"
  printf 'size:          %s bytes\n' "${src_bytes:-?}"
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
repo_root=""; repo_vcs=""; repo_ref=""; repo_commit=""; repo_remote=""
author_name=""; author_email=""
if git rev-parse --show-toplevel >/dev/null 2>&1; then
  repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"
  repo_ref="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
  repo_commit="$(git rev-parse HEAD 2>/dev/null)"
  repo_remote="$(git config --get remote.origin.url 2>/dev/null)"
fi
if command -v jj >/dev/null 2>&1 && jj root >/dev/null 2>&1; then
  repo_vcs="jujutsu"
  [ -z "$repo_root" ] && repo_root="$(jj root 2>/dev/null)"
  # jj workspaces aren't always colocated git working trees, so fill the bits
  # git couldn't: the working-copy commit id and the nearest ancestor bookmark.
  [ -z "$repo_commit" ] && repo_commit="$(jj log -r @ -n1 --no-graph --no-pager -T 'commit_id' 2>/dev/null | tr -d '\n')"
  [ -z "$repo_ref" ] && repo_ref="$(jj log -r '::@ & bookmarks()' -n1 --no-graph --no-pager -T 'bookmarks' 2>/dev/null | tr -d '\n' | sed 's/  */ /g; s/^ //; s/ *$//')"
elif [ -n "$repo_root" ]; then
  repo_vcs="git"
fi
author_name="$(git config user.name 2>/dev/null)"
author_email="$(git config user.email 2>/dev/null)"
if [ -z "$author_name" ] && command -v jj >/dev/null 2>&1; then author_name="$(jj config get user.name 2>/dev/null)"; fi
if [ -z "$author_email" ] && command -v jj >/dev/null 2>&1; then author_email="$(jj config get user.email 2>/dev/null)"; fi

# Default a human title from the slug when the agent didn't pass one.
[ -n "$TITLE" ] || TITLE="$(printf '%s' "$SHORT_NAME" | tr '-' ' ')"

# JSON helpers (no jq/python dependency).
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

cat >"$meta_path" <<EOF
{
  "schema_version": 1,
  "title": $(jstr "$TITLE"),
  "short_name": $(jstr "$SHORT_NAME"),
  "summary": $(jstr "$SUMMARY"),
  "exported_at_utc": $(jstr "$now_iso"),
  "exported_at_unix": $(jnum "$now_epoch"),
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
  "export": {
    "transcript_file": $(jstr "$out_base"),
    "metadata_file": $(jstr "$meta_base"),
    "dest_dir": $(jstr "$dest_dir")
  }
}
EOF

msg "exported $tool_name session ($DETECTED_VIA)"
printf '  transcript: %s  (%s bytes)\n' "$out_path" "${src_bytes:-?}"
printf '  metadata:   %s\n' "$meta_path"
