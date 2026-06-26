---
name: improving-vcs-skill
description: Iterative, measurement-driven harness for IMPROVING the `vcs` skill. Use ONLY while authoring or changing `vcs` — never during normal development. It spawns parallel sub-agents that exercise `vcs` (and only `vcs`) on deterministic, pre-committed conflicting work across both VCS modes (Jujutsu-on-Git and Git-only) and a difficulty ladder, measures conflict-resolution speed and quality broken down by model tier, then drives rounds of revise-and-re-measure until the numbers meet the bar.
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

## Test the VCS, not the coding (the determinism principle)

The only thing under test is whether agents **collaborate through version
control** — integrate each other's work and resolve merge conflicts cleanly and
fast. So the harness removes coding-ability variance entirely:

- Every agent's change is **generated deterministically and pre-committed** on
  that agent's own branch/bookmark (`agent-K`) — a realistic "finished PR". The
  sub-agent **writes no code**; its sole job is to integrate `agent-K` onto the
  shared `main`, resolving the conflicts that arise because teammates touched
  the same files and lines.
- Sub-agents are told **not to do any coding work after integrating** — no new
  code, no tests, no running the app, no "make it work" verification. We measure
  the quality and speed of the conflict resolution **immediately** after the
  merge/rebase, because that — not downstream patching — is what `vcs` governs.
  The one allowed finish step is the VCS tidy-up `vcs` prescribes (deleting the
  merged `agent-K` branch/bookmark), which has its own hygiene metric.
- Because the inputs are deterministic, the **correct merged result is
  deterministic too**, so `check-quality.sh` scores resolution quality
  objectively (union preserved, tie-break value correct, files still parse,
  nothing lost or clobbered) rather than just scanning for conflict markers.

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

## Difficulty ladder and model tiers (both varied every loop)

- **Difficulty** (`new-sandbox.sh --difficulty`): `easy` (one small union
  conflict), `medium` (several union conflicts + a same-line tie-break), `hard`
  (every agent rewrites the same large blocks across several files → big,
  overlapping, multi-file conflicts with many parallel agents). See
  [SCENARIOS.md](SCENARIOS.md).
- **Model tier** (vendor-agnostic): each sub-agent stands in for a capability
  tier — **large** (frontier), **mid** (workhorse), **small** (fast/cheap).
  Different-sized models behave very differently on big conflicts, so results
  are recorded and reported **per tier**: a `vcs` revision that only works for
  large models has **not** met the bar. See [MATRIX.md](MATRIX.md).

## The loop (one round)

1. **Provision** an isolated sandbox per mode + difficulty with `new-sandbox.sh`
   — deterministic fixtures, each agent's work pre-committed on `agent-K`, an
   integration point (`main`), and integration-only briefs.
2. **Brief & spawn** sub-agents (one per workspace) that load **only** `vcs`,
   spread across model tiers and environments ([MATRIX.md](MATRIX.md)). Each
   integrates its pre-committed `agent-K` onto `main` using only `vcs`.
3. **Run** them: each resolves conflicts, publishes, **stops**, and returns a
   structured report.
4. **Measure** with `check-quality.sh` (objective pass/fail incl. the resolution
   oracle, plus `STALE_REFS`, `DEFAULT_OK`, `ORPHAN_WS`, `ORPHAN_DIRS`, and `ORPHAN_EMPTY_HEADS`
   lifecycle hygiene lines) and `record-metrics.sh` / `scoreboard.sh` (speed,
   conflict cost, **output tokens**, stale-ref hygiene, **jj default readiness**,
   and **retired-workspace cleanup**, broken down by round and by tier) —
   [METRICS.md](METRICS.md).
5. **Revise** `vcs` (its `SKILL.md`, referenced files, helper scripts) — and the
   companion `commit` skill it defers to for message format — to fix what stalled,
   then **re-run and re-measure**. Keep changes that improve the numbers; revert
   changes that don't, or that buy speed with botched merges.
6. **Repeat** until the exit bar is met — [LOOP.md](LOOP.md) and [METRICS.md](METRICS.md).

The loop above is the `--task integrate` flow (land work, resolve conflicts). A
symmetric `--task start` flow measures the other bookend — **session-start
isolation**: whether an agent carves out its own worktree/workspace before doing
new work so co-located agents don't interfere. Run start rounds alongside
integration rounds; details in [LOOP.md](LOOP.md) and [SCENARIOS.md](SCENARIOS.md).

## Bundled scripts

Run these from this skill's own directory (the path the runtime loaded it from);
below that is written `<skill-dir>/scripts/`. They keep every sandbox in one
disposable work area outside any real repo (`$VCS_HARNESS_DIR`, default
`$TMPDIR/vcs-harness`), so the harness never pollutes the project under test.
They require `python3` (the deterministic content engine) plus `git`, and `jj`
for jj-mode rounds.

| Script               | Purpose                                                                                                                                                                                                                                                                                                                                      |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `new-sandbox.sh`     | Provision one round: `--task integrate` (fixtures + pre-committed per-agent work + integration briefs; jj rounds deliberately stale `default`) or `--task start` (shared repo + a one-edit brief that tests session-start isolation).                                                                                                        |
| `check-quality.sh`   | Objectively score an integrated round: mode integrity, no markers/unresolved, no lost work, correct resolution, **+ branch/bookmark hygiene** (`STALE_REFS`), **jj default readiness** (`DEFAULT_OK`), and **retired workspace cleanup** (`ORPHAN_WS` / `ORPHAN_DIRS` / `ORPHAN_EMPTY_HEADS`). Also scores a start round's change + cleanup. |
| `check-isolation.sh` | Score a `--task start` round's **session-start isolation** (`ISOLATED`) — did the agent carve out its own worktree/workspace before working — from durable git-reflog / jj-op-log signals. Also scores the **`<ide>-<work>` naming** convention (`NAME_OK`, main arm only).                                                                  |
| `scenario.py`        | Deterministic content engine: seeds fixtures, applies each agent's diff, emits the plan, runs the oracle, and prints the start-task edit instructions.                                                                                                                                                                                       |
| `record-metrics.sh`  | Append one agent's measurements (time, conflict time, **tokens**, **stale refs**, **orphan workspaces**, **default readiness**, **isolation**, retries, quality, **tier**, **difficulty**) to the log.                                                                                                                                       |
| `scoreboard.sh`      | Aggregate the log by round (trend) **and by model tier** (incl. `mean_tok`, `stale`, `orph`, `def`, and a difficulty×tier pass-rate matrix).                                                                                                                                                                                                 |
| `rm-sandbox.sh`      | Tear down a round or the whole work area (guarded to the harness work area only).                                                                                                                                                                                                                                                            |

Run `bash <skill-dir>/scripts/<name>.sh --help` for usage. Full round procedure,
sub-agent briefing, and the revise/revert discipline are in [LOOP.md](LOOP.md).

## Exit condition (the bar)

Stop only when, across **multiple consecutive rounds** (not one lucky run),
sub-agents using only `vcs` reliably (a) complete parallel work and (b) resolve
merge conflicts among themselves quickly and cleanly — **in both modes, across
the difficulty ladder, and across model tiers** — with mode detection holding
before and after work, while batch wall-clock and, above all, conflict-resolution
time are low and **trending down**, and output quality holds or improves. The
precise thresholds and how to read them are in [METRICS.md](METRICS.md).
