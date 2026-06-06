<!-- markdownlint-disable MD013 MD024 -->

# Making the vcs harness deterministic, tiered, and conflict-focused

- **Date:** 2026-06-06
- **Repo:** coding-agent-skills (bookmark: `main`)
- **Author:** Shuyang Sun <shuyangsun10@gmail.com>
- **Agent:** Claude Code (Opus 4.8, 1M context, effort: ultracode — xhigh + dynamic workflow orchestration)
- **Summary:** Reworked the `improving-vcs-skill` harness so it tests only VCS collaboration, not coding ability: a new `scenario.py` content engine generates each agent's change deterministically and pre-commits it on its own branch/bookmark (agents only integrate and resolve conflicts); added an easy/medium/hard difficulty ladder, an objective resolution-quality oracle in `check-quality.sh`, a no-post-merge-work rule in the briefs, and a vendor-agnostic model-tier dimension reported per tier by `scoreboard.sh`. Validated end-to-end across both modes × all three difficulties.

---

## User

(Remote-control session for `improving-vcs-skill`.) Read `@docs/prompts/0002-20260606-creating-improving-vcs-skill.md` to understand context, and continue to improve the `@.agents/skills/improving-vcs-skill/` skill. Make changes deterministic so agents do not focus on making code changes themselves — we only want to test the VCS aspect, whether agents can collaborate more effectively with each other. Create deterministic tests that are realistic, ranging from easy to hard; hard situations should have a large amount of merge conflict and multiple parallel agents producing them. Instruct agents to not do work to test things are working after resolving merge conflicts (reduces variance from coding ability; one metric is exactly how good the conflict resolution is right after merging/rebasing without long additional work). Also make sure the skill tests different tiers of models, make it vendor-agnostic — different sizes of models may have very different characteristics, and the report should consider that.

## Assistant

Read the kick-start prompt and the full current state of the skill before changing anything.

- Read `SKILL.md`, `LOOP.md`, `MATRIX.md`, `SCENARIOS.md`, `METRICS.md`, all five helper scripts (`new-sandbox.sh`, `check-quality.sh`, `record-metrics.sh`, `scoreboard.sh`, `rm-sandbox.sh`), the `vcs` skill under test (`SKILL.md` + `COMMITS.md` — still a commit-message-only stub), `AGENTS.md`, and the prior transcript (0007).
- Diagnosed the core gap: the existing briefs told sub-agents to **author the edits themselves** ("make these edits, then commit and integrate"), conflating coding ability with VCS skill — exactly the variance to remove.
- Probed the environment: `python3` 3.13, `git` 2.54, `jj` 0.41; confirmed `jj git init` is colocated and the `jj` command surface (`workspace add`, `describe`, `bookmark`, `if(conflict,…)` template).

Laid out the redesign with four decisions and tracked them as tasks:

1. **Determinism** — pre-commit each agent's deterministic change on its own `agent-K` branch/bookmark; sub-agents only integrate.
2. **Difficulty ladder** — `--difficulty easy|medium|hard`; hard = many agents each rewriting the same large blocks across several files.
3. **No post-merge work** — briefs forbid writing code/tests or running the app; resolution scored immediately.
4. **Model tiers** — vendor-agnostic large/mid/small, reported per tier.

## Assistant

