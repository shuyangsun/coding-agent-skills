# RETRIEVAL — contextual indexing, hybrid search, Qwen reranking, and packing

The retrieve path is in [`scripts/query.py`](scripts/query.py); knobs are the
`contextual_llm` / `hybrid` / `rerank` / `top_k` blocks of
[`scripts/rag-config.json`](scripts/rag-config.json). The pipeline:

```text
index: raw chunk ──Nemotron context + header──► dense+sparse vectors in Qdrant

query ──embed──► dense prefetch (bge-small)   ─┐
        embed──► sparse prefetch (bm25)        ─┴─►  RRF fuse  ──►  Qwen3 rerank top-N  ──►  top-k
```

The generated context is retrieval-only. Payloads keep `raw_text`, and
`answer.py` packs raw chunks with citations.

## 0. Contextual indexing: Nemotron situates chunks

With the shipped config, `index.py` calls the local OpenAI-compatible Nemotron
endpoint (`http://127.0.0.1:8085/v1`, served model `model`) once per chunk and
caches the result under `$RAG_HOME/context/nemotron-w12k/`. It embeds:

```text
[project] path (kind)
<1-2 sentence Nemotron situating context>

<verbatim raw chunk>
```

Measured result: Nemotron-generated contexts were the quality ceiling for the
index-time generator comparison (held-out nDCG +0.059 overall, code nDCG +0.089,
code sentinel +0.158). Contextualize **all chunks**, including code.

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

## 3. Reranking: Qwen3 on the shortlist

RRF gives a good top-N; **Qwen3-Reranker-4B** then reads each (query, chunk) pair
together and re-scores them. The shipped config expects a Jina-compatible
`/rerank` endpoint at `http://127.0.0.1:8086` and wraps the query/documents in the
official Qwen3 reranker instruction template. That template is load-bearing: the
benchmark found the model anti-ranked without it.

- **Default when the service is running:** always-on Qwen3 reranking was the largest
  measured retrieval win: held-out nDCG 0.848, pMRR 0.800, sentinel 0.955, hit@5
  0.991 on the campaign slice.
- **Drop it** (`--no-rerank` or `rerank.enabled=false`) when the service is down,
  latency dominates, or the corpus is tiny.

## 4. top-k and prefetch

- `top_k` (default 20) = how many chunks the consumer gets. Match it to the
  consumer's context budget: fewer for a small model, more for synthesis.
- `prefetch`/`rerank.top_n` set how wide the funnel is before fusion/rerank. Wider
  = higher recall, more rerank cost. 50–60 is a good balance for a mid-size corpus.

## 5. Test-only answer generation and packing

The retrieval engine does not require an LLM to answer questions. For testing and
future GUI/backend experiments, [`scripts/answer.py`](scripts/answer.py) reuses
the same retrieval path, packs retrieved chunks with bracketed source ids, and
calls an OpenAI-compatible `/v1/chat/completions` endpoint. Use it to test local
servers such as vLLM or TensorRT-LLM, or a cloud provider with an OpenAI-compatible
API:

```sh
RAG_LLM_BASE_URL=http://127.0.0.1:8085/v1 \
RAG_LLM_MODEL=model \
python3 scripts/answer.py "your question" --project <name-or-path> --kind all
```

By default, `answer.py` uses the measured **parent-4k + extractive** setup:
retrieved chunks are grouped by parent/source before truncation to about 4k tokens,
and the prompt asks the model to preserve exact identifiers, constants, commands,
file names, and quoted strings. `answer.py --dry-run --show-context` verifies
retrieval and prompt packing without calling the provider. Keep answer quality
separate from retrieval quality: tune chunking, hybrid retrieval, and reranking with
IR metrics first, then use answer generation only as an end-to-end smoke test.

## 6. When to reach for more (add only if measured to help)

- **Contextual Retrieval** (Anthropic): now the shipped strong profile when Nemotron
  is available. Keep the deterministic header and apply to **all** chunks.
- **Portable fallback**: use a config with `contextual_llm.enabled=false` and
  `rerank.enabled=false` if no local LLM/reranker service is available. It is faster
  and weaker.
- **Doc2Query / document expansion** (LLM): append a few predicted queries each chunk
  answers to a **separate BM25 field**. Measured: a code win (+0.030 nDCG, +0.082 sentinel),
  ≈ contextual-retrieval quality but it costs some prose slices — prefer contextual retrieval;
  use Doc2Query when code recall is the priority. All-chunks, never prose-only.
- **Late chunking** (long-context embed + per-chunk pooling): **tested and rejected** on this
  corpus — whole-document pooling _blurs_ within-document discrimination and regressed every
  slice. Document context helps only when it _sharpens_ a chunk's identity (contextual
  retrieval, Doc2Query), not when it averages chunks toward a shared vector.
- **Query transforms** (HyDE, multi-query expansion): tested and rejected in Wave 6;
  they did not replicate held-out and sometimes diluted exact identifiers.
- **Graph/source-map overlay**: tested and rejected in Wave 5; it redistributed rank
  mass and caused repeated slice regressions.

Every item in §5 is opt-in and must **beat the baseline on the held-out gold set**
([TUNING.md](TUNING.md)) before it stays. More stages ≠ better retrieval.
