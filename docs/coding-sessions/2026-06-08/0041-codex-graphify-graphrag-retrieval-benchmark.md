<!-- markdownlint-disable MD013 MD024 -->

# Graphify GraphRAG Retrieval Benchmark

- Date: 2026-06-08
- Repo: coding-agent-skills (`codex-graphify-graphrag-retrieval-benchmark`)
- Author: Shuyang Sun <shuyangsun10@gmail.com>
- Agent: Codex Desktop (GPT-5.5, reasoning effort: xhigh)
- Summary: Benchmarked local Qdrant/FastEmbed RAG against a local GraphRAG prototype and graphify on `inception/` plus an alpha-zero test project, researched contextual retrieval integration with graphify, documented the results, then rebased the work onto the latest `main` and resolved additive documentation index conflicts.

<!-- markdownlint-disable MD034 -->

## User

Use the /improving-context-retrieval-skills harness to benchmark and compare the local Qdrant RAG setup against using https://github.com/safishamsi/graphify.

Implement local GraphRAG and use @inception/ and @[REDACTED_LOCAL_PATH]/alpha-zero/ as test projects. Test both coding session history and project code context retrieval, record important metrics and token usage, save the methodology and benchmark in the same file under @docs/benchmarks/.

As a side task, research and tell me if I want to use more advanced context retrival techniques such as contextual retrieval described in the Anthropic engineering blog https://www.anthropic.com/engineering/contextual-retrieval (and maybe more recent advancements), is it possible to integrate that with graphify? I know contextual retrival is more about RAG, I'm not sure if it makes sense for somehting like graphify. Save this research result under @docs/research.

Do not yet change the /setting-up-rag skill, let me know when you are done with your research and benchmark, give me a summary about the situation, then I will make a decision on what to do.

## Assistant

Loaded the requested `improving-context-retrieval-skills` harness plus the repo's `vcs`, `updating-docs`, `retrieving-context`, and `coding-style` skills as relevant. Worked from the isolated jj workspace `codex-graphify-graphrag-retrieval-benchmark`.

Read the existing benchmark and research conventions under `docs/benchmarks/` and `docs/research/`. Confirmed that `setting-up-rag` should be used as-is for the Qdrant baseline and not edited.

Provisioned the local RAG dependencies with the existing `setting-up-rag` setup script after the first check showed missing local dependencies and no Qdrant server. The setup created the local FastEmbed/Qdrant environment and used embedded Qdrant mode.

Created a benchmark reproducer script for three methods:

- `qdrant-rag`: the existing `setting-up-rag` Qdrant/FastEmbed path with dense `BAAI/bge-small-en-v1.5`, sparse `Qdrant/bm25`, reciprocal-rank fusion, and `Xenova/ms-marco-MiniLM-L-6-v2` reranking.
- `local-graphrag`: a local prototype that builds file nodes, token/entity nodes, and file-file edges from imports, includes, Markdown links, path mentions, and lexical overlap, then combines BM25-like direct scoring with graph-neighbor expansion.
- `graphify`: graphify v8 / `0.8.35`, using tree-sitter extraction for code and Gemini-backed semantic extraction for markdown/history corpora.

Built four corpora:

- `inception` history from this repo's `docs/coding-sessions/**/*.md`;
- `inception` code from source/config files under `inception/`;
- alpha-zero history from `memory/**/*.md` plus `alpha-zero-game/docs/dev_dependencies.md`;
- alpha-zero code from curated source/config files, excluding hidden agent/editor dirs, build outputs, generated files, dependencies, and third-party code.

Pinned 12 gold queries, 3 per project/domain pair. Each query specified a primary file plus answer sentinels, then measured recall@20, answer hit@5, primary MRR, NDCG@10, top-5 context token proxy, read tokens to the primary file, retrieval latency, and graphify indexing tokens.

Ran and debugged the benchmark. Qdrant was strong for natural-language history and small `inception` code, but failed all three alpha-zero code queries. The local GraphRAG prototype reached `1.000` recall@20 across both projects and domains, but had weaker alpha-zero code ranking and larger top-5 context. Graphify produced compact query contexts and worked on small `inception` code, but it was weak on alpha-zero code and unreliable for coding-session history.

Inspected graphify output and found the key coding-session blocker: for the inception transcript corpus, graphify nodes often used files mentioned inside transcripts as `source_file` instead of preserving the transcript file that contained the evidence. This made graphify poor for "which session recorded this?" retrieval.

Researched contextual retrieval and related techniques from external sources, including Anthropic Contextual Retrieval, graphify's v8 docs, GraphRAG, Microsoft GraphRAG, LightRAG, and Late Chunking. The conclusion was that contextual retrieval can integrate with graphify only as a hybrid: graphify or a graph extractor can provide relationship/source-map context, but Qdrant should remain the scored dense+sparse retrieval and reranking layer unless graphify grows a vector/BM25 sidecar and fixes provenance.

Added the benchmark report, raw TSV, and reproducer script under `docs/benchmarks/2026-06-08/` and added the research note under `docs/research/2026-06-08/`. Updated the benchmark and research overview indexes. Did not edit `setting-up-rag`.

Verified the new docs and script with:

- Python compile for the benchmark script;
- Prettier on the edited markdown files;
- scoped `markdownlint-cli2 --no-globs` for the edited markdown files.

The first markdownlint run without `--no-globs` picked up the repo-wide configured glob and reported pre-existing unrelated transcript/table lint failures, so the final clean lint check was scoped to the edited files.

## User

Advance main, resolve conflicts. Then rebased onto main, resolve conflicts, export coding session transcript, then integrate using the [$vcs](./.agents/skills/vcs/SKILL.md) skill.

## Assistant

Loaded the named `vcs` skill again for VCS operations and loaded `export-coding-session` because the user explicitly requested a transcript export.

Confirmed jj mode with `jj root` and inspected the current workspace. Ran `jj git fetch` to advance the local view of `main`; it reported `Nothing changed`. Checked bookmarks and found local `main` had advanced to the prior Qdrant-vs-local-GraphRAG benchmark work.

Rebased the current graphify benchmark change onto `main` with `jj rebase -s @ -d main`. The rebase produced additive conflicts in `docs/benchmarks/OVERVIEW.md` and `docs/research/OVERVIEW.md`.

Resolved the benchmark overview conflict by keeping main's new `0008` Qdrant-vs-local-GraphRAG entry and renaming this task's graphify benchmark artifacts to `0009`. Resolved the research overview conflict by keeping main's new `0001` contextual-retrieval-with-GraphRAG note and renaming this task's graphify research note to `0002`.

Updated the renamed report, research note, and benchmark script self-links/default output path so the filenames and overview indexes agree. Verified that conflict markers were gone and `jj status` no longer reported unresolved conflicts.

Allocated the next coding-session transcript index with `bash .agents/skills/export-coding-session/next-index.sh`, which returned `docs/coding-sessions/2026-06-08` and index `0041`. Read the active Codex JSONL session log, reconstructed this transcript with exact user turns except for required local-path redactions, and prepared it for redaction scanning before integration.
