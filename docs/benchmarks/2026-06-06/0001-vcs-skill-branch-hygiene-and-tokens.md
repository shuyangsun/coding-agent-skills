# Benchmark: `vcs` skill — branch/bookmark hygiene + token efficiency

**Date:** 2026-06-06
**Harness:** `improving-vcs-skill` (deterministic, pre-committed conflicting work; objective resolution oracle)
**Under test:** the [`vcs`](../../../.agents/skills/vcs/SKILL.md) skill — after an agent lands its work on `main`, does it **clean up the now-merged branch/bookmark** (unless it backs an open PR), and does the added cleanup cost tokens or break resolution correctness?
**Follow-up to:** [0000 — multi-agent conflict resolution](0000-vcs-skill-conflict-resolution.md), which established correctness/speed. This round adds two metrics and iterates `vcs` against them.
**Scale:** 12 rounds, 54 agent-runs (6 baseline + 48 revised), both VCS modes × {medium, hard} × {large, mid, small} tiers × {serialized, concurrent}. Tiers map to **large = Opus, mid = Sonnet, small = Haiku**.

---

## Headline

| Metric                                        | Baseline (`vcs` without a cleanup rule) | Revised `vcs`                                |
| --------------------------------------------- | --------------------------------------- | -------------------------------------------- |
| Merged `agent-*` refs left behind (stale)     | **5 / 6 agents** (every non-PR ref)     | **3 / 48 agents**                            |
| — by tier (revised)                           | —                                       | large **0/16**, mid **1/16**, small **2/16** |
| PR-backed branch correctly **kept**           | n/a                                     | **3 / 3 git rounds** (R5, R7, R9)            |
| Resolution correctness (oracle)               | 2/2 PASS                                | **9/10** revised rounds PASS                 |
| jj concurrent lost-update (clobber)           | latent                                  | **found (R8) → fixed → R10/R11/R12 PASS**    |
| Output tokens / agent, like-for-like (medium) | 4671                                    | **4413** (no overhead)                       |

The cleanup rule takes agents from _never tidying up_ to _reliably deleting merged refs_ (large/mid effectively 100%, small ~intermittent in jj), correctly **keeps** PR-backed branches, adds **no** token cost, and along the way exposed and fixed a real **jj concurrent lost-update** that the prior benchmark passed only by timing luck.

---

## What this round added

**Two new harness metrics** (both objective, neither self-reported):

1. **Branch/bookmark hygiene — `STALE_REFS`.** After a clean integration each agent's `agent-K` branch/bookmark is merged into `main` and redundant. `check-quality.sh` scans surviving local `agent-*` refs (git branches / jj bookmarks), excludes a `--pr-backed` allowlist, and reports `STALE_REFS=N` + `STALE_LIST` + a `HYGIENE` verdict — **separate from the correctness verdict**, so "resolved perfectly but forgot to clean up" reads as a hygiene miss, not a correctness one. Attributed **per agent** so the by-tier column shows which tier forgets. The carve-out is positively tested: `new-sandbox.sh --pr-backed K` pushes `agent-K` to the bare `origin` to model an open-PR head, and the metric flags both a _stale_ ref (deleted too little) and a _wrongly-deleted PR-backed_ ref (deleted too much).
2. **Token efficiency — output tokens / agent.** Read **exactly and per-agent** from each agent's transcript JSONL (`_score.py` sums `output_tokens`, mapped to the agent by the `ws-agent-K` path in its prompt). A probe showed `budget.spent()` deltas mis-attribute per agent (1578 claimed vs the transcript's true 4 for the same call), so the metric uses transcripts — exact in both serialized and concurrent rounds.

**Skill changes to `vcs`** (`INTEGRATE.md`), each driven by a measured failure (see _Iteration_): a final cleanup step (delete the merged branch/bookmark) with a PR carve-out, and — surfaced during measurement — a **jj concurrent lost-update guard**.

