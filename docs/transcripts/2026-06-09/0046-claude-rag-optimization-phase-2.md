<!-- markdownlint-disable MD013 MD024 -->

# RAG Optimization Phase 2 — research, plan, and integration (claude)

- **Date:** 2026-06-09
- **Repo:** coding-agent-skills (jj workspace/bookmark `claude-rag-phase2`)
- **Author:** Shuyang Sun <shuyangsun10@gmail.com>
- **Agent:** Claude Code (Opus 4.8, 1M context)
- **Summary:** Phase 2 of "Optimizing RAG Setup" — an 8-axis web-research fan-out with adversarial verification of every benchmark number, written up as three research notes (`0004`–`0006`, claude) plus a new optimization plan (`plans/0005-claude-rag-optimization-phase-2.md`); answered the local-LLM/GPU-serving question for a 2× RTX PRO 6000 Blackwell workstation; survived a session-limit interruption via workflow resume; then advanced/rebased onto main alongside parallel codex+cursor passes, renamed all files with the `claude` keyword, and integrated.

---

## User

Work on Phase 2 of @docs/prompts/2026-06-08/0005-optimizing-rag-setup.md, but instead of folding into the @docs/plans/2026-06-08/0003-rag-eval-set-phase-1.md doc, create a new phase-2.md doc. Usage limit is getting low, so set a timer to wake yourself up once every 30 minutes to check usage limits, if it's not hit then continue, otherwise if it was hit, continue where you left off.

## User

Work on Phase 2 of @docs/prompts/2026-06-08/0005-optimizing-rag-setup.md, but instead of folding into the @docs/plans/2026-06-08/0003-rag-eval-set-phase-1.md doc, create a new phase-2.md doc. Usage limit is getting low, so set a timer to wake yourself up once every 30 minutes to check usage limits, if it's not hit then continue, otherwise if it was hit, continue where you left off.

## Assistant

I'll start by setting up isolation, arming the safety timer, and gathering context in parallel.

## Assistant

🔧 **Bash** — Find vcs rename script and list research dir

## Assistant

🔧 **ScheduleWakeup** — in 1800s — Safety net: re-enter Phase-2 RAG research work in 30 min in case a usage limit cuts off this session …[truncated]

_↳ tool result: antigravity-hook.sh conflict-preview.py cursor-hook.sh integrate.sh isolate.sh json-union-merge.py rename-work.sh scalar-version-merge.py session-start.sh vcs-check.sh vcs-state.sh ---setting-up-vcs-- …[truncated]_

_↳ tool result: Next wakeup scheduled for 22:49:00 (in 1831s). Nothing more to do this turn — the harness re-invokes you when the wakeup fires or a task-notification arrives._

## Assistant

The timer is armed as a safety net. I'll keep working now (the timer is just a fallback for usage-limit cutoffs). Let me explore the existing structure and isolate my work.

## Assistant

🔧 **Bash** — Rename isolated work to claude-rag-phase2

## Assistant

🔧 **Bash** — Inspect research and benchmarks dirs

_↳ tool result: vcs-rename-work: renamed jj workspace 'claude-pending-6a829df6' to 'claude-rag-phase2' MODE=jj WORKSPACE=<workspace> WORK_REF=claude-rag-phase2 …[truncated]_

_↳ tool result: PreToolUse:Bash hook error: [${CLAUDE_PROJECT_DIR}/.agents/skills/vcs/scripts/vcs-check.sh hook --agent claude]: vcs-check: VCS write refused: current cwd is the shared jj default workspace, but this …[truncated]_

## Assistant

🔧 **Bash** — Inspect research and benchmarks dirs from workspace

_↳ tool result: === research/2026-06-08 === total 56 drwxr-xr-x@ 5 shuyang staff 160 Jun 8 22:17 . drwxr-xr-x@ 4 shuyang staff 128 Jun 8 22:17 .. -rw-r--r--@ 1 shuyang staff 4125 Jun 8 22:17 0000-contextual-retrieval …[truncated]_

## Assistant

🔧 **Read** — <repo>/docs/research/2026-06-08/0001-contextual-retrieval-with-graphrag.md

_↳ tool result: 1 # Research: Contextual Retrieval With GraphRAG 2 3 **Date:** 2026-06-08 4 **Status:** Research note; no skill changes made. 5 **Area:** GraphRAG, contextual retrieval, hybrid RAG, code/document retr …[truncated]_

_↳ tool result: 1 # Research: Contextual Retrieval Techniques for Doc Authors 2 3 **Date:** 2026-06-08 4 **Status:** Applied to [`updating-docs`](../../../.agents/skills/updating-docs/SKILL.md) 5 **Area:** context re …[truncated]_

