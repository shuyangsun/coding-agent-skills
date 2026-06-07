# Plan: `improving-docs-and-rag-skills` — a harness that co-optimizes a `docs` skill and a `rag` skill

- **Date created:** 2026-06-07
- **Last updated:** 2026-06-07
- **Status:** Draft for review (plan only — do not build yet)
- **Author:** Claude (Opus 4.8), workspace `claude-improving-docs-harness-plan`
- **Repo:** `coding-agent-skills`
- **Scope:** This is a **plan**, not an implementation. It describes how to build
  `improving-docs-and-rag-skills` (a meta-skill) and the local app it drives. It
  does not author the `docs` skill, the `rag` skill, the harness, or the app.
- **Filed flat** as `docs/plans/0002-…` to match the directory's current
  convention (`0001` is flat); §10 proposes migrating all of `docs/` to dated
  subdirs, after which this would move to `docs/plans/2026-06-07/0002-…`.

---

## 0. Read this first (the whole plan in one screen)

**Goal.** Build `improving-docs-and-rag-skills`: a measurement-driven meta-skill
that iteratively improves **two** skills at once, exactly as
[`improving-vcs-skill`](../../.agents/skills/improving-vcs-skill/SKILL.md) improves
[`vcs`](../../.agents/skills/vcs/SKILL.md):

- **`docs`** — teaches agents to **read/search** and **write** docs (co-located
  with code for simple agents and as RAG context, and centralized under `docs/`
  under one convention). Concerned **solely** with docs.
- **`rag`** — teaches agents to **set up effective RAG over a given set of docs**:
  choosing and tuning chunking, embeddings, contextual retrieval, hybrid (sparse +
  dense) fusion, reranking, query transforms, top-k, and vector-DB config.
  Concerned **solely** with retrieval setup. Works for **local and cloud** LLM /
  vector-DB providers; **local-first** to bound scope.

**Why one harness for both — the coupling thesis.** How docs are *written* changes
the *best* RAG setup (self-contained, front-loaded docs let RAG use coarser chunks
and skip costly per-chunk contextualization); and how RAG is *set up* changes how
docs *should* be written (heading-aware chunking rewards clean sections; a small
local embedder rewards explicit lexical anchors). The two are a **joint
optimization**. The harness measures each skill's marginal effect **and their
interaction**, and lets a round revise **either** skill while watching both.

**The five outcome metrics** (every one sliced by model tier and query difficulty):

| Metric | What it measures | Mostly driven by | Made objective by |
| --- | --- | --- | --- |
| **Precision** | of retrieved docs, how many are relevant | docs + rag | graded `qrels` |
| **Recall** | of relevant docs, how many retrieved (recall@20 headline) | docs + rag | graded `qrels` |
| **Speed** | index time + per-query retrieval latency (p50/p95) | **rag** | app per-stage timers, same-host trend |
| **Factuality** | answer stays **grounded** in retrieved docs (no hallucination) | docs + rag | sentinel containment + closed-book control + advisory judge |
| **Token usage** | context/read tokens to answer *at equal correctness* (↓) | **rag** (ctx) / **docs** (read) | read from transcripts, never self-reported |

**The keystone, and the one hard problem.** `vcs` works because the correct merge
is *computable* — a deterministic oracle. **Doc/retrieval quality has no such
oracle.** The plan replaces it with **deterministic surrogates** (§2) and is honest
about which numbers are bit-reproducible vs distributions. Three corrections are
load-bearing throughout:

- **Two measurement planes** (§3): a **frozen retrieval gate** (fixed corpus +
  fixed reference RAG + pinned `qrels`, bit-reproducible) is the primary number;
  the **skill-effect plane** is inherently nondeterministic and reported as
  **distributions over N seeds with paired tests**.
- **A 2×2 factorial** (§3): corpus authoring {naive, `docs`-skill} × RAG config
  {baseline, `rag`-skill}. The **interaction term is the coupling signal** — this
  is what makes one harness for two skills coherent rather than two harnesses
  glued together.
- **Graded, multi-relevant `qrels`** (§6): this repo's own facts disprove "one
  sentinel = one doc" (`ORPHAN_EMPTY_HEADS` is in 5 docs, `380s` in 2).

**Build it phased, cheapest-first** (§7). Do **not** build the TanStack + Qdrant +
Ollama + Docker stack first. **Phase 0** is a thin in-process eval (BM25 +
in-memory vectors, one CLI) that proves a measurable factorial signal exists. Only
past that GO gate build the **Phase 1** local app — which is also the owner-facing
repo-Q&A tool, and the substrate the `rag` skill configures.

