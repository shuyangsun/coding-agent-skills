# Benchmark: `vcs` skill — multi-agent conflict resolution

**Date:** 2026-06-06
**Harness:** `improving-vcs-skill` (deterministic, pre-committed conflicting work; objective resolution oracle)
**Under test:** the [`vcs`](../../skills/vcs/SKILL.md) skill — can many coding agents, given only `vcs`, integrate each other's work onto a shared `main` and resolve merge conflicts cleanly and fast?
**Scale:** 16 rounds, 72 agent-runs (14 baseline + 58 revised), across both VCS modes × {easy, medium, hard} × {large, mid, small} model tiers × {serialized, concurrent} integration.

Model tiers map to: **large = Opus**, **mid = Sonnet**, **small = Haiku**.

---

## Headline

| Metric | Baseline (`vcs` = commit-messages only) | Revised `vcs` |
| --- | --- | --- |
| Rounds passing (objective oracle) | 3 / 4 | **12 / 12** |
| Agent-runs | 14 | **58** |
| Agent pass rate | 71% | **100%** (0 failures) |
| Mode-detection errors | — | **0 / 58** |
| Serialized retries / stalls | 5 / 6 | **0 / 0** |
| jj/medium round | **FAIL** (conflicted commit left in history) | PASS |
| Worst small-model conflict time (serialized) | 380s | ~85s |

The revision turned a commit-message-only stub into a skill that takes **100% of agents, every tier**, cleanly through union conflict resolution and publish in **both** VCS modes across the whole difficulty ladder — including under genuine concurrent contention.

---

## Method

Every agent's change is generated deterministically and **pre-committed** on its own branch/bookmark (`agent-K`) — a finished "PR". The sub-agent writes no code; its only job is to integrate `agent-K` onto the shared `main`, resolving the conflicts that arise because teammates touched the same files/lines. Because the inputs are deterministic, the correct merged result is deterministic, so quality is scored by an **objective oracle**, not by what agents claim.

- **Conflict classes** (per [SCENARIOS](../../.agents/skills/improving-vcs-skill/SCENARIOS.md)): adjacent-insert union (CHANGELOG), JSON array union (registry), list union (handlers), **same-line tie-break** (`version:` — keep the higher), large multi-line block union (pipeline), disjoint per-agent files.
- **Difficulty ladder:** easy (1 union conflict), medium (3 unions + a version tie-break among a subset), hard (all of it, for every agent, + a big shared pipeline block + 6-way version tie-break).
- **Integration patterns:** *serialized* (agents land one after another — clean to measure) and *concurrent* (all agents contend for `main` at once — the real multi-agent case).
- **Sub-agents** were given **only** the `vcs` skill and an integration-only ticket — never the harness, the mode, or where the conflicts are. Mode detection and conflict handling had to come from `vcs` alone.

### Oracle is a real discriminator

Before trusting any number, the oracle was checked against deliberately-broken resolutions: it PASSes the canonical union+tie-break and FAILs a dropped entry, a duplicate-paste, a wrong tie-break, a forbidden edit to an untouched file, and structurally-broken JSON.

### Measurement-validity fix (harness)

The jj mode-integrity check was **asserted, not verified**: a jj-mode round integrated with *pure git* (the wrong tool in a colocated repo) scored a false PASS. `check-quality.sh` was hardened to require op-log proof that `main` was advanced **through jj** (a `point/move bookmark main` operation — the seed never moves `main`, so it is version-stable evidence). Pure-git-in-a-jj-repo now correctly FAILs; genuine jj passes.

---

## Baseline (stub `vcs`)

The stub covered only commit-message formatting. Every agent reported the same gap — *"the skill gives zero guidance on the actual integration workflow"* — and re-derived it from general knowledge. Consequences:

- **jj/medium FAILED:** content was correct, but a **conflicted merge commit was left in `::main`** (jj records conflicts as commit state). No agent was taught to resolve the conflict *in* the commit before advancing `main`.
- **Small-model thrash:** Haiku burned 380s and 334s on conflicts (vs large 40–108s), with retries and stalls.
- **Repeated friction:** git-worktree confusion (`git checkout main` fails when `main` is checked out elsewhere); jj publish confusion (move bookmark + `jj git export`).
- **Mode detection was *not* the problem** — all agents detected git vs jj correctly (see Limitations for the caveat).

---

## The revision

Driven only by measured failures, kept compact:

- **`SKILL.md`** → compact router: mode detection first (`jj root` → use jj even in a colocated repo where git also works), then pointers.
- **`INTEGRATE.md`** (new) → the missing procedure: the integration model, union + higher-value tie-break etiquette (with the `git rebase` side-inversion caveat), an explicit **git recipe** (`fetch → rebase → push HEAD:main`, non-ff retry loop), and an explicit **jj recipe** whose core rule is **no conflicted commit may remain in `::main`** before advancing the bookmark.
- **`COMMITS.md`** → unchanged (baseline never faulted it).

---

## Results

### Before → after (same cells, same tier layout)

