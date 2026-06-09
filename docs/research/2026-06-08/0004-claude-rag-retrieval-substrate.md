# Research: SOTA Local Retrieval Substrate (embeddings, code chunking, sparse, fusion, reranking, Qdrant knobs)

**Date:** 2026-06-08 (last updated 2026-06-09)
**Status:** Research complete — input to [`0005-claude-rag-optimization-phase-2`](../../plans/2026-06-08/0005-claude-rag-optimization-phase-2.md); no skill changes made.
**Area:** dense + code embeddings, code-aware chunking, learned-sparse retrieval, hybrid fusion, reranking, Qdrant vector-DB configuration
**Parent campaign:** "Optimizing RAG Setup" Phase 2 — improving [`setting-up-rag`](../../../.agents/skills/setting-up-rag/SKILL.md) and [`retrieving-context`](../../../.agents/skills/retrieving-context/SKILL.md), measured on the Phase-1 gold set ([`0003-rag-eval-set-phase-1`](../../plans/2026-06-08/0003-rag-eval-set-phase-1.md), 207 Q across 6 repos, 137 `code` / 70 `nl`).
**Sibling notes:** [`0005` contextual indexing + query routing + answer faithfulness](0005-claude-rag-contextual-routing-faithfulness.md), [`0006` local-LLM + GPU serving plan](0006-claude-rag-local-llm-gpu-serving.md). Earlier: [`0000`](0000-contextual-retrieval-for-doc-authors.md)/[`0001`](0001-contextual-retrieval-with-graphrag.md)/[`0002`](0002-contextual-retrieval-and-graphify.md).

## Summary

This note covers the **retrieval substrate** — what you index and how you match it: the dense
embedder, the code-specialized embedder, code-aware chunking, the sparse arm, hybrid fusion,
the reranker, and the Qdrant knobs underneath. The current [`setting-up-rag`](../../../.agents/skills/setting-up-rag/SKILL.md)
stack is **Qdrant + FastEmbed, CPU-only**: dense `BAAI/bge-small-en-v1.5` (384-d, MIT,
512-token cap), sparse `Qdrant/bm25` (server-side IDF), RRF fusion, a CPU cross-encoder
rerank (`Xenova/ms-marco-MiniLM-L-6-v2`), heading-aware prose chunking + block-packed code
chunking, `top_k=20`.

The headline conclusion: on the user's **2× RTX PRO 6000 Blackwell** workstation (96 GB GDDR7
each, 192 GB total — see [`0005`](0006-claude-rag-local-llm-gpu-serving.md)) the **single biggest
recall lever for the code cohort (137/207 Q) is the dense embedder**, not the sparse model or
fusion. `bge-small` (general, 384-d) is far below code-capable embedders. The
**Qwen3-Embedding** family (Apache-2.0) is the strongest *shippable* upgrade — it is
near-SOTA on prose **and** the top open code retriever, so one model serves both cohorts.
Everything below is an **A/B candidate, not an adopt-on-spec win**: every cited number is a
generic-benchmark or vendor self-report, none was measured on this mixed C++/CUDA + TS +
transcript corpus, and the keep/revert decision is made on the Phase-1 gold set scored **per
cohort** ([`setting-up-rag` TUNING.md](../../../.agents/skills/setting-up-rag/TUNING.md)).

> **Every benchmark number below was adversarially re-verified.** Where the first research
> pass quoted a wrong figure (mislabeled MTEB-Code columns, Qdrant's RRF `k`, non-commercial
> licenses sold as defaults), the **corrected** value is what appears here, with the
> correction called out.

## Source map — where each lever lives

