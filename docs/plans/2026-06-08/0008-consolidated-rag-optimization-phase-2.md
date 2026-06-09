# Plan: Consolidated RAG Optimization Phase 2

- **Date created:** 2026-06-09
- **Status:** Consolidated Phase 2 synthesis complete; Phase 3 implementation should start from the pre-work checklist below.
- **Repo:** `coding-agent-skills`
- **Prompt:** [`0005` - Optimizing RAG Setup](../../prompts/2026-06-08/0005-optimizing-rag-setup.md)
- **Phase 1 input:** [`0003` - RAG eval set Phase 1](0003-rag-eval-set-phase-1.md), with 207 verified gold facts in [`eval-set.json`](0003-rag-eval-set-phase-1/eval-set.json)
- **Source plans:** [`0004` cursor](0004-cursor-rag-optimization-phase-2.md), [`0005` claude](0005-claude-rag-optimization-phase-2.md), [`0006` codex](0006-codex-rag-optimization-phase-2.md), [`0007` agy](0007-agy-rag-optimization-phase-2.md)
- **Research sources:** [`0000` contextual retrieval for docs](../../research/2026-06-08/0000-contextual-retrieval-for-doc-authors.md), [`0001` GraphRAG](../../research/2026-06-08/0001-contextual-retrieval-with-graphrag.md), [`0002` graphify](../../research/2026-06-08/0002-contextual-retrieval-and-graphify.md), [`0003` cursor SOTA](../../research/2026-06-08/0003-cursor-rag-optimization-phase-2-sota-techniques.md), [`0004` claude retrieval substrate](../../research/2026-06-08/0004-claude-rag-retrieval-substrate.md), [`0005` claude contextual/routing/faithfulness](../../research/2026-06-08/0005-claude-rag-contextual-routing-faithfulness.md), [`0006` claude local LLM/GPU](../../research/2026-06-08/0006-claude-rag-local-llm-gpu-serving.md), [`0007` codex techniques](../../research/2026-06-08/0007-codex-rag-optimization-techniques-phase-2.md), [`0008` agy SOTA](../../research/2026-06-08/0008-agy-sota-rag-techniques.md)
- **Prior benchmark context:** [`0006` baseline vs RAG](../../benchmarks/2026-06-08/0006-rag-skill-baseline-vs-rag.md), [`0007` contextual source maps](../../benchmarks/2026-06-08/0007-updating-docs-contextual-retrieval.md), [`0008` Qdrant vs local GraphRAG](../../benchmarks/2026-06-08/0008-qdrant-vs-local-graphrag.md), [`0009` graphify vs Qdrant vs local GraphRAG](../../benchmarks/2026-06-08/0009-graphify-graphrag-rag.md)

## Summary

This document consolidates the Phase 2 research plans for optimizing `setting-up-rag` and `retrieving-context` with the `improving-context-retrieval-skills` harness. It supersedes the agent-specific Phase 2 plans as the Phase 3 execution plan, but keeps the source plans and research notes as provenance.

The agents agree on the core strategy: keep the current Qdrant/FastEmbed hybrid stack as the baseline, wire the 207-question Phase 1 gold set into deterministic scoring, split results by `domain=code` and `domain=nl`, and change one retrieval or answer-generation variable at a time. The likely winning system is not a single GraphRAG, graphify, or vector-model swap. It is a measured hybrid stack with code-aware metadata, stronger local embeddings/rerankers, parent-window retrieval, contextual indexing for long prose/session corpora, optional graph/source-map expansion for hard multi-hop slices, and source-grounded answer generation.

The consolidated decision is:

- **Baseline first:** current `BAAI/bge-small-en-v1.5` dense, Qdrant BM25 sparse, RRF fusion, MiniLM rerank, existing chunkers, and `top_k=20`.
- **Report slices, not averages:** always score per repo, `code` vs `nl`, category, difficulty, single-primary vs multi-primary, and hard-tail vs easy queries.
- **Protect source truth:** use `raw_text` for citations and sentinel verification; use `contextualized_text` only for retrieval fields.
- **Keep graph systems secondary:** test graph/source-map overlays, not graph-first replacement, until held-out metrics beat Qdrant without code or provenance regressions.
- **Use a local LLM for the full campaign, not the first baseline:** no LLM is needed to establish current retrieval metrics; a local LLM/GPU stack is needed for contextual retrieval, answer generation, judging, query transforms, and zero API-token cost.

