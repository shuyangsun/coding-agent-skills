# Benchmark 0010 — Wave 0: RAG baseline + controls (207-query, 6-repo)

- **Date:** 2026-06-09
- **Wave:** 0 (baseline + leakage controls) of the Phase-3 roadmap in
  [`0008-consolidated-rag-optimization-phase-2.md`](../../plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md)
- **Harness:** [`0008-…/harness/run_benchmark.py`](../../plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/harness/run_benchmark.py)
  over the 207-query gold set ([`eval-set.json`](../../plans/2026-06-08/0003-rag-eval-set-phase-1/eval-set.json))
- **Artifacts:** [`0010-wave0-baseline-metrics.tsv`](0010-wave0-baseline-metrics.tsv) (1449 rows = 207 q × 7 arms),
  [`0010-wave0-baseline-summary.json`](0010-wave0-baseline-summary.json)
- **Machine:** Ubuntu GPU box `delos`; CPU FastEmbed (`bge-small`+`bm25`+MiniLM), dedicated
  Qdrant 1.17.1 on `:6343` (isolated from the unrelated face-embed Qdrant on `:6333`).

## What this run establishes

The single **baseline config every later wave must beat**, plus the leakage controls that
keep the numbers honest. One combined code+docs corpus per repo (type-blind retrieval);
`domain` (code|nl) is a reporting slice only. All metrics are file-level IR against
**primary-only** graded qrels (grade-2 pinned files; immune to short-sentinel inflation),
with sentinel coverage measured over the **real packed top-20 chunk context**.

Gold slices: 207 q = **137 code / 70 nl**; 139 codebase / 35 design-doc / 33 session-prompting;
26 easy / 126 medium / 55 hard; 178 single- / 29 multi-primary; **dev 96 / held-out 111**.

## Pre-flight finding — the corpus must respect `.gitignore`

The first audit caught a corpus-quality bug worth shipping back into the skill. The corpus
loader walked the filesystem and indexed **git-ignored generated output**. In `alpha-zero`,
`artifacts/.../selfplay_traces/trace_*.json` (git-ignored, 0 tracked) held **1.47 M words —
84% of that repo's text, ~15 k of ~17.6 k chunks** — of machine-generated self-play traces
(50–84 k words/file). They are never a gold primary (0 of 207), are pure retrieval noise, and
made CPU indexing intractable (~35 min for one repo).

**Fix:** restrict the corpus to **git-tracked files** (`git ls-files`), which respects
`.gitignore` generally instead of enumerating dir names. Effect on `alpha-zero`: **17,592 →
2,857 chunks (6.2×)**, restoring the pre-work's original "219 code files" count. All 207 gold
primaries are tracked, so nothing pinned is lost; readiness stayed GO/207-sentinel. Total
corpus is now **~8,733 chunks** across 6 repos (matches the pre-work estimate).

> **Skill-promotion candidate:** the shipped `setting-up-rag` loader (`rag_lib.load_corpus`)
> has the same gap — it would index a user's git-ignored `build/`, `artifacts/`, checkpoints,
> etc. Promote a `.gitignore`-respecting filter (git-tracked allowlist when the corpus is a git
> work tree; a per-file size cap as the non-git fallback). CPU-clean, license-neutral, clearly
> correct. Tracked in the Wave-1/2 promotion list.

## Results — overall (all 207)

| arm                          | R@5   | R@20  | R@100 | nDCG@10   | MRR       | pMRR      | sentCov   | hit@5     | contam | ctxTok | ms     |
| ---------------------------- | ----- | ----- | ----- | --------- | --------- | --------- | --------- | --------- | ------ | ------ | ------ |
| **plain-current** (baseline) | 0.714 | 0.956 | 0.992 | 0.608     | 0.530     | 0.530     | 0.793     | 0.744     | 1.41   | 6372   | 1499   |
| **plain-current-no-rerank**  | 0.767 | 0.953 | 0.992 | **0.625** | **0.565** | **0.565** | **0.820** | **0.812** | 1.40   | 6544   | **37** |
| dense-only                   | 0.716 | 0.952 | 1.000 | 0.594     | 0.531     | 0.531     | 0.801     | 0.754     | 1.51   | 5799   | 49     |
| bm25-only                    | 0.723 | 0.905 | 0.984 | 0.596     | 0.541     | 0.541     | 0.774     | 0.758     | 1.32   | 7162   | 46     |
| _wrong-context_ (control)    | 0.140 | 0.391 | 0.560 | 0.126     | 0.114     | 0.114     | 0.211     | 0.145     | 1.43   | 6374   | —      |
| _closed-book_ (control)      | 0.000 | 0.000 | 0.000 | 0.000     | 0.000     | 0.000     | 0.000     | 0.000     | 0.00   | 0      | —      |
| _manual-simple_ (rg floor)   | 0.545 | 0.896 | 0.995 | 0.435     | 0.367     | 0.367     | 0.944     | 0.812     | 1.23   | 116162 | 16     |

