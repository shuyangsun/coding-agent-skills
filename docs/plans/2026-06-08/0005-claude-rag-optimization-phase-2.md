# Plan: RAG Optimization — Phase 2 (research + the Phase-3 optimization roadmap)

- **Date created:** 2026-06-08 (last updated 2026-06-09)
- **Status:** Phase 2 complete — SOTA techniques researched and adversarially verified; this file is the **optimization plan** Phase 3 executes. No skill changes made yet.
- **Author:** Claude (Opus 4.8, workspace `claude-rag-phase2`).
- **Repo:** `coding-agent-skills`
- **Prompt:** [`0005-optimizing-rag-setup`](../../prompts/2026-06-08/0005-optimizing-rag-setup.md) — Phase 2 ("Research Potential Optimizations").
- **Scope:** Maximize **retrieval quality AND answer-generation quality** on the Phase-1 gold set across all six repos, as a measurement-driven loop. Improves [`setting-up-rag`](../../../.agents/skills/setting-up-rag/SKILL.md) and [`retrieving-context`](../../../.agents/skills/retrieving-context/SKILL.md) via the [`improving-context-retrieval-skills`](../../../.agents/skills/improving-context-retrieval-skills/SKILL.md) harness. `updating-docs` is **not** modified.
- **Relationship to Phase 1:** This is a **separate** plan, deliberately **not** folded into [`0003-rag-eval-set-phase-1`](0003-rag-eval-set-phase-1.md) (which stays the frozen eval-set record). Phase 1 produced the gold set; **this** plan consumes it.

---

## Summary

Phase 1 built the eval set ([`0003`](0003-rag-eval-set-phase-1.md): **207** verified gold Q/A
across 6 repos, **137 `code` / 70 `nl`**, sentinel-anchored, non-circular). Phase 2 — this plan
— researched the SOTA techniques to optimize against it and lays out the **ordered, one-variable-
at-a-time experiment roadmap** for Phase 3.

Unlike prior attempts, the brief is **unrestricted** (not GraphRAG/graphify-only). The research
is captured in three companion notes under [`docs/research/2026-06-08/`](../../research/2026-06-08/):

- [`0004` — SOTA local retrieval substrate](../../research/2026-06-08/0004-claude-rag-retrieval-substrate.md): dense + code embeddings, code chunking, sparse, fusion, reranking, Qdrant knobs.
- [`0005` — contextual indexing, query routing, answer faithfulness](../../research/2026-06-08/0005-claude-rag-contextual-routing-faithfulness.md): contextual retrieval, Adaptive-RAG routing, architectures, answer-gen + faithfulness measurement.
- [`0006` — local-LLM + GPU serving plan](../../research/2026-06-08/0006-claude-rag-local-llm-gpu-serving.md): the 2× RTX PRO 6000 Blackwell hardware plan, model shopping list, and the local-LLM decision.

**Every benchmark number in those notes was adversarially re-verified**, which corrected real
errors (mislabeled MTEB-Code columns, a misattributed ConTEB figure, Qdrant's RRF `k` default,
non-commercial licenses that disqualify "default" candidates, the no-NVLink topology). The
governing discipline is unchanged from the skill's own [TUNING.md](../../../.agents/skills/setting-up-rag/TUNING.md):
**keep a change only if it beats the current config on the held-out gold set, per cohort; one
change at a time, on a fresh index; else revert.**

## The two questions the prompt asks, answered

### Do you need a local LLM? — **Yes; your hardware is more than enough.**

A local generative LLM is **needed** for three roles, and removes **all API token cost** for the
campaign (full reasoning in [`0005`](../../research/2026-06-08/0006-claude-rag-local-llm-gpu-serving.md)):

| Need a local LLM? | For what | Model size |
| --- | --- | --- |
| **Yes** | index-time **contextualization** (Anthropic Contextual Retrieval — the best-supported retrieval lever) | 12–30B |
| **Yes** | **answer generation** (the answer-quality cohort) | 32–70B |
| **Yes (advisory)** | **faithfulness judging** (Lynx / FaithJudge) + a CPU NLI core (HHEM) | 8–70B |
| Optional | Doc2Query / query decomposition / HippoRAG triples | 7–70B |
| **No** | dense / sparse / **reranking** retrieval (these are GPU-*served* models, not chat LLMs) | — |
| **No** | the Adaptive-RAG router / self-query / CRAG evaluator | 22M–770M / rules |

