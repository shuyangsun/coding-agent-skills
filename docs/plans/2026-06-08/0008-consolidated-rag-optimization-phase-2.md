# Plan: Consolidated RAG Optimization Phase 2

- **Date created:** 2026-06-09
- **Status:** Phase 3 **Waves 0-3 executed** (2026-06-09), **Wave 4 COMPLETE** (2026-06-10), **Wave 5 COMPLETE** (2026-06-10, evening), **Wave 6 COMPLETE** (2026-06-10, late night) on the Ubuntu GPU box `delos`. Wave-4 steps 1/1b (contextual retrieval + generator comparison) ran in the morning (`0014`/`0015`, the top win); steps 2-6 ran in the afternoon: `0016` late chunking (**rejected**), `0017` session metadata (**weak/optional**), `0018` Doc2Query (**code win, campaign**), `0019` reader/packing (**deferred to Wave 7**). Wave 5 (`0020`): the deterministic graph/source-map **overlay is a measured REJECT** — keepers: the **twin-baseline jitter control** and the `w4llm + bge-reranker-v2-m3` lever measurement. Wave 6 (`0021`): **every adaptive query-time mechanism REJECTS** (self-query, decomposition, HyDE/multi-query, the fitted CRAG confidence gate, rerank guards), but the wave's reranker A/B — **`Qwen3-Reranker-4B` faithfully served (vLLM seq-cls conversion + instruction template)** — is the **campaign's largest single-variable win** (held-out nDCG **+0.090** → **0.848**, pMRR +0.107 → 0.800, hit@5 +0.144 → 0.991, replicated) and is **promoted as the always-on campaign reranker**; the 0020 "coverage-vs-precision lever" framing is retired. See "Phase 3 Execution Progress" below and `docs/benchmarks/2026-06-10/0014`-`0021`. **Wave 7 not yet started** (it now also owns the agentic-loop question and the two named qwen caveat slices).
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

## Phase 3 Execution Progress (2026-06-09)

Waves 0-3 executed on the Ubuntu GPU box `delos`. The benchmark runner
(`harness/run_benchmark.py`, `report.py`, `serve_infinity.py`) drives the 207-query gold set
over a **dedicated isolated Qdrant on `:6343`** (never the unrelated face-embed `:6333`).
Full reports + TSV/JSON: [`docs/benchmarks/2026-06-09/0010-0013`](../../benchmarks/2026-06-09/).