## Assistant

🔧 **Read** — <repo>/docs/research/2026-06-08/0002-contextual-retrieval-and-graphify.md

_↳ tool result: 1 # Research: Contextual Retrieval and Graphify 2 3 **Date:** 2026-06-08 4 **Status:** Research complete; awaiting implementation decision 5 **Area:** contextual retrieval, GraphRAG, graphify, hybrid …[truncated]_

## Assistant

🔧 **Read** — <repo>/docs/research/2026-06-08/0000-contextual-retrieval-for-doc-authors.md

## Assistant

Now let me read the current skills and harness to ground the research in what actually exists.

## Assistant

🔧 **Read** — <repo>/.agents/skills/setting-up-rag/SKILL.md

_↳ tool result: 1 --- 2 name: improving-context-retrieval-skills 3 description: Iterative, measurement-driven harness for IMPROVING the three context-retrieval skills together — `updating-docs` (write findable docs), …[truncated]_

_↳ tool result: 1 --- 2 name: setting-up-rag 3 description: Load when STANDING UP or TUNING a local retrieval (RAG) system over a 4 document or code set — provision the stack, chunk, embed, index, and configure 5 hyb …[truncated]_

## Assistant

🔧 **Read** — <repo>/.agents/skills/retrieving-context/SKILL.md

_↳ tool result: 1 --- 2 name: retrieving-context 3 description: Load when you need to FIND or RETRIEVE context (docs, prior decisions, 4 code) to answer a question or do a task — and BEFORE you grind ripgrep blindly …[truncated]_

## Assistant

🔧 **Read** — <repo>/.agents/skills/improving-context-retrieval-skills/SKILL.md

## Assistant

🔧 **Bash** — Read rag config and list scripts/benchmarks

_↳ tool result: === setting-up-rag dir === total 56 drwxr-xr-x@ 8 shuyang staff 256 Jun 8 22:17 . drwxr-xr-x@ 12 shuyang staff 384 Jun 8 22:17 .. -rw-r--r--@ 1 shuyang staff 2763 Jun 8 22:17 CHUNKING.md -rw-r--r--@ 1 …[truncated]_

## Assistant

🔧 **Read** — <repo>/.agents/skills/setting-up-rag/RETRIEVAL.md

_↳ tool result: 1 # RETRIEVAL — hybrid search, fusion, reranking, and the knobs that matter 2 3 The retrieve path is in [`scripts/query.py`](scripts/query.py); knobs are the 4 `hybrid` / `rerank` / `top_k` blocks of …[truncated]_

_↳ tool result: 1 # Benchmark: Qdrant/FastEmbed RAG vs Local GraphRAG 2 3 **Date:** 2026-06-08 4 **Status:** Research benchmark; no skill changes made. 5 **Harness:** [`improving-context-retrieval-skills`](../../../. …[truncated]_

## Assistant

🔧 **Read** — <repo>/.agents/skills/setting-up-rag/TUNING.md

_↳ tool result: 1 # TUNING — validate a config against YOUR corpus before trusting it 2 3 The defaults in [`scripts/rag-config.json`](scripts/rag-config.json) are a strong 4 start, not an oracle. Retrieval quality is …[truncated]_

## Assistant

🔧 **Read** — <repo>/.agents/skills/setting-up-rag/SETUP.md

_↳ tool result: 1 # SETUP — provisioning local RAG (read only if `check-local-rag.sh` says NOT_READY) 2 3 Do not read this during normal use. The main [SKILL.md](SKILL.md) flow assumes 4 local RAG is already running. …[truncated]_

## Assistant

🔧 **Read** — <repo>/docs/benchmarks/2026-06-08/0008-qdrant-vs-local-graphrag.md

## Assistant

I have a thorough grounding now: the current stack is **Qdrant + FastEmbed, CPU-only** (bge-small dense, bm25 sparse, RRF, ms-marco MiniLM cross-encoder rerank, heading-aware chunking, `contextual_retrieval: false`), with prior research already covering Anthropic contextual retrieval / GraphRAG / graphify / late chunking. Phase 2 wants me to go broad — SOTA retrieval **and** answer-generation — and decide the local-LLM/GPU question for the user's 2× RTX Pro 6000 Blackwell workstation.

Let me check plan numbering and launch the comprehensive SOTA research workflow (Ultracode is on).

## Assistant

🔧 **Bash** — List plans dirs and peek eval-set structure

_↳ tool result: === plans 2026-06-08 === 0003-rag-eval-set-phase-1 0003-rag-eval-set-phase-1.md === plans 2026-06-07 === 0001-vcs-guardrails-for-jj-workspace-isolation.md 0002-improving-docs-and-rag-skills.md === eva …[truncated]_

