<!-- markdownlint-disable MD013 MD024 -->

# improving-docs-and-rag harness — no-doc/no-RAG floor baseline + code-vs-NL content-type axis

- **Date:** 2026-06-07
- **Repo:** coding-agent-skills (jj workspace/bookmark `claude-baseline-cell-docs-rag`, parent `main`)
- **Author:** Shuyang Sun <shuyangsun10@gmail.com>
- **Agent:** Claude Code (Opus 4.8, 1M context, thinking: high; the very first exploration ran on Sonnet 4.6 before the owner switched models)
- **Summary:** Two changes to the `improving-docs-and-rag-skills` Phase-0 harness. (1) Added an absolute **no-doc/no-RAG floor** baseline (`Z` empty corpus + `docs-eval.py --no-retrieval`) that runs first, with a scoreboard "baseline-first" lift view (floor → docs-only → RAG-only → docs+RAG). (2) Added a **content-type axis** that scores natural-language docs/transcripts vs **code** (the repo's `inception/` TanStack app) **separately**, with per-domain metrics and a code-vs-NL scoreboard view. Along the way fixed two bugs the exploration surfaced: 4 stale gold-fact primary paths (date-dir drift that broke `gold.py validate`) and `OVERVIEW.md` index docs leaking sentinels into the corpus. Ran a 5-dimension adversarial review workflow (20 agents); fixed all 10 confirmed findings (graceful no-`inception/` skip, a `--domain`/`--corpus-kind` consistency guard, an honest code-recall-saturation caveat, scoreboard round-gating/empty-bucket/dup-column hardening, and several doc corrections). Then exported this session and handed off to `vcs` to merge/clean up/push.

## User

If this is not already the case, change the /improving-docs-rag-skills harness to first have a baseline benchmark without any doc or RAG, before generating benchmarks with docs only, RAG only, or docs + RAG.

## Assistant

Explored the harness with a read-only sub-agent and read the operational files (`SKILL.md`, `LOOP.md`, `MATRIX.md`, `METRICS.md`, `SCENARIOS.md`) and the five Phase-0 scripts (`gold.py`, `docs-eval.py`, `check-retrieval.py`, `mk-corpus.py`, `scoreboard.py`). Established the current shape: a 2×2 factorial of **corpus** (`N` naive vs `D` docs-skill-authored) × **rag** (`b` baseline config vs `r` skill config) — every cell already has documents and runs a real RAG pipeline, so even `Nb` is not "no doc, no RAG."

Started editing `mk-corpus.py` to add an empty `Z` corpus and began wiring a floor.

## User

> _(model switched via `/model claude-opus-4-8[1m]`)_

Start over with Opus 4.8, I was using the wrong model

## Assistant

Restarted the approach on Opus 4.8. Recognized a genuine design fork that the request's wording ("baseline without any doc or RAG" → "docs only / RAG only / docs + RAG") didn't pin down, because the harness's existing 2×2 is *docs-quality × rag-quality*, not *docs-presence × rag-presence*. Asked the owner to choose how the floor should fit, via `AskUserQuestion` with three options: (A) add a true-zero floor cell and keep the existing factorial; (B) reframe the axes to presence on/off; (C) nest quality inside presence.

The owner chose **A — add a true-zero floor cell**.

Implemented option A:

- **`mk-corpus.py`** — emit an empty `Z/` corpus alongside `N`/`D`.
- **`docs-eval.py`** — added a `--no-retrieval` flag (the literal "no RAG" floor: build no index, run no retrieval, every query returns an empty ranked list ⇒ all IR metrics 0); made `--config` optional in that mode.
- **`scoreboard.py`** — added a "Baseline-first view" (floor → docs-only `Db` → RAG-only `Nr` → docs+RAG `Dr`, each as a Δ-lift above the floor; `Nb` shown as the naive reference), plus a floor row in the cell-means table; the 2×2 factorial stays unchanged. Refactored round selection into a shared helper and added a clean lift-line formatter (fixing a `++`/alignment glitch).
- **`check-retrieval.py`** help text, **`LOOP.md`** (floor runs first), and the prose docs (`SKILL.md`/`MATRIX.md`/`METRICS.md`/`SCENARIOS.md`) updated.

Verified end-to-end in a temp harness dir: the floor scores all-zero (5 queries, 0 missing), the four cells report as lifts above it, the scoreboard renders the requested order, and a no-floor TSV degrades gracefully to "(not run — add Z/--no-retrieval cell)". Noted that `gold.py validate` was already failing **before** my change — a pre-existing gold-set/docs-layout drift, unrelated to the floor.

## User

Make sure the improving docs and rag skills harness also test exported coding-session retrieval, not just code. OVERVIEW.md docs should be generated for exported transcripts, plus other subdirectories under docs/ as well (including docs/ itself).

## Assistant

Noted this as a second task and finished Task 1's remaining prose-doc edits first. Then mapped the surfaces with a 5-reader exploration workflow (OVERVIEW.md convention, the `export-coding-session` skill, the gold-set/corpus coverage + the path drift, plan/skill existence, and OVERVIEW-as-retrieval-target). Key findings: all six `OVERVIEW.md` files already exist (hand-written, no generator); the `docs`/`rag` skills don't exist yet (Phase 0 builds the harness first); 4 of 5 gold-fact primary paths are stale (date-dir drift); and `OVERVIEW.md` files were silently in-corpus despite the docstring claiming they were excluded.

## User

After you're done, /export-coding-session then use /vcs to merge, clean up, and push.

## Assistant

Acknowledged and queued those two steps for the end.

## User

For Task 2, what I meant is the harness should test coding session transcript and code (inception only for now) separately, and produce separate metrics so we can understand code vs natural language differences.

## Assistant

This clarification reframed Task 2 away from OVERVIEW.md generation and toward a **content-type axis with separate metrics**. Grepped the repo and found `inception/` — a real TanStack Start app (Vite 8, Bun, React 19 + React Compiler, `tsgo`) that an earlier session had scaffolded explicitly "as a target codebase for the `improving-docs-and-rag-skills` harness." That resolved "inception only for now": the code corpus is `inception/`.

Designed the change: facts carry a `domain` (`nl` = markdown docs incl. coding-session transcripts; `code` = the inception app), each scored against its own corpus, with a per-domain scoreboard comparison. Folded in the two adjacent bugs the exploration surfaced, since both directly affect the comparison's integrity. Gathered real, unique sentinels by reading `inception/`'s source/config and grepping transcripts for uniqueness.

Implemented across the scripts (tracked with a task list):

- **`gold.py`** — added a `domain` field to `Fact`; added `find_code_corpus_root` + a `kind="code"` branch in `load_corpus` (skips `node_modules`/build output/lockfiles); made `validate`/`build`/`score` domain-aware (each fact validated against its own corpus); added 3 code facts (router preload, React-Compiler wiring, `tsgo` typecheck) and 1 NL transcript fact (the inception-scaffold session); **fixed the 4 stale primary paths**; and **excluded `OVERVIEW.md`** from the corpus to match the documented firewall.
- **`docs-eval.py` / `check-retrieval.py`** — added `--corpus-kind {md,code}` + `--domain {nl,code}`; emit a new `domain` TSV column.
- **`scoreboard.py`** — added a "Content-type comparison — code vs natural language" view (per rag config), reading each domain's real corpus.
- **`mk-corpus.py`** — snapshot a `code/` corpus from `inception/`.
- Updated `LOOP.md`/`SKILL.md`/`METRICS.md`/`MATRIX.md`/`SCENARIOS.md`.

Verified: `gold.py validate` now passes across both domains (9 facts: 6 nl / 3 code; the OVERVIEW exclusion drops docs 56→50); the full pipeline runs the floor + four NL cells + two code cells; the scoreboard shows the code-vs-NL comparison; the `domain` TSV column and dev/held-out split filters work.

Then ran a **5-dimension adversarial review workflow** (review → verify each finding, 20 agents): gold correctness, eval-script back-compat, scoreboard robustness, doc/code consistency, and measurement integrity. It returned **10 confirmed findings** (5 false positives correctly dismissed). Fixed all 10:

- **gold.py** — a no-`inception/` checkout now degrades to nl-only with a warning (was hard-failing `validate`/`build`), via an `active_facts` filter.
- **docs-eval.py / check-retrieval.py** — added a `--domain`/`--corpus-kind` consistency guard (a mismatch could silently mis-grade via cross-domain sentinel overlap) and a note about the fixed `retrieval_hit@20` TSV column.
- **scoreboard.py** — gated the content-type section on round-selected rows; hardened `per_query_cell`/`floor_per_query` against an empty/NA metric cell; de-duped `key_metrics`; and added an honest caveat that code recall **saturates** (≈12 files < `top_k`) so only ndcg/mrr/precision discriminate code rankers.
- **SKILL.md / SCENARIOS.md / LOOP.md** — saturation caveat; re-attributed `--qrels-mode` to `check-retrieval.py`; fixed "from this skill's directory" → "from the repo root"; refreshed the gold-facts table (date-dir paths + all 9 facts + a domain column).

Re-verified every fix (graceful skip, the guard rejecting mismatches, no crash on NA, no duplicate column, no spurious code section across rounds, old-schema TSV still parses) and re-ran the full happy path. Updated the project memory note for the harness.

Then proceeded to export this session and hand off to `vcs`.
