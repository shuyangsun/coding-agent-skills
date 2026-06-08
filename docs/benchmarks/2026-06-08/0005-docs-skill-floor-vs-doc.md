# Benchmark: `docs` skill — floor (no doc) vs with-doc findability (Phase 0)

**Date:** 2026-06-08
**Harness:** [`improving-docs-and-rag-skills`](../../../.agents/skills/improving-docs-and-rag-skills/SKILL.md)
— Phase-0 deterministic in-process eval (BM25 + in-memory vectors; no services, no
eval-time LLM; bit-reproducible).
**Under test:** the new [`docs`](../../../.agents/skills/docs/SKILL.md) skill —
specifically, **how findable the repo's docs are** when a blind consumer queries
for facts they contain.
**Not under test:** the `rag` skill (it does not exist yet). Retrieval is the
harness's **control** config [`baseline-b`](../../../.agents/skills/improving-docs-and-rag-skills/configs/baseline-b.json)
only — fixed 256-word chunks, one hashed embedder, dense-only, no fusion, no
rerank. No `rag`-skill tuning is applied.
**Domain:** natural-language (`nl`) markdown under `docs/`. The code content-type
axis (`inception/`) is out of scope this round.

Raw metrics (one row per query × cell): [0005-docs-skill-floor-vs-doc-metrics.tsv](0005-docs-skill-floor-vs-doc-metrics.tsv)

---

## What this measures

This is the **first** round of the `docs` harness and the answer to the most
basic question a docs skill must justify: **does having docs at all make the
repo's facts findable, and does writing them with structure help?**

It compares three conditions over the **same 6 gold facts** and the same
paraphrased queries (queries never echo their answer's sentinel; see the
harness firewall):

| Cell | Corpus | Retrieval | Reads as |
| ---- | ------ | --------- | -------- |
| **`Z`** (floor) | empty — **zero docs** | **none** (`--no-retrieval`) | the absolute "no doc, no RAG" baseline; every metric is identically `0` |
| **`Nb`** (naive ref) | naive dump — same content, structure destroyed (front-matter dropped, headings demoted, opaque filenames) | `baseline-b` | docs exist but unstructured |
| **`Db`** (with docs) | the repo's **structured** docs verbatim (clean headings, dated/indexed filenames, metadata headers) | `baseline-b` | docs written the way this repo writes them |

`Nb` and `Db` carry the **identical fact payload** and the same 54 documents
(`mk-corpus.py --mode perdoc`), so any `Db − Nb` difference is attributable to
**structure alone** — the docs-skill signal at a fixed, naive retriever.

> **Why `Db` = today's `docs/` and not the skill's output.** In Phase 0 the `D`
> corpus is a verbatim snapshot of the existing `docs/` tree. So this round
> measures the **conventions the `docs` skill codifies** (dated `NNNN-slug`
> filenames, per-type `OVERVIEW.md` indexes, H1 title + metadata header,
> one-concept-per-file), not the skill's generative WRITE loop — that loop and its
> `check-convention.sh` oracle are not built yet.

The gold facts (6 `nl`, 5 medium + 1 hard), as paraphrased queries:

| Query id | Type | Difficulty | Paraphrase |
| -------- | ---- | ---------- | ---------- |
| `bench-conflict-time` | benchmark | medium | how much did tuning the vcs skill speed up resolving a batch of merge conflicts? |
| `orphan-empty-head` | issue | hard | what stray jj change was left behind after a workspace cleanup, and how was it removed? |
| `name-metric-transaction-hook` | skill-behavior | medium | how is the workspace-naming convention scored durably even though branch names disappear on delete? |
| `composer-benchmark` | benchmark | medium | which coding model was benchmarked head-to-head on jj vs plain Git for the vcs skill? |
| `integrate-degenerate-merge` | issue | medium | why did the integrate helper sometimes create an empty merge that could not be pushed? |
| `session-inception-toolchain` | coding-session | medium | which exported session stood up the demo app so it type-checks with the native-Go TS compiler? |

---

## Headline (nl, n = 6 queries, `split=all`)

`retrieval_hit@20` (a grade-2 doc in the top 20) is the Phase-0 **answerability**
signal; `recall@20` is the headline IR metric.

