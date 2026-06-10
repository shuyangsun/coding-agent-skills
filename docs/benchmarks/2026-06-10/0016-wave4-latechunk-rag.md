# Wave 4 — late chunking / LLM-free contextual embedding (bge-m3)

- **Date:** 2026-06-10
- **Wave:** 4 (contextual / long-document retrieval), steps 2–3 — "LLM-free contextual
  embedding" + "late chunking"
- **Plan:** [`0008-consolidated-rag-optimization-phase-2.md`](../../plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md) §"Wave 4"
- **Harness:** `…/0008-…/harness/{wave4_latechunk.py,enriched_index.py,run_benchmark.py,wave4_analyze.py}`
- **Artifacts:** `0016-wave4-latechunk-metrics.tsv`, `-summary.json`
- **Embedder:** `BAAI/bge-m3` (MIT, 8192-ctx XLM-RoBERTa, 1024-d), staged on the NAS, served on GPU1
- **Disposition:** **REJECT** — late chunking regresses **every** gating metric on **both**
  splits and **both** domains. The naive→late delta isolates the _method_ as the cause.
  Keeps the established LLM situating-context win (`w4-llm-all`, [`0014`](0014-wave4-contextual-gemma4-rag.md))
  as the only contextual-embedding technique that helps. Portable + campaign defaults **unchanged**.

## Question

[`0014`](0014-wave4-contextual-gemma4-rag.md) proved an **LLM** situating-context per chunk
wins (held-out code nDCG +0.045). Wave 4 steps 2–3 ask whether we can get that document
context **without** a generative LLM, via **late chunking** (Günther et al. / Jina): embed
the whole document once with a long-context encoder, then mean-pool each chunk's token
embeddings so every chunk vector carries document context. If it worked it could be a
cheaper campaign default — or even portable. It does not.

## What changed (clean single-variable isolation)

`wave4_latechunk.py` precomputes per-chunk **dense** vectors with bge-m3 on the GPU in two
modes and caches them; the benchmark runner reads the cache (and a precomputed query-vector
cache) so it stays torch-free and **only the dense doc/query vector swaps** — chunker,
sparse/BM25, deterministic header, fusion, top_k all held identical:

| arm                                       | dense vector                                                                       | sparse           | header |
| ----------------------------------------- | ---------------------------------------------------------------------------------- | ---------------- | ------ |
| `w2-ctx-header` (baseline, portable best) | bge-small over **header+raw** chunk                                                | BM25(header+raw) | ✓      |
| `w4-lc-bge-m3-naive` (control)            | bge-m3 mean-pool of the **chunk alone** (no context)                               | BM25(header+raw) | ✓      |
| `w4-lc-bge-m3-late` (treatment)           | bge-m3 mean-pool of the chunk's tokens **in whole-doc context** (8192-tok windows) | BM25(header+raw) | ✓      |
| `w4-ctx-llm-gemma4-all` (campaign best)   | bge-small over **header+LLM-context+raw**                                          | BM25(same)       | ✓      |

The **naive→late** pair is the controlled method test (same model, dim, pooling, chunker,
sparse, header — only the encoding window differs). Pooling is mean-pool for documents **and**
queries (late chunking requires per-token states; consistent mean-pooling keeps the spaces
comparable). Precompute: 9361 naive + 9361 late chunk vecs + 207 query vecs in **67 s** on one
RTX PRO 6000.

## Results

### Overall (all 207, from `report.py`)

| arm                     | R@20  | nDCG@10 | pMRR  | sentCov | hit@5 | ms\* |
| ----------------------- | ----- | ------- | ----- | ------- | ----- | ---- |
| `w2-ctx-header`         | 0.963 | 0.679   | 0.616 | 0.853   | 0.812 | 41   |
| `w4-lc-bge-m3-naive`    | 0.922 | 0.639   | 0.579 | 0.792   | 0.797 | 14   |
| `w4-lc-bge-m3-late`     | 0.882 | 0.528   | 0.470 | 0.733   | 0.725 | 14   |
| `w4-ctx-llm-gemma4-all` | 0.977 | 0.715   | 0.647 | 0.919   | 0.865 | 42   |

\* The bge-m3 arms' 14 ms is an **artifact** — the dense query vector is a cache lookup, not a
live forward pass. A production late-chunk query needs a GPU bge-m3 pass (~10–30 ms). Latency
is **not** a reason to prefer these arms.

### Held-out (n=111) — the gate

| arm                        | nDCG@10            | pMRR               | sentCov        | hit@5          |
| -------------------------- | ------------------ | ------------------ | -------------- | -------------- |
| `w2-ctx-header` (baseline) | 0.730              | 0.665              | 0.833          | 0.793          |
| `w4-lc-bge-m3-naive`       | 0.693 (−0.037)     | 0.628 (−0.037)     | 0.790 (−0.044) | 0.820 (+0.027) |
| `w4-lc-bge-m3-late`        | **0.614 (−0.115)** | **0.553 (−0.111)** | 0.745 (−0.089) | 0.766 (−0.027) |
| `w4-ctx-llm-gemma4-all`    | 0.767 (+0.037)     | 0.706 (+0.041)     | 0.913 (+0.080) | 0.847 (+0.054) |

