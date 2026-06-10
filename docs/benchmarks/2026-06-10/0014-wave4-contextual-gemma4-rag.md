# Wave 4 — Anthropic-style contextual retrieval (gemma-4)

- **Date:** 2026-06-10
- **Wave:** 4 (contextual / long-document retrieval), step 1 — LLM situating context
- **Plan:** [`0008-consolidated-rag-optimization-phase-2.md`](../../plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md) §"Wave 4"
- **Harness:** `…/0008-…/harness/{wave4_context.py,enriched_index.py,run_benchmark.py,wave4_analyze.py}`
- **Artifacts:** `0014-wave4-contextual-gemma4-metrics.tsv`, `-summary.json`
- **Generator:** `gemma-4` (Gemma-4-31B-IT, NVFP4, vLLM) at `llm.shuyangsun.com`
- **Disposition:** **PROMOTE to the campaign (GPU) config** — header + LLM-context on **all** chunks. Portable CPU default unchanged (this needs an index-time LLM). Keep the deterministic header.

## Headline

Generating a 1–2 sentence LLM "situating context" per chunk (Anthropic's contextual
retrieval) and prepending it to the **embedding/sparse field** (raw text stays
verbatim) beats the Wave-2 deterministic-header baseline on every held-out gating
metric, **driven almost entirely by the code domain**:

| held-out (n=111) | nDCG@10 | primary-MRR | recall@20 | sentinel cov | answer hit@5 |
| --- | --- | --- | --- | --- | --- |
| `w2-ctx-header` (baseline) | 0.735 | 0.669 | 0.986 | 0.833 | 0.793 |
| **`w4-llm-all`** (header + LLM, all chunks) | **0.765 (+0.031)** | **0.702 (+0.033)** | 0.995 | **0.913 (+0.080)** | **0.847 (+0.054)** |

The win is **index-time only**: query latency (≈38 ms) and packed answer-context cost
(≈6.2k tokens, drawn from verbatim `raw_text`) are unchanged. The sole added cost is a
one-time generation pass (9,139 chunks, ~19 min on the local gemma-4 at ~8 chunk/s).

## What changed