| Metric | Floor `Z` (no doc) | **With docs `Db`** | **Lift vs floor** | Naive ref `Nb` |
| --------------------- | -----------------: | -----------------: | ----------------: | -------------: |
| **retrieval_hit@20**  |              0.000 |      **0.833** (5/6) |        **+0.833** |   0.833 (5/6) |
| **recall@20**         |              0.000 |          **0.642** |        **+0.642** |         0.642 |
| recall@10             |              0.000 |              0.433 |            +0.433 |         0.642 |
| recall@5              |              0.000 |              0.267 |            +0.267 |         0.433 |
| ndcg@10               |              0.000 |              0.280 |            +0.280 |         0.445 |
| mrr                   |              0.000 |              0.344 |            +0.344 |         0.552 |
| precision@5           |              0.000 |              0.133 |            +0.133 |         0.167 |
| index_ms / retr p50ms |        — (no index)|         95 / 1.1 ms|                 — |    94 / 1.2 ms|

**The floor → with-docs step is the largest, cleanest result in the run:**
answerability goes from **0% to 83%** (5 of 6 facts surfaced in the top 20) just
by having the repo's docs present and indexed.

### The docs marginal at baseline (`Db − Nb`) — structure alone

| Metric | `Db − Nb` | Reading |
| ----------------- | --------: | ------- |
| recall@20         |  **0.000** | structure adds **no** top-20 recall |
| retrieval_hit@20  |  **0.000** | same facts answerable either way |
| recall@10         |    −0.208 | structure pushes some answers past rank 10 |
| recall@5          |    −0.167 | …and past rank 5 |
| ndcg@10           |    −0.164 | slightly worse ranking |
| mrr               |    −0.207 | first relevant hit ranked lower |

At a **naive fixed-chunk dense retriever**, structured docs and a naive dump of
the same content **tie on recall and answerability**, and structure is in fact a
small *ranking* disadvantage (lower ndcg/mrr, answers a few ranks deeper). With
`n = 6` this dip is **directional, not significant** — but the direction is the
point: **fixed-256-word chunking ignores headings, so the structural advantage of
`D` has nothing to bite on.** This is the harness's coupling thesis in miniature —
the value of well-structured docs is **unlocked by structure-aware retrieval**
(heading-aware chunking, hybrid sparse+dense, rerank), i.e. by the `rag` skill,
which is deliberately **not** exercised here.

So read the `Db` column as a **lower bound** on the docs skill's value: it is the
payoff measured against the weakest retriever the harness offers.

---

## Per-query (recall@20 / hit@20 / mrr)

| Query | `Nb` | `Db` | Note |
| ----- | ---- | ---- | ---- |
| `bench-conflict-time`           | 0.00 / 0 / 0.00 | 0.00 / 0 / 0.00 | **missed by both** |
| `orphan-empty-head` (hard)      | 1.00 / 1 / 1.00 | 1.00 / 1 / 0.50 | found; `D` ranks it lower |
| `name-metric-transaction-hook`  | 1.00 / 1 / 0.11 | 1.00 / 1 / 0.07 | found deep in both |
| `composer-benchmark`            | 0.10 / 1 / 1.00 | 0.10 / 1 / 0.33 | grade-2 doc top-ranked; partial chunk recall |
| `integrate-degenerate-merge`    | 0.75 / 1 / 1.00 | 0.75 / 1 / 1.00 | tie |
| `session-inception-toolchain`   | 1.00 / 1 / 0.20 | 1.00 / 1 / 0.17 | found deep in both |

**The one consistent miss is `bench-conflict-time`.** Neither corpus surfaces
`benchmarks/2026-06-06/0000-…` for the paraphrase about *how much* conflict
resolution sped up (sentinels `380s`/`85s`). This is a **Phase-0 embedder limit,
not a doc defect**: the dense vector is a deterministic *hashed-lexical
placeholder* with no semantics, so a paraphrase that shares no surface tokens with
the answer chunk cannot match. A real embedder (Phase 1) is the fix; on the
**docs** side, the hedge is to state the headline number in plain prose directly
under a descriptive heading so even lexical retrieval lands it.

---

## Observations

1. **Docs are worth having — emphatically.** From nothing to the repo's docs,
   answerability jumps `0 → 83%`. Whatever else the `docs` skill does, having
   docs present and indexed is the dominant lever in this run.
2. **Structure is retrieval-neutral at a naive retriever, by construction.**
   `Db` and `Nb` tie on recall@20/hit@20 because fixed-256-word chunking is blind
   to the headings/sections that make `D` structured. The slight top-k ranking
   dip for `D` is within noise. **The docs skill's structural payoff is a
   docs×rag interaction, not a standalone docs effect** — which is exactly why
   this harness optimizes both skills together.