There is also an **LLM-free contextualization path** (`pplx-embed-context-v1`, MIT) if you'd
rather not run a generator for indexing — but answer-gen and judging still want one, so the
recommendation is **stand up the local stack**. Retrieval itself never needs a generative LLM.

### Local dependencies to install in advance

Keep the current **CPU-portable default** (`setting-up-rag` [SETUP.md](../../../.agents/skills/setting-up-rag/SETUP.md)):
Python venv + `qdrant-client[fastembed]` + Qdrant. **Add, for the GPU campaign on this
workstation** (details in [`0005` §6](../../research/2026-06-08/0006-claude-rag-local-llm-gpu-serving.md)):

- **Drivers/runtime:** NVIDIA driver + CUDA for Blackwell (SM 12.0; confirm FP4 kernels).
- **Serving:** **vLLM** (source/nightly with `torch_cuda_arch_list=12.0`; answer-gen + judge),
  **SGLang** (prefix-heavy contextualization), **TEI** and/or **Infinity** (GPU embedder +
  reranker + SPLADE).
- **Models (HF pulls):** Qwen3-Embedding-{0.6B,4B,8B}, Qwen3-Reranker-4B, mxbai-rerank-v2,
  `Splade_PP_en_v1`, Qwen3-32B (FP8), Llama-3.3-70B (FP8), Gemma-3-27B, a contextualizer
  (Qwen3-30B-A3B or Gemma-3-12B), Lynx-8B/70B, HHEM-2.1-Open; optionally `pplx-embed-context-v1`.
- **Chunking/eval:** `tree-sitter` + grammars (C++/CUDA/TS/Python/shell) or `chonkie[code]`;
  `ragas` pointed at the local endpoints.
- **Disk:** ~70 GB for an FP8 70B + embedder/reranker weights + a larger Qdrant index (a 4096-d
  8B embedder is ~10.7× the 384-d baseline → enable int8 quantization).

## Phase-0 harness wiring (do this before any experiment)

The harness's Phase-0 in-process eval ([`improving-context-retrieval-skills`](../../../.agents/skills/improving-context-retrieval-skills/SKILL.md))
is the measurement bed. Wire the Phase-1 set into it (`gold.py`), per [`0003` §"Feeding Phase 2"](0003-rag-eval-set-phase-1.md):

1. **Per-repo corpora.** Each repo is its own corpus; index `domain=code` with `--kind code`,
   `domain=nl` with `--kind md`. Sentinels → sentinel-mode `qrels`; hand-pinned `primary` paths
   → grade-2 labels.
2. **Self-reference exclusion (critical).** Add `plans/2026-06-08/0003-rag-eval-set-phase-1*`
   **and this plan + the three research notes** to `gold.py`'s `EXCLUDE_GLOBS`, so a retriever
   can't "answer" a `coding-agent-skills` query by returning the eval file that quotes its own
   sentinel. The five external repos have no such hazard.
3. **Domain ↔ corpus-kind guard.** Score `domain=code` only against the code corpus and
   `domain=nl` only against prose (`check-retrieval.py --corpus-kind … --domain …`). **Report
   code and prose cohorts separately at every step** — never average away a regression in one to
   flatter the other.
4. **Enrich the index payload.** `index.py` currently writes only `{doc_id, chunk_idx, kind,
   text}`. Add `repo`, `lang`, `doc_type` (and `kind=code|md|transcript`) — required for
   self-query filtering, cohort scoring, and the dual-field pattern. This is a one-time re-index.
5. **Establish the baseline.** Current CPU stack (`bge-small` + bm25 + RRF + MiniLM rerank),
   recall@20 / precision@5 / nDCG@10 / MRR + sentinel factuality + retrieval latency p50/p95,
   on the dev / held-out split, **per cohort**. This is the number every experiment is judged
   against.

## The Phase-3 experiment roadmap (ordered: confidence × cost, cheapest first)

