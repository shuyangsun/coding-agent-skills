---
title: Export-Raw-Transcript Metadata v3 for Gem Share
date: 2026-06-27
repo: "coding-agent-skills (jj workspace `claude-export-metadata-v3`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Opus 4.8, 1M context, effort: max, CLI 2.1.195)"
summary: >-
  Extended the export-raw-transcript metadata sidecar to schema v3 — adding
  agent-supplied tags/issues/changes arrays, a Jujutsu change-id `rev` field, and
  concise length-bounded title/summary — so it can power Gem Share's gem-card,
  then migrated the seven archived v2 sidecars on the NAS to v3.
---

<!-- markdownlint-disable MD013 MD024 -->

# Export-Raw-Transcript Metadata v3 for Gem Share

> Note: absolute paths under the user's home directory are abbreviated to `~/`
> as a redaction; transcript content is otherwise faithful.

## User

The ~/developer/gem-share/  repository currently only contains the Angular 22 frontend prototype. Requirements were in ~/developer/gem-share/docs/prompts/00001-prd.md. I have not built the backend layer yet.

I will put transcripts exported by the /export-raw-transcript in the raw transcript storage backend. Exported transcripts are stored on a local folder synced with my Synology NAS. I may sync exported transcripts to the cloud in the future. Both local and cloud storage can be used as the raw transcript storage backend.

I will implement a job to process raw transcripts and their metadata to another format. Processed transcripts will be stored in the processed transcripts backend. This backend will serve the backend API called by the frontend.

No backend implementation exists yet.

I am not sure if the /export-raw-transcript can produce metadata files with sufficient information to power the overview `gem-card` component. ~/developer/gem-share/src/app/shared/gem-card.html has implementation details. I have identified a few gaps:

1. The same session transcript may reference multiple PRs, CLs, Issues, or Bugs.
2. The title and summary may be too long to display on the GUI. Make both more concise.
3. Some repositories may use Jujustu, with Git as backend. Add a `rev` field in the `repo` block when `jj` is present. This field is the lower-case letter change ID in Jujutsu.

Improve the metadata JSON file produced by the /export-raw-transcript skill. Make sure you understand the context first, keep the big picture in mind. For example, you do not need to handle features such as bookmarks and likes, they will be handled by the backend.

## Assistant

I started by reading the context across both repos before touching anything, to keep the big picture in view:

- **Frontend (gem-share):** `src/app/shared/gem-card.html` + `gem-card.ts` + `gem-card.scss`, the `docs/prompts/00001-prd.md` PRD, the domain model `src/app/core/models.ts`, and a real mock gem in `src/app/core/mock-data.ts`.
- **The skill (coding-agent-skills):** `.agents/skills/export-raw-transcript/` — `SKILL.md`, `metadata.schema.json`, `export-raw-transcript.sh` (the orchestrator that assembles the JSON), `parse-claude-transcript.sh`, and `validate-metadata.py`.

Mapping what the gem-card renders to where each field comes from:

