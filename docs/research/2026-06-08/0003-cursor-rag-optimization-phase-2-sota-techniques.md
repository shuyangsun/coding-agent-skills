# Research: RAG optimization techniques for Phase 2 (beyond GraphRAG / graphify)

**Date:** 2026-06-08
**Status:** Research complete — feeds Phase 3 measurement loop
**Area:** hybrid retrieval, chunking, reranking, query transforms, code-aware RAG, answer generation
**Sources:** [Anthropic Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval), [Late Chunking (arXiv:2409.04701)](https://arxiv.org/abs/2409.04701), [cAST / EMNLP 2025](https://aclanthology.org/2025.findings-emnlp.430.pdf), [Practical Code RAG at Scale (arXiv:2510.20609)](https://arxiv.org/html/2510.20609), [CodeRAG (EMNLP 2025)](https://aclanthology.org/2025.emnlp-main.1187.pdf), [Mix-of-Granularity (arXiv:2406.00456)](https://arxiv.org/html/2406.00456v1), [CRAG (arXiv:2401.15884)](https://arxiv.org/pdf/2401.15884v2), [LightRAG (arXiv:2410.05779)](https://arxiv.org/abs/2410.05779), [0009 benchmark](../../benchmarks/2026-06-08/0009-graphify-graphrag-rag.md), [0008 benchmark](../../benchmarks/2026-06-08/0008-qdrant-vs-local-graphrag.md)

## Summary

Phase 1 established a **207-query, six-repo gold set** with separate `code` and `nl`
cohorts. Prior benchmarks in this repo already tested GraphRAG, graphify, and
Qdrant-only hybrid RAG on a **12-query slice** — enough to learn direction, not enough
to tune. The clearest prior finding: **Qdrant hybrid + rerank is the proven default for
prose/history**, but **code retrieval regresses badly** on C++/CUDA corpora when queries
are phrased in task language rather than symbol/path language. Graph overlays help
recall but are not drop-in replacements; graphify failed transcript provenance.

Phase 2 therefore prioritizes **measured, one-knob-at-a-time improvements on the
existing Qdrant + FastEmbed stack**, not another graph-first pivot. The highest-expected
lift paths, in order:

1. **Code-aware chunking + metadata** (AST/symbol paths, language tags, parent-file IDs)
2. **Stronger sparse/dense arms + fusion tuning** (SPLADE, bge-base/large, prefetch/RRF)
3. **Parent / small-to-big retrieval** (retrieve child, return parent window)
4. **Contextual retrieval at index time** (Anthropic-style capsules — needs a local LLM)
5. **Late chunking** (long-context embedder — alternative to LLM capsules for transcripts)
6. **Query transforms** (multi-query expansion, HyDE — query-time LLM, gated carefully)
7. **Stronger rerankers** (GPU cross-encoder or lightweight LLM BESTFIT rerank for code)
8. **Optional graph/source-map overlay** (local GraphRAG prototype from 0009 as expansion,
   not replacement)
9. **Answer-generation grounding** (citation-forced prompts, CRAG-style strip filtering)

GraphRAG / graphify remain **secondary**: useful as provenance-aware expansion after Qdrant
recall is fixed, especially for cross-file code and session-history queries.

## What the Phase 1 eval set demands

| Cohort | Queries | Corpus shape                                | Dominant failure mode (from prior benchmarks + gold design)                          |
| ------ | ------: | ------------------------------------------- | ------------------------------------------------------------------------------------ |
| `code` |     137 | C++23/CUDA/TS source, configs, tests        | NL query ↔ symbol/path mismatch; wrong file ranks (templates, adjacent modules)      |
| `nl`   |      70 | design docs, `memory/`, session transcripts | long multi-hop prose; pronoun-heavy chunks; session file vs mentioned-file confusion |

Hard tier (55 queries) requires **multi-sentinel, multi-file synthesis** — rewards reranking,
parent retrieval, and graph expansion more than raw recall@1.

Per-repo split matters: Alpha Zero engine repos dominate `code`; `coding-agent-skills` and
`website` split code vs session/prompting history.

## Technique catalog (SOTA → practical for this harness)

### Tier A — implement first (no or low LLM cost)

| Technique                                            | What it fixes                               | Fit for our corpora                 | Cost / deps          | Prior art in repo                        |
| ---------------------------------------------------- | ------------------------------------------- | ----------------------------------- | -------------------- | ---------------------------------------- |
| **Hybrid BM25 + dense + RRF + cross-encoder**        | baseline recall + rank quality              | already default                     | CPU, FastEmbed       | 0006 baseline; keep as floor             |
| **SPLADE sparse** (`prithivida/Splade_PP_en_v1`)     | identifier/symbol recall                    | code + API names                    | CPU, re-index        | noted in `rag-config.json` `_alt_sparse` |
| **bge-base / bge-large dense**                       | semantic paraphrase                         | nl design docs, session prose       | CPU/GPU re-index     | `_alt_dense` in config                   |
| **DBSF / weighted RRF**                              | one arm dominates                           | when SPLADE or dense wins on a repo | config only          | RETRIEVAL.md                             |
| **prefetch / top_n / top_k sweep**                   | recall vs latency                           | all                                 | config only          | TUNING.md method                         |
| **Heading-aware prose chunking + `min_words` merge** | tiny-section explosion                      | skills docs, plans                  | already in skill     | CHUNKING.md                              |
| **Code block chunking with symbol metadata**         | path, language, enclosing symbol in payload | all code repos                      | extend `index.py`    | partial today                            |
| **AST-aware chunking (cAST / astchunk)**             | split mid-function failures                 | C++/TS repos                        | tree-sitter grammars | not yet in skill                         |
| **Parent / small-to-big retrieval**                  | child hits, parent context for answer       | long files, transcripts             | index metadata       | not yet                                  |
| **Local GraphRAG overlay (0009 prototype)**          | cross-file recall without LLM index         | alpha-zero code                     | pure local graph     | 0009: best recall profile                |

**Evidence:** Practical Code RAG (2025) finds BM25 + word/line splitting wins for code→code
under latency budgets; cAST (EMNLP 2025) adds +1.8–4.3 Recall@5 on RepoEval when structure
matters; a May 2026 controlled study finds sliding-window ≈ cAST within ~1 pp on Pass@1 —
so **start with cheap line/block chunking + metadata**, then A/B cAST only if code recall
stalls.

### Tier B — index-time LLM (one-time per corpus; your GPUs help here)

| Technique                                           | What it fixes                           | Fit                                    | Cost                             | Notes                                                                                   |
| --------------------------------------------------- | --------------------------------------- | -------------------------------------- | -------------------------------- | --------------------------------------------------------------------------------------- |
| **Anthropic contextual retrieval**                  | decontextualized chunks ("this option") | session transcripts, dense design docs | ~1 cheap LLM call/chunk at index | 35–67% failure-rate reduction reported with rerank; `contextual_retrieval: false` today |
| **Late chunking** (Jina v3 / long-context embedder) | boundary context without LLM text       | long transcripts                       | GPU embed pass; swap embedder    | cheaper than contextual at scale; needs long-context model                              |
| **Context capsules from doc structure** (no LLM)    | parent module/path in chunk header      | all                                    | free if authored well            | pairs with `updating-docs` rules                                                        |

**Recommendation:** use **local LLM for contextual retrieval on `nl` corpora first**
(transcripts + `memory/`), not on code (symbols already lexical). Batch index jobs on
your workstation; cache contextualized text separately from raw chunks for answer stage.

### Tier C — query-time LLM (per query; gate hard)

| Technique                             | What it fixes              | Risk                           | Gate                                                   |
| ------------------------------------- | -------------------------- | ------------------------------ | ------------------------------------------------------ |
| **Multi-query expansion**             | vocabulary mismatch        | hurts exact identifier queries | dev split only; disable for `domain=code` if regresses |
| **HyDE** (hypothetical doc embedding) | vague questions            | adds off-topic dense matches   | nl cohort only                                         |
| **Query decomposition**               | multi-hop                  | latency × N                    | hard-tier subset                                       |
| **LLM rerank (BESTFIT / CodeRAG)**    | code task-language queries | latency                        | Qwen3-8B on GPU beats listwise for code                |
| **CRAG strip filter**                 | noisy top-k context        | may drop true positives        | advisory until measured                                |

### Tier D — defer unless Tier A–C plateau

| Technique                             | Why defer                                                                                   |
| ------------------------------------- | ------------------------------------------------------------------------------------------- |
| **Full GraphRAG community summaries** | strong for global "what changed" questions; weak on pinpoint symbol lookup; expensive index |
| **graphify as primary backend**       | provenance bugs on transcripts (0009); LLM index cost                                       |
| **ColBERT / late-interaction index**  | infra complexity; try stronger cross-encoder rerank first                                   |
| **Cloud rerank/embed APIs**           | conflicts with local-first bar unless parity milestone                                      |

## Answer-generation quality (secondary metrics)

Retrieval metrics are primary in Phase 3, but the gold set also has **sentinel
factuality** answers. Improvements that help generation without hurting retrieval:

1. **Return raw chunk + parent window** — consumer sees full context, not truncated embed text.
2. **Citation-forced answer template** — answer must quote sentinel-bearing passage.
3. **CRAG decompose-then-recompose** — filter top-k strips before LLM (open-source CRAG
   repros use T5 evaluators; a cross-encoder may substitute locally).
4. **Closed-book control** — unchanged; detects hallucination when retrieval misses.

Do **not** add an LLM-as-judge to the gate (harness rule); keep generation checks
deterministic (sentinel containment).

## Repo-specific hypotheses (for Phase 3 experiment ordering)

| Repo                  | First knobs to try                                                                                              | Why                                        |
| --------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| `coding-agent-skills` | exclude eval self-reference; contextual retrieval on `docs/transcripts/`; parent retrieval for long transcripts | self-ref hazard documented in Phase 1 plan |
| `alpha-zero`          | SPLADE + symbol/path metadata; local graph overlay; larger code chunks or whole-file for small headers          | 0009: 0% code recall@20 on Qdrant          |
| `alpha-zero-api`      | contract/header-focused chunking; bm25 boost on `include/` paths                                                | header-only API surface                    |
| `az-game-*`           | `memory/` contextual capsules; code chunks aligned to game interface files                                      | split nl/code per methodology              |
| `website`             | same as skills repo for transcripts; Worker/React code metadata                                                 | Cloudflare Worker identifiers              |

## What we are NOT repeating

- **Graphify-first indexing** — keep as optional context capsule generator only
  ([0002 research](0002-contextual-retrieval-and-graphify.md)).
- **Replacing Qdrant with graph-only retrieval** — 0009 shows local GraphRAG wins recall
  but Qdrant wins history answer@5; hybrid overlay is the path.
- **Single global chunk size** — Mix-of-Granularity and Practical Code RAG both show
  optimal granularity is task- and budget-dependent; tune per `--kind code|md` and per repo.

## Local LLM: do you need one?

**Yes, but only for specific arms — not for the baseline loop.**

| Use case                               | Need local LLM?           | Suggested model (your 2× RTX Pro 6000)                       | Alternative without LLM       |
| -------------------------------------- | ------------------------- | ------------------------------------------------------------ | ----------------------------- |
| Phase 3 baseline (hybrid + CPU rerank) | **No**                    | —                                                            | current stack                 |
| Contextual retrieval (index)           | **Yes** (or cloud $)      | Gemma 3 4B/12B IT, Qwen3-8B, or Llama 3.1 8B via Ollama/vLLM | late chunking + better docs   |
| Query expansion / HyDE                 | optional                  | same, query-time                                             | skip for code cohort          |
| LLM rerank for code                    | optional                  | Qwen3-8B (CodeRAG paper)                                     | ms-marco cross-encoder on GPU |
| Answer generation in eval              | **No** for retrieval gate | harness uses sentinel check, not full generation             | —                             |

**Cost control:** contextualize **`nl` corpora only** (~70-query primary files skew transcript/doc).
Cache `(chunk_id → context_prefix)` on disk; re-use across benchmark rounds. Estimated
index tokens: order **1–5M input tokens** across six repos depending on chunk count — cheap
on local hardware vs API.

## References to prior repo research

- [0000 — contextual retrieval for doc authors](0000-contextual-retrieval-for-doc-authors.md) — authoring rules (orthogonal but synergistic)
- [0001 — contextual retrieval with GraphRAG](0001-contextual-retrieval-with-graphrag.md)
- [0002 — contextual retrieval + graphify hybrid pattern](0002-contextual-retrieval-and-graphify.md)
- [0009 benchmark — Qdrant vs local GraphRAG vs graphify](../../benchmarks/2026-06-08/0009-graphify-graphrag-rag.md)