| Lever | Current | Strongest shippable upgrade | Touches | Re-index? |
| --- | --- | --- | --- | --- |
| Dense embedder | `bge-small-en-v1.5` 384-d (MIT, CPU) | Qwen3-Embedding-4B 2560-d (Apache, GPU) | `rag_lib.py` embed, `rag-config.json` `embedding` | **Yes** |
| Code embedder | (none; general model) | Qwen3-Embedding-4B/8B or CodeRankEmbed-137M | Qdrant named vector `dense_code` | **Yes** |
| Code chunking | block-packed (`code_size 120`) | AST headers + parent retrieval | `index.py` `chunk_code` | **Yes** |
| Sparse arm | `Qdrant/bm25` (Apache) | keep BM25 for code; SPLADE for prose | `rag-config.json` `embedding.sparse_model` | sparse only |
| Fusion | RRF (Qdrant `k`=**2**) | per-cohort weighted RRF | `query.py` `FusionQuery` | No |
| Reranker | `ms-marco-MiniLM-L-6-v2` (CPU) | mxbai-rerank-v2 (Apache) / Qwen3-Reranker (GPU) | `query.py` rerank stage | No |
| Vector-DB | embedded/server, default HNSW | named vectors + int8+rescore + high-quality HNSW | Qdrant collection schema | rebuild |

## 1. Dense embedding model — the biggest code-cohort lever

The current `bge-small-en-v1.5` is **MTEB 62.17 overall / 51.68 retrieval**, 384-d, MIT,
~33M params, 512-token cap. It is a legitimate **CPU-portable default** but is weak on code.

