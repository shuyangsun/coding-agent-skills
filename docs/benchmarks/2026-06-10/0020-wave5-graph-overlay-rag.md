# Wave 5 — deterministic graph / source-map overlay on hybrid retrieval

- **Date:** 2026-06-10
- **Wave:** 5 (code graphs, source maps, hierarchy), steps 1–2 — "deterministic repo
  graph overlay" + "local GraphRAG-style source map" (the benchmark-0009 prototype,
  rebuilt as a candidate-expansion layer)
- **Plan:** [`0008-consolidated-rag-optimization-phase-2.md`](../../plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md) §"Wave 5"
- **Harness:** `…/0008-…/harness/{wave5_graph.py (new), run_benchmark.py (apply_graph_overlay)}`,
  arms in `…/0008-…/configs/wave5/`
- **Artifacts:** [`0020-wave5-graph-overlay-metrics.tsv`](0020-wave5-graph-overlay-metrics.tsv)
  (record run, 8 arms × 207 queries), `-summary.json`,
  [`-replicate-metrics.tsv`](0020-wave5-graph-overlay-replicate-metrics.tsv) (independent second
  draw), dev sweeps `0020-wave5-go-dev-sweep{1,2,3}-summary.json`, `-dev-campaign-summary.json`
- **Disposition:** **REJECT (all variants) — no promotion.** Query-time graph expansion is a
  _redistribution_, not a win: the only held-out-positive point (`lambda=0.05` tie-break boost,
  overall nDCG **+0.018…+0.023**, code **+0.033…+0.036**) buys its average lift with
  **deterministic, twice-replicated regressions on specific nl slices** (website-nl pMRR
  **−0.077**, tic-tac-toe-nl **−0.083**, easy-nl **−0.125**, alpha-zero-code negative in both
  draws) and so fails the plan's no-material-slice-regression gate. Expansion **before the
  bge-m3 reranker adds nothing over the reranker alone**. Free side-products kept: the
  **twin-baseline jitter control** (run any same-collection A/B with a duplicated baseline arm)
  and the first measurement of **`w4llm + bge-reranker-v2-m3`** as a coverage-vs-precision lever
  on the campaign best (hit@5 **+0.045**, sentinel **+0.015**, code R@20 **1.000**, at nDCG
  **−0.045**).

## What was built

`wave5_graph.py` builds one deterministic file graph per repo over exactly the indexed corpus
(no LLM, no AST): `import` (C/C++/CUDA `#include`, Python imports, TS/JS relative imports),
`pair` (same-stem header↔impl), `test` (test-naming conventions), `link` (markdown relative
links), `mention` (repo-relative path tokens + corpus-unique bare filenames — the 0009
local-GraphRAG "source map" signal). One edge per (src,dst), strongest extractor wins
(import > pair > test > link > mention). Scale: 42–365 files and 112–1,670 edges per repo
(alpha-zero 301 files/1,157 edges, 423 import; website 365/1,670, 1,325 mention); build is
sub-second and cached.

At query time (`run_benchmark.apply_graph_overlay`, **before** the reranker — the plan's
"expand candidates, then rerank"): the top-10 fused files seed direction-aware expansion
(forward weight 1.0/0.8, reverse ≈ half, per-seed log-degree damping); every candidate chunk
gets `final = 1/(60+rank) + lambda·G(file)`; with `fetch` on, strong unseen neighbors get their
best 2 chunks pulled in via a `doc_id`-filtered hybrid query and merged behind the originals.
Knobs swept: `lambda`, `fetch`, `head_lock` (freeze the top-10 chunks), `rev_scale`,
`edge_types`. **Query-time only:** overlay arms share the baseline's collection byte-for-byte
(same `index_key`), so the A/B is immune to the ~0.03 HNSW re-index noise floor from
[`0017`](0017-wave4-session-meta-rag.md). Latency cost ≈ +27 ms/query (36→64 ms).

## Results — held-out (n=111), record run + replication

Baseline `w2-ctx-header` (portable best: headers ON, rerank OFF): R@20 0.986, nDCG@10 0.731,
pMRR 0.665, sentCov 0.833, hit@5 0.793.