(`ms` = mean per-query retrieval latency; `ctxTok` = char/4 token estimate of the packed top-20.)

## Findings

### 1. The shipped MiniLM cross-encoder reranker HURTS ranking — and costs 40× latency

Removing the reranker (otherwise identical config) **improves every ranking and grounding
metric** and holds on held-out:

| metric            | held-out Δ (no-rerank − rerank) | overall: rerank → no-rerank |
| ----------------- | ------------------------------- | --------------------------- |
| R@5               | —                               | 0.714 → **0.767** (+0.053)  |
| nDCG@10           | **+0.010**                      | 0.608 → 0.625               |
| MRR / primary-MRR | **+0.034**                      | 0.530 → 0.565               |
| sentinel coverage | +0.024                          | 0.793 → 0.820               |
| answer hit@5      | **+0.081**                      | 0.744 → 0.812               |
| R@20              | −0.005 (noise)                  | 0.956 → 0.953               |
| latency           | —                               | **1499 ms → 37 ms (40×)**   |

The reranker pushes relevant chunks _out of the top-5_ (R@5 −0.053, hit@5 −0.068 overall). The
cause is model–domain mismatch: `ms-marco-MiniLM-L-6-v2` is trained on web-prose passage
ranking and mis-scores code/technical chunks against paraphrased questions. The harm is broad —
both domains (code hit@5 +0.059, nl hit@5 +0.085 when removed) and **4 of 6 repos** (biggest:
`alpha-zero` pMRR 0.456 → 0.617). Two small repos see a mild rerank _benefit_
(`az-game-tic-tac-toe` nDCG −0.054, `az-game-xiang-qi` hit@5 −0.091 when removed), so a blanket
"disable" carries a small-slice caveat — but on the dominant slices, held-out, and latency, the
current reranker is **not earning its cost.**

→ **Carried to Wave 1** as the leading promotion candidate (disable the default reranker), and
to **Wave 3** (replace MiniLM with a code-capable reranker — `bge-reranker-v2-m3`,
`qwen3-reranker`; the right fix may be a _better_ reranker, not none).

### 2. Hybrid RRF fusion is justified — it beats either arm alone

