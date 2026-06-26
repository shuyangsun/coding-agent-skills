---
title: "Improving-docs-and-rag harness: scaffold the `docs` skill + floor-vs-doc benchmark (0005)"
date: 2026-06-08
repo: "`coding-agent-skills` @ `main` (work isolated in jj workspace/bookmark `claude-docs-skill`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Opus 4.8, 1M context, thinking: high)"
summary: >-
  Used the `improving-docs-and-rag-skills` Phase-0 harness to measure the repo's docs
  (floor `Z` = no doc vs `Nb`/`Db` = naive/structured docs, `baseline-b` retrieval only —
  RAG deliberately not exercised), wrote benchmark report `0005`, scaffolded the initial
  `docs` skill, ran a 3-agent adversarial review that caught two contamination leaks + a
  corpus-poisoning hole, fixed them, then exported, rebased onto current `main`, and
  integrated.
---

<!-- markdownlint-disable MD013 MD024 -->

# Improving-docs-and-rag harness: scaffold the `docs` skill + floor-vs-doc benchmark (0005)

## User

Use the /improving-docs-rag-skills harness to start creating and working on the `docs` skill. Do not use or test RAGs yet, that does not exist. Benchmark baseline without any doc, then compare with with doc, save them under @docs/benchmarks/ with index `0005-`.

[Request interrupted by user]

## User

Use the /improving-docs-rag-skills harness to start creating and working on the `docs` skill. Do not use or test RAGs yet, that does not exist. Benchmark baseline without any doc, then compare with with doc, save them under @docs/benchmarks/ with index `0005-`.

## Assistant

Loaded the `improving-docs-and-rag-skills` skill and read its operational docs (`LOOP.md`, `SCENARIOS.md`, `METRICS.md`) plus the phase-0 memory note.

_Surveyed state (Bash/Read):_ the harness ships `gold.py`, `mk-corpus.py`, `docs-eval.py`, `check-retrieval.py`, `scoreboard.py` and `configs/baseline-b.json`, `configs/rag-r.json`. **No `docs` or `rag` skill existed yet** — greenfield. Benchmarks are date-foldered with a global `NNNN` index (existing 0000–0004 are all `vcs`), so `0005-` lands under `docs/benchmarks/2026-06-08/`.

The session-start hook had created an isolated jj workspace; the `vcs-check` guard refuses non-read-only commands from the shared default workspace, so I ran everything as `cd <workspace> && …`. Renamed the work to `claude-docs-skill` via `rename-work.sh` (jj workspace rename keeps the directory path stable).

_Interpretation of the request:_ floor `Z` (`docs-eval.py --no-retrieval`, every metric 0) is "baseline without any doc"; "with doc" = the structured-docs corpus `D` at the **control** retrieval config `baseline-b`. The `rag` skill (config `rag-r`) is deliberately not run. Added `Nb` (naive dump) as the reference that isolates structure.

_Ran the Phase-0 benchmark_ (self-contained runner under `$TMPDIR`, executed from the workspace):

- `gold.py validate` / `build` → 9 facts (6 `nl` + 3 `code`); `mk-corpus.py` → `Z`=0, `N`=54, `D`=54 docs.
- Floor `Z`, then `Nb` and `Db` under `baseline-b`, scored by `check-retrieval.py`; `scoreboard.py` for the lift view.

**Result (nl, n=6):**

| Metric | Floor `Z` (no doc) | With docs `Db` | Lift vs floor | Naive ref `Nb` |
| --- | ---: | ---: | ---: | ---: |
| retrieval_hit@20 | 0.000 | **0.833** (5/6) | **+0.833** | 0.833 |
| recall@20 | 0.000 | **0.642** | **+0.642** | 0.642 |
| ndcg@10 | 0.000 | 0.280 | +0.280 | 0.445 |
| mrr | 0.000 | 0.344 | +0.344 | 0.552 |

