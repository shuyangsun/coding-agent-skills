# Plan: RAG Eval Set Phase 1

- **Date created:** 2026-06-08
- **Last updated:** 2026-06-08
- **Status:** Phase 1 collection complete; candidate eval set only
- **Author:** Codex, workspace `codex-rag-eval-set`
- **Repo:** `coding-agent-skills`
- **Scope:** Collect detailed source-grounded question-and-answer pairs for improving `setting-up-rag` and `retrieving-context` with the `improving-context-retrieval-skills` harness. Existing docs and source files in the six target repos were read as-is. The `updating-docs` skill was not modified.

## Summary

This plan stores the Phase 1 candidate gold set for later RAG optimization. It covers all six requested repos:

| Repo                                                      | Candidates | Split                           |
| --------------------------------------------------------- | ---------: | ------------------------------- |
| `/Users/shuyang/developer/coding-agent-skills`            |         14 | 7 codebase, 7 prompting/history |
| `/Users/shuyang/developer/alpha-zero/alpha-zero`          |         12 | codebase/docs                   |
| `/Users/shuyang/developer/alpha-zero/alpha-zero-api`      |         14 | codebase/docs                   |
| `/Users/shuyang/developer/alpha-zero/az-game-tic-tac-toe` |         12 | codebase/docs                   |
| `/Users/shuyang/developer/alpha-zero/az-game-xiang-qi`    |         16 | codebase/docs                   |
| `/Users/shuyang/developer/website`                        |         16 | 8 codebase, 8 session/history   |

Use these as candidate records for the next harness phase. Each item should later become a structured gold fact with a `domain` (`code`, `nl`, or `history`), query text, answer/sentinel(s), primary relevant documents, and graded `qrels`.

## Candidate Format

Each candidate contains:

- **Category** - the eval slice or subsystem.
- **Question** - a specific, multi-hop query that should require more than a shallow keyword match.
- **Grounded answer** - the expected answer based on local primary sources.
- **Sources** - paths and line numbers from the target repo root unless otherwise stated.
- **Eval note** - why the item is useful for RAG evaluation.

## `/Users/shuyang/developer/coding-agent-skills`

This repo has both source/skill mechanics and exported session transcripts, so the set is split evenly between codebase questions and prompting/history questions.

### 1. Retrieval routing ladder

- **Category:** codebase
- **Question:** When an agent needs repo context, what retrieval ladder does `retrieving-context` require, and when should it escalate from manual search to local RAG?
- **Grounded answer:** It prefers managed/cloud RAG first if the repo exposes it, then local RAG via `setting-up-rag` for medium-to-large local corpora, then manual doc-structure navigation as the always-available floor. Manual search should escalate once the agent is paging through many hits, working with long transcripts, or expecting repeated queries. Retrieved hits are candidates only; the agent must open primary sources before relying on them.
- **Sources:** `.agents/skills/retrieving-context/SKILL.md:30`, `.agents/skills/retrieving-context/SKILL.md:32`, `.agents/skills/retrieving-context/SKILL.md:46`, `.agents/skills/retrieving-context/SKILL.md:69`, `.agents/skills/retrieving-context/SKILL.md:88`, `.agents/skills/retrieving-context/SKILL.md:106`.
- **Eval note:** Tests whether retrieval selects the right tier instead of blindly using keyword search or overbuilding RAG.

### 2. Qdrant indexing and re-index semantics

- **Category:** codebase
- **Question:** How does the current `setting-up-rag` indexer build a hybrid Qdrant collection, and how does it prevent duplicate chunks when re-indexing with Snowflake point IDs?
- **Grounded answer:** `index.py` builds a collection with named `dense` and `sparse` vectors, using FastEmbed dense vectors and BM25-style sparse vectors. It uses a live Qdrant server if available or embedded on-disk mode otherwise. Because Snowflake IDs are time-based, re-indexing would append duplicate points unless old chunks were removed first; the indexer gathers affected `doc_id`s and deletes matching existing points before inserting new Snowflake-ID points. Fully removed docs still require `--recreate`.
- **Sources:** `.agents/skills/setting-up-rag/scripts/index.py:4`, `.agents/skills/setting-up-rag/scripts/index.py:12`, `.agents/skills/setting-up-rag/scripts/index.py:70`, `.agents/skills/setting-up-rag/scripts/index.py:76`, `.agents/skills/setting-up-rag/scripts/index.py:81`, `.agents/skills/setting-up-rag/scripts/index.py:86`, `.agents/skills/setting-up-rag/scripts/index.py:100`.
- **Eval note:** Requires understanding both vector-store setup and the non-obvious delete-before-upsert invariant.

### 3. VCS boundary filtering in corpus loaders

- **Category:** codebase
- **Question:** What rule prevents nested Jujutsu workspaces or Git worktrees from being indexed as parent-repo files, and what exception must still work?
- **Grounded answer:** Corpus loaders treat `.git` and `.jj` as VCS boundary markers. When walking a corpus, they prune VCS roots below the selected corpus root and skip dependency/build directories. The selected corpus root itself may be a Git worktree or Jujutsu workspace, so direct indexing of that workspace must still work.
- **Sources:** `.agents/skills/setting-up-rag/scripts/rag_lib.py:51`, `.agents/skills/setting-up-rag/scripts/rag_lib.py:58`, `.agents/skills/setting-up-rag/scripts/rag_lib.py:76`, `.agents/skills/setting-up-rag/scripts/rag_lib.py:83`, `.agents/skills/improving-context-retrieval-skills/scripts/gold.py:276`, `.agents/skills/improving-context-retrieval-skills/SCENARIOS.md:71`.
- **Eval note:** Evaluates whether RAG understands workspace isolation and avoids duplicate or unrelated corpus pollution.

### 4. Chunking strategy and min-word floor

- **Category:** codebase
- **Question:** How does `setting-up-rag` chunk Markdown and code differently, and why is the Markdown `min_words` merge floor important?
- **Grounded answer:** Markdown is split by headings, tiny adjacent sections are merged up to `min_words`, and overlong sections fall back to fixed windows. Code is packed by blank-line-separated blocks so small functions/configs stay intact, with fixed windows only for oversized blocks. The `min_words` floor prevents heading-dense docs from exploding into many tiny chunks; this repo recorded a roughly 2.5x chunk-count reduction at equal recall.
- **Sources:** `.agents/skills/setting-up-rag/CHUNKING.md:12`, `.agents/skills/setting-up-rag/CHUNKING.md:15`, `.agents/skills/setting-up-rag/CHUNKING.md:19`, `.agents/skills/setting-up-rag/scripts/rag_lib.py:132`, `.agents/skills/setting-up-rag/scripts/rag_lib.py:169`, `docs/benchmarks/2026-06-08/0006-rag-skill-baseline-vs-rag.md:98`.
- **Eval note:** Tests retrieval-quality reasoning beyond surface chunk-size knobs.

### 5. Harness factorial attribution

- **Category:** codebase
- **Question:** In the context-retrieval harness, how do `N`, `D`, `b`, `r`, `Z`, `simple`, and `rag` map to skill attribution, and what is the interaction formula?
- **Grounded answer:** `Z` is the no-doc/no-RAG floor. `N` is the naive corpus, `D` is the structured/docs-skill corpus, `b` is baseline RAG config, and `r` is the `setting-up-rag` config. The four cells are `Nb`, `Db`, `Nr`, and `Dr`; docs effects are `Db - Nb` and `Dr - Nr`, RAG effects are `Nr - Nb` and `Dr - Db`, and coupling is `(Dr - Db) - (Nr - Nb)`. `simple` mode measures manual structure navigation; `rag` mode measures routing through the RAG pipeline, so a `retrieving-context` change must not win one mode while regressing the other.
- **Sources:** `.agents/skills/improving-context-retrieval-skills/MATRIX.md:10`, `.agents/skills/improving-context-retrieval-skills/MATRIX.md:14`, `.agents/skills/improving-context-retrieval-skills/MATRIX.md:19`, `.agents/skills/improving-context-retrieval-skills/METRICS.md:56`, `.agents/skills/improving-context-retrieval-skills/METRICS.md:58`, `.agents/skills/improving-context-retrieval-skills/SKILL.md:157`.
- **Eval note:** Forces multi-document reasoning about the experimental design, not just metric lookup.

### 6. Gold-set firewall and qrels modes

- **Category:** codebase
- **Question:** What contamination controls does `gold.py` enforce, and how do `pinned` and `sentinel` qrels differ?
- **Grounded answer:** The firewall rejects queries that echo their own sentinels or overlap too much lexically with primary docs. It excludes harness plans/sessions, context-retrieval benchmark reports, and every `OVERVIEW.md` from corpus snapshots to avoid scoring summaries or self-referential docs. In `pinned` mode, hand-pinned primary docs are grade 2 and other sentinel-containing docs are grade 1. In `sentinel` mode, any corpus doc containing all sentinels is grade 2 and partial sentinel matches are grade 1, which works even for naive corpora with opaque filenames.
- **Sources:** `.agents/skills/improving-context-retrieval-skills/scripts/gold.py:19`, `.agents/skills/improving-context-retrieval-skills/scripts/gold.py:62`, `.agents/skills/improving-context-retrieval-skills/scripts/gold.py:75`, `.agents/skills/improving-context-retrieval-skills/scripts/gold.py:357`, `.agents/skills/improving-context-retrieval-skills/scripts/gold.py:362`, `.agents/skills/improving-context-retrieval-skills/scripts/gold.py:366`, `.agents/skills/improving-context-retrieval-skills/scripts/gold.py:429`.
- **Eval note:** Checks whether an evaluator can distinguish real evidence from leakage-prone summaries and benchmark writeups.

### 7. Phase-0 eval and content-type split

- **Category:** codebase
- **Question:** How does the Phase-0 eval measure retrieval without services or LLM generation, and how does it keep code and natural-language corpora from being mis-scored against each other?
- **Grounded answer:** `docs-eval.py` runs deterministic local retrieval with BM25 plus an in-memory hashed-vector index, then `check-retrieval.py` scores the run against `gold.py` qrels. Phase 0 cannot generate answers, so factuality is `NA`; `retrieval_hit@20` is the answerability proxy. Code and natural language are separated by `--corpus-kind code --domain code` versus `--corpus-kind md --domain nl`, and both `docs-eval.py` and `check-retrieval.py` reject mismatched `domain`/`corpus-kind` combinations to avoid cross-domain sentinel overlap.
- **Sources:** `.agents/skills/improving-context-retrieval-skills/scripts/docs-eval.py:37`, `.agents/skills/improving-context-retrieval-skills/scripts/docs-eval.py:312`, `.agents/skills/improving-context-retrieval-skills/scripts/docs-eval.py:315`, `.agents/skills/improving-context-retrieval-skills/scripts/check-retrieval.py:4`, `.agents/skills/improving-context-retrieval-skills/scripts/check-retrieval.py:15`, `.agents/skills/improving-context-retrieval-skills/scripts/check-retrieval.py:67`.
- **Eval note:** Tests harness mechanics and guards against inflated metrics from mixed corpora.

### 8. Optimizing-RAG prompt requirements

- **Category:** prompting/history
- **Question:** What did `docs/prompts/2026-06-08/0005-optimizing-rag-setup.md` ask Phase 1 to collect for this repo, and what constraint did it put on `updating-docs`?
- **Grounded answer:** The prompt asked agents to use the `improving-context-retrieval-skills` harness to improve `setting-up-rag` and `retrieving-context`. Phase 1 required 10-20 detailed Q&A pairs per repo, with repos like `coding-agent-skills` split half codebase and half prompting/history/session recollection. It also explicitly said to use existing docs as-is and not modify `updating-docs`, focusing on RAG.
- **Sources:** `docs/prompts/2026-06-08/0005-optimizing-rag-setup.md:3`, `docs/prompts/2026-06-08/0005-optimizing-rag-setup.md:16`, `docs/prompts/2026-06-08/0005-optimizing-rag-setup.md:20`, `docs/prompts/2026-06-08/0005-optimizing-rag-setup.md:22`, `docs/prompts/2026-06-08/0005-optimizing-rag-setup.md:23`.
- **Eval note:** Directly mirrors the current eval-set collection task and checks prompt-following memory.

### 9. Docs/RAG harness plan and convention migration

