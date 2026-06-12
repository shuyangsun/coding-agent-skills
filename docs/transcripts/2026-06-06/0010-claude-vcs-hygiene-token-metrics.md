<!-- markdownlint-disable MD013 MD024 -->

# Add branch/bookmark hygiene + token metrics to the vcs harness, then iterate the vcs skill

- **Date:** 2026-06-06
- **Repo:** coding-agent-skills (jj change `tsvvsyqq`, colocated jj-on-git)
- **Author:** Shuyang Sun <shuyangsun10@gmail.com>
- **Agent:** Claude Code (Opus 4.8, 1M context, effort: ultracode / xhigh)
- **Summary:** Added two new metrics to the `improving-vcs-skill` harness — branch/bookmark **stale-ref hygiene** and per-agent **output-token** efficiency — plus a branch-cleanup rule (with a PR carve-out) and a jj concurrent lost-update guard to the `vcs` skill itself, then ran a 12-round / 54-agent baseline→revised eval that drove the cleanup right. Hygiene went from a ref left for 5/6 baseline agents to 3/48 revised; correctness held (9/10, the one failure being a real jj clobber that was then fixed); tokens stayed flat. Results written to `docs/benchmarks/0001-...`.

---

## User

In the /improving-vcs-skill skill, is there a metric about stale Jujutsu bookmarks or local Git branches? I don't want them after the code has been committed, merged into main, and pushed. (If the branch maps to a remote PR, then obviously I want to keep it.)

## Assistant

Investigated the skill: read `METRICS.md`, `check-quality.sh`, the `scenario.py` oracle, and the `record-metrics.sh`/`scoreboard.sh` schema, and grepped the whole skill for cleanup verbs (`jj bookmark forget`, `git branch -d`, `abandon`, `prune`, `stale`).

**Answer: no such metric.** The harness measured speed, friction, and resolution-correctness only. The `agent-K` bookmarks/branches are deliberately created as inputs ("finished PRs") and nothing checks they're cleaned up; the throwaway sandboxes get torn down, so post-merge branch hygiene was simply out of scope — and there's no remote/PR concept to attach the "keep it if it has a PR" exception to. Noted that the cleanup behavior belongs in the `vcs` skill itself, and offered to add both the rule and a measuring check.

## User

I changed the improving VCS skill and the BCS skill itself. Yes, add these plus token usage as metrics for improvement, then iterate on the skill to improve metrics. Previous benchmark results were stored in @docs/benchmark

## Assistant

Read the user's committed changes (a `vcs` revision with `INTEGRATE.md` + harness eval runners) and the prior benchmark at `docs/benchmarks/0000-...`. Stated the design decisions up front:

- **Cleanup rule → `vcs`:** delete the merged `agent-K` (jj `bookmark delete`; git `switch --detach && branch -d`) unless a remote branch backs it.
- **Hygiene metric** kept separate from the correctness verdict (`STALE_REFS` + `HYGIENE` line), with a `--pr-backed` allowlist.
- **Token metric** via orchestrator measurement, not agent self-report.
- **PR carve-out** positively tested in git mode (real bare-origin remote); jj tests full cleanup.

Implemented across the skill + harness: added the cleanup rule and a PR carve-out to `skills/vcs/INTEGRATE.md` + `SKILL.md`; added `--pr-backed` to `new-sandbox.sh` (pushes the branch to the bare origin to model a PR head) and softened the integration brief so a skill-directed tidy-up isn't forbidden; added the stale-ref scan to `check-quality.sh` (per-agent `STALE_LIST`); extended `record-metrics.sh`/`scoreboard.sh`/`_score.py`/`METRICS.md` with `tokens` and `stale_refs` columns and exit-bar criteria.

**Dry-tested with no agents:** seeded git+jj sandboxes and simulated no-cleanup / correct-cleanup / over-deletion states — hygiene detection was exact in both modes, the PR-backed carve-out worked, and the real skill cleanup commands ran. Verified the `_score.py`→`scoreboard` chain and column rendering.