Each rung is an A/B with the keep/revert rule, recorded as **one benchmark file per experiment**
under [`docs/benchmarks/`](../../benchmarks/) naming what changed and which metrics moved
(continuing the `0005`–`0009` series). Re-index only where marked.

### 3.1 — Free / re-index-free wins (no GPU; highest confidence)
- **Per-cohort weighted RRF** — up-weight sparse for code, dense for prose; grid-search on the
  split. **Mind Qdrant's RRF `k` default = 2** (not 60). _[no re-index]_
- **Lost-in-the-middle context reordering** — best-reranked chunks at the prompt's start/end.
  Verify it doesn't hurt single-span code. _[answer-time]_
- **Citation-enforced prompting + mechanical citation-existence check** (cited chunk-id/line
  must exist) — the strongest code-cohort faithfulness lever. _[answer-time]_
- **High-quality / exact HNSW** (`m=32`, `ef_construct=400`, raise `hnsw_ef`) — removes ANN
  approximation as a recall-loss source; cheap at 6-repo scale. _[rebuild]_

### 3.2 — LLM-free index-time wins (re-index; stay CPU-portable)
- **Contextual chunk headers** (`repo/path::symbol` for code; `session-title+date+project` for
  transcripts) before embedding **and** BM25. _[re-index]_
- **Parent-document / small-to-big retrieval + dual-field** (`raw_text` for sentinels/citation,
  `contextualized_text` for embed/BM25). _[re-index]_
- **cAST AST chunking** — lower priority (Pareto-equal to the current block-packed chunker per
  arxiv 2605.04763); test only if headers + parent retrieval plateau. _[re-index]_

