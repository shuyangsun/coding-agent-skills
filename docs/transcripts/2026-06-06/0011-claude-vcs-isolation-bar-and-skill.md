<!-- markdownlint-disable MD013 MD024 -->

# Add a session-start isolation measurable bar to the harness, then teach the vcs skill to isolate parallel work

- **Date:** 2026-06-06
- **Repo:** coding-agent-skills (jj change `rsxwxtnm`, colocated jj-on-git)
- **Author:** Shuyang Sun <shuyangsun10@gmail.com>
- **Agent:** Claude Code (Opus 4.8, 1M context, effort: ultracode / xhigh)
- **Summary:** Established that the `vcs` skill had no session-start isolation guidance and the `improving-vcs-skill` harness couldn't measure it; added a new `--task start` measurable bar (deterministic greenfield scenario + `check-isolation.sh` oracle scoring git-reflog / jj-op-log durable signals + an `iso` scoreboard column + exit-bar criterion), dry-tested it across 8 simulated agent behaviors and adversarially reviewed it (false-pass refuted); then changed the `vcs` skill itself — a new `ISOLATE.md` (create your own worktree/workspace before new work unless already isolated, with the technically-grounded "already in a git worktree + jj available" judgement case) wired into `SKILL.md` and the `INTEGRATE.md` cleanup.

---

## User

(Continued from a compacted session that had just finished adding branch/bookmark stale-ref hygiene + token metrics to the harness and committed/pushed them.)

Does the VCS skill instruct the agent to create a new JJ workspace before starting new work? Does it only do that when it's currently on the main Git branch, or does it do that even if it's in a Git worktree?

## Assistant

Read the whole `vcs` skill — `SKILL.md`, `INTEGRATE.md`, `COMMITS.md` — plus the harness `LOOP.md`.

**Answer: no.** The skill never tells the agent to create a jj workspace (or git worktree) before new work, so the "only on main vs even in a worktree" conditional doesn't apply — there's no workspace-creation instruction to gate. The skill is scoped to landing already-committed work: `INTEGRATE.md` opens with "You have a finished change on your branch/bookmark." The only `jj workspace` mention anywhere is the reactive `jj workspace update-stale`; worktrees come up only to warn off `git checkout main` and to `git switch --detach` before deleting a merged branch. Noted that the harness's own `LOOP.md` lists "new workspace/worktree…" as a _wished-for_ helper it doesn't yet have — i.e. a recognized gap. Flagged that in jj the "on the main branch" framing doesn't map cleanly (jj has no checked-out-branch concept). Offered to add a session-start section.

## User

Does that make sense for my end goal? Multiple agents working on things together without interfering each other.

## Assistant

Reasoned through it rather than jumping to code. Separated two kinds of "interference":

1. **Development-time (filesystem):** two agents in the _same_ working directory trample each other — fixed by a per-agent worktree (git) / workspace (jj). The right primitive. **But** creating it is usually the _orchestrator's_ job (naming coordination, lifecycle/teardown, avoiding double-isolation) — the harness itself already provisions workspaces and hands agents a path.
2. **Publish-time (history):** even with isolated working copies, concurrent publishes collide on `main` — the lost-update/clobber already hardened last session. Isolation at the start buys nothing here.

Takeaway: "no interference" = isolated start **+** disciplined integration; workspaces are mostly an orchestration concern, and the genuinely per-agent etiquette that belongs in `vcs` is the conditional "don't develop directly on shared `main`; if you're not already isolated, isolate first." Asked which deployment model they target (co-located processes vs separate clones), since it changes the design.

## User

Mainly co-located processes on one machine. Add these to the harness as a measurable bar only for now, I'll use the improving-vcs-skill skill to iteratively improve the VCS skill later.

## Assistant

Built the measurable bar; left the `vcs` skill untouched (per "measurement only").

**Probed the durable signals first** (don't guess what you'll measure): seeded scratch git + jj repos and confirmed — git's primary `HEAD` reflog (`.git/logs/HEAD`) stays at the seed line-count through `worktree add` + commit-in-worktree + push + worktree removal + `branch -d`, but grows on both non-isolation modes (commit on primary `main`; `switch -c` in primary); jj's op log records `add workspace '<name>'` append-only (the seed only ever adds `default`), surviving `workspace forget`. Worktree detection: `git rev-parse --git-dir != --git-common-dir`.

**Implemented across the harness:**