**Sections:** 1 the three skills & coupling · 2 the keystone · 3 planes,
corpora & the factorial · 4 the three loops · 5 two consumer modes · 6 gold
dataset · 7 phased testing bed · 8 scripts · 9 metrics & scoreboard · 10
convention standardization · 11 the loop & revert discipline · 12 exit bar · 13
risks · 14 open questions · 15 build sequence.

---

## 1. The three skills and the coupling

```
vcs  ←improves─ improving-vcs-skill                       (exists today)
docs ┐
     ├←improves─ improving-docs-and-rag-skills            (this plan)
rag  ┘          └── drives ──> docs-eval app (local; Phase 0 CLI → Phase 1 TanStack/Qdrant/Ollama)
```

**`docs` skill (built later) — solely reading and writing docs.** Repo-agnostic.
*Write:* front-loaded high-signal openings, one concept per file, descriptive kebab
filenames, an `OVERVIEW.md` per directory, stable anchors, the centralized-docs
convention (§10), sync up the tree on every change. *Read:* start at the nearest
`OVERVIEW.md`, follow links, judge relevance from front-matter + filename, grep
numbered slugs / dated folders, detect stale-vs-source. Its **testable invariants**
(the `vcs` "mode detection" analog): `frontload_ok`, `filename_descriptive`,
`overview_coverage`, `chunk_size_ok`, `self_context_ok`, `anchor_stable`,
`sync_freshness` — each lintable **and** tied to a retrieval outcome (§10).

**`rag` skill (built later) — solely setting up effective RAG over a given doc
set.** Repo-agnostic; **local-first**, cloud-capable behind the same config schema.
There are many knobs and competing algorithms, so the skill teaches an agent **how
to choose and tune** them for a given corpus and provider, not one fixed recipe.
The decision surface it owns:

- **Chunking** — strategy (heading-aware / recursive / semantic / fixed-grid),
  size, overlap.
- **Embeddings** — model choice (local: `nomic-embed-text`, `bge-*`, …; cloud
  later), dimension, normalization.
