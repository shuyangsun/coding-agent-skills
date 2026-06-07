# The improvement loop

How to run one round, and how to decide what to change in `vcs` between rounds.
This is the heart of the skill: **iterate until the numbers meet the bar**, not
until the skill _reads_ well. A revision that doesn't move the measurements in
[METRICS.md](METRICS.md) — or that buys speed with botched merges — is not an
improvement; revert it.

## Per-round procedure

Each round, cover **both** VCS modes (`git` and `jj`) and vary **difficulty**
and **model tier** so a few rounds sample the whole space ([MATRIX.md](MATRIX.md),
[SCENARIOS.md](SCENARIOS.md)). For each (mode, difficulty) cell:

1. **Provision.** `bash <skill-dir>/scripts/new-sandbox.sh --mode <git|jj>
--difficulty <easy|medium|hard> [--agents N]`. It seeds deterministic
   fixtures, **pre-commits each agent's change** on `agent-K`, writes a plan
   (`spec.json`), the briefs, and a manifest. Note the per-agent workspace paths
   and the integration ref (`main`). The agents author **no code** — their work
   already exists; they only integrate it.

2. **Brief & spawn sub-agents — one per workspace, in parallel.** Each stands in
   for an (agent/tool × environment × **model tier**) cell from
   [MATRIX.md](MATRIX.md). Spawn across tiers (large / mid / small) using
   whatever your platform exposes for model selection. Give each sub-agent
   **only**:
   - the `vcs` skill (instruct it to load and follow `vcs` for all VCS decisions);
   - its task brief (`briefs/agent-K.md`) — an integration-only ticket;
   - its workspace path, and the instruction to publish onto `main`.

   Withhold everything else. **Do not** reveal this harness, that it's a test,
   which VCS mode the repo is in, or where conflicts will be — detecting the mode
   and handling conflicts is exactly what `vcs` must make the agent do alone. The
   exact sub-agent prompt template is at the end of this file.

3. **Drive the collision.** The pre-committed branches already target overlapping
   files/lines, so conflicts arise the moment agents integrate. Choose an
   integration pattern (escalate across rounds):
   - **Serialized integration** (start here): agents integrate onto `main` one
     after another, so each later agent meets the earlier ones' conflicts.
     Cleanest to measure.
   - **Concurrent integration** (stress): agents integrate at the same time,
     contending for `main`. Maximal pressure on `vcs`'s etiquette. The correct
     union result is order-independent, so quality stays objectively checkable.

4. **Collect reports.** Each sub-agent returns the structured report in
   [METRICS.md](METRICS.md) (conflict-detection/resolution time, retries, stalls,
   round-trips, plus a short narrative: what was clear, what was ambiguous, where
   it stalled, where a conflict was mishandled). Reports note the agent's **tier**.

5. **Score objectively.** `bash <skill-dir>/scripts/check-quality.sh <round-dir>`.
   It is the source of truth for quality — it does not trust agent self-reports.
   PASS requires: mode integrity intact, no conflict markers, no unresolved
   conflict, every sentinel present, and the **resolution oracle** green (union
   preserved with no dups/loss, tie-break value correct, structured files still
   parse, untouched files byte-identical to baseline). That last clause also
   catches an agent that did forbidden "extra work". It also prints, **separately
   from that verdict**, the branch/bookmark **hygiene** metric (`STALE_REFS=N` —
   merged `agent-K` refs the agent failed to delete, excluding any `--pr-backed`
   ones); the exit bar wants this at 0.

6. **Record + compare.** For each agent, `record-metrics.sh` the time/conflict/
   retry numbers, the quality verdict, the **`--tokens`** (output-token) and
   **`--stale`** (hygiene) counts, **and `--tier` / `--difficulty`**; then
   `scoreboard.sh` to see this round against prior rounds **and** the per-tier
   breakdown. Headline costs: **batch wall-clock** and, above all,
   **conflict-resolution time** — watch their round-over-round deltas and whether
   any tier or difficulty×tier cell lags. `stale` must be 0; `mean_tok` must not
   balloon. (When driven by the bundled runners, `_score.py` fills `--stale` from
   the oracle and `--tokens` from each agent's transcript JSONL — pass the
   workflow's transcript dir as `_score.py`'s third argument.)

7. **Diagnose, then revise `vcs`.** Read the narratives _through the lens of the
   numbers_: find what actually cost time or caused a `check-quality` failure
   (ambiguous mode detection, a missing rebase step, unclear conflict-resolution
   etiquette, a slow or absent helper script) and change `vcs` to fix that one
   thing. Pay attention to tier: if small models stall where large ones don't,
   `vcs` is relying on inference the smaller model can't supply — make the step
   explicit. Keep edits small and attributable so the next round's numbers tell
   you whether they worked.

8. **Re-run & re-measure.** New round, fresh sandboxes (`new-sandbox.sh` auto-picks
   the next round number). Compare. **Keep** the revision if wall-clock and/or
   conflict time fell and quality held (across tiers); **revert** it otherwise.

