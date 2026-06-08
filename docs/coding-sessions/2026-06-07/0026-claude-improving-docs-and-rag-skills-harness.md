<!-- markdownlint-disable MD013 MD024 -->

# Improving-docs-and-rag-skills harness: Phase-0 build (and an isolation-aware vcs guard fix)

- **Date:** 2026-06-07
- **Repo:** coding-agent-skills (jj workspace/bookmark `claude-improving-docs-rag-skills`)
- **Author:** Shuyang Sun <shuyangsun10@gmail.com>
- **Agent:** Claude Code (Opus 4.8, 1M context, thinking: high)
- **Summary:** Started building the `improving-docs-and-rag-skills` harness from `docs/plans/0002`; immediately hit the open vcs-guard cwd-drift trap (`docs/issues/0008`), so — at the owner's direction — first made the guard isolation-aware (path-based edits + leading-`cd` + owner-marker, plus `session_id` preservation on rename) and landed it on local `main`, then built and committed a deterministic, zero-dependency Phase-0 of the harness (gold set, thin BM25+hashed-dense eval, N/D corpus axis, and a 2×2 factorial scoreboard) that runs the full factorial end-to-end.

## User

Work on the `improving-docs-rag-skills` harness based on plan in `docs/plans/0002-improving-docs-and-rag-skills.md`.

(SessionStart hook had created jj workspace `claude-pending-c626f4f6` at a sibling directory and printed `NEXT_CWD`.)

## Assistant

Read the plan in full. It describes a measurement-driven meta-skill co-optimizing a `docs` skill and a `rag` skill via a 2×2 factorial (corpus N|D × rag b|r), two measurement planes, three loops, five metrics, and a cheapest-first Phase-0 (in-process BM25 + in-memory vectors) gating a Phase-1 TanStack/Qdrant/Ollama app.

Tried to explore the repo, but every non-read-only Bash command and every `Write`/`Edit` was refused by the `vcs-check.sh` PreToolUse hook:

> vcs-check: VCS write refused: current cwd is the shared jj default workspace.

Diagnosed it against `docs/issues/0008`: the guard infers "am I in the shared workspace?" from the hook process's `$PWD`, but this Claude Code harness **resets the Bash cwd to the project root after every command** ("Shell cwd was reset to …"), and the jj workspace is a _sibling_ directory outside the project tree. So the cwd can never be made to "live" inside the workspace, and the documented recovery (`cd NEXT_CWD`) is itself a non-read-only command that gets refused — an unescapable deadlock. Confirmed both `Bash` writes and the `Write` tool were blocked, and that a plain `cd` is gated too.

Read `vcs-check.sh`, `vcs-state.sh`, `session-start.sh`, `rename-work.sh`, and the hook config in `.claude/settings.json`. Noted several concurrent `codex-*` jj workspaces (so isolation genuinely matters) and that the default workspace has no owner marker.

## User

By the way, I will ask agents to create the TanStack Start project using the latest instructions later, no need to do that now. Continue with what you were doing.

## Assistant

Acknowledged — kept the Phase-1 TanStack app out of scope. Presented the blocker and asked how to proceed (path-add the workspace, work in the default workspace, use the issue-0008 vetted-helper Bash escape, or fix the guard first).

## User

(Chose) **Fix the guard first.**

## Assistant

Made the guard isolation-aware rather than cwd-based. Because the hook executes the **default workspace's** copy of the scripts (`$CLAUDE_PROJECT_DIR/.agents/skills/vcs/scripts/…`), I authored and verified the fix in the isolated workspace first, then activated it by copying into the default workspace — so a typo couldn't brick the live hook.

Changes:

- **`vcs-state.sh`** — added `vcs_shared_root_abs`, `vcs_path_in_shared_root` (is a path inside the shared checkout?), and `vcs_session_owns_isolated_workspace` (does this `session_id` own a non-default workspace marker?); and made `vcs_record_current_session` preserve a real previously-recorded `session_id` instead of overwriting it with a synthesized `local-` id.
- **`vcs-check.sh`** — `check_pre_edit` is now path-aware (refuse only edits whose target is inside the shared checkout); a new `maybe_chdir_leading_cd` honors a leading `cd <dir> &&|;` (and a bare `cd`) so the rest of the command is judged from where it runs; `check_hook` extracts `session_id`; `ensure_not_shared`/`hook_warn_if_shared` consult the owner marker and emit differentiated guidance.
- **`rename-work.sh`** — carries the original `session_id` forward across a rename so the refreshed marker keeps matching the owning session.

