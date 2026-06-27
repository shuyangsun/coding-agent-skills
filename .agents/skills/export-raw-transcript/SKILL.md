---
name: export-raw-transcript
description: >-
  Back up the CURRENT coding-agent session's RAW transcript file (Claude Code,
  Codex, Cursor, Antigravity, Gemini CLI) verbatim into
  ~/Downloads/transcripts/<YYYYMMDD>/, alongside a rich JSON metadata sidecar. A
  bundled bash script auto-detects the OS and the active agent, locates the
  session's own log, and copies the unread .jsonl (or other format) byte-for-byte
  — the large transcript is NEVER read into the model. Run only when the user
  explicitly asks to back up or export the raw session; never proactively.
  Distinct from `export-transcript`, which writes curated, redacted markdown into
  docs/transcripts/.
---

# Export raw transcript

Copy the running agent session's **raw transcript file** — exactly as the agent
wrote it on disk — into `~/Downloads/transcripts/<YYYYMMDD>/`, plus a
`*-metadata.json` sidecar describing the session. Agent-neutral: the same skill
directory serves every agent, whether used from `.agents/skills/` or symlinked
into another runtime path (`.claude/skills/`, etc.).

The export is two files that share one prefix:

```text
~/Downloads/transcripts/<YYYYMMDD>/<utc-ts>-<short-name>.<ext>            # raw copy
~/Downloads/transcripts/<YYYYMMDD>/<utc-ts>-<short-name>-metadata.json    # sidecar
```

`<utc-ts>` is a UTC stamp like `20260626T234513Z`; the `<YYYYMMDD>` folder is the
same instant in UTC, so a file always matches its folder. `<ext>` is whatever the
source uses (usually `.jsonl`). The script creates the dated folder if missing.

## Do NOT read the transcript into model context

Raw transcripts are large. **Never `cat`, `Read`, open, or otherwise pull the
transcript file into your context.** The bundled script does the mechanical work
(detect, locate, copy, checksum, write metadata). For Codex transcripts only, it
also delegates to `parse-codex-transcript.sh`, which reads the small metadata
records (`session_meta` and the first `turn_context`) directly in bash so the
model, effort, CLI version, session id, entrypoint, and cwd come from the raw
log without being shown to the agent.

Your only job is to hand it a few short descriptive strings you already know
from the live conversation — a name, a title, and a one-line summary. A
`--model` value is still accepted as a fallback for agents that do not expose it
in their transcript.

## Not the same as `export-transcript`

|                         | `export-raw-transcript` (this skill)                         | `export-transcript`                         |
| ----------------------- | ------------------------------------------------------------ | ------------------------------------------- |
| Output                  | The raw on-disk file, verbatim, + JSON metadata              | Curated `## User` / `## Assistant` markdown |
| Destination             | `~/Downloads/transcripts/` (local backup, **not** committed) | `docs/transcripts/` (committed to the repo) |
| Redaction               | **None** — it is the unredacted, verbatim log                | Secrets/PII redacted before commit          |
| The model reads the log | No                                                           | Yes (to render it)                          |

Because this skill keeps the log **unredacted**, the output may contain secrets,
tokens, absolute paths, or PII. It lands in `~/Downloads` (outside the repo) on
purpose. Do not commit these files or share them without scrubbing first — for a
shareable, redacted, readable version use `export-transcript` instead.

## Locating the bundled script

`export-raw-transcript.sh` lives next to this `SKILL.md`, with
`parse-codex-transcript.sh` beside it. Run the exporter from **this skill's own
directory** — the path the runtime gave you when it loaded the skill (e.g.
`.agents/skills/export-raw-transcript/`, `.claude/skills/export-raw-transcript/`,
or wherever the skill directory was symlinked). Below this is written as
`<skill-dir>/`; substitute the actual path. The script detects the OS, detects
the active agent, resolves the working repo, and creates output directories on
its own, so it works from any agent and any working directory.

## Steps

1. **Preview (detect).** Run:

   ```sh
   bash <skill-dir>/export-raw-transcript.sh --detect
   ```

   It prints the detected OS, agent, current session file, and its size — without
   writing anything. Confirm it found the right agent and a plausible file. If it
   picked the wrong agent (e.g. several tools are installed), force it with
   `--tool claude|codex|cursor|antigravity|gemini`.

2. **Name the session.** Choose a concise kebab-case `short-name` describing the
   topic (the script lowercases and sanitizes it anyway). Also prepare, from what
   you already know — **never by reading the transcript into context** — a human
   `--title` and a one-line `--summary`. For Codex, the exporter reads `model`
   and `effort` from `turn_context`; for other agents, pass your exact `--model`
   string when known (e.g. `"Claude Opus 4.8 (1M context)"`).