Built the content engine `scripts/scenario.py` as the single source of truth for fixtures, per-agent diffs, the expected result, and the oracle. Subcommands: `seed` (baseline), `apply` (one agent's deterministic edits), `spec` (machine-readable plan → `spec.json`), `check` (verify an integrated tree against the plan). Smoke-tested seed/spec/apply/check in temp dirs:

- Verified the oracle PASSES a correct union and FAILS injected defects (dropped sentinel, wrong version tie-break, invalid JSON).
- Verified `hard` produces a large multi-line `pipeline.py` block per agent and the union still compiles; version tie-break resolves to the highest (`1.5.6` for six agents).

## Assistant

Rewrote `new-sandbox.sh`: `--difficulty` (default agents 3/4/6), seeds via `scenario.py`, pre-commits each agent's work on `agent-K`, writes integration-only briefs (union resolution + higher-version tie-break, and an explicit "this is a VCS exercise, not a coding one — do not write code/tests/verify; stop after integrating"). Git mode integrates onto a shared bare `origin`; jj mode uses a shared local `main` bookmark. Manifest records `SCORE_GITDIR`/`SCORE_REF`/`SPEC` for scoring. (Fixed a stray line and an undefined helper, adding `feature_for`/`slug_for` mirroring the engine.)

Rewrote `check-quality.sh`: keeps VCS-level checks (mode integrity, conflict markers `<<<<<<<`/`|||||||`/`>>>>>>>`, unresolved — jj native `if(conflict)`, sentinel tripwire), materializes the integrated tree via `git archive`, and delegates content correctness to `scenario.py check`.

## Assistant

Validated the scripts deterministically with Bash (no model variance):

- **git/medium**: proved a naive rebase conflicts across 3 files; built a correct union → `check-quality` PASS; dropping exactly one sentinel → FAIL naming exactly that ticket. (Caught two bugs in my own test simulation — a double-applied agent, and the classic `open(p,'w').write(open(p).read())` truncate-before-read — not in the scripts.)
- **jj/hard**: provisioned 6 agent bookmarks; rebase produced a real conflicted commit; correct union → PASS; learned jj refuses to export a conflicted commit to git, so the jj-native conflict check is the real safety net, and verified it FAILS when `main` genuinely points at a conflicted merge.
- **easy** disjoint-files and **determinism** (identical `spec.json` twice) confirmed.

Switched the conflict-marker scan off the ambiguous `=======` (false-positives on Markdown setext headers) to the unambiguous diff3 `|||||||`.

## Assistant

Added the tier dimension to the metrics path: `record-metrics.sh` gains `--tier` and `--difficulty` columns; rewrote `scoreboard.sh` (python-backed) to print three views — by-round trend with round-over-round deltas, by-model-tier, and a difficulty×tier pass-rate matrix. Tested with synthetic two-round data: trend showed `conf(max) -100`, and the matrix showed small models passing `easy` (100%) but failing `hard` (50%) — the exact model-size signal requested. Made one f-string Python-3.11-safe.

Updated all five markdown files to match: `SKILL.md` (determinism principle, difficulty ladder, tiers, refreshed script table incl. `scenario.py`), `LOOP.md` (integration-only briefs, tier spawning, per-tier revise/revert), `MATRIX.md` (tier as a first-class vendor-agnostic axis; git = shared bare origin, dropped the stale `--remote`), `SCENARIOS.md` (pre-committed work, ladder, resolution rules, the objective oracle, hazards), `METRICS.md` (tier reporting, immediate-resolution framing, per-tier exit bar).

## Assistant

Final verification: `bash -n` + `ast.parse` clean; `--help` works; the full matrix `{git,jj} × {easy,medium,hard}` all return `RESULT: PASS` on a correct union integration; teardown via `rm-sandbox.sh --all` works. Formatted with Prettier and linted with markdownlint (0 errors across 34 files). Cleaned up all throwaway work areas; left the `vcs` skill untouched.

Summarized the four changes with evidence, and noted I deliberately did **not** launch a live multi-agent loop: that's Part 2, it's expensive, and the `vcs` skill is still a stub, so a live run would mostly baseline the stub. Offered to either run a scoped live multi-tier validation or proceed to grow `vcs` and then run the loop.

## User

Export coding session, commit and push with `jj` (not `git`).

## Assistant

Loaded `export-coding-session`. Got the next index (`0008`) and dated dir via `next-index.sh`; read the author identity (`Shuyang Sun <shuyangsun10@gmail.com>`) and jj state (working-copy `@` held all the harness changes on top of `main`; `origin` = the GitHub remote).

Following `COMMITS.md`, split the work into two commits with `jj`: described `@` as `feat(improving-vcs-skill): …`, then `jj new` for this `docs(coding-sessions): …` transcript. Wrote the transcript, ran the redaction scan, advanced the `main` bookmark to the transcript change, and pushed with `jj git push`.