| arm (vs `w2-ctx-header`)               | R@20   | nDCG@10    | pMRR       | sentCov | hit@5  |
| -------------------------------------- | ------ | ---------- | ---------- | ------- | ------ |
| `w2-ctx-header-b` (jitter twin)        | +0.000 | −0.005     | −0.005     | +0.000  | +0.000 |
| `w5-go-portable` (λ=1, fetch)          | −0.009 | **−0.208** | **−0.215** | −0.095  | −0.207 |
| `w5-go-portable-tiebreak` (λ=0.05)     | +0.000 | **+0.023** | **+0.035** | −0.012  | +0.018 |
| `w5-go-portable-headlock` (λ=.5, H=10) | +0.000 | −0.009     | −0.009     | +0.003  | +0.000 |

Replication draw (same three arms, independent run): twin +0.003/+0.005; tiebreak **+0.018
nDCG / +0.026 pMRR** overall, code +0.033/+0.042, nl −0.011/−0.004 — the aggregate lift and the
code-domain lift replicate.

**Why tiebreak is still rejected:** the per-slice regression scan shows the same cells, at the
same magnitudes, in **both** independent draws — website-nl pMRR 0.933→0.856 (**−0.077**),
az-game-tic-tac-toe-nl 0.667→0.583 (**−0.083**), easy×nl 1.000→0.875 (**−0.125**), and
alpha-zero-code nDCG −0.031/−0.050. Identical repeated magnitudes mean the damage is
deterministic (the graph demotes those queries' primaries every run), unlike the twin baseline
whose "regressions" move randomly between draws (worst −0.071 in draw 1, a single −0.007 in
draw 2). The +0.02 average is bought by trading specific nl/easy queries down for code-cluster
queries up — exactly what the promotion criteria exclude ("without regressing any
repo/domain/category/difficulty slice").

### Campaign compose — expand-then-rerank adds nothing (held-out)

Campaign best `w4-ctx-llm-gemma4-all`: R@20 0.995, nDCG 0.760, pMRR 0.697, sentCov 0.913,
hit@5 0.847 (matches [`0014`](0014-wave4-contextual-gemma4-rag.md) within jitter on the
refreshed corpus).

| arm (deltas vs `w4-ctx-llm-gemma4-all`)   | R@20   | nDCG@10 | pMRR   | sentCov    | hit@5      | ms  |
| ----------------------------------------- | ------ | ------- | ------ | ---------- | ---------- | --- |
| `w4llm-rrk` (+bge-reranker-v2-m3)         | 0.995  | −0.045  | −0.052 | **+0.015** | **+0.045** | 141 |
| `w5-go-w4llm-rrk` (+overlay, then rerank) | −0.009 | −0.046  | −0.056 | +0.001     | +0.054     | 160 |

Overlay-into-reranker vs reranker alone: nDCG −0.001, pMRR −0.004, sentCov −0.014, hit@5
+0.009 — pure noise. At 60-deep prefetch over these corpora the reranker already sees every
candidate the graph would inject. The `w4llm-rrk` row itself is a useful new standing
measurement: on top of the Wave-4 winner the GPU reranker is a **coverage lever** (code
sentinel +0.030 → 0.904, code hit@5 +0.068 → 0.863, code R@20 1.000) that **costs ranking
precision** (nDCG −0.045) — choose per consumer at Wave 7, don't default it on.

### Dev sweeps (n=96) — how the design space collapsed

1. **Sweep 1, λ∈{0.5,1,2,4}×fetch:** every arm craters ranking (nDCG −0.074 at λ=0.5 down to
   −0.252 at λ=4, monotone) while R@20 ticks up (+0.010…+0.015). Mechanism: the fused RRF
   rank-score curve is nearly flat (adjacent-rank gaps ~1e-4 vs useful graph boosts ~5e-3), so
   any meaningful additive boost leapfrogs dozens of ranks and scrambles the precise head.
2. **Edge ablations at λ=1:** code-only −0.064, sourcemap-only −0.147, forward-only −0.143 —
   no edge subset rescues the strong boost.
3. **Sweep 2, tie-break λ + head-lock:** λ=0.05 is the only Pareto-ish point (dev +0.006).
   `head_lock=10` keeps the head intact and shows the one genuine retrieval-shape change —
   dev R@20 +0.016, **multi-primary R@20 +0.031** — but pays sentinel coverage (−0.062: the
   boosted files' fetched chunks displace sentinel-bearing chunks from the top-20 pack), and
   its R@20 gain does **not** replicate held-out (+0.000).
4. **Sweep 3, code-only edges at tie-break λ:** exactly flat — the code-domain gain of sweep 2
   came from the `mention`/`link` (source-map) edges, the same edges that damage nl. There is
   no edge subset that wins one domain without taxing the other.
5. **Campaign dev:** overlay alone on the w4 base: nDCG −0.195 (same failure); overlay+rerank
   0.664 vs rerank-alone 0.659 — the reranker fully absorbs the damage and extracts no value.

## Methodology — the twin-baseline jitter control (keep using this)

Qdrant **server-side RRF fusion is non-deterministic run-to-run** (tie order): repeat calls
reorder ~30% of positions below rank ~10 (first divergence ≈ rank 11). Running the baseline
config twice under two arm names inside the same benchmark measures the resulting metric
floor directly: **±0.005 on 111-query aggregates, up to ±0.07 on single repo×domain cells**
(the twin showed website-nl pMRR −0.050 in one draw and a single −0.007 cell in another, with
identical configs and collections). Per-slice deltas must be read against this _query-time_
floor (it composes with `0017`'s ~0.03 _re-index_ floor); single-draw cell regressions are
meaningless — replicate and look for repeated cells, which is exactly what convicted the
tiebreak arm here.

## Why this loses — one sentence extending the Wave-4 synthesis

Index-time context that **sharpens a chunk's identity** wins (0014/0018); query-time rank
forcing by file adjacency **redistributes** rank mass between query populations — and both of
the overlay's real signals are already delivered better elsewhere: the mention/link signal
index-side by the 0017 session capsule and the Wave-2/4 headers/contexts, and candidate
arbitration by the Wave-3 reranker over a 60-deep prefetch that already contains the graph's
candidates.

## Wave-5 step dispositions

1. **Deterministic repo graph overlay** — built, swept, **rejected** (this report).
2. **0009-style source-map expansion layer** — built (`link`+`mention` edges = 0009's edge
   inventory), **rejected**; its one real signal (mentioned-file lists) already ships
   index-side as the optional 0017 capsule.
3. **Graphify** — **not re-tested**: its 0009 transcript-provenance defect stands, and steps
   1–2 show the underlying query-time expansion mechanism loses on this corpus even with
   correct provenance; fixing graphify's provenance would buy a mechanism we now know is
   dominated.
4. **Full GraphRAG/LightRAG/HippoRAG/RAPTOR/PathRAG** — **deferred indefinitely**: these are
   heavier instances of the same expansion idea; the gating evidence (multi-hop/multi-primary)
   showed only a dev-split R@20 bump that vanished held-out, while rerank-alone already reaches
   R@20 0.995/1.000-code. Revisit only if Wave-7 answer-stage metrics expose persistent
   multi-hop failures that retrieval-stage metrics hide.
5. **Source maps as answer bridges** — answer-stage by definition; folded into Wave 7 with the
   deferred 0019 packing arms. **No LLM was needed for any Wave-5 decision** (the prompt's
   Nemotron-120B reservation stays parked for Wave-7 generation/judging).

## Reproduce

```bash
H=docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/harness
CFG=docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/configs
RAG=~/.cache/rag-skill/venv/bin/python

python3 $H/wave5_graph.py report --top 3            # per-repo graph stats (stdlib-only)
# Infinity reranker for the two -rrk arms (GPU1):
CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 \
  ~/developer/third-party/python_venvs/infinity_env/.venv/bin/python $H/serve_infinity.py \
  --port 7997 --model /mnt/nas/home/ml/model/reranker/bge-reranker-v2-m3 &
$RAG $H/run_benchmark.py --split all --tag 0020-wave5-graph-overlay \
  --out-dir docs/benchmarks/2026-06-10 \
  --arm wave2/w2-ctx-header --config $CFG/wave5/w2-ctx-header-b.json \
  --config $CFG/wave5/w5-go-portable.json --config $CFG/wave5/w5-go-portable-tiebreak.json \
  --config $CFG/wave5/w5-go-portable-headlock.json \
  --arm wave4/w4-ctx-llm-gemma4-all --config $CFG/wave5/w4llm-rrk.json \
  --config $CFG/wave5/w5-go-w4llm-rrk.json
python3 $H/wave4_analyze.py docs/benchmarks/2026-06-10/0020-wave5-graph-overlay-metrics.tsv \
  --baseline w2-ctx-header --splits held-out,dev
```