3. **Export.** Run:

   ```sh
   bash <skill-dir>/export-raw-transcript.sh \
     --title "Short human title" \
     --summary "One sentence on what this session did." \
     --model "Claude Opus 4.8 (1M context)" \
     <short-name>
   ```

   The script copies the raw file and writes the metadata JSON, then prints both
   destination paths. For Codex, transcript-parsed `model` and `effort` take
   precedence over `--model`; `--model` is only a fallback if the parser cannot
   find those fields. Add `--tool <slug>` if step 1 needed it, or `--out-root
   <dir>` to target a different root.

4. **Report.** Relay the two output paths (transcript + metadata) the script
   printed. That's the whole task — do not open either file.

## How detection works (per agent)

The script identifies the active agent from the environment variable it injects,
then falls back to the most-recently-written transcript across all known stores
(reliable because the live session is the file being appended to right now). You
can always override with `--tool`.

| Agent (`--tool`)            | Current-session signal                         | Raw transcript location                                                             |
| --------------------------- | ---------------------------------------------- | ----------------------------------------------------------------------------------- |
| Claude Code (`claude`)      | `$CLAUDE_CODE_SESSION_ID` → exact `<id>.jsonl` | `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`                               |
| Codex CLI (`codex`)         | newest mtime (no session env var)              | `${CODEX_HOME:-~/.codex}/sessions/YYYY/MM/DD/rollout-*.jsonl`; metadata is parsed from `session_meta` and first `turn_context` |
| Gemini CLI (`gemini`)       | `$GEMINI_CLI=1` marker, then newest mtime      | `${GEMINI_CLI_HOME:-~}/.gemini/tmp/<hash>/chats/*.json[l]`                          |
| Antigravity (`antigravity`) | newest mtime (no session env var)              | `~/.gemini/antigravity{-cli,}/brain/*/.system_generated/logs/transcript_full.jsonl` |
| Cursor agent CLI (`cursor`) | `$CURSOR_AGENT`, then newest mtime             | `~/.cursor/projects/*/agent-transcripts/**/*.jsonl`                                 |

**Claude Code is the primary, fully-verified path.** The others are derived from
each tool's published storage layout; tools change paths between versions, so use
`--detect` to confirm and `--tool` to correct. **Cursor caveat:** only the
`cursor-agent` CLI writes a single-file JSONL transcript. The Cursor IDE keeps
chat in a live SQLite DB (`…/User/globalStorage/state.vscdb`), which is not a
faithful single-file per-session transcript — the script reports this and stops
rather than copying a partial/torn DB.

## What the metadata sidecar captures

The `*-metadata.json` is the YAML-header idea from `export-transcript`, but richer
and machine-readable. The script fills everything automatically except `title`,
`summary`, and `model`, which you pass in. Top-level keys:

- `title`, `short_name`, `summary`, `schema_version`
- `exported_at_utc` / `exported_at_unix` / `exported_at_local`
- `timezone`: `name` (IANA, e.g. `America/New_York`), `abbreviation` (e.g.
  `EDT`), `utc_offset` (e.g. `-04:00`) — lets a UTC stamp be read back as local
  wall-clock time
- `agent`: `vendor`, `tool`, `tool_version`, `model`, `effort`, `entrypoint`,
  `session_id`, `detected_via`
- `os`: `kernel`, `platform`, `arch`, `hostname`
- `repo`: `root`, `vcs`, `ref`, `commit`, `remote` (from Git, with a Jujutsu
  fallback)
- `author`: `name`, `email` (from the repo's VCS config)
- `source`: `path`, `filename`, `format`, `extension`, `bytes`, `lines`,
  `sha256`, `modified_utc` (the checksum lets you verify the copy later)
- `export`: `transcript_file`, `metadata_file`, `dest_dir`

For Codex transcripts, the parser can currently extract these additional raw
metadata signals for more accurate sidecars: `session_id`, `cli_version`,
`originator`, `source`, `thread_source`, `model_provider`, launch `cwd`,
`turn_id`, first `workspace_root`, `current_date`, `timezone`, `approval_policy`,
`sandbox_policy.type`, `permission_profile.type`, `model`, `comp_hash`,
`personality`, `collaboration_mode.mode`, `reasoning_effort`,
`multi_agent_version`, `realtime_active`, `effort`, and transcript `summary`.
The exporter uses the subset that maps to the current schema.

## When to run this skill

Opt-in only: back up the raw session when the user explicitly asks. Never
proactively.

## Notes

- The copy is a snapshot taken at export time; the agent appends to its log as it
  runs, so the exported size may exceed what `--detect` showed a moment earlier.
- Detection prefers the agent's own env marker; with several agents installed and
  no marker (Codex, Antigravity), it uses newest-mtime — pass `--tool` if that
  guesses wrong.
- The scripts are portable across macOS (BSD) and Linux (GNU) and need no `jq` or
  `python`; they shell out only to standard tools (`uname`, `stat`, `date`, `cp`,
  `find`, `sed`, `shasum`/`sha256sum`).
