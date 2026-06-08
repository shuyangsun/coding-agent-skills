# Research: Contextual Retrieval and Graphify

**Date:** 2026-06-08
**Status:** Research complete; awaiting implementation decision
**Area:** contextual retrieval, GraphRAG, graphify, hybrid RAG
**Sources:** [Anthropic Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval), [graphify v8 how-it-works](https://github.com/safishamsi/graphify/blob/v8/docs/how-it-works.md), [graphify README](https://github.com/safishamsi/graphify/blob/v8/README.md), [GraphRAG paper](https://arxiv.org/abs/2404.16130), [Microsoft GraphRAG project](https://www.microsoft.com/en-us/research/project/graphrag/), [LightRAG](https://arxiv.org/abs/2410.05779), [Late Chunking](https://arxiv.org/abs/2409.04701)

## Summary

Contextual retrieval can be integrated with graphify, but it does not fit graphify as a direct drop-in feature in the same way it fits a vector/BM25 RAG system.

Anthropic's contextual retrieval is a chunk-indexing technique: generate a short chunk-specific context from the parent document, prepend it to the chunk, then index that contextualized text with embeddings and BM25. Graphify is different. Its current v8 design extracts code structure locally, extracts semantic graph nodes/edges for docs with an LLM, and treats graph structure as the similarity signal rather than using a separate embedding or vector database.

The most practical integration is therefore hybrid: keep Qdrant as the scored retrieval layer, use graphify or a graph extractor to produce context capsules, relationship edges, and source maps, then embed/index those enriched chunks. Graphify can help create context, but graphify alone should not be treated as contextual retrieval.

## Fit And Mismatch

Contextual retrieval improves first-stage retrieval by making otherwise ambiguous chunks self-describing before embedding and sparse indexing. It directly targets the failure mode where a chunk says "this option" or "the company" without enough parent context for retrieval.

Graphify targets a different representation. Its docs describe three passes: local tree-sitter extraction for code, optional media transcription, and LLM extraction for docs/papers/images/transcripts. It then uses graph edges and community structure; graphify explicitly says there is no separate embedding step or vector database in that path.

That mismatch matters. If graphify does not embed chunks or build BM25 over chunks, then prepending contextual text to chunks will not automatically improve graphify query behavior. It can improve graphify only if one of these is also true:

- graphify's LLM extraction prompt consumes the contextualized text and emits better nodes, edges, and provenance;
- graphify exports graph-derived context to a separate vector/BM25 index;
- graphify itself gains a vector/BM25 sidecar and uses graph nodes only for routing or expansion.

The benchmark in [0009](../../benchmarks/2026-06-08/0009-graphify-graphrag-rag.md) also found a concrete graphify blocker for coding-session retrieval: transcript graphs can assign `source_file` to files mentioned inside the transcript rather than the transcript file containing the evidence. Contextual retrieval does not fix that automatically; graphify needs explicit provenance fields or extraction instructions for "evidence file" versus "mentioned file".

## Integration Patterns

### Qdrant-Primary Graph Context

This is the lowest-risk path.

For each chunk, generate a compact context capsule before indexing:

- source file, section, project, language, and date/status when available;
- graphify node labels associated with the file or chunk;
- neighboring files/entities from graph edges;
- relationship facts such as imports, implements, tests, supersedes, validates, or mentions;
- coding-session provenance such as "this evidence is in session file X and mentions code file Y".

Index the contextualized chunk in Qdrant with dense embeddings and BM25, but preserve the raw chunk separately for final answer context. This matches Anthropic's contextual retrieval shape and lets graphify contribute graph-derived context without becoming the retrieval backend.

### Graphify-Primary With Vector Sidecar

Graphify could keep `graph.json` as the structural index but add a sidecar vector/BM25 index over:

- node labels and descriptions;
- edge triples;
- community summaries;
- source-file snippets;
- graph-derived source maps.

The vector sidecar would seed graph traversal, then graph edges would expand candidates. This resembles the hybrid direction in LightRAG, which combines graph structures with vector representations and supports low-level and high-level retrieval.

This path is more invasive than Qdrant-primary enrichment because graphify's current query model would need ranking and provenance changes.

### Prompt-Level Provenance Fix

For docs and transcripts, graphify's semantic extraction prompt can be made provenance-aware:

- `evidence_source_file`: the file being extracted;
- `mentioned_source_file`: any file or path discussed inside that evidence;
- `evidence_quote` or short evidence anchor;
- `relationship`: the reason the evidence file connects to the mentioned file.

This is not contextual retrieval by itself, but it addresses the benchmark's transcript failure and makes graphify output more useful as context for a RAG index.

### Community Summaries As Parent Context

GraphRAG builds an entity graph and pregenerates community summaries for query-focused summarization over large corpora. Microsoft has continued this line with variants such as dynamic community selection, LazyGraphRAG, and benchmarking tools.

For this repo, community summaries would be useful as parent context for broad questions like "what changed across the context-retrieval skills?" They are less obviously useful for pinpoint coding questions like "which file defines this action encoding?" unless paired with file-level provenance and reranking.

## More Recent Techniques

Late chunking is relevant for long coding-session transcripts. It embeds the long document first and pools token embeddings into chunks afterward, preserving surrounding context without an LLM-generated context string. It could reduce indexing-token cost compared with Anthropic-style contextualization, but it still needs a long-context embedding model and clean parent documents.

LightRAG is directionally closer to the hybrid system that would make graphify useful for retrieval. It combines graph structures with vector representations and incremental updates, which maps well to "graph for relationships, vector/BM25 for recall."

Classic GraphRAG is strongest for global sensemaking questions over large corpora. It is not automatically better for exact code-context retrieval, where source paths, symbols, and tests often matter more than entity-community summaries.

Reranking remains important in all of these designs. A graph can expand candidate sets, and contextualized chunks can improve recall, but a reranker is still the cleanest way to choose final evidence for the agent context window.

## Recommendation

Yes, contextual retrieval makes sense with graphify, but only as a hybrid:

- Use graphify or a smaller local graph extractor to produce relationship context and source maps.
- Put that graph-derived context into Qdrant-indexed chunks.
- Keep Qdrant's dense+sparse retrieval and reranking as the main scored retrieval path.
- Fix transcript provenance before using graphify output for coding-session history.
- Avoid making graphify the only retrieval backend until it beats Qdrant/local GraphRAG on primary-file recall and answer-sentinel metrics.

The next implementation decision should be whether to prototype Qdrant-primary contextualized chunks using a local graph/source-map context capsule. That is more aligned with Anthropic contextual retrieval than replacing Qdrant with graphify.
