<!-- markdownlint-disable MD013 MD024 -->

# vcs skill: workspace naming convention + a measurable `NAME_OK` harness metric

- **Date:** 2026-06-06
- **Repo:** coding-agent-skills (jj; work landed on `main` from the `vcs-tune` workspace, since retired)
- **Author:** Shuyang Sun <shuyangsun10@gmail.com>
- **Agent:** Claude Code (Opus 4.8, 1M context)
- **Summary:** Ran the `improving-vcs-skill` start-isolation harness to confirm agents create their own workspace/worktree before working (14/14 pass), added the `<ide>-<work>` workspace-naming convention to the `vcs` skill, and built a new durable, measurable `NAME_OK` metric into the harness (git reference-transaction hook + jj op log) — validated end-to-end, including a real small-model naming miss. Reordered "workspace/worktree" jj-first and documented the jj workspace-path one-liner. Mid-session, isolated the work into its own jj workspace after the user flagged it. Merged via a clean 3-commit split (no push), then over follow-up turns documented two jj multi-workspace lifecycle gaps in `docs/issues/0001` (stale `default` workspace; retired workspaces not cleaned up), un-staled `default`, and cleaned up the `vcs-tune` workspace.

## User

> /goal — Run the /improving-vcs-skills harness to ensure all agents create new workspaces with `jj` before starting work (or Git worktree if `jj` is not available). You don't need to run the full harness for this, I only need to test the workspace creation behavior. If agents do not create new workspace before making changes, the /vcs skill description and content likely needs to be tuned. Since agents only see the skill name and description at the beginning, it's important for the skill description to emphasize that the /vcs skill should almost always be used.

## Assistant

Explored the harness (`.agents/skills/improving-vcs-skill/`) and the `vcs` skill. Identified that the relevant flow is `--task start` (session-start isolation), scored by `check-isolation.sh` from durable signals (git: primary `HEAD` reflog line count; jj: op-log `add workspace` entries). The harness force-loads `vcs` into each sub-agent, so it tests the skill's *content*, not description-triggered loading.

Provisioned 8 single-agent start rounds with `new-sandbox.sh`: the `main` arm (agent must isolate) across large/mid/small tiers in both git and jj, plus the `worktree` arm (must not over-isolate) in both modes. Each sub-agent sees only `vcs` + a brief asking for one tiny edit in a shared repo with concurrent teammates — the isolation decision must come from `vcs` alone. Launched the baseline workflow.

## User

> did you create a new Jujutsu workspace yourself for this session?

## Assistant

Honest answer: **no.** The repo is colocated jj and I was in the shared `default` workspace. I'd only read files and written sandboxes to `$TMPDIR` so far (no repo mutation yet), but since tuning `vcs` would edit repo files, I isolated per the very skill under test:

```sh
jj workspace add --name vcs-tune ../coding-agent-skills-vcs-tune -r main
```

All subsequent edits land in the `vcs-tune` workspace.

## User

> In your VCS skill, make sure to also instruct the agent to create new workspaces with name IDE-an-intuitive-name-related-to-the-work. `IDE` can be `claude`, `codex`, `agy`, or `cursor`, etc.

## Assistant

Added the `<ide>-<work>` naming convention to `vcs` (in the `vcs-tune` workspace): defined it once in `ISOLATE.md`'s objective section and applied it through every recipe and cleanup command (git `worktree add -b`, `switch -c`, jj `workspace add --name`, `worktree remove`, `workspace forget`), and surfaced it in `SKILL.md` §2.

Then collected the baseline workflow: **8/8 `ISOLATED=pass`** across both modes, all tiers, both arms — the current skill already drives isolation; no isolation tuning needed.

## User

> Actually, tweak the harness so the IDE / model name at the beginning of the workspace name should be a measurable metric.

## Assistant

Investigated durability: jj's op log keeps `add workspace '<name>'` (survives `workspace forget`), but **git keeps no record of a branch name once it's deleted** (`branch -d` drops the reflog; `worktree remove` drops the worktree). Designed and wired a new metric:

- **`new-sandbox.sh`** — for git start rounds, install a `reference-transaction` hook in the seed `.git` that appends every agent-created `refs/heads/*` name to `CREATED_REFS_LOG` (outside the repo, teardown-robust); installed after the seed refs exist so only the agent's creations log. Also stopped the start brief from prescribing the branch name, so the name comes from `vcs` alone.
- **`check-isolation.sh`** — `NAME_OK=pass/fail` + `WS_NAME`/`NAME_PREFIX` (main arm only; worktree arm `n/a`), against an `NAME_IDE_TOKENS` allowlist (claude/codex/agy/cursor/opus/…).
- **`record-metrics.sh`** (`--name-ok` + column), **`scoreboard.sh`** (`name` column, by-round and by-tier), **`_score.py`** (parse + record + display).
- Docs: `METRICS.md`, `SCENARIOS.md`, `LOOP.md`, harness `SKILL.md`.