Verified with `bash -n` plus an 11-case behavior battery (allow isolated edits, deny shared-checkout edits, `cd ws && jj commit` allowed, bare `jj commit` denied, `git push` denied, no-session-id denied, etc.) — all passed. Activated by `cp` into the default workspace; confirmed the live hook now permits a `Write` into the isolated workspace and still denies a `Write` into the shared checkout (with the new "you already own an isolated workspace, prefix with `cd …`" message).

Renamed the workspace `claude-pending-c626f4f6 → claude-improving-docs-rag-skills`, which surfaced the `session_id`-clobber bug (marker rewritten to `local-…`); restored the real id, then verified the `rename-work.sh` + `vcs_record_current_session` fix via a rename round-trip (id preserved). Recorded a memory about the cwd-reset behavior and the new guard.

## User

Commit hook in the default workspace, then continue what you are doing.

## Assistant

Committed the guard fix in the default workspace and advanced **local `main`** to it (`2d29c6b7`), leaving the default workspace on a clean empty `@`; did **not** push (`main@origin` stayed put). Rebased the isolated workspace onto the new main so its duplicate guard-fix edits were absorbed (clean empty base), and deleted the stale `claude-pending-c626f4f6` bookmark.

Then built the Phase-0 harness under `.agents/skills/improving-docs-and-rag-skills/` (deterministic, stdlib-only, no services, no eval-time LLM):

- **`SKILL.md`** + spine (`LOOP.md`, `METRICS.md`, `SCENARIOS.md`, `MATRIX.md`) mirroring `improving-vcs-skill`.
- **`scripts/gold.py`** — the single source of truth: a repo-grounded seed fact table (verified anchors: `380s`/`85s`→benchmark 0000; `urruyqxt`→issue 0007; `reference-transaction`→session 0012; `Composer 2.5`→benchmark 0002; `degenerate`→issue 0003), graded BEIR qrels in `pinned` and `sentinel` modes, build-time validation, a non-circularity firewall (no-echo + trigram-Jaccard guard, stable dev/held-out split, self-reference/meta-doc exclusion), and the shared IR scorer (recall/precision/nDCG/MRR).
- **`scripts/docs-eval.py`** — heading/fixed/recursive chunkers, BM25 + a **stable-hash** dense index (fixed a `PYTHONHASHSEED` determinism bug by switching to `zlib.crc32`), RRF/weighted fusion, optional placeholder rerank; deterministic rankings + per-stage timings.
- **`scripts/check-retrieval.py`** — the READ oracle (`KEY=VALUE` + plan-schema per-query TSV; judge-free `retrieval_hit@20`).
- **`scripts/mk-corpus.py`** — the corpus axis: D (structured) vs N (naive de-structured, one opaque file per doc) carrying the same fact payload, so retrieval deltas are attributable to structure.
- **`scripts/scoreboard.py`** — the 2×2 factorial view: cell means, both marginal effects, and the coupling/interaction, paired per query with seeded-bootstrap CIs.
- **`configs/baseline-b.json`**, **`configs/rag-r.json`**.

Validated `gold.py` (5 facts / 41 docs / 3 multi-relevant), ran the rag axis over GOLD (rag-r beats baseline-b: recall@20 0.675 vs 0.60, MRR 0.54 vs 0.38, retrieval_hit@20 0.80 vs 0.60), confirmed rankings are bit-reproducible, then ran the **full 2×2 factorial** (Nb/Nr/Db/Dr). Honest read: the instrument works and the **rag axis is detectable** (rag marginal @N ≈ +0.18 recall@20), but the **docs axis and coupling are not yet conclusive** (CIs include zero) — limited by the placeholder hashed-lexical embedding and the 5-query seed set; a conclusive GO/NO-GO needs Phase-1 embeddings and a larger gold set. Committed the harness (`c3bb6d9c`) on the workspace bookmark (WIP, not on main) and recorded a project memory.

## User

Advance and rebase to main if needed, export coding session then use /vcs to commit and cleanup, no need to push.

## Assistant

Assessed jj state: local `main` = `2d29c6b7` (guard fix), `main@origin` behind at `767ce7aa` (unpushed, intended); the harness commit `c3bb6d9c` is already a direct child of local main → no rebase needed. Created an empty commit on top for the export, ran the export-coding-session skill to write this transcript, then used the `/vcs` skill to commit the session doc and integrate the stack onto `main`, and cleaned up the workspace — without pushing. Closed with a read-only multi-agent verification pass over the final repo state and the Phase-0 harness.
