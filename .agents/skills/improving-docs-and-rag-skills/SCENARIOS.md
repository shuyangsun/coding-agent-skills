# SCENARIOS — corpora, gold facts, traps, and the firewall

## Corpora (the factorial's corpus axis)

- **GOLD** — a frozen snapshot of today's `docs/` at a pinned revision, scored by
  the **frozen retrieval gate** (Plane 1). Moves here flag *instrument* drift, not
  skill quality. `gold.py --qrels-mode pinned`.
- **D** — `docs`-skill-authored: well-structured (clean headings, one concept per
  file, descriptive filenames, front-matter). The Phase-0 stand-in (`mk-corpus.py`)
  preserves the structured docs verbatim.
- **N** — naive dump: identical content and sentinels, structure destroyed
  (front-matter dropped, headings demoted, opaque filenames). Same doc count as D
  in `--mode perdoc` so doc-level recall is not saturated.

N and D carry the **same fact payload**, so any retrieval difference is
attributable to **structure** — the docs-axis signal. Labels for N/D are
**sentinel-derived per corpus** (`gold.py --qrels-mode sentinel`), never taken
from GOLD's paths (plan §3).

## The gold facts (the seed table in `gold.py`)

Grounded in this repo's own machine-checkable facts, verified at build time
(every sentinel must still occur in its pinned primary doc):

| Fact | Sentinel(s) | Primary doc | difficulty |
| --- | --- | --- | --- |
| benchmark conflict time | `380s`, `85s` | `benchmarks/0000-…` | medium |
| orphan empty head | `urruyqxt` | `issues/0007-…` | hard |
| name-metric durability | `reference-transaction` | `coding-sessions/2026-06-06/0012-…` | medium |
| Composer 2.5 benchmark | `Composer 2.5` | `benchmarks/0002-…` | medium |
| integrate degenerate merge | `degenerate` | `issues/0003-…` | medium |

This is a **seed**. The plan calls for 50–100+ queries (a power calc): enumerate
the cross-link graph as relevance pairs and add anchored paraphrases. Growing the
`FACTS` table in `gold.py` is ordinary round work; validation + the firewall keep
it honest.

## The non-circularity firewall (plan §6, enforced by `gold.py`)

1. **No echoes.** A query may not contain its own sentinel verbatim, and its
   token-trigram Jaccard with the primary doc must stay below `LEXICAL_OVERLAP_MAX`
   (queries are paraphrases, not lookups). Violations fail `gold.py validate`.
2. **Dev/held-out split.** Stable `hash(query_id)` parity (even=dev, odd=held-out),
   never regenerated per round. Tune on dev; clear the bar only on held-out.
3. **Self-reference exclusion.** The harness's own plan + its session transcript
   (which quote the gold facts as worked examples) are excluded from every corpus
   (`EXCLUDE_GLOBS`), so the gold set never points at a doc that merely cites a
   fact. `.agents/` (skills/harness) is never in the corpus.
4. **Closed-book control (Phase 1).** Generate with empty context; if the model
   emits a sentinel from parametric memory, exclude that query from factuality.
   `retrieval_hit` (judge-free) is the primary answerability signal regardless.

## The WRITE convention trap (the `--task write` loop)

A sub-agent with **only** `docs` authors into an empty `docs/` from a fixed fact
payload, against a seeded trap: a pre-existing `NNNN` index forcing a
globally-unique number, and a divergent flat doc to standardize. Scored on
`CONV_OK` (durable file signals) and `WRITE_FINDABLE` (the just-authored doc,
indexed against a fixed background index, surfaces in top-k). `next-index.sh` and
`check-convention.sh` (future) own this.

## Contamination firewall (the agents under test)

Sub-agents see **only** the skill under test (`docs` *or* `rag`) and a realistic
task — never this harness, never the gold queries, never `metrics.tsv`. The
RAG-setup agent in particular is **blind to the gold queries** so it tunes to
doc-set properties, not to the test.