| wave                                   | benchmark                                                                          | headline                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | disposition                                                   |
| -------------------------------------- | ---------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| **0** baseline                         | [`0010`](../../benchmarks/2026-06-09/0010-wave0-baseline-rag.md)                   | declared `plain-current` baseline; closed-book/wrong-context controls clean; RAG is **18× more token-efficient** than the ripgrep floor at better ranking                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | reference floor                                               |
| **0** pre-flight                       | `0010`                                                                             | corpus must **respect `.gitignore`** — alpha-zero was **84% git-ignored `artifacts/` self-play traces** (17.6k→2.9k chunks)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | **promoted to skill**                                         |
| **0/1** reranker                       | `0010`/`0011`                                                                      | shipped **CPU MiniLM reranker HURTS** held-out ranking (nDCG −0.010, hit@5 −0.081) and costs **40× latency**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | drop from portable default                                    |
| **1** re-index-free                    | [`0011`](../../benchmarks/2026-06-09/0011-wave1-reindex-free-rag.md)               | **NEGATIVE result** — no RRF-`k`/weight/DBSF/prefetch/HNSW-exact knob beats baseline on held-out (dev gains didn't replicate); ANN is not lossy                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | keep defaults                                                 |
| **2** contextual headers               | [`0012`](../../benchmarks/2026-06-09/0012-wave2-contextual-headers-rag.md)         | deterministic `[repo] path :: symbol/heading (lang)` header → held-out **nDCG +0.056, primary-MRR +0.055, NO slice regresses**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | **PROMOTE (top win)**                                         |
| **3** reranker bge-m3 (GPU)            | [`0013`](../../benchmarks/2026-06-09/0013-wave3-gpu-substrate-rag.md)              | `bge-reranker-v2-m3` strictly beats MiniLM (4.5× faster), **fixes the 2 weak repos**, big answer-grounding gains; a coverage-vs-precision lever vs no-rerank                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | campaign reranker                                             |
| **3** embedder bge-base                | `0013`                                                                             | `bge-base` (768-d) vs `bge-small` (384-d) is a **wash** — nl +0.023 nDCG but code −0.008, ~flat overall at 2× vector size; representation (headers) ≫ embedder swap                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | `bge-small` stays portable                                    |
| **4** contextual retrieval (gemma-4)   | [`0014`](../../benchmarks/2026-06-10/0014-wave4-contextual-gemma4-rag.md)          | LLM 1–2-sentence situating context per chunk → embedded field (raw_text stays verbatim): held-out **nDCG +0.031, primary-MRR +0.033, sentinel +0.080, hit@5 +0.054**, **code domain nDCG +0.045 / sentinel +0.123**; nl already at ceiling (flat); **index-time only — no query-latency or answer-context cost**                                                                                                                                                                                                                                                                                                                                                                                                                       | **PROMOTE (campaign / GPU)**                                  |
| **4** apply-to + header ablation       | `0014`                                                                             | Contextualize **all chunks** (code+md) ≫ prose-only (code nDCG +0.045 vs +0.019) — the "code-dilution" worry was wrong; **keep the deterministic header** (dropping it regresses nl, e.g. website-nl −0.084)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | all-chunks + header                                           |
| **4** generator-model comparison       | [`0015`](../../benchmarks/2026-06-10/0015-wave4-generator-model-comparison-rag.md) | context generator matters on a hard corpus: **Nemotron-120B held-out code nDCG +0.089 (~2× gemma-4-31B's +0.037), no code regression** (but verbose contexts regress some nl); gemma-4≈Qwen-27B. Serving: vLLM NVFP4 ~8 ch/s ≫ TRT-LLM Docker ~2.6–3.4 ch/s ≫ llama.cpp GGUF-Q8 ~0.3–0.8 ch/s                                                                                                                                                                                                                                                                                                                                                                                                                                          | gemma-4 **default** (throughput); Nemotron **ceiling** (code) |
| **4** late chunking (bge-m3)           | [`0016`](../../benchmarks/2026-06-10/0016-wave4-latechunk-rag.md)                  | **NEGATIVE** — LLM-free contextual embedding via late chunking (whole-doc mean-pool, bge-m3) regresses **every** held-out slice (nDCG −0.115, naive→late −0.079 isolates the method); whole-doc pooling **blurs** within-doc discrimination. Contextual retrieval wins by **sharpening** per-chunk identity, not averaging                                                                                                                                                                                                                                                                                                                                                                                                             | **REJECT**                                                    |
| **4** session metadata (deterministic) | [`0017`](../../benchmarks/2026-06-10/0017-wave4-session-meta-rag.md)               | LLM-free session capsule (`session <id> <vendor> <date> — <name>; files: …`) on transcript chunks: held-out overall nDCG **+0.019**, on-target `session-prompting` **+0.056** with **website transcripts → perfect (1.000)**. The genuinely-new signal is the **mentioned-file list**. Also bounded the **HNSW re-index noise floor at ~0.03** (a no-capsule repo moved −0.034 between identical-text builds)                                                                                                                                                                                                                                                                                                                          | **optional portable** (transcript corpora)                    |
| **4** Doc2Query (gemma-4)              | [`0018`](../../benchmarks/2026-06-10/0018-wave4-doc2query-rag.md)                  | predicted queries → separate BM25 field: **all-chunks** is a robust **code** win (held-out +0.030 sparse / +0.060 both; dev +0.043 / +0.076) but costs nl (alpha-zero design-docs −0.062). **Prose-only REJECTED** (regresses code — 3rd confirmation of "never restrict index-time context to prose"). ≈ contextual-retrieval quality but **less clean** on nl                                                                                                                                                                                                                                                                                                                                                                        | **campaign** (alt to ctx-retrieval)                           |
| **4** reader/packing arms              | [`0019`](../../benchmarks/2026-06-10/0019-wave4-reader-packing-rag.md)             | packing **order** (source/score/parent-first) is **order-invariant** under every retrieval-stage metric (file-rank, set-membership sentinel/hit, sum-of-tokens) → cannot be measured here; the discriminating metric is answer faithfulness                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | **deferred to Wave 7**                                        |
| **5** graph/source-map overlay         | [`0020`](../../benchmarks/2026-06-10/0020-wave5-graph-overlay-rag.md)              | deterministic file graph (import/pair/test/link/mention, `wave5_graph.py`) boosts + fetches neighbors of the top fused files, **query-time only** (shares the baseline's collection): strong boost **destroys ranking** (held-out nDCG **−0.208** — the flat RRF rank-score curve lets any useful additive boost leapfrog dozens of ranks); tie-break λ=0.05 is **aggregate-positive but slice-redistributive** (overall +0.018…+0.023 replicated, **but** website-nl pMRR −0.077 / ttt-nl −0.083 / easy-nl −0.125 **identical across two independent draws** = deterministic damage); **expand-then-rerank ≈ rerank alone** (nDCG −0.001)                                                                                             | **REJECT (all variants)**                                     |
| **5** rerank lever on campaign best    | `0020`                                                                             | first measurement of `w4-ctx-llm-gemma4-all` **+ `bge-reranker-v2-m3`** (the Wave-3 "compose" recommendation): a coverage-vs-precision lever on the campaign winner — held-out hit@5 **+0.045**, sentinel **+0.015**, code R@20 **1.000** / code sentinel **+0.030**, at nDCG **−0.045** / pMRR −0.052 and 141 ms                                                                                                                                                                                                                                                                                                                                                                                                                      | documented lever (Wave 7 decides)                             |
| **5** query-time noise floor           | `0020`                                                                             | **twin-baseline jitter control**: Qdrant server-side RRF tie order is nondeterministic per call → metric floor **±0.005** on 111-query held-out aggregates, up to **±0.07** on single repo×domain cells; composes with `0017`'s ~0.03 re-index floor. Judge slice deltas only against a duplicated-baseline arm + replicated draws                                                                                                                                                                                                                                                                                                                                                                                                     | standing control                                              |
| **6** query routing / adaptive         | [`0021`](../../benchmarks/2026-06-10/0021-wave6-query-routing-rag.md)              | every adaptive mechanism **rejects**: self-query soft filters (dev hit@5 −0.031), LLM + deterministic decomposition (held-out flat; ungated regresses hit@5 −0.031), HyDE (dev +0.030 does **not** replicate held-out, sentinel −0.027, invents identifiers), multi-query (R@20 → 1.000 without adding one sentinel chunk), `protect_top1` guards (non-monotonic noise). The fitted CRAG confidence gate (rerank iff `d_top≤0.752 OR d_gap≤0.0215`, 38% fire) **dominates always-bge-rerank on every held-out aggregate** (nDCG +0.008 vs −0.045, sentinel 0.946 vs 0.928) but fails the repeated-cells slice gate (10 cells regress in both draws — adverse selection: it routes to the reranker exactly where the reranker is worst) | **REJECT (all)**                                              |
| **6** reranker A/B (the real fix)      | `0021`                                                                             | **`Qwen3-Reranker-4B` (Apache-2.0) served faithfully** — vLLM seq-cls conversion + official instruction template (untemplated scores are **inverted**: relevant 0.137 < off-topic 0.907 — why Wave 3 never measured it) — always-on, ungated: held-out **nDCG 0.848 (+0.090), pMRR 0.800 (+0.107), sentinel 0.955 (+0.042), hit@5 0.991 (+0.144)**, code nDCG **+0.119** / hit@5 **+0.192**, nl positive, replicated to the 3rd decimal; **exceeds the oracle of gating bge-m3**. Caveats (both draws): alpha-zero pMRR (−0.008/−0.067) and `session-prompting` (−0.012/−0.018) regress while their pack coverage improves → Wave-7 adjudicates. 555 ms/query, ~28 GB                                                                  | **PROMOTE (campaign reranker, always-on)**                    |

**Current best config after Wave 0-6** (Wave 6 upgraded the campaign reranker; the portable default is unchanged):

- **Portable default (CPU, ships):** bge-small dense + bm25 sparse, RRF, **contextual headers ON, rerank OFF**, `top_k=20` → held-out nDCG@10 **0.737**, primary-MRR **0.675** (vs shipped baseline 0.670 / 0.586). **Wave-4 LLM techniques (contextual retrieval, Doc2Query) stay campaign-side** (index-time LLM). The one Wave-4 portable-eligible add is the **deterministic session capsule** (`0017`) — **optional**, for corpora that contain session/coding transcripts (it drove website transcript retrieval to perfect); not a forced default since its lift is small and corpus-shape-dependent. Wave 6 added **nothing portable** (its only portable-eligible arms — self-query filters, deterministic decomposition — both rejected).
- **Campaign (GPU):** header **+ LLM situating context on all chunks** (Wave 4, gemma-4) **+ `Qwen3-Reranker-4B` always-on** (Wave 6, `w6-rrk-qwen4b`: vLLM seq-cls conversion, official instruction template via `rerank.template="qwen3"`, top_n=50) → held-out nDCG@10 **0.848**, primary-MRR **0.800**, sentinel **0.955**, hit@5 **0.991**, R@20 0.995 (code: nDCG 0.840, hit@5 0.986; replicated 0.845/0.795/0.955/0.991). **This retires the 0020 lever framing** — with a faithfully-served SOTA reranker, always-on strictly beats no-rerank AND every gated/guarded variant; `bge-reranker-v2-m3` and the CRAG gate survive only as latency knobs (147/275 ms vs 555 ms). Named caveats for Wave 7: alpha-zero pMRR and `session-prompting` ranking regress slightly in both draws while their pack coverage (sentinel/hit@5) improves — answer-stage metrics decide whether rank-1 precision matters there. **Doc2Query all-chunks** (`0018`) remains the code-priority alternative to contextual retrieval; **stacking** (situating context in dense + predicted queries in BM25) is still untested. All index-time techniques leave query latency unchanged; the reranker adds ~515 ms/query campaign-side.
- **Methodology note (from `0017` + `0020`):** two distinct noise floors. (1) **Re-index floor** (`0017`): Qdrant HNSW re-index non-determinism is ~**0.03** on a single hard slice — avoid entirely by sharing one collection across arms when the indexed text is identical (what `0020` does). (2) **Query-time floor** (`0020`): server-side RRF tie order jitters per call — ±0.005 on 111-query aggregates, up to **±0.07 on single repo×domain cells**, measured by running the baseline twice as a **twin arm** in the same benchmark. A slice regression is real only if it repeats across independent draws (the `0020` tiebreak arm's nl cells did — same cells, same magnitudes — which is what rejected it).

**Promoted into the shipped `setting-up-rag` this session** (proven, CPU-clean, license-neutral):

1. **`.gitignore`-respecting corpus** — `rag_lib.load_corpus` now skips git-ignored generated/build output (`git ls-files -co --exclude-standard` allowlist).
2. **Comprehensive code extensions** — `CODE_EXTS` + `CODE_FILENAMES` now cover C/C++/CUDA/CMake/shell/config (the loader indexed _zero_ C++ before; alpha-zero 155→301 files).

**Recommended next promotion** (proven at harness level; apply with a measured shipped-chunker
implementation): **contextual headers** — the +0.055 win, deterministic, no LLM. (The skill's
SKILL.md §6 documents the _LLM_ contextual-retrieval upgrade; the deterministic header itself is
still a portable-default promotion to land in the shipped chunker.)

### Wave-4 synthesis — one mechanism explains all five experiments

Across `0014`-`0018`, index-time context helps **iff it sharpens a chunk's identity, and hurts iff
it blurs it**, and it must apply to **code**, not just prose:

- **Sharpen → win:** LLM situating context (`0014`, cleanest) and Doc2Query predicted queries
  (`0018`, code win) each add _distinct_ per-chunk signal. Both are campaign (index-time LLM).
- **Blur → lose:** late chunking (`0016`) pools each chunk toward a _shared_ document vector,
  collapsing within-document discrimination — rejected on every slice.
- **Never prose-only:** restricting context to md chunks regresses code in **both** `0014` and
  `0018` (it makes prose chunks artificially competitive). Apply to all chunks.
- **Deterministic, targeted, portable:** the session capsule (`0017`) adds a cheap mentioned-file
  signal that helps the transcript slice it targets — optional, corpus-conditional.
- **Reader packing** (`0019`) is order-invariant for retrieval metrics → it is a Wave-7 (answer
  faithfulness) experiment, not a retrieval one.

**Still open (not yet run):** Wave-2 parent-window / small-to-big retrieval + code chunk-size
sweeps; the GPU embedder sweep (Infinity embed backend — `qwen3-embedding-4b`/`bge-code-v1` with
Qwen3 prefixes; `serve_infinity.py` serves them, the `infinity_emb v2` CLI is broken so use the
script) — deprioritized after `0013` showed embedder swaps are a wash vs representation, **but
`0021`'s reranker result argues for one revisit**: the same instruction-template fidelity issue
that hid Qwen3-Reranker-4B applies to the Qwen3 decoder _embedders_ (prefix plumbing, Wave-3
step 2); **Wave 7** (answer generation + the deferred `0019` packing arms + the agentic-loop
question + the `0021` caveat slices: alpha-zero pMRR / session-prompting). A
Doc2Query×contextual-retrieval **stack** is a cheap Wave-4 add-on if revisited.

### Wave-5 synthesis — query-time graph forcing is dominated by what already shipped

The overlay's two genuine signals are both better delivered elsewhere: the **mention/link
(source-map) signal** belongs **index-side** (the `0017` capsule and Wave-2/4 headers/contexts
sharpen the same cross-file identity without touching rank math), and **candidate arbitration**
belongs to the **reranker**, whose 60-deep prefetch already contains every file the graph would
inject (`0020`: overlay+rerank ≡ rerank alone). Additive rank boosts on RRF's flat score curve
cannot express "a little more relevant" — at useful strength they reorder dozens of ranks, and at
tie-break strength they trade specific queries down for others up. This closes the prompt-`0005`
graph thread on retrieval: graph mechanisms return, if at all, as **answer-stage bridges**
(Wave 7), not as retrieval overlays.

### Wave-6 synthesis — adaptivity was compensating for a weak arbiter

Wave 6 built the full routing toolkit (deterministic router features, self-query soft filters,
LLM + deterministic decomposition, identifier-protected HyDE/multi-query, a dev-fitted CRAG
confidence gate, rerank guards) and **every piece rejected** — flat or slice-regressive
held-out, with two recurring failure shapes: (1) **dev wins that do not replicate** (HyDE
+0.030 dev → −0.009 held-out: fitted thresholds and LLM-text drift overfit 96 queries), and
(2) **adverse selection** (the confidence gate routes to the reranker exactly the populations
the reranker handles worst — gating can dilute a bad arbiter's damage but never fix it; it
still failed the repeated-cells slice gate). The decisive experiment was the one the routing
was implicitly compensating for: **serving the plan's "SOTA pick" reranker faithfully**.
`Qwen3-Reranker-4B` is a decoder-based scorer whose relevance signal lives behind an
instruction template — untemplated, its scores **invert** (relevant 0.137 < off-topic 0.907),
which is why naive cross-encoder serving never measured it. Templated and always-on it beats
the best gated variant by +0.023 nDCG and the no-rerank base by **+0.090**, exceeding the
oracle ceiling of gating the old reranker. Lesson recorded for the skills: before building
adaptive routing around a component's weaknesses, **verify the component is being used the way
its training assumed** — serving fidelity beat a wave of clever routing.

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
- model pulls — _(2026-06-09: the **embedding + reranker set is already downloaded** to `/mnt/nas/home/ml/model/{embedding,reranker}/`: Qwen3-Embedding-0.6B/4B/8B, Qwen3-Reranker-0.6B/4B, `bge-reranker-v2-m3`, mxbai-rerank-base/large-v2, `Splade_PP_en_v1`, plus bge-small/base-en-v1.5, bge-m3, mxbai-embed-large-v1, multilingual-e5-large-instruct, arctic-embed-l-v2.0, embeddinggemma-300m, code embedders bge-code-v1 / SFR-Embedding-Code-2B_R, and zerank-1-small/2; full sizes + licenses in [`0005`](../../prompts/2026-06-08/0005-optimizing-rag-setup.md) → "Models staged on the NAS". **Generative + judge LLMs still to pull:** Qwen3-32B, Llama-3.3-70B, Gemma-3-27B, Qwen3-30B-A3B or Gemma-3-12B, Lynx-8B/70B, and HHEM-2.1-Open — `gemma-4`/Gemma-4-31B-IT is already served.)_
- optional `pplx-embed-context-v1` for the LLM-free contextual-embedding arm;
- `ragas`, MiniCheck/HHEM/Lynx packages, or other advisory judge packages pointed at local endpoints.

#### Installed on the Ubuntu workstation PC (2026-06-09)

_(Workstation-specific — applies only to this Ubuntu GPU box (`delos`), not the portable skill. All native, no Docker, for max performance. System `python3` is pyenv 3.14 (too new for ML wheels), so every venv pins uv-managed CPython 3.12.13.)_

- **Portable skill stack** — `~/.cache/rag-skill/venv`: `qdrant-client` 1.18.0 + `fastembed` 0.8.0, FastEmbed models warmed (bge-small, BM25/SPLADE, MiniLM). `check-local-rag.sh` → `READY (server)` against the **native Qdrant 1.17.1** already running on `:6333` (no container; the `rag-qdrant` Docker path in `setup-local-rag.sh` is skipped because healthz answers).
- **Campaign harness venv** — `~/developer/third-party/python_venvs/rag_campaign_env/.venv` (Waves 0–7 scoring/chunking/judges): `ranx` 0.3.21, `ir-measures` 0.4.3, `pytrec_eval`, `rapidfuzz` 3.14.5, `tree-sitter` + `tree-sitter-language-pack` 1.8.1 (cpp/cuda/c/python/typescript/bash/markdown grammars verified), `networkx` 3.6.1, `scikit-learn` 1.9.0, `umap-learn` 0.5.12, `hdbscan` 0.8.44, `openai` 1.109.1, `ragas` 0.2.15 (pinned with the langchain 0.3 family for import compat), plus `qdrant-client[fastembed]`. SQLite FTS5 ships in the stdlib `sqlite3`. _(Updated 2026-06-09: added `transformers 5.10.2` + `torch 2.12.0` (CUDA-enabled, sm_120 Blackwell) + `sentence-transformers 5.5.1` for Wave-4/7 local judge inference.)_
- **Wave-3 GPU embed/rerank serving** — `~/developer/third-party/python_venvs/infinity_env/.venv`: **Infinity** (`infinity-emb` 0.0.77) on `torch` 2.11.0+cu130 (Blackwell `sm_120`), `optimum` pinned to 1.23.3. Verified loading NAS-staged models on the free card (`CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1`; GPU0 is saturated by the gemma-4 vLLM server): bge-small embeds (384-d) and ms-marco-MiniLM reranks correctly on GPU. **TEI was not installed** — its prebuilt binaries don't target Blackwell `sm_120` and a CUDA-13 source build is heavy; Infinity (torch-based) is the native embed/rerank server here.
- **Reused as-is (not reinstalled):** NVIDIA driver 590.44.01 / CUDA 13.1; `vLLM` 0.20.0 + `LiteLLM` 1.83.14 in `~/developer/third-party/python_venvs/llm_env/.venv` serving `gemma-4` behind nginx TLS at `llm.shuyangsun.com` (left untouched; reuse for Wave-4+ generation, and add the Infinity embed/rerank endpoints to its `model_list` when Wave 3 goes live); `bun`, `ripgrep`, `uv`, `cargo`.
- **Deferred / needs sudo:** `universal-ctags` (optional, Wave 5) — sudo install script written to `~/Downloads/install-deferred-sudo.sh`; run manually: `bash ~/Downloads/install-deferred-sudo.sh`. `SGLang` not installed (gemma-4/vLLM already covers generation + index-time contextualization). `pplx-embed-context-v1` is Perplexity API-only — no public HF model exists, skipped. _(Updated 2026-06-09: judge model weights downloaded to NAS; see judge table below.)_

#### Judge models staged on NAS (2026-06-09)

Downloaded to `/mnt/nas/home/ml/model/llm/` for Wave-4/7 faithfulness diagnostics. Note: `vectara/hhem-2.1-open` does not exist on HF; the actual HHEM-2.1 release is `vectara/hallucination_evaluation_model` (Apache-2.0, 438 MB, complete at first try). `bespoke-minicheck` is not on PyPI; weights are used directly via `transformers`. Lynx and MiniCheck are **NC** (cc-by-nc-4.0), campaign-only. HHEM is the only Apache-2.0 judge and is portable-eligible.

| dir                                                     | HF repo                                           | size   | license             | status                                                                                  |
| ------------------------------------------------------- | ------------------------------------------------- | ------ | ------------------- | --------------------------------------------------------------------------------------- |
| `vectara_hallucination_evaluation_model`                | vectara/hallucination_evaluation_model            | 0.4 G  | Apache-2.0          | **complete** — portable NLI judge default (HHEMv2, Flan-T5-based, 438 MB), CPU-eligible |
| `bespokelabs_Bespoke-MiniCheck-7B`                      | bespokelabs/Bespoke-MiniCheck-7B                  | 14 G   | cc-by-nc-4.0 **NC** | **downloading** — factuality/faithfulness judge (InternLM2-7B), campaign-only           |
| ~~`PatronusAI_Llama-3-Patronus-Lynx-8B-Instruct-v1.1`~~ | PatronusAI/Llama-3-Patronus-Lynx-8B-Instruct-v1.1 | 16 G   | cc-by-nc-4.0 **NC** | **cancelled + deleted** — download stopped, dir removed from NAS                        |
| ~~`PatronusAI_Llama-3-Patronus-Lynx-70B-Instruct`~~     | PatronusAI/Llama-3-Patronus-Lynx-70B-Instruct     | ~140 G | cc-by-nc-4.0 **NC** | **cancelled + deleted** — download stopped, dir removed from NAS                        |

HHEM can run CPU-local via `sentence-transformers CrossEncoder` (now in campaign venv) or be served via Infinity as a reranker endpoint. Lynx models are available to re-download if needed for Wave-7 faithfulness validation; they require vLLM + LiteLLM proxy for GPU inference. All four stale partial-download residual dirs (`PatronusAI_Patronus-Lynx-*/` v1.0 and v1.1/70B) have been removed from NAS.

### Local LLM and GPU Setup

The consolidated local-LLM decision is:

- **No local LLM is required for the first baseline.** Plain hybrid retrieval, BM25/FTS5/`rg`, parent retrieval, metadata indexing, late chunking, embedding swaps, and reranker swaps can be measured without a generative model.
- **A local LLM is required for the full Phase 3 loop** if API token cost should stay near zero. It is needed for index-time contextual retrieval, Doc2Query/query rewrites, graph/source-map summaries, answer generation, and advisory claim checks.
- **Use one model per GPU where possible.** Claude's GPU research found no NVLink, so treat the workstation as two independent 96 GB VRAM pools. Avoid tensor-parallel serving across both cards for latency-sensitive paths unless a long-context 70B answer model forces it.
- **The GPU workstation is a SEPARATE machine on the LAN, not the host running the harness/Qdrant.** Serve over the network, not localhost: bind vLLM (generative) and TEI/Infinity (embed/rerank) to `--host 0.0.0.0`, and front them with a single **LiteLLM proxy** on the GPU box (`0.0.0.0:<port>`, master/API key, stable LAN hostname or static IP, port open to the LAN only — not the public internet). The harness points its OpenAI-compatible client at `http://<gpu-host>:<port>/v1` and health-checks (one completion + one embedding) before any long indexing run. Embed/rerank serving comes online at Wave 3; the generative LLM at Wave 4. All of this is campaign-side; the portable `setting-up-rag` default stays CPU-only with no network LLM. _(Realized 2026-06-09: the LiteLLM proxy is live at `https://llm.shuyangsun.com/v1` serving `gemma-4` over the LAN (nginx TLS front, IP-allowlisted to `192.168.0.0/24`); concrete base URL, model name, placeholder-keyed auth, and smoke tests are in [`0005`](../../prompts/2026-06-08/0005-optimizing-rag-setup.md) → "The live endpoint on this workstation". TEI/Infinity embed/rerank serving is still to be stood up for Wave 3, but the embedding/reranker weights are already on the NAS.)_
- **Re-verify model versions before pinning.** The prompt mentioned Gemma 4 as possible, but the research only verified Qwen3, Llama 3.3, Gemma 3, Lynx, HHEM, Qwen3-Embedding, and mxbai-rerank. Pull official model cards at campaign time before recording a default. _(Updated 2026-06-09: Gemma-4-31B-IT (`gemma-4`) is now the deployed generative model; the embedding/reranker model cards and licenses were verified against the live HF API and recorded in the `0005` staged-models tables. Still re-pull official cards for the generative + judge LLMs before pinning them.)_

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

_(2026-06-09: every embedder and reranker named in this wave is already downloaded to the NAS at `/mnt/nas/home/ml/model/{embedding,reranker}/` — see [`0005`](../../prompts/2026-06-08/0005-optimizing-rag-setup.md). New options beyond the original list, also staged: code-specialized embedders `bge-code-v1` (Apache) and `SFR-Embedding-Code-2B_R` (NC) for the code cohort, and the calibrated instruction rerankers `zerank-1-small` (Apache) and `zerank-2` (NC) — worth A/B-ing in steps 1 and 5.)_

1. **Dense embedder sweep.** Compare `bge-small` with Qwen3-Embedding-0.6B, 4B, and 8B. Qwen3-Embedding-4B is the likely sweet spot, but this corpus decides.
2. **Instruction-prefix plumbing.** Qwen-style decoder embedders require query prefixes and no document prefixes. Wire index and query paths correctly before trusting metrics.
3. **Named vectors.** Test `dense_code` and `dense_prose` vectors with cohort-specific routing if one dense model does not dominate both cohorts.
4. **Sparse arm split.** Keep BM25 for code. A/B `Splade_PP_en_v1` for prose and long `nl` queries. Do not globally swap BM25 to SPLADE until exact identifier behavior is measured.
5. **Reranker swap.** Compare CPU MiniLM with permissive candidates such as `bge-reranker-v2-m3`, mxbai-rerank-v2, and Qwen3-Reranker-4B. Validate Qwen3-Reranker serving and score sanity before use.
6. **BGE-M3 and multi-representation arms.** Test as an experimental dense+sparse+multi-vector collapse, especially for long prose, but do not assume it beats Qwen3 dense on code.
7. **Qdrant storage knobs.** Use named vectors, int8 scalar quantization plus rescoring for large vectors, and high-quality HNSW. Reserve binary quantization for large/high-dimensional indexes if memory becomes binding.

### Wave 4 - Contextual and Long-Document Retrieval — ✅ COMPLETE (2026-06-10)

Goal: improve transcript, design-doc, and ambiguous prose retrieval without diluting code identifiers.

1. **Anthropic-style contextual retrieval.** Use a local LLM to generate 50-100 token chunk context before dense and sparse indexing. Start with `nl` corpora and long transcripts. — ✅ **DONE, PROMOTED (campaign)** [`0014`](../../benchmarks/2026-06-10/0014-wave4-contextual-gemma4-rag.md)/[`0015`](../../benchmarks/2026-06-10/0015-wave4-generator-model-comparison-rag.md): held-out nDCG +0.031 (code +0.045), apply to **all** chunks (not nl-only). The cleanest index-time-LLM win.
2. **LLM-free contextual embedding.** A/B `pplx-embed-context-v1` or late chunking against generated contextual retrieval. — ❌ **REJECTED** [`0016`](../../benchmarks/2026-06-10/0016-wave4-latechunk-rag.md) (`pplx` is API-only/untestable; late chunking is the available LLM-free arm and loses — see step 3).
3. **Late chunking.** Test long-context embedding plus pooled chunk vectors on `coding-agent-skills` and `website` session transcripts before source code. — ❌ **REJECTED** [`0016`](../../benchmarks/2026-06-10/0016-wave4-latechunk-rag.md): bge-m3 whole-doc mean-pool regresses every held-out slice (nDCG −0.115); whole-doc pooling blurs within-doc discrimination.
4. **Doc2Query/document expansion.** Use prose-only expansions in a separate field so code identifiers are not crowded out. — ✅ **DONE (campaign)** [`0018`](../../benchmarks/2026-06-10/0018-wave4-doc2query-rag.md): **all-chunks** is a code win (+0.030/+0.060), **prose-only is REJECTED** (regresses code). Separate BM25 field; ≈ contextual-retrieval quality, less clean on nl.
5. **Session metadata and summaries.** Add session IDs, dates, projects, turn windows, mentioned-file lists, and optional source-map capsules. — ✅ **DONE (optional portable)** [`0017`](../../benchmarks/2026-06-10/0017-wave4-session-meta-rag.md): deterministic capsule, on-target win (website transcripts → perfect); the mentioned-file list is the live signal. Corpus-conditional.
6. **Long-context reader arms.** Compare whole sections/files/sessions with source-order, score-order, and parent-before-child packing. — ⏭️ **DEFERRED to Wave 7** [`0019`](../../benchmarks/2026-06-10/0019-wave4-reader-packing-rag.md): packing **order** is order-invariant for all retrieval-stage metrics; it needs answer faithfulness to score. (Parent-window _granularity_ is Wave-2 step 2.)

### Wave 5 - Code Graphs, Source Maps, and Hierarchy — ✅ COMPLETE (2026-06-10)

Goal: recover cross-file dependencies and architecture/history answers as overlays, not replacements.

1. **Deterministic repo graph overlay.** Expand candidates with include/import/call/class/test edges, then rerank with Qdrant and the normal reranker. — ❌ **REJECTED** [`0020`](../../benchmarks/2026-06-10/0020-wave5-graph-overlay-rag.md): strong boost destroys held-out ranking (nDCG −0.208; flat RRF score curve), tie-break boost is aggregate-positive but deterministically regresses specific nl slices in two independent draws, and **expansion before `bge-reranker-v2-m3` adds nothing over the reranker alone** — the 60-deep prefetch already contains the graph's candidates.
2. **Local GraphRAG-style source map.** Reuse the promising deterministic graph approach from benchmark `0009` as a candidate expansion layer for code and multi-hop questions. — ❌ **REJECTED** [`0020`](../../benchmarks/2026-06-10/0020-wave5-graph-overlay-rag.md): the 0009 edge inventory (markdown links + path mentions) was rebuilt as `link`/`mention` edges; the sweep-3 ablation shows those edges carry the code-domain gain _and_ the nl damage — the signal is real but belongs **index-side** (`0017` capsule, Wave-2/4 headers/contexts), not in query-time rank math. 0009's perfect-recall promise dissolved once Waves 0–4 fixed the substrate it was compensating for.
3. **Graphify only after provenance fixes.** — ⏭️ **SKIPPED** [`0020`](../../benchmarks/2026-06-10/0020-wave5-graph-overlay-rag.md): the provenance defect stands, and steps 1–2 show the query-time expansion mechanism it would feed is dominated on this corpus — fixing graphify would buy a losing mechanism.
4. **Full GraphRAG/LightRAG/HippoRAG/RAPTOR/PathRAG.** — ⏭️ **DEFERRED indefinitely** [`0020`](../../benchmarks/2026-06-10/0020-wave5-graph-overlay-rag.md): heavier instances of the same expansion idea; the multi-hop/multi-primary gating evidence showed only a dev-split R@20 bump that vanished held-out while rerank-alone reaches R@20 0.995 (code 1.000). Revisit only if Wave-7 answer metrics expose persistent multi-hop failures.
5. **Source maps as answer bridges.** Let source maps improve answerability, but require the consumer to verify against primary code/docs because source maps can rank above primary files. — ⏭️ **folded into Wave 7** (answer-stage by definition, alongside the deferred `0019` packing arms). No LLM was needed for any Wave-5 decision; the Nemotron-120B reservation stays parked for Wave-7 generation/judging.

### Wave 6 - Query Routing and Adaptive Retrieval — ✅ COMPLETE (2026-06-10)

Goal: spend expensive transforms only on hard queries.

1. **Deterministic feature router.** Start with features such as repo, domain, query length, identifier density, path mentions, code tokens, difficulty estimate, multi-hop markers, available indexes, and first-pass retrieval confidence. — ✅ **BUILT, then REJECT as default** [`0021`](../../benchmarks/2026-06-10/0021-wave6-query-routing-rag.md): query-TEXT features cannot route reranking (0020 mining: helped/hurt populations have identical text stats); retrieval-STATE features can (oracle +0.083 dev) but the fitted gate fails the repeated-cells slice gate. Toolkit kept in `wave6_query.py` (+`route.*` TSV channel, `wave6_fit_gate.py`).
2. **Self-query soft filters.** — ❌ **REJECTED** [`0021`]: rank-fused (never additive) lang/kind/path filter, 17% trigger; dev hit@5 −0.031 — extracted filters misfire too often.
3. **Query decomposition.** — ❌ **REJECTED** [`0021`]: Nemotron-120B and deterministic splitter both held-out flat (twins move as much); ungated all-queries variant regresses hit@5 −0.031. Subquery RRF fusion preserved lexical signals as designed — there was just no headroom to win.
4. **HyDE and multi-query.** — ❌ **REJECTED** [`0021`]: HyDE's dev +0.030 did **not** replicate held-out (−0.009, sentinel −0.027; Nemotron invents plausible identifiers); multi-query reaches R@20 1.000 without adding one sentinel-bearing chunk. Identifier-protective gating was not the issue — gated and ungated fail alike.
5. **CRAG-style evaluator.** — ❌ **REJECT as default / superseded** [`0021`]: the frozen confidence gate (rerank iff `d_top≤0.752 OR d_gap≤0.0215`, 38% fire) **dominates always-bge-rerank on every held-out aggregate** but inherits replicated slice damage via adverse selection — and the faithfully-served Qwen3-Reranker-4B then beats the gate's oracle ceiling, reducing the gate to a latency knob. The same wave **promoted that reranker campaign-side** (held-out nDCG **0.848**, the campaign's largest single-variable win; serving recipe = vLLM seq-cls conversion + mandatory instruction template, plumbed as `rerank.template="qwen3"`).
6. **Agentic loop.** — ⏭️ **CLOSED BY EVIDENCE, folded into Wave 7** [`0021`]: static retrieval after the substrate fix sits at R@20 0.995 (code 1.000) / nDCG 0.848, and every routed mechanism this wave was dominated by that fix; a bounded agent re-querying the same substrate has only answer-stage headroom (tokens-to-primary, abstain) — measure there.

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
