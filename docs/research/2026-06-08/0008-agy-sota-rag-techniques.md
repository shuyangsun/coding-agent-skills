# State of the Art RAG Techniques (2026)

Based on recent research and industry standards in mid-2026, the state-of-the-art for context retrieval and answer generation, especially for codebases and mixed documentation, centers around moving from "naive RAG" to agentic and graph-aware architectures.

## 1. Hybrid Search + Neural Reranking
The foundation of modern retrieval is hybrid search. It combines:
- **Dense Vector Search:** For semantic intent and concepts.
- **Sparse Search (BM25):** For exact matches on identifiers, variable names, and error codes.
- **Reciprocal Rank Fusion (RRF):** To combine the scores.
- **Cross-Encoder Reranking:** (e.g., BGE-Reranker) The critical step that re-scores the top candidates to ensure high precision before passing context to the LLM.

## 2. Advanced and Semantic Chunking
Fixed-size chunks are largely considered obsolete. Current techniques use semantic splitters that respect context boundaries:
- **Code:** AST-aware splitting using tools like Tree-sitter, keeping functions or classes intact rather than cutting them mid-logic.
- **Contextual Chunking:** Prepending chunks with contextual summaries (e.g., MiA-RAG) or file metadata so the LLM understands the global scope.

## 3. Agentic RAG and Query Transformation
RAG is treated as an iterative agentic loop rather than a single pass pipeline. **LangGraph** has emerged as the dominant framework here due to its support for cyclic control, state management, and built-in checkpointing for multi-hop investigations.
- **Corrective RAG (CRAG):** An LLM evaluator grades retrieved chunks as `relevant`, `irrelevant`, or `ambiguous`. `Relevant` chunks proceed to generation, `irrelevant` chunks trigger query rewriting or fallback tools, and `ambiguous` chunks combine strategies.
- **Step-back Prompting:** The agent abstracts a specific query into a conceptual one (e.g., "Why does processOrder fail?" -> "How does OrderManager handle validation?"), retrieving for both to ground answers in macro and micro details.
- **Query Rewriting & Transformation:** Agents dynamically decompose complex queries, heavily utilizing HyDE and multi-query expansion based on the first pass of retrieval.
- **Tool Routing:** Agents autonomously route sub-queries to the most appropriate tools (vector search, AST search, git blame).

## 4. Graph-Based RAG (Architectural Reasoning)
For resolving multi-hop reasoning over code architecture, Knowledge Graphs are essential to prevent the "retrieval plateau" seen in pure vector RAG. 
- **AST-Driven Semantic Chunking & Dependency Graphs:** Tree-sitter parses code into Abstract Syntax Trees (ASTs) to chunk by logical entity (classes/functions) and extract deterministic edges (`CALLS`, `INHERITS`, `IMPORTS`).
- **Hybrid Traversal Retrieval:** Vector search finds semantic "anchor points", and the system expands from these anchors via graph traversal to retrieve structurally related nodes, giving the LLM perfectly grounded context.
- **Advanced Features:** SOTA systems use **Incremental Indexing** (updating only changed code) and **Agentic Routing** (switching between cheap vector and expensive graph searches dynamically).
- **Tools & Frameworks:** Open-source projects like **CodeGraph**, **Code-Graph-RAG**, **Codebase-Memory** (using MCP), **CocoIndex**, **LightRAG**, and **Graphiti** are leading the way in hybrid semantic/graph codebase search.

## 5. Evaluation-Driven Optimization
The standard is to optimize through continuous traces using frameworks like RAGAS or custom suites. The evaluation focuses on splitting failures into retrieval (recall/precision) versus generation (faithfulness/hallucination) so that tuning is applied to the correct layer.