The floor→doc step (answerability 0 → 83%) is the dominant lever. But the **docs-only marginal at baseline is neutral/negative** (`Db`≈`Nb` on recall@20/hit@20; `Db` slightly worse on ndcg@10/mrr): fixed-256-word chunking is blind to headings, so structure has nothing to bite on — the coupling thesis (structure pays off only with structure-aware retrieval, i.e. the `rag` skill). `bench-conflict-time` (sentinels `380s`/`85s`) was missed by both corpora — a placeholder-embedder limit, not a doc defect.

_Wrote the deliverables_ (into the isolated workspace): `docs/benchmarks/2026-06-08/0005-docs-skill-floor-vs-doc.md` + co-located `…-metrics.tsv` (18 rows), and updated `docs/benchmarks/OVERVIEW.md`.

_Scaffolded the `docs` skill_ at `.agents/skills/docs/SKILL.md` (repo layout confirmed: every skill is a real dir under `.agents/skills/`, `.claude/skills` is a symlink). Findability-first, repo-agnostic, consumer-facing (so it must not reference the harness/gold queries). While writing it I caught a bug in the next-index shell snippet — the original `/[0-9]{4}-` pattern matched the `YYYY-` date folder and returned `2026`; rewrote it to read the filename prefix with base-10 handling.

_Adversarial review (Workflow, 3 parallel auditors):_ numbers-vs-TSV, skill (firewall/agnostic/snippet/bloat), and convention/links. Findings:

- **2 firewall leaks (major):** the skill's lexical-anchoring example reused the exact gold sentinels `380s`/`85s`, and a slug example reused the real gold issue `0007-orphan-empty-jj-head` — both would prime a blind WRITE-loop agent. Replaced with neutral, domain-free examples.
- **2 rounding nits:** docs-marginal `−0.165→−0.164` (ndcg) and `−0.208→−0.207` (mrr).
- **Deeper hole the audit implied:** the new report itself quotes gold sentinels, so it would poison future `N`/`D` corpora. Fixed `gold.py` `EXCLUDE_GLOBS` to exclude harness benchmark reports (`benchmarks/*docs-skill*` / `*rag-skill*` / `*docs-rag*`). The numbers auditor independently recomputed every figure from the TSV and confirmed accuracy; the convention auditor confirmed naming + all links resolve.

_Verified the fixes:_ re-ran the benchmark with `0005` now present in `docs/` — `D`/`N` stayed at 54 docs (report excluded), metrics byte-identical, `validate` passed, and a final firewall sweep on the skill found no leak tokens. Updated agent memory (new `docs-skill-scaffolded` note; corrected the stale `repo-local-vs-downloadable-skills` note that claimed a non-existent top-level `skills/`).

Reported the summary; left everything uncommitted in `claude-docs-skill`.

## User

Export session then integrate and push.

## Assistant

Loaded the `export-coding-session` and `vcs` skills.

_Discovered `main` had advanced_ (a parallel session): `jj log` showed `main` now at `docs(export): preserve verbatim user turns` with a sibling `claude-rag-skill` workspace (the `rag` work — not yet on `main`). `main` already contained coding-session `0034` (`0034-codex-session-export-verbatim.md`), so my export had to be `0035`; benchmarks on `main` still topped out at `0004`, so `0005` stayed free.

_Rebased only my change onto current `main`_ (`jj rebase -r claude-docs-skill -d main`), leaving the `claude-rag-skill` sibling untouched — clean, no conflicts. `next-index.sh` then correctly returned `0035`.

_Firewall for this transcript:_ coding-session transcripts are in the `nl` corpus, and this one contains gold sentinels/paraphrases, so I named it `0035-claude-improving-docs-and-rag-docs-skill.md` to match the existing `coding-sessions/*/*improving-docs-and-rag*.md` exclusion (no extra `gold.py` change needed). Wrote the transcript with generalized paths, ran the redaction scanner, then described the change and ran `integrate.sh` to land on `main` and pushed.