**Verified MTEB scores** (primary: arxiv [2506.05176](https://arxiv.org/abs/2506.05176)
Table 3; HF model cards). Columns: MTEB-Multilingual / MTEB(eng,v2) / **MTEB-Code**:

| Model | Multi | eng-v2 | **Code** | Dims | License | Notes |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `bge-small-en-v1.5` (current) | — | — | low | 384 | MIT | baseline, 512-token cap |
| **Qwen3-Embedding-0.6B** | 64.33 | 70.70 | **75.41** | 1024 | Apache-2.0 | CPU-viable upgrade; 2.67× index vs 384-d |
| **Qwen3-Embedding-4B** | 69.45 | 74.60 | **80.06** | 2560 | Apache-2.0 | **sweet spot**; 6.67× index |
| **Qwen3-Embedding-8B** | 70.58 | 75.22 | **80.68** | 4096 | Apache-2.0 | recall ceiling; 10.67× index |
| BGE-M3 (dense head) | — | ~63 | 58.22 | 1024 | MIT | weak code dense; multi-rep (below) |
| gte-Qwen2-7B-instruct | — | — | 56.41 | 3584 | Apache | strictly dominated by Qwen3-4B |
| EmbeddingGemma-300M | 61.15 | — | 68.76 | 768→128 (MRL) | **Gemma license**, no-fp16 | strong-for-size but Qwen3-0.6B dominates |

**Corrections that matter** (the first pass had these wrong):
- Qwen3 MTEB-Code is **75.41 / 80.06 / 80.68** (0.6B/4B/8B) — the earlier 76.42/83.34/84.23
  were the **Chinese C-MTEB Pair-Classification** column, mislabeled as code.
- gte-Qwen2-7B code is **56.41**, not 81.16 (also a mislabeled pair-classification cell). The
  "Qwen3-4B beats gte-Qwen2-7B at half the params" claim **holds, by a wider margin**.
- **Licensing gate is decisive.** Only **Qwen3-Embedding (Apache-2.0)** and **bge (MIT)** are
  cleanly shippable. NV-Embed-v2 and jina-v4 are **non-commercial** (CC-BY-NC); EmbeddingGemma
  is Gemma-licensed with a hard **no-float16** constraint. Restrict published-skill candidates
  to Qwen3-Embedding + bge.

**The #1 integration pitfall:** Qwen3 (and all decoder embedders) are **instruction-aware and
asymmetric** — queries take an `Instruct: {task}\nQuery: {q}` prefix, documents take none.
Mis-wiring the prefix (prefixing documents, or omitting it at query time) silently tanks
recall. This must be plumbed into **both** index and query paths.

**Recommendation:** A/B sweep **Qwen3-0.6B (1024-d, GPU-optional) vs 4B (2560-d) vs 8B
(4096-d)** against `bge-small`, GPU-served (§ serving in [`0005`](0006-claude-rag-local-llm-gpu-serving.md)).
The 4B is the likely sweet spot — the 8B's +~1 MTEB / +0.6 code rarely justifies 2× latency
and a 10.67× index. Whether MTEB deltas actually move **recall@20 on the 207-Q set** is the
open question — small gold sets can saturate, and MTEB-Code is Python/web code, **not** C++23/
CUDA/transcripts. Measure, don't assume.

## 2. Code-specialized embedder and code-aware chunking

**Do you need a separate code embedder?** Mostly **no** — a single strong general+code model
(Qwen3-Embedding) avoids two pipelines and covers the xiang-qi repo's Chinese terms a
pure-code model would miss. But Qdrant **named vectors** make a dual arm cheap if it wins:

- **`dense_code`** (code embedder) for `domain=code`, **`dense_prose`** (general) for
  `domain=nl`, plus a shared **`sparse`** — each named vector can carry its own
  `hnsw_config`/`quantization_config`. The eval set already tags `domain`, and a cheap
  heuristic routes at query time. This lets each cohort be tuned without dragging the other.

**Deployable code embedders** (Apache/MIT only; proprietary = ceiling reference):
- **Qwen3-Embedding-4B/8B** (Apache, MTEB-Code 80.06/80.68) — the deployable code winner.
- **CodeRankEmbed** (nomic, 137M, MIT, CoIR 60.1 / CSN-MRR 77.9) — near-`bge-small` footprint,
  CPU-viable code specialist; **caveat:** Safetensors-only + `trust_remote_code`, so the CPU
  ONNX-export fallback is **unverified** — validate the export before promising it as a default.
- **voyage-code-3 / CodeXEmbed** — proprietary API; **ceiling oracle only**, violates the
  no-token-cost mandate.

**Code chunking** is independent of the embedder and a separate lever:
- **cAST** (AST split-then-merge, tree-sitter; arxiv [2506.15655](https://arxiv.org/abs/2506.15655),
  EMNLP 2025): +1.8–4.3 Recall@5 / +2.67 Pass@1 on RepoEval/SWE-bench. **But** the controlled
  study arxiv [2605.04763](https://arxiv.org/abs/2605.04763) finds **sliding-window and cAST are
  Pareto-equivalent** while function-level chunking *underperforms* (−3.6 to −5.6pp). The
  current **block-packed `code_size=120` already approximates sliding-window**, so expect a
  **small** cAST lift — deprioritize it relative to headers + bigger returned context.
- **Contextual chunk headers (LLM-free, high value):** prepend `repo/path::Class::method (C++/
  CUDA)` for code, `session-title + date + project` for transcripts, before embedding **and**
  BM25. Near-zero cost, resolves the "the fix" anaphora and lets BM25 match path/identifier
  tokens. The deterministic cousin of Anthropic Contextual Retrieval (covered in [`0004`](0005-claude-rag-contextual-routing-faithfulness.md)) —
  **do not** borrow Anthropic's 35/49/67% figures for the header variant; those are for the
  LLM-generated form. Measure the header's lift separately.
- **Parent-document / small-to-big retrieval:** index precise child chunks, return the parent
  window at answer time (the cross-file-context lever, +4.2pp on code-completion in
  [2605.04763](https://arxiv.org/abs/2605.04763)). Gives code answers their surrounding
  includes/templates and gives transcript hits their antecedent.
- **Dual-field pattern (mandatory here):** store `raw_text` (verbatim, for citation + **gold
  sentinel matching**) separate from `contextualized_text` (header/context, embedded + BM25).
  The harness scores answer factuality by sentinel containment against the **raw** chunk, so
  embedding-side context must never overwrite cited text.

## 3. Sparse arm — keep BM25 for code, A/B SPLADE for prose

Do **not** blindly swap BM25 → SPLADE globally.

- **BM25 (current, Apache, server-side IDF):** loses on code IR **in aggregate** (CoIR BM25
  mean nDCG@10 **29.79** vs best dense ~56, arxiv [2407.02883](https://arxiv.org/abs/2407.02883)),
  but is **decisive on exact-identifier / error-string / config-flag queries** and
  high-overlap code tasks (StackOverflow-QA 56.80, CodeSearchNet). Keep it as the **lexical arm
  of hybrid for the code cohort** — not as a standalone code retriever.
- **SPLADE-v3** (learned sparse, arxiv [2403.06789](https://arxiv.org/abs/2403.06789)): BEIR-13
  51.7, MS-MARCO MRR@10 40.2 — wins on **prose** via query expansion. **But** it
  subword-splits identifiers (camelCase/snake_case/CUDA symbols), which can blur the exact
  matches BM25 nails. **License gate:** SPLADE-v3 weights are `cc-by-nc-sa-4.0`
  (**non-commercial**) → not a publishable default; the Apache option is `Splade_PP_en_v1`
  (already in FastEmbed). Turn the server-side **IDF modifier OFF** for SPLADE (weights are
  learned, not term-stats).
- **Recommendation:** per-cohort sparse — BM25 for code, SPLADE(_PP) for prose — A/B'd
  separately. The crux ("does SPLADE hurt exact-identifier matching vs BM25?") is **unverified
  on this corpus** and could go either way; it must be measured on the code cohort.

**BGE-M3** is worth one experimental arm: one model emits dense + learned-sparse + ColBERT
multi-vector (8192 context, MIT), and could collapse the dense+sparse two-arm hybrid. But its
**dense head (~63 / code 58.22) is well below Qwen3** — its value is multi-functionality and
long context for transcripts, not peak dense recall.

## 4. Hybrid fusion — a cheap, re-index-free win

- **RRF** (current) fuses by rank, immune to score-scale mismatch. **Correction:** Qdrant's
  RRF `k` defaults to **2**, *not* 60 (60 is the generic Cormack-2009 literature default). Pass
  an explicit `k` or grid-search it.
- **Per-cohort weighted RRF** (Qdrant ≥1.17): up-weight **sparse for code**, **dense for
  prose**, grid-searched on the dev/held-out split. This is the highest-value fusion change
  because the two cohorts disagree on which arm is decisive. "Hand-tuned weights without
  measurement are unlikely to beat (1.0, 1.0)" — use the split.
- **DBSF** (score-based, Qdrant ≥1.11): only when one arm is clearly better-calibrated;
  unstable when sparse and dense score scales differ wildly (SPLADE vs cosine). Validate.

Neither fusion dominates universally — decide on the gold set. Pure query-time math, no
re-index.

## 5. Reranking — move it to the GPU, and it stops being the bottleneck

The current `ms-marco-MiniLM-L-6-v2` (22M, 512-token, CPU) is the **weakest and slowest link**
— the dominant ~0.8–3 s p50 latency cost — and at the current **`top_n=50` it sits at its
documented degradation ceiling** (lightweight cross-encoders ingest noise and can fall *below*
baseline as the pool grows toward 100). So **do not simply deepen `top_n` on the CPU MiniLM.**

**Candidates** (verified; cross-harness numbers are **not** mutually comparable — the only
decision-grade number is a local cohort-separated eval):
- **Qwen3-Reranker-4B** (Apache, MTEB-Code **81.20** — higher than any embedder): best code
  candidate. **Caveat:** vLLM needs `hf_overrides` (`Qwen3ForSequenceClassification`,
  `classifier_from_token=['no','yes']`) and has **open score-correctness bugs** (#20532, #21681)
  → requires a validated serving recipe + score-sanity check.
- **jina-reranker-v3** (0.6B, listwise single-pass, 131k context, BEIR 61.94): best
  efficiency/long-context (fixes MiniLM's 512-token truncation on long transcripts/code). **But
  CC-BY-NC (non-commercial)** → GPU campaign only, **cannot** be the published default.
- **mxbai-rerank-v2** (large 1.5B / base 0.5B, **Apache-2.0**): license-clean, near-tied on
  code (CoIR ~70.9), closest **drop-in** to the current pointwise cross-encoder API.
- **bge-reranker-v2-m3** (MIT): the permissive **CPU-default upgrade** over MiniLM.
- **GPU-serve** via TEI / Infinity / vLLM to kill the CPU latency; then re-tune `top_n` per
  cohort (strong rerankers keep gaining with depth; deeper for the code cohort).

## 6. Qdrant vector-DB knobs (mostly free at 6-repo scale)

- **Named vectors:** dual `dense_code` + `dense_prose` arms (and shared `sparse`) in one
  collection, each with its own HNSW/quant config (§2).
- **int8 scalar quantization + rescoring** = the safe default for a big GPU embedder (Qdrant
  docs: error "usually < 1%", ~4× memory). **Correction:** the 96%/0.98-recall figures the
  first pass cited are for **binary** quant on 1536-d/4096-d models, not int8. **Binary** only
  pays off for ≥1024-d embedders on a large corpus — **not** binding on 6 repos. Reserve binary
  for a 4096-d 8B embedder.
- **HNSW:** at 6-repo scale you can afford `m=32 / ef_construct=400` (or even **exact search**)
  to remove ANN approximation as a recall-loss source for both cohorts at negligible cost.
  `hnsw_ef` is the search-time recall knob (no re-index).

## Decision signals (carried into the Phase-2 plan)

1. **Biggest code lever = the dense embedder.** A/B Qwen3-Embedding-0.6B/4B/8B vs `bge-small`,
   GPU-served, named-vector dual arm; keep `bge-small` as the published CPU default.
2. **Keep BM25 for code, A/B SPLADE(_PP) for prose**; never a blind global sparse swap.
3. **Per-cohort weighted RRF** is a cheap, re-index-free first win (mind Qdrant `k`=2).
4. **Swap the CPU reranker for a GPU one** (mxbai-v2 Apache for default-clean; Qwen3-Reranker
   for max code, with a validated serving recipe) — it is the dominant latency cost.
5. **Chunking:** prioritize **contextual headers + parent retrieval + dual-field** over cAST
   (cAST is Pareto-equal to the current sliding-window-like chunker).
6. **Qdrant:** named vectors + int8+rescore + high-quality/exact HNSW — mostly free here.
7. **Nothing ships without a per-cohort win on the 207-Q gold set.** Licenses gate the
   *published default* (Apache/MIT only); the GPU campaign may use heavier models locally.

## Sources

- Qwen3-Embedding: [arxiv 2506.05176](https://arxiv.org/abs/2506.05176), [GitHub](https://github.com/QwenLM/Qwen3-Embedding), [blog](https://qwenlm.github.io/blog/qwen3-embedding/)
- CoIR code-IR benchmark: [arxiv 2407.02883](https://arxiv.org/abs/2407.02883)
- CodeRankEmbed: [HF nomic-ai/CodeRankEmbed](https://huggingface.co/nomic-ai/CodeRankEmbed)
- cAST AST chunking: [arxiv 2506.15655](https://arxiv.org/abs/2506.15655); chunking-vs-context-length controlled study: [arxiv 2605.04763](https://arxiv.org/abs/2605.04763)
- SPLADE-v3: [arxiv 2403.06789](https://arxiv.org/abs/2403.06789); BGE-M3: [arxiv 2402.03216](https://arxiv.org/abs/2402.03216)
- Rerankers: [Qwen3-Reranker](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B), [jina-reranker-v3 arxiv 2509.25085](https://arxiv.org/abs/2509.25085), [mxbai-rerank-v2](https://www.mixedbread.com/blog/mxbai-rerank-v2)
- Qdrant: [quantization](https://qdrant.tech/documentation/guides/quantization/), [vectors/named vectors](https://qdrant.tech/documentation/concepts/vectors/), [hybrid/fusion](https://qdrant.tech/documentation/concepts/hybrid-queries/)
