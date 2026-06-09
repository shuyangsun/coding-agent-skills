# Phase 2: Optimizing RAG Setup Plan

This plan details the steps to optimize context retrieval and answer generation metrics over the benchmark repositories, following the research findings documented in `@docs/research/2026-06-08-sota-rag-techniques.md`.

## 1. Optimization Strategy

We will iteratively implement and measure the impact of the following SOTA techniques on the Phase 1 evaluation set. We will establish a baseline first and then introduce one variable at a time, keeping changes only if they improve metrics. Codebase questions will be split from session transcript questions to tune each cohort independently.

1. **Baseline Construction:** Implement basic dense vector retrieval.
2. **Hybrid Search Pipeline:** Add BM25 sparse search and merge results using Reciprocal Rank Fusion (RRF).
3. **Reranking Layer:** Introduce a cross-encoder (e.g., BGE-Reranker) to rescore top-K candidates.
4. **Semantic Chunking:** Replace fixed-size chunking with AST-aware splitting (Tree-sitter) for code, and header-aware chunking for docs. Prepend context summaries to chunks.
5. **Query Expansion & Transformation:** Implement HyDE, Step-back Prompting, and multi-query rewriting.
6. **Graph-Based RAG:** Integrate AST-driven dependency graphs (via Tree-sitter) into a graph database to enable Hybrid Traversal Retrieval from semantic anchor points. Explore tools like CodeGraph or LightRAG.
7. **Agentic Orchestration:** Wrap the pipeline in LangGraph to enable cyclic multi-hop reasoning. Implement Corrective RAG (CRAG) to grade retrieved chunks (Relevant/Irrelevant/Ambiguous) and autonomously route queries to either vector search or graph traversal.

## 2. Required Local Dependencies

Before starting the optimization loop, the following local dependencies need to be installed on the workstation:
- **Qdrant:** As the vector database for hybrid search (supports both dense and sparse vectors).
- **FastEmbed:** For local embedding generation.
- **Tree-sitter:** Along with relevant language parsers (Python, TypeScript, Go, etc.) for AST-aware chunking and graph building.
- **Graph Database:** e.g., Neo4j, FalkorDB, or Memgraph to store AST-derived dependency relationships.
- **Agentic Frameworks:** `LangGraph` and related dependencies.
- **BM25 Libraries:** e.g., `rank_bm25` (if not natively using Qdrant's sparse features).
- **Cross-Encoder Model:** Local reranking model (e.g., `BAAI/bge-reranker-v2-m3`).
- **Evaluation Framework:** `ragas` or a custom suite for measuring context recall, precision, and faithfulness.

## 3. Local LLM Requirements

**Yes, a local LLM is highly recommended.**
Given the two NVIDIA RTX Pro 6000 Blackwell GPUs, hosting a local LLM will significantly cut down on API costs and reduce latency during the measurement-driven loop. We will need the local LLM for two primary functions:
1. **Cheap Context Generation & Query Rewriting:** For techniques like HyDE and multi-query expansion. A model like **Llama 3 (70B)** or **Gemma 2 (27B)** running on vLLM or Ollama will be perfect for this.
2. **Evaluation (LLM-as-a-Judge):** To evaluate answer generation quality (faithfulness, relevance) against the eval set.

Please set up **vLLM** or **Ollama** on your workstation and ensure we have an API endpoint compatible with our scripts to call the local model.