- **Category:** prompting/history
- **Question:** What documentation convention did the June 7 docs/RAG plan propose, and how did the loop compare revisions?
- **Grounded answer:** The plan observed that only `coding-sessions/` used dated subdirectories, while other doc types had inconsistent flat layouts and no `OVERVIEW.md` taxonomy. It proposed `docs/<type>/YYYY-MM-DD/NNNN-slug.md`, globally unique zero-padded indexes, required front matter, per-directory and top-level overviews, and adding `research`. The loop provisions N/D corpora and baseline/skill RAG configs, runs WRITE/RAG/READ loops, scores objectively, then compares recall, marginals, interaction CIs, factuality, latency, and tokens.
- **Sources:** `docs/plans/2026-06-07/0002-improving-docs-and-rag-skills.md:444`, `docs/plans/2026-06-07/0002-improving-docs-and-rag-skills.md:451`, `docs/plans/2026-06-07/0002-improving-docs-and-rag-skills.md:457`, `docs/plans/2026-06-07/0002-improving-docs-and-rag-skills.md:460`, `docs/plans/2026-06-07/0002-improving-docs-and-rag-skills.md:480`, `docs/plans/2026-06-07/0002-improving-docs-and-rag-skills.md:486`.
- **Eval note:** Requires retrieving an architectural plan and connecting conventions to evaluation mechanics.

### 10. Docs-skill floor benchmark interpretation

- **Category:** prompting/history
- **Question:** In benchmark `0005-docs-skill-floor-vs-doc`, what result was considered the cleanest signal, and why was the docs-by-RAG interaction not computable?
- **Grounded answer:** The cleanest signal was floor-to-with-docs: `retrieval_hit@20` rose from 0 to 0.833 and `recall@20` from 0 to 0.642. But `Db - Nb` was zero at baseline because fixed 256-word dense chunking ignored the structure that made `D` better. The run only included the baseline `b` column, so `Nr` and `Dr` were absent; therefore the RAG marginal and docs-by-RAG interaction could not be computed.
- **Sources:** `docs/benchmarks/2026-06-08/0005-docs-skill-floor-vs-doc.md:33`, `docs/benchmarks/2026-06-08/0005-docs-skill-floor-vs-doc.md:63`, `docs/benchmarks/2026-06-08/0005-docs-skill-floor-vs-doc.md:68`, `docs/benchmarks/2026-06-08/0005-docs-skill-floor-vs-doc.md:85`, `docs/benchmarks/2026-06-08/0005-docs-skill-floor-vs-doc.md:96`, `docs/benchmarks/2026-06-08/0005-docs-skill-floor-vs-doc.md:145`.
- **Eval note:** Tests nuanced benchmark interpretation rather than just reading the headline table.

### 11. RAG skill creation and benchmark `0006`

- **Category:** prompting/history
- **Question:** What did the `0036` RAG-skill session build and verify, and what were the main `0006` benchmark deltas?
- **Grounded answer:** The session built a local-first Qdrant + FastEmbed RAG skill with setup/check scripts plus `index.py`, `query.py`, `rag_lib.py`, and config. It proved the real pipeline end to end: dense `bge-small`, sparse BM25 with IDF, named-vector upsert, RRF fusion, and cross-encoder rerank. The skill chunker produced 1092 chunks versus 2729 in the Phase-0 heading chunker. Benchmark `0006` found RAG made every natural-language query answerable (`retrieval_hit@20` to 1.000), improved natural-language recall by +0.100, and improved code ranking by +0.141 nDCG and +0.153 MRR. A follow-up switched point IDs to Snowflakes and proved delete-stale by holding re-index count at 1092 rather than doubling.
- **Sources:** `docs/coding-sessions/2026-06-08/0036-claude-improving-docs-and-rag-rag-skill.md:153`, `docs/coding-sessions/2026-06-08/0036-claude-improving-docs-and-rag-rag-skill.md:185`, `docs/coding-sessions/2026-06-08/0036-claude-improving-docs-and-rag-rag-skill.md:291`, `docs/benchmarks/2026-06-08/0006-rag-skill-baseline-vs-rag.md:45`, `docs/benchmarks/2026-06-08/0006-rag-skill-baseline-vs-rag.md:48`, `docs/coding-sessions/2026-06-08/0036-claude-improving-docs-and-rag-rag-skill.md:470`.
- **Eval note:** Requires synthesizing session narrative, benchmark numbers, and a later design correction.

### 12. Updating-docs contextual retrieval result

- **Category:** prompting/history
- **Question:** What did the contextual retrieval work conclude about source maps, and what concrete token reductions supported the `updating-docs` changes?
- **Grounded answer:** The benchmark found that explicit source maps and context capsules help advanced retrieval when docs span code. For alpha-zero code under `rag-r`, source maps cut tokens-to-answer from 199 to 99 while preserving primary-source hits; for inception code, tokens-to-answer fell from 396 to 75. The resulting skill guidance says source maps should bridge to primary sources, not replace verification, and docs should include compact retrieval context, exact paths/identifiers, and explicit relationship edges.
- **Sources:** `docs/benchmarks/2026-06-08/0007-updating-docs-contextual-retrieval.md:15`, `docs/benchmarks/2026-06-08/0007-updating-docs-contextual-retrieval.md:19`, `docs/benchmarks/2026-06-08/0007-updating-docs-contextual-retrieval.md:21`, `docs/benchmarks/2026-06-08/0007-updating-docs-contextual-retrieval.md:92`, `.agents/skills/updating-docs/SKILL.md:56`, `.agents/skills/updating-docs/SKILL.md:176`.
- **Eval note:** Evaluates whether retrieval can connect research, benchmark evidence, and skill edits.

### 13. Graphify vs Qdrant vs local GraphRAG

- **Category:** prompting/history
- **Question:** Why did benchmark `0009` recommend against replacing `setting-up-rag` with graphify, even though graphify produced compact contexts?
- **Grounded answer:** Qdrant remained the strongest proven default for history retrieval and small TypeScript app code, while local GraphRAG had the best recall profile across projects. Graphify produced compact contexts, but it was unreliable for coding-session history because graph nodes often used files mentioned inside transcripts as `source_file` instead of the transcript file containing the evidence. It also underperformed on larger mixed C++/Python code. The recommendation was to keep Qdrant/FastEmbed as the default, add code-aware fields or side indexes, and consider a graph/source-map overlay rather than graphify as the sole backend.
- **Sources:** `docs/benchmarks/2026-06-08/0009-graphify-graphrag-rag.md:13`, `docs/benchmarks/2026-06-08/0009-graphify-graphrag-rag.md:15`, `docs/benchmarks/2026-06-08/0009-graphify-graphrag-rag.md:17`, `docs/benchmarks/2026-06-08/0009-graphify-graphrag-rag.md:105`, `docs/benchmarks/2026-06-08/0009-graphify-graphrag-rag.md:113`, `docs/research/2026-06-08/0002-contextual-retrieval-and-graphify.md:10`.
- **Eval note:** Tests historical retrieval over benchmark plus research docs, with a nuanced hybrid-not-replacement answer.

### 14. Nested VCS workspace metric session

- **Category:** prompting/history
- **Question:** What did the `0039-codex-exclude-vcs-workspaces-rag` session add, and how was the new hygiene metric verified?
- **Grounded answer:** The session added marker-based VCS-boundary pruning to the real RAG loader and the harness loader, so nested Jujutsu workspaces, Git worktree `.git` files, and nested Git repos are excluded when they appear under another corpus root. It also added `check-vcs-boundary.py`, which verifies nested VCS roots are excluded while directly selected VCS roots still index. The session reports `vcs_boundary_ok=1`, `vcs_boundary_nested_docs_indexed=0`, direct-root indexing OK, and `gold.py validate` passing with 9 facts across 2 domains.
- **Sources:** `docs/coding-sessions/2026-06-08/0039-codex-exclude-vcs-workspaces-rag.md:61`, `docs/coding-sessions/2026-06-08/0039-codex-exclude-vcs-workspaces-rag.md:67`, `docs/coding-sessions/2026-06-08/0039-codex-exclude-vcs-workspaces-rag.md:82`, `docs/coding-sessions/2026-06-08/0039-codex-exclude-vcs-workspaces-rag.md:129`, `docs/coding-sessions/2026-06-08/0039-codex-exclude-vcs-workspaces-rag.md:138`, `.agents/skills/improving-context-retrieval-skills/scripts/check-vcs-boundary.py:2`, `.agents/skills/improving-context-retrieval-skills/scripts/check-vcs-boundary.py:136`.
- **Eval note:** Combines historical session recollection with current harness metric behavior.

## `/Users/shuyang/developer/alpha-zero/alpha-zero`

No session transcripts were present in the inspected tree, so all candidates are codebase/docs focused.

### 1. Build and game wiring

- **Category:** build system / game abstraction
- **Question:** If this repo is swapped from Xiang Qi to a different game implementation, which files and dimensions must change, and which engine components are intended to remain game-agnostic?
- **Grounded answer:** The root `CMakeLists.txt` currently fetches `az-game-xiang-qi` and `alpha-zero-api`, while Tic Tac Toe remains fetched for tests. A new game requires changing the `FetchContent_Declare(XiangQiGame ...)` block, replacing `game_xq serializer_xq deserializer_xq augmentation_xq inference_xq train_xq` links in `src/CMakeLists.txt`, and updating entrypoints such as `arena.cc`, `mcts.cc`, and `train.cc` that hardcode Xiang Qi includes/types. The model input/output widths also need to match the new serializer; current Xiang Qi compact output is `1 + kMaxLegalActions`. If the new game has history-dependent state, the current empty `RingBufferView` path must be replaced with real history threading. Templates under `include/az/`, such as `Node<G>`, `MCTSPlayer<G>`, and model/policy wrappers, are meant to stay game-agnostic.
- **Sources:** `README.md:5`, `README.md:71`, `README.md:86`, `README.md:90`, `CMakeLists.txt:49`, `src/CMakeLists.txt:18`, `AGENTS.md:38`.
- **Eval note:** Requires connecting README migration instructions, build files, entrypoint assumptions, and API-level game abstraction boundaries.

### 2. Eval weight freezing

- **Category:** training runtime / evaluator isolation
- **Question:** During `alphazero_train`, why do evaluator games use frozen candidate weights even though the trainer is continuously mirroring weights into inference servers?
- **Grounded answer:** The trainer mirrors only the self-play `inference_servers[]` every `mirror_every_steps`; the eval inference server is deliberately separate and not touched by the trainer loop. At each eval cycle, the evaluator loads a candidate snapshot from `eval_anchor_checkpoint_dir`, mirrors that snapshot once into `eval_live_inference_server`, and then plays against older anchor models whose policies each route through their own eval-device server. The docs explicitly state the eval queue is disjoint from self-play queues, so self-play mirroring cannot cause candidate drift mid-match.
- **Sources:** `docs/training_pipeline.md:37`, `docs/training_pipeline.md:85`, `docs/training_pipeline.md:150`, `docs/training_pipeline.md:194`, `docs/training_pipeline.md:203`, `src/az/train/eval.cc:324`, `src/az/train/eval.cc:334`, `src/az/train/trainer.cc:242`.
- **Eval note:** Tests whether retrieval can distinguish self-play replicas, eval candidate replicas, anchor replicas, and the trainer's mirror path.

### 3. Storage layout resolution

- **Category:** config schema / GUI integration
- **Question:** How does `storage.root_dir` affect artifact paths in the C++ trainer, and how does the GUI keep its dashboard, model picker, and spawned daemon aligned with that layout?
- **Grounded answer:** In the C++ config, per-artifact paths are joined onto `storage.root_dir` only when they are non-empty and not already absolute; absolute paths are preserved. The resolved config is written to `<storage.config_dir>/run.toml`, and checkpoint auto-resume scans `<storage.model_checkpoint_dir>` when `resume_from` is absent. The GUI mirrors this with `readStorageLayout`: it reads `<configDir>/run.toml`, resolves every `[storage]` directory against `root_dir`, and uses those resolved paths for CSVs, the pidfile, `--checkpoint-dir`, and `--games-dir`. `AZ_TRAINING_DIR` pins the config directory; `AZ_CONFIG_ROOT` lets the GUI pick the newest `run.toml`.
- **Sources:** `include/az/training/train_config.md:16`, `include/az/training/train_config.md:20`, `include/az/training/train_config.md:23`, `src/az/training/train_config.cc:1043`, `tests/training/train_config_test.cc:633`, `gui/src/server-fns/storage-layout.ts:39`, `gui/README.md:49`, `gui/README.md:63`.
- **Eval note:** Requires joining C++ config semantics with TypeScript GUI layout resolution and runtime daemon spawning behavior.