**Probed the token mechanism** with a tiny throwaway Workflow: `budget.spent()` deltas turned out to be **batched and mis-attributed per agent** (claimed 1578 output tokens for a call whose transcript showed 4). Pivoted the token metric to read exact `output_tokens` from each agent's transcript JSONL, mapped by the `ws-agent-K` path in its prompt — concurrency-independent — and reverted the runner serialization that the (failed) budget approach had required.

Ran the **baseline** (committed pre-cleanup `vcs`) vs **revised** medium rounds (both modes) as two background Workflows.

- Baseline: correctness PASS but **5 stale refs** left (R1 git 2, R2 jj 3).
- Revised: **stale → 0**, tokens flat — but R3's Opus agent deleted the PR-backed branch, reasoning _"a bare local remote isn't a real PR host."_ The metric caught it (`HYGIENE: FAIL — PR-backed ref wrongly deleted`).

Fixed the PR-exception to key on the checkable signal — "does a remote branch of that name exist? → keep it" — and to explicitly **not** judge whether the remote is "a real PR host."

## User

Once you're done with baseline, wait for 45 minutes before you run the next round. My token usage is high, about to reset in 35 minutes.

## Assistant

Persisted the timing constraint to a tracking file and held: let the running medium workflows finish and scored them (cheap, no new agents), but launched no new agent rounds.

Scored both arms: **baseline left a ref for 5/6 agents → revised 0** on the medium rounds, PR-backed fix confirmed. Made the PR-exception fix (non-agent edit). Then started a 45-minute background hold timer (with a `HOLD_UNTIL` timestamp for self-correction) before the next round.

## User

The usage was reset, you can remove the timer and continue.

## Assistant

Stopped the hold timer and ran **Stage 2** against the fixed `vcs`:

- Serialized R5 git/medium (PR-backed) + R6 jj/medium — R5 **kept** `agent-1` correctly (fix confirmed); R6 had one Haiku agent forget its jj bookmark delete (`stale=1`).
- Concurrent R7 git/hard + R8 jj/hard (6 agents each) — R7 clean (both Haiku cleaned up, PR kept); **R8 jj/hard FAILED correctness**: two Opus agents reported published but their work was clobbered off `main`.

Diagnosed R8 as a **jj concurrent lost-update**: `jj bookmark set main` has no rejection, so a stale advance silently overwrites a teammate — the git recipe's non-fast-forward retry loop had no jj equivalent. Added a guard (re-check your merge descends from the current `main` before advancing; re-form with `jj new main agent-K` if it moved), reordered the Finish to "check the remote first, then keep-or-delete," inlined the delete command into each recipe step, and dropped the risky "when in doubt, keep it" hedge.

Re-ran the two hardest cells (R9 git/hard, R10 jj/hard): **R9 clean; R10 correctness back to PASS** (clobber guard worked). R10 still had one Haiku jj miss; R11 surfaced a different edge — a Sonnet agent kept its bookmark, fooled by jj's `@git` colocated backend looking like a remote. Two more targeted fixes: recovery must **re-form** (`jj new main agent-K`), not `jj rebase` a bare merge (which drops a parent); and `@git` is **not** a remote (only `jj git remote list` entries count). Final round **R12 jj/hard came back fully clean** — `stale=0`, correctness PASS, all tiers cleaned up under `main` moving up to 5× under contention.

Compiled the 12-round dataset and wrote the benchmark to `docs/benchmarks/0001-vcs-skill-branch-hygiene-and-tokens.md`:

- **Hygiene:** baseline 5/6 agents → revised **3/48** (large 0/16, mid 1/16, small 2/16).
- **Correctness:** 9/10 revised rounds; the one failure (jj clobber) fixed and clean across the final three jj/hard rounds.
- **Tokens:** flat like-for-like (medium 4671 → 4413).

Saved a memory about the `budget.spent()` mis-attribution and the transcript-token workaround. Documented the honest residual (intermittent Haiku jj-bookmark miss, ~80% vs 100% in git) rather than chasing it on a single round. Left the changes uncommitted and offered to commit + export.

## User

Yes, export session transcript, then use JJ to commit and push.

## Assistant

Exported this transcript (the file you're reading), detecting jj mode via `jj root` per the `vcs` skill, then committed the work and the transcript as separate changes and pushed — following the `vcs` skill's own jj workflow.
