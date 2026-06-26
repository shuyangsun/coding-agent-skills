---
title: "Updating Docs Contextual Retrieval Benchmark"
date: 2026-06-08
repo: "coding-agent-skills (`codex-improve-updating-docs-retrieval`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Codex Desktop (GPT-5.5, reasoning effort: xhigh)"
summary: >-
  Benchmarked `updating-docs` with the `improving-context-retrieval-skills` harness on
  `inception/` plus an alpha-zero test project, researched contextual retrieval and
  related RAG techniques, updated `updating-docs` with context-capsule/source-map
  guidance, documented research and metrics, then prepared the jj work for integration.
---

<!-- markdownlint-disable MD013 MD024 -->

# Updating Docs Contextual Retrieval Benchmark

## User

Use the [$improving-context-retrieval-skills](./.agents/skills/improving-context-retrieval-skills/SKILL.md) harness to benchmark and improve the [$updating-docs](./.agents/skills/updating-docs/SKILL.md) skill.

Use @inception/ and @[REDACTED_LOCAL_PATH]/alpha-zero/ as test projects. Test both coding session history and project code context retrieval, record important metrics and token usage, save the methodology and benchmark in the same file under @docs/benchmarks/. Do not touch the $retrieving-context skill, only use it as-is during benchmark. Research and make the [$updating-docs](./.agents/skills/updating-docs/SKILL.md) skill to work well with more advanced context retrieval techniques such as contextual retrieval described in the Anthropic engineering blog https://www.anthropic.com/engineering/contextual-retrieval (and maybe more recent advancements). Save your research result under @docs/research/ for my educational purposes.

## Assistant

Loaded the requested `improving-context-retrieval-skills` and `updating-docs` skills, then used `vcs` because the work required source edits. Confirmed the session was in the isolated jj workspace and renamed it from the pending name to `codex-improve-updating-docs-retrieval`.

Inspected the harness docs and scripts (`SKILL.md`, `LOOP.md`, `METRICS.md`, `SCENARIOS.md`, `gold.py`, `mk-corpus.py`, `docs-eval.py`, `check-retrieval.py`, and `scoreboard.py`) and verified the key constraint: the shipped Phase-0 harness has a pinned gold set for this repo's docs plus `inception/`, so alpha-zero needed a custom matrix using the same deterministic retrieval core rather than changing the gold table.

Inspected current docs conventions under `docs/`, `docs/benchmarks/`, and `docs/coding-sessions/`. Read the `retrieving-context` skill to use it as-is and confirmed it stayed untouched.

Ran the shipped Phase-0 benchmark on `docs/` plus `inception/` before editing. It produced the usual floor/factorial/content-type view: `Db` recall@20 `0.642`, `Nr` `0.775`, `Dr` `0.742`, code recall@20 saturated at `1.000`, and code `rag-r` ranking better than baseline on nDCG/MRR.

Explored the alpha-zero test project with bounded file searches, excluding nested dependencies/build outputs after an initial broad search was too noisy. Found that alpha-zero did not have exported `coding-sessions/`; it had long-form `memory/` project docs and C++/Python source, so those memory docs were treated as the project-history/prose analogue and the limitation was recorded in the benchmark.

## User

If you update docs under the @~/developer/alpha-zero/ repository, you can leave them as-is, I'll commit and push them later.

## Assistant

Acknowledged that alpha-zero doc edits could be left for the user, but did not modify alpha-zero files during the benchmark.

Built a custom deterministic matrix over four corpora: `inception` history, `inception` code, alpha-zero project memory, and alpha-zero code. Each corpus was run in raw and source-map conditions with the harness's `baseline-b` and `rag-r` configs. Metrics included recall@20, nDCG@10, answer hit@5, primary hit@20, answer MRR, primary MRR, retrieval latency, chunk counts, and token proxies (`ctx_tokens_top5_chunks`, `ctx_tokens_to_answer_chunk`, `read_tokens_to_primary_doc`).

Key custom benchmark results:

- Alpha-zero code under `rag-r`: primary source hits were `1.000`; source-map treatment cut tokens-to-answer from `199` to `99`.
- Inception code under `rag-r`: source-map treatment cut tokens-to-answer from `396` to `75`.
- Inception history under `rag-r`: source-map treatment lifted answer hit@5 from `0.333` to `1.000`.
- Alpha-zero history under `rag-r`: source-map treatment kept answer hit@5 at `1.000`, with a small token-to-answer increase from `81` to `92`.
- Source maps sometimes ranked above primary sources, so the skill update needed to preserve primary-source verification rather than treating source maps as replacement truth.

Researched current retrieval techniques from primary/external sources: Anthropic Contextual Retrieval, Late Chunking, Reconstructing Context, RAPTOR, GraphRAG, LightRAG, and LongRAG. The applied conclusion was that advanced retrieval benefits from authored context: parent project/module names, exact paths and identifiers, section-local subject names, and explicit relationship edges.

Edited only `./.agents/skills/updating-docs/SKILL.md` for the skill change. Added:

- a third empirical anchor for advanced retrieval needing authored context;
- source maps for cross-cutting code context;
- retrieval context lines near the top of ambiguous docs;
- self-contained section starts;
- prose mirrors for table-only facts;
- a new "Write for advanced retrieval without bloat" section;
- anti-patterns for context-free chunks and source maps that replace verification;
- a checklist update requiring the key fact plus source path/API/command and retrieval context.

Added `docs/research/` and the research note `docs/research/2026-06-08/0000-contextual-retrieval-for-doc-authors.md`. Added benchmark report `docs/benchmarks/2026-06-08/0007-updating-docs-contextual-retrieval.md` and raw metrics TSV `0007-updating-docs-contextual-retrieval-metrics.tsv`. Updated `docs/OVERVIEW.md`, `docs/benchmarks/OVERVIEW.md`, and `docs/research/OVERVIEW.md` so the new docs are findable.

Re-ran the shipped Phase-0 harness after adding the new research doc; the `docs/` corpus count became 58 and the metrics stayed unchanged. Ran `gold.py validate --corpus docs --code-corpus inception`; it passed with 9 facts across 2 domains.

Installed the pinned Bun dependencies because `prettier` was absent in the isolated workspace. Ran Prettier and reverted unrelated formatter churn in existing transcripts/benchmarks. Final verification:

- targeted Prettier check passed for changed Markdown files;
- targeted `markdownlint-cli2 --no-globs` passed for changed Markdown files;
- `gold.py validate` passed;
- repo-wide `bun run lint:md` still failed on pre-existing unrelated transcript/benchmark lint issues, so it was not treated as a clean check.

Final work before export touched only `updating-docs`, docs indexes, the benchmark, the metrics TSV, and the research note. `retrieving-context` was not modified.

## User

 Advance main, export coding session, then integrate using the VCS skill

## Assistant

Loaded the named `vcs` skill again before VCS operations and loaded `export-coding-session` because the user explicitly requested an export. Confirmed jj mode and current workspace/bookmark `codex-improve-updating-docs-retrieval`.

Advanced the local view of `main` with `jj git fetch`; it reported `Nothing changed`. Checked bookmarks and found `main` had moved ahead of the original parent of this work, so the later `integrate.sh` helper would need to land this work against the current `main`.

Allocated the next session export path with `bash .agents/skills/export-coding-session/next-index.sh`, which returned `docs/coding-sessions/2026-06-08` and index `0039`. Read the active Codex JSONL session under the local Codex session log and reconstructed the transcript with exact task user turns, summarized assistant/tool activity, and redactions for local filesystem paths outside this repo.
