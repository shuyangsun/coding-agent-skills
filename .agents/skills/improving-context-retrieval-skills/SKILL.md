---
name: improving-context-retrieval-skills
description: Iterative, measurement-driven harness for IMPROVING the three context-retrieval skills together — `updating-docs` (write findable docs), `setting-up-rag` (stand up retrieval over a doc set), and `retrieving-context` (the consumer that routes cloud→local→manual retrieval). Use ONLY while authoring or changing those three — never during normal development. It establishes a no-doc/no-RAG floor baseline first, then builds naive vs skill-authored corpora and baseline vs skill RAG configs, drives a skilled consumer over each cell, runs a deterministic in-process eval (BM25 + in-memory vectors) over a pinned gold set, and reports each treatment as a lift above the floor plus each skill's marginal effect AND their interaction (the coupling) so revisions are kept or reverted on the numbers.
---

# Improving the context-retrieval skills (one harness, three skills)

This is a **meta-skill**: a closed loop that makes three skills measurably better at
the same time —

- [`updating-docs`](../updating-docs/SKILL.md) — **write** docs so they are found
  (co-located with code and centralized under `docs/`),
- [`setting-up-rag`](../setting-up-rag/SKILL.md) — **stand up effective retrieval**
  over a given doc set (chunking, embeddings, contextual retrieval, hybrid fusion,
  reranking, query transforms, top-k, vector-DB config), local-first, and
- [`retrieving-context`](../retrieving-context/SKILL.md) — the **consumer** side:
  route to the best retrieval available (cloud → local → navigate the structure by
  hand) and retrieve well within whichever tier is reachable.

It uses a measurement-driven loop for docs+retrieval. You run rounds; each round
produces numbers; you keep the revisions that move the numbers and revert the ones
that don't.

> **Scope — authoring only.** Use this skill _only_ when authoring or changing
> `updating-docs`, `setting-up-rag`, or `retrieving-context`. It is never loaded
> during ordinary development, and the sub-agents under test must never see it or the
> gold queries (the **contamination firewall**, [SCENARIOS.md](SCENARIOS.md)).

Full design rationale lives in
[`docs/plans/2026-06-07/0002-improving-docs-and-rag-skills.md`](../../../docs/plans/2026-06-07/0002-improving-docs-and-rag-skills.md).
This file is the operational entry point.

## Why one harness for three skills (the coupling thesis)

How docs are **written** changes the **best** RAG setup (self-contained,
front-loaded docs let RAG use coarser chunks and skip costly per-chunk
contextualization); how RAG is **set up** changes how docs **should** be written
(heading-aware chunking rewards clean sections; a small local embedder rewards
explicit lexical anchors); and how the **consumer retrieves** changes what either is
worth (a consumer that grinds keyword search rewards different doc structure than one
that queries a hybrid index, and a consumer that never finds the local index wastes a
good one). The three are a **joint optimization**. The harness measures each skill's
marginal effect **and their interaction**, and a round may revise **one** of the three
while watching all of them.

The first two skills are separated by the 2×2 **corpus × rag** factorial below; the
third — `retrieving-context` — owns the **consumer plane** (which retrieval tier the
agent reaches for and how well it uses it), measured by the READ loop across both
consumer modes. A `retrieving-context` change is judged by whether it improves
consumer outcomes without regressing either mode or either factorial marginal.

## The keystone: no oracle, so three deterministic surrogates