### 4. Replay checkpoint schema drift

- **Category:** replay persistence / doc-code consistency
- **Question:** What compact replay checkpoint schema does the implementation actually write and load today, and what documentation drift exists in the repo?
- **Grounded answer:** The implementation defines `kSchemaCompactV5 = 5`, writes compact checkpoints with `kSchemaCompactV5`, and rejects any compact checkpoint whose header schema is not V5. V5 appends `material_own` and `material_opp` float targets after the V4 `state_bytes` payload. The material-head doc agrees that replay buffers bumped to V5 and pre-V5 buffers are refused. However, `docs/replay_buffer_checkpoint.md` still describes schema code `4=compact V4 (current)`, so that markdown is stale relative to the code and material-head doc.
- **Sources:** `docs/replay_buffer_checkpoint.md:30`, `docs/beyond_alphazero/material_head.md:51`, `docs/beyond_alphazero/material_head.md:141`, `src/az/training/replay_buffer_checkpoint.cc:32`, `src/az/training/replay_buffer_checkpoint.cc:41`, `src/az/training/replay_buffer_checkpoint.cc:823`, `src/az/training/replay_buffer_checkpoint.cc:928`, `src/az/training/replay_buffer_checkpoint.cc:886`.
- **Eval note:** A shallow search may return the stale markdown; a good RAG system should reconcile docs, implementation, and focused design notes.

### 5. FP8 inference constraints

- **Category:** mixed precision / CUDA model backend
- **Question:** For compact Xiang Qi transformer inference with `inference_precision = "fp8_e4m3"`, why are full batches with `max_batch = 64` and `seq_len = 195` valid while tail batches or single-row forwards may fail, and why does the head stay FP16?
- **Grounded answer:** cuBLASLt FP8 body GEMMs require `M`, `N`, and `K` multiples of 16. Transformer body GEMMs satisfy `N/K` when `d_model` and `d_ffn` are 16-aligned; `M` is `B * seq_len`, so `64 * 195 = 12480 = 16 * 780` works for full compact-Xiang-Qi batches. Tail batches whose `B * seq_len` is not divisible by 16 can hit `CUBLAS_STATUS_NOT_SUPPORTED`, and single-row `Forward` only works if `seq_len` itself is 16-aligned. The policy head stays FP16 because compact Xiang Qi `output_size = 105`, which is not generally 16-aligned. Config validation also restricts non-FP32 precision to transformer architecture and rejects it under model-parallel; FP8 distributional value heads are also rejected.
- **Sources:** `include/az/model/fp8-inference.md:29`, `include/az/model/fp8-inference.md:35`, `include/az/model/fp8-inference.md:45`, `docs/faster_inference.md:230`, `docs/faster_inference.md:241`, `docs/faster_inference.md:249`, `src/az/training/train_config.cc:1381`, `src/az/training/train_config.cc:1390`, `src/az/training/train_config.cc:1424`.
- **Eval note:** Requires combining CUDA shape math, compact Xiang Qi dimensions, backend precision design, and config validation.

### 6. Batch inference async path

- **Category:** inference serving / concurrency
- **Question:** How does `BatchInferenceServer` change behavior when the model implements `IAsyncForwardModel`, and how does it keep `Mirror()` safe?
- **Grounded answer:** For async-capable FP16/FP8 transformer replicas, the server uses two `cudaHostAlloc` pinned staging slots and pipelines submit/wait two-deep: it submits batch N into one slot, advances `next_slot_`, then drains the previous slot while the CPU can pack the next batch. Sync-only models use slot 0 and `ForwardBatch`. `Mirror()` is queued on the same executor and requires the read-side model to be quiescent; the executor drains any in-flight async slot with `WaitForward` before calling `MirrorParametersFrom`. Successful mirrors increment `mirror_version_` and `Stats::mirror_publishes`.
- **Sources:** `include/az/model/batch-inference-server.md:23`, `include/az/model/batch-inference-server.md:31`, `include/az/model/batch-inference-server.md:48`, `include/az/model/batch_inference_server.h:38`, `src/az/model/batch_inference_server.cc:284`, `src/az/model/batch_inference_server.cc:368`, `tests/model/batch_inference_server_test.cc:395`.
- **Eval note:** Tests nuanced retrieval across design docs, header comments, executor implementation, and race-prevention tests.

### 7. Compact and auxiliary heads

- **Category:** model output layout / policy adapters
- **Question:** How do compact policy heads, distributional value heads, opponent-reply heads, and material heads affect transformer output layout and inference adapters?
- **Grounded answer:** Compact heads use `kMaxLegalActions` policy slots instead of `kPolicySize`; legal actions are mapped by per-row `legal_indices`, with padding skipped. Distributional value heads are supported on `CudaTransformer` plus compact policy: the first `NumValueBins()` slots are atom logits on uniform support `[-1,+1]`, and policy logits start after that prefix. The compact policy adapter accepts output widths of `n_value_bins + K`, `n_value_bins + 2K`, `n_value_bins + K + 2`, or `n_value_bins + 2K + 2`, covering baseline, opponent-policy, material, and both auxiliary heads. Material slots are always the trailing two scalar columns.
- **Sources:** `include/az/model/policy_head.md:1`, `include/az/model/policy_head.md:58`, `include/az/model/model.h:100`, `include/az/model/policy.h:420`, `include/az/model/policy.h:428`, `docs/beyond_alphazero/material_head.md:17`, `tests/model/distributional_value_head_test.cc:61`.
- **Eval note:** Requires understanding multiple optional heads and their shared `W_head` layout rather than retrieving one keyword.

### 8. MCTS value point of view and target mixing

- **Category:** MCTS semantics / self-play targets
- **Question:** What perspective are MCTS values stored in, how does virtual loss affect Q, and how does `root_q` become part of self-play value targets?
- **Grounded answer:** Node values are stored in the leaf `last_player_` perspective, not necessarily the side-to-move perspective. Non-terminal network values are negated when `last_player_ != cur_player_`, and backup flips signs when ancestor `LastPlayer()` differs from the leaf's `last_player_`. Virtual loss reads as one `-1` outcome from the parent perspective by increasing effective visits and subtracting from effective value. `MctsResult::root_q` is converted back to side-to-move point of view in `MCTSPlayer`, and self-play can mix it with terminal outcome as `(1 - alpha) * z + alpha * root_q`.
- **Sources:** `include/az/mcts/conventions.md:21`, `include/az/mcts/conventions.md:34`, `include/az/mcts/conventions.md:132`, `include/az/mcts/node.h:446`, `include/az/mcts/node.h:533`, `include/az/mcts/player.h:515`, `src/az/train/self_play.cc:397`, `src/az/train/self_play.cc:399`, `tests/mcts/value_sign_test.cc:77`.
- **Eval note:** Prevents shallow answers that confuse network value point of view, node storage point of view, root point of view, and replay target point of view.

### 9. Gumbel root selection interactions

- **Category:** MCTS search variants
- **Question:** When Gumbel root selection is enabled, which root-level mechanisms are replaced or suppressed, and what policy target is emitted?
- **Grounded answer:** Gumbel root selection owns root descent through a `GumbelSchedule` and suppresses Dirichlet noise, LCB selection, root-side forced playouts, and the normal exploration cutoff / temperature schedule. Winner selection comes from the Gumbel schedule rather than normal visit-proportional or LCB root choice. The training target is not raw visit normalization; when Gumbel is scheduled, the player emits `BuildGumbelImprovedPolicy`, a completed-Q improved policy over all root actions.
- **Sources:** `docs/beyond_alphazero/research.md:637`, `include/az/mcts/player.h:326`, `include/az/mcts/player.h:393`, `include/az/mcts/player.h:446`, `include/az/mcts/player.h:497`, `include/az/mcts/gumbel.h:264`, `tests/mcts/gumbel_root_test.cc:169`.
- **Eval note:** Requires synthesizing research status, player control flow, Gumbel helper behavior, and tests for suppression of noise.

### 10. Reanalyze writeback safety

- **Category:** replay buffer / reanalyze worker
- **Question:** How does the reanalyze worker avoid corrupting replay rows that self-play has evicted, and which row fields does it overwrite versus preserve?
- **Grounded answer:** Compact replay buffers expose `SnapshotForReanalyze`, which samples rows along with physical slot indices and per-slot push-id generations. The worker decodes each row's `state_bytes`; rows with missing/invalid state bytes are skipped. After running MCTS on the reconstructed game, `BuildReanalyzedRow` preserves `input`, `value`, `push_step`, `ply`, `opp_*`, `state_bytes`, and `material_*`, and overwrites only `legal_indices` and `target_values`. `WriteBackReanalyzed` writes an updated row only if the slot's current push-id still matches the sampled generation, silently skipping evicted slots.
- **Sources:** `include/az/training/replay_buffer.md:99`, `include/az/training/replay_buffer.h:194`, `include/az/training/replay_buffer.h:508`, `src/az/train/reanalyze.md:17`, `src/az/train/reanalyze.cc:112`, `src/az/train/reanalyze.cc:130`, `src/az/train/reanalyze.cc:246`, `tests/training/replay_buffer_reanalyze_test.cc:102`.
- **Eval note:** Tests retrieval of a concurrency contract spanning replay buffer APIs, worker implementation, and tests.

### 11. Opponent-reply pairing

- **Category:** self-play sample generation / auxiliary targets
- **Question:** How does self-play build opponent-reply targets when PCR fast searches or resignation low-budget searches are present?
- **Grounded answer:** Opponent-reply targets are based on the next full-search ply, not merely the next ply. Self-play pre-scans the trace so each full-search entry points to the next full-search successor; PCR fast-search and resignation plies are excluded because their visit budget is too low to provide a policy target. For rows with a successor, it augments both current and successor positions, pairs augmented rows by transform index, and sets `opp_legal_indices`, `opp_target_values`, and `opp_present = 1`. Tail full-search samples with no successor are emitted with padding/zero opponent arrays and `opp_present = 0`.
- **Sources:** `docs/beyond_alphazero/opp_reply_head.md:14`, `docs/beyond_alphazero/opp_reply_head.md:31`, `docs/beyond_alphazero/opp_reply_head.md:43`, `src/az/train/self_play.cc:377`, `src/az/train/self_play.cc:433`, `src/az/train/self_play.cc:441`, `tests/training/self_play_opp_pairing_test.cc:5`, `tests/training/self_play_opp_pairing_test.cc:104`.
- **Eval note:** Requires understanding temporal pairing across filtered plies, augmentation alignment, and target masking.

### 12. GUI and serve contract

- **Category:** GUI / HTTP daemon / model loading
- **Question:** What is `alphazero_serve` responsible for versus the TanStack GUI server and browser, and how are model identity, checkpoint version, and live game state handled?
- **Grounded answer:** `alphazero_serve` is a loopback daemon for model listing and inference only; it is stateless with respect to live games because the browser resends the position for each `/infer`. The TanStack side handles filesystem-backed games, CSVs, `run.toml`, pidfile, and proxying `/api/infer`. `/models` lists checkpoint files with `{path, sha256, mtime, size_bytes, schema_version}`. `/infer` accepts a `model_id` that can be a SHA prefix or path and a `wire_version`; version 3 checkpoints load via `CudaMlp::Load`, version 5 via `CudaTransformer::Load`, and other CMLP versions fail clearly. The model cache is keyed by sha256, has LRU capacity default 2, and serializes same-model inference through a per-cache-entry mutex while allowing different cached models to interleave.
- **Sources:** `src/serve.cc:7`, `src/serve.cc:113`, `src/serve.cc:199`, `src/serve.cc:243`, `src/serve.cc:475`, `src/serve.cc:502`, `src/serve.cc:539`, `docs/gui_design.md:224`, `docs/gui_design.md:287`, `docs/gui_design.md:337`, `gui/src/engine-kit/server-move-provider.ts:46`.
- **Eval note:** Tests a cross-language contract among C++ HTTP code, frontend provider code, GUI design docs, and checkpoint format dispatch.

## `/Users/shuyang/developer/alpha-zero/alpha-zero-api`

No session transcripts were present in the inspected tree, so all candidates are codebase/docs focused.

### 1. API contract

