# Benchmark 0011 — Wave 1: re-index-free retrieval knobs (207-query, 6-repo)

- **Date:** 2026-06-09
- **Wave:** 1 (re-index-free, low-risk retrieval wins) of
  [`0008`](../../plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md)
- **Baseline to beat:** Wave-0 current best `plain-current-no-rerank` (server RRF, prefetch 60,
  rerank OFF) — see [`0010-wave0-baseline-rag.md`](0010-wave0-baseline-rag.md).
- **Discipline:** tune on **dev (96)**, decide on **held-out (111)**. Every arm shares the
  Wave-0 base index (these are query-time-only knobs), so nothing was re-indexed.
- **Artifacts:** `0011-wave1-reindex-free-dev-*` (18-arm dev sweep),
  `0011-wave1-reindex-free-holdout-summary.json` (prefetch×exact),
  `0011-wave1-reindex-free-wrrf-holdout-summary.json` (weighted-RRF held-out).

## Headline

**No re-index-free fusion knob beats the no-rerank baseline on held-out.** The two promising
dev-split signals — deeper prefetch and dense-up-weighted RRF — **did not replicate on held-out**
(textbook overfitting the dev set; this is exactly what the dev→held-out split is for). The one
real Wave-1 win is the change carried from Wave 0: **disable the MiniLM reranker.**

## What was swept (all rerank OFF, server/​in-process fusion over the base index)

| knob                 | values                    | result                                                                                                                                           |
| -------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Fusion method        | server RRF vs server DBSF | **RRF wins** (dev nDCG 0.562–0.571 vs DBSF 0.544–0.550). Drop DBSF.                                                                              |
| RRF `k` (in-process) | 2, 10, 60                 | no held-out separation; `k`≈60 ≈ server RRF, `k`=2 in-proc slightly < server.                                                                    |
| dense/sparse weights | 1:1, 1:1.5, 1.5:1, 1:2    | dense-up-weight helped on **dev** (k10 dense1.5 nDCG 0.567 vs 0.549) but **regressed held-out** (0.672 vs 0.687). Sparse-up-weight always worse. |
| prefetch depth       | 60, 120, 200              | dev nDCG 0.565→0.571; **held-out flat** (0.690±0.004, R@20 identical).                                                                           |
| HNSW search          | ANN vs `exact=true`       | **R@20 identical (0.982)** ⇒ ANN is **not** losing recall at this scale.                                                                         |

### Held-out confirmation (prefetch × exact), n=111

| arm                            | R@20  | nDCG@10 | pMRR  | sentCov | hit@5     |
| ------------------------------ | ----- | ------- | ----- | ------- | --------- |
| **baseline (prefetch60, ANN)** | 0.982 | 0.684   | 0.625 | 0.812   | **0.829** |
| prefetch120, ANN               | 0.982 | 0.690   | 0.629 | 0.818   | 0.829     |
| prefetch120, exact             | 0.982 | 0.694   | 0.632 | 0.818   | 0.829     |
| prefetch200, ANN               | 0.982 | 0.691   | 0.629 | 0.812   | 0.829     |
| prefetch60, exact              | 0.982 | 0.678   | 0.614 | 0.812   | 0.829     |

The spread (nDCG 0.678–0.694) is within run-to-run noise, R@20 and hit@5 are pinned, and no arm
dominates. **Decision: keep defaults (prefetch 60, ANN, server RRF).**

### Held-out confirmation (weighted RRF), n=111

dense-up-weight, which looked good on dev, **loses** on held-out: k10 dense1.5 nDCG 0.672 / hit@5
0.784 vs baseline 0.684 / 0.829; only R@20 rises (k2 dense1.5 → 0.991) at the cost of pMRR/hit@5.
**Decision: keep equal-weight fusion.** (A _per-cohort_ weight needs a query router — deferred to
Wave 6 — not a global weight.)

## The one Wave-1 promotion — disable the MiniLM reranker

Confirmed on held-out in Wave 0 (identical config ± reranker): removing it gives **nDCG +0.010,
MRR/primary-MRR +0.034, sentinel coverage +0.024, answer hit@5 +0.081, R@5 +0.053**, and **40×
lower latency (1499 → 37 ms)**. `ms-marco-MiniLM-L-6-v2` is web-prose-trained and mis-ranks this
code/technical corpus, demoting relevant chunks out of the top-5.

**Caveat (honest):** vs the no-rerank config, two _small_ repos see a mild reranker _benefit_
(`az-game-tic-tac-toe` nDCG −0.054, `az-game-xiang-qi` hit@5 −0.091 when the reranker is removed;
n=24 and 33). Net across the corpus, held-out, both domains, and the other 4 repos, removing it is
a clear win and removes a 40× latency tax. **Disposition:** the portable default should ship with
the reranker **off**, but the actual `rag-config.json` edit is held until **Wave 3** decides
whether a _code-capable_ reranker (`bge-reranker-v2-m3`, `qwen3-reranker-4b`) is a strict win that
also lifts those two repos — the better outcome than "no reranker."

## Keep / revert

| change                                      | decision                                                        | basis                                                            |
| ------------------------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------- |
| Disable MiniLM reranker (default)           | **PROMOTE candidate** (apply in Wave 3 with the reranker sweep) | held-out nDCG/MRR/hit@5 up, 40× faster                           |
| Server RRF, prefetch 60, ANN, equal weights | **KEEP (no change)**                                            | no held-out win from any alternative                             |
| DBSF fusion                                 | **REJECT**                                                      | loses to RRF on dev                                              |
| Weighted RRF / `k` tuning                   | **REJECT (global)**                                             | dev gain didn't replicate held-out; revisit per-cohort in Wave 6 |
| HNSW `exact` / deeper prefetch              | **REJECT**                                                      | ANN already lossless on recall here                              |

## Deferred to later waves (not re-index-free)

- **Lost-in-the-middle reorder** & **mechanical citation-existence checks** (plan Wave-1 items 5–6)
  are answer-side — they don't change retrieval IR metrics; moved to **Wave 7**.
- Per-cohort fusion weighting needs a **router** → **Wave 6**.

## Takeaway

Wave 1 is mostly a **negative result**, and a valuable one: on a strong hybrid baseline, the
fashionable query-time knobs (weighted fusion, DBSF, `k`, deep prefetch, exact search) buy nothing
on held-out for this corpus. The retrieval headroom is in the **representation** (chunking/payload
— Wave 2) and the **models** (embedder/reranker — Wave 3), not in fusion arithmetic. The current
best config is unchanged from Wave 0 (`no-rerank`); Wave 2 builds on it.
