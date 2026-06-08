<!-- markdownlint-disable MD013 MD024 -->

# Codex Exclude VCS Workspaces From RAG

- Date: 2026-06-08
- Repo: coding-agent-skills (`codex-exclude-jj-workspaces-from-rag`)
- Author: Shuyang Sun <shuyangsun10@gmail.com>
- Agent: Codex Desktop (GPT-5.5, reasoning effort: xhigh)
- Summary: Added a context-retrieval harness metric and generic RAG loader filtering so nested Jujutsu workspaces and Git worktrees are not indexed as parent-repo files, then exported this session and prepared the work for VCS integration.

## User

With the [$improving-context-retrieval-skills](./.agents/skills/improving-context-retrieval-skills/SKILL.md) harness, add one more metric - when a new Jujutsu workspace is added with `jj workspace add <workspace-name>`, it creates a subdirectory within the repo itself. Make sure RAGs or other techniques do NOT index or embed files under those directories. Note that all skills should be generic regardless which repo or project it is used for, so don't hardcode `coding-agent-skills`. However, RAG or other solutions SHOULD work when new Jujutsu workspaces are created, or new Git worktrees are created either inside or outside of the current repository root directory, it's just that they should not be treated as new files added under the project.

For `coding-agent-skills` repo specifically, add directories with regex `coding-agent-skills.*/` to @.gitignore. This may be a good solution for other repos to mitigate this problem as well, but that's the job of the [$setting-up-rag](./.agents/skills/setting-up-rag/SKILL.md) skill.

If you have questions or need me to choose between possible options, let me know.

## Assistant

I’ll use the `vcs`, `coding-style`, `improving-context-retrieval-skills`, and `setting-up-rag` skill guidance here. I’m starting in the isolated Jujutsu workspace the session created, then I’ll inspect the harness and RAG indexing code before editing.

## Assistant

Tool summary:

- Read the `vcs`, `coding-style`, `improving-context-retrieval-skills`, and `setting-up-rag` skill instructions.
- Confirmed the pre-created isolated jj workspace was active.
- Renamed the temporary workspace to `codex-exclude-jj-workspaces-from-rag`.

## Assistant

I’m going to inspect the file loaders and metric/reporting path now. The important distinction is that a nested jj workspace or Git worktree should remain usable as its own corpus when selected directly, but should be invisible when it appears under another repo’s corpus root.

## Assistant

Tool summary:

- Inspected `setting-up-rag/scripts/index.py` and `setting-up-rag/scripts/rag_lib.py`.
- Inspected `improving-context-retrieval-skills/scripts/docs-eval.py`, `check-retrieval.py`, `gold.py`, and `scoreboard.py`.
- Checked `.gitignore` and existing context-retrieval harness documentation.

## Assistant

The RAG skill currently loads every file under the requested corpus with no VCS-boundary filter, and the Phase 0 harness has its own independent loader. I’m checking both so the metric tests the harness behavior and the operator skill gets the generic exclusion behavior too.

## Assistant

There isn’t a general Python style file in the repo’s coding-style skill, so I’m following the existing stdlib-heavy script style. I’m also going to avoid shelling out to `jj` in loaders; marker-based pruning is portable and works for Git worktrees, jj workspaces, and repos without either tool installed.

## Assistant

Tool summary:

- Verified the marker shape of a nested `jj workspace add` fixture in a temporary repository.
- Confirmed the fixture creates a nested `.jj` directory under the workspace subdirectory.
- Saw the repo VCS guard require an explicit owned-workspace prefix for write-like commands.

## Assistant

I’ve found the clean implementation points: `setting-up-rag/scripts/rag_lib.py` for real indexing, and `improving-context-retrieval-skills/scripts/gold.py` for the harness and Phase 0 eval. I’ll add one shared behavior in each: prune nested VCS roots below the chosen corpus root, while still allowing the chosen root itself to be a workspace/worktree.

## Assistant

Tool summary:

- Added marker-based VCS-boundary pruning to `setting-up-rag/scripts/rag_lib.py`.
- Added the same corpus-file iteration behavior to `improving-context-retrieval-skills/scripts/gold.py`.
- Added `check-vcs-boundary.py` to fixture nested jj workspaces, Git worktree `.git` files, and nested Git repos.
- Documented the new hygiene metric in the context-retrieval harness docs.
- Documented the generic loader behavior in `setting-up-rag/SKILL.md`.
- Added the repo-specific `coding-agent-skills*/` ignore guard to `.gitignore`.

## Assistant

