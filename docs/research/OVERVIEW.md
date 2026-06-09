# research/

Research notes that explain external techniques behind this repo's skill
designs. Use these for educational background and for decisions that would bloat a
skill if included inline.

Naming: `YYYY-MM-DD/NNNN-slug.md`, with `NNNN` unique across the whole
`research/` tree.

## Notes

### 2026-06-08

- [`0000` — contextual retrieval techniques for doc authors](2026-06-08/0000-contextual-retrieval-for-doc-authors.md)
- [`0001` — contextual retrieval with GraphRAG](2026-06-08/0001-contextual-retrieval-with-graphrag.md)
- [`0002` — contextual retrieval integration with graphify](2026-06-08/0002-contextual-retrieval-and-graphify.md)
- [`0003` — RAG optimization Phase 2 SOTA techniques (cursor, beyond GraphRAG)](2026-06-08/0003-cursor-rag-optimization-phase-2-sota-techniques.md)
- [`0003` — Codex Phase 2 RAG optimization techniques](2026-06-08/0007-codex-rag-optimization-techniques-phase-2.md)
- [`0004` — SOTA local retrieval substrate — claude (embeddings, code chunking, sparse, fusion, reranking, Qdrant knobs)](2026-06-08/0004-claude-rag-retrieval-substrate.md)
- [`0005` — contextual indexing, query routing, and answer-generation faithfulness — claude](2026-06-08/0005-claude-rag-contextual-routing-faithfulness.md)
- [`0006` — local-LLM + GPU serving plan for the 2× RTX PRO 6000 Blackwell workstation — claude](2026-06-08/0006-claude-rag-local-llm-gpu-serving.md)

> RAG-optimization campaign ("Optimizing RAG Setup"), Phase 2. Three parallel passes were run:
> the **claude** pass is research `0004`–`0006`, feeding the plan
> [`docs/plans/2026-06-08/0005-claude-rag-optimization-phase-2.md`](../plans/2026-06-08/0005-claude-rag-optimization-phase-2.md);
> the **cursor** and **codex** passes are research `0003` (two notes) with their own plans
> (`plans/0004-cursor-rag-optimization-phase-2.md`, `plans/0006-codex-rag-optimization-phase-2.md`). `0000`–`0002` are
> the earlier contextual-retrieval/GraphRAG notes.