- **Category:** API contract
- **Question:** In the current API, what must a concrete game type expose to satisfy `Game`, and how did the repo move non-mutating state transitions out of concrete games?
- **Grounded answer:** A game must be a value type with `board_t`, `action_t`, `player_t`, and `error_t`; static `kHistoryLookback`, `kPolicySize`, `kMaxLegalActions`, and `kMaxRounds`; observers including board, round, players, last move, canonical board, legal-action enumeration, terminal state, score, and policy index; mutation via `ApplyActionInPlace` and `UndoLastAction`; and human-readable I/O. The non-mutating `ApplyAction` is a free function that copies the game, applies the action in place, and returns the copy.
- **Sources:** `src/include/alpha-zero-api/game.h:16`, `src/include/alpha-zero-api/game.h:66`, `doc/report.md:53`.
- **Eval note:** Tests whether retrieval can synthesize the whole concept contract plus the design rationale, not just find `concept Game`.

### 2. History and ring buffer semantics

- **Category:** history and ring buffer semantics
- **Question:** How is game-state history represented for serializers, and what are the ordering and zero-history semantics of the ring buffer?
- **Grounded answer:** History is owned by the engine, not by `G`. Serializers receive `RingBufferView<G>`; `game` itself is not in the view. Index 0 is the most recent prior state and `Size() - 1` is the oldest retained state. A `RingBuffer` with capacity 0 is valid: `Push` is a no-op and `View()` returns empty, which is what Markov games such as Tic Tac Toe use through `kHistoryLookback == 0`.
- **Sources:** `src/include/alpha-zero-api/serializer.h:13`, `src/include/alpha-zero-api/ring_buffer.h:41`, `src/include/alpha-zero-api/ring_buffer.h:101`, `src/include/alpha-zero-api/ring_buffer.h:168`, `test/tic_tac_toe/main.cc:40`.
- **Eval note:** Requires combining serializer docs, ring-buffer implementation, and the test alias.

### 3. v0.2.1 migration

- **Category:** v0.2.1 migration
- **Question:** Why did v0.2.1 replace `ValidActions()` with `ValidActionsInto(...)`, and what must callers do with the returned count?
- **Grounded answer:** `ValidActions()` allocated a `std::vector` per MCTS expansion. v0.2.1 writes legal actions into caller-owned `std::array<action_t, kMaxLegalActions>` and returns `count`, eliminating heap allocation in the hot loop. Callers must iterate only `out[0..count)` and ignore entries at indices `>= count`; the deterministic state-only ordering contract remains unchanged.
- **Sources:** `doc/migration-guides/v0.2.0-to-v0.2.1.md:3`, `doc/migration-guides/v0.2.0-to-v0.2.1.md:16`, `doc/migration-guides/v0.2.0-to-v0.2.1.md:92`, `doc/migration-guides/v0.2.0-to-v0.2.1.md:132`.
- **Eval note:** Catches whether RAG can retrieve a versioned migration rationale and operational caller rules.

### 4. Dense policy serialization

- **Category:** dense policy serialization
- **Question:** What exact layout does the default dense policy serializer produce, and how does the default dense deserializer reconstruct legal-action probabilities?
- **Grounded answer:** `DefaultPolicyOutputSerializer` returns `G::kPolicySize + 1` floats laid out as `[z, p_0, ..., p_{kPolicySize-1}]`; slot 0 is `target.z`, and each `target.pi[i]` is scattered to `1 + game.PolicyIndex(actions[i])` after `ValidActionsInto`. `DefaultPolicyOutputDeserializer` requires the same size, gathers `output[1 + PolicyIndex(action)]` for each current legal action, and returns those probabilities verbatim with `output.front()` as value.
- **Sources:** `src/include/alpha-zero-api/defaults/serializer.h:14`, `src/include/alpha-zero-api/defaults/deserializer.h:19`.
- **Eval note:** Requires following scatter/gather through `ValidActionsInto` and `PolicyIndex`.

### 5. Compact policy head

- **Category:** compact policy head
- **Question:** When should a game use the compact policy interfaces, and what do the default compact serializer/deserializer expect?
- **Grounded answer:** The compact path is for games where `kPolicySize` is huge and `kMaxLegalActions / kPolicySize` is small; the guide suggests `kPolicySize > 10^4` and ratio `< 0.1`. The compact serializer emits `value`, `count`, legal policy indices, and values without padding. The compact deserializer expects equal-length `legal_indices` and `values`, skips `kPaddingSlot`, gathers every current legal action by `PolicyIndex`, and errors if a legal slot is missing.
- **Sources:** `doc/migration-guides/v0.1.0-to-v0.2.0.md:36`, `src/include/alpha-zero-api/policy_output.h:58`, `src/include/alpha-zero-api/defaults/compact_serializer.h:13`, `src/include/alpha-zero-api/defaults/compact_deserializer.h:17`.
- **Eval note:** Tests multi-file understanding of compact labels, network outputs, padding, and migration guidance.

### 6. Docs/code consistency

- **Category:** docs/code consistency
- **Question:** Does the current default deserializer apply softmax, and which repo source contradicts that?
- **Grounded answer:** Current dense and compact default deserializers explicitly return probabilities verbatim and say callers whose networks emit logits should implement or compose softmax themselves. The custom Tic Tac Toe deserializer does softmax over legal logits. However, the v0.0.5-to-v0.1.0 migration guide says the default deserializer "softmax-normalizes," which conflicts with the current headers.
- **Sources:** `src/include/alpha-zero-api/defaults/deserializer.h:22`, `src/include/alpha-zero-api/defaults/compact_deserializer.h:28`, `test/tic_tac_toe/deserializer.cc:19`, `doc/migration-guides/v0.0.5-to-v0.1.0.md:174`.
- **Eval note:** A strong eval item for source reconciliation rather than trusting the first matching document.

### 7. Tic Tac Toe game behavior

- **Category:** Tic Tac Toe game behavior
- **Question:** How does `TttGame` enumerate legal actions, map actions to policy slots, and parse/display board coordinates?
- **Grounded answer:** Legal actions are empty cells emitted in row-major order. `PolicyIndex` is `row * TTT_COLS + col`. Display labels rows from 3 down to 1 and columns A-C; parsing trims input, accepts a letter column plus digit row, uppercases the column, checks ranges, and maps row number to internal row index as `TTT_ROWS - row_number`. `ActionToString` reverses that mapping.
- **Sources:** `test/tic_tac_toe/game.cc:150`, `test/tic_tac_toe/game.cc:206`, `test/tic_tac_toe/game.h:116`.
- **Eval note:** Requires connecting internal row/column storage, UI strings, and policy layout.

### 8. Tic Tac Toe serialization/deserialization

- **Category:** Tic Tac Toe serialization/deserialization
- **Question:** What does the Tic Tac Toe state serializer output, and how does the Tic Tac Toe deserializer differ from the default dense deserializer?
- **Grounded answer:** The serializer ignores history because Tic Tac Toe is Markov, flattens the 3x3 board row-major into 9 floats, and emits current-player-relative values by using `player ? -cell : cell`. The Tic Tac Toe deserializer requires `kPolicySize + 1` floats, gathers legal-action logits by `PolicyIndex`, then applies softmax before returning `Evaluation`.
- **Sources:** `test/tic_tac_toe/serializer.h:12`, `test/tic_tac_toe/serializer.cc:10`, `test/tic_tac_toe/deserializer.h:13`, `test/tic_tac_toe/deserializer.cc:45`.
- **Eval note:** Tests a nuanced contrast between example-specific behavior and library defaults.

### 9. Augmentation

- **Category:** augmentation
- **Question:** How many Tic Tac Toe augmentations are produced, why is that historically unusual, and how does inference combine them?
- **Grounded answer:** `AugmentAll` returns 12 variants: original, three rotations, four horizontal-mirror variants, and four vertical-mirror variants. The docs note D4 has only 8 elements, so the last four duplicate earlier transforms but are retained for historical behavior. Inference averages all evaluations equally: values are averaged, and probabilities are mapped back to original legal-action order using `InverseTransformAction` plus `PolicyIndex`.
- **Sources:** `test/tic_tac_toe/augmentation.h:12`, `test/tic_tac_toe/augmentation.cc:115`, `test/tic_tac_toe/inference.cc:30`, `doc/report.md:419`.
- **Eval note:** Requires retrieving code plus design-review commentary to explain a non-obvious historical quirk.

### 10. Training augmentation

- **Category:** training augmentation
- **Question:** How does `TttTrainingAugmenter` preserve and remap a training target under symmetry?
- **Grounded answer:** It calls `AugmentAll`, builds an original action-index map keyed by `game.PolicyIndex`, then for each augmented game enumerates its legal actions, inversely transforms each augmented action back to the original coordinate frame, looks up the original probability, and writes `aug_pi` in the augmented game's legal-action order. `target.z` is preserved unchanged.
- **Sources:** `test/tic_tac_toe/train.h:13`, `test/tic_tac_toe/train.cc:24`, `src/include/alpha-zero-api/augmenter.h:51`.
- **Eval note:** Good for evaluating whether RAG can follow probability alignment through transformed action spaces.

### 11. Terminal state and score semantics

- **Category:** terminal state and score semantics
- **Question:** How does Tic Tac Toe determine terminal states, scoring, and undo behavior?
- **Grounded answer:** `CheckGameStatus` checks rows, columns, diagonals, then draw/ongoing. `IsOver` returns true if `current_round_ >= *kMaxRounds` or status is not ongoing. `GetScore` returns 0 for ongoing/draw, +1 for the player whose symbol won, and -1 otherwise. `ApplyActionInPlace` writes `1` for `current_player_ == true` and `-1` otherwise, toggles the player, increments the round, and records history; `UndoLastAction` clears the last cell, toggles back, and decrements the round.
- **Sources:** `test/tic_tac_toe/game.h:71`, `test/tic_tac_toe/game.cc:61`, `test/tic_tac_toe/game.cc:164`, `test/tic_tac_toe/main.cc:142`.
- **Eval note:** Requires reading private helper logic plus public mutation semantics.

### 12. Build and packaging

- **Category:** build and packaging
- **Question:** How is the header-only API packaged in CMake, and how do tests consume it?
- **Grounded answer:** The root project is `AlphaZeroAPI` version 0.2.1 using C++23. `src/CMakeLists.txt` defines `api` as an `INTERFACE` library with alias `AlphaZeroAPI::api`, configures `configuration.h`, installs public headers, and conditionally defines `defaults`/`AlphaZeroAPI::defaults` only when `DEFAULTS` is enabled. Tests force `DEFAULTS=ON`, bring the parent repo in via `FetchContent`, build Tic Tac Toe static libraries, and link the test executable against serializer, deserializer, inference, train, and game.
- **Sources:** `CMakeLists.txt:3`, `src/CMakeLists.txt:14`, `src/CMakeLists.txt:49`, `test/CMakeLists.txt:10`, `test/CMakeLists.txt:20`.
- **Eval note:** Verifies cross-file understanding of exported targets and test integration.

### 13. Test script and CI

- **Category:** test script and CI
- **Question:** What build scenarios does `test.sh` verify, and how is that script run in CI?
- **Grounded answer:** `test.sh` wipes `build/build-tests`, builds default, `STATIC_ONLY`, `SHARED_ONLY`, expects configuration failure when both static and shared are true, builds with `DEFAULTS=True`, configures the `test` project via FetchContent, builds it, runs `tic-tac-toe-main`, then cleans the build directory. GitHub Actions runs on pushes to `main`, installs `cmake`, `ninja-build`, and `g++`, then executes `bash test.sh`.
- **Sources:** `test.sh:36`, `.github/workflows/test.yml:1`, `src/CMakeLists.txt:1`.
- **Eval note:** Tests whether retrieval can combine local shell logic with CI configuration.

### 14. Historical migrations

