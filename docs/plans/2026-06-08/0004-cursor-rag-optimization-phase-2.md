# Plan: RAG optimization — Phase 2 (research + experiment design)

- **Date created:** 2026-06-08
- **Last updated:** 2026-06-08
- **Status:** Phase 2 complete — research captured; Phase 3 ready to run
- **Authors:** Cursor (Composer)
- **Repo:** `coding-agent-skills`
- **Harness:** [`improving-context-retrieval-skills`](../../../.agents/skills/improving-context-retrieval-skills/SKILL.md)
- **Scope:** Phase 2 of [Optimizing RAG Setup](../../prompts/2026-06-08/0005-optimizing-rag-setup.md) — research SOTA retrieval/answer techniques, document prerequisites, and a prioritized experiment matrix for Phase 3. Builds on the Phase 1 gold set ([`0003-rag-eval-set-phase-1.md`](0003-rag-eval-set-phase-1.md), [`eval-set.json`](0003-rag-eval-set-phase-1/eval-set.json)).

---

## Summary

Phase 1 delivered **207 verified gold facts** across six repos with `code` / `nl` cohorts.
Phase 2 reviewed recent RAG literature, prior repo benchmarks (especially [0009](../../benchmarks/2026-06-08/0009-graphify-graphrag-rag.md)), and the current [`setting-up-rag`](../../../.agents/skills/setting-up-rag/SKILL.md) defaults. **GraphRAG/graphify are deprioritized** as primary backends; the plan optimizes the existing **Qdrant + FastEmbed hybrid pipeline** first, then layers optional graph overlay and index-time contextualization.

Research write-up: [`docs/research/2026-06-08/0003-cursor-rag-optimization-phase-2-sota-techniques.md`](../../research/2026-06-08/0003-cursor-rag-optimization-phase-2-sota-techniques.md).

---

## Phase 2 deliverables (this doc)

| Deliverable | Location | Status |
| --- | --- | --- |
| SOTA technique survey + repo-specific hypotheses | [`0003` research](../../research/2026-06-08/0003-cursor-rag-optimization-phase-2-sota-techniques.md) | done |
| Experiment matrix + dependency list | this file §Experiment matrix, §Prerequisites | done |
| Local LLM requirement decision | this file §Local LLM | done |
| Harness wiring notes from Phase 1 | this file §Harness wiring | done |

---

## Key conclusions from research

1. **Keep Qdrant hybrid as the scored retrieval core.** Prior benchmarks: perfect history
   recall@20 on Qdrant; catastrophic alpha-zero **code** recall (0/3 in 0009 slice). Fix code
   path before graph replacements.
2. **Split metrics by `domain=code` and `domain=nl`.** Phase 1 set is already tagged; Phase 3
   must never average away a code regression.
3. **Highest ROI knobs (no LLM):** SPLADE sparse, bge-base dense, code metadata (path,
   language, symbol), parent/small-to-big retrieval, prefetch/rerank sweep, local graph overlay
   from 0009 prototype.
4. **Highest ROI knobs (with local LLM):** contextual retrieval on `nl` corpora (transcripts,
   `memory/`), optional Qwen3-8B BESTFIT rerank for code queries.
5. **Graphify/GraphRAG:** optional enrichment only; fix transcript `evidence_source_file` before
   trusting session graphs.

---

## Prerequisites — install before Phase 3

Run these on the **benchmark host** (your workstation) once. Paths follow
[`setting-up-rag` SETUP.md](../../../.agents/skills/setting-up-rag/SETUP.md).

### Required (baseline Phase 3 loop)

```sh
# Core RAG stack (idempotent)
bash .agents/skills/setting-up-rag/scripts/setup-local-rag.sh --warm

# Docker Qdrant server (recommended for six-repo indexing — concurrent query + stable IDF)
docker run -d --name rag-qdrant -p 6333:6333 -p 6334:6334 \
  -v "$HOME/.cache/rag-skill/qdrant-storage:/qdrant/storage" qdrant/qdrant

# Python for harness eval (Phase 0 path)
python3 -m pip install --user qdrant-client fastembed rank-bm25  # or use skill venv via RAG_PYTHON

# Verify
bash .agents/skills/setting-up-rag/scripts/check-local-rag.sh   # expect READY
```

