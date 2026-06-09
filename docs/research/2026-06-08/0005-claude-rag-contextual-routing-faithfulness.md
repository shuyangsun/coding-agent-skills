# Research: Contextual Indexing, Query Routing, and Answer-Generation Faithfulness

**Date:** 2026-06-08 (last updated 2026-06-09)
**Status:** Research complete — input to [`0005-claude-rag-optimization-phase-2`](../../plans/2026-06-08/0005-claude-rag-optimization-phase-2.md); no skill changes made.
**Area:** contextual retrieval / late chunking, query transforms + adaptive routing, advanced RAG architectures, answer-generation quality, faithfulness measurement (LLM-judge / NLI / nuggets)
**Parent campaign:** "Optimizing RAG Setup" Phase 2 — improving [`setting-up-rag`](../../../.agents/skills/setting-up-rag/SKILL.md) and [`retrieving-context`](../../../.agents/skills/retrieving-context/SKILL.md), measured on the Phase-1 gold set ([`0003-rag-eval-set-phase-1`](../../plans/2026-06-08/0003-rag-eval-set-phase-1.md), 207 Q, 137 `code` / 70 `nl`).
**Sibling notes:** [`0004` retrieval substrate](0004-claude-rag-retrieval-substrate.md), [`0006` local-LLM + GPU serving plan](0006-claude-rag-local-llm-gpu-serving.md).

## Summary

[`0003`](0004-claude-rag-retrieval-substrate.md) covers *what you index and how you match it*.
This note covers the layers **above** the substrate: (a) **contextual indexing** — making each
chunk self-describing before it is embedded; (b) **query-side routing/transforms** — spending
expensive multi-step retrieval only on the hard tail; (c) **advanced architectures** (graph /
agentic RAG); and (d) **answer generation + faithfulness measurement** — the cohort the Phase-2
prompt explicitly asks to optimize, beyond retrieval.

Two cross-cutting findings shape everything here:

1. **Prefer index-time over query-time transforms for this corpus.** 137/207 queries are
   precise code identifiers — exactly the case where query-side expansion (HyDE, multi-query)
   *averages away* the signal. Index-time techniques (contextual retrieval, Doc2Query,
   contextual headers) bridge vocabulary once at indexing with **zero query latency**, so they
   never slow or dilute the easy code cohort.
2. **Everything answer-gen / faithfulness here is PROSE-validated.** Lynx, Provence, RAGAS,
   nuggets — all on QA/medical/finance prose (or, for the one code paper, Python-only). The
   single highest-value action for this mixed C++/CUDA/TS + transcript corpus is an
   **adversarial code-cohort calibration check** before trusting any code-cohort faithfulness
   score.

## A. Contextual indexing — make each chunk self-describing

The worst case in this corpus is a long coding-session **transcript** chunk that says "the
fix" / "this option" with no project named, and pronoun-heavy multi-file design docs. Two ways
to fix it:

| Technique | LLM at index time? | License | Reported lift | Fit |
| --- | --- | --- | --- | --- |
| **Anthropic Contextual Retrieval** | **Yes** (per chunk) | n/a (your model) | top-20 failure −35% / −49% (+BM25) / −67% (+rerank) | best for transcripts + nl-to-code; smaller on pure symbols |
| **pplx-embed-context-v1** (Perplexity) | **No** (context-aware embedder) | **MIT** | ConTEB 81.96 (self-reported, prose) | LLM-free alternative; shippable license |
| **Contextual chunk headers** (path/symbol/title) | **No** (deterministic) | n/a | ~5–15% precision (task-dependent) | code + transcripts; near-zero cost |
| **Parent-document / small-to-big** | No | n/a | cross-file-context +4.2pp (code-completion) | both cohorts; low risk |
| **Late chunking** (embed doc, pool to chunks) | No | needs long-ctx embedder | +1.8–1.9pp avg; +9 nDCG on ConTEB | transcripts; needs long-context embedder |

**Anthropic Contextual Retrieval** prepends a 50–100-token LLM-generated blurb to each chunk
before embedding **and** BM25. Headline numbers are **verified verbatim**: top-20 retrieval
failure cut **35%** (embeddings) / **49%** (+ contextual BM25) / **67%** (+ reranking),
evaluated across domains **including codebases**; one-time cost ~$1.02 / 1M doc tokens **with
prompt caching** — locally **$0**. **Two caveats:** every lift was **Claude-Haiku-generated**,
so small-local-model contextualization *quality* is the open risk to A/B; and a fabricated
"code Pass@10 87%→95%" figure that circulated is **not** in the Anthropic post — drop it.
Requires the **dual-field pattern** ([`0003` §2](0004-claude-rag-retrieval-substrate.md)) and
a full re-index. The local-LLM cost is cheap and one-time — see [`0005`](0006-claude-rag-local-llm-gpu-serving.md).