- **Category:** historical migrations
- **Question:** What were the major breaking changes across v0.0.3, v0.0.5, v0.1.0, v0.2.0, and v0.2.1?
- **Grounded answer:** v0.0.3 renamed the root namespace from `alphazero` to `az`. v0.0.5 made `IGame` take an explicit error type for `ActionFromString`, encouraging `TttError`/`TttResult<T>` style aliases. v0.1.0 removed virtual `IGame`, split `PolicyOutput` into `Evaluation` and `TrainingTarget`, made history engine-owned, and formalized `PolicyIndex`. v0.2.0 added `kMaxLegalActions` and compact policy interfaces. v0.2.1 replaced heap-allocating `ValidActions()` with caller-owned `ValidActionsInto(...)`.
- **Sources:** `doc/migration-guides/v0.0.2-to-v0.0.3.md:3`, `doc/migration-guides/v0.0.4-to-v0.0.5.md:3`, `doc/migration-guides/v0.0.5-to-v0.1.0.md:1`, `doc/migration-guides/v0.1.0-to-v0.2.0.md:1`, `doc/migration-guides/v0.2.0-to-v0.2.1.md:1`.
- **Eval note:** Requires chronological synthesis across multiple migration documents.

## `/Users/shuyang/developer/alpha-zero/az-game-tic-tac-toe`

No session transcripts were present in the inspected tree, so all candidates are codebase/docs focused.

### 1. Static API contract

- **Category:** API contract / game design
- **Question:** What exact AlphaZero `Game` contract shape does `TttGame` implement, and why does this design avoid virtual dispatch or heap-backed factories?
- **Grounded answer:** `TttGame` is a value-semantic concrete type satisfying `::az::game::api::Game`, enforced by a `static_assert`. It defines `board_t`, `action_t`, `player_t`, and `error_t`; static constants `kHistoryLookback = 0`, `kPolicySize = 9`, `kMaxLegalActions = 9`, and `kMaxRounds = 9`; and the required observers, mutation primitives, and string I/O. The docs emphasize that the MCTS engine is templated on the concrete game and stores instances by value, so there is no virtual base class, no `unique_ptr` factory, and no member `ApplyAction` shadowing the API free function.
- **Sources:** `memory/api_contract.md:13`, `memory/api_contract.md:19`, `include/ttt/game.h:73`, `include/ttt/game.h:87`, `include/ttt/game.h:268`, `memory/mcts_constraints.md:7`.
- **Eval note:** Requires connecting design docs, API notes, and the actual header, not just finding one symbol.

### 2. Packed board and terminal detection

- **Category:** board representation / game state
- **Question:** How are Tic Tac Toe cells encoded in `TttBoard`, and how does `IsOver()` use that encoding to detect wins and draws?
- **Grounded answer:** The board stores 9 cells in a `uint32_t`, two bits per cell in row-major order: `00` empty, `01` X, `10` O, with bits 18..31 reserved. `state.cc` masks the low bit of each cell with `0x15555`, derives O bits by shifting high bits down, and checks both against eight precomputed win-line masks. It also treats the game as over when `round_ >= kMaxRounds` or when the union of X and O low-bit masks equals `0x15555`, meaning all 9 cells are filled.
- **Sources:** `memory/game_design.md:64`, `include/ttt/game.h:21`, `src/ttt/game/state.cc:10`, `src/ttt/game/state.cc:15`, `src/ttt/game/state.cc:48`, `src/ttt/game/state.cc:57`.
- **Eval note:** Tests whether retrieval can assemble bit-level representation, constants, and terminal-state behavior.

### 3. Apply/undo hot path

- **Category:** MCTS mutation semantics
- **Question:** How does the implementation support deep MCTS rollback without heap allocation, and what exact state is restored by `UndoLastAction()`?
- **Grounded answer:** `TttGame` stores `std::array<TttA, 9> action_history_` plus `history_size_`, matching the maximum 9-ply game depth. `ApplyActionInPlace` writes the current player's mark, records the action if history has capacity, increments `round_`, and toggles `cur_player_`. `UndoLastAction` no-ops on empty history; otherwise it pops the last action, clears that cell's two bits, decrements `round_` if positive, and toggles the current player back. Tests apply all 9 moves, record snapshots, then undo one ply at a time and compare board, round, and player.
- **Sources:** `memory/mcts_constraints.md:25`, `memory/mcts_constraints.md:45`, `include/ttt/game.h:258`, `src/ttt/game/action.cc:39`, `src/ttt/game/action.cc:50`, `tests/unit/game_action.cc:181`.
- **Eval note:** Requires code-path reasoning across docs, private fields, implementation, and tests.

### 4. Valid action ordering and policy slots

- **Category:** policy layout / action semantics
- **Question:** Why must `ValidActionsInto()` be deterministic, and how does this repo preserve policy-label alignment through `PolicyIndex`, serialization, and deserialization?
- **Grounded answer:** The docs say policy labels are recorded under `ValidActionsInto()` order; if ordering changes, training labels scramble. The implementation returns empty cell indices in increasing row-major order unless the game is over, and `PolicyIndex(action)` is identity. `SerializePolicyOutputInto` scatters `target.pi[i]` to `out[1 + PolicyIndex(actions[i])]`, while `Deserialize` gathers `output[1 + PolicyIndex(actions[i])]` back in current valid-action order.
- **Sources:** `memory/mcts_constraints.md:72`, `src/ttt/game/action.cc:19`, `src/ttt/game/action.cc:35`, `src/ttt/serializer/serializer.cc:58`, `src/ttt/deserializer/deserializer.cc:20`, `tests/unit/game_action.cc:113`.
- **Eval note:** A shallow search may find each method, but the answer needs the cross-module invariant.

### 5. Canonical board and state encoding

- **Category:** neural-network input encoding
- **Question:** What does `CanonicalBoard()` do for Player 2, and how does that affect the 18-float state vector produced by `TttSerializer`?
- **Grounded answer:** For Player 1 to move, `CanonicalBoard()` returns the raw board. For Player 2 to move, it swaps low and high bits so the current player's marks always encode as `01` and the opponent's as `10`. The serializer then emits 18 floats: slots 0..8 are the current-player mask and slots 9..17 are the opponent mask. Because of this perspective encoding, tests expect a board with X at cell 0 and O to move to serialize the same as a board with O at cell 0 and X to move.
- **Sources:** `include/ttt/game.h:158`, `src/ttt/game/state.cc:37`, `include/ttt/serializer.h:17`, `src/ttt/serializer/serializer.cc:32`, `tests/unit/serializer.cc:60`, `tests/unit/serializer.cc:84`.
- **Eval note:** Forces reconciliation of header docs, bit manipulation, serializer layout, and a subtle test expectation.

### 6. Policy output round trip

- **Category:** serializer / deserializer contract
- **Question:** What is the exact policy output vector layout, what wrong-size error is returned, and how is round-trip behavior tested?
- **Grounded answer:** The policy vector has length `kPolicySize + 1`, so 10 floats. Slot 0 stores `target.z`; slots 1..9 store action priors by `1 + PolicyIndex(action)`, leaving illegal-action slots zero. `TttDeserializer` rejects any span whose size is not 10 with `TttError::kDeserializeWrongSize`, then gathers legal-action priors verbatim with no softmax or renormalization. Tests reject too-short, too-long, and empty vectors, and verify `Deserialize(SerializePolicyOutput(...))` recovers `z` and `pi`.
- **Sources:** `include/ttt/serializer.h:25`, `src/ttt/serializer/serializer.cc:61`, `include/ttt/deserializer.h:16`, `src/ttt/deserializer/deserializer.cc:14`, `tests/unit/deserializer.cc:29`, `tests/unit/deserializer.cc:90`.
- **Eval note:** Checks that retrieval can join format docs, typed errors, implementation, and tests.

### 7. Known coverage gaps

- **Category:** test coverage / API migration
- **Question:** Which documented API-contract checks are still marked incomplete even though implementations exist, and where are those implementations?
- **Grounded answer:** The checklist still marks two gaps: `SerializeCurrentStateInto` and `SerializePolicyOutputInto` should be tested for identical output to their allocating counterparts, and `InverseTransformAction(transform_action(a, sym), sym) == a` should be tested for every supported symmetry and representative action. The `Into` methods are declared in `serializer.h` and implemented with `out->assign(...)` in `serializer.cc`; `TransformAction` and `InverseTransformAction` are declared in `augmentation.h` and implemented from forward/inverse permutation tables in `augmentation.cc`.
- **Sources:** `memory/unittest_checklists.md:155`, `memory/unittest_checklists.md:173`, `include/ttt/serializer.h:66`, `src/ttt/serializer/serializer.cc:32`, `include/ttt/augmentation.h:58`, `src/ttt/augmentation/augmentation.cc:84`.
- **Eval note:** Good eval item for finding a documented gap with implementation lookup.

### 8. D4 augmentation ordering

- **Category:** symmetry augmentation
- **Question:** What are the eight Tic Tac Toe augmentation variants, in what order are they returned, and how is that order encoded in the implementation?
- **Grounded answer:** The D4 set is `kOriginal`, `kRotate90CW`, `kRotate180`, `kRotate270CW`, `kMirrorHorizontal`, `kMirrorVertical`, `kMirrorDiagonalMain`, and `kMirrorDiagonalAnti`. The header says `kOriginal = 0`, rotations first, then reflections, and `AugmentAll` returns one variant per enum member in enum order. The implementation encodes the same order in `kForwardPerm`, reserves 8 results, transforms board cells for each permutation, and builds variants preserving current player and round.
- **Sources:** `memory/augmentation_strategy.md:53`, `include/ttt/augmentation.h:21`, `src/ttt/augmentation/augmentation.cc:13`, `src/ttt/augmentation/augmentation.cc:70`, `tests/unit/augmentation.cc:24`.
- **Eval note:** Requires precise enum-order reasoning across docs, declarations, implementation, and tests.

### 9. Inference-time symmetry aggregation

- **Category:** inference augmenter
- **Question:** How does `TttInferenceAugmenter::Interpret` combine per-variant evaluations back into the original action space?
- **Grounded answer:** It first collects the original valid-action order and initializes result probabilities with that length. For each evaluation variant, it adds the value to a sum, casts the variant index to `TttAugmentation`, gathers that augmented game's valid actions, maps each augmented action back through `InverseTransformAction`, linearly finds the matching original action slot, and accumulates that probability. It returns the mean value and divides accumulated probabilities by the number of evaluations. If augmented or evaluation spans are empty, it returns zero value with correctly sized zero probabilities.
- **Sources:** `memory/augmentation_strategy.md:75`, `include/ttt/inference.h:41`, `src/ttt/inference/inference.cc:19`, `src/ttt/inference/inference.cc:30`, `src/ttt/inference/inference.cc:52`, `tests/unit/inference.cc:81`.
- **Eval note:** The answer depends on algorithmic flow, not just symbol lookup.

### 10. Training-time equivariance

- **Category:** training augmenter
- **Question:** How does the training augmenter avoid the documented bug of treating policy targets as augmentation-invariant?
- **Grounded answer:** The strategy doc says `target.pi` must be permuted alongside the augmented board, while `target.z` is preserved. The implementation collects original valid actions, calls `AugmentAll`, then for each augmented game collects its valid actions and builds a fresh `TrainingTarget`. For each augmented action, it maps back to the original action with `InverseTransformAction` and copies the matching original `target.pi[j]` into the augmented `pi[i]`. Tests verify one output per variant, `pi` length matches each augmented game's valid-action count, probability mass is preserved, and `z` is unchanged.
- **Sources:** `memory/augmentation_strategy.md:92`, `include/ttt/train.h:13`, `src/ttt/train/train.cc:14`, `src/ttt/train/train.cc:32`, `tests/unit/train.cc:56`, `tests/unit/train.cc:80`.
- **Eval note:** Evaluates whether retrieval captures the subtle invariant/equivariant distinction.

### 11. REPL integration contract

- **Category:** interactive binary / integration behavior
- **Question:** What contract does the `ttt` REPL exercise each round, and how does it wire history relative to `ApplyActionInPlace`?
- **Grounded answer:** The REPL prints round/player/last move, board, terminal status and scores, valid-action count, serialization debug lines, and augmentation debug lines. It parses user input through `ActionFromString` and compares string forms against current valid actions so `Action` need not define `operator==`. Before applying a chosen move, it pushes the current game into the `RingBuffer`; for Tic Tac Toe this is a no-op because `kHistoryLookback == 0`, but if lookback changed, the next round's serializer would see the previous state at history index 0.
- **Sources:** `memory/main_binary.md:11`, `memory/main_binary.md:33`, `memory/history_lookback.md:51`, `src/main.cc:117`, `src/main.cc:166`, `src/main.cc:303`.
- **Eval note:** Requires following an integration path through docs and `main.cc`.

### 12. Build and test topology