| Dependency | Purpose | Notes |
| --- | --- | --- |
| Python 3.10+ | harness + index/query scripts | skill uses `$RAG_HOME/venv` |
| `qdrant-client[fastembed]` | hybrid index + query | pinned in skill setup |
| Qdrant server **or** embedded mode | vector store | server preferred for multi-repo |
| Docker (optional) | Qdrant daemon | embedded OK for dev |
| ~2 GB disk | model cache | bge-small + bm25 + ms-marco rerank |
| Git access to six repos | corpus roots | paths in `eval-set.json` |

### Recommended for Tier A experiments

| Dependency | Purpose | Install |
| --- | --- | --- |
| **SPLADE** sparse model | better lexical recall | auto-download via FastEmbed on first index; set in `rag-config.json` |
| **bge-base-en-v1.5** | stronger dense | same; re-index with `--recreate` |
| **tree-sitter** + C++/TS grammars | AST chunking prototype | `pip install tree-sitter tree-sitter-cpp tree-sitter-typescript` or `astchunk` CLI |
| **ripgrep** | gold verification / harness | usually preinstalled |

### Optional for Tier B/C (local LLM arms)

| Dependency | Purpose | Install |
| --- | --- | --- |
| **Ollama** or **vLLM** | index-time contextual retrieval + query transforms | `ollama pull qwen3:8b` or Gemma 3 variant you prefer |
| **CUDA toolkit** | GPU embed/rerank | already on workstation |
| `fastembed-gpu` or **sentence-transformers** | GPU cross-encoder / larger embedders | only if CPU rerank too slow at scale |
| **Qwen3-8B** (or similar) | CodeRAG-style BESTFIT rerank | ~16 GB VRAM; you have headroom on RTX Pro 6000 |

### Explicitly NOT required for baseline

- GraphRAG / graphify / Gemini API
- Cloud embedding or rerank APIs
- TanStack Start eval app (Phase 1 of harness — deferred until Phase 0 signal on new gold set)

---

## Local LLM

**You should stand up a local model before Tier B/C experiments, not before the baseline.**

| Phase 3 stage | Local LLM? | Recommendation |
| --- | --- | --- |
| **3a — baseline sweep** (config knobs, SPLADE, chunk metadata) | No | CPU FastEmbed + ms-marco rerank |
| **3b — contextual retrieval** (`nl` corpora) | **Yes** | Ollama/vLLM with **Qwen3-8B** or **Gemma 3 4B/12B** on one GPU; batch index overnight |
| **3c — query transforms** | Optional | same model; gate per cohort |
| **3d — LLM rerank for code** | Optional | Qwen3-8B on second GPU if cross-encoder plateaus |

Gemma 4 (when available to you) is fine for contextual capsules — quality matters less than
consistency and cost; **8B class is the sweet spot** for rerank following CodeRAG. No local LLM
needed if you limit Phase 3 to Tier A only (still valuable).

---

## Harness wiring (from Phase 1 → Phase 3)

Before first eval run:

1. **Import gold set** — point harness at [`eval-set.json`](0003-rag-eval-set-phase-1/eval-set.json); map records to `gold.py` `Fact` shape (fields already aligned).
2. **Self-reference exclusion** — add to `gold.py` `EXCLUDE_GLOBS`:
   - `plans/2026-06-08/0003-rag-eval-set-phase-1*`
   - `plans/2026-06-08/0004-cursor-rag-optimization-phase-2*`
3. **Per-repo corpus roots** — index each repo separately; `--kind code` for `domain=code`,
   `--kind md` for `domain=nl`.
4. **Score separately** — `check-retrieval.py --corpus-kind code --domain code` and
   `--corpus-kind md --domain nl`.
5. **Floor first** — `--no-retrieval` baseline = 0 across metrics each round.
6. **Re-verify** — `python3 docs/plans/2026-06-08/0003-rag-eval-set-phase-1/verify.py eval-set.json`