## Phase 3 Pre-Work

Do this before running optimization experiments. This section consolidates all harness, data, environment, and local-model setup that the agents identified as prerequisite work.

### Harness and Gold-Set Wiring

1. **Add an external gold-set loader.** Load `docs/plans/2026-06-08/0003-rag-eval-set-phase-1/eval-set.json` into the harness while preserving `id`, `repo`, `domain`, `category`, `question`, `answer`, `sentinels`, `primary`, `difficulty`, `evidence`, and `source`.
2. **Validate sentinels before every run.** Reuse the Phase 1 raw-byte sentinel checks so every sentinel remains a literal substring of one pinned primary file.
3. **Build graded qrels.** Assign grade 2 to hand-pinned `primary` files. If sentinel-mode qrels are enabled, assign grade 1 to non-primary chunks containing the sentinel, but keep primary-file metrics separate.
4. **Split dev and held-out deterministically.** Derive the split from stable query IDs so each experiment can tune on dev and report final held-out deltas without drift.
5. **Index per repo as one combined corpus; treat domain as a reporting slice, not a corpus split.** Each of the six repos is its own corpus, indexed with code **and** docs together so a single query retrieves whatever is helpful regardless of type (code references docs and docs reference code; 12 gold questions even have primaries spanning both). The retriever is type-blind: do **not** score `domain=code` against a code-only corpus or `domain=nl` against a docs-only corpus. Instead report metrics **total and sliced by `domain=code` vs `domain=nl`** (and category/repo). _(Revised 2026-06-09 per owner: earlier wording said score each domain against its own corpus; that isolated code from docs and is replaced by combined retrieval with sliced reporting — see the pre-work harness README.)_
6. **Emit one row per query x repo x domain x config.** The benchmark TSV must support per-slice aggregation rather than only global means.
7. **Separate retrieval, packing, generation, and verification metrics.** A stronger answer prompt must not hide a weaker retriever.

### Contamination and Self-Reference Controls

1. **Hard-exclude the eval files from the `coding-agent-skills` corpus.** Add `docs/plans/2026-06-08/0003-rag-eval-set-phase-1*` to the exclusion list for this repo, covering both the overview and subdirectory. This prevents retrieving the file that quotes every gold answer.
2. **Hard-exclude this consolidated plan from Phase 3 scoring.** Add `docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md` because it restates benchmark decisions and can become a duplicate answer source.
3. **Use per-query contamination checks for Phase 2 synthesis docs.** Agent plans, research notes, and benchmark reports can be legitimate primary sources for some `coding-agent-skills` gold questions, but they can also restate facts from other files. Do not globally exclude all research or benchmark docs. Instead, flag any retrieved Phase 2 plan/research/benchmark path that is not in the query's `primary` list, and either exclude it for that query or report a contamination hit separately.
4. **Keep the non-echo query rule.** No query should contain its own sentinel. Re-run `python3 docs/plans/2026-06-08/0003-rag-eval-set-phase-1/verify.py eval-set.json` before baseline scoring.
5. **Add closed-book and wrong-context controls.** Run no-retrieval, shuffled/distractor-context, and shuffled-citation variants to detect parametric leakage, answer guessing, and citation laundering.

### Index Payload and Storage Changes

The current index payload is too thin for the planned experiments. Before Phase 3, enrich indexed points with:

- `repo`
- `domain`
- `kind` or `doc_type` (`code`, `md`, `transcript`, `design-doc`, `session-history`, etc.)
- `lang`
- `path`
- `heading_path`
- `parent_id`
- `chunk_idx`
- byte offsets and line ranges
- session IDs, turn indexes, dates, and mentioned-file lists for transcripts
- symbol, class/function, import/include, build-target, and test metadata for code

Add the dual-field pattern:

