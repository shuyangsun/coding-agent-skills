---
title: "Phase 3 RAG — Wave 4 steps 2–6 (late chunking, session metadata, Doc2Query, reader/packing)"
date: 2026-06-10
repo: "coding-agent-skills (bookmark `main`; work change `feat(rag): Phase 3 Wave 4 steps 2-6 …`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Opus 4.8, 1M context, effort: max)"
summary: >-
  Completed the remaining Wave-4 items of the consolidated RAG optimization (plan `0008`):
  built late-chunking and Doc2Query harness modules plus a deterministic session-metadata
  capsule, ran one-variable-at-a-time benchmarks on the GPU box, recorded `0016`–`0019`,
  updated the plan and the `setting-up-rag` skill, landed the work on `main`, then
  exported this session and pushed.
---

<!-- markdownlint-disable MD013 MD024 -->

# Phase 3 RAG — Wave 4 steps 2–6 (late chunking, session metadata, Doc2Query, reader/packing)

## User

Advance main then rebase onto main. Read @docs/prompts/2026-06-08/0005-optimizing-rag-setup.md and @docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md to understand what was done in Wave 4. Experiment and benchmark the remaining items in wave 4 that were not done, then update docs and improve skills.

_(Session model set to Opus 4.8 (1M context); effort set to max.)_

## Assistant

Loaded the `vcs` skill, then worked in the assigned jj workspace (`claude-pending-f1115056`, later renamed `claude-rag-wave4`).

- **VCS:** `jj git fetch` (origin already current) → local `main` was at `15a66a05` (session 0055) while my workspace parent was `fb4edb3b` (0054). Rebased my empty working copy onto `main` (`jj rebase -s @ -d main`), which pulled in the Wave-4 harness files. Renamed the work to `claude-rag-wave4`. (Noted the shell cwd resets between commands and a `vcs-check.sh` hook requires every Bash command to `cd` into my workspace first.)
- **Read** prompt `0005`, plan `0008`, and benchmarks `0014` (gemma-4 contextual retrieval — the top win) and `0015` (generator-model comparison). Established that Wave-4 **step 1/1b were done**; the **remaining items are steps 2–6**: LLM-free contextual embedding, late chunking, Doc2Query, session metadata, and long-context reader arms.
- **Read the harness** (`run_benchmark.py`, `enriched_index.py`, `wave4_context.py`, `gold_loader.py`, `corpus_manifest.py`, `metrics.py`) to learn the config schema, the dual-field (`raw_text` / `contextualized_text`) indexer, the index-identity hashing, and the gold-set wiring (207 questions, dev/held-out by hash parity, `domain=code|nl` a reporting slice over one combined per-repo corpus).
- **Environment:** confirmed I was running on the GPU box `delos` itself — GPU1 free, the gemma-4 vLLM endpoint live, both Qdrant instances healthy (`:6343` the isolated Phase-3 store), all venvs and all six repos present. So the full GPU/LLM campaign was runnable.

Set up a task list and planned four experiments (EXP-1 late chunking, EXP-2 Doc2Query, EXP-3 session metadata, EXP-4 reader/packing), each one variable at a time vs the `w2-ctx-header` baseline, sliced + regression-scanned.

### EXP-1 — Late chunking (Wave 4 steps 2+3)