- title, summary → metadata (exist, but **gap #2**: unbounded length)
- author, model/vendor, turns, duration, createdAt → metadata (already present)
- **issues[]** (key, title, url, tracker, status) and **changes[]** (number, title, url, host, repo, state) → **gap #1**: not in the metadata at all
- **tags[]** → rendered by the card, but not in the metadata (content-derived, like title/summary)
- likes / bookmarks / visibility / handle / live PR-state → backend or live-enrichment (out of scope per your note)

Key observations:

- The v2 schema has **no** `issues`/`changes`/`tags`; `repo` has `root/vcs/ref/commit/remote` but no `rev`; `title`/`summary` are unbounded.
- `validate-metadata.py` is a small custom validator that supports `$ref/const/enum/type/required/maxLength/pattern/minimum` — but it does **not** recurse into array `items`, so any new object-array shapes would go unchecked.
- `parse-claude-transcript.sh` is a bash wrapper around an embedded python3 program — the established pattern for "read the transcript in a subprocess without surfacing it to the model."

Plan: bump schema v2 → v3; add `tags`/`issues`/`changes` (agent-supplied, URL-parsed into the shapes the card consumes); add `repo.rev` (jj change id); bound `title`/`summary` with maxLength + in-script word-boundary truncation; and teach the validator to validate array items.

I also flagged the architectural separation I'd follow: the sidecar captures **identity** (which PR/issue/CL was touched), while live/mutable state (open/merged, additions/deletions, likes, bookmarks) is left to the downstream processing job / backend — consistent with your "bookmarks and likes are handled by the backend."

## User

By the way, only focus on Claude metadata for now. No need to modify GPT Codex metadata yet. You can find previously exported metadata JSON files under ~/nas/database/llm_transcripts.

## Assistant

Acknowledged — I scoped my changes to the shared orchestrator/schema/validator (no Codex parser changes) and read a real exported sidecar from the NAS to ground the design (`…/raw/20260627/…-export-raw-transcript-v2-metadata-metadata.json`). It confirmed both gaps on real data: a 78-char title and a ~370-char summary, and a `repo` block with `commit` = the git SHA but no jj change id.

I implemented the change across four files:

**`metadata.schema.json`** — `schema_version` const 2 → 3; `title` `maxLength: 70`, `summary` `maxLength: 160`; new top-level `tags`/`issues`/`changes` arrays with `$defs/issueRef` (`key/title/url/tracker`, tracker ∈ github/gitlab/jira/linear/buganizer) and `$defs/changeRef` (`number/title/url/host/repo`, host ∈ github/gitlab/gerrit); and `repo.rev` (`pattern: ^[k-z]+$` or null).

**`validate-metadata.py`** — added array-`items` recursion so the new element shapes are actually validated.

**`export-raw-transcript.sh`** —
- New repeatable flags `--issue`/`--change` (`"<url> [title]"`), `--tag`/`--tags`, accumulated as newline-delimited strings (bash-3.2-safe; no empty-array expansion under `set -u`).
- A python helper (`refs_to_json`) parses each URL into the structured shape: GitHub PR/issue, GitLab MR/issue (incl. nested groups), Gerrit CL, Jira, Linear, Buganizer (`b/…`). Unrecognized URLs keep `url`+`title` with null structure. Live status/state is intentionally **not** captured.
- `tags_to_json` trims + de-duplicates tags case-insensitively.
- `clip_text` collapses whitespace and trims `title`/`summary` to 70/160 code points at a word boundary (python, so multibyte text is never cut mid-glyph) — this also tames Claude's long auto/fallback titles.
- `repo.rev` from `jj log -r @ -T change_id`, guarded so only a real `[k-z]+` change id lands in the field.

**`SKILL.md`** — documented the flags, the conciseness guidance, `repo.rev`, and the new content blocks.

I ran a full end-to-end export to a temp dir with sample refs of every supported host plus an over-length title/summary. First pass: `tags`/`issues`/`changes` came out empty. The bug was that `python3 - <<'EOF'` reads the **program** from stdin, so a piped data feed is silently discarded and `sys.stdin.read()` returns nothing — `clip_text` had worked only because it passes data via `argv`. I switched the ref/tag helpers to take their data via `argv` too.

Re-run: every field populated correctly — nested GitLab groups, Gerrit CL numbers, Buganizer keys, case-insensitive tag dedup, `repo.rev` (a 32-letter k–z id) distinct from the git `commit`, and word-boundary-trimmed title/summary. I then ran six **negative** tests (bad tracker enum, negative change number, extra property in an item, non-`[k-z]` rev, over-length title, over-length tag) — all correctly rejected — plus a positive control. Confirmed the no-refs path still yields valid v3 with empty arrays.

Tool calls in this phase (summarized): `Read` the schema/validator/orchestrator/parser/SKILL.md; `Edit` all four files; `Bash` to syntax-check, run the exporter against `--out-root /tmp/...`, and run the validator over crafted-invalid mutations.

I renamed the working copy `claude-pending-… → claude-export-metadata-v3` via the vcs `rename-work.sh`, and updated the persisted memory for the skill (schema v3 + the argv-vs-stdin gotcha).

**Decisions I surfaced for you:** I added `tags[]` even though it wasn't in your three gaps (the card renders them and they're content-derived); I deliberately left live PR/issue **state** out of the sidecar (the backend enriches it); `author.handle` stays a backend concern. And I did not migrate the existing v2 sidecars — `schema_version` exists precisely so the processing job can read both — but offered to.

## User

Migrate the 7 existing v2 sidecars on the NAS.

## Assistant

I inspected all 7 first: 4 Claude + 3 Codex, all `schema_version: 2`. Four Claude files had over-length summaries (one also an over-length title) — the only lossy part; the 3 Codex files were within limits, so they'd migrate **schema-only** (no Codex logic touched).

For `repo.rev`, the historical jj change id isn't stored — but it's recoverable from the recorded `commit` SHA via the shared jj repo. I probed `jj -R <main-repo> log -r <commit> -T change_id` for each commit: all 6 jujutsu files resolved to valid k–z change ids; the 7th is a Git worktree → `null`.

I wrote a migration script (`/tmp/migrate_v2_to_v3.py`) that, per file: bumps to v3; trims title/summary at a word boundary only where over-limit; adds empty `tags`/`issues`/`changes` (historical refs aren't recoverable without re-reading transcripts); recovers `repo.rev`; reorders keys to the canonical v3 order; **validates against the v3 schema and backs up the original to `/tmp/v2bak/` before overwriting**, so a bad migration can never corrupt the archive.

Result: all 7 migrated and re-validated 7/7 as v3; 6 `rev`s recovered, 1 `null`; 4 summaries trimmed (1 title). The raw `.jsonl` transcripts were untouched, and the pre-trim originals survive in `/tmp/v2bak/`, so nothing is irreversibly lost.

Tool calls (summarized): `Bash` to inspect lengths/vcs and probe change-id recovery; `Write` the migration script; `Bash` to run it and re-validate all 7 in place; a before→after diff on the most-changed file.

## User

/export-transcript then integrate with /vcs. After that, /export-raw-transcript .

## Assistant

Wrapping up in three steps:

1. **`/export-transcript`** — wrote this markdown transcript to `docs/transcripts/2026-06-27/0080-claude-export-raw-metadata-v3.md` (index from `next-index.sh`), then ran the redaction scan and abbreviated home-directory paths.
2. **`/vcs`** — committed the four skill changes plus this transcript and integrated the `claude-export-metadata-v3` workspace into `main`.
3. **`/export-raw-transcript`** — backed up this session's raw `.jsonl` plus a fresh **v3** metadata sidecar (dogfooding the new `tags`/`rev` fields) into the NAS raw-transcript store.