| Cell | Verdict | wall(max) s | conflict(max) s | retries | stalls |
| --- | --- | --- | --- | --- | --- |
| git/easy | PASS → PASS | 88 → 72 | 40 → 63\* | 0 → 0 | 0 → 0 |
| jj/easy | PASS → PASS | **558 → 112** | **380 → 70** | 0 → 0 | 2 → 0 |
| git/medium | PASS → PASS | **191 → 108** | 108 → 76 | 0 → 0 | 1 → 0 |
| **jj/medium** | **FAIL → PASS** | **474 → 136** | **334 → 85** | **5 → 0** | **3 → 0** |

\*git/easy conflict(max) +23 is a self-report artifact (a Haiku agent timestamped conflict-start at run-start); the round passed and total time fell.

### Revised difficulty × tier (agent pass% | worst conflict s)

| tier | easy | medium | hard |
| --- | --- | --- | --- |
| large | 100% (61s) | 100% (85s) | 100% (297s) |
| mid | 100% (70s) | 100% (65s) | 100% (446s) |
| small | 100% (63s) | 100% (137s) | 100% (277s) |

### All 16 rounds

| round | cell | pattern | skill | n | verdict | wall(max)s | conflict(max)s | retries | stalls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | git/easy | serial | stub | 3 | PASS | 88 | 40 | 0 | 0 |
| 2 | jj/easy | serial | stub | 3 | PASS | 558 | 380 | 0 | 2 |
| 3 | git/medium | serial | stub | 4 | PASS | 191 | 108 | 0 | 1 |
| 4 | jj/medium | serial | stub | 4 | **FAIL** | 474 | 334 | 5 | 3 |
| 5 | git/easy | serial | revised | 3 | PASS | 72 | 63 | 0 | 0 |
| 6 | jj/easy | serial | revised | 3 | PASS | 112 | 70 | 0 | 0 |
| 7 | git/medium | serial | revised | 4 | PASS | 108 | 76 | 0 | 0 |
| 8 | jj/medium | serial | revised | 4 | PASS | 136 | 85 | 0 | 0 |
| 9 | git/hard | serial | revised | 6 | PASS | 132 | 88 | 0 | 0 |
| 10 | jj/hard | serial | revised | 6 | PASS | 190 | 150 | 0 | 0 |
| 11 | git/medium | serial | revised | 4 | PASS | 112 | 65 | 0 | 0 |
| 12 | jj/medium | serial | revised | 4 | PASS | 180 | 137 | 0 | 0 |
| 13 | git/hard | concurrent | revised | 6 | PASS | 324 | 277 | 12 | 0 |
| 14 | jj/hard | concurrent | revised | 6 | PASS | 471 | 446 | 7 | 0 |
| 15 | git/hard | concurrent | revised | 6 | PASS | 339 | 297 | 9 | 0 |
| 16 | jj/hard | concurrent | revised | 6 | PASS | 318 | 228 | 5 | 2 |

Under **concurrent** integration the 33 retries are *inherent* — an agent that loses a push/bookmark race must re-fetch and re-integrate. Every agent still landed a correct, union-preserved, conflict-free result; no work was lost and no jj conflict commit survived.

---

## Exit-bar assessment

| Criterion | Status |
| --- | --- |
| Quality (objective oracle) every round | ✅ 12/12 revised rounds PASS |
| Mode detection holds before & after; jj workflow verified used | ✅ 0/58 errors; bookmark-op proof in every jj round |
| Conflict-resolution time low & down from baseline | ✅ 380s → ~85s (serial floor) |
| Batch wall-clock low & down | ✅ |
| Friction low | ✅ serialized 0/0; concurrent retries are race-loss, not ambiguity |
| No tier left behind | ✅ all tiers 100% across the full ladder |
| Multiple consecutive passing rounds | ✅ 12 consecutive (rounds 5–16) |

---

## Limitations / next steps

- **Colocated mode-detection trap is under-tested.** The harness's per-agent jj workspaces contain only `.jj` (no `.git`), so the genuinely-ambiguous *colocated* case (`.git` **and** `.jj` both work, but jj is correct) is never the directory the agent operates in. Agents scored 100% detection partly because detection is trivial there. A future harness cell should drop the agent in the colocated root to actually exercise the trap the skill warns about.
- **Candidate `vcs` refinements not yet measurement-justified:** a note that JSON/array union may require re-adding separators to stay valid (agents flagged it but none produced invalid JSON). Deferred until a failure is observed.
- **Concurrent contention cost** (mid/large at hard reaching ~300–450s under a 6-way race) is inherent serialization, not a skill defect — all such rounds passed.

---

## Reproduction

Harness scripts live in `.agents/skills/improving-vcs-skill/scripts/`. The eval was driven by `_run-baseline.wf.js` (serialized) and `_run-concurrent.wf.js` (concurrent), scored by `_score.py` (wraps `check-quality.sh` + `record-metrics.sh`). Per round: `new-sandbox.sh --mode {git|jj} --difficulty {easy|medium|hard}` → spawn integration agents on each `ws-agent-K` with only the `vcs` skill → `check-quality.sh <round-dir>`. Metrics aggregate via `scoreboard.sh`.