**pplx-embed-context-v1** (Perplexity, **MIT**, 0.6B/4B, 32K context, released 2026-02-26) is
the standout **LLM-free** route: it runs one bidirectional pass over the whole document so each
chunk's vector already carries document context — the same "the fix" anaphora fix at embed
time, no per-chunk LLM. **But** all its wins (ConTEB 81.96, MTEB 69.66) are **Perplexity
self-reported on prose/QA**, code/transcript lift is unproven, and the runtime is Transformers/
ONNX (**not** SentenceTransformers). A strong GPU A/B arm; `bge-small` stays the CPU default.

**Contextual chunk headers** (deterministic, LLM-free) are the **best recall-lift-per-token**
for code: prepend `repo/path::Class::method`. Pairs with AST chunking. The taxonomy paper
arxiv [2602.16974](https://arxiv.org/abs/2602.16974) is more nuanced than "always helps" —
contextualized chunking improves **in-corpus** retrieval but can **degrade in-document**
retrieval, and *simple structure-based* headers beat LLM-guided ones for in-corpus. So the gain
is task-dependent — measure per cohort.

## B. Query transforms and adaptive routing — protect the easy cohort

The corpus is **bimodal**: 137 precise code/identifier queries (want fast single-step, often
already top of hybrid) and 70 nl queries whose **hard** members are multi-sentinel / multi-file
(want multi-hop). The right shape is a **router**, not a global transform.

- **Adaptive-RAG complexity routing** (arxiv [2403.14403](https://arxiv.org/abs/2403.14403),
  NAACL 2024): a small classifier routes each query to no-retrieval / single-step / iterative
  multi-step. **Corrected facts:** the **classifier is T5-Large (~770M)**; the *generator* is
  FLAN-T5-XL/XXL (don't conflate them). SQuAD (FLAN-T5-XL): Adaptive-RAG **26.80 EM / 38.30 F1
  / 1.37 steps** vs the cheap Adaptive-Retrieval baseline **13.40 / 23.10 / 0.50** — a ~+13.4 EM
  lift. A 2026 follow-up shows a **TF-IDF+SVM router at 93% accuracy / a 22M MiniLM router at
  90%**, so the **router itself needs no large LLM** (CPU-portable). This is the **single best
  fit** for the KEY QUESTION — it lifts the hard tail without taxing the easy code cohort.
  *Open risk:* the open-domain-QA-trained classifier has **no measured transfer** to code+
  transcripts; build/label a 3-class router on the 207-Q set or use a heuristic, and A/B.
- **Query decomposition** (the safe hard-arm): split a multi-faceted question into precise
  sub-queries, retrieve each, synthesize. Each sub-query stays lexically precise, so it
  **preserves** rather than dilutes signal — safer than HyDE/multi-query for code. Gate behind
  the router.
- **Iterative / agentic retrieval** (IRCoT / Self-Ask): the multi-step "C" arm — reads results,
  issues the next hop, repeats until sentinel coverage. The accuracy ceiling for the hard
  bucket but **8–10× latency**; **catastrophic if applied to all 207 Q** — gate strictly.
- **Doc2Query / document expansion at index time** (append LLM-predicted questions to chunks):
  pre-bridges question/answer vocabulary with **zero query latency**. Good for prose; for code,
  keep expansions short in a **separate field** so they don't crowd out exact identifiers.
- **Self-query metadata filtering**: an LLM (or rules) extracts `repo` / `lang` /
  `kind=code|md|transcript` filters from the query → Qdrant payload condition. Cheap,
  lexical-safe, lifts precision@5/latency. **Correction:** `index.py` currently writes only
  `{doc_id, chunk_idx, kind, text}` — this needs a **re-index to add `repo`/`lang`/`doc_type`
  payload** first. Make filters **soft** (don't drop the gold chunk on mis-extraction).
- **HyDE and multi-query / RAG-Fusion are HAZARDS here** — they underperform on
  entity/identifier queries and add latency. Gate strictly to the nl cohort if used at all.

## C. Advanced architectures — graph/agentic RAG (mostly skip for this corpus)

- **HippoRAG 2** (arxiv [2502.14802](https://arxiv.org/abs/2502.14802)): open-KG + Personalized
  PageRank that *ranks passages* (so it **fuses with** Qdrant, doesn't replace it). Strong
  multi-hop (+9.5 F1 2Wiki) and flat-to-up on simple QA. **But all its evidence is prose-only**
  (Wikipedia/medical/novels); triple extraction over C++/CUDA and dialog transcripts is the
  risk. **Experimental arm only, scoped to the nl/multi-hop subset, fused** — never on code.
- **GraphRAG / LightRAG / LazyGraphRAG / graphify:** the repo **already rejected** these vs
  Qdrant ([`0001`](0001-contextual-retrieval-with-graphrag.md)/[`0002`](0002-contextual-retrieval-and-graphify.md),
  benchmark [`0008`](../../benchmarks/2026-06-08/0008-qdrant-vs-local-graphrag.md)). New evidence
  reinforces it: the bias-corrected audit arxiv [2506.06331](https://arxiv.org/abs/2506.06331)
  **drops LightRAG's win-rate from 66.7% to 39.06%** (a loss to naive RAG). Their strength is
  corpus-wide theme summarization, which a **recall@20-headline** gold set does not reward.
- **CRAG (Corrective RAG)** (arxiv [2401.15884](https://arxiv.org/abs/2401.15884)): a
  lightweight retrieval-confidence evaluator that gates correction. **Useful pattern** — reuse
  the existing **cross-encoder rerank score** as the evaluator to decide *answer vs abstain*
  (reduces confident hallucination when no doc supports the question). Drop the web-search
  fallback (irrelevant for a closed local corpus); replace with local re-query / abstain. Note
  the clinical-benchmark numbers that circulated are **misattributed** (they belong to a
  Haystack pipeline, not CRAG); only Self-RAG's 5.8% lowest-hallucination is corroborated.
- **Self-RAG:** needs a fine-tuned generator (reflection tokens) — skip the training, keep
  CRAG's evaluator pattern.

## D. Answer generation + faithfulness — the second metric family

The prompt asks to optimize **answer-generation** metrics, not just retrieval. The harness
today scores answer factuality only by **gold sentinel string containment**. Upgrades:

**Generation-time wins that need NO local LLM (adopt first):**
- **Context reordering against "lost in the middle":** place the highest-reranked chunks at the
  **start and end** of the prompt, bury weaker ones mid-context. NoLiMa shows GPT-4o
  **99.3% → 69.7%** as relevant context moves to 32K depth; the stack feeds `top_k=20` chunks,
  exactly where mid-context burial bites. Free, model-less, CPU-portable. Verify it doesn't hurt
  the **single-span code** cohort.
- **Citation-enforced / grounded prompting + a MECHANICAL citation check:** instruct the
  generator to answer only from chunks and emit inline `[chunk-id:line]` citations; then
  **deterministically verify each cited chunk ID / line range actually exists**. This is the
  **strongest code-cohort faithfulness lever found** (arxiv [2512.12117](https://arxiv.org/abs/2512.12117),
  92% on Python repos via exactly this check). The prompt **alone is insufficient** —
  strongly-trained models exhibit *knowledge override* / phantom citations; the mechanical
  check is the cheap deterministic backstop.

**Faithfulness measurement (advisory, never a gate — matches the harness's METRICS.md):**
- **HHEM-2.1-Open** (NLI cross-encoder, ~600MB, CPU, permissive): the **default-friendly,
  deterministic faithfulness core** — 85–90% human agreement on RAGTruth/HaluBench, runs on the
  CPU-portable default. (Unlike Provence below, it is permissively licensed.)
- **Patronus Lynx-8B / 70B**: purpose-built RAG hallucination classifier. Lynx-70B **87.4% on
  HaluBench** (beats GPT-4o 86.5%, far above RAGAS-faithfulness 66.9%); 4-bit AWQ ~40GB fits one
  Blackwell card; Lynx-8B is trivial. **Prose-validated** — calibrate on code answers first.
- **FaithJudge-style few-shot LLM-judge** (local Llama-3.3-70B 77.5% / Qwen-2.5-72B 73.2% on
  FaithBench): transparent, editable exemplars — add code/transcript exemplars to cover what
  Lynx misses. Advisory only (≈10pt below proprietary judges on prose).
- **RAGAS context-precision/recall**: maps onto the harness's existing retrieval-vs-generation
  fault split; weak as a *faithfulness detector* (66.9% HaluBench) and claim-decomposition is
  ill-defined for code — use for the diagnostic split, not the headline gate.
- **Nugget-based recall (TREC AutoNuggetizer):** graded generalization of single-sentinel
  containment (the Phase-1 gold answers already have sentences to derive nuggets from). Strong
  **aggregate** ranking correlation (Kendall 0.887) but **weak per-topic** (0.36–0.54), so on a
  207-item set it may not change per-question keep/revert vs single sentinel — A/B on a subset
  before paying the authoring cost.
- **Provence context pruning** (ICLR 2025, arxiv [2501.16214](https://arxiv.org/abs/2501.16214)):
  fuses pruning into the reranker (nearly free), cuts context-tokens-to-answer. **But license is
  CC-BY-NC-ND** (non-commercial **and** no-derivatives) → **GPU box only, not the published
  default**; it has **zero code in its eval** (sentence-pruning can delete needed code lines) →
  prose/transcripts only. Substitute a permissive pruner / HHEM for the default.

**Judge hygiene (mandatory to keep numbers reproducible and the judge non-gating):** temp=0 +
fixed seed; **pin judge model + revision + prompt as part of the metric definition**;
randomize/swap option order (position bias ≈10–15pt); watch verbosity (15–30pt) and
self-preference (10–25%, so **don't judge with the same family as the generator** for the
headline); calibrate against a human-labeled slice of the 207-Q set. **SGLang ships
batch-invariant deterministic serving** (Sept 2025), so deterministic local judging on the
Blackwell box is production-ready; the NLI-classifier argmax route is the robust fallback. Keep
the **closed-book + non-response (confabulation) accounting** the harness already names, so
abstain-gaming and leakage are caught.

**Generator model choice** (detail in [`0005`](0006-claude-rag-local-llm-gpu-serving.md)): Qwen3-32B
FP8 primary (strong code), Llama-3.3-70B FP8 quality ceiling, Gemma-3-27B for the xiang-qi
Chinese terms. The specific Qwen3 faithfulness/SimpleQA numbers that circulated are
**unsourced/contested** — pick the generator on a re-pulled-at-campaign-time leaderboard plus
your own corpus eval, not on those figures.

## Decision signals (carried into the Phase-2 plan)

1. **Index-time, not query-time** is the default for this code-heavy corpus.
2. **Contextual headers + parent retrieval + dual-field** (LLM-free) ship first; then A/B
   **Anthropic Contextual Retrieval** (LLM) vs **pplx-embed-context** (LLM-free) on the nl
   cohort — gated per cohort, not on the published ConTEB/Anthropic numbers.
3. **Adaptive-RAG router (CPU) + query decomposition** for the hard nl/multi-hop tail; leave the
   easy code path single-step. **HyDE/multi-query are hazards** — nl-only if at all.
4. **Skip graph re-architecture** (HippoRAG 2 experimental-only, fused, nl-only); keep CRAG's
   evaluator pattern for answer-vs-abstain.
5. **Answer-gen: adopt the free wins** (lost-in-the-middle reorder, citation + mechanical
   check). **Measure faithfulness** with HHEM (default) + Lynx/FaithJudge (advisory, GPU),
   under strict judge hygiene.
6. **Code-cohort calibration of every faithfulness signal is the single highest-value action**
   — all of these are prose-validated.

## Sources

- Anthropic Contextual Retrieval: [news/contextual-retrieval](https://www.anthropic.com/news/contextual-retrieval); ConTEB: [HF blog manu/conteb](https://huggingface.co/blog/manu/conteb)
- pplx-embed: [Perplexity research](https://research.perplexity.ai/articles/pplx-embed-state-of-the-art-embedding-models-for-web-scale-retrieval), [HF card](https://huggingface.co/perplexity-ai/pplx-embed-context-v1-4b)
- Late chunking: [arxiv 2409.04701](https://arxiv.org/abs/2409.04701); contextualized-chunking taxonomy: [arxiv 2602.16974](https://arxiv.org/abs/2602.16974)
- Adaptive-RAG: [arxiv 2403.14403](https://arxiv.org/abs/2403.14403); HippoRAG 2: [arxiv 2502.14802](https://arxiv.org/abs/2502.14802); CRAG: [arxiv 2401.15884](https://arxiv.org/abs/2401.15884); GraphRAG win-rate audit: [arxiv 2506.06331](https://arxiv.org/abs/2506.06331)
- Lost-in-the-middle / NoLiMa: [TACL 2024 "Lost in the Middle"](https://arxiv.org/abs/2307.03172); code citation + mechanical check: [arxiv 2512.12117](https://arxiv.org/abs/2512.12117)
- Faithfulness: Patronus Lynx [arxiv 2407.08488](https://arxiv.org/abs/2407.08488); FaithJudge/Vectara [arxiv 2505.04847](https://arxiv.org/abs/2505.04847); Provence [arxiv 2501.16214](https://arxiv.org/abs/2501.16214); AutoNuggetizer [arxiv 2411.09607](https://arxiv.org/abs/2411.09607) / [2504.15068](https://arxiv.org/abs/2504.15068); [RAGAS docs](https://docs.ragas.io/)
