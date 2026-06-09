# plans/

Higher-level design docs that frame _what_ to build and _why_, then guide the
detailed work. Each plan records its **Date** (and last-updated). When a plan grows
past ~500 lines, it gets its own subdirectory for modular pieces.

Naming: `YYYY-MM-DD/NNNN-slug.md`, `NNNN` unique across the whole `plans/` tree.

## Plans

### 2026-06-07

- [`0001` — VCS guardrails for jj workspace isolation](2026-06-07/0001-vcs-guardrails-for-jj-workspace-isolation.md) — the guard-hook design that the [issues](../issues/OVERVIEW.md) 0002/0004/0005 motivated.
- [`0002` — `improving-docs-and-rag-skills` harness](2026-06-07/0002-improving-docs-and-rag-skills.md) — co-optimizing a `docs` and a `rag` skill; §10 specifies this very `docs/` convention.

### 2026-06-08

- [`0003` — RAG eval set Phase 1](2026-06-08/0003-rag-eval-set-phase-1.md) — **207** verified, source-grounded gold Q&A pairs (paraphrased query + grep-checked sentinels + primary paths, `code`/`nl` split) across `coding-agent-skills`, the four Alpha Zero repos, and `website`, for optimizing `setting-up-rag` and `retrieving-context`. Consolidates the Claude + Codex passes; machine-readable [`eval-set.json`](2026-06-08/0003-rag-eval-set-phase-1/eval-set.json).
- [`0004` — RAG optimization Phase 2 (cursor)](2026-06-08/0004-cursor-rag-optimization-phase-2.md) — SOTA research synthesis, local dependency checklist, local-LLM decision, and prioritized Phase 3 experiment matrix (Waves 1–3). Research detail in [`0003` research](../research/2026-06-08/0003-cursor-rag-optimization-phase-2-sota-techniques.md).
- [`0006` — Codex RAG optimization Phase 2](2026-06-08/0006-codex-rag-optimization-phase-2.md) — plan to wire the Phase 1 eval set into the harness, baseline all six repos, benchmark contextual retrieval, stronger local models, code-specific retrieval, long-document/graph arms, and document local dependency plus local-LLM requirements.