Doc/retrieval quality has no perfect oracle — an LLM authors the corpus, the
`setting-up-rag` skill chooses the config, and a consumer driven by
`retrieving-context` does the querying.
[`scripts/gold.py`](scripts/gold.py) (the `scenario.py` analog — it emits the labels
**and** runs the scorers so they can't drift) replaces the oracle with three
deterministic surrogates:

1. **Gold-set IR metrics (PRIMARY, reproducible).** Version-pinned, graded BEIR
   `qrels` → precision@k, recall@k (recall@20 headline), MRR, nDCG@10. Label-pinned
   and order-independent ⇒ deterministic.
2. **Downstream sentinel factuality (SECONDARY).** The answer must **contain** a
   unique sentinel from a known-relevant doc — string containment, no judge in the
   gate; hard tier uses multi-sentinel containment.
3. **Convention lint (`updating-docs`) + config validity (`setting-up-rag`) + route
   correctness (`retrieving-context`).** [`check-convention.sh`](scripts/check-convention.sh)
   (durable file signals) and [`check-rag-config.sh`](scripts/check-rag-config.sh)
   (config well-formed, reproducible, provider-portable, beats baseline) — 100%
   mechanical; the consumer's tier choice is checked against what was actually
   provisioned for the cell.

An LLM-as-judge is permitted **only** as an advisory, non-gating signal.

## Two measurement planes and the 2×2 factorial

- **Plane 1 — Frozen retrieval gate (primary, bit-reproducible).** A fixed
  reference RAG over the **GOLD** corpus (a pinned snapshot of today's `docs/`)
  with pinned `qrels`. It does not move when any skill changes; a move here
  flags **instrument** drift, not skill quality.
- **Plane 2 — Skill effects via a 2×2 factorial, above an absolute floor.** Every
  cell is read as a **lift above the floor `Z`** — the genuine "no doc, no RAG"
  baseline: an **empty corpus** scored with retrieval turned **off**
  (`docs-eval.py --no-retrieval`), so every metric is identically 0. The floor is
  run **first** each round; the four treatment cells are two binary treatments on
  the same fact payload and gold queries:
  - **corpus** ∈ {`N` = naive dump, `D` = `updating-docs`-skill-authored}
  - **rag** ∈ {`b` = baseline config, `r` = `setting-up-rag`-skill config}

  |              | rag = `b`             | rag = `r`            |
  | ------------ | --------------------- | -------------------- |
  | (floor `Z`)  | `0` (no doc, no RAG)  | —                    |
  | corpus = `N` | `Nb` (control)        | `Nr` (rag-only gain) |
  | corpus = `D` | `Db` (docs-only gain) | `Dr` (co-designed)   |

  Read as the named conditions the scoreboard reports in order — **floor → docs-only
  (`Db`) → RAG-only (`Nr`) → docs+RAG (`Dr`)** — each as a lift above `Z` (`Nb` is
  the naive "neither-skill" reference between floor and treatments). Computed
  **per query (paired)** over the four cells (the floor is the reference, not part
  of the interaction math):
  - **`updating-docs` marginal** = `Db − Nb` and `Dr − Nr`
  - **`setting-up-rag` marginal** = `Nr − Nb` and `Dr − Db`
  - **Coupling (interaction)** = `(Dr − Db) − (Nr − Nb)`. Positive ⇒ co-design
    beats additive. This is the headline number that makes one harness coherent.

- **The consumer plane (`retrieving-context`).** Each cell is queried by a consumer
  driven by `retrieving-context` in one of two **modes** (below); the mode it picks
  and how well it retrieves within it is the third skill's signal. Held against the
  same gold set, a `retrieving-context` change reads as a shift in the SIMPLE/RAG
  outcomes, attributed separately from the corpus/rag axes.

Corpus `D` is LLM-authored and config `r` may use LLM contextualization, so
factorial cells are **distributions**: author **N ≥ 5 seeds** per cell, report
median + IQR, gate on a **paired sign/permutation test** whose CI excludes zero
across rounds. Use **PLAIN** (no-contextualization) retrieval as the noise-free
cross-round comparison and **FULL** as the corroborating arm.

## Content-type axis: natural language vs code vs image (separate metrics)

Retrieval behaves differently over **prose**, **code**, and **image-backed
evidence**, so the harness measures them **separately** and reports all three. Each
gold fact carries a `domain`:

- **`nl`** — natural-language markdown under `docs/`, including the exported
  **session transcripts** (long, dialog-shaped prose). This is the corpus
  the N/D/Z factorial above runs on.
- **`code`** — the repo's own [`inception/`](../../../inception) TanStack Start app
  (source + config), indexed in place ("inception only for now").
- **`image`** — image-backed project context from an external project passed with
  `--image-corpus`. Phase 0 indexes source/docs/session transcripts plus curated
  image-summary documents whose doc ids are the real image paths. Gold questions
  ask real development questions (for example, how an arm cutout works), with
  grade-2 relevance on code/NL context and grade-1 relevance on supporting image
  paths.

All domains run the **same** chunk→index→fuse→rerank path and the same configs;
only the file loader and which queries run change. `scoreboard.py` prints a
**natural-language-vs-code-vs-image** view (per rag config) on top of the
factorial. The factorial/floor stay an `nl` story; code and image are their own
columns. Code is scored via `--corpus-kind code --domain code`; image via
`--corpus-kind image --domain image --qrels-mode pinned` so primary project
context and supporting image paths remain distinct.

> **Caveat (Phase 0):** absolute recall is **not** cross-domain comparable while
> the code/image corpora are tiny (files < `top_k`): `recall@k` and
> `retrieval_hit@20` sit at ceiling, so only `ndcg@10`/`mrr`/`precision` tell
> rankers apart. Grow those corpora/fact sets (or shrink `top_k`) before reading
> their recall as signal; the scoreboard prints this caveat too.

## The metrics

| Metric           | Measures                                             | Mostly driven by                                                             | Made objective by                                           |
| ---------------- | ---------------------------------------------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------------- |
| **Precision**    | of retrieved, how many relevant                      | updating-docs + setting-up-rag                                               | graded `qrels`                                              |
| **Recall**       | of relevant, how many retrieved (recall@20 headline) | updating-docs + setting-up-rag                                               | graded `qrels`                                              |
| **Speed**        | index time + per-query latency (p50/p95)             | **setting-up-rag**                                                           | per-stage timers, same-host                                 |
| **Factuality**   | answer stays grounded in retrieved docs              | all three                                                                    | sentinel containment + closed-book control + advisory judge |
| **Token usage**  | context/read tokens at equal correctness (↓)         | **setting-up-rag** (ctx) / **retrieving-context** + **updating-docs** (read) | read from transcripts, never self-reported                  |
| **VCS boundary** | nested jj workspaces / Git worktrees are not indexed | **setting-up-rag** + harness loaders                                         | `check-vcs-boundary.py` (`vcs_boundary_ok=1`)               |

Precision through token usage are sliced by tier and difficulty. VCS boundary is
a hygiene metric: it must stay green, and it is interpreted separately from
retrieval-quality lift.

## Two consumer modes (the `retrieving-context` plane)

The consumer is driven by `retrieving-context`, which routes to the best retrieval
available. In the local harness that surfaces as two modes — the skill's Tier-3 and
Tier-2 paths (Tier-1 cloud is a later, separately-gated milestone):

- **SIMPLE** — no RAG; answer by ripgrep/file/keyword navigation of `docs/`
  (`retrieving-context`'s manual-structure floor). `setting-up-rag` does not
  participate, so SIMPLE is a joint **`updating-docs` × `retrieving-context`**
  outcome — and the guard that docs serve non-RAG consumers and that the consumer
  navigates structure well.
- **RAG** — the `setting-up-rag` pipeline, reached because `retrieving-context`
  routed to the local index; a joint **`updating-docs` × `setting-up-rag` ×
  `retrieving-context`** outcome. A `updating-docs` change that helps RAG but hurts
  SIMPLE still fails; a `retrieving-context` change that wins RAG but mis-routes
  SIMPLE still fails.

## The three loops (each round)

1. **WRITE-docs** (`new-corpus.sh --task write`, `_run-write.wf.js`, oracle
   `check-convention.sh`): a sub-agent with **only** `updating-docs` authors into an
   empty `docs/` from a fixed fact payload, against a seeded convention trap. Scored
   on `CONV_OK` + `WRITE_FINDABLE`.
2. **RAG-setup** (`apply-rag.sh`, `_run-rag.wf.js`, oracle `check-rag-config.sh`):
   a sub-agent with **only** `setting-up-rag`, given a corpus + provider profile,
   produces a `rag-config.json` **blind to the gold queries**. Scored on validity/
   reproducibility/portability + its marginal effect.
3. **READ/eval** (`new-corpus.sh --task read`, `_run-read.wf.js`, oracle
   `check-retrieval.py`): a **blind** consumer with **only** `retrieving-context`
   queries a (corpus × rag) cell in each mode; the gold set is scored. This is the
   shared outcome feeding the factorial **and** the consumer plane — it measures
   whether the consumer routes to the right tier and retrieves well within it.

The loops close: a `updating-docs` change that raises `CONV_OK` but lowers recall is
reverted; a `setting-up-rag` change that raises recall but balloons latency/tokens at
no factuality gain is reverted; a `retrieving-context` change that wins one mode but
regresses the other is reverted; a change to one skill that **degrades another's
marginal effect** (negative coupling) is flagged and reverted.

## Phased testing bed (cheapest-first)

- **Phase 0 — thin in-process eval (build + run first).** No services, no Docker,
  no eval-time LLM. [`scripts/docs-eval.py`](scripts/docs-eval.py) chunks + indexes
  a `(corpus, rag-config)` with **BM25 + an in-memory vector index**, runs the gold
  queries, emits the metrics TSV. Enough to compute all four cells **and** the
  interaction. **GO/NO-GO gate:** build Phase 1 only once Phase 0 shows a
  measurable, significant factorial signal.
- **Phase 1 — the local app (only past the GO gate).** TanStack Start + Qdrant +
  Ollama + Python sidecar; headless `POST /api/eval` taking a full `rag-config`;
  snapshotting; reproduction kit; owner chat UI. **Deferred** — do not build until
  the gate clears.

## Bundled scripts

Run from this skill's own directory (`<skill-dir>/scripts/`). All sandboxes live
under `$CONTEXT_RETRIEVAL_HARNESS_DIR` (default `$TMPDIR/context-retrieval-harness`);
only `metrics.tsv` persists. They require `python3`; Phase 0 needs **no** services
and **no** eval-time LLM.

| Script                                                    | Role                                                                                                                                                                                                                            |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `gold.py`                                                 | **Single source of truth**: emit per-corpus graded `qrels` + records, run surrogates, build-time validation, held-out split, firewall; owns the `nl`/`code`/`image` content-type domains and their corpus loaders.              |
| `docs-eval.py`                                            | Phase-0 thin eval: given `(corpus, rag-config)`, chunk + index (BM25 + in-memory vectors), run gold queries, emit ranked results + per-stage timings. `--no-retrieval` runs the floor (no index, no retrieval ⇒ all metrics 0). |
| `check-retrieval.py`                                      | READ oracle: precision/recall/MRR/nDCG + factuality, `KEY=VALUE` lines; `--corpus-kind code --domain code` and `--corpus-kind image --domain image` score non-NL runs, emitting a `domain` column.                              |
| `check-vcs-boundary.py`                                   | Hygiene metric: fixture nested Jujutsu workspaces + Git worktrees under a corpus root and assert loaders exclude them while still allowing a VCS root when selected directly.                                                   |
| `check-convention.sh`                                     | `updating-docs` WRITE oracle: durable file signals → `CONV_OK` / `WRITE_FINDABLE`.                                                                                                                                              |
| `check-rag-config.sh`                                     | `setting-up-rag` oracle: `rag-config.json` well-formed, reproducible, provider-portable; beats baseline.                                                                                                                        |
| `new-corpus.sh`                                           | Provision a round: `--task read\|write`; build Z (empty floor) + N/D (+ GOLD); seed the write convention trap.                                                                                                                  |
| `apply-rag.sh`                                            | Given a corpus + `rag-config.json`, chunk + (optionally) contextualize + snapshot + index per (corpus × config).                                                                                                                |
| `next-index.sh`                                           | Globally-unique zero-padded index **per type folder**; shared by `updating-docs` + the WRITE oracle.                                                                                                                            |
| `record-metrics.sh`                                       | One TSV row per `query × cell(corpus,rag) × mode × round`.                                                                                                                                                                      |
| `scoreboard.py`                                           | By round / by tier×mode / difficulty×tier **+ the 2×2 factorial view (marginal effects + interaction)**.                                                                                                                        |
| `_score.py`                                               | Glue: run oracles, parse `KEY=VALUE`, read per-agent output tokens **exactly** from transcript JSONLs (never `budget.spent()`, never self-reported).                                                                            |
| `_run-write.wf.js` / `_run-rag.wf.js` / `_run-read.wf.js` | Workflow runners for the three loops (`updating-docs` / `setting-up-rag` / `retrieving-context`); `JSON.parse(args)`; blind to gold labels.                                                                                     |
| `rm-corpus.sh`                                            | Teardown, guarded to `$CONTEXT_RETRIEVAL_HARNESS_DIR` only.                                                                                                                                                                     |

Run `bash <skill-dir>/scripts/<name>.sh --help` (or `python3 … --help`) for usage.
Round procedure and the revise/revert discipline are in [LOOP.md](LOOP.md); metric
definitions and the scoreboard in [METRICS.md](METRICS.md); corpora, traps, and the
firewall in [SCENARIOS.md](SCENARIOS.md); tier/mode/difficulty sampling in
[MATRIX.md](MATRIX.md).

## Exit condition (the bar)

Stop only when, across **multiple consecutive rounds**, in **both consumer modes**,
across the **difficulty ladder** and **embedding + generation tiers**:

1. recall@k / precision@5 / nDCG@10 high and stable-or-rising on cell **`Dr`**,
   relative to the GOLD baseline measured **on the same host** that round;
2. **both factorial marginals positive with CI excluding zero** (`updating-docs` and
   `setting-up-rag`), surviving both chunker choices;
3. **`retrieving-context` routes correctly** — it reaches the best provisioned tier
   for each cell and improves SIMPLE+RAG outcomes without regressing either mode;
4. **coupling non-harmful** — every pairwise interaction ≥ 0 and stable;
5. **speed** — `retrieval_ms` p50/p95 low and trending-down-or-stable (same host);
6. **factuality** high — multi-sentinel grounded, closed-book control clean;
7. **hygiene closes** — `CONV_OK` + `WRITE_FINDABLE` (updating-docs) and
   `rag_config_ok` (setting-up-rag);
8. **no tier/mode left behind** — small/mid tiers clear it; a win in RAG that loses SIMPLE fails;
9. **token usage** low and stable-or-down per tier at equal correctness;
10. **local-first holds** — the bar is met with local providers; cloud parity is a later, separately-gated milestone;
11. **revert discipline / anti-bloat** — every revision judged by the scoreboard; one small attributable change to one skill at a time; fresh indexes; noise dropped; all three skills kept compact.