- **`raw_text`:** verbatim chunk text used for citations, sentinel matching, and final answer context.
- **`contextualized_text`:** deterministic headers or LLM-generated chunk context used for dense embedding and sparse/BM25 indexing.

This is required for contextual retrieval, parent-window retrieval, metadata filtering, citation verification, and source-preserving answer generation.

### Baseline and Benchmark Harness

Run these baselines before any optimization:

- `closed-book`: no retrieval; detects answer leakage.
- `wrong-context`: distractor or shuffled context; detects low retrieval dependence.
- `manual-simple`: the manual/ripgrep path where applicable.
- `plain-current`: current `setting-up-rag` defaults.
- `plain-current-no-rerank`: isolates reranker lift.
- `bm25-only` and `dense-only`: isolate sparse and dense arms before fusion.
- `prefetch-topn-sweep`: tune prefetch, rerank `top_n`, and final `top_k` before adding new models.

Report at least:

- retrieval metrics: nDCG@10, recall@5/20/100, precision@k, MRR, MAP, primary-file MRR, answer hit@5, sentinel coverage;
- answer metrics: citation support, unsupported-claim rate, closed-book confabulation, non-response/abstain rate;
- efficiency metrics: context tokens to first supporting evidence, context tokens to answer, index time, query latency p50/p95, generation latency, model/download size, index size, reranker/judge calls, and cost per correct faithful answer.

Each experiment should produce:

- `docs/benchmarks/YYYY-MM-DD/NNNN-<technique>-<scope>.md`
- optional `NNNN-<technique>-metrics.tsv`
- optional `NNNN-<technique>-config.json`
- optional `NNNN-<technique>-summary.json`

### Local Dependencies

Required for the baseline loop:

- all six repos available locally at the prompt paths;
- repo toolchain ready with `bun install`, `bun run format:check`, and `bun run lint:md`;
- the baseline RAG stack: `bash .agents/skills/setting-up-rag/scripts/setup-local-rag.sh --warm`;
- Python 3.10+ and the skill venv with `qdrant-client[fastembed]`;
- Qdrant server mode preferred for repeatable multi-repo benchmarks; embedded mode is acceptable for small dev runs;
- Docker if using Qdrant server;
- `ripgrep`;
- deterministic IR tooling such as `ranx`, `ir-measures`, or `pytrec_eval`;
- `rapidfuzz` or equivalent dedup/similarity support.

Recommended before code and retrieval-substrate experiments:

- `tree-sitter` plus C++/CUDA/TypeScript/Python/shell grammars, or `chonkie[code]`;
- SQLite FTS5 for lexical code retrieval;
- optional `ctags` or LSP metadata extraction;
- `networkx` for deterministic graph/source-map overlays;
- optional `scikit-learn`, `umap-learn`, and `hdbscan` for hierarchy/cluster experiments.

Recommended before GPU and LLM-backed experiments:

- NVIDIA driver and CUDA for the 2x RTX PRO 6000 Blackwell workstation;
- vLLM for answer-generation and judge endpoints;
- SGLang for prefix-heavy index-time contextualization;
- TEI and/or Infinity for GPU embedding, reranking, and SPLADE serving;
- model pulls for Qwen3-Embedding-0.6B/4B/8B, Qwen3-Reranker-4B, mxbai-rerank-v2, `Splade_PP_en_v1`, Qwen3-32B, Llama-3.3-70B, Gemma-3-27B, Qwen3-30B-A3B or Gemma-3-12B, Lynx-8B/70B, and HHEM-2.1-Open;
- optional `pplx-embed-context-v1` for the LLM-free contextual-embedding arm;
- `ragas`, MiniCheck/HHEM/Lynx packages, or other advisory judge packages pointed at local endpoints.

### Local LLM and GPU Setup

The consolidated local-LLM decision is:

- **No local LLM is required for the first baseline.** Plain hybrid retrieval, BM25/FTS5/`rg`, parent retrieval, metadata indexing, late chunking, embedding swaps, and reranker swaps can be measured without a generative model.
- **A local LLM is required for the full Phase 3 loop** if API token cost should stay near zero. It is needed for index-time contextual retrieval, Doc2Query/query rewrites, graph/source-map summaries, answer generation, and advisory claim checks.
- **Use one model per GPU where possible.** Claude's GPU research found no NVLink, so treat the workstation as two independent 96 GB VRAM pools. Avoid tensor-parallel serving across both cards for latency-sensitive paths unless a long-context 70B answer model forces it.
- **Re-verify model versions before pinning.** The prompt mentioned Gemma 4 as possible, but the research only verified Qwen3, Llama 3.3, Gemma 3, Lynx, HHEM, Qwen3-Embedding, and mxbai-rerank. Pull official model cards at campaign time before recording a default.

## Consolidated Operating Rules

### Keep and Revert Discipline

Every Phase 3 change is an A/B against the current best config:

- change one variable at a time;
- build a fresh index when the indexed text, model, payload schema, sparse field, or vector schema changes;
- tune on the dev split, then report held-out metrics;
- keep only if the headline metric rises or holds clear of noise and no important slice regresses;
- record the decision in a benchmark file;
- separate the portable published default from the local GPU campaign config.

The portable `setting-up-rag` default should stay CPU-portable and license-clean. Apache/MIT models are default-safe. Non-commercial or no-derivatives models may be used only in local campaign experiments unless licensing changes.

### Primary Metrics

Use deterministic IR and source-grounding metrics as the gate:

- retrieval: recall@20, nDCG@10, MRR, primary-file MRR, recall@5/100, precision@k, MAP;
- source truth: sentinel containment, answer hit@5, primary-path support, citation existence;
- answer quality: unsupported-claim rate and citation support, with LLM/NLI judges advisory rather than gating;
- efficiency: p50/p95 latency, index time, context tokens, model/call counts, and index size.

LLM-as-judge, RAGAS, Lynx, FaithJudge, MiniCheck, HHEM, and nugget scoring are diagnostics until calibrated on a hand-labeled slice of this mixed code/transcript corpus.

### Required Slices

Every benchmark must report:

- repo;
- `domain=code` vs `domain=nl`;
- category (`codebase`, `design-doc`, `session-prompting`);
- difficulty;
- single-primary vs multi-primary;
- single-hop vs multi-hop or hard-tail estimate;
- source agent (`claude` vs `codex`) when useful;
- answerable vs abstain/unanswerable if introduced;
- index/query/generation cost.

## Phase 3 Experiment Roadmap

The roadmap collapses overlapping agent recommendations into ordered waves. The order is confidence x cost: cheap query-time math and harness controls first, then index schema, then GPU substrate, then generated context and adaptive systems.

### Wave 0 - Baseline and Controls

Goal: make current performance measurable on the 207-query gold set before optimizing.

1. Wire the gold loader, qrels, contamination controls, and slice metrics.
2. Run `closed-book`, `wrong-context`, `manual-simple`, `plain-current`, `plain-current-no-rerank`, `bm25-only`, `dense-only`, and prefetch/top_n/top_k sweeps.
3. Record latency, index cost, and context-token budgets for each baseline.
4. Declare the baseline config that later experiments must beat.

### Wave 1 - Re-Index-Free and Low-Risk Retrieval Wins

Goal: improve ranking and answer grounding without changing the corpus representation.

1. **Per-cohort weighted RRF.** Up-weight sparse for code and dense for prose, and grid-search on dev. Qdrant's RRF `k` default is 2, not the literature-default 60, so pass or tune it explicitly.
2. **DBSF or weighted fusion.** Test only if score calibration is stable enough to beat RRF.
3. **Prefetch and rerank-depth tuning.** Do not blindly deepen CPU MiniLM `top_n`; it can degrade near top_n 50-100.
4. **High-quality or exact HNSW.** At six-repo scale, `m=32`, `ef_construct=400`, higher `hnsw_ef`, or exact search can remove ANN approximation as a recall-loss source.
5. **Lost-in-the-middle context reordering.** Place strongest evidence at the start/end of the prompt and compare score-order vs source-order layouts.
6. **Mechanical citation-existence checks.** Require chunk IDs or line references in generated answers and verify the cited chunk/line exists.

### Wave 2 - LLM-Free Index and Payload Improvements

Goal: add the metadata and parent context that many later arms need.