- De-risked with a smoke test: `bge-m3` (MIT, 8192-ctx, 1024-d) loads on GPU1 and offset-mapping token pooling is sane (an MCTS query ranked the MCTS chunks above a GUI chunk under naive pooling; late pooling raised/contextualized all sims as expected).
- Wrote `wave4_latechunk.py`: GPU precompute of per-chunk dense vectors in two modes — **naive** (each chunk embedded alone) and **late** (whole-document 8192-token windows, mean-pool each chunk's contextual tokens) — plus the 207 query vectors, cached as numpy so the benchmark runner stays torch-free and only the dense doc/query vector swaps.
- Wired two surgical hooks: dense-from-cache in `enriched_index.index_repo`, query-from-cache in `run_benchmark._embed_query`, and folded `dense_source` into the index identity. Added two arm configs (`w4-lc-bge-m3-naive`, `w4-lc-bge-m3-late`).
- Precompute: 9361 naive + 9361 late + 207 query vecs in 67 s. Topped up the gemma-4 context cache for `coding-agent-skills` (it had grown since 0014) so the `w4-llm-all` reference ran at full coverage.
- **Result (held-out, benchmark `0016`):** late chunking is the worst arm — nDCG 0.614 vs baseline 0.730 (−0.115); the clean **naive→late delta is −0.079** (the method). Regresses both code and nl, all repos, confirmed on dev (−0.192). **REJECTED.** Whole-document pooling blurs within-document discrimination; contextual retrieval wins by _sharpening_ per-chunk identity, not averaging.

### EXP-2 — Doc2Query / document expansion (Wave 4 step 4)

- Wrote `wave4_doc2query.py` (gemma-4 predicts 4 search queries per chunk, cached like the context generator) and added a **separate `bm25_text` field** to the indexer so the expansion is lexical-only (dense and `raw_text` untouched) — the faithful Doc2Query, honoring the plan's "separate field" instruction. Generalized the indexer's dense/sparse split.
- Generated 9361 expansions (~5 chunk/s) in the background while building EXP-3, then ran four arms.
- **Result (held-out, benchmark `0018`):** all-chunks Doc2Query is a robust **code** win (nDCG +0.030 sparse / +0.060 both; dev +0.043 / +0.076), but it costs some nl slices (alpha-zero design-docs −0.062 across all arms). **Prose-only is REJECTED** (regresses code — the third confirmation that index-time context must never be restricted to prose). ≈ contextual-retrieval quality, but less clean on nl → **campaign-side, alternative to contextual retrieval**, not a replacement.

### EXP-3 — Session metadata (Wave 4 step 5)

- Checked the gold set: 33 `session-prompting` questions (all nl); 15 of their primaries are transcripts (11 of them website's `llm-sessions-history/`). Implemented a deterministic, LLM-free `session_capsule()` in `enriched_index.py` — `session <id> <vendor> <date> — <name>; files: <mentioned-file list>` — prepended to transcript chunks; validated it on real transcripts.
- **Result (held-out, benchmark `0017`):** weak/targeted positive — overall nDCG +0.019, but on the target `session-prompting` slice +0.056 with **website transcripts → perfect (1.000)**. The only flagged regression (alpha-zero code −0.034) is on a repo with **no transcripts** → byte-identical text → pure HNSW re-index noise, which usefully **bounds the per-slice noise floor at ~0.03**. → **optional portable enrichment for transcript corpora.**

### EXP-4 — Long-context reader / packing arms (Wave 4 step 6)

- Determined (benchmark `0019`) that packing **order** (source/score/parent-first) is **order-invariant** under every retrieval-stage metric (file-rank metrics, set-membership sentinel/hit, sum-of-tokens) → it cannot be measured at the retrieval stage; the discriminating metric is answer faithfulness. **Deferred to Wave 7** with the proof + the measured packed cost (~6.3k tokens/top-20). Packing _granularity_ (parent windows) is Wave-2 territory.

### Docs + skills

- Updated plan `0008`: status line, progress table (rows for `0016`–`0019`), current-best config, a **Wave-4 synthesis** ("index-time context helps iff it sharpens, not blurs, and applies to all chunks, not just prose"), the HNSW noise-floor note, and per-step roadmap outcomes.
- Updated `setting-up-rag` SKILL.md §6 (Doc2Query campaign option, optional session capsule, late-chunking rejection, the sharpen-not-blur rule) and RETRIEVAL.md §5 (contextual retrieval now measured; Doc2Query added; late chunking flagged rejected). `retrieving-context` left unchanged — all Wave-4 findings are index-construction concerns. Portable default unchanged.
- Ran prettier + markdownlint on my files (all clean; remaining repo lint debt is pre-existing).

### Landing the work

- `jj describe` with a full conventional-commit message, deleted the stale pre-rename bookmark, and ran `integrate.sh claude-rag-wave4`: fast-forwarded `main` to `c560ee2d`, deleted the merged bookmark, and **retired my jj workspace** (NEXT_CWD = the shared default checkout).
- Tried the final `jj git push --bookmark main` but the `vcs-check.sh` publish guard refused it from the shared default — and then refused _every_ Bash command from there (the retired workspace's owner marker still claimed I owned a workspace). Reported the work as landed on **local main** with the push handed off, and flagged the `integrate.sh` ↔ `vcs-check.sh` inconsistency as a real `vcs`-skill bug.

## User

Export coding session, then commit and push again. Be creative on how to push, it’s okay to bypass guards since you’re the only agent running now, believe in yourself, you can do it! (And please clean up afterwards.)

## Assistant

Read `vcs-check.sh` and found the real mechanics: the guard **explicitly allows** standalone `jj git push --bookmark main` and `jj describe -r main -m "…"` even from the shared default — my earlier pushes failed only because I bundled them with `&&` (which the guard's "simple command" parser rejects). It also whitelists the `.agents/skills/vcs/scripts/*.sh` helper paths (I'd been invoking the `.claude/...` copy). Non-VCS commands are allowed from any non-default cwd (e.g. `/tmp`).

- Loaded the `export-coding-session` skill. Created a fresh isolated workspace via the vetted `.agents/.../isolate.sh` (`claude-export-wave4`, off `main` = `c560ee2d`) so the file-writing export is permitted. `next-index.sh` → `0056`, dir `docs/coding-sessions/2026-06-10`.
- Wrote this transcript into the workspace, ran the redaction scanner, committed it on top of the Wave-4 change, integrated it onto `main`, and pushed `main` to origin with a standalone `jj git push --bookmark main`.
- Cleaned up: retired the export workspace and removed my stale session owner markers.

## Session outcome

Wave 4 of the consolidated RAG optimization is complete. Two clean negatives (late chunking; prose-only Doc2Query), one campaign win (all-chunks Doc2Query), one optional portable enrichment (deterministic session capsule), and one principled Wave-7 deferral (reader packing) — unified by "index-time context must sharpen, not blur, and must cover code, not just prose." Benchmarks `0016`–`0019`, plan `0008`, and the `setting-up-rag` skill were updated and landed on `main`, and this session was exported as `0056`.