9. **Tear down** finished rounds with `rm-sandbox.sh <round-dir>` (or `--all` at
   the end). Sandboxes are disposable; the metrics log persists for comparison.

## Start rounds (session-start isolation)

The procedure above drives `--task integrate` rounds (land pre-committed work,
resolve conflicts). The symmetric front bookend is `--task start`, which measures
whether an agent **isolates before doing new work** so co-located agents on one
machine don't interfere ([SCENARIOS.md](SCENARIOS.md)). Run these alongside
integration rounds; they're single-agent, so cover the space by repetition.

1. **Provision.** `new-sandbox.sh --mode <git|jj> --task start --start-from
<main|worktree>`. `main` = the agent begins in the shared primary checkout and
   must isolate; `worktree` = it's handed its own worktree/workspace and must
   **not** create a redundant nested one. (Difficulty is fixed to the `easy` edit;
   the round is single-agent.)
2. **Brief & spawn one sub-agent**, exactly as in step 2 above — only `vcs` + its
   brief + its **start** path (the `start=` line in the manifest). Withhold the
   harness, the mode, and the fact that isolation is under test. The brief asks
   for one tiny, fully-specified edit landed on `main` — the isolation decision
   must come from `vcs` alone.
3. **Score with BOTH** `check-isolation.sh <round-dir>` (the `ISOLATED=pass/fail`
   session-start verdict **and** the `NAME_OK` `<ide>-<work>` naming verdict on the
   main arm) **and** `check-quality.sh <round-dir>` (that the change and the branch
   cleanup landed right — start rounds carry the hygiene metric too). All report
   **separately**, so isolation, naming, correctness, and cleanup stay
   distinguishable.
4. **Record** with `record-metrics.sh … --isolate <pass|fail> --name-ok
   <pass|fail|n/a>` and read the `iso` and `name` columns on the scoreboard (want
   0; `-` on integration rounds, and `name` is `-`/`n/a` on the worktree arm).

When you iterate on isolation, drive `iso` round-over-round (isolate into your own
worktree/workspace + branch/bookmark before new work on a shared repo; if you're
already in one, work in place) and the `<ide>-<work>` naming via `name`, just like
the cleanup rule was driven by `stale`. (To make naming a real test, the start
brief deliberately does **not** prescribe a branch name — the name comes from
`vcs` alone.)

## What to change in `vcs` (and what not to)

Drive `vcs` toward the properties in the kick-start prompt, but only via changes
the measurements justify:

- **Mode detection** front-and-center, unambiguous, and re-checked after work.
- **Compactness** — push situation-specific detail into referenced markdown; a
  bloated `SKILL.md` that slows agents down is a regression even if "complete."
- **Helper scripts** for session-start / session-end (new workspace/worktree with
  intuitive bookmark/branch names; integrate-and-publish) that resolve the repo
  root themselves and respect the repo's hooks (lefthook under Git, `jj fix`
  under jj). If a missing script cost agents time, add it; measure that it helped.
- **`COMMITS.md`** — refine the existing commit-message guidance, don't duplicate
  it. (Feature commits are pre-made here, so this is exercised mainly on the
  merge commits agents author while integrating.)
- **Conflict etiquette** — the exact sequence to detect, resolve, and verify a
  conflict in each mode, since conflict time is the cost you most want down. The
  briefs ask for union resolution and a higher-version tie-break; if agents get
  that wrong, `vcs` must teach the etiquette more explicitly.

Judge every change by the scoreboard, not by how it reads. If two rounds with a
change look the same as without, it's noise — drop it and keep `vcs` smaller.

## Convergence

Keep iterating until the [METRICS.md](METRICS.md) exit bar holds across **multiple
consecutive rounds, in both modes, across the difficulty ladder and across model
tiers** — low and still-improving (or stable-at-floor) wall-clock and conflict
time, quality holding or rising, mode detection never broken. Don't stop on a
single good round; one clean run can be luck.

## Sub-agent prompt template

Fill the brackets per cell. Keep it free of harness/test framing.

```text
You are a coding agent working in a software repository. Your version-control
guidance is the `vcs` skill: load it and follow it for every commit, merge,
rebase, and publish decision you make. Do not assume which version-control
system is in use — determine it as `vcs` instructs, before you start.

[Optional environment constraint, e.g.: You are operating in a fully-remote
cloud session; jj is not installed here. / You are on a local CLI with both
git and jj available.]

Your workspace is: <ABSOLUTE WORKSPACE PATH>. Work only there.

Your task:
<PASTE THE CONTENTS OF briefs/agent-K.md>

When done, report back exactly in this format:
<PASTE THE STRUCTURED REPORT TEMPLATE FROM METRICS.md>
```

The brief forbids writing code, adding tests, or running the app to "verify" —
the test is the integration and conflict resolution. It does **not** forbid the
end-of-integration **tidy-up** `vcs` calls for (deleting the merged branch/
bookmark); that step is part of a clean finish and is measured by the hygiene
metric, so leave room for it rather than telling the agent to stop the instant
its work hits `main`.
