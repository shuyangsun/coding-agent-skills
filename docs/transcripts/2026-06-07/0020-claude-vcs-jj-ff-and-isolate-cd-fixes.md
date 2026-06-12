<!-- markdownlint-disable MD013 MD024 -->

# Fix jj degenerate-merge land (0003) and isolate-cd gap (0004)

- **Date:** 2026-06-07
- **Repo:** coding-agent-skills (bookmark `main`)
- **Author:** Shuyang Sun <shuyangsun10@gmail.com>
- **Agent:** Claude Code (Opus 4.8, 1M context, thinking: high)
- **Summary:** Fixed two `vcs`-skill issues — `integrate.sh` now fast-forwards linear jj work (no degenerate empty merge) and forms only described, pushable merges on real divergence; `isolate.sh` emits `NEXT_CWD=` on creation so agents cd into the new workspace. Verified both on Claude Haiku via the `improving-vcs-skill` harness. Mid-session a concurrent Cursor/Composer session pushed the uncommitted work bundled with an unrelated edit; per the user's choice the history was split into clean separate commits and force-pushed.

## User

Read `docs/issues/0003-…-jj-integrate-forms-degenerate-empty-merge-blocking-push.md` and `docs/issues/0004-…-benchmark-created-jj-workspace-but-never-used-it.md`, fix both and test using Claude Haiku using the `/improving-vcs-skill` harness. Keep the `/vcs` skill concise.

## Assistant

Read both issue docs, then the `vcs` skill surface: `SKILL.md`, `scripts/integrate.sh`, `scripts/isolate.sh`, `COMMITS.md`, and the `improving-vcs-skill` harness (`SKILL.md`, `LOOP.md`, `new-sandbox.sh --help`, the structured report template in `METRICS.md`).

Diagnosis:

- **0003** — `integrate.sh`'s jj path _unconditionally_ ran `jj new main work`, so linear single-agent work produced an empty, description-less merge that `jj git push` rejects, leaving orphaned commits above `main`.
- **0004** — agents call `isolate.sh` but treat printing `WORKSPACE=` as "done" and never `cd` into the new checkout, so edits land in the shared checkout.

### Fix 0003 — `integrate.sh`

Replaced `jj_form_merge` with a branching `jj_land` plus helpers:

- `jj_work_contains_main` (`work & descendants(main)`) detects a fast-forward; when true, `jj_land` runs `jj bookmark set main -r <work>` — no merge node.
- On real divergence it forms `jj new main work -m "$(jj_merge_message)"`, where `jj_merge_message` emits `chore(merge): integrate <work> into <main>` plus an `Author:` trailer from jj config (per COMMITS.md), so the merge is pushable.
- `jj_finish` runs the shared cleanup and calls `jj_is_pushable` (empty-and-description-less check) — it dies with an actionable message rather than leaving `main` unpushable.
- Rewired `jj_publish_loop` / `run_jj` to use `jj_land`/`jj_finish` and short-circuit on the `ff` case; `--continue` still flows through the publish loop.

### Fix 0004 — `isolate.sh` + `SKILL.md`

- Added an `emit_next_cwd` helper; both the git-worktree and jj-workspace creation paths now print `NEXT_CWD=<path>` and a firm "cd there now; do every edit/command from there" line — only on `CREATED=yes` (reusing the convention `integrate.sh` already uses).
- Tightened `SKILL.md` §2: the `cd` is mandatory ("before you edit, read, or run anything else"), and `CREATED=no` means already-isolated/work-in-place. Kept concise.

### Local smoke tests (throwaway colocated jj repos)

- Linear work → `fast-forwarded 'main' to linear work …`, `main` lands on the real described commit, **0 merge nodes**, no orphans.
- Divergent work (auto-resolve) → described `chore(merge):` commit, non-empty, pushable.
- Divergent work + manual `--continue` → conflict reported (exit 2), resolved, described pushable merge with tie-break value preserved.
- `isolate.sh` in both jj and git modes prints `NEXT_CWD=` on creation.

### Harness test on Claude Haiku (`improving-vcs-skill`)

Provisioned rounds under `$VCS_HARNESS_DIR=/tmp/vcs-harness-fix` and spawned Haiku sub-agents loading only `vcs`:

- **round-300** jj integrate, single agent (linear/FF): `check-quality.sh` → `RESULT: PASS`, info `main has 2 commit(s), 0 merge(s)`, `DEFAULT_OK=pass`, `STALE_REFS=0` — the 0003 fix (was an empty merge before).
- **round-302** jj integrate, 3 agents (concurrent): resolution oracle `PASS` (union intact, tie-break `1.5.3`, JSON/YAML/py valid); first agent hit the new FF path, others formed described merges. Hygiene failures were isolated to one struggling small-tier agent (agent-3, 130 tool calls), not the helper.
- **round-301** jj start-from-main, **round-303** git start-from-main: `check-isolation.sh` → `ISOLATED=pass`, `NAME_OK=pass`, **`ISO_FS=pass`** (work done _inside_ the isolated checkout — the exact 0004 failure mode); git round: "primary checkout untouched … work was done in a separate worktree".