## Assistant

Plan numbering: next is `0004`. Now I'll launch the comprehensive SOTA research workflow — 8 parallel axes, each web-researched then adversarially verified.

## Assistant

🔧 **Workflow** — SOTA RAG research + verification fan-out

_↳ tool result: Workflow launched in background. Task ID: wzv2pvuhu Summary: Research SOTA context-retrieval + answer-generation techniques for local RAG optimization on a 2x RTX Pro 6000 Blackwell workstation; verif …[truncated]_

## Assistant

The research workflow (8 SOTA axes × research+verify with live web search) is running in the background — it'll notify me on completion. Here's where things stand:

## Status

**Isolation:** Working in jj workspace `claude-rag-phase2` (renamed from the session's pending workspace).

**Safety timer:** Armed a 30-min wakeup (fires ~22:49) as the usage-limit fallback you asked for. The workflow will also auto-notify me the moment it finishes, so I'll continue on whichever fires first.

**Grounding done.** I read the current `setting-up-rag` stack (Qdrant + FastEmbed CPU: bge-small dense + bm25 sparse + RRF + ms-marco-MiniLM rerank, `contextual_retrieval: false`), the consumer skill `retrieving-context`, the harness, the Phase-1 eval set (207 Q/A, 137 code + 70 prose across 6 repos), and the three prior research notes (0000–0002: contextual retrieval / GraphRAG / graphify) + benchmark 0008. So the research is scoped to go _beyond_ what's already been studied.

**Research workflow launched** — 8 parallel axes, each web-researched then adversarially verified for over-claimed numbers/specs:

1. Dense embeddings SOTA (Qwen3-Embedding, EmbeddingGemma, BGE-M3, NV-Embed…) for GPU serving
2. Code-specialized embeddings + AST/tree-sitter code chunking
3. Rerankers (Qwen3-Reranker, BGE-v2-m3, ColBERT late-interaction, listwise-LLM)
4. Contextual retrieval / late chunking / parent-doc / hierarchical
5. Query transforms + advanced architectures (HippoRAG 2, LazyGraphRAG, CRAG, Adaptive-RAG)
6. Answer-generation quality + faithfulness + local evaluation (RAGAS/judge)
7. Sparse/learned-sparse + fusion math + Qdrant knobs (quantization, HNSW, multivector)
8. Local LLM + GPU serving plan for the 2× RTX Pro 6000 Blackwell (the local-LLM decision)

**Deliverables once results land:** research note(s) under `docs/research/2026-06-08/` (next index 0003+), and the new plan at `docs/plans/2026-06-08/0004-rag-optimization-phase-2.md` (a separate "phase-2" doc, _not_ folded into 0003, following the repo's `NNNN-slug` convention — I'll flag the name in my final summary). The plan will explicitly answer the local-LLM question and list local deps to pre-install.

I'll continue automatically when the workflow reports back.

## User _(harness: task-notification)_

_Workflow notification — status: completed. Dynamic workflow "Research SOTA context-retrieval + answer-generation techniques for local RAG optimization on a 2x RTX Pro 6000 Blackwell workstation; verify claims adversarially" completed_

## Assistant

The workflow completed but **hit the session limit** (reset 2am ET) partway — 5 of 8 research axes finished, 3 failed entirely (`rerankers`, `contextual-retrieval-and-chunking`, `sparse-fusion-vectordb-knobs`), and 3 verify stages failed. The limit has since reset (date rolled to 06-09), so I'll **resume the workflow** (cached agents return instantly; only the failed 9 re-run) and simultaneously capture the partial results so nothing is lost.

## Assistant

🔧 **Workflow** — (workflow)

_↳ tool result: Workflow launched in background. Task ID: wh6l0jkzu Summary: Research SOTA context-retrieval + answer-generation techniques for local RAG optimization on a 2x RTX Pro 6000 Blackwell workstation; verif …[truncated]_

## Assistant

🔧 **Bash** — Capture partial results and summarize structure

_↳ tool result: Exit code 1 axes returned: 4 Traceback (most recent call last): File "<stdin>", line 5, in <module> AttributeError: 'str' object has no attribute 'get'_

## Assistant

Let me inspect the partial structure more carefully — it has mixed types.

## Assistant

🔧 **Bash** — Robustly inspect partial result types

_↳ tool result: top-level type: dict len: 4 [0] type=str STRING (first 300): summary [1] type=str STRING (first 300): agentCount [2] type=str STRING (first 300): logs [3] type=str STRING (first 300): result Shell cwd …[truncated]_

## Assistant

The `.output` is a wrapper — the workflow's return is under `result`. Let me parse correctly.

## Assistant

🔧 **Bash** — Parse result array and list techniques per axis

_↳ tool result: wrapper keys: ['summary', 'agentCount', 'logs', 'result'] result type: list len: 5 === [0] dense-embeddings === techniques=12 verdict=yes - [high/ab-test-priority] Qwen3-Embedding-4B (embedding-model) …[truncated]_

## Assistant

Excellent — 5 axes with rich, mostly-verified research are captured (the 2 fully-verified axes plus 3 with research done, verify pending). The resume is filling the 3 missing research axes (rerankers, contextual-chunking, sparse/vector-DB) + the pending verifies. Let me extract a complete digest of what's in hand so I can internalize it (and stay productive even if the resume window is tight).

## Assistant

🔧 **Bash** — Generate readable digest of 5 completed axes

_↳ tool result: wrote digest-5axes.md (112854 chars) Shell cwd was reset to <repo>_

## Assistant

🔧 **Read** — /tmp/rag-phase2-research/digest-5axes.md

_↳ tool result: <system-reminder>[Truncated: PARTIAL view — showing lines 1-201 of 459 total (48355 tokens, cap 25000). Call Read with offset=202 limit=201 for the next page, or Grep to find a specific section. Do NO …[truncated]_

## Assistant

The verification caught material errors (mislabeled MTEB-Code numbers, a fabricated Pass@10 figure, license gates) — exactly why the adversarial pass matters. Let me read the rest (query-transforms, answer-gen, serving).

## Assistant

🔧 **Read** — /tmp/rag-phase2-research/digest-5axes.md

_↳ tool result: File content (27386 tokens) exceeds maximum allowed tokens (25000). Use offset and limit parameters to read specific portions of the file, or search for specific content instead of reading the whole f …[truncated]_

## Assistant

🔧 **Read** — /tmp/rag-phase2-research/digest-5axes.md

_↳ tool result: 202 ## key_takeaways 203 - The KEY QUESTION has a clear answer: an Adaptive-RAG-style complexity ROUTER is the layer that lifts the hard multi-sentinel/multi-file tail without taxing the easy precise- …[truncated]_

## Assistant

🔧 **Read** — /tmp/rag-phase2-research/digest-5axes.md

_↳ tool result: 332 333 ### Provence — context pruning + reranking unified (extractive compression, near-free) [high | ab-test-priority | answer-gen] llm_needed=False 334 WHAT: ICLR 2025: a lightweight DeBERTa cross- …[truncated]_

## Assistant

I now have all 5 completed axes fully internalized — including the adversarial corrections (which caught real errors: mislabeled MTEB-Code scores, a fabricated Pass@10 figure, license gates, the no-NVLink topology constraint). The resume is filling the last 3 axes (rerankers, contextual-chunking, sparse/vector-DB) plus the 3 pending verifies in the background.

To write the deliverables **once, correctly** (verified numbers, all 8 axes), I'll wait for the resume rather than risk rework with unverified figures. Re-arming the 30-min safety timer as you asked.

## Assistant

🔧 **ScheduleWakeup** — in 1800s — Safety net while the resume workflow (3 research + verifies) runs in background; on wake I check usa …[truncated]

_↳ tool result: Next wakeup scheduled for 02:39:00 (in 1854s). Nothing more to do this turn — the harness re-invokes you when the wakeup fires or a task-notification arrives._

## Assistant

Status: research is essentially complete and verified for 5 of 8 axes; the resume is finishing the last 3 (rerankers, contextual-chunking, sparse/vector-DB) plus 3 verifies in the background. Safety timer re-armed (02:39). I'll continue automatically when the resume reports back — then write the 3 research docs + the new `0004-rag-optimization-phase-2.md` plan using the verified numbers, and answer the local-LLM/GPU question (preview: **yes, a local LLM is worth hosting** — for index-time contextualization, answer generation, and faithfulness judging; retrieval itself doesn't need one).

## User _(harness: task-notification)_

_Workflow notification — status: completed. Dynamic workflow "Research SOTA context-retrieval + answer-generation techniques for local RAG optimization on a 2x RTX Pro 6000 Blackwell workstation; verify claims adversarially" completed_

## Assistant

The resume completed cleanly (12 min, no failures) — I now have all 8 axes with verdicts. Let me capture the 3 new axes (rerankers, contextual-chunking, sparse/vector-DB) plus the now-resolved verdicts for the previously-pending axes.

## Assistant

🔧 **Bash** — Parse full 8-axis result and check verdicts

_↳ tool result: PreToolUse:Bash hook error: [${CLAUDE_PROJECT_DIR}/.agents/skills/vcs/scripts/vcs-check.sh hook --agent claude]: vcs-check: owner check refused: no session owner marker for this workspace_

## Assistant

The vcs hook guards cwd; let me run from my workspace with absolute `/tmp` paths.

## Assistant

🔧 **Bash** — Parse full 8-axis result from workspace cwd

_↳ tool result: axes: 8 - dense-embeddings techniques=12 verdict=yes - code-embeddings-and-chunking techniques=13 verdict=yes - rerankers techniques=11 verdict=yes - contextual-retrieval-and-chunking techniques=11 ve …[truncated]_

## Assistant

All 8 axes complete with verdicts. Let me generate a digest of the 3 new axes plus the now-resolved verdicts for the previously-pending ones.

## Assistant

🔧 **Bash** — Generate digest of 3 new axes + 3 resolved verdicts

_↳ tool result: wrote digest-new.md (105896 chars) Shell cwd was reset to <repo>_

## Assistant

🔧 **Read** — /tmp/rag-phase2-research/digest-new.md

_↳ tool result: 1 2 ########################################################################################## 3 # AXIS: rerankers [NEW research] 4 #################################################################### …[truncated]_

## Assistant

🔧 **Read** — /tmp/rag-phase2-research/digest-new.md

_↳ tool result: 175 - pplx-embed-context-v1's ConTEB lead (81.96% vs Anthropic 72.4%) is measured on PROSE/QA domains (Football, Geography, NarrativeQA, Covid-QA) - NOT code or dialog transcripts. Its real lift on C+ …[truncated]_

## Assistant

🔧 **Read** — /tmp/rag-phase2-research/digest-new.md

_↳ tool result: 305 FIT: Directly targets the KEY QUESTION: maximizing recall@20 on the CODE cohort (137 Q over C++/CUDA/TS/Python). Code embedders dramatically outperform bge-small on identifier/code-to-text/text-to …[truncated]_

## Assistant

I now have a complete, adversarially-verified picture across all 8 axes. The verification was invaluable — it corrected mislabeled MTEB-Code scores, a misattributed ConTEB number, Qdrant's RRF `k` default (2, not 60), several non-commercial licenses that disqualify "default" candidates, and the no-NVLink topology constraint. Time to write the deliverables.

Let me start the three research docs. First, the retrieval-substrate doc:

## Assistant

🔧 **Write** — <workspace>/docs/research/2026-06-08/0003-sota-local-retrieval-substrate.md

_↳ tool result: File created successfully at: <workspace>/docs/research/2026-06-08/0003-sota-local-retrieval-substrate.md (file state is current in your contex …[truncated]_

## Assistant

Now the second research doc — contextual indexing, query routing, and answer-generation faithfulness:

## Assistant

🔧 **Write** — <workspace>/docs/research/2026-06-08/0004-contextual-indexing-query-routing-answer-faithfulness.md

_↳ tool result: File created successfully at: <workspace>/docs/research/2026-06-08/0004-contextual-indexing-query-routing-answer-faithfulness.md (file state is …[truncated]_

## Assistant

Now the third research doc — the local-LLM + GPU serving plan (which answers your hardware question directly):

## Assistant

🔧 **Write** — <workspace>/docs/research/2026-06-08/0005-local-llm-gpu-serving-plan.md

_↳ tool result: File created successfully at: <workspace>/docs/research/2026-06-08/0005-local-llm-gpu-serving-plan.md (file state is current in your context — …[truncated]_

## Assistant

Now the centerpiece — the new Phase-2 plan doc (separate from `0003`, as you asked):

## Assistant

🔧 **Write** — <workspace>/docs/plans/2026-06-08/0004-rag-optimization-phase-2.md

_↳ tool result: File created successfully at: <workspace>/docs/plans/2026-06-08/0004-rag-optimization-phase-2.md (file state is current in your context — no ne …[truncated]_

## Assistant

Now let me update the research `OVERVIEW.md` index to include the three new notes.

## Assistant

🔧 **Read** — <workspace>/docs/research/OVERVIEW.md

_↳ tool result: 1 # research/ 2 3 Research notes that explain external techniques behind this repo's skill 4 designs. Use these for educational background and for decisions that would bloat a 5 skill if included inli …[truncated]_

## Assistant

🔧 **Edit** — <workspace>/docs/research/OVERVIEW.md

_↳ tool result: The file <workspace>/docs/research/OVERVIEW.md has been updated successfully. (file state is current in your context — no need to Read it back)_

## Assistant

Let me verify the deliverables exist and all cross-links resolve.

## Assistant

🔧 **Bash** — Verify new docs exist and links resolve

_↳ tool result: === new files === -rw-r--r--@ 1 shuyang staff 15345 Jun 9 02:25 docs/plans/2026-06-08/0004-rag-optimization-phase-2.md -rw-r--r--@ 1 shuyang staff 17413 Jun 9 02:20 docs/research/2026-06-08/0003-sota- …[truncated]_

## Assistant

All four deliverables are in place and every cross-link resolves. Let me record a short project memory so a future session knows Phase 2 is done and Phase 3 is next, then summarize.

## Assistant

🔧 **Write** — <home>/.claude/projects/<project>/memory/rag-optimization-phase2.md

_↳ tool result: File created successfully at: <home>/.claude/projects/<project>/memory/rag-optimization-phase2.md (file state is current in your context — no need to Read it …[truncated]_

## Assistant

🔧 **Read** — <home>/.claude/projects/<project>/memory/MEMORY.md

_↳ tool result: <system-reminder>Warning: the file exists but is shorter than the provided offset (28). The file has 22 lines.</system-reminder>_

## Assistant

🔧 **Read** — <home>/.claude/projects/<project>/memory/MEMORY.md

_↳ tool result: 18 - [coding-style skill](coding-style-skill.md) — non-negotiable per-tech coding rules; SKILL.md routes to styles/<tech>.md (react, typescript); ban manual memo→React Compiler; reusable oxlint fragme …[truncated]_

## Assistant

🔧 **Edit** — <home>/.claude/projects/<project>/memory/MEMORY.md

_↳ tool result: The file <home>/.claude/projects/<project>/memory/MEMORY.md has been updated successfully. (file state is current in your context — no need to Read it back)_

## Assistant

Phase 2 is complete. Here's the summary.

## What I delivered

**The new plan** (separate from `0003`, as you asked — I followed the repo's `NNNN-slug` convention so it's findable, while clearly being the "phase-2" doc):

- **`docs/plans/2026-06-08/0004-rag-optimization-phase-2.md`** — the Phase-3 optimization roadmap, ordered cheapest-/highest-confidence-first, with keep/revert discipline and per-cohort (code vs prose) scoring.

**Three research notes under `docs/research/2026-06-08/`** (indexed in `OVERVIEW.md`):

- `0003` — SOTA retrieval substrate: embeddings, code chunking, sparse, fusion, reranking, Qdrant knobs
- `0004` — contextual indexing, query routing, and answer-generation faithfulness
- `0005` — local-LLM + GPU serving plan for your 2× RTX PRO 6000 Blackwell

## Your two direct questions, answered

**Do you need a local LLM? → Yes — and your hardware is overkill for it.** Needed for three roles: **index-time contextualization** (Anthropic Contextual Retrieval — the best-supported retrieval lever), **answer generation**, and **faithfulness judging**. _Not_ needed for retrieval itself (embedding/sparse/reranking are GPU-_served_ models, not chat LLMs). Hosting it locally takes the entire campaign to **zero API token cost**. (There's also an LLM-free contextualization path — Perplexity's MIT `pplx-embed-context` — but answer-gen + judging still want a generator.)

**Local deps to pre-install:** vLLM (answer/judge) + SGLang (prefix-cached contextualization) + TEI/Infinity (GPU embedder+reranker); models — Qwen3-Embedding, Qwen3-Reranker/mxbai-rerank-v2, Qwen3-32B & Llama-3.3-70B FP8, a contextualizer, Lynx + HHEM judges; tree-sitter/Chonkie + ragas. Full list in `0005 §6` and the plan. **Key hardware constraint: no NVLink → one model per card** (don't tensor-parallel across both).

## Top recommendations the plan front-loads

Biggest code-cohort lever is the **dense embedder** (Qwen3-Embedding replaces bge-small); then GPU reranker (kills the CPU latency), contextual chunk headers + parent-doc + dual-field, per-cohort weighted RRF, and Anthropic-CR-vs-pplx-embed contextualization. The published skill default stays CPU-portable Apache/MIT; the GPU stack is the opt-in campaign config.

## Process notes

- The 8-axis research ran with **adversarial verification**, which caught real errors I corrected before writing (mislabeled MTEB-Code scores, Qdrant's RRF `k`=2 not 60, several non-commercial licenses that disqualify "default" candidates, a fabricated Pass@10 figure).
- **The session limit was hit** mid-research (~2am ET reset); I **resumed the workflow** after the reset (cached agents returned instantly, only the 9 failed agents re-ran) — so nothing was lost and all 8 axes completed.
- Work lives in the jj workspace `claude-rag-phase2` and is **not committed** — say the word and I'll commit/integrate it.
- The 30-min safety timer is still armed for ~02:39; since the work is done it'll fire once, I'll confirm completion, and the loop ends (no re-arm).

Everything verified: all four files exist and every cross-link resolves.

## User _(scheduled 30-min wakeup)_

_Continue Phase 2 of docs/prompts/2026-06-08/0005-optimizing-rag-setup.md. The SOTA research workflow is done/resuming (results captured at /tmp/rag-phase2-research/result.json + digest-5axes.md). Chec …[truncated]_

## Assistant

The safety timer fired and usage is fine — but the work is already complete from the prior turn. Let me verify the deliverables are intact, then end the loop.

## Assistant

🔧 **Bash** — Confirm Phase 2 deliverables intact

_↳ tool result: === deliverables === docs/plans/2026-06-08/0004-rag-optimization-phase-2.md docs/research/2026-06-08/0003-sota-local-retrieval-substrate.md docs/research/2026-06-08/0004-contextual-indexing-query-rout …[truncated]_

## Assistant

All Phase 2 deliverables are present and tracked in the workspace (4 new files + the `OVERVIEW.md` update). The work was completed in the prior turn — this was just the 30-minute safety check confirming nothing was cut off.

**Nothing left to do** — ending the loop (not re-arming the timer).

## Phase 2: complete ✓

| Deliverable                                | Path                                                                                     |
| ------------------------------------------ | ---------------------------------------------------------------------------------------- |
| Plan (new, separate from `0003`)           | `docs/plans/2026-06-08/0004-rag-optimization-phase-2.md`                                 |
| Research — retrieval substrate             | `docs/research/2026-06-08/0003-sota-local-retrieval-substrate.md`                        |
| Research — advanced retrieval + answer-gen | `docs/research/2026-06-08/0004-contextual-indexing-query-routing-answer-faithfulness.md` |
| Research — local-LLM/GPU serving           | `docs/research/2026-06-08/0005-local-llm-gpu-serving-plan.md`                            |
| Index                                      | `docs/research/OVERVIEW.md` (updated)                                                    |

**Answers locked in:** local LLM = **yes** (contextualization, answer-gen, judging — not retrieval); deps + the 2× RTX PRO 6000 (no-NVLink) serving plan documented; all numbers adversarially verified and corrected; per-cohort keep/revert roadmap ready for Phase 3.

Work lives uncommitted in jj workspace `claude-rag-phase2`. Say the word to commit/integrate, or to kick off Phase 3.

## User

Other agents were doing similar work. Advance main, rebased onto main and resolve conflicts if you see any. Make sure all of your files are clearly renamed with `claude` keyword. Then export session transcript, use the /vcs skill to integrate, commit and push.

## Assistant

I'll work through this in order: advance main, rebase my workspace onto it, rename my files with the `claude` keyword (also resolving any index collisions with other agents' work), export the transcript, then integrate/commit/push. Let me start by loading the `vcs` skill (the governing skill for integration) and checking the current state.

## Assistant

🔧 **Skill** — vcs

_↳ tool result: Launching skill: vcs_

## Assistant

I'm in jj mode (workspace `claude-rag-phase2`). Let me confirm the mode, fetch to advance `main`, and see what other agents have landed in the directories I touched.

## Assistant

🔧 **Bash** — Confirm jj mode and fetch to advance main

_↳ tool result: === jj root === <workspace> === fetch (advance main) === Nothing changed. === main bookmark now === ffc3abf87f4f docs(rag): add codex phase 2 o …[truncated]_

## Assistant

`main` has already advanced — a **Codex agent landed the same Phase-2 work** (`ffc3abf docs(rag): add codex phase 2 optimization plan`), ahead of my parent `d06afd4`. Let me see exactly what Codex added so I can detect filename collisions before renaming mine.

## Assistant

🔧 **Bash** — List Codex's files on main in the touched dirs

_↳ tool result: === research/2026-06-08 ON MAIN === docs/research/2026-06-08/0000-contextual-retrieval-for-doc-authors.md docs/research/2026-06-08/0001-contextual-retrieval-with-graphrag.md docs/research/2026-06-08/0 …[truncated]_

## Assistant

Now I see the picture — **Codex and Cursor both already landed Phase-2 work**, creating index collisions with mine:

- research: `0003-codex-...` and `0003-cursor-...` exist (my `0003`/`0004`/`0005` need fresh indices + `claude`)
- plans: `0004-cursor-...` and `0006-codex-rag-optimization-phase-2.md` exist (my plan `0004` collides with cursor's)

The likely content conflict is `docs/research/OVERVIEW.md` (everyone edits it). Let me check main's OVERVIEW.md, then rebase.

## Assistant

🔧 **Bash** — Show OVERVIEW.md as it stands on main

_↳ tool result: === OVERVIEW.md ON MAIN === ## Notes ### 2026-06-08 - [`0000` — contextual retrieval techniques for doc authors](2026-06-08/0000-contextual-retrieval-for-doc-authors.md) - [`0001` — contextual retriev …[truncated]_

## Assistant

Conflict will be in `OVERVIEW.md` (everyone appends there). My plan: rebase onto main, union the OVERVIEW entries, then rename my 4 files with fresh indices + `claude` keyword (research `0004/0005/0006`, plan `0005` — the colliding indices are taken by codex/cursor). Let me rebase first.

## Assistant

🔧 **Bash** — Rebase my working-copy change onto advanced main

_↳ tool result: === rebase @ onto main === Rebased 1 commits to destination Working copy (@) now at: ynkwkvsm b4d61c0b claude-rag-phase2\* | (conflict) (no description set) Parent commit (@-) : tntwslzw ffc3abf8 main …[truncated]_

## Assistant

Rebase done; only `OVERVIEW.md` conflicts (as expected). Now let me rename my 4 files with the `claude` keyword and fresh non-colliding indices (research `0004/0005/0006`, plan `0005`), and fix the internal cross-links.

## Assistant

🔧 **Bash** — Rename my 4 files with claude keyword and fix internal cross-links

_↳ tool result: docs/research/2026-06-08/0004-claude-rag-retrieval-substrate.md: 6 link refs updated docs/research/2026-06-08/0005-claude-rag-contextual-routing-faithfulness.md: 7 link refs updated docs/research/2026 …[truncated]_

## Assistant

Now I need to fix the display-label indices inside the docs (the link _targets_ are updated, but labels like ``[`0003` ...]`` still show old numbers). Let me update those, anchored on distinctive title text so the unrelated eval-set `0003` reference is untouched.

## Assistant

🔧 **Bash** — Fix display-label indices in renamed docs

_↳ tool result: docs/research/2026-06-08/0004-claude-rag-retrieval-substrate.md: 3 labels fixed docs/research/2026-06-08/0005-claude-rag-contextual-routing-faithfulness.md: 3 labels fixed docs/research/2026-06-08/000 …[truncated]_

## Assistant

Now resolve the `OVERVIEW.md` conflict by unioning all passes' entries. Let me read the conflicted file, then write the resolved version.

## Assistant

🔧 **Read** — <workspace>/docs/research/OVERVIEW.md

_↳ tool result: 1 # research/ 2 3 Research notes that explain external techniques behind this repo's skill 4 designs. Use these for educational background and for decisions that would bloat a 5 skill if included inli …[truncated]_

## Assistant

🔧 **Write** — <workspace>/docs/research/OVERVIEW.md

_↳ tool result: The file <workspace>/docs/research/OVERVIEW.md has been updated successfully. (file state is current in your context — no need to Read it back)_

## Assistant

Let me verify the conflict is resolved and all links (including to the new cross-pass files) resolve.

## Assistant

🔧 **Bash** — Verify conflict resolved and links valid

_↳ tool result: === jj status === Working copy changes: A docs/plans/2026-06-08/0005-claude-rag-optimization-phase-2.md A docs/research/2026-06-08/0004-claude-rag-retrieval-substrate.md A docs/research/2026-06-08/000 …[truncated]_

## Assistant

Conflict resolved cleanly, all links valid. Now let me export the session transcript (it'll add a file under `docs/coding-sessions/` that should be part of this commit).

## Assistant

🔧 **Skill** — export-coding-session

_↳ tool result: Launching skill: export-coding-session_

## Assistant

Let me get the target index (from my workspace so the file lands in my commit) and locate the session log.

## Assistant

🔧 **Bash** — Get session index, locate jsonl, read author

_↳ tool result: === next-index === dir: docs/coding-sessions/2026-06-09 index: 0046 === session jsonl candidates === <home>/.claude/projects/<project>/7bf4bedd-4350-4660-966 …[truncated]_

## Assistant

Index `0046`, today's folder. Let me inspect the session JSONL schema so I can render it faithfully.

## Assistant

🔧 **Bash** — Inspect session jsonl schema

_↳ tool result: lines: 270 records: 270 types: {'queue-operation': 12, 'attachment': 24, 'user': 67, 'last-prompt': 26, 'assistant': 141} roles: {None: 62, 'user': 67, 'assistant': 141} [user] top-keys=['parentUuid', …[truncated]_

## Assistant

Schema understood: 67 user records (most are harness-injected task-notifications / wakeups / skill launches; the genuine human turns are the Phase-2 prompt and this integrate prompt), 141 assistant records. Let me render the transcript — human turns verbatim, harness-injected turns labeled/truncated, tool calls briefly summarized, thinking omitted.

## Assistant

🔧 **Bash** — Render session transcript to markdown