1. **Contextual chunk headers.** Add deterministic headers such as `repo/path::symbol (language)` for code and `session-title + date + project` for transcripts. Index headers in retrieval fields while preserving raw source text.
2. **Parent-document and small-to-big retrieval.** Retrieve child chunks, then return parent sections, file windows, or session-turn windows.
3. **Dual-field storage.** Use `contextualized_text` for retrieval and `raw_text` for citations and sentinels.
4. **Code metadata.** Add language, path, symbol, include/import, build-target, test, and mentioned-file signals.
5. **Lexical code retrieval control.** Add `rg`/SQLite FTS5/BM25 with identifier/path weighting and structure-aware deduplication. This is a required control, not merely a fallback.
6. **Chunking sweeps.** Tune markdown heading size/min-merge, code block packing, overlap, transcript chunks, and parent windows.
7. **AST-aware chunking.** Test tree-sitter function/class chunks, cAST-style recursive chunks, and Late Code Chunking-style retrieval/comprehension contexts after cheaper headers and parent windows are measured.

### Wave 3 - GPU Retrieval Substrate

Goal: test stronger local retrieval models while keeping source verification deterministic.

1. **Dense embedder sweep.** Compare `bge-small` with Qwen3-Embedding-0.6B, 4B, and 8B. Qwen3-Embedding-4B is the likely sweet spot, but this corpus decides.
2. **Instruction-prefix plumbing.** Qwen-style decoder embedders require query prefixes and no document prefixes. Wire index and query paths correctly before trusting metrics.
3. **Named vectors.** Test `dense_code` and `dense_prose` vectors with cohort-specific routing if one dense model does not dominate both cohorts.
4. **Sparse arm split.** Keep BM25 for code. A/B `Splade_PP_en_v1` for prose and long `nl` queries. Do not globally swap BM25 to SPLADE until exact identifier behavior is measured.
5. **Reranker swap.** Compare CPU MiniLM with permissive candidates such as `bge-reranker-v2-m3`, mxbai-rerank-v2, and Qwen3-Reranker-4B. Validate Qwen3-Reranker serving and score sanity before use.
6. **BGE-M3 and multi-representation arms.** Test as an experimental dense+sparse+multi-vector collapse, especially for long prose, but do not assume it beats Qwen3 dense on code.
7. **Qdrant storage knobs.** Use named vectors, int8 scalar quantization plus rescoring for large vectors, and high-quality HNSW. Reserve binary quantization for large/high-dimensional indexes if memory becomes binding.

### Wave 4 - Contextual and Long-Document Retrieval

Goal: improve transcript, design-doc, and ambiguous prose retrieval without diluting code identifiers.

1. **Anthropic-style contextual retrieval.** Use a local LLM to generate 50-100 token chunk context before dense and sparse indexing. Start with `nl` corpora and long transcripts.
2. **LLM-free contextual embedding.** A/B `pplx-embed-context-v1` or late chunking against generated contextual retrieval.
3. **Late chunking.** Test long-context embedding plus pooled chunk vectors on `coding-agent-skills` and `website` session transcripts before source code.
4. **Doc2Query/document expansion.** Use prose-only expansions in a separate field so code identifiers are not crowded out.
5. **Session metadata and summaries.** Add session IDs, dates, projects, turn windows, mentioned-file lists, and optional source-map capsules.
6. **Long-context reader arms.** Compare whole sections/files/sessions with source-order, score-order, and parent-before-child packing.

### Wave 5 - Code Graphs, Source Maps, and Hierarchy

Goal: recover cross-file dependencies and architecture/history answers as overlays, not replacements.

1. **Deterministic repo graph overlay.** Expand candidates with include/import/call/class/test edges, then rerank with Qdrant and the normal reranker.
2. **Local GraphRAG-style source map.** Reuse the promising deterministic graph approach from benchmark `0009` as a candidate expansion layer for code and multi-hop questions.
3. **Graphify only after provenance fixes.** Graphify compacted contexts but misattributed transcript evidence by storing mentioned files as `source_file`. Require separate `evidence_source_file` and `mentioned_source_file` before using it for session-history scoring.
4. **Full GraphRAG/LightRAG/HippoRAG/RAPTOR/PathRAG.** Scope these to global, architectural, and hard `nl`/multi-hop slices. Do not use them as the default retrieval path unless held-out metrics prove a broad win.
5. **Source maps as answer bridges.** Let source maps improve answerability, but require the consumer to verify against primary code/docs because source maps can rank above primary files.

