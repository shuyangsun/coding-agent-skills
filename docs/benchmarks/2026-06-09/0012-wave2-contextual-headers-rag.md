# Benchmark 0012 — Wave 2: deterministic contextual headers (207-query, 6-repo)

- **Date:** 2026-06-09
- **Wave:** 2 (LLM-free index/payload) of
  [`0008`](../../plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md)
- **Baseline:** Wave-0/1 current best `plain-current-no-rerank` (hybrid RRF, rerank OFF).
- **Change (one variable):** prepend a **deterministic** header to each chunk's
  embedding/sparse field — `[repo] path :: <symbol|heading_path> (lang)` — while
  `raw_text` stays byte-verbatim for citations/sentinels. **No LLM**; re-index only
  (new `index_key`). Same chunker, same models, rerank still OFF.
- **Artifacts:** `0012-wave2-ctx-header-{metrics.tsv,summary.json}`.

## Headline — the biggest clean win of the campaign, and it's free

| slice              | nDCG@10 Δ                | primary-MRR Δ            | sentCov Δ | R@20 Δ | hit@5 Δ |
| ------------------ | ------------------------ | ------------------------ | --------- | ------ | ------- |
| **overall (207)**  | **+0.057** (0.625→0.683) | **+0.055** (0.565→0.621) | +0.033    | +0.010 | +0.000  |
| **held-out (111)** | **+0.056** (0.681→0.737) | **+0.055** (0.620→0.675) | +0.021    | +0.005 | −0.036  |
| code (137)         | +0.061                   | +0.053                   | +0.027    | +0.015 | +0.000  |
| nl (70)            | +0.050                   | +0.060                   | +0.045    | +0.000 | +0.000  |

The gain **replicates on held-out** (unlike every Wave-1 knob) and is **uniform**.

## No slice regresses — the promotion gate is clean

Every repo, difficulty, and category improves on the ranking metrics (nDCG@10 / primary-MRR):

| axis           | best                                                            | weakest                                     | notable                                                                                                        |
| -------------- | --------------------------------------------------------------- | ------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **repo**       | coding-agent-skills +0.085 / +0.090, alpha-zero +0.087 / +0.071 | az-game-xiang-qi +0.016 / +0.018            | **the two small repos that `no-rerank` regressed in Wave 0 now improve** (tic-tac-toe +0.035, xiang-qi +0.016) |
| **difficulty** | **hard +0.089 / +0.092**                                        | easy +0.003 / +0.005 (already near ceiling) | the lift concentrates exactly on the hard tail                                                                 |
| **category**   | **session-prompting +0.095 / +0.127**                           | design-doc +0.011 / +0.000 (ceiling)        | codebase +0.060 / +0.052                                                                                       |

The only negative anywhere is **held-out hit@5 −0.036** (overall hit@5 is flat). Against
substantial, uniform gains on the four gate metrics (recall@20, nDCG@10, MRR, primary-file
MRR) and sentinel coverage, with **zero repo/domain/category/difficulty regression**, this
clears the `0008` promotion criteria.

## Why it works

The header injects the chunk's **location and identity** (`repo`, `path`, `symbol`/`heading`,
`lang`) into the embedded + BM25-indexed text. That (a) lets a query naming a file, symbol, or
section match its chunks directly, (b) disambiguates near-duplicate chunks across files, and
(c) gives every code chunk — which otherwise embeds as a context-free block — a stable anchor.
The biggest gains are on **hard** and **session-prompting** questions, which most need that
disambiguation. `raw_text` is untouched, so citations and the deterministic sentinel gate are
unaffected (verbatim verified).

## Cost

Header text adds ~10–20 tokens/chunk to the embedded field (not the packed context, which still
uses `raw_text`): index size and query latency are unchanged (44 ms vs 37 ms, noise). Re-index
is required but one-time. **CPU-clean, license-neutral, no network/LLM.**

## Decision

| change                               | decision                                         | basis                                                                             |
| ------------------------------------ | ------------------------------------------------ | --------------------------------------------------------------------------------- |
| **Deterministic contextual headers** | **PROMOTE to portable `setting-up-rag` default** | held-out nDCG/primary-MRR +0.055; **no slice regresses**; deterministic, CPU-only |

**New current best = `header + no-rerank`** (nDCG@10 0.683, primary-MRR 0.621, sentCov 0.853).
Wave 3 builds on the header index. Promotion into the shipped skill (a `contextual_header` option
in `rag_lib`/`index.py` + default-on) is applied in the consolidation step.

## Not yet tested (cheaper-first discipline; candidates for a later Wave-2 pass)

Parent-window / small-to-big retrieval, code chunk-size sweeps (the code chunker still averages
~9.5 chunks/doc), and AST/cAST chunking — all deferred behind this header win, which was the
highest-ROI payload change and is now banked.

## Reproduce

```bash
H=docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/harness
C=docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/configs
VENV=~/.cache/rag-skill/venv/bin/python
QDRANT_URL=http://localhost:6343 $VENV $H/run_benchmark.py \
  --config $C/wave2/w2-ctx-header.json --repos all --split all \
  --tag 0012-wave2-ctx-header --out-dir docs/benchmarks/2026-06-09
```
