<!-- markdownlint-disable MD013 MD024 -->

# Benchmark created `cursor-vcs-benchmark` jj workspace but never used it

- **Status:** Resolved (2026-06-07) — guardrail added; the original run stays as recorded
- **Date:** 2026-06-07
- **Area:** `vcs` skill adherence during harness orchestration; benchmark artifact provenance
- **Severity:** Low–medium — the benchmark results are still valid, but the orchestrator violated its own isolation rule and the written report overstated what happened
- **Environment:** Jujutsu (`jj`) on a Git backend, colocated `coding-agent-skills` repo; `improving-vcs-skill` harness in `/tmp/vcs-harness`
- **Related:** [0002](0002-20260607-agent-used-default-jj-workspace-instead-of-isolating.md) (same class of failure: parent agent skipped `vcs` isolation); benchmark [0002](../benchmarks/0002-vcs-skill-composer-2.5-jj-vs-git.md)

## Summary

During the Cursor Composer 2.5 jj-vs-git benchmark session, the orchestrating
agent ran `isolate.sh cursor-vcs-benchmark` at the user's explicit request
("Create a new Jujutsu workspace first"), then **never `cd`'d into that
workspace or did any repo work from it**. Harness sandboxes were provisioned and
scored from `/tmp/vcs-harness` (correct for the test fixtures), but benchmark
artifacts (`docs/benchmarks/0002-…` and `docs/benchmarks/data/0002-…`) were
written into the **default** checkout. The benchmark report incorrectly labeled
`cursor-vcs-benchmark` as the "orchestration workspace."

The workspace still exists on disk as a sibling checkout; it was a no-op for the
session.

## Expected behavior

Two distinct locations are involved in a harness run like this:

| Location                                               | Role                                                                                                                                                                               |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Orchestrator jj workspace** (`cursor-vcs-benchmark`) | Where the parent agent should isolate before editing _this repo_ — provisioning commands can run from anywhere, but writing `docs/benchmarks/*` and any commits should happen here |
| **Harness sandboxes** (`$VCS_HARNESS_DIR/round-*`)     | Disposable test repos outside the project; per-agent `ws-agent-K` workspaces/worktrees where integration sub-agents run                                                            |

The correct orchestration flow:

1. Detect jj (`jj root` succeeds in `coding-agent-skills`).
2. `bash <skill-dir>/scripts/isolate.sh cursor-vcs-benchmark`.
3. `cd` to the printed `WORKSPACE=` path
   (`/Users/shuyang/developer/coding-agent-skills-cursor-vcs-benchmark`).
4. From there, drive `new-sandbox.sh`, `check-quality.sh`, `record-metrics.sh`
   (paths to `/tmp/vcs-harness` are fine).
5. Write benchmark markdown and metrics TSV under `docs/benchmarks/` in **that**
   isolated checkout, then integrate onto shared `main` per `vcs` when done.

The user asked to create the jj workspace **first** specifically so orchestration
would not dirty the shared `default` checkout.

## Actual behavior

1. `isolate.sh cursor-vcs-benchmark` ran successfully and printed:

   ```text
   vcs-isolate: created jj workspace
   MODE=jj
   WORKSPACE=/Users/shuyang/developer/coding-agent-skills-cursor-vcs-benchmark
   WORK_REF=cursor-vcs-benchmark
   CREATED=yes
   ```

2. The agent did **not** `cd` into `WORKSPACE`. Subsequent shell commands and a
   shell subagent operated from the default tree and `/tmp` paths.

3. Benchmark deliverables landed in the default checkout:
   - `docs/benchmarks/0002-vcs-skill-composer-2.5-jj-vs-git.md`
   - `docs/benchmarks/data/0002-composer-2.5-metrics.tsv`

   The isolated sibling checkout contains the repo snapshot from workspace
   creation time and does **not** include those files (it diverged before the
   benchmark docs were written).

4. The benchmark report's metadata claimed:

   > **Orchestration workspace:** `cursor-vcs-benchmark` (jj workspace created via `isolate.sh` before the run)

   That was inaccurate — creation happened; use did not.

5. When the user asked whether the workspace had been used, the agent confirmed
   it had not. The user declined a retroactive fix ("too late now") and asked
   for this issue doc instead.

## Why this matters

**Isolation integrity.** The `vcs` skill's first rule is "isolate before you
edit." The benchmark session was explicitly about exercising jj workspaces vs
git worktrees, yet the orchestrator treated workspace creation as a checkbox
rather than the directory it would work from. That is the same meta-failure as
[0002](0002-20260607-agent-used-default-jj-workspace-instead-of-isolating.md),
but worse in one respect: here the agent _did_ call `isolate.sh` and still
ignored the result.

**Report accuracy.** Labeling an unused workspace as "orchestration workspace"
misleadingly suggests the run followed `vcs` end-to-end. Readers comparing jj
orchestration ergonomics could draw the wrong conclusion about whether the
parent agent actually practiced what was measured.

**Artifact provenance.** Benchmark files in `default`'s working copy are not on
the `cursor-vcs-benchmark` bookmark. If the isolated workspace is later
forgotten or deleted, there is no jj history tying the benchmark commit to the
named workspace the user requested.