### 3.3 — GPU substrate upgrades (stand up TEI/Infinity + vLLM)
- **GPU reranker swap** — the dominant CPU latency cost. A/B **mxbai-rerank-v2** (Apache,
  drop-in) and **Qwen3-Reranker-4B** (max code, **with a validated vLLM recipe + score-sanity
  check** — open bugs #20532/#21681). Re-tune `top_n` per cohort. _[answer-time]_
- **Dense embedder A/B** — **Qwen3-Embedding 0.6B vs 4B vs 8B** vs `bge-small`, **named-vector
  dual arm** (`dense_code` + `dense_prose`), int8+rescore, **instruction prefixes wired into
  both index and query paths**. _[re-index]_
- **Sparse for prose** — A/B `Splade_PP_en_v1` (Apache) on the nl cohort; **keep BM25 for code**
  (turn IDF off for SPLADE). _[sparse re-index]_

### 3.4 — LLM-backed index-time contextualization (Card B, prefix-cached)
- **Anthropic Contextual Retrieval (LLM)** vs **pplx-embed-context (LLM-free)** — on the **nl
  cohort first** (transcripts/design docs), dual-field, group chunks per document for prefix
  caching. Gate per cohort, **not** on the published ConTEB/Anthropic numbers; small-local-model
  contextualization quality is the explicit risk to A/B. _[re-index]_
- **Doc2Query document expansion** — prose only, into a **separate field** so code identifiers
  aren't diluted. _[re-index]_

### 3.5 — Query routing + hard-tail architectures (query-side; little/no re-index)
- **Adaptive-RAG complexity router** (CPU MiniLM/TF-IDF) → single-step for easy code,
  **query-decomposition / iterative** for hard nl/multi-hop. Label a 3-class router on the 207-Q
  set or start heuristic. **Do not** apply HyDE/multi-query to code.
- **Self-query metadata filtering** (soft filters on `repo`/`lang`/`kind`) — needs the §Phase-0
  payload enrichment.
- **CRAG evaluator** — reuse the rerank score for *answer-vs-abstain* (drop web fallback).
- **HippoRAG 2** — experimental, **nl/multi-hop only, fused** with the RRF list; skip if the
  triple graph over transcripts is noisy. (Graph re-architecture is **not** justified for this
  recall-headline corpus — see [`0004` §C](../../research/2026-06-08/0005-claude-rag-contextual-routing-faithfulness.md).)

### 3.6 — Answer generation + faithfulness measurement
- **Local generator** (Qwen3-32B FP8 primary; Llama-3.3-70B FP8 ceiling; Gemma-3-27B for the
  xiang-qi Chinese terms) on vLLM. Pick on **your own corpus eval**, not the circulating
  (contested) numbers.
- **Faithfulness scoring** — **HHEM-2.1-Open** (CPU, permissive, deterministic) as the
  default-friendly core; **Lynx-8B/70B + FaithJudge** as advisory GPU judges, under strict
  **judge hygiene** (temp=0, pinned model/revision/prompt, position-swap, don't share family
  with the generator). Keep closed-book + non-response (confabulation) accounting.
- **Nugget-based recall** (AutoNuggetizer) — A/B on a subset before paying authoring cost (weak
  per-topic correlation may not change keep/revert vs single sentinel).
- **Code-cohort calibration** — every faithfulness signal above is prose-validated; calibrate
  against a hand-labeled slice of the 137 code answers **before** trusting any code-cohort score.

## Keep/revert discipline and exit criteria

- **One attributable change at a time, fresh index, per-cohort scoring.** Keep only if the
  headline metric (recall@20 for retrieval; sentinel/faithfulness for answer-gen) holds-or-rises
  **clear of noise** and no other slice regresses (code vs prose, easy vs hard), with
  latency/index-cost acceptable. Else revert. Record each in a `docs/benchmarks/` file.
- **Published-default vs campaign config are separate artifacts.** The published
  `setting-up-rag` default stays CPU-portable and **Apache/MIT-licensed** (bge-small + MiniLM +
  bm25 + RRF). The GPU campaign may use heavier/non-commercial models locally; only changes that
  also help (or at least don't regress) the portable default — or that are clearly documented as
  the GPU upgrade — get folded into the skill.
- **Exit when**, across consecutive rounds and **both cohorts**: recall@k / nDCG@10 high and
  stable-or-rising on the best cell vs the GOLD baseline; faithfulness high (multi-sentinel +
  closed-book clean); latency p50/p95 stable-or-down; and further changes stop helping. This
  mirrors the harness's own exit bar.

## Risks and caveats (carried from the verification)

1. **MTEB/BEIR deltas may not transfer.** Every number is generic-benchmark or vendor
   self-report; MTEB-Code is Python/web, not C++23/CUDA/transcripts; a 207-Q set can saturate
   recall@20. **The only decision-grade number is the local per-cohort eval.**
2. **Licenses gate the published default.** jina-reranker-v3, SPLADE-v3, Provence, NV-Embed-v2,
   jina-v4 are non-commercial → GPU-campaign-only, never the shipped default.
3. **No NVLink** → one model per card; a 70B at long (128K) context may need both cards,
   conflicting with "embedder/reranker on the spare card" — budget context length.
4. **Qwen3-Reranker on vLLM** needs `hf_overrides` and has open score-correctness bugs —
   validate scores before trusting the rerank.
5. **Contextualization quality from a small local model** (vs Claude Haiku, which generated
   Anthropic's headline lifts) is unproven — A/B the contextualizer model, not just the on/off.
6. **Prefix-caching speedups are workload-dependent** — measure realized throughput locally;
   group each document's chunks contiguously (vLLM #12080) or the win shrinks.
7. **All faithfulness tooling is prose-validated** — the code-cohort calibration check (§3.6) is
   the single highest-value de-risking action.

## Provenance

Phase 2 research was run as an 8-axis fan-out (dense embeddings, code embeddings + chunking,
rerankers, contextual retrieval + chunking, query transforms + architectures, answer-generation
+ faithfulness, sparse + fusion + vector-DB knobs, local-LLM + GPU serving), each web-researched
then **adversarially verified** by an independent skeptic agent that re-checked every concrete
number, spec, and license. Findings are consolidated into research notes
[`0003`](../../research/2026-06-08/0004-claude-rag-retrieval-substrate.md)/[`0004`](../../research/2026-06-08/0005-claude-rag-contextual-routing-faithfulness.md)/[`0005`](../../research/2026-06-08/0006-claude-rag-local-llm-gpu-serving.md);
this file is the optimization plan they feed. Phase 3 executes the roadmap above.
