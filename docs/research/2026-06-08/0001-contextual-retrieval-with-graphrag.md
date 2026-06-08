# Research: Contextual Retrieval With GraphRAG

**Date:** 2026-06-08
**Status:** Research note; no skill changes made.
**Area:** GraphRAG, contextual retrieval, hybrid RAG, code/document retrieval
**Question:** Can Anthropic-style contextual retrieval and related advanced
retrieval techniques be implemented with Microsoft GraphRAG?

## Summary

Yes, contextual retrieval can be implemented with GraphRAG, but not as a simple
drop-in flag. In Microsoft GraphRAG it would be a preprocessing or custom-workflow
step: generate short chunk-specific context, attach or prepend it to each text
unit, and then embed/index those contextualized text units. The safer design is to
store both raw chunk text and contextualized retrieval text so citations and source
verification still point at the original files.

For this repo, GraphRAG is not a clear replacement for Qdrant/FastEmbed yet.
GraphRAG is promising for global/multi-hop questions across long histories and
cross-linked decisions. For day-to-day agent context retrieval over code and docs,
hybrid dense+sparse search plus reranking is still the stronger default until a
larger benchmark proves graph retrieval wins.

## What GraphRAG Gives

Microsoft GraphRAG's indexer is a configurable pipeline that extracts entities,
relationships, claims, communities, community reports, and embeddings from raw text.
Its query modes are not one thing:

- **Local Search** combines graph data with raw text chunks for entity-specific
  questions.
- **Global Search** searches AI-generated community reports in map-reduce style
  for broad corpus questions.
- **DRIFT Search** adds community information to local search and expands into
  follow-up questions.
- **Basic Search** is a rudimentary vector-RAG comparison mode.

The official docs make the key extension point clear: GraphRAG has text units,
entities, relationships, community reports, and configurable workflows. That means
contextual retrieval can be inserted before embedding, before graph extraction, or
as a parallel field used only for retrieval.

## How To Add Contextual Retrieval

Anthropic's contextual retrieval prepends a short chunk-specific explanation before
embedding and BM25 indexing. They report top-20 retrieval failure reductions of 35%
for contextual embeddings, 49% for contextual embeddings plus BM25, and 67% when
reranking is added.

With GraphRAG, implement it as one of these patterns:

| Pattern                    | How it works                                                                                                   | Tradeoff                                                                             |
| -------------------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Preprocess input files     | Materialize contextualized chunks before `graphrag index` sees them.                                           | Easiest to prototype; risks polluting citations unless raw source IDs are preserved. |
| Custom workflow step       | Insert `ChunkDocuments -> ContextualizeTextUnits -> EmbedChunks/ExtractGraph`.                                 | Best architecture; requires GraphRAG workflow customization and version maintenance. |
| Dual text fields           | Keep raw `text_units.text`, add contextualized retrieval text for embeddings/BM25.                             | Safest for source verification; needs custom query/index adapter work.               |
| Graph-aware context prompt | Include document path, parent module, known entities, and nearby graph neighbors in the contextualizer prompt. | Most powerful, but can create feedback loops and index-time token cost.              |

The implementation rule is: contextualize retrieval text, not source truth. Keep
the original chunk available for citations and for the consumer to verify.

## Where Contextual Retrieval Helps

It is most likely to help:

- long exported coding-session transcripts where a chunk says "the fix" or "this
  helper" without naming the project, skill, or source path;
- code design docs where the answer depends on parent module context;
- cross-cutting docs whose facts span several files;
- queries with paraphrased wording but stable entities, paths, commands, or IDs.

It is less likely to help, or may hurt, when:

- the corpus is mostly small source files with strong exact identifiers;
- repeated boilerplate context floods BM25 and graph extraction;
- generated context mentions too many related files and causes false graph edges;
- the index-time LLM is too small to produce valid structured entities/relationships.

## More Recent Techniques

