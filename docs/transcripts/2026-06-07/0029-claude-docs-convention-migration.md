---
title: "Migrate `docs/` to the dated convention + kick-start the docs skill"
date: 2026-06-07
repo: "coding-agent-skills (bookmark `claude-docs-convention-migration`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Opus 4.8, 1M context, thinking: high)"
summary: >-
  Located the reference `writing-docs` skill in the sibling `website` repo, then
  reorganized every non-session `docs/` folder (`benchmarks`, `issues`, `plans`,
  `prompts`) into the `coding-sessions` layout — dated `YYYY-MM-DD/` subdirs with clean
  `NNNN-slug.md` filenames — as history-preserving renames, rewrote all cross-links, and
  authored six `OVERVIEW.md` files to kick-start the docs skill.
---

<!-- markdownlint-disable MD013 MD024 -->

# Migrate `docs/` to the dated convention + kick-start the docs skill

## User

Use the reference docs skill file to kick start the /docs skill, start populating docs for the repository. Reorganize other folders under @docs/ to have the same folder and file name structure as the coding-sessions directory.

## Assistant

Explored the repo to find the docs skill and understand the current layout.

- **Bash** — listed `docs/` (`benchmarks`, `coding-sessions`, `issues`, `plans`, `prompts`) and searched for a `docs` SKILL.md. No `docs` skill is installed locally; only `improving-docs-and-rag-skills` exists under `.agents/skills/`.
- **Bash** — read `README.md` / `AGENTS.md` and checked global `~/.claude/skills/`. Found no standalone docs skill.

I was about to inspect `improving-docs-and-rag-skills` when the user interrupted.

## User

Check chat session history, there was a conversation where I referenced an existing docs skill in another repo.

## Assistant

Searched the Claude session transcripts for a docs-skill reference in another repo.

- **Bash** — `grep` across `~/.claude/projects/` surfaced a `writing-docs` skill; extracted full paths and located it on disk at `website/.agents/skills/writing-docs/SKILL.md`.
- **Bash** — read `writing-docs/SKILL.md`. Its method: an `OVERVIEW.md` per directory (front-loaded, ≤50 lines, 100 hard limit), modular docs colocated with code, centralized docs under `docs/`, and "front-load for discovery" so the first ~100 lines carry the high-signal material.

The repo's own plan pinned the exact target convention:

- **Bash / Read** — `plans/0002-improving-docs-and-rag-skills.md` §10 ("Convention standardization") defines the canonical form `docs/<type>/YYYY-MM-DD/NNNN-slug.md`, preserving per-subdir `NNNN`, with an `OVERVIEW.md` per subdir and a top-level `docs/OVERVIEW.md`. Migration step (1): preserve `NNNN`, add the dated path, rewrite all relative cross-links.

Planned the migration and mapped every cross-link before moving anything.

- **Bash** — `rename-work.sh claude-docs-convention-migration` to name the vcs work.
- **Bash** — grepped all relative `.md`/`.tsv` links in the non-session docs, plus external references into these paths from skill files/scripts, and confirmed `prompts/` had no internal links. Determined only one external **link** (the plan reference in `improving-docs-and-rag-skills/SKILL.md`) needed updating; the other references were bare issue-number prose where `NNNN` is preserved.

Executed the moves (plain `mv`; jj auto-tracks as renames):

- **Bash** — `benchmarks/`: `0000`/`0001` → `2026-06-06/`, `0002`–`0004` → `2026-06-07/`; co-located the `data/*.tsv` into their doc's date folder and removed the empty `data/` dir.
- **Bash** — `issues/`: `0001` → `2026-06-06/`, `0002`–`0008` → `2026-06-07/`, stripping the embedded `YYYYMMDD` from each filename.
- **Bash** — `plans/` (both `2026-06-07/`) and `prompts/` (all `2026-06-06/`, date stripped).

Rewrote cross-links:

- **Bash** — applied the uniform rule `](../../` → `](../../../` (every file gained one directory level), then fixed type-internal sibling links (same-date vs cross-date), the cross-type `issues`↔`benchmarks`/`plans`↔`issues` links, and `data/x.tsv` → `x.tsv`.
- **Edit** — updated the plan link in `improving-docs-and-rag-skills/SKILL.md` to the dated path.
- **Python (Bash)** — validated every relative link resolves. The only "broken" hits were a pre-existing `skills/vcs` typo in two benchmark docs (siblings prove the right path is `.agents/skills/vcs`) — fixed those — plus forward-references in the harness SKILL.md to not-yet-built artifacts (out of scope) and immutable session transcripts (left untouched).

Kick-started the docs skill by authoring `OVERVIEW.md` files:

- **Write** — `docs/OVERVIEW.md` (taxonomy + convention), and one per type: `benchmarks`, `coding-sessions`, `issues`, `plans`, `prompts`. Each front-loaded and ≤34 lines.

Formatting / lint:

- **Bash** — ran the repo's pinned Prettier and markdownlint-cli2 (from the root `node_modules`) over the changed docs. Fixed two new MD040 errors by adding a `text` language to the convention code fences in the two top-level OVERVIEWs; remaining lint hits were all pre-existing in immutable transcripts / unchanged docs.
- **jj** — noticed the broad `prettier --write` glob had reformatted 5 unrelated transcripts (blank-line normalization only); `jj restore --from @-` reverted them to keep the change set scoped to the migration + OVERVIEWs.

Final `jj st`: 6 added OVERVIEWs, 1 modified SKILL.md, and history-preserving renames across `benchmarks`/`issues`/`plans`/`prompts`.

## User

Export session, commit and push with /vcs

## Assistant

Invoked the `export-coding-session` skill, allocated index `0029` via `next-index.sh`, read the repo author from VCS config, and wrote this transcript. Next: redaction scan, then commit and push via the `vcs` skill.
