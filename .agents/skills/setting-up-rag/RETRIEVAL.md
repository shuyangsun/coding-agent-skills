# RETRIEVAL — hybrid search, fusion, reranking, and the knobs that matter

The retrieve path is in [`scripts/query.py`](scripts/query.py); knobs are the
`hybrid` / `rerank` / `top_k` blocks of
[`scripts/rag-config.json`](scripts/rag-config.json). The pipeline:

```text
query ──embed──► dense prefetch (bge-small)   ─┐
        embed──► sparse prefetch (bm25)        ─┴─►  RRF fuse  ──►  rerank top-N  ──►  top-k
```

## 1. Hybrid: dense + sparse (the default, and why)

- **Dense** (`bge-small`, cosine) captures _meaning_: a paraphrased question
  matches a passage that shares no words with it.
- **Sparse** (`bm25`, lexical) captures _exact tokens_: identifiers, function and
  flag names, error codes, version strings — the things dense embedders blur and
  the things code/doc search hinges on. bm25 is applied with Qdrant's server-side
  **IDF modifier** (set on the collection), so rare terms count more.

Either alone leaves recall on the table; together they cover both failure modes.
Each arm fetches `hybrid.prefetch` (default 60) candidates.

## 2. Fusion: RRF (rank-based) by default

Reciprocal Rank Fusion combines the two ranked lists by rank position, not by raw
score — so it is immune to dense and sparse living on incompatible score scales
(the classic hybrid bug). It is Qdrant's `FusionQuery(fusion=Fusion.RRF)`.

- Switch to `"fusion": "dbsf"` (Distribution-Based Score Fusion) to weight by
  normalized scores when one arm is clearly stronger on your corpus.
- For per-arm weighting, Qdrant also offers weighted RRF (`RrfQuery(rrf=Rrf(k=…,
weights=[…]))`); add it only if a measured imbalance justifies the extra knob.

## 3. Reranking: a cross-encoder on the shortlist

RRF gives a good top-N; a **cross-encoder** (`Xenova/ms-marco-MiniLM-L-6-v2`, ONNX,
CPU) then reads each (query, chunk) pair _together_ and re-scores them, which
separates the truly relevant chunk from lexical near-misses far better than any
bi-encoder similarity. It re-scores the fused `rerank.top_n` (default 50) and the
`top_k` survive.

- **Worth it for search/answering**: in the smoke test it lifted the correct chunk
  to rank 1 with a wide score gap. Cost is ~0.3–0.6 s for ~50 candidates on CPU.
- **Drop it** (`--no-rerank` or `rerank.enabled=false`) when latency dominates or
  the corpus is tiny (then RRF order is already fine).

## 4. top-k and prefetch

- `top_k` (default 20) = how many chunks the consumer gets. Match it to the
  consumer's context budget: fewer for a small model, more for synthesis.
- `prefetch`/`rerank.top_n` set how wide the funnel is before fusion/rerank. Wider
  = higher recall, more rerank cost. 50–60 is a good balance for a mid-size corpus.

## 5. When to reach for more (add only if measured to help)

- **Contextual Retrieval** (Anthropic): prepend a one-line, LLM-generated summary
  of the chunk's place in its document _before embedding_. Reported to cut
  retrieval-failure rate substantially on prose; it costs one cheap LLM call per
  chunk at index time and is the optional "full" arm vs the "plain" no-context
  default. Enable via `contextual_retrieval` once you have an index-time LLM and a
  gold set to prove the lift. (Plain is the noise-free cross-run comparison.)
- **Query transforms** (HyDE, multi-query expansion): help when queries are terse
  or vocabulary-mismatched to the corpus; they add latency and can hurt precise
  lexical queries — gate on the gold set.
- **Late-interaction / ColBERT rerank**: a stronger (heavier) alternative to the
  cross-encoder for larger corpora.

Every item in §5 is opt-in and must **beat the baseline on the held-out gold set**
([TUNING.md](TUNING.md)) before it stays. More stages ≠ better retrieval.