### Wave 6 - Query Routing and Adaptive Retrieval

Goal: spend expensive transforms only on hard queries.

1. **Deterministic feature router.** Start with features such as repo, domain, query length, identifier density, path mentions, code tokens, difficulty estimate, multi-hop markers, available indexes, and first-pass retrieval confidence.
2. **Self-query soft filters.** Extract or infer `repo`, `lang`, and `kind` filters. Keep filters soft so a misclassification does not drop the gold chunk.
3. **Query decomposition.** Prefer decomposition over broad HyDE for multi-part hard questions because subqueries can preserve exact lexical signals.
4. **HyDE and multi-query.** Gate to `nl` or dev-proven vague queries only. Disable for identifier-heavy code unless held-out metrics prove a win.
5. **CRAG-style evaluator.** Reuse rerank/evidence support scores to choose answer, retry, local re-query, or abstain. Drop web fallback for this closed local corpus.
6. **Agentic loop.** Only after static and routed retrieval plateau, test a bounded agent with keyword, semantic, graph/source-map, and file-read tools. Measure route correctness, tokens-to-primary, and latency.

### Wave 7 - Answer Generation and Faithfulness

Goal: optimize answer quality after retrieval quality is stable.

1. **Source-preserving context packer.** Compare raw top-20 chunks with 2k, 4k, and 8k extractive packs that preserve source IDs, source order, parent headers, and deduplicated spans.
2. **Citation-forced answers.** Require sentence-level source-path or chunk-line citations.
3. **Mechanical citation verification.** Check that cited chunks and line ranges exist and contain support.
4. **Sentinel and nugget coverage.** Keep sentinel containment as the deterministic gate. A/B nugget scoring on a subset before committing to authoring cost.
5. **Faithfulness diagnostics.** Use HHEM as the default-friendly deterministic NLI core, and Lynx/FaithJudge/RAGAS as advisory GPU diagnostics.
6. **Code-cohort calibration.** All public faithfulness tools are prose-validated. Calibrate on a hand-labeled slice of C++/CUDA/TS answers before trusting code-cohort scores.
7. **Generator choices.** Test Qwen3-32B, Llama-3.3-70B, and Gemma-3-27B or current verified successors locally. Pick on this corpus, not generic leaderboards.

## Repository-Specific Starting Hypotheses

| Repo                  | First experiments                                                                                                     | Reason                                                                                 |
| --------------------- | --------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `coding-agent-skills` | Eval self-reference exclusion, transcript contextual headers, parent/session windows, source-map contamination checks | Contains the eval files, research docs, benchmark docs, and coding-session transcripts |
| `alpha-zero`          | Qwen3 embeddings, BM25/path/symbol weighting, deterministic graph overlay, parent windows, code reranker              | Prior 12-query benchmark exposed severe Qdrant code failure on this repo               |
| `alpha-zero-api`      | Header/API surface chunking, `include/` path boosts, contract-oriented parent windows                                 | Header-only API surface and migration docs                                             |
| `az-game-tic-tac-toe` | Game-interface code chunks, memory contextual capsules, symbol/path metadata                                          | Mixed C++ game implementation plus `memory/` docs                                      |
| `az-game-xiang-qi`    | Same as tic-tac-toe plus Chinese-term generator/embedder checks                                                       | Mixed code/docs and xiang-qi terminology                                               |
| `website`             | Transcript/session contextual retrieval, Worker/React path and config metadata, parent windows                        | Code plus session/prompting history, similar hazards to `coding-agent-skills`          |

## Conflicts and Consolidated Resolutions

### Local LLM Urgency

- **Cursor and Codex:** no local LLM is needed for the baseline; use one for contextual retrieval and later answer-quality arms.
- **Claude and Agy:** strongly recommend standing up a local LLM for the campaign.
- **Resolution:** baseline first without a generative LLM; set up the local GPU/LLM stack before Wave 4 and answer-generation work. Retrieval substrate models and rerankers are GPU-served but not generative LLMs.