Late chunking embeds the full document first and pools token embeddings into chunks
afterward, preserving long-document context without a per-chunk LLM call. It is a
good fit when a long-context embedding model is available, but less useful with
short-context local embedders.

RAPTOR and related tree-retrieval systems recursively summarize clustered chunks.
They target holistic questions that need information from multiple parts of a
document. That overlaps with GraphRAG Global Search and community reports.

LightRAG and newer graph-RAG variants combine graph structures with vector
retrieval to improve contextual awareness and efficiency. Deep GraphRAG, published
in 2026, pushes hierarchical graph retrieval further with global-to-local filtering
and dynamic reranking. These support the same conclusion: graph retrieval is useful
for structured, multi-hop, broad-context questions, not necessarily as the default
for every local code lookup.

Recent 2026 retrieval studies still support the boring-but-strong baseline: hybrid
retrieval plus reranking remains competitive, and no single retrieval strategy wins
across all query types. For this repo, that argues for adaptive routing: Qdrant
hybrid RAG by default, GraphRAG for explicitly graph-shaped questions, and manual
source verification always.

## Feasibility With Microsoft GraphRAG

Implementation is feasible:

- GraphRAG already has `text_units`, `entities`, `relationships`, and
  `community_reports` tables.
- Its config can embed `text_unit_text`, `entity_description`, and
  `community_full_content`.
- Its architecture supports custom providers, custom vector stores, and custom
  workflow steps.
- Its local/global/DRIFT query modes provide natural places to test contextualized
  text units versus plain text units.

But it is not free:

- Full Standard GraphRAG relies on LLM extraction and summarization; indexing cost
  and structured-output reliability become the main risks.
- FastGraphRAG lowers cost with NLP/entity co-occurrence, but the graph is noisier.
- Code retrieval needs code-aware entity extraction; generic noun phrases are weak
  for APIs, paths, symbols, and generated files.
- Contextualized chunks can improve embeddings while damaging graph quality if the
  prepended context creates artificial co-occurrences.

## Recommendation

Do not replace local Qdrant RAG with GraphRAG yet. Add a future experimental arm:

1. Grow the gold set to at least 30-50 queries with separate code, history, and
   multi-hop/global slices.
2. Keep the current Qdrant/FastEmbed hybrid+rerank baseline.
3. Add Microsoft GraphRAG Standard or FastGraphRAG with a real local LLM/API key.
4. Add a contextualized-GraphRAG variant that stores raw text and contextualized
   retrieval text separately.
5. Gate on recall@20, nDCG@10, MRR, p50/p95 latency, index tokens/cost, context
   tokens-to-answer, and source-verification failures.

Only move `setting-up-rag` toward GraphRAG if the GraphRAG arm wins on held-out
multi-hop/history queries without regressing code lookup or making index cost
unacceptable.

## Sources

- [Anthropic: Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)
- [Microsoft GraphRAG repository](https://github.com/microsoft/graphrag)
- [GraphRAG indexing overview](https://microsoft.github.io/graphrag/index/overview/)
- [GraphRAG query overview](https://microsoft.github.io/graphrag/query/overview/)
- [GraphRAG output schema](https://microsoft.github.io/graphrag/index/outputs/)
- [GraphRAG indexing methods](https://microsoft.github.io/graphrag/index/methods/)
- [Late Chunking](https://arxiv.org/abs/2409.04701)
- [RAPTOR](https://arxiv.org/abs/2401.18059)
- [LightRAG](https://arxiv.org/abs/2410.05779)
- [Deep GraphRAG](https://arxiv.org/abs/2601.11144)
- [GraphRAG on Consumer Hardware](https://arxiv.org/abs/2605.20815)
- [Hybrid Retrieval and Reranking Framework](https://arxiv.org/abs/2605.01664)
- [Biomedical RAG retrieval strategy benchmark](https://arxiv.org/abs/2605.02520)
