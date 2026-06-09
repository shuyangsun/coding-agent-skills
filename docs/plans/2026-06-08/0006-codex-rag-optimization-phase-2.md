# Plan: Codex RAG Optimization Phase 2

- **Date created:** 2026-06-09
- **Last updated:** 2026-06-09
- **Status:** Codex Phase 2 plan ready; no skill changes made yet.
- **Repo:** `coding-agent-skills`
- **Prompt:** [`0005` - Optimizing RAG Setup](../../prompts/2026-06-08/0005-optimizing-rag-setup.md)
- **Phase 1 input:** [`0003` - RAG eval set Phase 1](0003-rag-eval-set-phase-1.md), with 207 verified gold facts in [`eval-set.json`](0003-rag-eval-set-phase-1/eval-set.json)
- **Research note:** [`0003` - Codex Phase 2 RAG optimization techniques](../../research/2026-06-08/0007-codex-rag-optimization-techniques-phase-2.md)
- **Target skills:** [`setting-up-rag`](../../../.agents/skills/setting-up-rag/SKILL.md) and [`retrieving-context`](../../../.agents/skills/retrieving-context/SKILL.md)

## Summary

Phase 2 turns the Phase 1 eval set into a measurement loop for optimizing local
RAG across all six target repositories: `coding-agent-skills`, `alpha-zero`,
`alpha-zero-api`, `az-game-tic-tac-toe`, `az-game-xiang-qi`, and `website`. The
work should first establish a clean baseline with the current `setting-up-rag`
stack, then test one retrieval or answer-generation variable at a time. Store
research under `docs/research/`, experiment reports under `docs/benchmarks/`, and
promote only measured wins into `setting-up-rag` or `retrieving-context`.

The Phase 2 plan deliberately lives in this separate `0006-codex-rag-optimization-phase-2.md` file
rather than being folded into the Phase 1 eval-set plan. Phase 1 remains the
gold-set source of truth; this Codex-authored document owns the optimization plan.

## Goals

- Convert `docs/plans/2026-06-08/0003-rag-eval-set-phase-1/eval-set.json` into
  harness inputs with graded `qrels` from `primary` paths and sentinel-derived
  factuality checks.
- Score each repo separately and report slices for `domain=code`, `domain=nl`,
  `category`, `difficulty`, `source`, single-hop vs multi-hop, and one-primary vs
  multi-primary queries.
- Establish baseline metrics for the current `setting-up-rag` default:
  `BAAI/bge-small-en-v1.5`, Qdrant BM25, RRF fusion, MiniLM reranking,
  heading/code chunking, and `top_k=20`.
- Benchmark current SOTA retrieval techniques against this repo set:
  contextual retrieval, stronger local embeddings/rerankers, lexical code
  retrieval, AST chunking, parent-document retrieval, long-context retrieval,
  graph/source-map overlays, adaptive routing, query transforms, and citation
  verification.
- Improve answer generation only after retrieval metrics are stable, using
  source-grounded prompting, context packing, sentence citations, and claim
  checks.
- Keep the optimization local-first unless a cloud arm is explicitly added as an
  optional comparison.

## Non-Goals

- Do not modify `updating-docs`; the prompt explicitly keeps existing docs files
  and that skill as-is.
- Do not replace Qdrant/FastEmbed with GraphRAG, LightRAG, or graphify without a
  held-out metric win.
- Do not tune on the held-out split. Use a stable dev/held-out partition derived
  from query IDs.
- Do not let `coding-agent-skills` retrieve its own eval files. Exclude this
  `0006-codex-rag-optimization-phase-2.md` plan, the Phase 1 plan/subdirectory, and related benchmark
  reports from the `coding-agent-skills` corpus when scoring.
- Do not start with RL-trained retrievers, full LLM GraphRAG, or heavy learned
  compressors. First prove cheap local inference-time variants beat the current
  config on the 207-query gold set.

## Required Local Setup

Install or verify these before Phase 3 optimization starts:

- All six repos exist locally at the paths named in the prompt:
  `~/developer/coding-agent-skills`, `~/developer/alpha-zero/alpha-zero`,
  `~/developer/alpha-zero/alpha-zero-api`,
  `~/developer/alpha-zero/az-game-tic-tac-toe`,
  `~/developer/alpha-zero/az-game-xiang-qi`, and `~/developer/website`.
- Repo formatting tools are ready with `bun install`, so docs can be checked with
  `bun run format:check` and `bun run lint:md`.
- Baseline local RAG dependencies are ready:
  `bash .agents/skills/setting-up-rag/scripts/setup-local-rag.sh --warm`.
  This creates the RAG venv and installs `qdrant-client[fastembed]`.
- Docker is available if we want persistent Qdrant server mode. Embedded Qdrant
  is acceptable for small dev runs, but server mode is better for repeatable
  benchmark loops.
- Python GPU stack is available for stronger local models: CUDA-compatible
  drivers, PyTorch, `transformers`, `sentence-transformers`, `FlagEmbedding`,
  `accelerate`, and any model-specific packages needed for Qwen3, BGE-M3, Jina,
  Nomic, CodeXEmbed, CodeR, or CoREB tests.