### Graph and Agentic Priority

- **Agy:** treats graph databases, LangGraph, and agentic RAG as central SOTA architecture.
- **Cursor, Claude, Codex, and benchmarks `0008`/`0009`:** keep Qdrant hybrid as the default; use graph systems as overlays because graphify has transcript provenance defects and graph-first ranking is not proven on code.
- **Resolution:** deterministic graph/source-map overlays are Wave 5; full GraphRAG/LightRAG/HippoRAG and agentic loops are scoped to hard multi-hop/global slices after static retrieval plateaus.

### AST Chunking Priority

- **Agy:** fixed-size chunks are obsolete; AST chunking should replace them.
- **Claude:** cAST and sliding-window-like block packing may be Pareto-close; headers and parent retrieval likely have higher ROI.
- **Cursor and Codex:** AST/cAST are useful arms but not the first thing to ship.
- **Resolution:** implement metadata, contextual headers, and parent windows before AST. A/B AST/cAST/Late Code Chunking after cheaper chunking changes are measured.

### Sparse Retrieval

- **Cursor:** SPLADE is a high-ROI sparse candidate.
- **Claude:** keep BM25 for code because SPLADE can blur exact identifiers; test SPLADE for prose.
- **Codex:** learned sparse is an arm, not a global replacement.
- **Resolution:** BM25 remains the code sparse arm. `Splade_PP_en_v1` is a prose/nl A/B first, and any global sparse change must win identifier-heavy code held-out metrics.

### Query Expansion and HyDE

- **Agy:** HyDE, step-back prompting, and multi-query rewriting are core SOTA query transforms.
- **Claude, Cursor, and Codex:** these are risky for exact code identifiers and should be gated.
- **Resolution:** query decomposition is the safer hard-tail transform; HyDE and multi-query are `nl`-only or dev-proven routes, disabled for code unless measured wins justify them.

### Answer-Generation Scoring

- **Agy and Codex:** mention RAGAS/LLM judges and answer-quality frameworks.
- **Cursor and Claude:** deterministic sentinel/citation checks should remain the gate; LLM judges are advisory.
- **Resolution:** deterministic IR, sentinel, and mechanical citation support gate promotion. HHEM/Lynx/FaithJudge/RAGAS diagnose failures after calibration.

### Model Claims, Licensing, and Defaults

- **Codex and Agy:** list broad model/tool families.
- **Claude:** adversarially corrected benchmark-column mistakes, Qdrant RRF `k`, licensing issues, and GPU topology.
- **Resolution:** use verified Apache/MIT candidates for anything that might ship as a default. Non-commercial or no-derivatives models are local-campaign-only. Re-pull current official model cards before pinning exact versions.

## Promotion Criteria

Promote a technique into `setting-up-rag` or `retrieving-context` only if it:

- beats the current best held-out config on recall@20, nDCG@10, and MRR or clearly improves answer quality at equal retrieval quality;
- does not materially regress any repo/domain/category/difficulty slice;
- improves or preserves citation support, sentinel coverage, and unsupported-claim rate;
- has acceptable p50/p95 query latency, index time, model size, and context-token cost;
- preserves raw-source verification and nested VCS/workspace exclusion;
- has a benchmark report with commands, config, metrics, and keep/revert decision;
- is clearly classified as portable default, optional local GPU upgrade, or research-only.

## Exit Criteria

Phase 3 can stop when, across consecutive rounds and both cohorts:

- retrieval metrics are high and stable on held-out queries;
- code and `nl` slices are reported separately and neither hides a regression;
- answer-generation metrics show high sentinel/citation support and low unsupported-claim rate;
- closed-book and wrong-context controls remain clean;
- latency and context-token budgets are stable or improved;
- additional single-variable changes stop producing held-out wins.

The final output should be a benchmark-backed recommendation for the portable `setting-up-rag` default, an optional GPU/local-LLM campaign config, and any `retrieving-context` routing changes proven by the 207-query six-repo eval set.