3. **One fact is currently unfindable** under the placeholder embedder; flagged
   for a Phase-1 re-measure with real embeddings.

### Coupling caveat (why no 2×2 this round)

The full factorial (marginals + interaction) needs all four cells —
`Nb, Nr, Db, Dr`. This round runs only the `b` (baseline) retrieval column, so
`Nr`/`Dr` are absent and the `rag` marginal and the docs×rag **interaction are
not computable**. That is intentional: the request was floor-vs-doc with no RAG.
The interaction — the headline number that tells us whether co-designed docs+rag
beat additive — waits for the round that adds `rag-r`.

---

## Reproduce

From the repo root, with `SK=.agents/skills/improving-docs-and-rag-skills` and a
sandbox `H="${DOCS_RAG_HARNESS_DIR:-$TMPDIR/docs-rag-harness}/0005"`:

```sh
# Gold set (single source of truth) + the corpus axis (Z empty / N naive / D structured).
python3 $SK/scripts/gold.py validate --corpus docs --code-corpus inception
python3 $SK/scripts/gold.py build    --corpus docs --code-corpus inception --out "$H/gold-set"
python3 $SK/scripts/mk-corpus.py     --corpus docs --code-corpus inception --out "$H/corpora"

# FLOOR FIRST — no doc, no retrieval (every metric is 0).
python3 $SK/scripts/docs-eval.py --corpus "$H/corpora/Z" --no-retrieval \
    --out "$H/cell-Z0" --corpus-tag Z --domain nl
python3 $SK/scripts/check-retrieval.py --run "$H/cell-Z0/run.jsonl" --corpus "$H/corpora/Z" \
    --qrels-mode sentinel --tsv-out "$H/metrics.tsv" --round 1 \
    --corpus-tag Z --rag-tag 0 --rag-config-id none --domain nl

# WITH DOC — naive (Nb) and structured (Db), baseline-b retrieval ONLY (no rag-r).
for corpus in N D; do
  python3 $SK/scripts/docs-eval.py --corpus "$H/corpora/$corpus" \
      --config $SK/configs/baseline-b.json --out "$H/cell-${corpus}b" \
      --corpus-tag "$corpus" --domain nl
  python3 $SK/scripts/check-retrieval.py --run "$H/cell-${corpus}b/run.jsonl" \
      --corpus "$H/corpora/$corpus" --qrels-mode sentinel --tsv-out "$H/metrics.tsv" \
      --round 1 --corpus-tag "$corpus" --rag-tag b --rag-config-id baseline-b --domain nl
done

python3 $SK/scripts/scoreboard.py --tsv "$H/metrics.tsv" --metric recall@20
```

The retrieval half is bit-reproducible (deterministic chunking, stable-hash
embedding, stable sort); only the `index_ms`/`retrieval_ms` columns vary.

---

## Limitations

- **`nl`-only, `baseline-b`-only.** The `rag` skill is not exercised; no SIMPLE
  (ripgrep/keyword) consumer is measured this round; the code content-type axis is
  not run.
- **Tiny, medium-heavy gold set.** `n = 6` (5 medium, 1 hard, 0 easy). The plan
  calls for 50–100+ queries via cross-link enumeration; no significance test is
  reported and small deltas (the `Db − Nb` ranking dip) should be read as
  directional only.
- **Placeholder embedder.** The Phase-0 dense vector is a deterministic
  hashed-lexical stand-in with no semantics, so paraphrase recall is **understated**
  (see `bench-conflict-time`). Absolute numbers are within-host, within-harness;
  they are not comparable across hosts or to a real embedder.
- **Snapshot, not generated.** `Db` is today's `docs/` verbatim, not the output of
  the docs-skill WRITE loop (which, with its `check-convention.sh` oracle, is not
  built yet). This measures the conventions, not the skill's authoring behavior.

## Next

- **Phase-1 embeddings (Ollama)** to lift the placeholder ceiling and re-measure
  `bench-conflict-time` and the `Db − Nb` ranking dip with semantics.
- **Grow `gold.FACTS`** (cross-link enumeration → 50–100+ queries) for the power
  the marginal/interaction CIs need.
- **Add the `rag-r` column** to run the full 2×2 and finally read the docs×rag
  **interaction** — the number that justifies one harness for two skills.
- **Wire the WRITE loop** (`check-convention.sh`) so the `docs` skill is scored on
  what it *authors*, not just on a snapshot of existing docs.