- Code retrieval utilities are available: `tree-sitter-language-pack` or
  equivalent parsers, `ripgrep`, optional `ctags`/LSP metadata, and SQLite FTS5.
- Evaluation utilities are available: `ranx` or `ir-measures`/`pytrec_eval`,
  `rapidfuzz`, and optional `ragas`, MiniCheck/HHEM-compatible models, or other
  advisory judge packages.
- Graph and hierarchy utilities are available as optional arms: `networkx`,
  `scikit-learn`, `umap-learn`, `hdbscan`, and optionally `graphrag`,
  `lightrag-hku`, `hipporag`, `colbert-ai`, or `ragatouille`.
- A local OpenAI-compatible LLM endpoint is available through vLLM, SGLang,
  Ollama, or another local server before testing contextual retrieval, HyDE,
  graph summaries, adaptive retrieval, or answer judges.
- Enough local disk is available for multiple indexes and model caches under
  `$RAG_HOME`, Qdrant storage, and `$CONTEXT_RETRIEVAL_HARNESS_DIR`.

## Local LLM Decision

A local LLM is not required for the first baseline. It is required for the full
optimization loop if we want to avoid spending API tokens on generated chunk
context, query rewrites, graph/source-map summaries, adaptive retrieval plans, and
advisory claim checks.

Use the workstation GPUs for index-time context generation and batched answer
diagnostics. The local model does not need to be the final answer model at first;
it needs to produce compact, stable, source-grounded context strings and
JSON-ish metadata. Prioritize an OpenAI-compatible endpoint, batching, stable
structured output, and 32k+ context over maximum reasoning quality. Larger local
models can be added only when graph extraction or answer-generation quality
becomes the bottleneck.

## Phase 2 Work Plan

### 1. Wire the Phase 1 eval set into the harness

- Add an external gold-set loader for
  `docs/plans/2026-06-08/0003-rag-eval-set-phase-1/eval-set.json`.
- Preserve each Phase 1 field: `id`, `repo`, `domain`, `category`, `question`,
  `answer`, `sentinels`, `primary`, `difficulty`, `evidence`, and `source`.
- Validate every sentinel against its primary files before every run.
- Build qrels with grade 2 for hand-pinned `primary` files and grade 1 for other
  chunks containing the sentinel, if sentinel-mode qrels are enabled.
- Split dev and held-out deterministically by `id` hash.
- Emit one benchmark row per `query x repo x domain x config`.
- Emit separate retrieval, packing, answer-generation, and verification metrics so
  a later answer prompt cannot hide a weaker retriever.

### 2. Establish baselines

- `closed-book`: no retrieval, to detect answer leakage and establish factuality
  floor.
- `wrong-context`: distractor or shuffled context to detect low retrieval
  dependence.
- `manual-simple`: the `retrieving-context` manual/ripgrep path where applicable.
- `plain-current`: current `setting-up-rag` defaults with reranking.
- `plain-current-no-rerank`: same retrieval without reranking to isolate reranker
  lift.
- `bm25-only` and `dense-only`: isolate sparse and dense arms before fusion.
- `prefetch-topn-sweep`: vary prefetch, rerank `top_n`, and final `top_k` before
  adding new models.

Report at least nDCG@10, recall@5/20/100, precision@k, MRR, MAP, sentinel-hit
rate, primary-file MRR, answer hit@5, unsupported-claim rate, context tokens to
first supporting evidence, index latency, query latency p50/p95, and index-time
token/model cost.

### 3. Run retrieval optimization arms

Test one variable at a time:

- **Embedding/reranker sweep:** compare `bge-small`, `bge-base`, BGE-M3, Qwen3
  Embedding/Reranker, Jina v4, Jina code embeddings, CodeXEmbed, CodeR, Nomic
  Embed Code, CoREB-style code rerankers, and optional hosted baselines such as
  Voyage Code 3 as local availability allows.
- **Sparse retrieval:** compare Qdrant BM25 with learned sparse candidates such as
  SPLADE where local performance and dependency cost are acceptable.
- **Lexical code retrieval:** test `rg`, SQLite FTS5/BM25, identifier-weighted
  reranking, and structure-aware deduplication as cheap baselines before heavier
  semantic indexing.
- **Chunking:** tune markdown heading chunk size/min-merge, code block packing,
  overlap, AST-aware chunks, and transcript-specific long chunks.
- **AST-aware chunking:** compare current block chunks with tree-sitter
  function/class chunks, cAST-style recursive AST chunks, and Late Code
  Chunking-style retrieval/comprehension contexts.
- **Parent-document retrieval:** retrieve child chunks, then provide parent
  sections, files, or session-turn windows using `parent_id`, `heading_path`,
  `session_id`, byte offsets, turn indexes, and mentioned-file metadata.
- **Contextual retrieval:** generate 50-100 token context strings per chunk using
  the local LLM, then index contextualized text for dense and sparse retrieval
  while preserving raw source text for final answers.
- **Late chunking and hierarchy:** test late chunking, RAPTOR-style summaries, and
  summary-first routing on long `nl` transcripts before using them on source code.