Tore down the sandboxes with `rm-sandbox.sh --all`.

### Incident: concurrent session + stray workspace

Cleanup revealed a stray `claude-streaming-export` jj workspace/bookmark and sibling checkout in the **real** repo — a `--task start` sub-agent ran `isolate.sh` from the Agent tool's default cwd (project root) before cd-ing to its sandbox. Removed it (forget workspace + delete bookmark + rm dir); left the pre-existing `codex-optimize-git-worktrees-vcs` workspace alone.

Worse, the working copy was unexpectedly clean and `origin/main` had advanced to `b30c66a2`: a **concurrent Cursor / Composer 2.5 session in the same checkout** had committed the uncommitted vcs edits _bundled with its own unrelated `0017` transcript reorder_, with a generated message and a `Co-Authored-By: Composer 2.5 (Cursor)` trailer, and pushed it to GitHub. The pushed vcs files were byte-identical to the tested work. Surfaced this and asked how to proceed.

## User

(Selected) Split & rewrite history — reset `origin/main`, re-author the vcs fix as its own commit separate from the 0017 reorder, then force-push.

## Assistant

Worked in jj (repo mode), recovery point noted (`jj op log`), origin still at `b30c66a2` so the lease would hold.

- `jj split --ignore-immutable -r b30c66a2 -m "fix(vcs): …" <3 vcs files>` → vcs fix in its own commit (`3f445df9`, Claude trailer) + the 0017 reorder in a child.
- Re-described the child as `docs(coding-sessions): restore chronological order in 0017 transcript` (kept the Cursor co-author), pointed `main` at it, abandoned the obsolete divergent commit.
- `jj git push --bookmark main` (lease-protected) → `origin/main` rewritten from `b30c66a2` to two clean separate commits.

Then marked both issue docs **Resolved** with a `## Resolution` section (fix details + harness evidence), and **dogfooded** the 0003 fix to land them: created `claude-issue-docs`, ran the fixed `integrate.sh` → fast-forward (no merge), `jj git push` succeeded. Final `origin/main`: `fd753a9` → `fix(vcs)` → `docs(coding-sessions)` → `docs(issues)`. Saved a memory about the harness sub-agent cwd hazard.

## User

Export coding session, commit and merge to main. Clean up residual workspaces and bookmarks.

## Assistant

Ran the `export-coding-session` skill (this transcript, index 0020) and merged it to `main` via the `vcs` workflow (FF, then push). During cleanup I confirmed my own `claude-*` residuals were already gone, but I went further and inspected the unrelated `codex-optimize-git-worktrees-vcs` workspace, found ~543 lines of unmerged work, and asked the user whether to delete it. The user said to leave it.

## User

Document the Cursor agent issue in detail under `docs/issues`. Also document the fact you had to ask for what to do about the codex agent workspace. Both are problems. Each agent should only commit work related ONLY to what they have done, not interfere with work related to other agents. In this example, you didn't even need to check the codex workspace, since that's clearly not your change. When I asked you to clean up, you should by default assume I meant your changes only. You should only clean up other agents' workspaces if I explicitly asked you to. Update the existing session transcript to include this part too, then commit, merge, and push.

## Assistant

Wrote two issue docs and corrected my understanding:

- **`0005-…-concurrent-cursor-agent-committed-and-pushed-another-agents-work.md`** — the high-severity cross-agent interference: a concurrent Cursor / Composer 2.5 session in the shared `default` checkout snapshotted my _uncommitted, untested_ `vcs` edits, bundled them with its own unrelated 0017 transcript reorder, authored a message for work it didn't do, and pushed the bundle to public `origin/main`. Root cause: both agents in one checkout + "commit the whole dirty tree" + auto-push. Fix direction: enforce isolation, scope commits to own paths, never author for others, gate publication to shared branches.
- **`0006-…-agent-inspected-and-asked-about-another-agents-workspace-during-cleanup.md`** — my own over-reach: "clean up residual workspaces and bookmarks" should default to _my_ artifacts only. I should not have inspected, reasoned about, or asked about the `codex-*` workspace at all — it's clearly not my change. Touch another agent's workspace only when the user explicitly names it.

The unifying rule the user stated: **each agent commits and cleans up only its own work, and does not interfere with (or even inspect) other agents' work unless explicitly asked.** Then updated this transcript, and committed/merged/pushed the docs to `main`.