- **Category:** build/configuration
- **Question:** How is this project built and tested, including external dependencies, C++ standard, target graph, and preset differences?
- **Grounded answer:** The top-level project requires CMake 3.26, C++23, disables C++ extensions, fetches `shuyangsun/alpha-zero-api` at tag `v0.2.1`, and builds tests only when `BUILD_TESTING` is on. Presets define debug, release, debug-test, and release-test; release adds `-O3`, `-DNDEBUG`, LTO, section GC flags, and hidden visibility, while test presets inherit and enable `BUILD_TESTING`. Source modules are static libraries (`game_ttt`, `serializer_ttt`, `deserializer_ttt`, `augmentation_ttt`, `inference_ttt`, `train_ttt`) wired through `az_add_game_module`; unit tests link all game modules plus `GTest::gtest_main` and are registered with `gtest_discover_tests`.
- **Sources:** `CMakeLists.txt:1`, `CMakeLists.txt:14`, `CMakeLists.txt:29`, `CMakePresets.json:8`, `src/ttt/CMakeLists.txt:1`, `tests/unit/CMakeLists.txt:3`.
- **Eval note:** Tests cross-file retrieval over config rather than just C++ source.

## `/Users/shuyang/developer/alpha-zero/az-game-xiang-qi`

No session transcripts were present in the inspected tree, so all candidates are codebase/docs focused.

### 1. API contract and state shape

- **Category:** API contract / state shape
- **Question:** Why is `XqGame::kHistoryLookback` zero even though Xiang Qi needs threefold-repetition detection, and what fixed API ceilings follow from that choice?
- **Grounded answer:** The network treats Xiang Qi as Markov: repetition state lives inside `XqGame`, not in the engine-owned history buffer. The fixed contract is `kHistoryLookback = 0`, `kPolicySize = 90 * 90 = 8100`, `kMaxLegalActions = 104`, and `kMaxRounds = 300`, with the round cap bounding action and position-history arrays.
- **Sources:** `include/xq/game.h:114`, `memory/game_design.md:43`, `memory/history_lookback.md:39`.
- **Eval note:** Requires connecting API constants, memory design, and repetition strategy.

### 2. Canonical frame and policy sharing

- **Category:** canonical frame / policy sharing
- **Question:** How does the engine make equivalent Red-to-move and Black-to-move actions share the same policy-head slot?
- **Grounded answer:** Red uses the live board/action frame. For Black, `CanonicalBoard()` rotates the board 180 degrees and negates piece signs; `CanonicalAction()` rotates both cells. Serializer and deserializer scatter/gather probabilities at `PolicyIndex(CanonicalAction(a))`, so equivalent "own piece advances" moves land in the same slot for both sides.
- **Sources:** `include/xq/game.h:227`, `src/xq/game/state.cc:50`, `src/xq/serializer/serializer.cc:132`, `tests/unit/game_state.cc:85`.
- **Eval note:** Shallow search for `PolicyIndex` misses the canonicalization dependency.

### 3. Dense serializer/deserializer

- **Category:** dense serializer / deserializer
- **Question:** What is the dense neural-network state and policy-output layout, and how are illegal actions represented?
- **Grounded answer:** Dense state is 15 planes of 90 cells: planes 0-6 for current-player pieces, 7-13 for opponent pieces, and plane 14 all ones only when Red is to move. Policy output is `[z, p0..p8099]`; valid actions are scattered into canonical policy slots and every non-valid slot remains zero. The dense deserializer requires exactly `kPolicySize + 1` floats and gathers verbatim values for current valid actions.
- **Sources:** `memory/game_design_details/board_encoding.md:54`, `src/xq/serializer/serializer.cc:44`, `src/xq/serializer/serializer.cc:129`, `src/xq/deserializer/deserializer.cc:21`.
- **Eval note:** Tests whether retrieval can assemble layout from docs plus implementation.

### 4. Compact policy ABI

- **Category:** compact policy ABI
- **Question:** How does the compact transformer-oriented serializer align legal-action tokens with compact policy targets, and why is this ordering load-bearing?
- **Grounded answer:** Compact state is 195 tokens by 2 floats, or 390 floats: 90 board tokens, one repeat-counter token, and 104 legal-action tokens. Real action tokens are canonical `(from, to)` sorted ascending; padding uses `XqA{90,90}`. `CompactPolicyTargetBlob` uses the same sorted non-padding order, so row `i` of the compact policy head corresponds to input action token `i`. Changing sorting, padding, or valid-action ordering is a breaking checkpoint ABI change.
- **Sources:** `include/xq/serializer.h:18`, `memory/api_contract.md:95`, `memory/game_design_details/action_encoding.md:79`, `src/xq/serializer/serializer.cc:156`.
- **Eval note:** Requires cross-referencing API contract, serializer constants, and target blob behavior.

### 5. Repetition tracking

- **Category:** repetition tracking
- **Question:** How is threefold repetition tracked without serializer history, and what limitation does the snapshot constructor introduce?
- **Grounded answer:** The game maintains a running Zobrist hash over board pieces plus side-to-move, logs hashes per ply, and counts the current hash against valid prior slots; count >= 3 is a draw. Snapshot construction recomputes the current hash but marks older history invalid, so augmented/snapshot games cannot meaningfully detect historical repetition.
- **Sources:** `memory/game_design_details/repetition.md:8`, `src/xq/game/state.cc:68`, `src/xq/game/constructors.cc:95`, `tests/unit/serializer.cc:301`.
- **Eval note:** Good eval for whether retrieval distinguishes engine history from rule history.

### 6. Termination and scoring

- **Category:** termination / scoring
- **Question:** What terminal conditions are evaluated first, and how does that affect scoring when conditions overlap?
- **Grounded answer:** Missing generals or no legal move are handled before repetition and max-round draw. Checkmate and stalemate both score the side to move `-1` and opponent `+1`; threefold and max rounds score `0/0`. A checkmate position at or beyond `kMaxRounds` remains a win/loss, not a draw.
- **Sources:** `memory/game_rules_details/termination.md:8`, `src/xq/game/state.cc:99`, `src/xq/game/state.cc:121`, `tests/unit/game_state.cc:272`.
- **Eval note:** Requires priority reasoning, not just listing rules.

### 7. Legal action generation

- **Category:** legal action generation
- **Question:** What exact pipeline turns piece moves into legal actions, and what invariants does `ValidActionsInto()` promise?
- **Grounded answer:** If `IsOver()` is true it returns zero. Otherwise it emits pseudo-legal moves in cell-major, piece-specific deterministic order into caller storage, then filters in place by applying each candidate to scratch board and rejecting moves that leave own General in check or create Flying General. The result has no pass sentinel, is deterministic, and uses at most `kMaxLegalActions`.
- **Sources:** `include/xq/game.h:262`, `src/xq/game/action.cc:39`, `memory/game_design_details/action_encoding.md:64`, `tests/unit/game_action.cc:98`.
- **Eval note:** Forces retrieval over header contract, implementation, and test invariants.

### 8. Piece-rule edge cases

- **Category:** piece-rule edge cases
- **Question:** Which non-obvious movement blockers are explicitly implemented and tested for Elephant, Horse, Cannon, and Soldier?
- **Grounded answer:** Elephants move diagonal-2, cannot cross the river, and require the midpoint eye to be empty. Horses require the orthogonal leg cell to be empty. Cannons move like Chariots when not capturing but need exactly one screen to capture an enemy target. Soldiers move forward before crossing, gain sideways moves after crossing, never move backward, and never promote.
- **Sources:** `memory/game_rules_details/pieces.md:30`, `src/xq/game/internal.cc:245`, `src/xq/game/internal.cc:271`, `src/xq/game/internal.cc:329`, `tests/unit/game_action.cc:245`.
- **Eval note:** Multi-hop domain question across rules, move generators, and tests.

### 9. MCTS apply/undo hot path

- **Category:** MCTS apply/undo hot path
- **Question:** How does `ApplyActionInPlace`/`UndoLastAction` stay allocation-free while restoring captures correctly?
- **Grounded answer:** The game stores fixed-size `action_history_`, `position_history_`, validity flags, and `apply_undo_log_`. Captured pieces are packed into one byte: sign in bit 7 and magnitude in low bits. Apply updates board, player, round, Zobrist hash, action history, and undo log; undo reverses from those arrays. Invalid actions are not validated on this hot path.
- **Sources:** `include/xq/game.h:404`, `src/xq/game/action.cc:21`, `src/xq/game/action.cc:73`, `memory/mcts_constraints.md:25`, `tests/unit/game_action.cc:540`.
- **Eval note:** Checks retrieval of performance constraints and low-level undo mechanics.

### 10. Snapshot constructor and augmentation safety

- **Category:** snapshot constructor / augmentation safety
- **Question:** Why can a snapshot-constructed game expose `LastAction()` but still refuse to undo it?
- **Grounded answer:** The snapshot constructor can seed `action_history_[round-1]` from `last_action`, letting observers report it, but it records `kUndoUnavailable` because capture metadata and older history are unknown. `UndoLastAction()` returns without mutation when the action is no-action or undo metadata is unavailable.
- **Sources:** `include/xq/game.h:176`, `src/xq/game/constructors.cc:110`, `src/xq/game/action.cc:104`, `tests/unit/game_action.cc:827`.
- **Eval note:** Subtle behavior easily missed by keyword retrieval.

### 11. Augmentation symmetry

- **Category:** augmentation symmetry
- **Question:** What board symmetries does Xiang Qi support in this repo, and how is the supported symmetry applied to board, actions, and players?
- **Grounded answer:** Only left/right mirror across central file is used; rotations and vertical flips are rejected because river, palace, and orientation break them. `kOriginal = 0`, `kMirrorHorizontal = 1`; mirroring maps cell `(r,c)` to `(r,8-c)`, preserves piece signs and current player, mirrors `LastAction()` if present, and preserves legal-action counts.
- **Sources:** `include/xq/augmentation.h:11`, `memory/game_design.md:168`, `src/xq/augmentation/augmentation.cc:24`, `tests/unit/augmentation.cc:62`.
- **Eval note:** Requires knowing both negative design decisions and actual transform mechanics.

### 12. Inference/training augmentation

- **Category:** inference/training augmentation
- **Question:** How do inference and training augmenters use inverse action transforms differently?
- **Grounded answer:** Inference builds a lookup from original `PolicyIndex` to original valid-action slot, then for each variant inverse-maps variant actions back to original actions and averages values/probabilities. Training instead builds augmented `(game,target)` pairs: for each variant action, inverse-map to the original action, gather the original `target.pi` by policy index, and preserve `target.z`.
- **Sources:** `memory/augmentation_strategy.md:75`, `src/xq/inference/inference.cc:21`, `src/xq/train/train.cc:14`, `memory/api_contract.md:130`.
- **Eval note:** Tests whether retrieval can compare two similar but distinct augmentation contracts.

### 13. Human/action I/O

- **Category:** human/action I/O
- **Question:** What notation does action string I/O use, and where do C++ and TypeScript intentionally mirror each other?
- **Grounded answer:** Action notation is `<from_col><from_row>-<to_col><to_row>` with columns `a..i` and rows `0..9`, where row 0 is Red's back rank. C++ trims whitespace and lowercases columns; out-of-range source and destination cells produce distinct typed errors. `gui/src/kit.ts` reimplements the pure codec for GameKit use with the same row-major `row * 9 + col` mapping.
- **Sources:** `memory/game_design_details/action_encoding.md:45`, `src/xq/game/string_conv.cc:91`, `tests/unit/game_string_conv.cc:55`, `gui/src/kit.ts:106`.
- **Eval note:** Spans engine docs, C++ parser behavior, tests, and GUI kit compatibility.

### 14. GUI/WASM integration

- **Category:** GUI/WASM integration
- **Question:** How does the browser GUI avoid duplicating game rules while still protecting the C++ engine from fabricated invalid moves?
- **Grounded answer:** The GUI loads `xq.js`/`xq.wasm` built from the C++ engine; the Embind shim forwards observers and exposes `applyValidActionByIndex`, which looks up the action from `ValidActionsInto()` before applying it. The TypeScript wrapper accepts an `{from,to}` action only if it matches the current snapshot's `validActions`, then calls the indexed WASM method and refreshes copied board snapshots.
- **Sources:** `memory/gui_design.md:25`, `src/wasm/bindings.cc:68`, `src/wasm/bindings.cc:82`, `gui/src/engine/xq-game.ts:41`.
- **Eval note:** Requires cross-language understanding of safety boundaries.

