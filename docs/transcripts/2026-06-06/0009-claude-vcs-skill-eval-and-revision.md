---
title: "Baselining and revising the vcs skill to the exit bar"
date: 2026-06-06
repo: "coding-agent-skills (bookmark: `main`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Opus 4.8, 1M context, effort: ultracode — xhigh + dynamic workflow orchestration)"
summary: >-
  Ran the `improving-vcs-skill` measurement loop end-to-end against the `vcs` skill. First
  proved the harness measures real resolution quality and fixed a measurement-validity gap
  (jj mode-integrity was asserted, not verified — a jj round integrated with pure git
  scored a false PASS; hardened `check-quality.sh` to require op-log proof that `main`
  advanced through jj). Established a baseline (stub `vcs` = commit-messages only): 71%
  pass, one outright jj/medium FAIL (conflicted commit left in jj history), and
  small-model conflict thrash to 380s. Diagnosed the real gaps as jj conflict hygiene +
  missing integrate/publish procedure + small-model thrash (not mode detection). Rewrote
  `SKILL.md` as a compact router and added `INTEGRATE.md` (per-mode integrate-and-resolve
  recipes). Re-measured across 12 revised rounds / 58 agents in both modes ×
  easy/medium/hard × large/mid/small tiers × serialized and concurrent integration: 100%
  pass, 0 mode-detection errors, 0 serialized retries/stalls, jj/medium FAIL→PASS, worst
  small-model conflict 380s→~85s. Saved a benchmark report and exported this session.
---

<!-- markdownlint-disable MD013 MD024 -->

# Baselining and revising the vcs skill to the exit bar

## User

(`/effort ultracode`, `/remote-control vcs-skill`)

Use the /improving-vcs-skill to iteratively work on the /vcs skill, so multiple parallel coding agents can collaborate effectively under the given environment. Run a baseline eval first to make sure the skill is actually solving real problems, not imaginary ones.

## Assistant

Loaded the `improving-vcs-skill` meta-skill and read its full surface — `LOOP.md`, `METRICS.md`, `MATRIX.md`, `SCENARIOS.md`, and every script (`new-sandbox.sh`, `check-quality.sh`, `scenario.py`, `record-metrics.sh`, `scoreboard.sh`, `rm-sandbox.sh`) — plus the target `vcs` skill (`SKILL.md` + `COMMITS.md`). Found `vcs` was a **stub covering only commit-message formatting**. Confirmed the environment: git 2.54, jj 0.41, python3.13.

Set up task tracking and made the first move the user's actual concern — _is the harness measuring real problems?_ Provisioned `git/medium` and `jj/medium` sandboxes and verified the resolution oracle is a genuine discriminator: built the canonical correct union+tie-break tree (PASS) and five deliberately-broken trees — dropped entry, duplicate-paste, wrong tie-break (kept lower version), forbidden edit to an untouched file, broken JSON — and confirmed the oracle **FAILs every defect class**.

Then probed a suspected hole: integrated a **jj-mode** sandbox using **pure git** (the wrong tool in a colocated repo). The jj op-count was unchanged, proving jj was never used — yet `check-quality.sh` returned a clean **PASS**. The harness asserted invariant #2 ("a jj agent must use jj throughout") but never verified it — exactly the "imaginary success" the user warned about.

## Assistant