**What was _not_ broken.** The harness sandboxes in `/tmp/vcs-harness` are
designed to live outside the real repo; agents integrating in `round-*/ws-agent-K`
were in the correct place for the _test_. Only the **parent agent's** repo edits
were in the wrong checkout.

## Timeline (this session)

1. User requested a Composer 2.5 benchmark across jj and git, all difficulties,
   with results under `docs/benchmarks/`, and to create a jj workspace first.
2. Agent ran `isolate.sh cursor-vcs-benchmark` ✓
3. Agent provisioned `round-200` … `round-205` under `/tmp/vcs-harness` ✓
4. Agent delegated integrations to a shell subagent (valid for harness work) ✓
5. Agent wrote benchmark docs/metrics to default checkout ✗
6. User noticed the workspace was unused; agent acknowledged the mistake ✓
7. User asked for this issue document instead of retroactive relocation ✓

## Suspected causes

1. **Task split confusion.** "Create jj workspace" and "run harness in `/tmp`"
   were treated as independent setup steps. The agent connected the first to
   `isolate.sh` but did not connect "write `docs/benchmarks`" to "work in
   `WORKSPACE`."

2. **Harness-first framing.** Loading `improving-vcs-skill` centers attention on
   sandbox paths (`$VCS_HARNESS_DIR`), not on where the orchestrator should stand
   in the host repo. No harness check enforces parent-agent isolation.

3. **Subagent delegation.** After spawning a shell subagent for integrations,
   the parent resumed file writes in whatever checkout Cursor had open (default),
   without re-validating `jj workspace list` or `pwd`.

4. **Cosmetic completion.** Printing `WORKSPACE=…` from `isolate.sh` was treated
   as sufficient evidence the step was "done," without the mandatory `cd`.

## Reproduction

1. In a jj-backed repo, ask an agent to create a workspace with `isolate.sh`
   and then run a task that writes files under `docs/` (e.g. a benchmark report).
2. Do not remind it to `cd` into `WORKSPACE`.
3. Observe: workspace exists (`jj workspace list` shows the new name), but new
   files appear in the default checkout's tree, not in the sibling workspace path.

## Acceptance criteria for a future fix

- When `isolate.sh` prints `CREATED=yes` and `WORKSPACE=…`, the orchestrator
  `cd`s there before any repo edit or documents why it cannot.
- Benchmark/issue docs do not claim a workspace was used unless `pwd` / jj
  workspace name confirm it at write time.
- Optional: a lightweight pre-edit guard in `vcs` or agent rules — if
  `jj workspace name` is `default` and the task will modify tracked files,
  stop and isolate first.
- Optional: harness README or `LOOP.md` note for parent agents: sandbox paths
  ≠ host-repo working copy; isolate before writing `docs/benchmarks/*`.
- Parent-agent isolation failures are tracked separately from `--task start`
  sub-agent isolation metrics (which only score synthetic sandboxes today).

## Resolution

The "created but never used" gap is closed at the point the workspace is made.
`scripts/isolate.sh` now emits, only when it actually creates a fresh
workspace/worktree (`CREATED=yes`), a prominent actionable pair reusing the
`NEXT_CWD=` convention agents already act on after `integrate.sh`:

```text
vcs-isolate: NEXT_CWD=<path>
vcs-isolate: cd to NEXT_CWD now; do every edit and command for this work from there, not the checkout you started in
```

`vcs/SKILL.md` §2 was tightened to make the `cd` mandatory ("before you edit,
read, or run anything else") and to distinguish `CREATED=no` (already isolated;
work in place). This targets the exact failure mode — treating workspace
creation as a checkbox rather than the directory to work from.

Verified with the `improving-vcs-skill` harness on Claude Haiku across both
modes: `--task start --start-from main` rounds in jj and git both score
`ISOLATED=pass`, `NAME_OK=pass`, and crucially **`ISO_FS=pass`** — the agent did
its edits *inside* the isolated checkout, not the shared one (the git round
confirms "primary checkout untouched … work was done in a separate worktree").

The behavioral acceptance criteria around *parent-agent* orchestration
(confirming `pwd`/workspace name before writing, separate parent-vs-sub-agent
isolation metrics) remain as future harness work; this fix addresses the
script/skill side that makes the `cd` unmissable.

## What would have been correct (for reference)

```sh
# once, at session start
bash .agents/skills/vcs/scripts/isolate.sh cursor-vcs-benchmark
cd /Users/shuyang/developer/coding-agent-skills-cursor-vcs-benchmark

# harness work (paths are outside the repo — fine from any cwd)
bash .agents/skills/improving-vcs-skill/scripts/new-sandbox.sh ...

# repo artifacts — must be from the isolated checkout
# edit docs/benchmarks/0002-... here, then integrate per vcs when ready
```

The unused workspace remains at
`/Users/shuyang/developer/coding-agent-skills-cursor-vcs-benchmark` with bookmark
`cursor-vcs-benchmark`; it can be forgotten or removed manually if no longer
needed.