### 15. GameKit/server reuse

- **Category:** GameKit/server reuse
- **Question:** What state does the reusable GameKit send to the upstream AlphaZero server, and why is there no history field?
- **Grounded answer:** `encodeSnapshotForServer` sends a plain JSON-serializable `{ board, current_player, current_round }`; it copies the `Int8Array` into `number[]` because typed arrays stringify poorly. There is no history field because `historyLookback` is 0 and Xiang Qi's required repetition state is internal to `XqGame`.
- **Sources:** `memory/gui_design.md:451`, `memory/gui_design.md:481`, `gui/src/kit.ts:100`, `gui/src/kit.test.ts:48`.
- **Eval note:** Validates retrieval over docs, TypeScript implementation, and tests.

### 16. Build and CI workflow

- **Category:** build and CI workflow
- **Question:** What are the native, test, and WASM build paths, and how does CI smoke-test the binary?
- **Grounded answer:** The project is C++23, pins `alpha-zero-api` via `ALPHA_ZERO_API_GIT_TAG = v0.2.1`, and keeps `BUILD_TESTING` off unless a test preset enables it. `debug-test` and `release-test` presets enable tests. WASM builds only target `xq_wasm`, uses Emscripten/Embind, and copies `xq.js`/`xq.wasm` into `gui/public/wasm`. CI configures and builds both test presets, runs the REPL binary with EOF, then runs `ctest`.
- **Sources:** `CMakeLists.txt:9`, `CMakePresets.json:30`, `src/wasm/CMakeLists.txt:1`, `gui/package.json:9`, `.github/workflows/ci.yml:27`.
- **Eval note:** Tests retrieval across CMake, package scripts, and CI rather than source code alone.

## `/Users/shuyang/developer/website`

This repo has both application code/docs and session transcripts, so the set is split evenly between codebase questions and session/history questions.

### 1. Shirt AI routing and consent

- **Category:** codebase / AI routing
- **Question:** How does `generateShirtThought` choose between Cloudflare AI Gateway, direct Google MaaS, and OpenAI for shirt thoughts versus submitted responses, and how does consent affect telemetry?
- **Grounded answer:** The function derives an observability profile from consent: `analytics` enables full telemetry, `essential` keeps metrics-only, and `none` disables telemetry. For Google, `none` uses direct Google MaaS; `analytics` and `essential` use AI Gateway, but only `analytics` collects logs/payloads. OpenAI is added as a parallel racer only when an API key exists. Response mode uses stronger defaults and larger budgets (`gpt-5.1`, `gemini-3-flash-preview`, lower temperature), while thought mode uses cheaper/faster defaults (`gpt-4.1-mini`, `GCP_AP_MODEL_ID`, higher temperature). The race returns the first successful parsed non-empty output and aborts slower candidates; fast errors or empty outputs do not win. Langfuse spans include prompt input/output only for full analytics consent.
- **Sources:** `shuyang-website/src/lib/generate-shirt-thought.ts:166`, `shuyang-website/src/lib/generate-shirt-thought.ts:362`, `shuyang-website/src/lib/generate-shirt-thought.ts:455`, `shuyang-website/src/lib/generate-shirt-thought.ts:524`, `shuyang-website/src/lib/generate-shirt-thought.ts:911`, `shuyang-website/src/lib/generate-shirt-thought.ts:1199`, `shuyang-website/src/lib/generate-shirt-thought.ts:1358`, `shuyang-website/src/lib/thought-ai.md:11`.
- **Eval note:** A shallow search for "OpenAI" or "consent" misses the interaction between mode, provider race, AI Gateway logging, direct MaaS, and Langfuse privacy gates.

### 2. AI Search retrieval bridge

- **Category:** codebase / retrieval
- **Question:** What exact AI Search retrieval settings does the app use, how are result objects normalized into GitHub citations, and why is `/github/search` unavailable in production?
- **Grounded answer:** The app uses the `WRITING_SEARCH` binding with hybrid retrieval enabled, RRF ranking, keyword `and` matching, a score threshold defaulting to `0.4`, query rewriting disabled, reranking enabled with `@cf/baai/bge-reranker-base`, and cache disabled. Max results are clamped between 1 and 50. Result keys under `github/v1/repos/...` are parsed into `repoKey`, repo-relative path, and GitHub blob URLs while preserving normalized scores and text chunks. The `/github/search` route is dev-only and returns 404 outside Vite dev mode to avoid exposing a sensitive exploratory search endpoint in production.
- **Sources:** `shuyang-website/src/lib/retrieval.server.ts:9`, `shuyang-website/src/lib/retrieval.server.ts:43`, `shuyang-website/src/lib/retrieval.ts:83`, `shuyang-website/src/lib/retrieval.ts:147`, `shuyang-website/src/routes/github.search.ts:12`, `shuyang-website/src/lib/retrieval.md:9`, `shuyang-website/src/lib/retrieval.md:28`.
- **Eval note:** Tests whether retrieval can connect config, route safety, key parsing, and citation construction across multiple files.

### 3. Hidden feature flag throttling

- **Category:** codebase / feature flags
- **Question:** How does the `higher-inner-thought-limit` flag give signed-in users faster thoughts without exposing the flag value, audience, or throttle profile to the browser?
- **Grounded answer:** Feature flags live in R2 under `flags/v1/` and are loaded only server-side with a 60-second cache and fail-closed behavior. The seed config defines `higher-inner-thought-limit` with default `false` and a signed-in audience. Resolution applies default, then audience rules, then signed-in user overrides keyed by the first 16 hex chars of `sha256(user.id)`. The browser never receives config or profile names; it only sees either a generated thought or a throttled response. Server throttle profiles use `normal` delays of 500 ms minimum idle / 1500 ms unfinished sentence idle and `higher` delays of 250 ms / 500 ms.
- **Sources:** `shuyang-website/src/lib/feature-flags.md:3`, `shuyang-website/src/lib/feature-flags.md:22`, `shuyang-website/src/lib/feature-flags.server.ts:16`, `shuyang-website/src/lib/feature-flags.server.ts:45`, `shuyang-website/src/lib/feature-flags.server.ts:180`, `shuyang-website/src/lib/inner-thought-throttle.server.ts:31`, `shuyang-website/src/lib/inner-thought-throttle.server.ts:69`, `docs/plan/feature-flags-2026-06-02.md:73`.
- **Eval note:** Requires combining config semantics, privacy constraints, auth-derived user hashes, and runtime throttling behavior.

### 4. GitHub mirror safety model

- **Category:** codebase / GitHub mirror
- **Question:** If an allowlisted repository is removed or `includeReadme` is disabled, why should stale R2 objects not be exposed, and why does the Worker avoid crawling Markdown during requests?
- **Grounded answer:** Runtime reads the R2 index through a short isolate cache, then filters results through the current committed allowlist. README routes validate the repo key, require the repo to still be in the current index, and reject repos without `readmeUrl`. The Worker only handles lightweight metadata and README refreshes, serving the last snapshot if GitHub fails. Recursive Markdown mirroring is intentionally a manual CLI job that writes files, manifests, README aliases, and index objects under `github/v1/`. The docs warn that mirrored private content is public once selected for mirroring.
- **Sources:** `shuyang-website/src/lib/github-mirror.md:3`, `shuyang-website/src/lib/github-mirror.md:30`, `shuyang-website/src/lib/github-mirror.md:53`, `shuyang-website/src/routes/github.readme.$.ts:19`, `tools/github-mirror/OVERVIEW.md:16`, `docs/plan/github-repo-mirror-2026-06-02.md:34`, `docs/plan/github-repo-mirror-2026-06-02.md:136`.
- **Eval note:** A good RAG system must distinguish stored objects from the current exposure path and understand the CLI/runtime split.

### 5. Avatar portrait pipeline

- **Category:** codebase / avatar generation
- **Question:** What happens when a signed-in user requests a generated avatar portrait, including missing OAuth photos, category classification, cache keys, consent routing, and privacy guarantees?
- **Grounded answer:** The client-safe wrapper calls a server function only after sign-in and consent. The server reads the Kinde session and returns `{ url: null }` for anonymous users. It resolves either the OAuth photo or an initials-based fallback identity, hashes the user ID and photo/source, checks R2 cache candidates, classifies the source into real person, artwork, or no-person/initials, loads the hero style reference, generates a 512 PNG, writes it to R2, and serves it through `/avatar/$`. Cache keys include user hash, photo hash, category alias, hero version, and prompt version. Source OAuth photos are not stored, Langfuse does not receive image bytes, AI Gateway payload logging is disabled, and `none` consent uses direct Vertex rather than Gateway.
- **Sources:** `shuyang-website/src/lib/generate-avatar-portrait.md:6`, `shuyang-website/src/lib/generate-avatar-portrait.md:34`, `shuyang-website/src/lib/generate-avatar-portrait.md:57`, `shuyang-website/src/lib/generate-avatar-portrait.ts:25`, `shuyang-website/src/lib/generate-avatar-portrait.server.ts:1296`, `shuyang-website/src/routes/avatar.$.ts:15`, `docs/plan/avatar-style-transfer-2026-05.md:14`, `docs/plan/avatar-style-transfer-2026-05.md:351`.
- **Eval note:** Tests cross-file understanding of auth, caching, privacy, generated assets, and route serving.

### 6. Phaser figure and shirt text layering

- **Category:** codebase / frontend rendering
- **Question:** Why is the forearm cutout rendered as a DOM layer instead of entirely inside Phaser, and how does the pointing pose keep shirt text aligned?
- **Grounded answer:** Phaser owns the base figure canvas, but a single canvas cannot sandwich part of the arm between DOM text layers. The base figure sits below the shirt text; the forearm cutout is a DOM image layer above resting text but below reacted text. Pointing uses an analogous cutout. The figure stage reports bob offsets and print geometry, while `registerPrintShift` computes the pointing pose's torso shift so the shirt print can move left and stay visually aligned. When `hero_point` is regenerated, Sapiens segmentation, arm cutout, head geometry, and trace outputs must be regenerated to avoid doubled arms or clipped fingers.
- **Sources:** `shuyang-website/src/components/OVERVIEW.md:10`, `shuyang-website/src/components/phaser-figure-stage.tsx:108`, `shuyang-website/src/components/interactive-landing.tsx:209`, `shuyang-website/src/components/interactive-landing.tsx:246`, `shuyang-website/src/styles.css:427`, `shuyang-website/src/styles.css:474`, `shuyang-website/src/styles.css:505`, `shuyang-website/src/lib/figure-align.ts:202`, `docs/research/sapiens-poc/OVERVIEW.md:30`.
- **Eval note:** Requires reasoning about rendering layers, generated geometry, CSS z-indexes, and asset maintenance.

### 7. Cookie consent storage and API boundaries

- **Category:** codebase / consent
- **Question:** How does the cookie consent system persist choices in production versus development, avoid initial landing flash, and enforce different API boundaries for analytics, essential, and no-cookie modes?
- **Grounded answer:** Production stores consent in `localStorage`; development uses `sessionStorage` with a boot ID so local testing can reset per dev session. Consent payloads include tier and timestamp. Inline bootstrap code redirects first-time visitors from `/` to `/cookies` and sets document state early for returning users to avoid a flash. Analytics consent records Langfuse consent and sends Gateway logs plus visitor ID. Essential keeps operational routing but suppresses Gateway payload collection and uses metrics-only Langfuse. No-cookie mode skips Langfuse, visitor IDs, and Gateway, routing direct to provider APIs.
- **Sources:** `shuyang-website/src/lib/consent.md:7`, `shuyang-website/src/lib/consent.md:23`, `shuyang-website/src/lib/consent.md:45`, `docs/plan/cookie-consent-2026-05.md:34`, `docs/plan/cookie-consent-2026-05.md:111`, `docs/plan/cookie-consent-2026-05.md:137`.
- **Eval note:** Evaluates whether retrieval can connect product UX, storage decisions, boot behavior, and backend privacy constraints.

### 8. Retrieval-agent status and remaining gaps

