# Plan: RAG eval set — Phase 1 (consolidated gold queries for `setting-up-rag` + `retrieving-context`)

- **Date created:** 2026-06-08
- **Last updated:** 2026-06-08
- **Status:** Phase 1 complete — **207** source-grounded, verified gold-query candidates across 6 repos; ready to wire into the harness (Phase 2).
- **Authors:** Claude (Opus 4.8, workspace `claude-rageval-collect`) + Codex (`codex-rag-eval-set`) — two independent passes, **consolidated into one set**.
- **Repo:** `coding-agent-skills`
- **Harness:** [`improving-context-retrieval-skills`](../../../.agents/skills/improving-context-retrieval-skills/SKILL.md)
- **Scope:** Phase 1 of "Optimizing RAG Setup" — collect a large, in-depth, source-grounded eval set to drive measurement-based improvement of [`setting-up-rag`](../../../.agents/skills/setting-up-rag/SKILL.md) and [`retrieving-context`](../../../.agents/skills/retrieving-context/SKILL.md). The existing docs/source of the six target repos were read **as-is**; [`updating-docs`](../../../.agents/skills/updating-docs/SKILL.md) was **not** modified. This file is the overview; the actual questions live in the per-repo files (in the [`0003-rag-eval-set-phase-1/`](0003-rag-eval-set-phase-1/) subdirectory) and in [`eval-set.json`](0003-rag-eval-set-phase-1/eval-set.json).

---

## Summary

This is the Phase-1 gold set for optimizing local retrieval. It holds **207 question/answer
gold facts** spread over **six repositories**, each in the shape the harness's gold set
consumes (a [`gold.py`](../../../.agents/skills/improving-context-retrieval-skills/scripts/gold.py)
`Fact`): a **paraphrased query**, the **grounded answer**, the **exact `sentinels`** that
occur verbatim in the **primary** source file(s), and a `domain` (`code` vs `nl`) and
`difficulty` slice. Every question was authored by reading the repo in depth, and **every
sentinel was re-verified against the primary file's raw bytes** at build time, while **no
query contains its own sentinel** (the non-circularity firewall).

The set is the **merge of two independent collection passes** — Claude's structured pass
(134 questions) and Codex's pass (84 prose candidates, of which **73 testing distinct facts**
were converted to this structured form and folded in). After the merge there are **0
near-duplicate pairs** (no shared sentinels, no near-identical questions) and **0 duplicate
ids**.

- **Machine-readable:** [`eval-set.json`](0003-rag-eval-set-phase-1/eval-set.json) — the consolidated set, the artifact the next phase consumes.
- **Human-readable:** one file per repo (linked below), grouped by `domain` then listing each gold fact.

## The six repositories and their corpora

Retrieval behaves differently over prose and over code, so each question is tagged with the
**corpus (`domain`)** it is scored against. Two repos carry exported session transcripts, so
their sets are **split** between codebase questions and prompting/session-history questions
(per the methodology); the four Alpha Zero repos mix engine-code and design-doc questions.

| Repo | Kind | `domain=code` corpus | `domain=nl` corpus |
| --- | --- | --- | --- |
| [`coding-agent-skills`](0003-rag-eval-set-phase-1/coding-agent-skills.md) | TS app + Python/shell harness **+ transcripts** (split) | `inception/`, `.agents/skills/*/scripts/`, `scripts/` | `docs/coding-sessions/`, `docs/{benchmarks,issues,plans,prompts,research}` |
| [`alpha-zero`](0003-rag-eval-set-phase-1/alpha-zero.md) | C++23 + CUDA engine + TS/TSX GUI | `src/ include/` (MCTS/inference/training), `gui/`, `tests/` | `docs/` (transformer/inference/perf design docs) |
| [`alpha-zero-api`](0003-rag-eval-set-phase-1/alpha-zero-api.md) | header-only C++ game contract | `src/ include/`, `test/` | `doc/report.md`, `doc/migration-guides/` |
| [`az-game-tic-tac-toe`](0003-rag-eval-set-phase-1/az-game-tic-tac-toe.md) | C++ game impl of the contract | `src/ include/ tests/` | `memory/` (constitution, rules, mcts/augmentation/history) |
| [`az-game-xiang-qi`](0003-rag-eval-set-phase-1/az-game-xiang-qi.md) | C++ game + TS/TSX GUI | `src/ include/ tests/`, `gui/` | `memory/` (game_design/rules + details/, gui_design, …) |
| [`website`](0003-rag-eval-set-phase-1/website.md) | Cloudflare-Worker React app **+ transcripts** (split) | `shuyang-website/src/` + config, `tools/`, `scripts/` | `llm-sessions-history/`, `prompts/`, `docs/{design,plan,research}` |

> Paths in each question's `primary` field are **relative to that repo's root** (the absolute
> root is stated at the top of every per-repo file and in `eval-set.json`).

## Question schema (one gold fact)

Each entry carries the fields below — the same shape as a `gold.py` `Fact`, so the set maps
into the harness with minimal transformation:

