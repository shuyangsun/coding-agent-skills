# The improvement loop

How to run one round, and how to decide what to change in `vcs` between rounds.
This is the heart of the skill: **iterate until the numbers meet the bar**, not
until the skill _reads_ well. A revision that doesn't move the measurements in
[METRICS.md](METRICS.md) — or that buys speed with botched merges — is not an
improvement; revert it.

## Per-round procedure

For **each** VCS mode (`git` and `jj`) — both run every round:

1. **Provision.** `bash <skill-dir>/scripts/new-sandbox.sh --mode <git|jj> --agents N`.
   It prints a manifest (and writes `manifest.env` / `manifest.txt` + `briefs/`).
   Note the per-agent workspace paths, the briefs, and the integration ref (`main`).
   See [SCENARIOS.md](SCENARIOS.md) for what the fixtures and briefs contain.

2. **Brief & spawn sub-agents — one per workspace, in parallel.** Each sub-agent
   stands in for an agent/tool × environment cell from [MATRIX.md](MATRIX.md). Give
   each sub-agent **only**:
   - the `vcs` skill (instruct it to load and follow `vcs` for all VCS decisions);
   - its task brief (`briefs/agent-K.md`) — a realistic ticket;
   - its workspace path, and the instruction to publish onto `main`.

   Withhold everything else. **Do not** reveal this harness, that it's a test,
   which VCS mode the repo is in, or where conflicts will be — detecting the mode
   and handling conflicts is exactly what `vcs` must make the agent do alone. The
   exact sub-agent prompt template is at the end of this file.

3. **Drive the collision.** The briefs already target overlapping files/lines, so
   conflicts arise naturally. Choose an integration pattern (escalate across
   rounds):
   - **Parallel work, serialized integration** (start here): all agents do their
     edits concurrently; they integrate onto `main` one after another, so each
     later agent meets the earlier ones' conflicts. Cleanest to measure.
   - **Fully parallel integration** (stress): agents also integrate concurrently,
     contending for `main`. Maximal pressure on `vcs`'s etiquette.

4. **Collect reports.** Each sub-agent returns the structured report defined in
   [METRICS.md](METRICS.md) (conflict-detection/resolution time, retries, stalls,
   round-trips, plus a short effectiveness narrative: what was clear, what was
   ambiguous, where it stalled, where a conflict was mishandled).

5. **Score objectively.** `bash <skill-dir>/scripts/check-quality.sh <round-dir>`.
   It is the source of truth for quality — it does not trust agent self-reports.
   PASS requires: mode integrity intact, no conflict markers on `main`, every
   agent's sentinel present (no lost/clobbered work), and no unresolved conflicts.

6. **Record + compare.** For each agent, `record-metrics.sh` the time/conflict/
   retry numbers and the quality verdict; then `scoreboard.sh` to see this round
   against prior rounds. The headline costs are **batch wall-clock** and, above
   all, **conflict-resolution time** — watch their round-over-round deltas.

7. **Diagnose, then revise `vcs`.** Read the narratives _through the lens of the
   numbers_: find what actually cost time or caused a `check-quality` failure
   (ambiguous mode detection, a missing rebase step, unclear conflict-resolution
   etiquette, a slow or absent helper script) and change `vcs` to fix that one
   thing. Keep edits small and attributable so the next round's numbers tell you
   whether they worked.

8. **Re-run & re-measure.** New round, fresh sandboxes (`new-sandbox.sh` auto-picks
   the next round number). Compare. **Keep** the revision if wall-clock and/or
   conflict time fell and quality held; **revert** it otherwise.

9. **Tear down** finished rounds with `rm-sandbox.sh <round-dir>` (or `--all` at
   the end). Sandboxes are disposable; the metrics log persists for comparison.

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
- **`COMMITS.md`** — refine the existing commit-message guidance, don't duplicate it.
- **Conflict etiquette** — the exact sequence to detect, resolve, and verify a
  conflict in each mode, since conflict time is the cost you most want down.

Judge every change by the scoreboard, not by how it reads. If two rounds with a
change look the same as without, it's noise — drop it and keep `vcs` smaller.

## Convergence

Keep iterating until the [METRICS.md](METRICS.md) exit bar holds across **multiple
consecutive rounds in both modes** — low and still-improving (or stable-at-floor)
wall-clock and conflict time, quality holding or rising, mode detection never
broken. Don't stop on a single good round; one clean run can be luck.

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
