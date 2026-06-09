# Phase 3 Pre-Work — RAG optimization benchmark harness

- **Date:** 2026-06-09
- **Status:** **Pre-work COMPLETE; Phase 3 (Wave 0+) NOT started.** The readiness gate
  is green. No baseline has been run and no baseline config has been declared — that is
  Wave 0, the first step of Phase 3.
- **Plan:** [`0008-consolidated-rag-optimization-phase-2.md`](../0008-consolidated-rag-optimization-phase-2.md) §"Phase 3 Pre-Work"
- **Gold set:** [`0003-rag-eval-set-phase-1/eval-set.json`](../0003-rag-eval-set-phase-1/eval-set.json) (207 questions, 6 repos)

This directory is the **reusable benchmark harness** for the Phase-3 RAG-optimization
campaign: it loads the 207-query gold set, defines per-repo corpora, indexes with a
rich dual-field payload, builds graded qrels, controls for contamination, and emits
slice-aware metrics. It is **campaign infrastructure**, deliberately kept out of the
portable `setting-up-rag` skill (see decisions below).

**Code and docs are one retrieval task.** Each repo is indexed as a SINGLE combined
corpus (code + markdown together) and every query retrieves across both — code often
needs its docs and docs often need the code. `domain` (code vs nl) is a **reporting
slice only**: metrics aggregate total and split by code/doc, but the retriever never
filters on type. 12 gold questions even have primaries spanning both code and docs
(e.g. `CHUNKING.md` + `rag_lib.py`), so combined retrieval is mandatory, not optional.

Run the readiness gate any time:

```bash
python3 harness/validate_prework.py        # GO / NO-GO across 6 checks; exit 0 == ready
```

## Why here, and the keep/revert discipline

- **Location.** A sibling subdir of the consolidated plan, mirroring the precedent set
  by [`0003-rag-eval-set-phase-1/`](../0003-rag-eval-set-phase-1/) (which puts
  `verify.py` beside the data). Prior real-Qdrant benchmarks `0008`/`0009` likewise kept
  their runners under `docs/benchmarks/`, **not** inside the skill. Keeping the harness
  here keeps the portable, downloadable `setting-up-rag` skill unbloated.
- **This subtree is hard-excluded from the `coding-agent-skills` corpus** (see
  `corpus_manifest.exclude_globs` and the matching `gold.py` `EXCLUDE_GLOBS`), so the
  harness can never contaminate the corpus it measures.
- **Nothing in the shipped skill was changed except a contamination fix.** The only edit
  outside this dir is adding the eval-set + consolidated-plan globs to
  `improving-context-retrieval-skills/scripts/gold.py` `EXCLUDE_GLOBS`. Payload
  enrichment, the comprehensive code-extension set, the dual-field schema, and chunker
  changes all live **harness-side**; per the plan's keep/revert discipline they are
  promoted into `setting-up-rag` only once a benchmark proves a win.

## Key findings from the pre-work audits

| Finding                          | Detail                                                                                                                                                                                                                  | Consequence                                                                                                                                                                                              |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Code-extension gap**           | Shipped `CODE_EXTS` is JS/TS/Python-only; **68 distinct gold primaries** (all C++/CUDA `.cc`/`.h`/`.cuh`, `CMakeLists.txt`, `.yml`, `.sh`) would not load.                                                              | Harness defines a comprehensive language-aware extension set (`corpus_manifest.LANG_BY_EXT`). Without it the code domain is **empty** for 4 of 6 repos.                                                  |
| **One combined corpus per repo** | Code + docs are indexed/retrieved together; `domain` is a reporting slice, never a corpus partition. **12 questions have primaries spanning both code and docs**; 9 more cite a primary whose file-type ≠ their domain. | A code question retrieves docs and vice versa. Demonstrated: a code question retrieved both its `.h` and its `.md` primary from one index; 29/30 alpha-zero-api queries pulled a code+doc mix in top-20. |
| **Contamination surface**        | `coding-agent-skills`: 31 synthesis docs in corpus, **11** questions legitimately cite one; `website`: 14 / 2; Alpha-Zero repos: 0.                                                                                     | Hard-exclude only the eval set + consolidated plan (never a legit primary). Use a **per-query** check for plans/research/benchmarks so the 13 legit citations are spared.                                |
| **Chunk integrity**              | `raw_text` byte-verbatim and **every gold sentinel fits within one chunk** in all 6 repos at baseline chunk size.                                                                                                       | The deterministic sentinel gate works at chunk level for all 207 questions.                                                                                                                              |
| **Split**                        | Stable hash → **dev 96 / held-out 111** (same algorithm as `gold.py`).                                                                                                                                                  | Tune on dev, report held-out.                                                                                                                                                                            |
| **Corpus size**                  | Largest: `alpha-zero` 219 code files/1.9 MB; `website` 203 md/1.8 MB. ~9k chunks total.                                                                                                                                 | Wave-0 indexing on CPU FastEmbed + embedded Qdrant is tractable.                                                                                                                                         |