`wave4_context.py` calls the local LLM once per chunk with the Anthropic prompt
(document + chunk → "give a short context to situate this chunk for search
retrieval"), caches the result on disk keyed by `(model, repo, path, byte-span)`, and
`enriched_index.contextual_text()` prepends it to the deterministic header in the
embedded field:

```text
[repo] path :: heading/symbol (kind)      ← Wave-2 header (kept)
<1–2 sentence LLM situating context>      ← Wave-4 addition
                                          ← blank line
<verbatim raw_text>                       ← embedded; ALSO what is retrieved/cited
```

Only `contextualized_text` (dense + BM25 input) changes; `raw_text` stays byte-verbatim
for citations/sentinels. Four arms, one variable each:

| arm | header | LLM context | apply to |
| --- | --- | --- | --- |
| `w2-ctx-header` (baseline) | ✓ | — | — |
| `w4-llm-all` | ✓ | ✓ | code + md |
| `w4-llm-nl` | ✓ | ✓ | md only |
| `w4-llm-all-noheader` | — | ✓ | code + md |

Generation: 9,139 chunks, 0 failures, avg ~210 chars (~45 tokens) of context, 25 docs
head-truncated at the 48k-char document window. Cache: `~/.cache/rag-skill/wave4-context/gemma-4/`.

## Results

### Overall (all 207, mechanically from `report.py`)

| arm | R@5 | R@20 | nDCG@10 | pMRR | sentCov | hit@5 | ctxTok | ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `w2-ctx-header` | 0.791 | 0.963 | 0.681 | 0.617 | 0.853 | 0.812 | 6362 | 38 |
| `w4-llm-all` | 0.846 | 0.977 | 0.721 | 0.655 | 0.919 | 0.865 | 6205 | 38 |
| `w4-llm-nl` | 0.798 | 0.965 | 0.698 | 0.638 | 0.854 | 0.807 | 6241 | 44 |
| `w4-llm-all-noheader` | 0.849 | 0.990 | 0.725 | 0.659 | 0.909 | 0.870 | 6261 | 43 |

### Held-out by domain (`wave4_analyze.py`) — the decisive view

**domain=code (n=73)** — the LLM context is a large win here:

| arm | nDCG@10 | pMRR | sentCov | hit@5 |
| --- | --- | --- | --- | --- |
| `w2-ctx-header` | 0.676 | 0.600 | 0.751 | 0.712 |
| `w4-llm-all` | 0.721 (**+0.045**) | 0.648 (**+0.048**) | 0.874 (**+0.123**) | 0.795 (**+0.082**) |
| `w4-llm-all-noheader` | 0.733 (**+0.057**) | 0.660 (**+0.060**) | 0.870 (+0.119) | 0.836 (**+0.123**) |
| `w4-llm-nl` | 0.695 (+0.019) | 0.617 (+0.017) | 0.756 (+0.005) | 0.712 (+0.000) |

**domain=nl (n=38)** — already near ceiling with the header; LLM context is ~flat:

| arm | nDCG@10 | pMRR | sentCov | hit@5 |
| --- | --- | --- | --- | --- |
| `w2-ctx-header` | 0.848 | 0.802 | 0.991 | 0.947 |
| `w4-llm-all` | 0.851 (+0.003) | 0.805 (+0.003) | 0.987 (−0.004) | 0.947 |
| `w4-llm-nl` | 0.861 (+0.014) | 0.820 (+0.019) | 0.978 (−0.013) | 0.947 |
| `w4-llm-all-noheader` | 0.840 (**−0.008**) | 0.791 (**−0.011**) | 1.000 | 0.947 |

## Analysis

1. **The win is the code domain.** Code chunks are dense in identifiers but thin in
   prose; a sentence naming the file/struct/component the chunk belongs to ("defines
   the `MctsConfig` struct … for Monte-Carlo Tree Search") adds the semantic surface
   that dense + BM25 were missing. Sentinel coverage on code jumps **+0.123**.
2. **Prose was already solved by the header.** `nl` sits at nDCG 0.85 / sentinel 0.99
   with the Wave-2 header alone, so there is little headroom; LLM context neither helps
   nor hurts it materially.
3. **Contextualize code too — the "dilution" worry was wrong.** `w4-llm-nl` (prose-only,
   the plan's starting hypothesis) gains only +0.019 nDCG on code (incidental, via
   co-retrieved docs) vs **+0.045** for `w4-llm-all`. Adding prose context to the code
   sparse field did **not** blur identifier matching — recall@20 on code went 0.986→1.000.
4. **Keep the deterministic header.** `w4-llm-all-noheader` edges `w4-llm-all` on code
   but **regresses nl** (nDCG −0.008, pMRR −0.011, and website-nl −0.084 nDCG / −0.114
   pMRR in the slice scan): removing the structural anchor hurts prose. `w4-llm-all`
   (header **and** LLM) keeps the nl ceiling while taking the code win — the balanced pick.

### Regression scan (held-out, `wave4_analyze.py`)

No arm is perfectly clean at the strict per-(repo×domain×difficulty) ε=0.005 gate. The
flagged cells for `w4-llm-all` are: **az-game-xiang-qi code** (nDCG −0.035, pMRR −0.056)
and a few **easy** cells. Reading them:

- **xiang-qi (Chinese) is the one real soft spot** — gemma writes *English* situating
  contexts over Chinese code/terms, which helps less and slightly reshuffles its top
  results. A multilingual generator (or Chinese-language contexts) is the Wave-4 follow-up
  for that slice; flagged for the model comparison.
- **"easy" cells are small-n ceiling noise** — easy-nl baseline is nDCG/​pMRR = 1.000
  over ~6 questions, so one chunk moving from rank 1→2 reads as a large negative delta.
  These do not appear in the domain aggregates (code +0.045, nl +0.003).

The aggregate code/nl picture (big code win, flat nl) holds; the only substantive
non-noise regression is xiang-qi code, isolated to the Chinese cohort.

## Decision

- **Campaign (GPU) config — PROMOTE `w4-llm-all`:** header + gemma-4 LLM situating
  context on **all** chunks. Clear held-out win (nDCG +0.031, code nDCG +0.045, sentinel
  +0.080, hit@5 +0.054) at **zero query-time or answer-context cost**; the only soft spot
  is the Chinese slice (a generator-choice follow-up).
- **Keep the deterministic header** (do not ship `noheader`): it protects the prose ceiling.
- **Portable CPU default unchanged.** Contextual retrieval needs an index-time generative
  LLM, so it cannot ship in the CPU-only `setting-up-rag` default. The portable default
  stays Wave-2 (header, no LLM). This is documented as the **campaign upgrade**.
- **`w4-llm-nl` rejected** — strictly dominated by `w4-llm-all`.

## Reproduce

```bash
H=docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/harness
CFG=docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/configs
CAMP=~/developer/third-party/python_venvs/rag_campaign_env/.venv/bin/python
RAG=~/.cache/rag-skill/venv/bin/python

# 1) generate + cache contexts (needs the gemma-4 endpoint)
$CAMP $H/wave4_context.py generate --repo all --model gemma-4 \
  --base-url https://llm.shuyangsun.com/v1 --workers 32

# 2) index + score the four arms (Qdrant :6343, FastEmbed CPU)
$RAG $H/run_benchmark.py --split all --tag 0014-wave4-contextual-gemma4 \
  --out-dir docs/benchmarks/2026-06-10 \
  --config $CFG/wave2/w2-ctx-header.json \
  --config $CFG/wave4/w4-ctx-llm-gemma4-all.json \
  --config $CFG/wave4/w4-ctx-llm-gemma4-nl.json \
  --config $CFG/wave4/w4-ctx-llm-gemma4-all-noheader.json

# 3) sliced A/B + regression scan
python3 $H/wave4_analyze.py docs/benchmarks/2026-06-10/0014-wave4-contextual-gemma4-metrics.tsv \
  --baseline w2-ctx-header
```

## Contamination

`coding-agent-skills` carries a high `contam` (≈5.9 synthesis-doc hits/query) because the
Wave-0–3 benchmark docs + the 0054 session transcript now live in its corpus. This is
**identical across all four arms** (same corpus), so the A/B deltas are unaffected; the
eval set and consolidated plan remain hard-excluded. The corpus_sig moved `aceb53→606d90`
vs Wave 0–3 from these added files, but held-out aggregates are unchanged (baseline
held-out nDCG 0.735 here vs 0.737 in Wave 2).
