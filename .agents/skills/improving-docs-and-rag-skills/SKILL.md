---
name: improving-docs-and-rag-skills
description: Iterative, measurement-driven harness for IMPROVING two skills at once — `docs` (read/write docs) and `rag` (set up retrieval over a doc set). Use ONLY while authoring or changing `docs` or `rag` — never during normal development. It builds naive vs skill-authored corpora and baseline vs skill RAG configs, runs a deterministic in-process eval (BM25 + in-memory vectors) over a pinned gold set, and reports each skill's marginal effect AND their interaction (the coupling) so revisions are kept or reverted on the numbers.
---

# Improving the `docs` and `rag` skills (one harness, two skills)

This is a **meta-skill**: a closed loop that makes two skills measurably better at
the same time —

- [`docs`](../docs/SKILL.md) — read/search and **write** docs (co-located with
  code and centralized under `docs/`), and
- [`rag`](../rag/SKILL.md) — **set up effective retrieval** over a given doc set
  (chunking, embeddings, contextual retrieval, hybrid fusion, reranking, query
  transforms, top-k, vector-DB config), local-first.

It is the [`improving-vcs-skill`](../improving-vcs-skill/SKILL.md) pattern applied
to docs+retrieval. You run rounds; each round produces numbers; you keep the
revisions that move the numbers and revert the ones that don't.

> **Scope — authoring only.** Use this skill _only_ when authoring or changing
> `docs` or `rag`. It is never loaded during ordinary development, and the
> sub-agents under test must never see it or the gold queries (the **contamination
> firewall**, [SCENARIOS.md](SCENARIOS.md)).

Full design rationale lives in
[`docs/plans/0002-improving-docs-and-rag-skills.md`](../../../docs/plans/0002-improving-docs-and-rag-skills.md).
This file is the operational entry point.

## Why one harness for two skills (the coupling thesis)

How docs are **written** changes the **best** RAG setup (self-contained,
front-loaded docs let RAG use coarser chunks and skip costly per-chunk
contextualization); and how RAG is **set up** changes how docs **should** be
written (heading-aware chunking rewards clean sections; a small local embedder
rewards explicit lexical anchors). The two are a **joint optimization**. The
harness measures each skill's marginal effect **and their interaction**, and a
round may revise **either** skill while watching both.

## The keystone: no oracle, so three deterministic surrogates

