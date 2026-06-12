# Wave 4 — deterministic session metadata capsule (LLM-free)

- **Date:** 2026-06-10
- **Wave:** 4 (contextual / long-document retrieval), step 5 — "session metadata and summaries"
- **Plan:** [`0008-consolidated-rag-optimization-phase-2.md`](../../plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md) §"Wave 4"
- **Harness:** `…/0008-…/harness/{enriched_index.py (session_capsule),run_benchmark.py,wave4_analyze.py}`
- **Artifacts:** `0017-wave4-session-meta-metrics.tsv`, `-summary.json`
- **Disposition:** **WEAK POSITIVE, corpus-conditional** — clear on-target win on the website
  session-transcript slice (held-out nDCG/pMRR 0.93→**1.00**), modest overall held-out lift
  (nDCG +0.019, pMRR +0.025) that sits near the measured re-index noise floor. **Promote as an
  OPTIONAL portable enrichment for transcript / session-history corpora** (deterministic, no LLM),
  gated on a gold-set check — not an unconditional default.

## What changed

A purely deterministic (LLM-free) **session capsule** is prepended to every chunk of a session
transcript — files matching `…/transcripts/<date>/<NNNN>-<vendor>-<name>.md` or
`…/llm-sessions-history/<date>/…`. It is parsed from the path + the whole document:

```text
[website] llm-sessions-history/2026-05-23/0000-claude-…md :: <heading> (md)   ← Wave-2 header (kept)
session 0000 claude 2026-05-23 — multi agent config and export skill;          ← NEW capsule
  files: settings.json, next-index.sh, .codex/config.toml, …                   ← mentioned-file list
                                                                               ← blank line
<verbatim raw_text>                                                            ← embedded + cited
```

The Wave-2 header already encodes the path (date, index, vendor, kebab name), so the capsule's
**genuinely new signal is the mentioned-file list** (the files a session touched, which a chunk
mid-transcript otherwise lacks) plus a normalized session tag. `raw_text` stays verbatim;
`session_capsule()` is computed once per transcript doc and reused for all its chunks. **No LLM,
no GPU, no network — portable-eligible.** Target: the 33 `session-prompting` gold questions (15 of
whose primaries are transcripts — 11 of them in website's `llm-sessions-history/`).

## Results

### Held-out (n=111) — overall + domain (`wave4_analyze`)

| split=held-out             | R@20  | nDCG@10            | pMRR               | sentCov | hit@5          |
| -------------------------- | ----- | ------------------ | ------------------ | ------- | -------------- |
| `w2-ctx-header` (baseline) | 0.986 | 0.730              | 0.665              | 0.833   | 0.793          |
| `w4-sess-meta`             | 0.986 | **0.750 (+0.019)** | **0.690 (+0.025)** | 0.833   | 0.802 (+0.009) |
| — domain=code (n=73)       | 0.986 | 0.684 (+0.015)     | 0.613 (+0.019)     | 0.751   | 0.712          |
| — domain=nl (n=38)         | 0.987 | 0.875 (+0.028)     | 0.838 (+0.036)     | 0.991   | 0.974 (+0.026) |

### The target: `category=session-prompting`

| slice                          | arm                | n   | nDCG@10            | pMRR               | sentCov |
| ------------------------------ | ------------------ | --- | ------------------ | ------------------ | ------- |
| held-out                       | `w2-ctx-header`    | 19  | 0.879              | 0.840              | 1.000   |
| held-out                       | **`w4-sess-meta`** | 19  | **0.935 (+0.056)** | **0.912 (+0.072)** | 1.000   |
| held-out · website             | `w2-ctx-header`    | 10  | 0.932              | 0.912              | 1.000   |
| held-out · website             | **`w4-sess-meta`** | 10  | **1.000 (+0.068)** | **1.000 (+0.088)** | 1.000   |
| held-out · coding-agent-skills | `w2-ctx-header`    | 9   | 0.821              | 0.759              | 1.000   |
| held-out · coding-agent-skills | `w4-sess-meta`     | 9   | 0.862 (+0.041)     | 0.815 (+0.056)     | 1.000   |
| dev                            | `w2-ctx-header`    | 14  | 0.792              | 0.720              | 1.000   |
| dev                            | `w4-sess-meta`     | 14  | 0.768 (−0.024)     | 0.690 (−0.030)     | 1.000   |

The capsule drives website's session-transcript questions to **perfect** held-out ranking — the
intended mechanism (the mentioned-file list + session tag pulls the right transcript above its
siblings). coding-agent-skills gains less (only 4 of its 18 session-prompting primaries are
transcripts; the rest are synthesis docs already well-anchored by their path header). The dev
session-prompting slice (n=14) regresses −0.024 — see noise below.

## The re-index noise floor (a methodological control, free from this run)

The regression scan flags **6 cells, all `alpha-zero` code** (nDCG −0.034, pMRR −0.045). But
**alpha-zero has no transcript files**, so `session_capsule()` returns `None` for every one of its
chunks — its `w4-sess-meta` embedded text is **byte-identical** to `w2-ctx-header`. The two arms'
alpha-zero vectors are therefore identical; the only difference is that `w4-sess-meta`'s collection
is a **fresh HNSW build** while `w2`'s was reused. So the −0.034 is **pure Qdrant HNSW
re-index non-determinism** — it bounds the per-slice noise floor at **~0.03** (largest on the
biggest/hardest code slice; the 111-question average is steadier).

Consequences for reading this result:

- The **overall** held-out +0.019 nDCG is modest and **near (slightly above) that noise floor** —
  real but small.
- The **website session-prompting** +0.068 (→ perfect) is **above** the floor, **on-target**, and
  mechanistically sensible — the genuine effect.
- The **dev session-prompting** −0.024 (n=14) is **within** the floor — noise, not a capsule effect.
- This floor applies to **every** small per-slice delta in the campaign; deltas < ~0.03 on a single
  slice should not be trusted without repetition. (It does not affect large results like the
  late-chunking −0.115 in [`0016`](0016-wave4-latechunk-rag.md).)

## Decision

- **Promote as an OPTIONAL, corpus-conditional portable enrichment.** It is deterministic, CPU-only,
  license-neutral, and it cleanly helps the slice it targets (session/transcript retrieval) with no
  real regression (the flagged code cell is identical-text re-index noise). It belongs in the
  portable skill as a **documented option for transcript-heavy corpora**, enabled + validated on a
  gold set — **not** forced into the default, because the overall lift is small and concentrated on
  corpora that actually contain session transcripts.
- **Mechanism note for the skill:** the win is the **mentioned-file list**, not the date/index/vendor
  (those are already in the path header). A capsule that only restates the path adds nothing.
- **Latency:** index-time only for the deterministic parse; query latency unchanged (the 86 ms vs
  38 ms in the run log is FastEmbed CPU contention from a co-running benchmark, not the capsule).

## Reproduce

```bash
H=docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/harness
CFG=docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/configs
RAG=~/.cache/rag-skill/venv/bin/python
$RAG $H/run_benchmark.py --split all --tag 0017-wave4-session-meta --out-dir docs/benchmarks/2026-06-10 \
  --config $CFG/wave2/w2-ctx-header.json --config $CFG/wave4/w4-sess-meta.json
python3 $H/wave4_analyze.py docs/benchmarks/2026-06-10/0017-wave4-session-meta-metrics.tsv \
  --baseline w2-ctx-header --splits held-out,dev
```