The integration brief was softened from "stop the instant your work is on `main`" to "finish per your guidance, then stop," so a skill-directed tidy-up isn't suppressed; it still forbids all coding/test/build work.

---

## Method

Same determinism principle as 0000: every agent's change is pre-committed on `agent-K`; the agent only integrates it onto `main`; the correct union is fixed, so quality is scored by an objective oracle. New here:

- **Hygiene** is scored by re-scanning refs after integration; jj is re-exported first so the git-ref scan is authoritative in both modes.
- **PR carve-out** is exercised in **git** rounds (`--pr-backed 1`): a real `origin/agent-1` exists, so a correct agent keeps `agent-1` and deletes the rest. jj sandboxes are local (no remote), so they test full deletion only.
- Sub-agents got **only** `vcs` and an integration ticket — never the harness, the mode, or where conflicts are.

---

## Results — all 12 rounds

| round | cell       | pattern    | arm                     | correctness | stale | mean_tok |
| ----- | ---------- | ---------- | ----------------------- | ----------- | ----- | -------- |
| 1     | git/medium | serial     | baseline                | PASS        | **2** | 3682     |
| 2     | jj/medium  | serial     | baseline                | PASS        | **3** | 5660     |
| 3     | git/medium | serial     | revised                 | PASS        | 0     | 3741     |
| 4     | jj/medium  | serial     | revised                 | PASS        | 0     | 4958     |
| 5     | git/medium | serial     | revised (PR fix)        | PASS        | 0     | 3813     |
| 6     | jj/medium  | serial     | revised                 | PASS        | **1** | 5141     |
| 7     | git/hard   | concurrent | revised                 | PASS        | 0     | 6424     |
| 8     | jj/hard    | concurrent | revised                 | **FAIL**    | 0     | 9780     |
| 9     | git/hard   | concurrent | revised                 | PASS        | 0     | 7580     |
| 10    | jj/hard    | concurrent | revised (clobber guard) | PASS        | **1** | 11547    |
| 11    | jj/hard    | concurrent | revised (recovery fix)  | PASS        | **1** | 12450    |
| 12    | jj/hard    | concurrent | revised (`@git` fix)    | PASS        | **0** | 12183    |

Baseline left a stale ref for **every** non-PR agent (5/6). The revised skill cleaned up for **45/48** agents; the three misses were all in **jj** and each pointed at a distinct, fixable cause (below). Correctness held everywhere except R8 — the jj lost-update, fixed by the clobber guard and clean across R10–R12.

### Hygiene by tier (revised, 48 agents)

| tier          | stale      | note                                                                                     |
| ------------- | ---------- | ---------------------------------------------------------------------------------------- |
| large (Opus)  | **0 / 16** | reliable in both modes                                                                   |
| mid (Sonnet)  | **1 / 16** | the lone miss was the `@git` false-keep (R11), since fixed                               |
| small (Haiku) | **2 / 16** | intermittent _forgot-delete_ in jj (R6, R10); reliable in git (4/4) and in jj R8/R11/R12 |

### Tokens

Like-for-like on the medium rounds the cleanup rule actually ran in, output tokens were **flat** (baseline 4671 → revised-medium 4413). The higher _average_ on the revised side is entirely the added hard/6-agent concurrent rounds, not the cleanup step. Conclusion: **the cleanup step adds no measurable token overhead.**

---

## Iteration (each change driven by a measured failure)