## Pre-work checklist (plan §"Phase 3 Pre-Work" → status)

**Harness and Gold-Set Wiring**

1. External gold-set loader — **done** (`gold_loader.py`, preserves every field + adds split).
2. Validate sentinels before every run — **done** (`verify.py` re-run; wired into `validate_prework.py`).
3. Graded qrels (grade 2 primary; grade 1 corroborating) — **done** (`gold_loader.build_file_qrels`; chunk-level grade-1 is built at index time by the runner).
4. Deterministic dev/held-out split — **done** (`gold_loader.split_of`, hash parity).
5. Index per repo (ONE combined code+docs corpus per repo) — **done** (`corpus_manifest.py`, 6 repos, comprehensive exts). Code-vs-doc is a metric slice (`slice.domain`), **not** a separate corpus; the retriever is type-blind (see "Code and docs are one retrieval task" above).
6. One row per query × repo × domain × config — **done** (`metrics.py` `TsvWriter`, slice columns; aggregate total + by-domain downstream).
7. Separate retrieval/packing/generation/verification metrics — **done** (`metrics.py` channel prefixes `ret.`/`pack.`/`gen.`/`ver.`).

**Contamination and Self-Reference Controls**

1. Hard-exclude eval files — **done** (`gold.py` + `corpus_manifest.exclude_globs`).
2. Hard-exclude the consolidated plan — **done** (same).
3. Per-query contamination check for synthesis docs — **done** (`contamination.py`).
4. Non-echo rule re-checked — **done** (`verify.py`: 207/207, 0 echo).
5. Closed-book + wrong-context controls — **scaffolded** (`contamination.closed_book_run` / `wrong_context_run` + config arms; the runner executes them in Wave 0).

**Index Payload and Storage Changes** — **done** (`enriched_index.py`): `repo, domain(kind), lang, path, heading_path, symbol, parent_id, chunk_idx, n_chunks, start/end byte, start/end line, parent span`, plus dual `raw_text` (verbatim) / `contextualized_text` (retrieval). Session/transcript metadata (session id, turn, mentioned-files) is **deferred to Wave 4**.

**Baseline and Benchmark Harness** — config arms **defined** (`configs/*.json`); report/TSV/JSON file conventions documented. Running the baselines is **Wave 0**.

**Local Dependencies** — skill venv has FastEmbed + Qdrant; `rapidfuzz` installed; `ripgrep`/Docker present. External IR libs (`pytrec_eval`/`ranx`/`ir_measures`) **intentionally not installed** — `gold.py`'s scorer is the deterministic IR core; they are advisory cross-checks. `tree-sitter`/SQLite-FTS5/`networkx` are **deferred** to the waves that need them (2/5).

**Local LLM and GPU Setup** — **deferred to Wave 4** by design (the plan: "No local LLM is required for the first baseline"). Re-verify model cards at campaign time before pinning.

## Files

