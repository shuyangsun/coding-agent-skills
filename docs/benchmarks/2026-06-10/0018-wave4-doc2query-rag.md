# Wave 4 — Doc2Query / document expansion (gemma-4)

- **Date:** 2026-06-10
- **Wave:** 4 (contextual / long-document retrieval), step 4 — "Doc2Query / document expansion"
- **Plan:** [`0008-consolidated-rag-optimization-phase-2.md`](../../plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md) §"Wave 4"
- **Harness:** `…/0008-…/harness/{wave4_doc2query.py,enriched_index.py (bm25_text),run_benchmark.py,wave4_analyze.py}`
- **Artifacts:** `0018-wave4-doc2query-metrics.tsv`, `-summary.json`
- **Generator:** `gemma-4` (Gemma-4-31B-IT, NVFP4, vLLM), 4 predicted queries/chunk, 9361 chunks
- **Disposition:** **Partial win — campaign-side.** All-chunks Doc2Query is a robust **code** win
  (held-out code nDCG +0.030 sparse / +0.060 both; dev +0.043 / +0.076) but carries an **nl slice
  cost** that contextual retrieval ([`0014`](0014-wave4-contextual-gemma4-rag.md)) avoids. The
  plan's **prose-only** hypothesis is **rejected** (it regresses code). Contextual retrieval stays
  the **preferred** index-time-LLM technique; Doc2Query-`all-sparse` is a viable campaign
  alternative when code retrieval is the priority. Portable default unchanged.

## What changed

`wave4_doc2query.py` asks gemma-4 for **4 search queries each chunk answers** (mixed questions +
keyword phrases) and caches them like the contextual-retrieval generator. The indexer appends them
to a **separate `bm25_text` field** (faithful Doc2Query: lexical expansion only, dense + `raw_text`
untouched) or to `contextualized_text` (dense+sparse). Four arms, one variable each:

| arm                        | predicted queries appended to | applied to                          |
| -------------------------- | ----------------------------- | ----------------------------------- |
| `w2-ctx-header` (baseline) | —                             | —                                   |
| `w4-d2q-nl-sparse`         | BM25 field only               | **md only** (the plan's hypothesis) |
| `w4-d2q-all-sparse`        | BM25 field only               | md + code                           |
| `w4-d2q-all-both`          | BM25 **and** dense field      | md + code                           |

## Results

### Held-out (n=111) — overall + domain

| split=held-out | arm                 | nDCG@10            | pMRR           | sentCov        | hit@5          |
| -------------- | ------------------- | ------------------ | -------------- | -------------- | -------------- |
| overall        | `w2-ctx-header`     | 0.733              | 0.669          | 0.833          | 0.793          |
| overall        | `w4-d2q-nl-sparse`  | 0.719 (−0.013)     | 0.652 (−0.017) | 0.841          | 0.793          |
| overall        | `w4-d2q-all-sparse` | 0.752 (+0.020)     | 0.686 (+0.017) | 0.887 (+0.054) | 0.820 (+0.027) |
| overall        | `w4-d2q-all-both`   | 0.765 (+0.032)     | 0.698 (+0.029) | 0.917 (+0.084) | 0.838 (+0.045) |
| **code** (73)  | `w4-d2q-all-sparse` | 0.708 (**+0.030**) | 0.633 (+0.026) | 0.833 (+0.082) | 0.753 (+0.041) |
| **code** (73)  | `w4-d2q-all-both`   | 0.738 (**+0.060**) | 0.666 (+0.059) | 0.879 (+0.128) | 0.781 (+0.068) |
| nl (38)        | `w4-d2q-all-sparse` | 0.838 (+0.000)     | 0.788 (+0.000) | 0.991          | 0.947          |
| nl (38)        | `w4-d2q-all-both`   | 0.817 (−0.021)     | 0.760 (−0.028) | 0.991          | 0.947          |

Dev replicates the code win (all-sparse **+0.043**, all-both **+0.076**) with nl flat
(−0.011 / +0.001) — so the win is robust, not held-out luck.

## Analysis

1. **Prose-only Doc2Query (the plan's hypothesis) is wrong — it _hurts_.** `w4-d2q-nl-sparse`
   regresses overall (−0.013) and code (−0.025, with xiang-qi code −0.081). Expanding **only** the
   prose chunks' lexical field makes them artificially competitive for code-domain queries, crowding
   real code chunks out. This is the **third** confirmation of the lesson from
   [`0014`](0014-wave4-contextual-gemma4-rag.md): **never restrict index-time context to prose** —
   code is where it must apply.
2. **All-chunks Doc2Query is a real code win.** Predicting natural-language questions over
   identifier-dense **code** chunks bridges the NL-question↔code-identifier vocabulary gap exactly
   where dense+BM25 were weakest (code sentinel coverage +0.082 sparse / +0.128 both).
3. **Putting the expansion in the dense field too (`all-both`) helps code more but costs nl.**
   The predicted questions are semantically close to real queries, so the dense vector benefits on
   code (+0.060 vs +0.030) — but on already-strong prose they add noise (nl −0.021; website nl
   −0.055). `all-sparse` keeps dense clean and so keeps nl flat.
4. **It is a code-vs-nl trade, unlike contextual retrieval.** Every d2q arm regresses **alpha-zero
   design-docs (nl −0.062)** — appended queries shift the BM25 term landscape against a few
   lexical-precise nl questions. Contextual retrieval (`0014`) reached the **same overall quality**
   (held-out nDCG 0.767 vs d2q-all-both 0.765, sentinel 0.913 vs 0.917) **without** those nl
   regressions. So as an index-time-LLM technique, contextual retrieval is **cleaner**.
5. **Index-time only.** Like contextual retrieval, the expansion lives in the index; `raw_text` is
   what gets packed/cited, so answer-context tokens and query latency are unchanged (the ms spread
   in the run log is FastEmbed CPU contention from a co-running benchmark).

## Decision

- **Reject `w4-d2q-nl-sparse`** (prose-only) — regresses code.
- **`w4-d2q-all-sparse` is the safe Doc2Query arm** (code +0.030 held-out / +0.043 dev, nl flat in
  aggregate); **`w4-d2q-all-both`** trades a bigger code win (+0.060) for an nl cost (−0.021) — use
  only when code retrieval is the priority.
- **Campaign-side (needs an index-time LLM)** — not portable, exactly like contextual retrieval.
- **Contextual retrieval ([`0014`](0014-wave4-contextual-gemma4-rag.md)) remains the recommended
  index-time-LLM default** (same code win, no nl regression). Doc2Query is a measured alternative,
  not a replacement.
- **Untested follow-up:** stacking Doc2Query on top of contextual retrieval (situating context in
  dense, predicted queries in the BM25 field) could compound the code win — worth a Wave-4 add-on if
  a code-heavy corpus justifies it.

## Reproduce

```bash
H=docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/harness
CFG=docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/configs
CAMP=~/developer/third-party/python_venvs/rag_campaign_env/.venv/bin/python
RAG=~/.cache/rag-skill/venv/bin/python
$CAMP $H/wave4_doc2query.py generate --repo all --model gemma-4 \
  --base-url https://llm.shuyangsun.com/v1 --apply-to md,code --workers 32 --n 4
$RAG $H/run_benchmark.py --split all --tag 0018-wave4-doc2query --out-dir docs/benchmarks/2026-06-10 \
  --config $CFG/wave2/w2-ctx-header.json --config $CFG/wave4/w4-d2q-nl-sparse.json \
  --config $CFG/wave4/w4-d2q-all-sparse.json --config $CFG/wave4/w4-d2q-all-both.json
python3 $H/wave4_analyze.py docs/benchmarks/2026-06-10/0018-wave4-doc2query-metrics.tsv \
  --baseline w2-ctx-header --splits held-out,dev
```
