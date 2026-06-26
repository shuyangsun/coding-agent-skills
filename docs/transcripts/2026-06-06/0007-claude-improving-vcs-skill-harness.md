---
title: "Authoring the improving-vcs-skill harness"
date: 2026-06-06
repo: "coding-agent-skills (bookmark: `main`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Opus 4.8, 1M context, effort: max)"
summary: >-
  Authored a repo-local, authoring-only meta-skill (`improving-vcs-skill`) that
  iteratively hardens the `vcs` skill via measured rounds of parallel sub-agent conflict
  testing; built and end-to-end-tested five helper scripts across both Git-only and
  jj-on-Git modes, then relocated/renamed the skill and updated the kick-start prompts.
---

<!-- markdownlint-disable MD013 MD024 -->

# Authoring the improving-vcs-skill harness

## User

(Set effort to max.) Read `@docs/prompts/0002-20260606-creating-testing-vcs-skill.md` and create the `testing-vcs-skill` skill. Make the main file compact and the skill modular, if the file is getting large, split it into multiple more modular files. Write scripts for common tasks.

## Assistant

Read the kick-start prompt, then oriented in the repo before writing anything.

- Read `AGENTS.md` (repo-agnostic rule for downloadable skills; Prettier + markdownlint; lefthook under Git, `jj fix` under jj), the current `vcs` skill (`SKILL.md` + `COMMITS.md` — commit-message formatting only today), and surveyed conventions in `export-coding-session` and `update-agent-permissions` plus the existing helper scripts (repo-root resolution: Git → Jujutsu → CWD).
- Noted `update-agent-permissions` lives as a real dir under `.agents/skills/` (not symlinked from `skills/`) — a repo-local skill.
- Probed the VCS command surface in throwaway temp dirs to lock down syntax before scripting:
  - `jj 0.41.0`, `git 2.54.0`; host repo is jj-colocated.
  - **Finding:** `jj git init` defaults to **colocated** (both `.git` and `.jj`; `git` _and_ `jj` work) — the realistic "jj on a Git backend" case and exactly the one mode-detection must get right (jj present ⇒ use jj even though Git also works). Git-only sandboxes have no `.jj`.
  - Confirmed conflict-detection primitives: Git `git ls-files -u` + `<<<<<<<`/`>>>>>>>` markers; jj `if(conflict,…)` template + `jj git export` to sync colocated refs.

Began writing the first and largest script, `new-sandbox.sh` (sandbox provisioner). _(Interrupted by the user mid-write.)_

## User

Remember, the `improving-vcs-skill` should only be in this repo, not something others need to download. Move `@skills/testing-vcs-skill/` to `@.agents/skills/`. Also change the name, name it as `improving-vcs-skill`, and highlight the iterative nature of this skill and its purpose is to improve another skill (`vcs`). Change both prompts under `@docs/prompts/` to update to this new name too.

## Assistant

Understood the correction: this is a **repo-local** meta-skill (like `update-agent-permissions`), so it belongs directly under `.agents/skills/`, not in the downloadable `skills/` set with a symlink. Did the housekeeping, then continued the build with the new name and framing.

- Relocated `skills/testing-vcs-skill/` → `.agents/skills/improving-vcs-skill/`; `git mv` + content-updated both `docs/prompts/` files to the new name (renamed the files too); left the two `docs/coding-sessions/` transcripts untouched as faithful historical records.
- Finished the script set under `.agents/skills/improving-vcs-skill/scripts/`:
  - `new-sandbox.sh` — provision one round's sandbox for a mode (Git or jj): seed conflict-prone fixtures (CHANGELOG top-insert, `config.yaml` version line, `pipeline.py` step marker, `registry.json` summary, `feature_flags.py`), an integration ref (`main`), one workspace per agent (`git worktree` / `jj workspace add`), and realistic per-agent task briefs with unique sentinel tickets. Keeps everything under one disposable work area (`$VCS_HARNESS_DIR`, default `$TMPDIR/vcs-harness`).
  - `check-quality.sh` — objectively score an integrated round: mode integrity (no `.jj` in a Git sandbox), no conflict markers on `main`, every sentinel present (no lost work), no unresolved conflicts (Git index / jj conflict template).
  - `record-metrics.sh` + `scoreboard.sh` — append per-agent measurements (TSV) and aggregate per round with round-over-round deltas (portable BSD-awk; no gawk extensions).
  - `rm-sandbox.sh` — guarded teardown (only ever deletes inside the harness work area; a round delete additionally requires `manifest.env`).
- **End-to-end tested all scripts** in an isolated temp work area (summarized tool runs):
  - Provisioned Git and jj sandboxes; verified `jj workspace add --name … -r main` flags on 0.41.
  - Proved the fixtures are genuinely hot: independent edits produced a **real Git merge conflict** and a **real jj rebase conflict**.
  - Verified `check-quality.sh` **passes** a clean integration and **fails** all four ways it should: `.jj` in a Git sandbox, leftover markers, a dropped changelog-only sentinel (lost work), and a conflicted jj commit on `main`.
  - Confirmed `scoreboard.sh` shows the target signal, e.g. `wall(max) 310→205 (-105)`, `conflict(max) 160→70 (-90)`, `pass% 67→100`.
  - Confirmed `rm-sandbox.sh` refuses paths outside the work area (e.g. `/etc`).
  - Noted a real jj gotcha for later `vcs` hardening: a cross-workspace conflict materializes into a workspace's working copy on its _next_ jj command, so hand-editing before letting jj settle gets clobbered — captured in `SCENARIOS.md`.
- Wrote a compact 75-line `SKILL.md` (purpose = iteratively improve `vcs`; the invariant: detect mode + abide before/after; the loop; script table; exit bar) delegating to four modular references: `LOOP.md` (per-round procedure, sub-agent prompt template, revise/revert discipline), `MATRIX.md` (agents × environments × modes; simulation fidelity), `SCENARIOS.md` (conflict fixtures, sentinel design, objective quality, hazards), `METRICS.md` (measurements, structured report format, scoreboard, the done bar).
- Formatted with Prettier and linted with markdownlint (0 errors across the repo); confirmed nothing gitignored; recorded the repo-local-vs-downloadable skill convention to memory.

Summarized the result and offered to actually run the improvement loop (Part 2) as a next step rather than launching many sub-agents unprompted.

## User

Export session, commit and push using `jj`.

## Assistant

Loaded the `export-coding-session` skill and checked `jj` state: working copy held the substantive change (skill + prompt renames) on top of `main`; `origin` = the GitHub remote; author identity `Shuyang Sun <shuyangsun10@gmail.com>`.

Followed `COMMITS.md`: split the work into two commits — `feat(improving-vcs-skill): …` for the skill + prompt renames, and `docs(coding-sessions): …` for this transcript — via `jj describe` then `jj new`. Wrote this transcript into the child commit, ran the redaction scan, advanced the `main` bookmark, and pushed with `jj git push`.