- **Long-context reader:** test larger retrieved units such as whole files,
  sections, or sessions with score-order vs source-order packing.
- **Code-specialized retrieval:** add code-aware metadata, symbol/path/import/test
  context, import/include graph expansion, code-query rewriting, and
  code-specific embeddings for `domain=code`.
- **Query transforms:** test HyDE and multi-query expansion only on dev queries
  where exact lexical signals are weak; disable them for identifier-heavy code
  queries unless metrics prove a win.
- **Diversity-aware retrieval:** compare RRF top-k with static and dynamic MMR to
  reduce redundant near-matches and recover complementary evidence.
- **Graph and source-map arms:** test deterministic source graphs,
  RANGER/GRACE-style repository graph expansion, GraphRAG, LightRAG, HippoRAG2,
  PathRAG, or a smaller local graph extractor only for multi-hop, cross-file
  dependency, architecture, and session-history slices.

### 4. Add adaptive and answer-generation arms

Static retrieval should win first. After the baseline and retrieval arms are
measured, add adaptive arms:

- `feature-router`: route by deterministic query/corpus features across manual,
  local RAG, lexical code search, graph/source-map, long-context, and corrective
  modes.
- `decompose`: split multi-part questions into subqueries or nuggets before
  retrieval, then fuse evidence.
- `hyde`: generate a hypothetical answer/document only for vague prose queries.
- `corag`: iteratively reformulate retrieval queries when first-pass evidence is
  incomplete.
- `crag`: grade evidence quality and retry with a different route when retrieved
  chunks fail a support check.
- `rankrag`: use a local instruction model for context ranking plus answer
  generation, compared against a smaller cross-encoder reranker.
- `agent-tool-budget`: expose keyword, semantic, graph/source-map, and read tools
  to a bounded agent and measure route correctness plus tokens-to-primary.

For answer generation:

- Pack top evidence by primary-file priority, reranked score, source diversity,
  parent context, source order, and token budget.
- Deduplicate near-identical chunks before generation.
- Compare raw top-20 context with 2k, 4k, and 8k token extractive packs.
- Require sentence-level source-path citations in generated answers.
- Verify generated answers with sentinel containment, sentence-level citation
  support, and, where useful, advisory claim-level checks.
- Record answer-generation metrics separately from retrieval metrics so a better
  answer prompt does not hide a weaker retriever.

### 5. Promote measured wins

Only update `setting-up-rag` or `retrieving-context` after a candidate:

- beats `plain-current` on held-out recall@20, nDCG@10, and MRR;
- improves answer hit, citation support, or unsupported-claim rate at equal or
  lower context cost;
- does not regress any repo/domain/category/difficulty slice materially;
- keeps code, technical docs, and transcript metrics separate rather than
  averaging away a loss;
- has acceptable p50/p95 query latency and index-time cost;
- preserves source verification, contamination controls, and nested VCS workspace
  exclusion;
- is documented under `docs/benchmarks/` with commands, config, metrics, and
  keep/revert decision.

## Benchmark Output Convention

Each experiment should create one benchmark report under `docs/benchmarks/` and
co-located machine-readable data files:

- `NNNN-<technique>-<repo-scope>.md` for the human report;
- `NNNN-<technique>-metrics.tsv` for per-query metrics;
- optional `NNNN-<technique>-config.json` for the exact RAG config;
- optional `NNNN-<technique>-summary.json` for scoreboard output.

Every benchmark report should name the config under test, the baseline it compares
against, the affected repo/domain/category slices, and the decision: keep, revert,
or keep researching.

## Acceptance Criteria

Phase 2 is complete when:

- the Phase 1 `eval-set.json` can be loaded, validated, split, indexed, and scored
  without manual editing;
- baseline metrics exist for all six repos and both `code` and `nl` domains where
  present;
- deterministic IR metrics, sentinel factuality, closed-book controls,
  wrong-context controls, citation support, unsupported-claim rate, latency, and
  cost are reported by slice;
- at least one contextual retrieval arm, one stronger model arm, one lexical code
  arm, one AST-aware code arm, one parent-window arm, one long-document arm, one
  graph/source-map arm, one adaptive routing arm, and one citation-verification
  arm has been benchmarked;
- the dependency and local-LLM requirements are documented clearly enough to start
  Phase 3 without another research pass;
- the next implementation changes for `setting-up-rag` and `retrieving-context`
  are ranked by measured expected lift, cost, and risk.

## Open Questions

- Which local LLM endpoint should be standardized for generated chunk context:
  vLLM, SGLang, Ollama, or another OpenAI-compatible server?
- Should the first strong local embedding sweep prioritize Qwen3/BGE-M3 for all
  domains or a code-specific model for `domain=code` first?
- How much index-time cost is acceptable for contextual retrieval if it improves
  transcript recall but not source-code recall?
- Should graph/hierarchical retrieval become a separate route in
  `retrieving-context`, or only an offline benchmark arm until it proves a broad
  held-out win?
- Should the first adaptive route be a deterministic feature router or a
  local-LLM planner with a strict step/token budget?