- **Category:** codebase / retrieval roadmap
- **Question:** As of the current docs, what parts of the retrieval-agent plan are implemented, and what remains pending for evals, citations, and agentic retrieval?
- **Grounded answer:** Implemented work includes the Cloudflare AI Search instance, `WRITING_SEARCH` binding, search-only bridge, dev `/github/search` route, normalized GitHub chunk metadata, inner-thought context injection, and submitted response mode using the same retrieval path. The docs still mark citations/source display, explicit Langfuse retrieval spans, agentic retrieval orchestration, a golden eval set, and Phase 1 evaluation harness work as pending. One smoke note says the `github mirror` query returned chunks, while session history records that `retrieval agent` returned zero because the index predated the newest local plan.
- **Sources:** `docs/plan/retrieval-agent-2026-06.md:6`, `docs/plan/retrieval-agent-2026-06.md:59`, `docs/plan/retrieval-agent-2026-06.md:329`, `shuyang-website/src/lib/retrieval.md:3`, `shuyang-website/src/lib/retrieval.md:47`, `llm-sessions-history/2026-06-05/0109-codex-ai-search-retrieval-bridge.md:90`.
- **Eval note:** Forces the evaluator to distinguish shipped code from roadmap items and historical indexing caveats.

### 9. Session export conventions

- **Category:** session history / repository process
- **Question:** How are session transcripts organized, what redaction/export conventions apply, and why does the repo prefer exporting sessions before commit?
- **Grounded answer:** Session transcripts live under `llm-sessions-history/<YYYY-MM-DD>/<NNNN>-<vendor>-<short-name>.md` with globally increasing four-digit indexes. Each file records metadata, summary, transcript, and outcome. Daily overview files summarize sessions for that date, and the root overview provides a chronological index. Sensitive material such as tokens, secret values, and account identifiers must be redacted. The repo convention is to export sessions before committing so the transcript can be included in the same change that records the work.
- **Sources:** `llm-sessions-history/OVERVIEW.md:1`, `llm-sessions-history/OVERVIEW.md:19`, `llm-sessions-history/OVERVIEW.md:24`.
- **Eval note:** Tests whether RAG can recover repository-specific process rules rather than application behavior.

### 10. Cookie consent rollout history

- **Category:** session history / product implementation
- **Question:** Reconstruct the two-step cookie consent rollout from the UI gate to backend no-cookie routing, including the later correction around essential telemetry.
- **Grounded answer:** Session 0044 implemented the first-time visitor cookie picker: chocolate largest, all cookies below the art, desktop/mobile responsive layout, legal hover/click behavior, no shirt input on the picker, and returning chocolate users going straight to the interactive landing. It split the landing into a gate and interactive experience, added consent storage/provider/bootstrap, tests, CSS, and docs, while backend routing was still deferred. Session 0045 then implemented no-cookie backend routing: no-cookie sends direct MaaS calls with no Langfuse/Gateway and no visitor ID; analytics keeps visitor IDs. After user clarification, essential was corrected to metrics-only Langfuse while still suppressing payload logs, and no-cookie continued to bypass both Langfuse and Gateway.
- **Sources:** `llm-sessions-history/2026-05-25/0044-codex-cookie-consent-gate.md:15`, `llm-sessions-history/2026-05-25/0044-codex-cookie-consent-gate.md:54`, `llm-sessions-history/2026-05-25/0044-codex-cookie-consent-gate.md:100`, `llm-sessions-history/2026-05-25/0045-codex-no-cookie-direct-llm.md:15`, `llm-sessions-history/2026-05-25/0045-codex-no-cookie-direct-llm.md:63`.
- **Eval note:** Requires chronological synthesis across two transcripts and product/code docs.

### 11. GitHub mirror R2 sync run

- **Category:** session history / data sync
- **Question:** What did the 2026-06-04 GitHub mirror R2 sync actually upload, what behavior did it clarify between offline sync and Worker runtime, and what verification caveat remained?
- **Grounded answer:** The session clarified that full Markdown mirroring is an offline/manual CLI sync, while the Worker remains lightweight and only handles metadata/README read-through. The remote sync uploaded data for four repos, including 317 Markdown file objects, four manifests, four README aliases, and the index. The wrapper command ended nonzero because of a zsh read-only variable/status issue, but logs showed no upload errors. A direct R2 readback verification remained incomplete because the 1Password token access timed out.
- **Sources:** `llm-sessions-history/2026-06-04/0102-codex-github-mirror-r2-sync-run.md:15`, `llm-sessions-history/2026-06-04/0102-codex-github-mirror-r2-sync-run.md:36`, `llm-sessions-history/2026-06-04/0102-codex-github-mirror-r2-sync-run.md:80`.
- **Eval note:** Captures a subtle operational distinction and a partial verification caveat likely missed by keyword-only retrieval.

### 12. OpenAI shirt-thought racer

- **Category:** session history / AI provider routing
- **Question:** Why was OpenAI added as a parallel racer, why was `gpt-4.1-mini` chosen for thoughts, and what happened when trying to upload the OpenAI key to Cloudflare?
- **Grounded answer:** The user requested OpenAI to run in parallel with GCP and to use the fastest valid result. The implementation chose `gpt-4.1-mini` for low-latency, non-reasoning shirt thoughts. The race starts GCP and OpenAI together, accepts only the first successful parsed non-empty output, aborts slower candidates, falls back to GCP-only without an OpenAI key, and attributes only the winning provider to Langfuse under existing consent rules. The user later added the key locally; setup scripts exported it, but a Cloudflare secret upload failed due token scope, and work stopped after the user objected to more attempts. The secret was not printed.
- **Sources:** `llm-sessions-history/2026-06-04/0104-codex-openai-shirt-thought-racer.md:15`, `llm-sessions-history/2026-06-04/0104-codex-openai-shirt-thought-racer.md:26`, `llm-sessions-history/2026-06-04/0104-codex-openai-shirt-thought-racer.md:44`, `llm-sessions-history/2026-06-04/0104-codex-openai-shirt-thought-racer.md:63`.
- **Eval note:** Requires historical reasoning about model choice, implementation details, and credential-handling boundaries.

### 13. AI Search setup to retrieval bridge

- **Category:** session history / retrieval setup
- **Question:** What manual Cloudflare AI Search settings were recommended before code integration, and what changed once the retrieval bridge was implemented?
- **Grounded answer:** The setup session recommended a Cloudflare AI Search instance scoped to Markdown under the GitHub mirror prefix, Workers smart embeddings, 1024-token chunks with 10% overlap, hybrid retrieval, RRF, keyword `AND`, Porter stemming, query rewriting off, max 10 results, threshold `0.4`, reranking on, and cache off while tuning. After the bridge session, tokens were split between R2 and Workers AI Search variables, endpoint validation succeeded, known search probes returned results, and the dev route returned three normalized chunks with repo key, path, GitHub URL, score, and text preview. The `retrieval agent` probe returned zero because the index predated the newest local plan.
- **Sources:** `llm-sessions-history/2026-06-04/0108-codex-ai-search-setup-docs.md:21`, `llm-sessions-history/2026-06-04/0108-codex-ai-search-setup-docs.md:41`, `llm-sessions-history/2026-06-04/0108-codex-ai-search-setup-docs.md:57`, `llm-sessions-history/2026-06-04/0108-codex-ai-search-setup-docs.md:79`, `llm-sessions-history/2026-06-05/0109-codex-ai-search-retrieval-bridge.md:69`.
- **Eval note:** Tests retrieval over operational setup, env-var naming, query tuning, and smoke-test interpretation.

### 14. Inner-thought AI Search integration

- **Category:** session history / prompt augmentation
- **Question:** How did session 0110 satisfy the requirement that shirt thoughts preserve the old prompt when no search results exist, but include search context when results are available?
- **Grounded answer:** The implementation added `buildUserPrompt`, `buildSearchContextForThought`, and `searchContextForThought`. Retrieval runs after server-side throttle and is best-effort; failures or empty chunks return `null`, preserving the old prompt shape. When chunks exist, they are inserted as source-labeled snippets and the same augmented prompt is sent to both GCP and OpenAI. Tests covered old-prompt behavior with null context, appended context with sources, empty chunk fallback, truncation, and retrieval failure. Validation included unit tests, lint/check/build, dev `/github/search` smoke, and browser generation.
- **Sources:** `llm-sessions-history/2026-06-05/0110-codex-ai-search-inner-thought.md:17`, `llm-sessions-history/2026-06-05/0110-codex-ai-search-inner-thought.md:25`, `llm-sessions-history/2026-06-05/0110-codex-ai-search-inner-thought.md:52`, `shuyang-website/src/lib/generate-shirt-thought.ts:198`, `shuyang-website/src/lib/generate-shirt-thought.ts:256`.
- **Eval note:** Evaluates a nuanced prompt-preservation requirement that spans transcript, implementation, and tests.

### 15. Submitted shirt response mode

- **Category:** session history / interaction design
- **Question:** How did the repo turn Enter and mobile blur into a factual submitted response path distinct from live thoughts, and why did the model defaults change?
- **Grounded answer:** Session 0111 added a two-mode generation flow: live thoughts remain short and throttled, while submitted responses are triggered by Enter or mobile blur, skip the inner-thought throttle, use more AI Search context, use a factual response prompt, and get a larger token budget. Shift/Alt/Meta/Ctrl Enter do not submit. The response appears as left-side marginalia on desktop and at the bottom on mobile. Defaults changed to stronger response models: OpenAI `gpt-5.1` and Google `gemini-3-flash-preview`, with environment overrides preserved.
- **Sources:** `llm-sessions-history/2026-06-05/0111-codex-shirt-response-submit.md:9`, `llm-sessions-history/2026-06-05/0111-codex-shirt-response-submit.md:19`, `shuyang-website/src/lib/generate-shirt-thought.ts:23`, `shuyang-website/src/lib/generate-shirt-thought.ts:53`, `shuyang-website/src/lib/generate-shirt-thought.ts:238`, `shuyang-website/src/lib/generate-shirt-thought.ts:1338`.
- **Eval note:** Requires distinguishing two user-facing generation modes that share infrastructure but differ in prompt, context, throttle, and UI behavior.

### 16. Hero point prompting and artifact fix

- **Category:** session history / image prompting and asset pipeline
- **Question:** What did the `hero_point` sessions learn about composite locking and prompt design, and how did the artifact-fix prompt/spec change to remove the hidden old arm and missing fingertip?
- **Grounded answer:** The first hero-point pipeline session diagnosed that the old point asset was a full redraw and built a composite-lock strategy so only the pointing arm region changed. It fixed a sharp-feather mask bug by using JS box blur, kept the alpha bounding box byte-identical, and selected a candidate where only about 12% of figure pixels differed. Later, the artifact-fix session found the fingertip existed in source but was hidden by rendering/cutout issues, and that an old arm was baked into the generated image. Local patch repairs were rejected. After user approval, the prompt relaxed pixel locking around the old-arm region, explicitly required removing every old-arm remnant, allowed local redraw of shirt/lap pixels, required a complete fingertip, widened the ROI, and lowered locked-region fidelity weight. Candidate F was selected, copied to `hero_point`, and the arm cutout was rebuilt.
- **Sources:** `llm-sessions-history/2026-06-01/0085-claude-art-pipeline-hero-point.md:12`, `llm-sessions-history/2026-06-01/0085-claude-art-pipeline-hero-point.md:40`, `llm-sessions-history/2026-06-01/0085-claude-art-pipeline-hero-point.md:64`, `llm-sessions-history/2026-06-01/0088-codex-hero-point-artifact-fix.md:10`, `llm-sessions-history/2026-06-01/0088-codex-hero-point-artifact-fix.md:31`, `llm-sessions-history/2026-06-01/0088-codex-hero-point-artifact-fix.md:54`, `prompts/20260602-hero-point-artifact-fix.md:3`, `tools/art-pipeline/specs/hero-point-artifact-fix.json:8`, `tools/art-pipeline/specs/hero-point-artifact-fix.json:27`, `docs/research/sapiens-poc/OVERVIEW.md:30`.
- **Eval note:** High-value historical prompt retrieval item because it requires connecting visual failure analysis, prompt changes, scoring weights, and downstream asset regeneration.

## Next Phase Notes

- Convert this candidate set into harness-owned structured records instead of scoring directly from this plan.
- Preserve code and natural-language/history splits: code questions should score against source/config/test corpora, while session/history questions should score against docs and transcript corpora.
- Use doc/code consistency traps as hard cases: stale replay checkpoint schema, API softmax drift, retrieval-agent implemented-vs-pending status, and source-map/RAG benchmark interpretation.
- Prefer multi-relevant qrels for answers spanning docs, implementation, and tests. Many of these questions intentionally require more than one relevant file.
