# SCENARIOS — corpora, gold facts, traps, and the firewall

## Corpora (the factorial's corpus axis)

- **Z** — the **floor**: an empty corpus (zero documents) scored with retrieval
  turned off (`docs-eval.py --no-retrieval`). The absolute "no doc, no RAG"
  baseline; every metric is identically 0. Built by `mk-corpus.py` (an empty `Z/`
  dir) and run **first** so all other cells read as lifts above nothing.
- **GOLD** — a frozen snapshot of today's `docs/` at a pinned revision, scored by
   the **frozen retrieval gate** (Plane 1). Moves here flag *instrument* drift, not
-  skill quality. `gold.py --qrels-mode pinned`.
  skill quality. `check-retrieval.py --qrels-mode pinned`.
  the **frozen retrieval gate** (Plane 1). Moves here flag _instrument_ drift, not
  skill quality. `gold.py --qrels-mode pinned`.
- **D** — `docs`-skill-authored: well-structured (clean headings, one concept per
  file, descriptive filenames, front-matter). The Phase-0 stand-in (`mk-corpus.py`)
  preserves the structured docs verbatim.
- **N** — naive dump: identical content and sentinels, structure destroyed
  (front-matter dropped, headings demoted, opaque filenames). Same doc count as D
  in `--mode perdoc` so doc-level recall is not saturated.

N and D carry the **same fact payload**, so any retrieval difference is
attributable to **structure** — the docs-axis signal. Labels for N/D are
**sentinel-derived per corpus** (`check-retrieval.py --qrels-mode sentinel`),
never taken from GOLD's paths (plan §3). (The pinned/sentinel logic lives in
`gold.py`'s `build_qrels`; the `--qrels-mode` flag is exposed on `check-retrieval.py`.)

## The content-type axis: natural language vs code

The corpora above are all **natural language** (`domain = nl`). A second content
type is scored separately:

- **code** (`domain = code`) — the repo's own [`inception/`](../../../inception)
  TanStack Start app (source + config), loaded by `gold.py`'s code loader (skips
  `node_modules`/build output/lockfiles), snapshot to `corpora/code/` by
  `mk-corpus.py`. "inception only for now."

Code facts pin primaries relative to the `inception/` root (e.g. `src/router.tsx`,
`vite.config.ts`, `package.json`) and are validated against the code corpus, never
the docs corpus. Coding-session **transcripts** are the emphasized `nl` content
type — long, dialog-shaped prose, a distinct retrieval challenge from the terse
issue/benchmark docs. The scoreboard reports `code` and `nl` with separate metrics
so the difference is visible rather than averaged away.

## The gold facts (the seed table in `gold.py`)

Grounded in this repo's own machine-checkable facts, verified at build time
(every sentinel must still occur in its pinned primary doc):

| Fact | Domain | Sentinel(s) | Primary doc (relative to its domain's corpus root) | difficulty |
| --- | --- | --- | --- | --- |
| benchmark conflict time | nl | `380s`, `85s` | `benchmarks/2026-06-06/0000-…` | medium |
| orphan empty head | nl | `urruyqxt` | `issues/2026-06-07/0007-…` | hard |
| name-metric durability | nl | `reference-transaction` | `coding-sessions/2026-06-06/0012-…` | medium |
| Composer 2.5 benchmark | nl | `Composer 2.5` | `benchmarks/2026-06-07/0002-…` | medium |
| integrate degenerate merge | nl | `degenerate` | `issues/2026-06-07/0003-…` | medium |
| inception toolchain (transcript) | nl | `native-preview` | `coding-sessions/2026-06-07/0028-…` | medium |
| router preload | code | `defaultPreload` | `src/router.tsx` | medium |
| React Compiler wiring | code | `@rolldown/plugin-babel`, `reactCompilerPreset` | `vite.config.ts` | hard |
| typecheck compiler | code | `tsgo --noEmit` | `package.json` | medium |
| Fact                       | Sentinel(s)             | Primary doc                         | difficulty |
| -------------------------- | ----------------------- | ----------------------------------- | ---------- |
| benchmark conflict time    | `380s`, `85s`           | `benchmarks/0000-…`                 | medium     |
| orphan empty head          | `urruyqxt`              | `issues/0007-…`                     | hard       |
| name-metric durability     | `reference-transaction` | `coding-sessions/2026-06-06/0012-…` | medium     |
| Composer 2.5 benchmark     | `Composer 2.5`          | `benchmarks/0002-…`                 | medium     |
| integrate degenerate merge | `degenerate`            | `issues/0003-…`                     | medium     |

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
3. **Self-reference + index exclusion.** The harness's own plan + its session
   transcript (which quote the gold facts as worked examples) **and every
   `OVERVIEW.md`** directory index are excluded from every corpus
   (`EXCLUDE_GLOBS`), so the gold set never points at a doc that merely cites a
   fact, and a retriever can't score a hit by surfacing the directory listing
   instead of the answer (index docs aggregate many facts' sentinels, which would
   inflate sentinel-mode qrels). `.agents/` (skills/harness) is never in the corpus.
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

Sub-agents see **only** the skill under test (`docs` _or_ `rag`) and a realistic
task — never this harness, never the gold queries, never `metrics.tsv`. The
RAG-setup agent in particular is **blind to the gold queries** so it tunes to
doc-set properties, not to the test.