Empirically compared op logs: a pure-git integration leaves only `import/export/snapshot` ops, while a genuine jj integration leaves `rebase`/`squash`/**`point bookmark main`** ops. Since the seed creates `main` once but never moves it, a `(point|move) bookmark main` op is version-stable proof jj advanced `main`. Hardened `check-quality.sh` with a jj-workflow-integrity check requiring that proof. Validated: the pure-git-in-jj round now **FAILs** ("not integrated through jj"); a genuine jj integration is recognized ("main advanced through jj").

Validated `check-quality.sh` end-to-end on a real serialized git merge (PASS), then built a faithful Workflow harness: each sub-agent is spawned at a model tier (opus=large, sonnet=mid, haiku=small), reads **only** the `vcs` skill + an integration-only brief + its workspace path, detects the mode itself, integrates, and returns a structured report (mode, timings, retries, stalls, narrative). Smoke-tested 2 agents serialized (sonnet then haiku) on a throwaway `git/easy` round — both integrated and published correctly; check-quality confirmed the union and flagged the deliberately-skipped third agent. (Discovered the Workflow tool delivers `args` as a JSON string — added a `JSON.parse` guard.)

Launched the baseline: rounds 1–4 = git/easy, jj/easy, git/medium, jj/medium, 14 agents spread across tiers, serialized within each round.

## User

Is Opus still working on the baseline?

## Assistant

Checked the live journal: yes — 8/14 agents done, three of four rounds content-complete on `main`, only round-3's last agent still integrating.

## User

Is the agent stuck? Why hasn't it finished yet? Kill it if it's stuck on something.

## Assistant

Confirmed **not stuck** — actively progressing (8→12 done between checks). One agent's transcript was 481 KB (3–4× the others) and still being written every 1–3 seconds: a small/Haiku model _thrashing_ on a hard case because the stub skill gave it no conflict procedure — itself a baseline signal. Ran a bounded watch; the heavy agent finished and the final agent drained out. No kill needed (killing would have discarded 12/14 results, and resume-from-cache was available anyway).

## Assistant

Baseline completed (14 agents). Scored every round objectively and recorded per-agent metrics:

- round 1 git/easy → **PASS** (clean, ~87s)
- round 2 jj/easy → **PASS** but Haiku thrashed 558s/380s conflict
- round 3 git/medium → **PASS** (repeated git-worktree-checkout stalls)
- round 4 jj/medium → **FAIL** — content was actually correct (union + tie-break 1.5.3 all green) but a **conflicted merge commit was left in `::main`** (the "jj commits conflicts" hazard); Haiku 474s/334s with 5 retries

Diagnosis: the real problems are **jj conflict hygiene**, the **missing integrate/publish procedure** (every agent said the skill only covers commit messages and re-derived the workflow), and **small-model thrash** — _not_ mode detection (all 14 agents detected mode correctly). Marked the baseline finding that the harness's per-agent jj workspaces are pure-`.jj`, so the colocated trap isn't actually exercised.

## Assistant

Revised `vcs`, each change attributable to a measured failure:

- `SKILL.md` → compact router: mode detection first (`jj root` → use jj even in a colocated repo), then pointers.
- `INTEGRATE.md` (new) → the integration model, union + higher-value tie-break etiquette, an explicit **git recipe** (`fetch → rebase → push HEAD:main`, non-ff retry loop — fixes the worktree stalls), and an explicit **jj recipe** whose core rule is **no conflicted commit may remain in `::main`** before advancing the bookmark (fixes round-4).

Validated the jj recipe by hand on a throwaway sandbox (clean PASS: no conflicted commit, correct union + tie-break). Re-ran the same four cells as rounds 5–8. Result, same cells/tiers:

- jj/easy: wall 558→112, conflict **380→70**
- git/medium: wall 191→108
- jj/medium: **FAIL→PASS**, conflict **334→85**, retries **5→0**

All 14 revised agents: detect OK, published, **0 retries, 0 stalls**. Kept the revision.

## Assistant

Escalated. Folded in three small clarity fixes agents flagged (arriving-first fast-forward is valid; `git rebase --continue` editor note; jj verify uses jj not git), then ran Pass A (rounds 9–12): git/hard + jj/hard (6 agents each, 6-way version tie-break → 1.5.6, 6 overlapping pipeline blocks) + medium confirms. **All four PASS**, 20 agents, 0 retries, 0 stalls.

Built a concurrent-integration workflow variant (all agents contend for `main` at once) and added the most-flagged correctness note (under `git rebase` the conflict sides are inverted, so "keep mine" is the wrong tie-break heuristic). Ran Pass B (rounds 13–14, concurrent hard) and a final confirm (rounds 15–16, concurrent hard): **all PASS**. Under contention the retries are inherent race-loss re-integration, not skill ambiguity; every agent still landed correct, conflict-free results, and the rebase-inversion note was explicitly load-bearing for the version field.

Final tally — revised rounds 5–16: **12/12 rounds PASS, 58 agents, 100%, 0 failures, 0 mode-detection errors.** Exit bar met across both modes × full difficulty ladder × all tiers × serialized and concurrent. Tore down sandboxes (kept the metrics log), saved two memories (the harness colocation gap; the Workflow `args`-is-a-string gotcha), and reported the deliverables.

## User

Save benchmark results under docs/, export chat session history, commit and push with JJ

## Assistant

Detected jj mode (`jj root`), surveyed `docs/` conventions, and confirmed `jj commit [FILESETS]` for per-path commits and `origin` → GitHub for push. Wrote the benchmark report to `./docs/benchmarks/0000-vcs-skill-conflict-resolution.md` (method, the oracle/validity checks, baseline vs revised, the 16-round table, exit-bar assessment, limitations). Exported this transcript via the `export-coding-session` skill, then committed the work in logical units with COMMITS.md-formatted messages and pushed with `jj git push`.