The first implementation pass is in place. I’m running the new boundary metric and compile checks now; if the fixture catches a path-shape issue I’ll tighten the loader before moving on to formatting/linting.

## Assistant

Tool summary:

- Ran `check-vcs-boundary.py`; it reported `vcs_boundary_ok=1`, `vcs_boundary_nested_docs_indexed=0`, and direct-root indexing OK.
- Ran `python3 -m py_compile` for the new and changed Python files.
- Ran `gold.py validate`; the gold set validated with 9 facts across 2 domains.

## Assistant

The core check is passing, but I’m tightening the metric before final validation: the direct-root side should cover Git worktrees and nested Git repos as well as jj workspaces, and the docs should call this a hygiene metric rather than implying it is sliced like recall/precision.

## Assistant

Tool summary:

- Updated `check-vcs-boundary.py` to verify direct indexing for three VCS-root shapes: jj workspace, Git worktree, and nested Git repo.
- Adjusted the harness metric docs to distinguish outcome metrics from the VCS-boundary hygiene metric.
- Reran the boundary metric, compile check, and gold-set validation.

## Assistant

Formatting and markdownlint are not installed in this workspace yet (`prettier` and `markdownlint-cli2` are missing). I’ll run the repo’s `bun install` setup, then repeat the checks; generated `__pycache__` directories are from my compile check and will be removed.

## Assistant

Tool summary:

- Ran `bun install`, which installed the pinned repo tooling and configured jj formatting hooks.
- Ran full `bun run format:check`; it exposed existing unrelated formatting drift in exported docs.
- Ran full `bun run lint:md`; it exposed existing unrelated Markdown lint errors.
- Formatted only touched Markdown files with the pinned Prettier binary.
- Ran targeted Prettier and markdownlint with `--no-globs` on touched Markdown files; both passed.

## Assistant

The new metric and targeted style checks are passing. I’ll do one quick Phase 0 eval smoke test with the baseline config, then remove generated caches and inspect the final worktree.

## Assistant

Tool summary:

- Ran a Phase 0 `docs-eval.py` smoke test on the docs corpus with `baseline-b.json`.
- Scored the dev split with `check-retrieval.py`; no query records were missing.
- Cleared generated `__pycache__` directories.
- Confirmed the intended tracked changes were limited to the harness, RAG skill, docs, and `.gitignore`.

## Assistant

Implemented.

Changed the RAG loaders to prune nested VCS roots below the selected corpus root, while still allowing a jj workspace or Git worktree to be indexed when it is passed directly as `--corpus`:

- `./.agents/skills/setting-up-rag/scripts/rag_lib.py`
- `./.agents/skills/improving-context-retrieval-skills/scripts/gold.py`

Added the new metric script:

- `./.agents/skills/improving-context-retrieval-skills/scripts/check-vcs-boundary.py`

It verifies nested jj workspaces, Git worktree `.git` files, and nested Git repos are excluded from parent-corpus loading, while direct indexing of those VCS roots still works.

Updated harness/RAG docs and added the repo-specific ignore guard:

- `.gitignore` now has `coding-agent-skills*/`, documented as the Gitignore glob equivalent of regex `coding-agent-skills.*/`.

Validation run:

- `check-vcs-boundary.py`: `vcs_boundary_ok=1`, `vcs_boundary_nested_docs_indexed=0`
- `gold.py validate`: OK, 9 facts across 2 domains
- Phase 0 eval smoke test: ran and scored with `n_missing=0`
- `py_compile`: passed
- Targeted Prettier and markdownlint on touched Markdown: passed

Repo-wide `bun run format:check` still fails on 4 pre-existing unrelated docs; repo-wide `bun run lint:md` also has existing unrelated Markdown errors.

## User

Advance main, export coding session, then integrate using the VCS skill

## Assistant

I’ll use `vcs` for the jj integration flow and `export-coding-session` for the transcript export. I’m going to inspect the current jj state and the export skill first, then I’ll advance/describe the work, export the session, and run the integrate helper.

## Assistant

Tool summary:

- Read the `export-coding-session` skill and rechecked the `vcs` integration helper.
- Checked the active jj bookmark and confirmed it was `codex-exclude-jj-workspaces-from-rag`.
- Ran the export skill’s `next-index.sh`, which selected `docs/coding-sessions/2026-06-08` and index `0039`.
- Described the jj change as `fix(rag): exclude nested vcs workspaces from indexing`.
- Located and inspected the active Codex session log.

## Assistant

The jj change is now described. For the transcript, I’m using the Codex event-level user messages so hidden/developer context stays out, while the user’s actual prompts are preserved and redacted per the export skill.