---

## Experiment matrix (Phase 3 — one variable at a time)

Each experiment → one file under `docs/benchmarks/2026-06-08/` naming the knob and metric deltas.
Keep/revert rule: headline metric (recall@20, nDCG@10) must rise on **held-out** split per cohort.

### Wave 1 — no LLM (run first)

| ID | Variable | Baseline | Candidate | Primary metric | Cohorts |
| --- | --- | --- | --- | --- | --- |
| W1-01 | sparse model | `Qdrant/bm25` | `Splade_PP_en_v1` | recall@20 | code, nl |
| W1-02 | dense model | `bge-small` | `bge-base` | nDCG@10 | nl |
| W1-03 | code chunk metadata | path in payload only | +language, +symbol, +repo | recall@20 | code |
| W1-04 | code chunk size | `code_size=120` | 32–64 lines / astchunk | recall@20 | code |
| W1-05 | parent retrieval | off | small child → parent window | nDCG@10, answer sentinel | nl, code |
| W1-06 | prefetch / rerank.top_n | 60 / 50 | 80 / 80 and 40 / 30 | recall@20 vs latency | all |
| W1-07 | fusion | RRF | DBSF / weighted RRF | per-repo winner | all |
| W1-08 | graph overlay | off | 0009 local-graphrag expansion post-RRF | recall@20 code | code |

### Wave 2 — index-time LLM (after W1 plateaus or parallel on nl)

| ID | Variable | Candidate | Cohorts | Notes |
| --- | --- | --- | --- | --- |
| W2-01 | contextual retrieval | Anthropic-style prefix via local LLM | **nl only** | compare to W1-05 parent retrieval |
| W2-02 | late chunking | Jina v3 long embed + pool | nl transcripts | A/B vs W2-01 cost |
| W2-03 | static context capsule | rule-based header from path+title | all | no LLM; pairs with updating-docs |

### Wave 3 — query-time + generation

| ID | Variable | Candidate | Gate |
| --- | --- | --- | --- |
| W3-01 | multi-query expansion | 3 paraphrases → fuse | disable if code precision drops |
| W3-02 | HyDE | hypothetical doc embed | nl hard tier only |
| W3-03 | LLM BESTFIT rerank | Qwen3-8B | code cohort |
| W3-04 | CRAG strip filter | cross-encoder strip scores | answer_hit@5 secondary |

### Stop rule (Phase 3 exit)

Per [0005 prompt](../../prompts/2026-06-08/0005-optimizing-rag-setup.md): continue until recall@20 /
nDCG@10 / sentinel factuality stabilize **per cohort** across all six repos and further single-knob
changes stop helping. Report code and session-transcript slices separately every benchmark file.

---

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Self-reference inflation on `coding-agent-skills` | EXCLUDE_GLOBS + verify no question echoes sentinel |
| Averaging code + nl | mandatory split in scoreboard |
| Contextual retrieval cost | nl-only; cache prefixes; batch on GPU workstation |
| AST chunking complexity | defer cAST until line+metadata stalls |
| graphify provenance | do not use for session primary-file qrels until fixed |
| Overfitting 207 queries | hash-held-out split; confirm wins on held-out |

---

## Links

- Phase 1 plan: [`0003-rag-eval-set-phase-1.md`](0003-rag-eval-set-phase-1.md)
- Prompt: [`0005-optimizing-rag-setup.md`](../../prompts/2026-06-08/0005-optimizing-rag-setup.md)
- Research: [`0003-cursor-rag-optimization-phase-2-sota-techniques.md`](../../research/2026-06-08/0003-cursor-rag-optimization-phase-2-sota-techniques.md)
- Prior benchmarks: [`0006`](../../benchmarks/2026-06-08/0006-rag-skill-baseline-vs-rag.md), [`0008`](../../benchmarks/2026-06-08/0008-qdrant-vs-local-graphrag.md), [`0009`](../../benchmarks/2026-06-08/0009-graphify-graphrag-rag.md)
