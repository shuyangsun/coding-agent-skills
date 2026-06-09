<!-- markdownlint-disable MD013 MD024 -->

# Codex RAG Phase 2 Research

- Date: 2026-06-09
- Repo: coding-agent-skills (`codex-rag-phase-2-doc`, change `tntwslzwzxsv`)
- Author: Shuyang Sun <shuyangsun10@gmail.com>
- Agent: Codex Desktop (GPT-5.5, reasoning effort: xhigh)
- Summary: Created Codex-marked Phase 2 RAG optimization plan and research docs, expanded them with parallel subagent SOTA research, rebased onto Cursor's parallel Phase 2 work, resolved additive overview conflicts, and prepared the work for VCS integration.

<!-- markdownlint-disable MD025 -->

## User

Work on Phase 2 of @docs/prompts/2026-06-08/0005-optimizing-rag-setup.md, but instead of folding into the @docs/plans/2026-06-08/0003-rag-eval-set-phase-1.md doc, create a new phase-2.md doc. Usage limit is getting low, so set a timer to wake yourself up once every 30 minutes to check usage limits, if it's not hit then continue, otherwise if it was hit, continue where you left off.

## Assistant

I loaded the `vcs` and `updating-docs` skill instructions and continued in the isolated jj workspace that the session hook had created. I set a 30-minute heartbeat automation named `RAG Phase 2 usage check`, then renamed the temporary jj workspace/bookmark to `codex-rag-phase-2-doc`.

I inspected the Phase 2 prompt, the consolidated Phase 1 eval-set plan, the existing docs conventions, and the current RAG skill/harness docs. I researched current retrieval techniques with web sources and existing repo research notes, then created two docs:

- `docs/plans/2026-06-08/phase-2.md`
- `docs/research/2026-06-08/0003-rag-optimization-techniques-phase-2.md`

The plan covered wiring `eval-set.json` into the harness, establishing baselines, benchmarking retrieval and answer-generation arms, documenting local dependencies, and deciding whether a local LLM was needed. The research note covered contextual retrieval, stronger embeddings and rerankers, late chunking, code retrieval, GraphRAG/LightRAG/RAPTOR-style arms, HyDE/query transforms, Self-RAG, ARES, and local-LLM usage.

I updated `docs/plans/OVERVIEW.md` and `docs/research/OVERVIEW.md`, installed the repo's Bun dependencies in the isolated workspace because `prettier` and `markdownlint-cli2` were missing, and verified the touched files with targeted Prettier and markdownlint checks. I also corrected an accidental initial patch that had landed in the shared checkout by moving the patch into the isolated workspace and removing only my own accidental shared-checkout changes.

## User

Other agents are running in parallel, so mark your file names as codex results. Once you do that, spin up multiple subagents to research more SOTA techniques, and add them to your research and plan results.

## Assistant

I renamed the Codex-owned files so they were explicitly disambiguated from parallel agents:

- `docs/plans/2026-06-08/0006-codex-rag-optimization-phase-2.md`
- `docs/research/2026-06-08/0007-codex-rag-optimization-techniques-phase-2.md`

I updated the titles, metadata, internal links, and directory overviews to use those Codex-marked filenames and confirmed the old unmarked filenames were absent.

I then spawned four read-only subagents for independent SOTA research:

- repository-scale code retrieval and code-specific models;
- agentic/adaptive RAG and answer grounding;
- long-context, hierarchical, graph, and transcript retrieval;
- RAG evaluation and metrics.

The subagents reported findings on CodeXEmbed, Jina code embeddings, Qwen3, CodeR, CoREB, AST-aware chunking, GrepRAG, repository graph overlays, adaptive routers, CoRAG, CRAG, RankRAG, context packing, citation verification, deterministic IR metrics, nugget scoring, contamination controls, parent-document retrieval, late chunking, LongRAG, RAPTOR, LightRAG, HippoRAG2, PathRAG, and local dependency implications.

I consolidated those findings into the Codex research and plan docs, expanding the recommendation matrix to include lexical code retrieval, AST code chunking, parent windows, late chunking, long-reader arms, diversity-aware retrieval, repo graph overlays, adaptive routers, context packing, and citation verification. I re-ran targeted Prettier and markdownlint on the Codex plan, Codex research note, and both overview files; all targeted checks passed.

## User

```xml
<heartbeat>
  <automation_id>rag-phase-2-usage-check</automation_id>
  <current_time_iso>2026-06-09T02:56:20.053Z</current_time_iso>
  <instructions>
Check the current usage-limit state for this thread. If the usage limit has not been hit, continue Phase 2 work for the RAG setup optimization prompt by creating or updating the Phase 2 plan document. If the previous turn stopped because of the usage limit, resume from the latest workspace state and notes before continuing.
  </instructions>
</heartbeat>
```

## Assistant

The Codex Phase 2 plan and research docs were already complete, so I deleted the `rag-phase-2-usage-check` heartbeat automation and reported that the recurring check was no longer needed.

## User

Other agents were doing similar work. Advance main, rebased onto main and resolve conflicts if you see any. Make sure all of your files are clearly marked as `codex`. Then export session transcript, use the [$vcs](./.agents/skills/vcs/SKILL.md) skill to integrate, commit and push.

## Assistant

I loaded the `vcs` and `export-coding-session` skill instructions. I confirmed the workspace was still the isolated jj workspace `codex-rag-phase-2-doc`, and found that `main` had advanced to Cursor's parallel Phase 2 work (`docs(rag): add cursor Phase 2 RAG optimization research and plan`).

I ran `jj git fetch` and rebased this Codex change onto `main`. The rebase produced additive conflicts in:

- `docs/plans/OVERVIEW.md`
- `docs/research/OVERVIEW.md`

I resolved both by keeping Cursor's index entries and adding the Codex entries below them. I verified that the Codex plan and research filenames remained clearly marked with `codex`:

- `docs/plans/2026-06-08/0006-codex-rag-optimization-phase-2.md`
- `docs/research/2026-06-08/0007-codex-rag-optimization-techniques-phase-2.md`

I then allocated this transcript path with the export helper:

```sh
bash .agents/skills/export-coding-session/next-index.sh
```

It returned `docs/coding-sessions/2026-06-09` and index `0045`, after Cursor's `0044` session export on `main`.
