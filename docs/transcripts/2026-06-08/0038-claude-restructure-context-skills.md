---
title: "Restructure context-retrieval skills for clearer responsibilities"
date: 2026-06-08
repo: "coding-agent-skills (bookmark `claude-restructure-context-skills`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Opus 4.8, 1M context, thinking: high)"
summary: >-
  Renamed/split the docs + rag + vcs-setup skills into clearer responsibilities —
  `setting-up-vcs`, `setting-up-rag`, `retrieving-context` (new), `updating-docs`, and the
  `improving-context-retrieval-skills` harness — verified with a deterministic check pass
  plus an adversarial multi-agent review, then advanced/rebased onto `main` and
  integrated.
---

<!-- markdownlint-disable MD013 MD024 -->

# Restructure context-retrieval skills for clearer responsibilities

## User

Restructure skills so their responsibilities are more clear:

1. Rename the `setup-vcs` skill to be `setting-up-vcs`, and update references to this skill to the new name, especially in the `improving-vcs-skill` skill (if it's referenced).
2. Split the current `rag` skill to be `setting-up-rag` and `retrieving-context`. The former is about setting it up, the latter is about retrieving context.
3. Split the current `docs` skill to be `updating-docs` and fold the reading docs part into the same `retrieving-context` skill created before. The `retrieving-context` skill should help agents understand the doc structure if local or cloud RAG is not available, but nudge agents to use more advanced solution when they are available.
4. Rename `improving-docs-and-rag-skills` to `improving-context-retrieval-skills` harness to work with the new skills structure, iteratively improve `setting-up-rag`, `updating-docs`, and `retrieving-context` skills.

## Assistant

[Request interrupted by user]

## User

Restructure skills so their responsibilities are more clear:

1. Rename the `setup-vcs` skill to be `setting-up-vcs`, and update references to this skill to the new name, especially in the `improving-vcs-skill` skill (if it's referenced).
2. Split the current `rag` skill to be `setting-up-rag` and `retrieving-context`. The former is about setting it up, the latter is about retrieving context.
3. Split the current `docs` skill to be `updating-docs` and fold the reading docs part into the same `retrieving-context` skill created before. The `retrieving-context` skill should help agents understand the doc structure if local or cloud RAG is not available, but nudge agents to use more advanced solution when they are available.
4. Rename `improving-docs-and-rag-skills` to `improving-context-retrieval-skills` harness to work with the new skills structure, iteratively improve `setting-up-rag`, `updating-docs`, and `retrieving-context` skills.

## Assistant

Scouted the repo before changing anything (`Bash` `ls`/`find`, `Read` of every affected `SKILL.md`). Established the key facts:

- `.agents/skills/` is the canonical home; `.claude/skills` is a **directory symlink** to it, so directory renames are picked up automatically with no per-skill symlink edits.
- The `setup-vcs-hooks.sh` referenced in `package.json` / `AGENTS.md` is an unrelated **script**, not the skill — left alone.
- `improving-vcs-skill` does **not** reference `setup-vcs`, so requirement 1's "especially in improving-vcs-skill" had nothing to update there.
- Historical docs (`docs/coding-sessions`, `docs/benchmarks`, `docs/plans`) are records and were intentionally **not** rewritten.

Renamed the work to `claude-restructure-context-skills` and tracked the plan with the task list.

**Mechanical renames** (`mv` under `.agents/skills/`):

- `setup-vcs` → `setting-up-vcs`
- `docs` → `updating-docs`
- `rag` → `setting-up-rag`
- `improving-docs-and-rag-skills` → `improving-context-retrieval-skills`
- scaffolded a new `retrieving-context/`

**Authoring:**

- `setting-up-vcs/SKILL.md` — updated `name:` + the prose self-reference.
- `setting-up-rag` — rescoped to the **operator** side (provision / index / configure / tune the local Qdrant + FastEmbed stack; kept `query.py`). Added a "building the index vs. using it" note pointing consumers to `retrieving-context`. Updated `TUNING.md`'s harness link and the `rag_lib.py` / `rag-config.json` skill-name strings.
- `retrieving-context/SKILL.md` (new) — a **router**: best-first ladder of cloud RAG → local RAG (via `setting-up-rag`) → manual doc-structure navigation (the folded-in "find/read before you write" half of the old `docs` skill), with explicit "nudge up a tier when the corpus is large/long-form" guidance and a "when retrieval comes up empty, write it down" hand-off to `updating-docs`.
- `updating-docs/SKILL.md` — the writing half of the old `docs` skill; delegates find-before-write to `retrieving-context`.
- `improving-context-retrieval-skills` — reframed SKILL/LOOP/METRICS/SCENARIOS/MATRIX for **three** skills (updating-docs = corpus axis, setting-up-rag = config axis, retrieving-context = consumer plane read off the SIMPLE-vs-RAG modes). Updated `docs-eval.py`, `gold.py` exclusion globs (kept old-name patterns for historical reports, added new-name patterns), `mk-corpus.py`, `scoreboard.py`, the configs, the `DOCS_RAG_HARNESS_DIR` → `CONTEXT_RETRIEVAL_HARNESS_DIR` env var, and `inception/README.md`. Cleaned two pre-existing botched merge artifacts in `SCENARIOS.md` (a garbled GOLD bullet and a duplicate fact table).

**Verification (deterministic):** grep sweep for stale old-name references in live files (only intentional historical pointers remained); all cross-skill `../X/SKILL.md` links resolve; `prettier@3.8.3 --check` + `markdownlint-cli2@0.22.1` clean on every changed file (fixed table alignment, a duplicate Phase-1 bullet, and two `MD040` missing-code-fence-language flags); JSON valid; Python compiles; `gold.py validate` still passes (9 facts across 2 domains).

**Verification (adversarial):** ran a background `Workflow` with four independent dimension reviewers (reference integrity, responsibility clarity, harness coherence, spec compliance) plus a verification pass. Result: **no blockers/majors, spec compliance clean**. Fixed its four minor findings — three stale skill-name comments in `mk-corpus.py` / `scoreboard.py` / the harness `SKILL.md` script table (`scoreboard.sh` → `scoreboard.py`), and a dangling `<setting-up-rag-dir>` placeholder in `retrieving-context` (added a locator: it's the sibling `../setting-up-rag`).

Updated user memory with a rename/split map and flagged the now-stale older skill memories.

## User

Advance main, rebase onto main, resolve conflicts, export coding session transcript, then integrate using the /vcs skill.

## Assistant

Loaded the `vcs` skill (jj mode, working in the owned workspace in place).

- **Advance main:** `jj git fetch` → "Nothing changed". Local `main` (`7da50999`, the coding-style skill + its transcript) was already ahead of `origin/main` (`bd8d0a9a`) by 2 commits, so `main` was already the most advanced.
- **Ownership check:** `jj st` confirmed my working copy held only my restructure changes (no foreign edits).
- **Describe + rebase:** described the restructure commit (`refactor(skills): …`, with the `Co-Authored-By` trailer), then `jj rebase -b @ -d main`. The rebase was **clean — no conflicts** (my work moved from `bd8d0a9a` onto `7da50999`, picking up the 6 coding-style files).
- **Export:** created a separate `jj new` commit for this transcript, ran the `export-coding-session` helper (`next-index.sh` → index 0038), reconstructed the turns from the session log (user turns verbatim), and ran the redaction scan.
- **Integrate:** landed the work on `main` through the `vcs` skill's `integrate.sh` helper.
