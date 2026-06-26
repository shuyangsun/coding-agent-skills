---
title: "RAG Phase 3 pre-work — benchmark harness + combined-corpus fix"
date: 2026-06-09
repo: "`coding-agent-skills` (jj bookmark `claude-rag-phase3-prework`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Opus 4.8, 1M context, thinking: high)"
summary: >-
  Built the reusable Phase-3 RAG-optimization benchmark harness under
  `docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/` (gold loader,
  per-repo corpus manifest, enriched dual-field indexer, contamination controls,
  slice-aware metrics, Wave-0 config arms, readiness gate) without starting Phase 3;
  surfaced and fixed a C++/CUDA extension gap; then, per owner feedback, reworked the
  scoring so the IR task is one combined code+docs corpus per repo with code-vs-doc as a
  reporting slice only.
---

<!-- markdownlint-disable MD013 MD024 -->

# RAG Phase 3 pre-work — benchmark harness + combined-corpus fix

## User

Read the consolidated plan at @docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md, and work on `Phase 3 Pre-Work` items to prepare for work in phase 3. Do NOT start phase 3 work, only do prep work. If you need more context, feel free to read other files under @docs/plans/2026-06-08/ and @docs/research/2026-06-08/.

_(The same request was sent once, interrupted, then re-sent verbatim.)_

## Assistant

Read the consolidated plan and gathered context before acting.

- Inspected the plan's "Phase 3 Pre-Work" section, the Phase-1 eval set (`0003-rag-eval-set-phase-1/eval-set.json`, 207 questions over 6 repos) and its `verify.py`, the shipped `setting-up-rag` scripts (`rag_lib.py`, `index.py`, `query.py`, `rag-config.json`), and the `improving-context-retrieval-skills` harness (`gold.py`).
- Dispatched an `Explore` agent to map how prior benchmarks (0006–0009) were produced. Finding: 0008/0009 were one-off `.py` runners under `docs/benchmarks/` that import `rag_lib` and run real Qdrant; there is **no** reusable multi-repo harness, and `gold.py` uses 9 hardcoded facts and did not exclude the eval files.
- Probed the environment: the skill venv has FastEmbed + Qdrant; all 6 repos present; Docker/`rg`/`jj` present; Qdrant server down (embedded mode works); IR libs + `rapidfuzz` absent.

Decided the harness is campaign infrastructure that belongs beside the consolidated plan (mirroring the `0003` precedent), kept out of the portable skill. Then built it, testing each piece:

- Fixed contamination first: added the eval-set + consolidated-plan globs to `improving-context-retrieval-skills/scripts/gold.py` `EXCLUDE_GLOBS`; re-ran `verify.py` → **207/207, 0 echo**.
- **Audit finding (headline):** the shipped `CODE_EXTS` is JS/TS/Python-only, so **68 distinct gold primaries** (all C++/CUDA `.cc`/`.h`/`.cuh`, `CMakeLists.txt`, `.yml`, `.sh`) would not load — the code domain would be empty for 4 of 6 repos. Built `corpus_manifest.py` with a comprehensive language-aware extension set.
- Wrote `gold_loader.py` (loads `eval-set.json` preserving every field + deterministic dev/held-out split, graded qrels, reachability validation), `enriched_index.py` (span-tracking chunker → byte-verbatim `raw_text` + rich dual-field Qdrant payload), `contamination.py` (per-query synthesis-doc check + closed-book/wrong-context control generators), `metrics.py` (slice-aware TSV reusing `gold.py`'s scorer), `make_configs.py` (8 Wave-0 arm configs), and `validate_prework.py` (one-command GO/NO-GO gate).
- Validated: all 207 primaries reachable + sentinel-bearing; `raw_text` byte-verbatim with no sentinel split across chunk boundaries in any repo; an end-to-end embedded-Qdrant index of `alpha-zero-api` retrieved 8/8 gold code primaries (harness validation, not a baseline). Installed `rapidfuzz`; left `pytrec_eval`/`ranx` uninstalled since `gold.py`'s scorer is the deterministic IR core.
- Formatted/linted new files with the repo's prettier; confirmed the only change outside the harness dir was the `gold.py` contamination fix. Final readiness gate: **6/6 GO, READY for Wave 0**. No baselines run, no baseline config declared (that is Wave 0 = Phase 3). Wrote a pre-work README mapping each plan item to status plus a Wave-0 runner contract, and saved a memory.

## User

Great! One question - I did mention that I would like different metrics for codebase and session history / docs. However, they shouldn’t be treated as completely separate text corpus and tests. Code sometimes reference docs, and docs often reference code. For information retrieval, the same question should usually retrieve both docs and code. Is everything built as two isolated corpus that cannot reference each other? If so, don’t do that, I just want to view total and separate (code vs doc) metrics, but the IR task should not care about the type of information, it should retrieve it as long as it’s helpful.

## Assistant

Diagnosed honestly: **partly isolated.** The index was already combined (one Qdrant collection per repo holding code + docs), but the scoring/qrels path isolated them — `gold_loader` had `DOMAIN_KINDS = {"code": ("code",), "nl": ("md",)}` and built a separate corpus per `(repo, domain)`, so a code question was scored only against code and an nl question only against docs. That framing had also leaked into the README, the config `index_mode: split-*` wording, and the consolidated plan's §5.

Fixed it so the IR task is one combined per-repo corpus and code-vs-doc is purely a reporting slice:

- `gold_loader.py`: replaced `DOMAIN_KINDS` + per-`(repo,domain)` `scored_corpus` with `combined_corpus(repo)` (code + docs together, with a primary backstop); `qrels`/reachability/`validate` now run over it; `cmd_qrels` reports one combined corpus per repo.
- `metrics.py`: added a `frac_code_retrieved` / `frac_md_retrieved` diagnostic and documented that aggregation is total + by code/doc domain, retriever type-blind.
- `make_configs.py`, `README.md`, and the consolidated plan **§5** reworded to "one combined index; domain is a slice, not a corpus partition" (the plan edit carries a dated revision note); left the historical Phase-1 `0003` guard wording as a superseded record.

Proof:

- **12 gold questions have primaries spanning both code and docs** (e.g. `CHUNKING.md` + `rag_lib.py`; `training_pipeline.md` + `eval.cc` + `trainer.cc`) — under the old split, a code question's doc primary was unreachable.
- On a real combined `alpha-zero-api` index, the cross-type question `azapi-cx-default-deser-no-softmax-vs-migration` retrieved **both** its `.h` code primary (rank 3) **and** its `.md` migration-doc primary (rank 12); **29/30** questions pulled a code+doc mix in top-20 (mean ~44% code / 56% doc).
- Readiness gate still **6/6 GO**; metrics now 38 columns including the kind diagnostic. Updated the memory note.

## User

Export session transcript, then use the VCS skill to integrate and push. Clean up residual Jujutsu workspace and bookmarks afterwards.

## Assistant

Invoked the `export-coding-session` skill: ran `next-index.sh` (→ `docs/coding-sessions/2026-06-09/`, index `0049`), pulled the verbatim user turns from the Claude Code log, and wrote this transcript with redaction-safe paths. Next: run the redaction scanner, then use the `vcs` skill to integrate the `claude-rag-phase3-prework` workspace onto `main` and push, then clean up the residual jj workspace and bookmark.