`vcs` works because the correct merge is *computable*. Doc/retrieval quality has
**no such oracle** — an LLM authors the corpus and the `rag` skill chooses the
config. [`scripts/gold.py`](scripts/gold.py) (the `scenario.py` analog — it emits
the labels **and** runs the scorers so they can't drift) replaces the oracle with
three deterministic surrogates:

1. **Gold-set IR metrics (PRIMARY, reproducible).** Version-pinned, graded BEIR
   `qrels` → precision@k, recall@k (recall@20 headline), MRR, nDCG@10. Label-pinned
   and order-independent ⇒ deterministic.
2. **Downstream sentinel factuality (SECONDARY).** The answer must **contain** a
   unique sentinel from a known-relevant doc — string containment, no judge in the
   gate; hard tier uses multi-sentinel containment.
3. **Convention lint (`docs`) + config validity (`rag`).**
   [`check-convention.sh`](scripts/check-convention.sh) (durable file signals) and
   [`check-rag-config.sh`](scripts/check-rag-config.sh) (config well-formed,
   reproducible, provider-portable, beats baseline) — 100% mechanical.

An LLM-as-judge is permitted **only** as an advisory, non-gating signal.

## Two measurement planes and the 2×2 factorial

- **Plane 1 — Frozen retrieval gate (primary, bit-reproducible).** A fixed
  reference RAG over the **GOLD** corpus (a pinned snapshot of today's `docs/`)
  with pinned `qrels`. It does not move when either skill changes; a move here
  flags **instrument** drift, not skill quality.
- **Plane 2 — Skill effects via a 2×2 factorial.** Two binary treatments on the
  same fact payload and gold queries:
  - **corpus** ∈ {`N` = naive dump, `D` = `docs`-skill-authored}
  - **rag** ∈ {`b` = baseline config, `r` = `rag`-skill config}

  |              | rag = `b`            | rag = `r`              |
  | ------------ | -------------------- | ---------------------- |
  | corpus = `N` | `Nb` (control)       | `Nr` (rag-only gain)   |
  | corpus = `D` | `Db` (docs-only gain)| `Dr` (co-designed)     |

  Computed **per query (paired)**:
  - **`docs` marginal** = `Db − Nb` and `Dr − Nr`
  - **`rag` marginal** = `Nr − Nb` and `Dr − Db`
  - **Coupling (interaction)** = `(Dr − Db) − (Nr − Nb)`. Positive ⇒ co-design
    beats additive. This is the headline number that makes one harness coherent.

Corpus `D` is LLM-authored and config `r` may use LLM contextualization, so
factorial cells are **distributions**: author **N ≥ 5 seeds** per cell, report
median + IQR, gate on a **paired sign/permutation test** whose CI excludes zero
across rounds. Use **PLAIN** (no-contextualization) retrieval as the noise-free
cross-round comparison and **FULL** as the corroborating arm.

## The five metrics (sliced by tier and difficulty)

| Metric | Measures | Mostly driven by | Made objective by |
| --- | --- | --- | --- |
| **Precision** | of retrieved, how many relevant | docs + rag | graded `qrels` |
| **Recall** | of relevant, how many retrieved (recall@20 headline) | docs + rag | graded `qrels` |
| **Speed** | index time + per-query latency (p50/p95) | **rag** | per-stage timers, same-host |
| **Factuality** | answer stays grounded in retrieved docs | docs + rag | sentinel containment + closed-book control + advisory judge |
| **Token usage** | context/read tokens at equal correctness (↓) | **rag** (ctx) / **docs** (read) | read from transcripts, never self-reported |

## Two consumer modes

- **SIMPLE** — no RAG; answer by ripgrep/file/keyword over `docs/`. The `rag`
  skill does not participate, so SIMPLE is primarily a **`docs`** outcome and the
  guard that docs serve non-RAG consumers.
- **RAG** — the `rag` skill's configured pipeline; a joint **`docs` × `rag`**
  outcome. A `docs` change that helps RAG but hurts SIMPLE still fails.

## The three loops (each round)

1. **WRITE-docs** (`new-corpus.sh --task write`, `_run-write.wf.js`, oracle
   `check-convention.sh`): a sub-agent with **only** `docs` authors into an empty
   `docs/` from a fixed fact payload, against a seeded convention trap. Scored on
   `CONV_OK` + `WRITE_FINDABLE`.
2. **RAG-setup** (`apply-rag.sh`, `_run-rag.wf.js`, oracle `check-rag-config.sh`):
   a sub-agent with **only** `rag`, given a corpus + provider profile, produces a
   `rag-config.json` **blind to the gold queries**. Scored on validity/
   reproducibility/portability + its marginal effect.
3. **READ/eval** (`new-corpus.sh --task read`, `_run-read.wf.js`, oracle
   `check-retrieval.py`): a **blind** consumer queries a (corpus × rag) cell; the
   gold set is scored. This is the shared outcome feeding the factorial.

The loops close: a `docs` change that raises `CONV_OK` but lowers recall is
reverted; a `rag` change that raises recall but balloons latency/tokens at no
factuality gain is reverted; a change to one skill that **degrades the other's
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
under `$DOCS_RAG_HARNESS_DIR` (default `$TMPDIR/docs-rag-harness`); only
`metrics.tsv` persists. They require `python3`; Phase 0 needs **no** services and
**no** eval-time LLM (match the `vcs` harness's restraint).

| Script | Role |
| --- | --- |
| `gold.py` | **Single source of truth**: emit per-corpus graded `qrels` + records, run surrogates, build-time validation, held-out split, firewall. |
| `docs-eval.py` | Phase-0 thin eval: given `(corpus, rag-config)`, chunk + index (BM25 + in-memory vectors), run gold queries, emit ranked results + per-stage timings. |
| `check-retrieval.py` | READ oracle: precision/recall/MRR/nDCG + factuality, `KEY=VALUE` lines. |
| `check-convention.sh` | `docs` WRITE oracle: durable file signals → `CONV_OK` / `WRITE_FINDABLE`. |
| `check-rag-config.sh` | `rag` oracle: `rag-config.json` well-formed, reproducible, provider-portable; beats baseline. |
| `new-corpus.sh` | Provision a round: `--task read\|write`; build N/D (+ GOLD); seed the write convention trap. |
| `apply-rag.sh` | Given a corpus + `rag-config.json`, chunk + (optionally) contextualize + snapshot + index per (corpus × config). |
| `next-index.sh` | Globally-unique zero-padded index **per type folder**; shared by `docs` + the WRITE oracle. |
| `record-metrics.sh` | One TSV row per `query × cell(corpus,rag) × mode × round`. |
| `scoreboard.sh` | By round / by tier×mode / difficulty×tier **+ the 2×2 factorial view (marginal effects + interaction)**. |
| `_score.py` | Glue: run oracles, parse `KEY=VALUE`, read per-agent output tokens **exactly** from transcript JSONLs (never `budget.spent()`, never self-reported). |
| `_run-write.wf.js` / `_run-rag.wf.js` / `_run-read.wf.js` | Workflow runners for the three loops; `JSON.parse(args)`; blind to gold labels. |
| `rm-corpus.sh` | Teardown, guarded to `$DOCS_RAG_HARNESS_DIR` only. |

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
2. **both marginal effects positive with CI excluding zero** (`docs` and `rag`),
   surviving both chunker choices;
3. **coupling non-harmful** — interaction ≥ 0 and stable;
4. **speed** — `retrieval_ms` p50/p95 low and trending-down-or-stable (same host);
5. **factuality** high — multi-sentinel grounded, closed-book control clean;
6. **hygiene closes** — `CONV_OK` + `WRITE_FINDABLE` (docs) and `rag_config_ok` (rag);
7. **no tier/mode left behind** — small/mid tiers clear it; a win in RAG that loses SIMPLE fails;
8. **token usage** low and stable-or-down per tier at equal correctness;
9. **local-first holds** — the bar is met with local providers; cloud parity is a later, separately-gated milestone;
10. **revert discipline / anti-bloat** — every revision judged by the scoreboard; one small attributable change to one skill at a time; fresh indexes; noise dropped; both skills kept compact.
