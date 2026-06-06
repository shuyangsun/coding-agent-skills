---
name: improving-vcs-skill
description: Iterative, measurement-driven harness for IMPROVING the `vcs` skill. Use ONLY while authoring or changing `vcs` — never during normal development. It spawns parallel sub-agents that exercise `vcs` (and only `vcs`) on deliberately conflicting work across both VCS modes (Jujutsu-on-Git and Git-only), measures speed and merge-conflict-resolution quality, then drives rounds of revise-and-re-measure until the numbers meet the bar.
---

# Improving the `vcs` skill

This is a **meta-skill**: a closed loop that makes the [`vcs`](../vcs/SKILL.md)
skill measurably better at letting many coding agents do parallel work and
resolve merge conflicts cleanly. The harness is the means; a faster, safer `vcs`
is the end. You run rounds, each round produces numbers, and you keep the
revisions that move the numbers and revert the ones that don't.

> **Scope — authoring only.** Use this skill _only_ when authoring or changing
> `vcs`. It is never loaded during ordinary development, and sub-agents under
> test must never see it — they see `vcs` and a realistic task, nothing else.

## The invariant you are driving into `vcs`

Above all else, every revision of `vcs` must make an agent:

1. **Detect its VCS mode before starting work** — Jujutsu-on-a-Git-backend
   (jj present; use jj even though Git also works in a colocated repo) vs.
   **Git-only** (no `.jj`; e.g. Git + worktree, the path for cloud/GitHub
   sessions where jj isn't available).
2. **Abide by that mode's workflow, before and after work** — a Git-only agent
   must never reach for jj; a jj agent must use the jj workflow throughout.

Both modes are exercised every round, and `check-quality.sh` fails any round
where mode integrity broke. **Verify this holds — never assert it.**

## The loop (one round)

1. **Provision** an isolated sandbox per mode with `new-sandbox.sh` — seeded with
   conflict-prone fixtures, an integration point (`main`), one workspace per
   agent, and realistic per-agent task briefs.
2. **Brief & spawn** sub-agents (one per workspace) that load **only** `vcs`,
   standing in for different agents/tools and environments ([MATRIX.md](MATRIX.md)).
   Drive them into overlapping, conflicting edits ([SCENARIOS.md](SCENARIOS.md)).
3. **Run** them: each does its work and integrates onto `main` using only `vcs`,
   then returns a structured report.
4. **Measure** with `check-quality.sh` (objective pass/fail) and `record-metrics.sh`
   / `scoreboard.sh` (speed + conflict cost across rounds) — [METRICS.md](METRICS.md).
5. **Revise** `vcs` (its `SKILL.md`, referenced files, helper scripts, `COMMITS.md`)
   to fix what stalled, then **re-run and re-measure**. Keep changes that improve
   the numbers; revert changes that don't, or that buy speed with botched merges.
6. **Repeat** until the exit bar is met — [LOOP.md](LOOP.md) and [METRICS.md](METRICS.md).

## Bundled scripts

Run these from this skill's own directory (the path the runtime loaded it from);
below that is written `<skill-dir>/scripts/`. They keep every sandbox in one
disposable work area outside any real repo (`$VCS_HARNESS_DIR`, default
`$TMPDIR/vcs-harness`), so the harness never pollutes the project under test.

| Script              | Purpose                                                                                                   |
| ------------------- | --------------------------------------------------------------------------------------------------------- |
| `new-sandbox.sh`    | Provision one round's sandbox for a mode: fixtures, `main`, per-agent workspaces, briefs.                 |
| `check-quality.sh`  | Objectively score an integrated round: mode integrity, no markers, no lost work, no unresolved conflicts. |
| `record-metrics.sh` | Append one agent's measurements (time, conflict time, retries, quality) to the metrics log.               |
| `scoreboard.sh`     | Aggregate the metrics log per round with round-over-round deltas (is it trending down?).                  |
| `rm-sandbox.sh`     | Tear down a round or the whole work area (guarded to the harness work area only).                         |

Run `bash <skill-dir>/scripts/<name>.sh --help` for usage. Full round procedure,
sub-agent briefing, and the revise/revert discipline are in [LOOP.md](LOOP.md).

## Exit condition (the bar)

Stop only when, across **multiple consecutive rounds** (not one lucky run),
sub-agents using only `vcs` reliably (a) complete parallel work and (b) resolve
merge conflicts among themselves quickly and cleanly — **in both modes**, with
mode detection holding before and after work — while batch wall-clock and,
above all, conflict-resolution time are low and **trending down**, and output
quality holds or improves. The precise thresholds and how to read them are in
[METRICS.md](METRICS.md).