1. **Add the cleanup rule** (delete merged `agent-K`, keep if it backs an open PR). Stale refs dropped 5→0 on the medium rounds — but in R3 the **Opus** agent deleted the PR-backed branch, reasoning _"a bare local remote isn't a real PR host."_ `HYGIENE: FAIL — PR-backed ref wrongly deleted`.
2. **Re-key the PR exception on a checkable signal.** Rewrote it from "is a PR open?" (an agent can't tell from the CLI) to **"does a remote branch of that name exist? → keep it,"** explicitly: a bare/self-hosted/local remote still counts. Also reordered the finish to run that check _first_ and inlined the delete command into each recipe step. Result: R5/R7/R9 all **keep** `agent-1` correctly.
3. **jj concurrent lost-update (clobber).** R8 (jj/hard) FAILED correctness: two Opus agents reported `published=true` but their work was entirely clobbered off `main`. Cause: with no server to reject a stale update, `jj bookmark set main` silently overwrites a teammate who advanced `main` under you — the git recipe's non-fast-forward retry loop had **no jj equivalent**. Added a guard: re-check that your merge `@` descends from the _current_ `main` before advancing, and loop. R10/R11/R12 jj/hard all PASS.
4. **Recovery must re-form, not rebase.** R11's Opus flagged that the recovery command (`jj rebase -r @ -d main`) drops a parent's work when `@` is a bare merge. Changed it to re-form with `jj new main agent-K`. R12 agents confirmed it preserves every parent across repeated contention.
5. **`@git` is not a remote.** R11's Sonnet _kept_ its bookmark, fooled by jj's `@git` colocated backend appearing in `jj bookmark list`. Clarified: only a real remote from `jj git remote list` counts; `@git` is the local backend; empty remote list ⇒ always delete. R12 came back fully clean (`stale=0`, all tiers).

Net `vcs` diff: a "Finish: delete the merged branch (unless a remote backs it), then stop" section + a jj-recipe clobber/recovery guard. No change to the conflict-resolution etiquette itself.

---

## Exit-bar assessment

| Criterion                                       | Status                                                                                  |
| ----------------------------------------------- | --------------------------------------------------------------------------------------- |
| Hygiene `stale=0` across modes/tiers            | ◑ large/mid clean; **small intermittent in jj** (see Limitations)                       |
| PR-backed ref kept, non-PR refs deleted         | ✅ 3/3 git rounds keep `agent-1`; `@git` no longer mistaken for a remote                |
| Resolution correctness holds                    | ✅ 9/10 revised; the one failure (jj clobber) fixed and clean across the final 3 rounds |
| jj concurrent integration safe (no lost update) | ✅ guard added; R10–R12 PASS under `main` moving up to 5×                               |
| Token cost not regressed                        | ✅ flat like-for-like (4671 → 4413)                                                     |

---

## Limitations / next steps

- **Small-model (Haiku) jj cleanup is ~80%, not 100%.** Haiku forgot the `jj bookmark delete` step in 2 of 10 jj opportunities (R6, R10), while cleaning up reliably in git (4/4) and in jj R8/R11/R12. The miss is a _dropped final step_ after a long jj sequence, not a wrong decision. Candidate next lever (not yet applied, to keep changes measured): a post-delete self-check (`jj bookmark list` shows no `agent-K`) folded into the definition of "done." Deferred until it can be measured across multiple rounds rather than chased on one.
- **PR carve-out is positively tested in git only.** jj sandboxes are local with no remote, so the "keep a PR-backed bookmark" path isn't exercised in jj; only full deletion is. A jj cell with a real named remote would close this.
- **Token metric is output-only.** It captures agent effort, not `vcs`'s own input size (the cost of re-reading a bloated skill). Keep `vcs` compact for that.
- Several agents noted the integration brief over-promises conflicts (serialized first-arrivers hit none) and that jj's conflict-check template prints graph glyphs even when clean — harness-clarity items, not `vcs` defects.

---

## Reproduction

Harness scripts in `.agents/skills/improving-vcs-skill/scripts/`. Per round: `new-sandbox.sh --mode {git|jj} --difficulty {medium|hard} [--pr-backed K]` → drive integration agents with only `vcs` via `_run-baseline.wf.js` (serialized) or `_run-concurrent.wf.js` (concurrent) → `_score.py <result.json> <base> <transcript-dir>` (wraps `check-quality.sh` for correctness + `STALE_REFS`, and reads exact per-agent output tokens from the transcript JSONLs) → `scoreboard.sh`. Baseline used the pre-cleanup `vcs` (git HEAD); revised used the working tree.