**The naive→late delta is −0.079 nDCG / −0.075 pMRR held-out** — that is the late-chunking
_method_ effect with everything else held constant. It is negative.

By domain (held-out): late regresses **code** (nDCG 0.674→0.569, −0.105) **and** **nl** (0.838→0.702,
−0.136). The dev split is worse still (late nDCG 0.428 vs baseline 0.620, **−0.192**), so this is
not held-out noise. The regression scan flags **46** (repo×domain / difficulty×domain) cells for
late — every repo, both domains.

## Analysis — why late chunking _hurts_ here

1. **Whole-document pooling blurs within-document discrimination.** Late chunking makes every
   chunk of a document inherit a shared document context, so the chunks of one doc become
   mutually _similar_. Retrieval needs the opposite: the one chunk that answers the query must
   stand out from its neighbours. On a micro-example the symptom is visible — three blocks of one
   doc scored 0.733/0.750/0.663 (naive, discriminating) vs 0.775/0.775/0.768 (late, collapsed).
   At corpus scale this costs −0.11 to −0.19 nDCG.
2. **LLM context wins for the opposite reason.** `w4-llm-all` adds a _distinct_ situating sentence
   per chunk ("defines the `MctsConfig` struct …") — it _sharpens_ each chunk's identity. Late
   chunking _averages_ toward a shared vector. Same goal (document context), opposite mechanism;
   only the sharpening one helps.
3. **Even naive bge-m3 < bge-small+header.** The mean-pooled bge-m3 control underperforms the
   portable baseline (−0.037 nDCG). Part of that gap is a confound — the bge-m3 arms embed the raw
   chunk/doc, so the **deterministic header is absent from their dense field** (it is still in
   their sparse field); the Wave-2 header win is a dense-side win the bge-m3 arms forgo by
   construction. But the **method** conclusion (late < naive) is header-confound-free: both have
   the identical header-in-sparse / raw-in-dense setup, and late is still −0.079.

### Honest caveats (do not over-claim)

- bge-m3's _official_ dense is CLS-pooled; mean-pooling (mandatory for per-chunk late pooling) is
  not bge-m3's best single-vector config. This benchmark rejects **late chunking as a method**, not
  "bge-m3 is a bad embedder." A header-in-dense bge-m3 control (held constant vs bge-small) was not
  run because the decisive finding — late < naive on every slice — does not depend on it.
- Late chunking is reported to help **very long, topically-homogeneous prose** where cross-chunk
  context disambiguates. This six-repo code+docs corpus is the opposite (identifier-dense code,
  short structured docs), which is exactly where within-doc discrimination matters most.

## Decision

- **REJECT `w4-lc-bge-m3-late`** (and the bge-m3 mean-pool naive variant). They regress every
  gating metric on both splits and both domains. Late chunking does **not** recover the
  contextual-retrieval win without an LLM on this corpus.
- **The LLM situating-context arm (`0014`) stays the only contextual-embedding promotion** —
  campaign (GPU) only.
- **Portable + campaign defaults unchanged.** This closes Wave 4 steps 2–3 with a documented
  negative (cf. the Wave-1 re-index-free negative): the cheaper LLM-free substitute for contextual
  retrieval does not exist here.
- `pplx-embed-context-v1` (the other step-2 LLM-free option) remains **untestable** — Perplexity
  API-only, no public weights — so late chunking was the available LLM-free arm.

## Reproduce

```bash
H=docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/harness
CFG=docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/configs
CAMP=~/developer/third-party/python_venvs/rag_campaign_env/.venv/bin/python
RAG=~/.cache/rag-skill/venv/bin/python

# 1) GPU precompute: naive + late chunk vectors + query vectors (bge-m3 on the free card)
CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 $CAMP $H/wave4_latechunk.py \
  precompute --repo all --mode naive,late --config $CFG/wave4/w4-lc-bge-m3-late.json
CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 $CAMP $H/wave4_latechunk.py precompute-queries

# 2) index + score the 4 arms (Qdrant :6343, FastEmbed CPU; dense for lc arms read from cache)
$RAG $H/run_benchmark.py --split all --tag 0016-wave4-latechunk --out-dir docs/benchmarks/2026-06-10 \
  --reindex --config $CFG/wave2/w2-ctx-header.json \
  --config $CFG/wave4/w4-lc-bge-m3-naive.json --config $CFG/wave4/w4-lc-bge-m3-late.json \
  --config $CFG/wave4/w4-ctx-llm-gemma4-all.json

# 3) sliced A/B + regression scan
python3 $H/wave4_analyze.py docs/benchmarks/2026-06-10/0016-wave4-latechunk-metrics.tsv \
  --baseline w2-ctx-header --splits held-out,dev
```

## Contamination

Identical corpus across all four arms (same `corpus_sig`), so the A/B deltas are unaffected; the
eval set + consolidated plan stay hard-excluded. `w4-ctx-llm-gemma4-all` ran at full context
coverage (gemma cache topped up to the current corpus: 2936/2936 coding-agent-skills, etc.).
