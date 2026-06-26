---
title: "jj workspaces vs git worktrees: what docs/benchmarks actually show"
date: 2026-06-06
repo: "coding-agent-skills (jj, `default` workspace on `main`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Cursor (Composer 2.5)"
summary: >-
  Read `docs/benchmarks` and related harness/issue docs to answer whether jj workspaces
  solve pain points git worktrees do not. Conclusion: both solve the same
  filesystem-isolation problem for co-located agents; the benchmarks show jj adding
  integration friction (conflicted commits on `main`, bookmark clobber, stale `default`,
  longer cleanup) rather than a measured advantage. Exported this session and committed
  from `default` without creating a sibling workspace.
---

<!-- markdownlint-disable MD013 MD024 -->

# jj workspaces vs git worktrees: what docs/benchmarks actually show

## User

Based on docs/benchmarks , does using Jujustu and workspaces actually solve any pain point compared to Git and worktrees?

## Assistant

Read `docs/benchmarks/0000-vcs-skill-conflict-resolution.md`, `docs/benchmarks/0001-vcs-skill-branch-hygiene-and-tokens.md`, `docs/issues/0001-20260606-jj-default-workspace-goes-stale-blocking-collaboration.md`, the harness setup in `.agents/skills/improving-vcs-skill/`, and `skills/vcs/ISOLATE.md` plus the [0011 session](./0011-claude-vcs-isolation-bar-and-skill.md).

**What the benchmarks compare:** whether agents can integrate pre-committed work onto shared `main` under multi-agent conflict, in git mode (per-agent `git worktree` + branch) vs jj mode (per-agent `jj workspace` + bookmark). Scored on correctness (objective oracle), speed, retries, branch/bookmark hygiene, and token cost — not day-to-day ergonomics.

**Shared pain point both solve equally:** development-time filesystem collision — two agents in the same working directory trample each other. Both give a separate on-disk checkout, own branch/bookmark, and safe parallel editing. The isolation harness treats them as equivalent objectives. Neither solves publish-time contention on `main`.

**Where jj was worse (even after the revised `vcs` skill):**

- Baseline stub skill: jj/easy wall(max) 558s vs git 88s; jj/medium **FAIL** (conflicted commit left in `::main`) vs git PASS.
- jj-specific failure modes: conflicted commits in history; bookmark clobber under concurrency (benchmark 0001 R8 — fixed with a skill guard); publish confusion (`jj bookmark set` + `jj git export`); harder hygiene for small models (Haiku forgot `jj bookmark delete` in 2/10 jj runs); `@git` mistaken for a real remote.
- Git friction was real but different: `git checkout main` fails when `main` is checked out elsewhere; detach-before-delete cleanup — workflow gotchas, not correctness failures. Git's non-fast-forward push rejection is safer by default than jj's silent bookmark overwrite.

**What jj does not demonstrably solve per these benchmarks:**

1. No measured speed or reliability advantage after skill revision (e.g. jj/hard concurrent wall 471s vs git 324s in round 14).
2. No simpler multi-agent lifecycle — the open issue doc describes jj-only stale-`default` and orphan-workspace gaps that compound with multi-agent use.
3. No isolation benefit git worktrees lack.

**Bottom line:** jj workspaces solve the **same** isolation pain point as git worktrees. The benchmarks do not show jj solving any **additional** pain point git worktrees cannot, and they show jj introducing extra integration semantics agents must learn. The measured win was teaching the right integration recipe per mode, not switching to jj. For purely "co-located agents without filesystem interference," git worktrees alone are sufficient per what `docs/benchmarks` validates.

## User

Don't create new jj workspace. Export session history and commit.

## Assistant

Invoked the `export-coding-session` skill. `next-index.sh` → `dir: docs/coding-sessions/2026-06-06`, `index: 0014`. Stayed in the existing `default` workspace (no `jj workspace add`). Wrote this transcript, ran `redaction-scan.sh`, and committed via jj.
