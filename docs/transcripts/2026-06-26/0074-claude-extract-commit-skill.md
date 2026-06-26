---
title: Extract commit skill from vcs
date: 2026-06-26
repo: "coding-agent-skills (jj; work landed on `main` from workspace `claude-commit-skill`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Opus 4.8, 1M context, effort: max)"
summary: >-
  Split the commit-message guidance (COMMITS.md) out of the `vcs` skill into a
  new standalone `commit` skill, rewired `vcs`, its integrate helper, and the
  `improving-vcs-skill` harness to reference it, verified with prettier /
  markdownlint, then committed and integrated to `main`.
---

<!-- markdownlint-disable MD013 MD024 -->

# Extract commit skill from vcs

_Session configured to Opus 4.8 (1M context) and effort `max` via `/model` and `/effort max` before the first request._

## User

Take @.agents/skills/vcs/COMMIT.md out of the VCS skill, put it into a different skill named `commit`. The VCS skill should still reference the new commit skill to enforce good commit habits.

## Assistant

Explored the `vcs` skill before changing anything.

- Listed `.agents/skills/vcs/` and `.agents/skills/`, and read `vcs/SKILL.md` and the commit-message file. Discovered the actual filename is **`COMMITS.md`** (plural), not `COMMIT.md` — it holds the commit-message format (type/scope/subject, WHY body, `Author:` + `Co-Authored-By:` trailers, examples, HEREDOC mechanics).
- Read `vcs/ISOLATE.md`/`INTEGRATE.md` heads, the `scripts/` listing, and `AGENTS.md`. Confirmed the conventions: each skill is a directory under `.agents/skills/` with a `SKILL.md`; `.claude/skills` is a single directory symlink to `.agents/skills`; skills must stay repo-agnostic.
- Grepped the repo for `COMMITS` references. Active (non-transcript) references: `vcs/SKILL.md` §5, `vcs/scripts/integrate.sh:428`, `improving-vcs-skill/SKILL.md:83`, `improving-vcs-skill/LOOP.md:147`, `improving-vcs-skill/scripts/new-sandbox.sh:333`. The rest were historical transcripts/benchmarks (left untouched).

Renamed the auto-created session-start workspace from `claude-pending-…` to `claude-commit-skill` with `rename-work.sh` now that the task was clear, then planned the move with a task list:

1. Create `commit` skill from `COMMITS.md`.
2. Remove `COMMITS.md` from `vcs`.
3. Point `vcs` at the `commit` skill.
4. Fix stale `COMMITS.md` refs in `improving-vcs-skill`.
5. Format, verify, commit, integrate.

**Built the `commit` skill.** Copied `vcs/COMMITS.md` → `commit/SKILL.md` to preserve the body verbatim (jj tracked it as a rename), then prepended YAML frontmatter (`name: commit` + a "Load BEFORE you write or edit a commit message…" description noting that `vcs` defers here) and renamed the heading to `# Commit messages`. Removed `vcs/COMMITS.md`.

**Pointed `vcs` at it.** Rewrote `vcs/SKILL.md` §5 ("Fallback docs and commit messages") so it no longer carries commit guidance — instead it says authoring/editing any message (including merge commits while integrating) "is governed by the separate `commit` skill… good commit habits are not optional." Updated the merge-message comment in `vcs/scripts/integrate.sh` to "see the commit skill."

**Fixed stale references** in the `improving-vcs-skill` harness so they point at the `commit` skill: the revise step in `SKILL.md`, the lever bullet in `LOOP.md`, and the "commit-skill-shaped" test-data comment in `scripts/new-sandbox.sh`.

**Verified.** Installed the pinned dev deps (`bun install --ignore-scripts`, to skip the `prepare` hook reconfiguring this session) and ran the real checks:

- `prettier --check` — clean on all four changed markdown files.
- `markdownlint-cli2` — my files clean. (`bun run lint:md` is already red on `main` from pre-existing issues in `docs/transcripts/…0073…` and `inception/README.md`, neither touched here.)
- `bash -n` — both edited shell scripts parse.

`jj status` showed exactly the intended change set: a rename `vcs/COMMITS.md => commit/SKILL.md` plus modifications to `vcs/SKILL.md`, `vcs/scripts/integrate.sh`, and the three `improving-vcs-skill` files — no foreign edits.

Presented the result and, since the user hadn't explicitly asked to land it, asked how to finish (commit + integrate / commit locally / leave uncommitted), with the proposed commit message previewed.

## User

_(Answered the question)_ **Commit & integrate to main** — `jj describe` with the proposed message, then `integrate.sh` to land on `main` and push.

## Assistant

- `jj describe` on the working-copy commit with a `refactor(vcs): split commit-message guidance into its own commit skill` message (WHY body + `Author:` and `Co-Authored-By:` trailers per the new `commit` skill). Re-verified `jj diff -r @ --name-only` listed only my six paths.
- Ran `integrate.sh claude-commit-skill`: it fast-forwarded `main` to the linear work (no merge needed), deleted the merged bookmark, retired the jj workspace, and published `main` to the remote.
- Verified on `main`: tip is the new commit and `main` / `main@origin` resolve to the same revision (push synced); `commit/SKILL.md` present, `vcs/COMMITS.md` gone, zero lingering `COMMITS.md` refs in active skills; my workspace retired cleanly (no orphan dir or owner marker). Noted two unrelated FYIs (pre-existing `lint:md` failures on `main`; stale `*-pending-*` workspaces from other sessions, left untouched per shared-checkout etiquette).

## User

/export-transcript, then commit and push again.

## Assistant

Loaded the `export-transcript` skill. Isolated a fresh workspace `claude-export-transcript` (the previous one was retired on integration), ran `next-index.sh` (→ `docs/transcripts/2026-06-26`, index `0074`), wrote this transcript, ran the redaction scan, then committed and integrated to `main`.