- `scenario.py`: a `start-instructions` subcommand printing the exact, mechanical one-edit work (the `easy` CHANGELOG line + notes file) so the brief embeds it verbatim — zero coding judgment, scored by the existing `easy` oracle (single source of truth).
- `new-sandbox.sh`: `--task start` (single-agent, difficulty pinned to `easy`) + `--start-from main|worktree`; a greenfield shared-repo scenario, a start brief, and durable baselines in the manifest (`SEED_HEAD_LINES`, `SEED_WS`, `GIVEN_WS`). The existing `--task integrate` path left behaviorally unchanged.
- `check-isolation.sh` (new): scores `ISOLATED=pass/fail` (+ `ISO_FS` / `OVER_ISOLATE` / `WORK_LANDED`) per mode × arm, **separate** from correctness and hygiene.
- `record-metrics.sh` `--isolate`, an `iso` column in `scoreboard.sh` (want 0; `-` on integration rounds), `_score.py` runs both oracles, plus a `_run-start.wf.js` runner and the docs (`METRICS.md` exit-bar criterion, `SCENARIOS.md`, `LOOP.md`, `MATRIX.md`, `SKILL.md`).

**Validated end-to-end with no agents:** simulated 8 agent behaviors (git/jj × main/worktree × isolated/not) — the oracle scored every one exactly right, composing with `check-quality.sh` so isolation, correctness, and cleanup stay independent. Ran `_score.py` over the 8 real sandboxes via a synthetic result.json; the scoreboard `iso` column populated correctly. Confirmed the integration path still provisions 6 pre-committed agent worktrees with `TASK=integrate`. Cleaned up scratch dirs.

**Adversarially reviewed it** with a background workflow (10 agents, 4 lenses — false-pass, false-fail, shell/portability, docs/determinism — each high/critical finding independently verified). The dangerous **false-pass** was refuted twice empirically (`git gc`/reflog-expire clears the reflog to _0_, not the seed count, so the check still fails; the live worktree count catches branchless extra worktrees). Folded in the real, cheap items: a comment documenting that the reflog signal intentionally flags only HEAD-mutating ops in the shared checkout (so `fetch`-then-`worktree add` scores pass), a defensive `2>/dev/null`, and a pre-existing `tier` doc clarification. Reported the bar built + validated, and that it starts red by design (no `vcs` isolation rule yet).

## User

Change the VCS skill to add new `jj` workspace or new Git worktree when it's deployed on local machine that's not running in a new Git worktree (sometimes that's the default behavior of the agentic coding tool). If it's already in a Git worktree, and Jujutsu is available, use your best judgement to instruct the agent to do something to achieve the same goal (parallel agent workflow and cleanup afterwards).

## Assistant

Before writing the judgement case, **probed the colocation reality**: created a colocated jj repo, added a git worktree, and confirmed the worktree has **no `.jj`** — `jj root`/`jj status` fail there ("There is no jj repo"), so jj genuinely cannot operate from inside a plain git worktree. Also confirmed the `--git-dir != --git-common-dir` worktree-detection signal.

**Changed the `vcs` skill:**

- New **`ISOLATE.md`**: isolate before new work unless already isolated. Git — primary checkout → `git worktree add`; already in a linked worktree → work on your own branch in place. jj — shared `default` workspace → `jj workspace add`; own workspace → work in place. The **judgement case** (already in a git worktree _and_ jj available), grounded in the probe: a git worktree of a colocated repo has no `.jj` so don't force jj there — either use git in the worktree you're in (you're already isolated) or step back to the main repo and `jj workspace add`; the goal is filesystem-isolated, cleanly-removable work, not a specific command. Scoped to the local co-located case; cloud/PR sessions skip it.
- `SKILL.md`: new §2 "Starting new work? Isolate first" pointing to `ISOLATE.md` (renumbered Land→3, Commit→4); description updated.
- `INTEGRATE.md` Finish: remove the worktree/workspace _you_ created (leave a tool-provided one for the tool), alongside deleting the merged branch/bookmark.

Did not touch the conflict-resolution etiquette. Ran Prettier (the repo's formatter of record) on the touched markdown — it normalized emphasis to `_underscore_` and re-aligned tables — and confirmed markdownlint reports 0 errors. Removed a stray `scripts/repo/` test artifact. Reported the change with the decision table and the technically-grounded judgement case, and offered to validate via the harness (cost-aware) and to commit.

## User

Export session history since last compact command, then commit and push.

## Assistant

Exported this transcript (index 0011), then committed the work and pushed via jj following the `vcs` skill's own workflow — the harness changes (isolation bar + review hardening) and the `vcs` skill change as separate commits, plus this transcript as its own `docs(coding-sessions)` change.
