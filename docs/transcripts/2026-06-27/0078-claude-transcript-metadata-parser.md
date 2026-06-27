---
title: Claude Transcript Metadata Parser
date: 2026-06-27
repo: "coding-agent-skills (jj workspace `claude-parse-claude-transcript`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Opus 4.8, 1M context, CLI 2.1.195, effort: max)"
summary: >-
  Built parse-claude-transcript.sh to extract all metadata from Claude Code
  JSONL transcripts, wired it into export-raw-transcript.sh behind a new session
  schema block, then established which sidecar fields come from the transcript
  versus the live environment.
---

<!-- markdownlint-disable MD013 MD024 -->

# Claude Transcript Metadata Parser

## User

Improve Claude metadata parsing in the @.agents/skills/export-raw-transcript/ skill. Currently, there is a an @.agents/skills/export-raw-transcript/parse-codex-transcript.sh that parses `.jsonl`  files from GPT Codex to extract metadata into a JSON file in the @.agents/skills/export-raw-transcript/metadata.schema.json format. I would like to do the same for Claude transcripts with a `parse-claude-transcript.sh` script. Make sure all metadata can be found in the `.jsonl` file are extracted. You can either use this chat session transcript as an example, or refer to ~/nas/database/llm_transcripts/20260626/20260626T231123Z-gem-share-frontend-metadata.json and ~/nas/database/llm_transcripts/20260626/20260626T231123Z-gem-share-frontend.jsonl. Note that `20260626T231123Z-gem-share-frontend.jsonl` is very large (9MB), don't try to read it yourself.

## Assistant

Read the existing skill (`export-raw-transcript.sh`, `parse-codex-transcript.sh`, `metadata.schema.json`, `validate-metadata.py`, `SKILL.md`) and the reference `…-gem-share-frontend-metadata.json` sidecar to learn the target shape.

Inspected the Claude JSONL structure on small and mid-size real transcripts (using `jq` only for my own inspection — the parser itself must stay dependency-light). Key findings:

- **Record types**: `user`, `assistant`, `system`, `attachment`, `mode`, `permission-mode`, `last-prompt`, `file-history-snapshot`, `bridge-session`, `ai-title`, `custom-title`, `agent-name`, `queue-operation`.
- **Key order is unstable** — control records start with `{"type":…}` but message records start with `{"parentUuid":…}` and bury `type` deep in the line, so substring/regex matching mis-detects record types. `message.model` is serialized after `message.content`, so a first-match regex is unsafe too.
- Rich fields available: the real CLI `version` (e.g. `2.1.195`), `gitBranch`, `cwd`, `entrypoint`, `userType`, `permissionMode`, `ai-title`/`custom-title`, the `bridge-session` id, plus per-assistant `message.model` and `usage` token counts.

Decision: because `export-raw-transcript.sh` already hard-requires `python3` for schema validation, the Claude parser uses `python3` as its JSON engine (streaming `json.loads` per line) — robust against the unstable key order and large lines, no new dependency, and it never loads the file into memory or surfaces it to the model.

Wrote **`parse-claude-transcript.sh`** (python3-backed, emitting `claude_*` shell assignments exactly like the Codex parser): session scalars, record/turn counts by type, distinct assistant models (excluding the `<synthetic>` placeholder), first/last record timestamp, and summed token usage.

Verified against the 9MB gem-share transcript using its sidecar as ground truth — an **exact match**: records 945, user_turns 230, assistant_turns 472, model `claude-opus-4-8`, and both start/end timestamps, in 0.27s. Cross-checked a mid-size transcript field-by-field against `jq`.

Extended **`metadata.schema.json`** with an optional `session` block (`started_utc`, `ended_utc`, `records`, `user_turns`, `assistant_turns`, `models[]`, `tokens{}`, `title`, `agent_name`, `bridge_session_id`) plus `nullableUtcDateTimeMs` and `nullableNonNegInt` defs.

Wired the parser into **`export-raw-transcript.sh`** (the `claude` case): transcript-sourced `version`/`session_id`/`entrypoint`/`cwd`/`model` (authoritative, env vars as fallback), a session preview in `--detect`, title precedence (explicit `--title` → transcript custom/ai title → slug), a `jarr` JSON-array helper, and the `session` block in the metadata heredoc (records falls back to the file line count for non-Claude agents).

Updated **`SKILL.md`** to document the Claude parser and the session block.

Tested end to end: live export validated; the Codex path still works and the session block degrades gracefully; negative schema tests reject bad values; the parser is robust over empty/blank/malformed inputs and 60 real transcripts (0 issues); multi-model sessions list every model and pick the most-frequent one as primary.

## User

There are a few fields that are `null` in ~/nas/database/llm_transcripts/20260626/20260626T231123Z-gem-share-frontend-metadata.json, can you modify the script and the skill to get them from the `.jsonl` file?

## Assistant

Investigated each null field (`agent.effort`, `agent.entrypoint`, `os.arch`, `os.hostname`, `repo.commit`, `repo.remote`) against the actual transcript by enumerating every top-level and `message` key across the whole 9MB file.

The honest result — only **one** of the six is in the `.jsonl`:

- `agent.entrypoint` — **yes** (`entrypoint` key), and the new parser already extracts it (→ `sdk-cli`). It was null only because that sidecar was a hand-built reconstruction predating the parser.
- `agent.effort`, `os.arch`, `os.hostname`, `repo.commit`, `repo.remote` — **not present**. The apparent matches were all conversational content or unrelated fields (`attributionSkill: "commit"`, `usage.service_tier`/`speed`, `origin: {"kind":"human"}`). These are live machine/repo facts the script already fills from `$CLAUDE_EFFORT`, `uname`, and `git`/`jj` during a normal live export; they show up null only when a sidecar is reconstructed from a transcript alone.

Made the one genuine `.jsonl`-sourced repo improvement: **`repo.ref` now backstops from the transcript's `gitBranch`** when the live VCS probe is uninformative (a detached `HEAD`, or an archived repo path that no longer exists to probe). Verified the fallback: `main`→`main`, `HEAD`→branch, empty→branch.

Updated **`SKILL.md`** to spell out which sidecar fields come from the transcript versus the live environment, so the null-on-reconstruction behavior is expected rather than surprising. Recorded the finding in memory. Offered (pending the user's call) a `--source <path>` flag to re-export arbitrary/archived transcripts, plus surfacing other unused signals (`service_tier`, `speed`, `origin.kind`, `attributionSkill`).

## User

/export-transcript — then integrate with /vcs. After that, export raw transcript with the skill you just modified.

## Assistant

Exported this session as the markdown transcript you're reading (`export-transcript`: `next-index.sh` → `0078`, reconstructed faithfully from context with verbatim user turns, then ran `redaction-scan.sh` and genericized local home paths to `~/`).

Integrated the work with the `vcs` skill: committed the feature (`parse-claude-transcript.sh` + the exporter, schema, and `SKILL.md` changes) and this transcript, then brought the `claude-parse-claude-transcript` workspace into the `main` line.

Finally, backed up the raw session with the just-modified `export-raw-transcript` skill into `~/Downloads/transcripts/` — the verbatim `.jsonl` plus a validated metadata sidecar that now includes the Claude `session` block.
