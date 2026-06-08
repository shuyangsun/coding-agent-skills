---
name: rag
description: Load when setting up or improving RETRIEVAL (RAG) over a document or
  code set — chunking, embeddings, hybrid (dense+sparse) search, reranking, and
  vector-DB config. Local-first (Qdrant + FastEmbed, CPU, no cloud). The main flow
  ASSUMES local RAG is already running; it bootstraps it only if not.
---

# RAG — local-first retrieval over a doc set

Set up effective retrieval over a given corpus (markdown docs, transcripts, or
source code) so a downstream agent can answer from it. The pipeline is
**Qdrant + FastEmbed**, CPU-only, no cloud key: chunk → embed (dense + sparse) →
index → hybrid retrieve (RRF) → rerank → top-k. Defaults live in
[`scripts/rag-config.json`](scripts/rag-config.json); the helpers do the
mechanics, so spend tokens on the corpus-specific choices, not the boilerplate.

This file assumes local RAG is **already running**. The first two lines below
handle the one case where it isn't — do not read the setup docs otherwise.

## 0. Make sure local RAG is up (one-time per host)

```sh
bash <skill-dir>/scripts/check-local-rag.sh   # prints READY or NOT_READY
```

If it prints **`NOT_READY`**, provision once with
`bash <skill-dir>/scripts/setup-local-rag.sh` (add `--warm` to pre-download
models). Only then open [SETUP.md](SETUP.md) — for Docker/Ollama/offline
specifics or troubleshooting. If it prints **`READY`**, skip all of that and go
to §1. (Qdrant runs as a server when one is up, else embedded on-disk with no
daemon; both use the same code path.)

## 1. Index the corpus

```sh
python3 <skill-dir>/scripts/index.py --corpus <dir> --kind md   # prose/markdown
python3 <skill-dir>/scripts/index.py --corpus <dir> --kind code # source code
```

Indexes into a hybrid collection (named `dense` + `sparse` vectors); point IDs are
time-ordered Snowflakes (`snowflake.py`). **Re-running replaces the prior chunks of
changed and added docs** — each doc's old points are dropped before re-insert, so
no duplicates or orphans accumulate. Pass `--recreate` after a chunking/embedding
change or when docs were **removed**; `--local` forces embedded mode. Use a
distinct `--collection` per corpus or content type. Chunking adapts to `--kind`
(heading-aware for prose, block-packed for code) — see [CHUNKING.md](CHUNKING.md).

## 2. Query

```sh
python3 <skill-dir>/scripts/query.py "a natural-language question" --top-k 20
python3 <skill-dir>/scripts/query.py "…" --json        # JSONL for a consumer/eval
python3 <skill-dir>/scripts/query.py "…" --no-rerank   # skip the rerank stage
```

Each query runs a dense and a sparse retrieval, fuses them with RRF, then a local
cross-encoder reranks the top candidates. The how-and-why is in
[RETRIEVAL.md](RETRIEVAL.md).

## 3. The method (what makes retrieval good, in priority order)

1. **Hybrid beats either arm alone.** Dense (semantic, `bge-small`) catches
   paraphrase; sparse (lexical, `bm25`) catches exact identifiers, error codes,
   API names. Fuse rank lists with **RRF** (robust to incompatible score scales).
2. **Chunk on structure, with a size floor.** Split markdown on headings, but
   **merge tiny sections** up to `min_words` so a heading-dense doc doesn't
   explode into hundreds of one-line chunks (a real cost: ~2.5× fewer chunks at
   equal recall on this repo). Code chunks pack whole blocks. → [CHUNKING.md](CHUNKING.md)
3. **Rerank the shortlist.** A cross-encoder re-scores the fused top-N; it sharply
   separates the right chunk from near-misses, at a small CPU cost. Worth it for
   search; drop it when latency is critical. → [RETRIEVAL.md](RETRIEVAL.md)
4. **Right-size top-k and prefetch** to the consumer's context budget.

## 4. Tune and validate against YOUR corpus — don't trust defaults blindly

The defaults are a strong start, **not** a guarantee. A knob that helps one corpus
can hurt another. Before keeping any change: build a small held-out gold query set
and confirm the change **beats the baseline** on recall@k / nDCG / MRR. Method,
gold-set construction, and the keep/revert rule are in [TUNING.md](TUNING.md).

## 5. Config

All knobs are in [`scripts/rag-config.json`](scripts/rag-config.json) (models,
chunk sizes, fusion, prefetch, rerank, top-k) and documented inline. Pass an
edited copy with `--config`. Provider/model alternatives (bigger dense model,
SPLADE sparse, Ollama embeddings) are noted there and in SETUP.md.
