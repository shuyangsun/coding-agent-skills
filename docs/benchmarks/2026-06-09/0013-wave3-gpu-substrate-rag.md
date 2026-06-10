# Benchmark 0013 — Wave 3: GPU retrieval substrate (reranker + embedder)

- **Date:** 2026-06-09
- **Wave:** 3 (stronger local models) of
  [`0008`](../../plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md)
- **Serving:** Infinity on the free GPU1 (`serve_infinity.py`, since the `infinity_emb v2`
  CLI is broken under the installed typer/click — see the script header). Reranker called
  from the runner via a `rerank.backend="infinity"` knob; the index is unchanged.
- **Baselines:** Wave-0 `plain-current` (MiniLM CPU rerank) and `plain-current-no-rerank`;
  Wave-2 `header+no-rerank` (current best).
- **Artifacts:** `0013-wave3-rerank-bge-m3-*`, `0013-wave3-header-plus-bge-m3-*`,
  `0013-wave3-embed-bge-base-*`.

## The reranker question, resolved

Wave 0/1 found the shipped **CPU MiniLM reranker hurts** ranking and costs 40× latency, but
mildly _helped_ two small repos. Wave 3 asks: does a **code-capable** reranker
(`bge-reranker-v2-m3`, Apache-2.0, 568 M, GPU) fix that — a strict win over MiniLM, and a
better trade than no reranker?

### Overall (207), reranking the **base** index (top_n=50)

| config                               | R@20      | nDCG@10   | pMRR      | sentCov   | hit@5     | ms     |
| ------------------------------------ | --------- | --------- | --------- | --------- | --------- | ------ |
| plain-current (MiniLM CPU)           | 0.956     | 0.608     | 0.530     | 0.793     | 0.744     | 1499   |
| no-rerank                            | 0.953     | 0.625     | 0.565     | 0.820     | 0.812     | **37** |
| **bge-m3 rerank (GPU)**              | **0.975** | 0.609     | 0.526     | **0.880** | **0.860** | 334    |
| header + no-rerank _(Wave-2 best)_   | 0.963     | **0.683** | **0.621** | 0.853     | 0.812     | 44     |
| **header + bge-m3 rerank** _(combo)_ | 0.970     | 0.633     | 0.557     | **0.888** | 0.841     | 132    |

### Two clean conclusions

1. **`bge-reranker-v2-m3` strictly dominates the shipped MiniLM.** Every slice: better or
   equal recall/nDCG/grounding, **4.5× faster** (334 vs 1499 ms). Held-out: R@20 0.996 vs
   0.987, sentCov 0.878 vs 0.788, hit@5 0.883 vs 0.748. If a reranker is used at all, it
   should be this one, never MiniLM.

2. **It fixes exactly the two repos `no-rerank` regressed.** `az-game-tic-tac-toe` nDCG
   0.547 and `az-game-xiang-qi` 0.588 are now the **best** of all three reranker states
   (no-rerank: 0.485 / 0.545; MiniLM: 0.539 / 0.540). The multilingual bge reranker handles
   the small game repos (incl. xiang-qi's Chinese terms) where bm25+dense fusion alone was
   weakest.

### But the reranker is a coverage-vs-precision **lever**, not a free win

vs `no-rerank`, bge-m3 **raises** recall@20 (+0.022), sentinel coverage (+0.060) and answer
hit@5 (+0.048) — it surfaces answer-bearing chunks into the top-k — while **lowering**
nDCG@10 (−0.016) and primary-MRR (−0.039): it ranks a semantically-relevant chunk above the
hand-pinned primary's best chunk. The drop concentrates on the already-strong, clean repos
(coding-agent-skills nDCG 0.706→0.592, alpha-zero pMRR 0.617→0.490); the gains concentrate on
code answer-grounding (code hit@5 0.730→0.818, code sentCov 0.755→0.841). Same pattern holds
**on top of contextual headers** (combo): best sentinel coverage of any config (0.888), but
headers-without-rerank keeps the best nDCG/primary-MRR.

**Reading:** if the downstream consumer needs the answer _string_ in a tight top-k context
(answer generation, Wave 7), the reranker's grounding gains win. If the goal is ranking the
exact pinned file first, headers-without-rerank wins. Both beat the shipped baseline.

## Decisions

| config                                | role                       | basis                                                                                 |
| ------------------------------------- | -------------------------- | ------------------------------------------------------------------------------------- |
| **header + no-rerank**                | **portable default** (CPU) | best nDCG@10/primary-MRR; deterministic; 44 ms                                        |
| **header + bge-reranker-v2-m3 (GPU)** | **campaign default**       | best sentinel coverage + hit@5; fixes weak repos; Apache-2.0; 4.5× faster than MiniLM |
| MiniLM cross-encoder                  | **drop**                   | strictly dominated by bge-m3 and by no-rerank                                         |

`bge-reranker-v2-m3` is Apache-2.0, so it is license-eligible for the portable default, but at
568 M it is GPU-practical only — it stays **campaign-side**; the portable default reranks with
nothing (the Wave-1 finding) and leans on contextual headers for ranking quality.

## Embedder sweep

One **portable** embedder tested; the **GPU campaign** sweep staged.

- **Portable (CPU) — `bge-base-en-v1.5` (768-d) vs `bge-small` (384-d), both no-rerank /
  no-headers to isolate the embedder: a WASH, REJECT.** Overall nDCG +0.003, primary-MRR
  −0.000, R@20 +0.007, hit@5 −0.019 (held-out +0.005 / +0.001 / −0.004 / −0.027). It splits by
  domain — **nl improves** (nDCG +0.023, hit@5 +0.014) but **code regresses** (nDCG −0.008,
  primary-MRR −0.009, hit@5 −0.036) — so the bigger model trades code for prose and nets to
  noise, at **2× the vector size and ~3× the CPU index time**. It does not clear the gate and is
  dwarfed by the contextual-header win (+0.055). **`bge-small` stays the portable dense default.**
  (Artifacts: `0013-wave3-embed-bge-base-*`.)
- **GPU campaign:** the heavier embedders (`qwen3-embedding-4b` — the plan's sweet spot — plus
  `mxbai-embed-large`, and `bge-code-v1` for the code cohort) need an Infinity **embed** backend
  wired into the indexer + query path (only the **rerank** backend exists today) and Qwen3
  query-vs-document instruction prefixes. This is the immediate Wave-3 continuation;
  `serve_infinity.py` already serves them on GPU1.

**Takeaway so far:** the largest retrieval win in Waves 0–3 is **representation** (deterministic
contextual headers, +0.055 held-out nDCG/primary-MRR, free and portable), not the
**model** — embedder/reranker swaps move answer-grounding and fix weak slices but trade against
exact-file ranking. The campaign should bank headers first, then layer the GPU reranker for
answer-grounding and finish the embedder sweep.

## Reproduce

```bash
H=docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/harness
C=docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/configs
# GPU serving (free card):
CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 \
  ~/developer/third-party/python_venvs/infinity_env/.venv/bin/python $H/serve_infinity.py \
  --port 7997 --model /mnt/nas/home/ml/model/reranker/bge-reranker-v2-m3
# experiments (reuse base / header indexes; no re-index):
VENV=~/.cache/rag-skill/venv/bin/python
QDRANT_URL=http://localhost:6343 $VENV $H/run_benchmark.py \
  --config $C/wave3/w3-rerank-bge-m3.json --config $C/wave3/w3-header-plus-bge-m3.json \
  --repos all --split all --tag 0013-wave3 --out-dir docs/benchmarks/2026-06-09
```