- **Contextual retrieval** (per
  <https://www.anthropic.com/engineering/contextual-retrieval>) — whether to
  prepend an LLM-generated situating blurb per chunk, the prompt, and the
  cost/benefit tradeoff.
- **Lexical / hybrid** — BM25 or SPLADE sparse, fusion (RRF or weighted), the
  dense/sparse balance.
- **Reranking** — on/off, model (`bge-reranker-*`), top-N → top-k.
- **Query transforms** — rewriting / expansion / HyDE (optional).
- **Retrieval params** — top-k, prefetch N, score thresholds, **metadata
  filtering** that consumes the `docs` convention's front-matter (type/date/tags).
- **Vector-DB config** — Qdrant collection params (HNSW `m`/`ef`, quantization);
  the provider abstraction (local Qdrant + Ollama first; hosted DB + cloud
  embeddings as a later flag).

Its **testable invariants** (the `rag` analog of `vcs` "conflict etiquette"): the
chosen config is **declarative and reproducible** (`rag-config.json`, pinned +
version-stamped); it **beats a naive baseline config** on the gold set; it stays
**provider-portable** (local↔cloud) for the same logical config; and it is
**justified by doc-set properties**, not brute-forced against the gold queries
(validated on held-out queries — §6).

**The coupling, made concrete (the thing the harness exploits):**

- *docs → rag:* well-front-loaded, self-contained docs let `rag` use coarser
  chunks and **skip or limit** per-chunk contextualization (an LLM call per chunk)
  → cheaper indexing, fewer context tokens at equal recall. Poorly structured docs
  force small chunks + aggressive contextualization + reranking.
- *rag → docs:* if `rag` settles on heading-aware chunking, `docs` should produce
  semantically-complete sections under clean headings; if `rag` uses a small local
  embedder, `docs` should carry the explicit lexical anchors users actually search.

The harness's **interaction term** (§3) quantifies this, and the revise loop (§11)
can change **either** skill and watch both marginal effects plus the interaction.

**Scope discipline (verbatim from `improving-vcs-skill`).** The harness is
**authoring-only**: used *only* while writing/changing `docs` or `rag`, never during
normal development. The sub-agents under test **must never see** the harness or the
gold queries — the *contamination firewall* (§6).

---

## 2. The keystone: no deterministic oracle, so use three surrogates

`vcs` has `scenario.py`: pre-committed conflicts → one mechanically-correct merge →
exact scoring. We cannot pre-commit "the one correct corpus" or "the one correct
RAG config" — an LLM authors the corpus and the `rag` skill chooses the config. So
a single source-of-truth module (`gold.py`, the `scenario.py` analog — it emits the
labels **and** runs the scorers so they can't drift) replaces the merge oracle with
**three deterministic surrogates**:

1. **Gold-set IR metrics (PRIMARY, reproducible).** Version-pinned `qrels` (BEIR
   format) → precision@k, recall@k (k=5/10/20), MRR, nDCG@k via
   `pytrec_eval`/`ranx`. Label-pinned + order-independent ⇒ deterministic.
2. **Downstream sentinel factuality (SECONDARY).** The answer must **contain** a
   unique sentinel from a known relevant doc — string containment, **no judge** in
   the gate; hard tier uses multi-sentinel containment. Core of the **factuality**
   metric.
3. **Convention lint (`docs` WRITE hygiene) + config validity (`rag` hygiene).**
   `check-convention.sh` (durable file signals, §1) and `check-rag-config.sh`
   (the `rag-config` is well-formed, reproducible, and provider-portable) — both
   100% mechanical.

An LLM-as-judge is permitted **only** as an advisory, **non-gating** signal.

---

## 3. Measurement planes, corpora, and the 2×2 factorial

> This is the heart of the two-skill change. Previously the RAG pipeline was a
> *fixed confound* used to isolate the `docs` skill. Now RAG setup is itself a
> skill under test, so it is a **second treatment** and the design becomes
> factorial.

**Plane 1 — Frozen retrieval gate (the primary, bit-reproducible number).** Run a
**fixed reference RAG config** over the **GOLD** corpus (a frozen snapshot of
today's `docs/` at a pinned revision) with version-pinned `qrels`. This number does
**not** change when either skill changes; it measures instrument health, so a move
here flags *instrument* drift, not skill quality.

**Plane 2 — Skill effects via a 2×2 factorial.** Two binary treatments on the same
fixed fact payload and gold queries:

- **corpus** ∈ {**N** = naive dump, **D** = `docs`-skill-authored}
- **rag** ∈ {**b** = baseline naive config, **r** = `rag`-skill config}

| | rag = **b** (baseline) | rag = **r** (`rag` skill) |
| --- | --- | --- |
| corpus = **N** (naive) | cell `Nb` (control) | cell `Nr` (rag-only gain) |
| corpus = **D** (`docs`) | cell `Db` (docs-only gain) | cell `Dr` (co-designed) |

Computed **per query (paired)** for power:

- **`docs` marginal effect** = `Db − Nb` (at baseline rag) and `Dr − Nr` (at rag
  skill).
- **`rag` marginal effect** = `Nr − Nb` (at naive docs) and `Dr − Db` (at docs
  skill).
- **Coupling (interaction)** = `(Dr − Db) − (Nr − Nb)` = `(Dr − Nr) − (Db − Nb)`.
  Positive ⇒ docs and rag are **synergistic** — co-design beats additive. This is
  the headline coupling number and the reason the two skills share one harness.

**Labels are per corpus.** `gold.py` derives `qrels` for N and D from the sentinels
actually present in each corpus's files (sentinel → containing-file is computable
*after* authoring), never from GOLD's paths.

**Nondeterminism is scoped, not denied.** corpus D is LLM-authored and config r may
involve LLM-generated contextualization, so factorial cells are **distributions**:
author **N ≥ 5 seeds** per (corpus × rag) cell, report median + IQR, gate on a
**paired sign/permutation test** whose **CI excludes zero** across consecutive
rounds. Snapshot per-chunk contexts per (corpus-hash × rag-config-hash) so identical
re-runs reuse them; use **PLAIN (no-contextualization) retrieval as the noise-free
cross-round comparison** and FULL as the corroborating arm.

**The headline attribution numbers.**

- *Self-describing premium* (docs): recall D reaches under the **baseline** rag —
  great docs make `docs + baseline-rag` approach `naive + rag-skill`.
- *Setup premium* (rag): recall the `rag` skill adds over baseline on the **same**
  corpus (`Dr − Db`, `Nr − Nb`).
- *Co-design dividend* (coupling): the interaction above.

---

## 4. The three loops (the bookends, now plus a setup loop)

Every round runs three coupled, separately-scored loops:

**WRITE-docs loop** (`new-corpus.sh --task write`, `_run-write.wf.js`, oracle
`check-convention.sh` — the `--task start` analog). A sub-agent with **only** the
`docs` skill gets a fixed fact payload (no prescribed structure), an empty `docs/`
target, and a **seeded convention trap** (a pre-existing `NNNN` forcing a
globally-unique index; a divergent flat doc to standardize). Scored on `CONV_OK`
(durable file signals + the §1 gates) and `WRITE_FINDABLE` (the just-authored doc,
indexed against a **fixed background index** so only the new doc varies, surfaces
in top-k; pass-rate over the N seeds).

**RAG-setup loop** (`apply-rag.sh`, `_run-rag.wf.js`, oracle `check-rag-config.sh`
— the new loop). A sub-agent with **only** the `rag` skill is given a corpus
(N or D) + a provider profile (local first) and must produce a `rag-config.json`
over it, **blind to the gold queries**. Scored on validity/reproducibility/
portability, and on its retrieval/factuality/speed/token outcomes vs the baseline
config (the `rag` marginal effect, §3).

**READ/eval loop** (`new-corpus.sh --task read`, `_run-read.wf.js`, oracle
`check-retrieval.py` — the `--task integrate` analog). A **blind** consumer queries
a given (corpus × rag) cell and the gold set is scored. This is the shared outcome
measurement feeding the factorial.

**The loops close.** A `docs` revision that improves `CONV_OK` but lowers recall is
reverted; a `rag` revision that raises recall but balloons latency or context
tokens at no factuality gain is reverted; a change to one skill that **degrades the
other's marginal effect** (a negative coupling move) is flagged and reverted. All
three must move together.

---

## 5. Two consumer modes (now mapping to "which skill dominates")

- **SIMPLE** — no RAG. Answer by ripgrep/file/keyword over `docs/`, honoring the
  convention. Models a **simple coding agent reading files**; the `rag` skill does
  not participate, so SIMPLE is primarily a **`docs`-skill** outcome and the guard
  that docs serve non-RAG consumers.
- **RAG** — the `rag` skill's configured pipeline. A **joint `docs` × `rag`**
  outcome; this is where the factorial's rag axis lives.

A `docs` change that helps RAG but hurts SIMPLE still fails (no consumer left
behind). A `rag` change is evaluated only in RAG mode. **Speed** and **context-token**
usage are mostly `rag`-skill outcomes (it controls index cost, reranking, top-k
context size); **read-token** usage is a `docs`-skill outcome (front-loading lets a
simple agent read less).

---

## 6. The gold dataset (deterministic, non-circular, graded — serves both skills)

`gold.py` greps the repo for **anchored, machine-checkable facts**, auto-pins each
source path, and emits BEIR `qrels` + records `{query, sentinel(s),
gold_doc_path(s), gold_chunk_ids, fact_source, difficulty, qtype}`. It is
**skill-agnostic** — the same queries score every factorial cell.

**Verified fact families (real sentinels here):** ISSUE facts (issue 0007 →
`jj abandon urruyqxt`, `ORPHAN_EMPTY_HEADS`), BENCHMARK numbers (benchmark 0000 →
`380s` → `~85s`), SKILL-BEHAVIOR facts (export-coding-session naming), the
CROSS-LINK graph (relative links = ready-made relevance labels), COMMIT-HISTORY.

**Graded, multi-relevant `qrels` (mandatory).** `ORPHAN_EMPTY_HEADS` is in **5**
docs, `380s` in **2** — singletons are false. Label *all* containing docs
(primary=2, corroborating=1); **nDCG is the headline**. Hard multi-hop requires
multi-sentinel sets spanning **distinct doc types**, verified at build time.

**Mechanical non-circularity firewall (assert it).** (1) Lexical-overlap guard
rejects queries whose token-trigram Jaccard with the gold doc exceeds a pinned
threshold (forces paraphrase). (2) BM25-only sanity floor moves exact-echo queries
to a separate bucket, excluded from the headline. (3) Fixed dev/held-out partition
(`hash(query_id) mod k`) — tune both skills on **dev**, clear the bar only on
**held-out**, never regenerated per round. (4) Both skills are rewarded **only** via
the fixed pipeline's metrics.

**Closed-book parametric-leakage control (critical — the corpus *is* this repo).**
Run generation with **empty** context; if the model emits the sentinel from prior
knowledge, exclude that query from factuality. `retrieval_hit` (gold doc in top-k,
judge-free, snapshot-reproducible) is the **primary** answerability signal;
`answer_ok` is secondary.

**Statistical power (small corpus: ~40 docs / ~109k words).** Recall moves in coarse
quanta, and the factorial's interaction needs even more power than a 2-arm A/B. State
the **minimum query count** (power calc; likely 50–100+), **enumerate every
cross-link edge as a relevance pair** and add anchored paraphrases to reach it, and
use **within-query paired** comparisons throughout. Name N + the test in round notes.

**Build-time validation + pinning.** Assert every sentinel still occurs in its
pinned doc; pin the corpus revision per `gold-set-version`. Sequencing vs the §10
migration is strict: **migrate first → cut the pinned revision → build gold-set v1 →
freeze**; trends never cross a `gold-set-version` boundary.

---

## 7. The testing bed — phased, cheapest-first

The owner wants a local-hosted **TanStack Start** app to ask questions about the
repo, pointing at a local LLM (Ollama / any OpenAI-compatible endpoint), in
**simple** or **RAG** mode. That app is a real deliverable **and** the substrate the
`rag` skill configures. But the harness only needs a headless eval entrypoint, and
the full stack is unjustified until the factorial shows a signal. So phase it:

**Phase 0 — thin in-process eval (build first).** No services/Docker/TanStack. One
CLI (`docs-eval`) that, given a `(corpus, rag-config)`, chunks + indexes with
**BM25 + an in-memory / embedded vector store** (Qdrant embedded-mode or a numpy
cosine index), runs the gold queries, emits the metrics TSV. Enough to compute all
four factorial cells **and** the interaction. (The `vcs` harness runs **0 services
and no eval-time LLM** — match that restraint.) **GO/NO-GO gate:** build Phase 1
only once Phase 0 shows a measurable, significant factorial signal.

**Phase 1 — the local app (only past the GO gate).** Two faces, one codebase:
the *owner-facing chat UI* (repo-Q&A, simple|RAG toggle, configured local LLM) and
the *harness-facing headless eval route* `POST /api/eval`
(`createFileRoute('/api/eval').server.handlers.POST`) + a CLI sharing the handler.
**Crucially, the eval route now takes a full `rag-config`** (the `rag` skill's
output) — chunker, embedder, contextualization, hybrid weights, reranker, top-k,
provider — rather than hardcoded pins, so the `rag` skill is exercised as a
first-class input. It returns ranked results + per-stage latencies + tokens and
writes the run file the scorer ingests. The harness drives only this route.

**Phase 1 stack, all pinned + version-stamped:** TanStack Start v1 (`createFileRoute`
server routes) on `:3000`; **Qdrant** (Docker, `:6333`) — collection(s) with named
dense + sparse vectors + payload (`path`, `type`, `date`, `NNNN`, `slug`,
`chunk_index`, `corpus_tag`, `rag_config_id`) + payload indexes for metadata
filtering; **Ollama** OpenAI-compatible (`:11434/v1`) for embeddings, contextual-
retrieval context generation, and chat; optional `bge-reranker-v2-m3` (FastEmbed/
ONNX, CPU-ok). A thin **Python sidecar** owns embeddings/sparse/rerank/Qdrant. The
`rag` skill's **provider abstraction** lets the same logical config target local
(Ollama+Qdrant) now and cloud (OpenAI / hosted vector DB) later behind one flag.

**Reproducibility (the local-LLM + variable-pipeline threat).** Pin model tags +
quant + Ollama version + `temp 0` + seed + `num_ctx`; warm the model; fix the host.
**Snapshot per-chunk contexts per (corpus-hash × rag-config-hash)** so the index is
byte-stable across eval runs. Embeddings + reranker are deterministic forward
passes, so over a fixed (corpus, config) the retrieval half is bit-reproducible;
only the answer step carries residual variance (scored by containment, not a judge).
Ship a **reproduction kit** (Docker + model digests, quant, versions); stamp every
TSV row with a **host fingerprint** and have `scoreboard.sh` **refuse cross-fingerprint
comparison**. Absolute recall/latency are host-relative; the frozen-gate numbers and
the within-host factorial deltas are what travel.

**Scope-creep guardrails (the dominant practical risk).** The app is an
**instrument**. MVP = one collection family, one local embed model, one chat model,
fixed gold set, the eval route (taking a `rag-config`), the TSV emitter. **Defer:**
cloud providers, multi-model sweeps, fancy UI, auth, streaming. Cache the
context-generation pass so an eval round is just deterministic retrieval.

---

## 8. Scripts (the `vcs` `scripts/` ported, extended for two skills)

| Script | `vcs` analog | Role |
| --- | --- | --- |
| `new-corpus.sh` | `new-sandbox.sh` | provision a round: `--task read\|write`; build N/D (and GOLD reference); seed the write convention trap |
| `apply-rag.sh` | (new) | given a corpus + a `rag-config.json`, chunk + contextualize + **snapshot** + index it; produce a reproducible, version-stamped index per (corpus × config) |
| `gold.py` | `scenario.py` | **single source of truth**: emit per-corpus `qrels` + records, run all surrogates, build-time validation, held-out split, firewall |
| `check-retrieval.py` | `check-quality.sh` | READ oracle: precision/recall/MRR/nDCG + factuality, `KEY=VALUE` lines |
| `check-convention.sh` | `check-isolation.sh` | `docs` WRITE oracle: durable file signals → `CONV_OK` / `WRITE_FINDABLE` + §1 gates |
| `check-rag-config.sh` | (new) | `rag` oracle: `rag-config.json` well-formed, reproducible, provider-portable; beats baseline |
| `next-index.sh` | (generalize export-coding-session's) | globally-unique index **per type folder**; shared by `docs` + the WRITE oracle |
| `record-metrics.sh` | same | one TSV row per `query × cell(corpus,rag) × mode × round` |
| `scoreboard.sh` | same | by-round / by-tier×mode / difficulty×tier **+ the 2×2 factorial view with marginal effects and the interaction** |
| `_score.py` | same | glue: run oracles, parse `KEY=VALUE`, read per-agent **output tokens exactly** from transcript JSONLs (never `budget.spent()`, never self-reported) |
| `_run-write.wf.js` / `_run-rag.wf.js` / `_run-read.wf.js` | `_run-*.wf.js` | Workflow runners for the three loops; `JSON.parse(args)`; `parallel()` over seeds/cells; per-cell `agent()` with a `REPORT_SCHEMA`; blind to gold labels |
| `rm-corpus.sh` | `rm-sandbox.sh` | teardown guarded to `$DOCS_RAG_HARNESS_DIR` only; drop throwaway Qdrant collections |

All sandboxes live under `$DOCS_RAG_HARNESS_DIR` (default `$TMPDIR/docs-rag-harness`);
only `metrics.tsv` persists.

---

## 9. Metrics and scoreboard

**TSV columns** (the `vcs` shape, re-keyed; the factorial adds the cell + config
dims): `round, loop(write|rag|read), corpus(GOLD|N|D), rag(b|r), rag_config_id,
mode(simple|rag), retrieval(plain|full), seed, query_id, qtype, difficulty,
embed_tier, gen_tier, chunker, embed_ver, gen_ver, recall@5/10/20, precision@5/10,
mrr, ndcg@10, retrieval_hit, answer_ok, factuality_grounded, closed_book_leak,
retrieval_ms_p50/p95, gen_ms_p50/p95, total_ms, ctx_tokens, read_tokens, conv_ok,
write_findable, rag_config_ok, total_chunks, mean_chunk_len, index_ms,
index_llm_cost, host_fingerprint, notes`.

**The five metrics, precisely** — unchanged definitions, now **attributed to `docs`
vs `rag` vs interaction** via the factorial:

- **Precision / Recall** — graded `qrels`; recall@20 headline; nDCG@10 the
  multi-relevance summary; reported per cell so marginal + interaction effects fall
  out.
- **Speed** — `retrieval_ms` (reproducible) separate from `gen_ms` (model-bound);
  `index_ms`/`index_llm_cost` one-time, reported not gated. Primarily a `rag`
  outcome; same-host trend only.
- **Factuality** — `factuality_grounded` via multi-sentinel containment + the
  **closed-book control**; advisory faithfulness judge (`temp 0`, pinned digest+seed,
  checkbox rubric, K=3 unanimity, downgrade-only) corroborates but never gates.
- **Token usage** — `ctx_tokens` (RAG context, a `rag` outcome) and `read_tokens`
  (SIMPLE reading, a `docs` outcome), from transcripts, judged **at equal
  correctness**, trending down.

**Diagnostic split (reported, never a gate):** on an `answer_ok` miss,
`retrieval_hit` attributes it to a **retrieval miss** (→ revise docs and/or rag) vs
a **generation miss** (model-bound noise, ignore).

**`scoreboard.sh` views:** (1) by round (trend on recall@20 + retrieval latency +
ctx_tokens, with deltas); (2) by tier × mode ("no tier/mode left behind"); (3)
difficulty × tier matrix; **(4) the 2×2 factorial: the four cell means, the two
marginal effects (`docs`, `rag`), and the interaction (coupling), each with its
paired-test CI.** Hygiene (`conv_ok`, `write_findable`, `rag_config_ok`) reported
**separately** from retrieval quality.

---

## 10. Convention standardization (`docs` territory; `rag` consumes it)

Clean structure is a direct input to retrieval, so standardizing `docs/` is part of
the `docs` skill's job — and the `rag` skill **consumes** it (front-matter →
payload metadata filters; clean headings → chunk boundaries; numbered slugs →
stable doc IDs). The two skills meet here.

**Current state (surveyed).** Only `coding-sessions/` uses dated subdirs
(`YYYY-MM-DD/NNNN-<vendor>-slug.md`). `issues/` & `prompts/` are flat with the date
in the filename; `benchmarks/` & `plans/` are flat `NNNN-slug`. **No `OVERVIEW.md`
exists anywhere under `docs/`**; the taxonomy is undocumented; `next-index.sh` is
hardcoded to `coding-sessions`.

**Canonical convention** (coding-sessions): `docs/<type>/YYYY-MM-DD/NNNN-slug.md`,
globally-unique zero-padded index from a **generalized** `next-index.sh`, required
front-matter, an `OVERVIEW.md` per subdir, and a top-level `docs/OVERVIEW.md`.
Types: keep `coding-sessions/benchmarks/issues/prompts/plans`; add `research`;
consider `decisions/` (ADRs), `designs/`, `guides/`, `reference/`.

**Each gate is a falsifiable hypothesis.** Re-run the gold set every round and
**demote** any structural gate that stays green while precision/recall/latency stays
flat — the `vcs` revise-and-revert discipline applied to doc structure. Note the
coupling: a gate's value may **depend on the rag config** (heading gates matter more
under heading-aware chunking), so evaluate gates *within* rag cells.

**Migration sequencing (strict).** (1) one-time migration: preserve per-subdir
`NNNN` (type-qualified), add the dated path + front-matter, rewrite **all** relative
cross-links. (2) cut the pinned revision. (3) build gold-set v1. (4) freeze, with a
CI assertion that the pinned revision matches what `qrels` were built against.

---

## 11. The loop and the revise/revert discipline

Per round (mirrors `improving-vcs-skill`'s `LOOP.md`, now over the factorial):

1. **Provision** N/D corpora and baseline/skill rag configs; snapshot per (corpus ×
   config); seed the write trap.
2. **Run** the three loops (WRITE-docs over N seeds; RAG-setup over N seeds; READ/
   eval over all four cells), both modes, via the `.wf.js` runners.
3. **Score** objectively (`check-retrieval.py`, `check-convention.sh`,
   `check-rag-config.sh`); read tokens from transcripts.
4. **Record + compare** (`record-metrics.sh`, `scoreboard.sh`): recall@20, the two
   marginal effects, the interaction CI, factuality, latency, tokens — by round,
   tier×mode, difficulty×tier, and the factorial.
5. **Diagnose then revise ONE skill** (one attributable change at a time), reading
   narratives through the numbers. Attribute via the factorial: if the `docs`
   marginal effect lags only under heading-aware chunking, the fix may belong to
   `docs` *or* `rag` — the interaction tells you which lever moves it.
6. **Re-run on fresh indexes.** **Keep** the change if its skill's marginal effect
   rises, quality holds across tiers/modes, **and** it doesn't degrade the other
   skill's marginal effect (coupling non-negative); **revert** otherwise. Noise →
   drop it and keep both skills **smaller**.
7. **Tear down** with `rm-corpus.sh`.

---

## 12. Exit bar (relative, host-fingerprinted, distributional, two-skill)

Stop only when **all** hold across **multiple consecutive rounds**, in **both
consumer modes**, across the **difficulty ladder**, across **embedding + generation
tiers**, and across **all loops**:

1. Recall@k / precision@5 / nDCG@10 high and stable-or-rising on cell **`Dr`**
   (co-designed), relative to the GOLD baseline measured **on the same host** that
   round.
2. **Both marginal effects positive with CI excluding zero:** `docs` (`Db−Nb`,
   `Dr−Nr`) and `rag` (`Nr−Nb`, `Dr−Db`), surviving both chunker choices.
3. **Coupling non-harmful:** the interaction `(Dr−Db)−(Nr−Nb)` is ≥ 0 (ideally > 0)
   and stable — co-design never *hurts*.
4. **Speed:** `retrieval_ms` p50/p95 low and trending-down-or-stable on the same
   host (a recall gain bought with unacceptable latency or index cost fails — a
   `rag`-skill regression).
5. **Factuality** high — multi-sentinel grounded, closed-book control clean.
   `retrieval_hit` primary; the judge never gates.
6. **Hygiene closes:** `CONV_OK` + `WRITE_FINDABLE` (docs) and `rag_config_ok`
   (reproducible, provider-portable, beats baseline) pass every relevant cell.
7. **No tier/mode left behind:** small/mid embedders **and** generators clear the
   bar; a change that wins RAG but loses SIMPLE fails.
8. **Token usage** low and stable-or-trending-down per tier (at equal correctness):
   `ctx_tokens` (rag) and `read_tokens` (docs).
9. **Local-first holds:** the bar is met with **local** providers (Ollama + Qdrant);
   cloud parity is a later, separately-gated milestone.
10. **Revert discipline / anti-bloat:** every revision judged by the scoreboard;
    one small attributable change to one skill at a time; fresh indexes; noise
    dropped; both skills kept compact.

---

## 13. Top risks and mitigations

- **`docs`/`rag` attribution confound** → the 2×2 factorial with per-query paired
  marginal + interaction effects is exactly the instrument that separates them;
  never change both skills in one round.
- **`rag` overfitting the gold set** (it has many knobs; a config could be tuned to
  the queries) → the held-out split is even more important here; `check-rag-config.sh`
  requires the config be **justified by doc-set properties**, and the bar is cleared
  only on held-out queries; report dev↔held-out gap as an overfit signal.
- **Combinatorial blowup** (4 factorial cells × 2 modes × difficulty × embed-tier ×
  gen-tier × N seeds × 2 chunkers) → mandatory axes (cell, mode, difficulty); sample
  + rotate the tier axes per round (MATRIX discipline); Phase-0 thin eval keeps each
  cell cheap.
- **Teaching-to-the-test (both skills)** → four-layer firewall + the factorial
  isolates good-writing/good-setup from lucky strings; held-out bar.
- **Gold-set rot / small-corpus noise** → pin corpus per gold-version + build-time
  assertions; enumerate cross-link edges + paraphrases for N; within-query paired
  tests; lean on deltas.
- **Local-LLM nondeterminism + variable pipeline** → pin everything + snapshot
  contexts per (corpus × config); PLAIN as the noise-free comparison.
- **Parametric leakage** (corpus *is* this repo) → closed-book control.
- **Cross-machine non-reproducibility** → host-fingerprint + refuse cross-fingerprint
  comparison + reproduction kit; absolute numbers host-relative.
- **Scope creep** → Phase-0 first, GO/NO-GO gate, local-first, the app is an
  instrument, defer cloud/sweeps/UI.
- **Self-reference loop** (indexing the harness/skills) → explicit include/exclude
  manifest (the `.aiexclude` analog).
- **Co-located-code-docs gap** — the repo is mostly skills + markdown, so co-located
  *code* docs barely exist; defer that corpus until the Phase-1 app itself becomes
  the first code worth co-located docs (a flagged later corpus, not MVP).

---

## 14. Open questions for the owner

1. **`rag` skill shape** — should it be a **decision guide** (given doc-set + provider
   properties, prescribe a config) or a **bounded search procedure** (try a small
   pinned grid, pick the best by the harness metrics)? Recommend a principled
   decision guide validated on held-out queries, to avoid overfitting; a *tiny*
   guarded sweep is acceptable if reported.
2. **Corpus scope** — index `docs/` only, or also raw source + `SKILL.md`? Recommend
   docs-only first.
3. **Provider matrix** — which **local** embed/gen models back `large/mid/small`, and
   which **cloud** providers are the eventual parity targets?
4. **Baseline RAG config** — what is the fixed naive `b` baseline (e.g. fixed-grid
   512-token chunks, one embed model, dense-only, no rerank)? It anchors every
   marginal-effect number.
5. **Gold-set policy** — confirm dev/held-out split, the target query count from the
   power calc, and OK to enumerate the cross-link graph to multiply `qrels`.
6. **App reuse** — should the Phase-1 app become the canonical local repo-Q&A tool,
   or stay eval-only?

---

## 15. Build sequence (milestones)

1. **M0 — `docs` skill v0 + `rag` skill v0** (separate efforts): `docs` (read/write
   + generalized `next-index.sh` + convention); `rag` (the local-first decision
   surface in §1, emitting `rag-config.json`). *Inputs to the harness, not part of
   it.*
2. **M1 — `gold.py` + GOLD gold-set v1**: facts, graded per-corpus `qrels`, firewall,
   build-time validation, dev/held-out split. Pin the corpus revision **after** the
   §10 migration.
3. **M2 — Phase-0 thin eval** (`docs-eval` CLI taking `(corpus, rag-config)`: BM25 +
   in-memory vectors) + `check-retrieval.py` + `check-rag-config.sh` +
   `record-metrics.sh` + `scoreboard.sh` (incl. the factorial view). Produce the
   first four-cell factorial + interaction. **GO/NO-GO gate.**
4. **M3 — harness skill** `.agents/skills/improving-docs-and-rag-skills/` (the
   five-doc spine SKILL/LOOP/METRICS/SCENARIOS/MATRIX + scripts), the three loop
   runners, the convention + rag-config traps, the exit bar.
5. **M4 — Phase-1 app** (only past the GO gate): TanStack Start + Qdrant + Ollama +
   sidecar; headless `/api/eval` taking a `rag-config`; snapshotting; reproduction
   kit; owner chat UI.
6. **M5 — iterate** both skills round-over-round until §12 holds; then a
   `docs/benchmarks/` write-up mirroring the `vcs` benchmarks. Cloud-provider parity
   is a separately-gated follow-on.