Caught and fixed a mistake: I'd edited `check-isolation.sh` in the shared `default` workspace by accident; restored `default` to clean and re-applied the edit in `vcs-tune`.

Functionally tested (git pass `claude-streaming-export`, git fail `quickfix`, jj pass `codex-add-export`; scoreboard + record-metrics smoke). Then ran a 6-round live validation against the updated skill + harness, scored via `_score.py`:

- git/main large & small, jj/main large → `claude-streaming-export` → `NAME_OK=pass`
- **jj/main small (haiku) → `verify-main` → `NAME_OK=fail`** (a real convention miss the metric caught)
- git/worktree, jj/worktree → `n/a` (name handed to it)

All 14 start agents (8 baseline + 6 validation) scored `ISOLATED=pass`. Also strengthened the `vcs` description to emphasize loading at the START of almost any repo task. Recorded a memory on the name-metric durability approach. Syntax-checked all scripts, tore down the sandboxes.

## User

> Since we're mainly using `jj`, use "workspace / worktree" (put workspace at first). Also, when using `jj`, add a one-liner at the appropriate place in one of the skill's markdown files to let the agent know they can find the full path for the Jujutsu workspace with `jj workspace list -T 'name ++ ": " ++ root ++ "\n"'`.

## Assistant

Reordered every inline "worktree/workspace" pair to **workspace-first** across `SKILL.md`, `ISOLATE.md`, and `INTEGRATE.md` (including the cleanup command pair → `jj workspace forget` / `git worktree remove`). Added the path one-liner to ISOLATE.md's jj-mode section and verified it runs (printed `default: …` and `vcs-tune: …`).

## User

> Export session transcript then merge, don't push.

## Assistant

Exported this transcript into `docs/coding-sessions/`. Then split the working-copy change into a clean 3-commit stack matching the repo's scopes — `feat(improving-vcs-skill)` (harness metric), `feat(vcs)` (naming + jj-first wording), `docs(coding-sessions)` (this transcript) — and fast-forwarded `main` onto it (no teammates had landed, so no conflicts). Synced the colocated git ref locally; **did not push** (`origin/main` left untouched, local `main` ahead).

## User

> This is a gap in the current skill. With `jj` workspace, I'd like to merge other workspaces to the default workspace before pushing. When I run `jj` in the main workspace, I get error: `The working copy is stale (not updated since operation …). Run jj workspace update-stale to update it.` This prevents effective agent collaboration. Document this problem under `docs/issues`, following the `XXXX-YYYYMMDD-...` filename format like other folders, then do what was said above so the default workspace is not stale. No need to fix it yet, just document it.

## Assistant

Reproduced the stale error in `default`, then wrote `docs/issues/0001-20260606-jj-default-workspace-goes-stale-blocking-collaboration.md` — symptom (every `jj` command in `default` blocked), repro, why jj does it (per-workspace working-copy sync pointer falls behind sibling operations), collaboration impact, the `jj workspace update-stale` remediation, and a proposed `vcs` direction (left unfixed per instruction). Committed it as `docs(issues): …` on `main` (no push). Then ran `jj workspace update-stale` in `default` and `jj new main` so it sits on the latest mainline, clean — the new issue file checked out there.

## User

> Another issue - now that the old workspace (`vcs-tune`) is no longer needed, it should have been cleaned up. This is another issue to document. Update the existing issue to document this undesired behavior, it's okay if you do it in the default workspace and commit afterwards.

## Assistant

Reframed issue 0001 into one tracking two related jj **multi-workspace lifecycle** gaps: Gap 1 (stale `default`) and a new Gap 2 — retired sibling workspaces are never auto-removed after their work lands on `main`, and each leftover keeps re-triggering Gap 1 (the two compound). As the concrete Gap-2 remediation, verified `vcs-tune`'s work was fully on `main`, then `jj workspace forget vcs-tune` + removed its directory (only `default` remains). Committed the doc update in `default` as `docs(issues): …`; no push.

## User

> Update existing session transcript @docs/coding-sessions/2026-06-06/0012-claude-vcs-skill-name-metric.md to include transcript after the last export, then commit.

## Assistant

Appended the post-export turns (the 3-commit merge, both `docs/issues` exchanges, and this update), refreshed the metadata/summary to the end state, re-ran the redaction scan, and committed the transcript on `main` (no push).