| File                          | Role                                                                                                                                                            |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `harness/corpus_manifest.py`  | Per-repo corpus roots, comprehensive language-aware exts, skip dirs, hard exclusions, VCS-boundary pruning. `load_repo_corpus()` with the cross-kind backstop.  |
| `harness/gold_loader.py`      | Load `eval-set.json` → `Question` records (+ split); `by_repo_domain`, `scored_corpus`, `build_file_qrels`, `validate_reachability`, `summary`.                 |
| `harness/enriched_index.py`   | Span-tracking chunker (verbatim `raw_text` + byte/line offsets) + rich dual-field Qdrant indexer (wraps `rag_lib`). `chunk-report` is a stdlib self-test.       |
| `harness/contamination.py`    | Per-query synthesis-doc contamination check; closed-book / wrong-context control-run generators; `surface` report.                                              |
| `harness/metrics.py`          | Slice-aware TSV schema (36 cols, 7 channels) + writer; `retrieval_metrics` (reuses `gold.py` scorer, adds primary-file split + sentinel coverage).              |
| `harness/make_configs.py`     | Generates the Wave-0 arm configs from the shipped `rag-config.json`.                                                                                            |
| `harness/validate_prework.py` | One-command GO/NO-GO readiness gate (the 6 checks above).                                                                                                       |
| `configs/*.json`              | The Wave-0 arms: `plain-current`, `plain-current-no-rerank`, `bm25-only`, `dense-only`, `closed-book`, `wrong-context`, `manual-simple`, `prefetch-topn-sweep`. |

## How to use it (commands)

```bash
H=docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/harness
VENV=~/.cache/rag-skill/venv/bin/python

python3 $H/validate_prework.py                       # readiness gate
python3 $H/gold_loader.py summary                    # slice tallies
python3 $H/gold_loader.py qrels --sentinel-grade1    # file-level graded qrels per cell
python3 $H/contamination.py surface                  # contamination surface
python3 $H/enriched_index.py chunk-report --repo alpha-zero   # stdlib chunk self-test
$VENV    $H/enriched_index.py index --repo alpha-zero --collection phase3_az --local  # needs venv
python3 $H/metrics.py schema                         # TSV column legend
```

## Wave-0 runner contract (what Phase 3 builds on top of this)

The harness provides data + indexing + scoring + controls. The **Wave-0 runner**
(Phase 3, not built here) wires them into a loop:

1. For each arm config, resolve `retrieval_mode`:
   - `hybrid` → shipped `query.py` path over the enriched collection;
   - `dense-only`/`bm25-only` → single-arm `query_points` (the runner implements this; shipped `query.py` only does hybrid);
   - `closed-book` → `contamination.closed_book_run` (empty context);
   - `wrong-context` → `contamination.wrong_context_run` over the real run;
   - `manual-rg` → `ripgrep` over the repo, no index.
2. Index per repo via `enriched_index.index_repo` — ONE combined code+docs collection
   per repo (`kinds=("md","code")`). No per-type indexes; the retriever is type-blind.
3. Score each query with `metrics.retrieval_metrics` against `gold_loader.build_file_qrels`
   over `gold_loader.combined_corpus(repo)`, passing retrieved chunk `raw_text` (sentinel
   coverage) and `kind` (the `frac_code/frac_md` diagnostic); flag contamination with
   `contamination.check_query`.
4. Emit one `metrics.TsvWriter` row per (query × arm); aggregate **total AND by code/doc
   domain**, plus repo, category, difficulty, multiplicity, split, source.
5. Write `docs/benchmarks/YYYY-MM-DD/NNNN-<arm>-<scope>.md` (+ `-metrics.tsv` /
   `-config.json` / `-summary.json`). Record latency + index time + context tokens.
6. **Then** declare the baseline config that later waves must beat.

## Explicit non-goals of this pre-work

- No baseline was run; no baseline config declared (Wave 0).
- The shipped `setting-up-rag` index/query were not modified (promote on measured wins).
- No GPU/LLM stack, no Docker Qdrant server (embedded suffices for dev), no AST/tree-sitter
  chunking, no contextual-retrieval LLM headers — all are later-wave work.
