# Wave 4 — long-context reader / packing arms (scoping record)

- **Date:** 2026-06-10
- **Wave:** 4 (contextual / long-document retrieval), step 6 — "long-context reader arms: compare
  whole sections/files/sessions with source-order, score-order, and parent-before-child packing"
- **Plan:** [`0008-consolidated-rag-optimization-phase-2.md`](../../plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md) §"Wave 4"
- **Disposition:** **Correctly deferred to Wave 7 (answer generation).** Packing **order** is
  invariant under every retrieval-stage metric this harness computes, so it cannot be measured here;
  the discriminating metric is answer faithfulness, which is Wave 7. Recorded with the proof rather
  than run, so the Wave-4 ledger is complete and Wave 7 inherits a precise task.

## Why packing _order_ is not a retrieval-stage experiment

Step 6 asks to compare **packing orders** (source-order vs score-order vs parent-before-child) of
the retrieved context. But the order in which the top-k chunks are arranged for the reader does not
move **any** metric the benchmark gates on — they are all order-invariant by construction:

| metric                              | why order-invariant                                                                                 |
| ----------------------------------- | --------------------------------------------------------------------------------------------------- |
| recall@k, nDCG@10, MRR, primary-MRR | computed from the **file-level ranked list** (retrieval rank), which packing order does not touch   |
| sentinel coverage                   | `count(s in "\n".join(top_k chunks))` — **set membership** over the join; arrangement is irrelevant |
| answer hit@5                        | any sentinel in the **union** of the top-5 chunks — which 5 is set by rank, not by packing order    |
| packed context tokens               | a **sum** over the top-k chunks — order-free                                                        |

The thing packing order _does_ change is how a **generator** reads the context — the
lost-in-the-middle effect, where evidence at the start/end of the prompt is used more reliably than
evidence buried in the middle. Measuring that requires an answer-generation pass and a faithfulness
/ answer-correctness judge — i.e. **Wave 7** (the harness's `gen.*` / `ver.citation_support`
channels, deliberately left unfilled at the retrieval stage). Running an order A/B here would print
four identical numbers.

## What _is_ measured here (the reader cost, order-free)

The harness already records the reader's context budget — the packed top-k chunk cost, drawn from
verbatim `raw_text`:

| arm                                     | packed context tokens (top_k=20) | chunks |
| --------------------------------------- | -------------------------------- | ------ |
| `w2-ctx-header` (portable best)         | ~6365                            | 20     |
| `w4-ctx-llm-gemma4-all` (campaign best) | ~6196                            | 20     |

Index-time techniques (contextual retrieval, Doc2Query) leave this **unchanged** — the context is
embedded, never packed — so they add no reader cost. `top_k` is the lever that trades this budget
against recall (the Wave-0 prefetch/top_k sweep); a smaller model gets fewer, larger-evidence-density
chunks.

## What belongs to other waves (not Wave 4 step 6)

- **Packing _granularity_** — returning whole **parent sections/files** instead of child chunks —
  _does_ change sentinel coverage and token cost, so it **is** retrieval-measurable. But that is
  **parent-window / small-to-big retrieval = Wave 2 step 2**, which the plan still lists as open. The
  payload already carries `parent_id` / `parent_start` / `parent_end` to support it; scoped to Wave 2,
  not duplicated here.
- **Context tokens to first supporting evidence** (an order-_dependent_ efficiency metric the plan
  lists) needs per-query packed-order instrumentation + a generation pass to be meaningful; folded
  into the Wave-7 answer-packer task below.

## Hand-off to Wave 7

When Wave 7 stands up the source-preserving context packer + faithfulness judge, the order A/B has a
precise, ready form: same retrieved top-k, three packings (source-order, score-order,
parent-before-child), scored on answer correctness + citation support + tokens-to-first-evidence —
**not** on the order-invariant retrieval metrics. Until then there is nothing to keep or revert here.