| field | meaning |
| --- | --- |
| `id` | unique kebab id (repo-prefixed; `-cx-` marks a fact sourced from the Codex pass) |
| `domain` | `code` (source/config files) or `nl` (markdown docs / README / transcripts) |
| `category` | `codebase`, `design-doc`, or `session-prompting` (the eval slice) |
| `question` | paraphrased natural-language query — **never contains its own sentinel** |
| `answer` | the grounded 1–4 sentence answer (naturally contains the sentinel) |
| `sentinels` | 1–4 exact strings that occur **verbatim** in a primary file (the factuality anchor) |
| `primary` | 1–3 repo-root-relative paths to the file(s) that state the answer |
| `difficulty` | `easy` / `medium` / `hard` (hard ⇒ multi-sentinel, multi-file synthesis) |
| `evidence` | the `path:line: text` proof that each sentinel really occurs in the primary |
| `source` | `claude` or `codex` (which collection pass authored it) |

**The two firewall rules** (enforced deterministically at build time, not by an LLM):

1. **Sentinel presence.** Each sentinel must be a literal substring of one of its `primary`
   files' raw bytes. This is the factuality anchor the harness scores against. (One Codex
   candidate that failed this was dropped automatically.)
2. **Non-echo.** No `question` may contain any of its own sentinels (case-insensitive), so
   retrieval cannot be won by lexical echo — the query is phrased by concept/behavior. (Two
   questions that violated this were reworded and re-checked.)

## The set by the numbers

| Repo | Total | claude | codex | `code` | `nl` | easy | medium | hard |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `coding-agent-skills` | 45 | 31 | 14 | 25 | 20 | 5 | 28 | 12 |
| `alpha-zero` | 32 | 20 | 12 | 20 | 12 | 3 | 17 | 12 |
| `alpha-zero-api` | 30 | 20 | 10 | 23 | 7 | 5 | 20 | 5 |
| `az-game-tic-tac-toe` | 24 | 14 | 10 | 19 | 5 | 2 | 17 | 5 |
| `az-game-xiang-qi` | 33 | 21 | 12 | 27 | 6 | 4 | 17 | 12 |
| `website` | 43 | 28 | 15 | 23 | 20 | 7 | 27 | 9 |
| **Total** | **207** | **134** | **73** | **137** | **70** | **26** | **126** | **55** |

## How it was collected and verified

1. **Generate.** Deep-exploration sub-agents read each repo (split repos got a codebase agent
   and a session/prompting agent; large repos were split further), drafting candidates with
   grep-confirmed sentinels and `primary` paths.
2. **Adversarial verify.** A per-repo verifier agent re-grepped every sentinel against the raw
   bytes of its primary file, de-echoed any query that leaked its answer, fixed wrong
   `primary` paths, and dropped trivial/generic items.
3. **Merge.** Codex's independent prose set was deduped against this set per repo (a different
   angle on the same file is **not** a duplicate; only the same underlying fact is) and its
   unique facts were converted to this structured shape with the same grep verification.
4. **Deterministic sweep.** A no-LLM checker
   ([`0003-rag-eval-set-phase-1/verify.py`](0003-rag-eval-set-phase-1/verify.py)) re-validated
   the whole set against the repos' raw files — every published question passes
   sentinel-presence **and** non-echo, and assembly refuses to emit any that don't. Re-run it
   from the subdirectory with `python3 verify.py eval-set.json` (reads each repo root from the JSON).

## Feeding Phase 2 (wiring into the harness)

The next phase turns these candidates into graded BEIR `qrels` and runs them through the
harness's Phase-0 eval (BM25 + in-memory vectors) per `(corpus × rag-config)` cell:

- **Per-repo corpus roots.** Each repo is its own corpus; index `domain=code` files with
  `--kind code` and `domain=nl` files with `--kind md` (see
  [`setting-up-rag` §1](../../../.agents/skills/setting-up-rag/SKILL.md)). The `sentinels`
  give sentinel-mode `qrels`; hand-pinned `primary` paths give grade-2 labels.
- **Self-reference exclusion (critical).** The `coding-agent-skills` questions point at this
  repo's own `docs/` and skill scripts. When that repo is indexed as a corpus, **these eval
  files must be excluded** (add `plans/2026-06-08/0003-rag-eval-set-phase-1*` to `gold.py`'s
  `EXCLUDE_GLOBS`, covering both this plan file and its subdirectory) — otherwise a retriever
  could "answer" a query by returning the eval file that quotes its own sentinel, inflating the
  score. The five external repos have no such hazard.
- **Domain ↔ corpus-kind guard.** Score `domain=code` only against the code corpus and
  `domain=nl` only against the prose corpus (`check-retrieval.py --corpus-kind … --domain …`),
  so code-vs-prose retrieval is compared with separate metrics.

## Provenance

Two agents independently executed Phase 1. Codex's pass landed first on `main` (the prior
`0003-rag-eval-set-phase-1/README.md`, now superseded by this file, and coding-session
[`0042`](../../coding-sessions/2026-06-08/0042-codex-rag-eval-set-phase-1.md)) as 84 prose
candidates. This consolidated revision replaces that prose with the structured, machine-readable
set and **folds Codex's 73 distinct facts into the per-repo files** (marked `source: codex`),
per the decision to merge into one set. Codex's original prose remains in git history.