No-rerank hybrid (nDCG 0.625, MRR 0.565, R@20 0.953) > dense-only (0.594 / 0.531 / 0.952) and >
bm25-only (0.596 / 0.541 / 0.905) overall. **Keep hybrid fusion.** Nuance: on _held-out_,
`bm25-only` ranking (nDCG 0.686, MRR 0.635) edges no-rerank hybrid (0.681 / 0.620) — the fusion
margin is dev-favored — so Wave 1 must re-confirm fusion gains on held-out and tune fusion
weights/`k` (Qdrant's server RRF hard-codes `k=2`).

### 3. Dense carries code recall; BM25 carries nl recall — a routing signal

R@20 by domain: **code** dense 0.935 ≫ bm25 0.863 (paraphrased code questions favor dense
semantics over literal identifiers); **nl** bm25 0.988 ≥ dense 0.974, with bm25 sentinel
coverage highest on nl (0.955). Fusion already combines both, but the asymmetry motivates the
Wave-1 weighted-fusion / Wave-6 per-cohort-routing experiments. The retriever stays type-blind;
this is a reporting observation, not a corpus split.

### 4. Controls are clean (the numbers are retrieval-dependent, not leakage)

- **closed-book** = 0.000 everywhere: no retrieval ⇒ no score. Confirms the gate measures
  retrieval, and (for Wave 7) that any closed-book answer correctness is parametric leakage.
- **wrong-context** collapses to R@20 0.391 / nDCG 0.126 / sentCov 0.211 (vs real 0.95 / 0.62 /
  0.82) under deterministic within-repo donor rotation — metrics are genuinely
  retrieval-dependent. (Non-zero because a same-repo donor occasionally shares a relevant file.)

### 5. RAG earns its cost vs the manual ripgrep floor

`manual-simple` is a strong _recall_ floor (R@20 0.896) and trivially "covers" sentinels
(0.944) because it returns **whole files** — but it ranks far worse (nDCG 0.435 vs 0.625, pMRR
0.367 vs 0.565) and packs **116,162 context tokens vs RAG's ~6,400 (18×)**. So RAG buys both
ranking quality _and_ an 18× smaller answer-context budget. (Where a repo is tiny and lexical,
ripgrep remains a fine floor — `retrieving-context`'s routing premise holds.)

### 6. Self-reference contamination is real but isolated

Per-query synthesis-doc flags (retrieved `docs/{plans,research,benchmarks}` that aren't the
query's primary) are **0.00 for all four Alpha-Zero repos**, 0.60 for `website`, and **5.91 for
`coding-agent-skills`** — the self-referential meta-repo, exactly as the pre-work predicted.
This does **not** inflate the gate (qrels are primary-only, so a non-primary synthesis hit is a
precision miss, not a false positive), but it flags that synthesis docs crowd
`coding-agent-skills` results — a Wave-1/2 target (per-query filtering / synthesis down-weight).

## Efficiency

| arm                     | mean latency | wall (incl. 1st index) | packed ctx tokens |
| ----------------------- | ------------ | ---------------------- | ----------------- |
| plain-current           | 1499 ms      | 963 s                  | 6,372             |
| plain-current-no-rerank | 37 ms        | 8 s                    | 6,544             |
| dense-only              | 49 ms        | 10 s                   | 5,799             |
| bm25-only               | 46 ms        | 10 s                   | 7,162             |
| manual-simple           | 16 ms        | 4 s                    | 116,162           |

**Index build (one-time, CPU bge-small, ~8,733 chunks):** 651 s total — `alpha-zero` 213 s,
`website` 188 s, `coding-agent-skills` 175 s dominate. Tractable but the slowest loop step; GPU
embed serving (Wave 3 infra) will accelerate Wave-2 re-index sweeps.

## Baseline declaration

- **Declared baseline (the shipped `setting-up-rag` default — the reference every later wave is
  measured against):** `plain-current` — `bge-small-en-v1.5` dense + Qdrant `bm25` sparse,
  server-side RRF fusion, **MiniLM rerank ON**, `top_k=20`. Overall **R@20 0.956 / nDCG@10
  0.608 / MRR 0.530 / sentCov 0.793 / hit@5 0.744**; held-out **R@20 0.987 / nDCG 0.670 / MRR
  0.586**; 1499 ms/query.
- **Current best after Wave 0 (the config Wave 1 iterates from):** `plain-current-no-rerank` —
  identical but rerank OFF. Overall **nDCG 0.625 / MRR 0.565 / sentCov 0.820 / hit@5 0.812** at
  **37 ms**. Beats the shipped baseline on every quality metric except a −0.005 R@20 (noise) and
  two small-repo nDCG/hit@5 slices; 40× faster.

## Keep / revert decisions

| change                                                 | decision                              | basis                                                                  |
| ------------------------------------------------------ | ------------------------------------- | ---------------------------------------------------------------------- |
| `.gitignore`-respecting corpus (git-tracked allowlist) | **KEEP** (harness) + promote to skill | removes 84%-noise repo; 0 gold loss; correctness fix, not tuning       |
| Hybrid RRF fusion (vs dense- or bm25-only)             | **KEEP**                              | beats both single arms overall (re-confirm held-out in W1)             |
| MiniLM cross-encoder reranker (shipped default)        | **REVERT candidate → Wave 1**         | hurts held-out nDCG/MRR/hit@5, 40× latency; small-repo caveat to clear |
| Baseline = shipped `plain-current`                     | **DECLARED**                          | the reference floor for all later waves                                |

## Reproduce

```bash
H=docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/harness
VENV=~/.cache/rag-skill/venv/bin/python
QDRANT_URL=http://localhost:6343 $VENV $H/run_benchmark.py \
  --arm plain-current --arm plain-current-no-rerank --arm dense-only --arm bm25-only \
  --arm wrong-context --arm closed-book --arm manual-simple \
  --repos all --split all --tag 0010-wave0-baseline --out-dir docs/benchmarks/2026-06-09
python3 $H/report.py docs/benchmarks/2026-06-09/0010-wave0-baseline-summary.json
```
