# METRICS — what is measured and how it is read

Five outcome metrics, every one sliced by model tier and query difficulty, and
every one **attributed to `docs` vs `rag` vs their interaction** via the factorial
(plan §9). Hygiene signals are reported **separately** from retrieval quality.

## The five metrics

| Metric          | Definition                                                       | Driven by          | Made objective by                                                                                            |
| --------------- | ---------------------------------------------------------------- | ------------------ | ------------------------------------------------------------------------------------------------------------ |
| **Precision**   | of retrieved, how many relevant (graded `qrels`)                 | docs + rag         | `check-retrieval.py`                                                                                         |
| **Recall**      | of relevant, how many retrieved; **recall@20 headline**          | docs + rag         | `check-retrieval.py`                                                                                         |
| **Speed**       | `index_ms` (one-time) + `retrieval_ms` p50/p95                   | **rag**            | `docs-eval.py` timers, same-host trend                                                                       |
| **Factuality**  | answer stays grounded (contains a sentinel from a relevant doc)  | docs + rag         | sentinel containment + closed-book control + advisory judge. Phase-0 proxy = `retrieval_hit@20` (judge-free) |
| **Token usage** | `ctx_tokens` (RAG) / `read_tokens` (SIMPLE) at equal correctness | **rag** / **docs** | transcripts via `_score.py`, never self-reported                                                             |

`nDCG@10` is the multi-relevance summary (graded). `retrieval_hit@20` (a grade-2
doc in top-20) is the **primary** Phase-0 answerability signal; `answer_ok` /
`factuality_grounded` are secondary and need the Phase-1 generation path.

## TSV schema (`metrics.tsv`)

One row per `query × cell(corpus,rag) × domain × mode × round`. The floor is logged
as `corpus=Z, rag=0` (all metric columns 0); code rows are `corpus=code, domain=code`.
Phase-0 fills what it can measure; the rest are `NA` until Phase 1. Columns emitted
today:

```
round  corpus(Z|N|D|code|GOLD)  domain(nl|code)  rag(0|b|r)  rag_config_id
mode(simple|rag)  retrieval(plain|full)  seed  query_id  qtype  difficulty
recall@5  recall@10  recall@20  precision@5  precision@10  ndcg@10  mrr  retrieval_hit@20
```

Phase-1 adds: `embed_tier gen_tier chunker embed_ver gen_ver factuality_grounded
closed_book_leak gen_ms_p50/p95 total_ms ctx_tokens read_tokens conv_ok
write_findable rag_config_ok total_chunks mean_chunk_len index_ms index_llm_cost
host_fingerprint notes`.

## Scoreboard views (`scoreboard.py`)

0. **Baseline-first view (floor)** — the absolute "no doc, no RAG" floor (`Z`,
   `--no-retrieval`; all metrics 0) printed first, then each named condition as a
   **lift above the floor**, in order: floor → docs-only (`Db`) → RAG-only (`Nr`) →
   docs+RAG (`Dr`), with `Nb` as the naive reference. Establishes that every
   reported gain is measured against nothing.
0b. **Content-type comparison (code vs natural language)** — when code rows are
   present, code (`inception/`) vs natural language (structured `D` docs incl.
   transcripts) on each domain's own corpus, per rag config. Separate metrics so
   the code/NL retrieval gap is directly visible. The factorial below stays `nl`.
1. **Cell means** — recall@20, nDCG@10, retrieval_hit@20, MRR for the floor `Z`
   plus each of Nb/Nr/Db/Dr.
2. **The 2×2 factorial (headline)** — the two marginal effects (`docs` = Db−Nb &
   Dr−Nr; `rag` = Nr−Nb & Dr−Db) and the **interaction** `(Dr−Db)−(Nr−Nb)`, each
   paired per query with a seeded-bootstrap 90% CI. `*` flags a CI excluding zero.
   The floor is the reference, **not** part of the interaction math.
 3. *(Phase 1)* by tier×mode ("no tier/mode left behind") and difficulty×tier.
3. _(Phase 1)_ by tier×mode ("no tier/mode left behind") and difficulty×tier.

Cross-host comparison is refused: absolute recall/latency are host-relative; only
the frozen-gate numbers and the **within-host factorial deltas** travel.

## Reading the numbers

- **rag marginal > 0** ⇒ the `rag` config beats baseline on that corpus.
- **docs marginal > 0** ⇒ structure helps retrieval at fixed rag.
- **interaction > 0** ⇒ co-design beats additive (the coupling dividend); `< 0`
  and stable ⇒ the change is anti-synergistic — revert.
- Diagnostic split (reported, never a gate): on an answer miss, `retrieval_hit`
  attributes it to a **retrieval miss** (revise docs and/or rag) vs a
  **generation miss** (model-bound noise, ignore).

The exit bar (the conditions that end the loop) is in [SKILL.md](SKILL.md#exit-condition-the-bar).
