---
title: "RAG Eval Set Phase 1"
date: 2026-06-08
repo: "coding-agent-skills (`codex-rag-eval-set`, change `uymqywuystklynxyytnotmmoolyvwqwn`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Codex Desktop (GPT-5, reasoning effort: high)"
summary: >-
  Collected a Phase 1 RAG evaluation set across six repositories, documented 84
  source-grounded Q&A candidates under `docs/plans/`, exported the session, and prepared
  the jj work for integration.
---

<!-- markdownlint-disable MD013 MD024 -->

# RAG Eval Set Phase 1

<!-- markdownlint-disable MD025 -->

## User

# Optimizing RAG Setup

Use the [$improving-context-retrieval-skills](./.agents/skills/improving-context-retrieval-skills/SKILL.md) harness to improve the [$setting-up-rag](./.agents/skills/setting-up-rag/SKILL.md) and the $retrieving-context skill.

## Methodology

Some prior benchmarks were done, but at a very limited scope. This time, use the following repos:

1. `~/developer/coding-agent-skills` (this repository).
2. `[REDACTED_LOCAL_PATH]/alpha-zero/alpha-zero`.
3. `[REDACTED_LOCAL_PATH]/alpha-zero/alpha-zero-api`.
4. `[REDACTED_LOCAL_PATH]/alpha-zero/az-game-tic-tac-toe`.
5. `[REDACTED_LOCAL_PATH]/alpha-zero/az-game-xiang-qi`.
6. `[REDACTED_LOCAL_PATH]/website`

Use the existing docs files as-is; do not modify the [$updating-docs](./.agents/skills/updating-docs/SKILL.md) skill. Focus on RAG.

## Phases

### Phase 1: Collect Eval Set

1. Start with sub-agents and go through ALL 6 repos above. For each repo, come up with 10 to 20 very detailed question-and-answer pairs that require in-depth knowledge to answer.
2. For repos with both code and session transcripts (like `~/developer/coding-agent-skills`), split the question-and-answer pairs into two halves: half about the codebase, half about prompting techniques and historical session recollection.
3. Store these questions per repo in a plan under @docs/plans/, which will be used to optimize RAG setup.

Work on Phase 1.

## Assistant

I loaded the `vcs` skill first, confirmed the repository was in jj mode, and continued in the isolated jj workspace for the task. I then loaded the requested RAG-related skills: `improving-context-retrieval-skills`, `setting-up-rag`, and the local `retrieving-context` skill, plus `updating-docs` because the output was a plan document under `docs/plans/`.

I inspected the relevant local instructions and docs conventions, including the skill harness guidance, the current `retrieving-context` routing behavior, and the plans overview. I renamed the temporary workspace/bookmark to `codex-rag-eval-set` so the work had a stable task name before editing.

I launched six sub-agents in parallel, one per requested repository, asking each agent to produce detailed, source-grounded Q&A candidates:

- `~/developer/coding-agent-skills`
- `[REDACTED_LOCAL_PATH]/alpha-zero/alpha-zero`
- `[REDACTED_LOCAL_PATH]/alpha-zero/alpha-zero-api`
- `[REDACTED_LOCAL_PATH]/alpha-zero/az-game-tic-tac-toe`
- `[REDACTED_LOCAL_PATH]/alpha-zero/az-game-xiang-qi`
- `[REDACTED_LOCAL_PATH]/website`

While the sub-agents ran, I used local `rg --files` and targeted reads to orient around the existing docs, plan layout, and skill files. When the sub-agents returned, I normalized their output into a single eval set and kept the code/history split where applicable:

- `coding-agent-skills`: 14 candidates, split evenly between codebase questions and prompting/session-history questions.
- `alpha-zero`: 12 codebase candidates.
- `alpha-zero-api`: 14 codebase candidates.
- `az-game-tic-tac-toe`: 12 codebase candidates.
- `az-game-xiang-qi`: 16 codebase candidates.
- `website`: 16 candidates, split evenly between codebase questions and prompting/session-history questions.

I spot-checked and corrected source details while consolidating the plan. One notable correction was in the website repo: the retrieval-agent source plan was `docs/plan/retrieval-agent-2026-06.md`, not the initially reported `docs/plan/retrieval-agent-2026-06-04.md`.

I wrote the Phase 1 eval set to `docs/plans/2026-06-08/0003-rag-eval-set-phase-1/README.md` and updated `docs/plans/OVERVIEW.md`. Because the plan was longer than 500 lines, I used the existing plans convention and put it in a dedicated subdirectory with a `README.md`.

For verification, I ran targeted formatting and lint checks on the files I changed:

```sh
bunx prettier --check docs/plans/OVERVIEW.md docs/plans/2026-06-08/0003-rag-eval-set-phase-1/README.md
bunx markdownlint-cli2 --no-globs docs/plans/OVERVIEW.md docs/plans/2026-06-08/0003-rag-eval-set-phase-1/README.md
```

Both targeted checks passed. A broader, unscoped markdownlint run was not used as the completion signal because it reported pre-existing issues in unrelated documents.

## User

Export session, integrate with the VCS skill

## Assistant

I loaded the `export-coding-session` skill and used its bundled `next-index.sh` helper, which allocated `docs/coding-sessions/2026-06-08/0042-codex-rag-eval-set-phase-1.md` for this transcript. I inspected the active Codex JSONL session, the existing coding-session transcript style, the current jj change, and the configured VCS author.

I wrote this transcript with the required markdownlint directive, redacted absolute local paths outside the repository, updated `docs/coding-sessions/OVERVIEW.md`, ran the bundled redaction scanner, and then re-ran targeted Prettier and markdownlint checks over both the plan files and session-export files before using the `vcs` integration helper to land the jj work.
