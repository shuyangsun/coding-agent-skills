# benchmarks/

Measurement reports that put the repo's skills under test. For `vcs`:
conflict-resolution speed/quality, branch hygiene, token cost, and Jujutsu
workspaces vs Git worktrees across vendors. For `docs`: retrieval findability of
the repo's documentation (floor-vs-doc, structure, and — later — the docs×rag
interaction). For `rag`: retrieval quality over a doc set (no-RAG floor vs RAG,
code vs natural language). Each report records its **Date** and links the SKILL
under test; raw metrics live in a co-located `.tsv` sharing the report's `NNNN`
and date folder.

Naming: `YYYY-MM-DD/NNNN-slug.md`, `NNNN` unique across the whole `benchmarks/`
tree (does not restart per day).

## Reports

### 2026-06-06

- [`0000` — multi-agent conflict resolution](2026-06-06/0000-vcs-skill-conflict-resolution.md)
- [`0001` — branch/bookmark hygiene + token efficiency](2026-06-06/0001-vcs-skill-branch-hygiene-and-tokens.md)

### 2026-06-07

- [`0002` — jj workspaces vs Git worktrees (Cursor Composer 2.5)](2026-06-07/0002-vcs-skill-composer-2.5-jj-vs-git.md) · [data](2026-06-07/0002-composer-2.5-metrics.tsv)
- [`0003` — Git worktree helper automation](2026-06-07/0003-vcs-skill-git-worktree-helper-automation.md) · [data](2026-06-07/0003-git-worktree-helper-metrics.tsv)
- [`0004` — jj vs Git token & speed, by model tier (GPT/Codex + Claude)](2026-06-07/0004-vcs-jj-vs-git-token-speed.md) · [data](2026-06-07/0004-vcs-jj-vs-git-metrics.tsv)

### 2026-06-08

- [`0005` — `docs` skill: floor (no doc) vs with-doc findability (Phase 0)](2026-06-08/0005-docs-skill-floor-vs-doc.md) · [data](2026-06-08/0005-docs-skill-floor-vs-doc-metrics.tsv)
- [`0006` — `rag` skill: no-RAG baseline vs RAG, code vs natural language](2026-06-08/0006-rag-skill-baseline-vs-rag.md) · [data](2026-06-08/0006-rag-vs-baseline-metrics.tsv)
- [`0007` — `updating-docs` skill: contextual retrieval source maps on inception and alpha-zero](2026-06-08/0007-updating-docs-contextual-retrieval.md) · [data](2026-06-08/0007-updating-docs-contextual-retrieval-metrics.tsv)
- [`0008` — Qdrant/FastEmbed RAG vs local GraphRAG on inception and alpha-zero](2026-06-08/0008-qdrant-vs-local-graphrag.md) · [data](2026-06-08/0008-qdrant-vs-local-graphrag-metrics.tsv)
- [`0009` — graphify vs Qdrant RAG vs local GraphRAG on inception and alpha-zero](2026-06-08/0009-graphify-graphrag-rag.md) · [data](2026-06-08/0009-graphify-graphrag-rag-metrics.tsv) · [script](2026-06-08/0009-graphify-graphrag-rag-benchmark.py)

### 2026-06-09

- [`0010` — Wave 0: RAG baseline + controls, 207-query 6-repo gold set](2026-06-09/0010-wave0-baseline-rag.md) · [data](2026-06-09/0010-wave0-baseline-metrics.tsv) · [summary](2026-06-09/0010-wave0-baseline-summary.json)
- [`0011` — Wave 1: re-index-free retrieval knobs](2026-06-09/0011-wave1-reindex-free-rag.md)
- [`0012` — Wave 2: deterministic contextual headers](2026-06-09/0012-wave2-contextual-headers-rag.md) · [data](2026-06-09/0012-wave2-ctx-header-metrics.tsv) · [summary](2026-06-09/0012-wave2-ctx-header-summary.json)
- [`0013` — Wave 3: GPU retrieval substrate, reranker + embedder](2026-06-09/0013-wave3-gpu-substrate-rag.md)

### 2026-06-10

- [`0014` — Wave 4: contextual retrieval with `gemma-4`](2026-06-10/0014-wave4-contextual-gemma4-rag.md) · [data](2026-06-10/0014-wave4-contextual-gemma4-metrics.tsv) · [summary](2026-06-10/0014-wave4-contextual-gemma4-summary.json)
- [`0015` — Wave 4: contextual-retrieval generator-model comparison](2026-06-10/0015-wave4-generator-model-comparison-rag.md) · [data](2026-06-10/0015-wave4-model-comparison-metrics.tsv) · [summary](2026-06-10/0015-wave4-model-comparison-summary.json)
- [`0016` — Wave 4: late chunking / LLM-free contextual embedding](2026-06-10/0016-wave4-latechunk-rag.md) · [data](2026-06-10/0016-wave4-latechunk-metrics.tsv) · [summary](2026-06-10/0016-wave4-latechunk-summary.json)
- [`0017` — Wave 4: deterministic session metadata capsule](2026-06-10/0017-wave4-session-meta-rag.md) · [data](2026-06-10/0017-wave4-session-meta-metrics.tsv) · [summary](2026-06-10/0017-wave4-session-meta-summary.json)
- [`0018` — Wave 4: Doc2Query / document expansion](2026-06-10/0018-wave4-doc2query-rag.md) · [data](2026-06-10/0018-wave4-doc2query-metrics.tsv) · [summary](2026-06-10/0018-wave4-doc2query-summary.json)
- [`0019` — Wave 4: long-context reader / packing arms scoping record](2026-06-10/0019-wave4-reader-packing-rag.md)
- [`0020` — Wave 5: deterministic graph / source-map overlay](2026-06-10/0020-wave5-graph-overlay-rag.md) · [data](2026-06-10/0020-wave5-graph-overlay-metrics.tsv) · [replicate](2026-06-10/0020-wave5-graph-overlay-replicate-metrics.tsv)
- [`0021` — Wave 6: query routing and adaptive retrieval, plus Qwen reranker A/B](2026-06-10/0021-wave6-query-routing-rag.md) · [data](2026-06-10/0021-wave6-query-routing-metrics.tsv) · [Qwen final](2026-06-10/0021-wave6-qwen-final-metrics.tsv)

### 2026-06-12

- [`0022` — Wave 7: answer faithfulness on the Qwen caveat slice](2026-06-12/0022-wave7-answer-faithfulness-rag.md) · [citation data](2026-06-12/0022-wave7-caveat-metrics.tsv) · [extractive data](2026-06-12/0022-wave7-caveat-extractive-metrics.tsv)
