<!-- markdownlint-disable MD013 MD024 -->

# Codex Image Context Retrieval

Date: 2026-06-12
Repo: coding-agent-skills (jj workspace `codex-image-context-retrieval`, change `yklmklqy`, commit `794d97c9`)
Author: Shuyang Sun <shuyangsun10@gmail.com>
Agent: Codex CLI (GPT-5.5, reasoning: xhigh)
Summary: Improved image-backed context retrieval guidance and the Phase-0 min-merge chunking benchmark, then prepared the work for VCS integration.

## User

````text
# AGENTS.md instructions for .

<INSTRUCTIONS>
# coding-agent-skills

General-purpose, repo-agnostic skills for LLM coding agents (Claude Code, Cursor, Codex, Gemini, and others).

## Layout

- `.agents/skills/` — the canonical, agent-neutral home for every skill. Each skill is one directory containing a `SKILL.md` plus any helper scripts. Add new skills here.
- `.claude/skills` — symlinks to `.agents/skills` so Claude Code picks up the same set.

## Consuming this repo from another project

This repo is meant to be downloaded, copied, or added as a Git submodule, then individual skill directories under `.agents/skills/` are symlinked into a host project's agent skill directory (under `.agents/` or `.claude/`). Because of that, skills must stay repo-agnostic:

- No hardcoded absolute paths, usernames, or assumptions about the host project's VCS or directory structure.
- Helper scripts resolve the working repo root themselves (Git → Jujutsu → current directory) and create any output directories they need, so they run correctly regardless of where the skill directory is symlinked from.
- Skills reference their own bundled scripts relative to the skill directory the runtime loaded, not a fixed `.agents/` or `.claude/` path, since either (or a different host-project path) may be the install location.

## Formatting

Markdown (and other supported files) are formatted with [Prettier](https://prettier.io), pinned to an exact version in `package.json` and run with [Bun](https://bun.sh).

```sh
bun install        # install Prettier + markdownlint + lefthook, then wire up VCS hooks
bun run format     # format everything in place
bun run format:check   # verify formatting without writing (use in CI)
bun run lint:md    # lint Markdown (use in CI)
bun run lint:md:fix    # lint Markdown and apply auto-fixes
```

Prettier config lives in `.prettierrc.json`; `.prettierignore` excludes dependencies, lockfiles, and verbatim documents. Prose wrapping and embedded-code formatting are disabled so exported session transcripts stay faithful to the original.

### Linting

Markdown is also linted with [markdownlint](https://github.com/DavidAnson/markdownlint) via `markdownlint-cli2`, configured in `.markdownlint-cli2.jsonc` (honored by both the CLI and the VS Code markdownlint extension). The config keeps markdownlint's defaults except for one rule that conflicts with our Prettier setup: `MD013` (line length) is off because we never reflow prose (`proseWrap: preserve`). Session transcripts additionally repeat `## User` / `## Assistant` headings (`MD024`); rather than relax that rule repo-wide, each exported transcript carries its own `<!-- markdownlint-disable MD013 MD024 -->` directive so it lints cleanly even when the skill is used in another project. Prettier owns formatting and markdownlint catches the structural issues it doesn't.

### Pre-commit formatting (Git and Jujutsu)

`bun install` runs `scripts/setup-vcs-hooks.sh` (via the `prepare` script), which configures whichever VCS the clone uses. You can re-run it any time with `bun run setup:hooks`.

- **Git** — [lefthook](https://lefthook.dev) installs a `pre-commit` hook (see `lefthook.yml`) that runs Prettier and then markdownlint on staged `*.md` files and re-stages any fixes.
- **Jujutsu** — jj has no commit hooks (commits are implicit and must stay fast), so the script configures `jj fix` to run Prettier on Markdown instead. Format changed files with `jj fix` (e.g. `jj fix -s @`). jj stores this config per-clone outside the repo, which is why the setup script must run after each fresh clone. `jj fix` only hosts stdin→stdout formatters, so markdownlint isn't wired into it — run `bun run lint:md` to lint under jj.

</INSTRUCTIONS>
<environment_context>
  <cwd>.</cwd>
  <shell>zsh</shell>
  <current_date>2026-06-12</current_date>
  <timezone>America/New_York</timezone>
  <filesystem><workspace_roots><root>.</root></workspace_roots><permission_profile type="disabled"><file_system type="unrestricted" /></permission_profile></filesystem>
</environment_context>
````

## User

```text
Use the $improving-context-retrieval-skills to work on image context retrieval. Make sure context contamination is properly handled.
```

## User

```text
<skill>
<name>improving-context-retrieval-skills</name>
<path>./.agents/skills/improving-context-retrieval-skills/SKILL.md</path>
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

It is the [`improving-vcs-skill`](../improving-vcs-skill/SKILL.md) pattern applied to
docs+retrieval. You run rounds; each round produces numbers; you keep the revisions
that move the numbers and revert the ones that don't.

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

`vcs` works because the correct merge is _computable_. Doc/retrieval quality has
**no such oracle** — an LLM authors the corpus, the `setting-up-rag` skill chooses the
config, and a consumer driven by `retrieving-context` does the querying.
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
and **no** eval-time LLM (match the `vcs` harness's restraint).

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

</skill>
```

## User

```text
<turn_aborted>
The user interrupted the previous turn on purpose. Any running unified exec processes may still be running in the background. If any tools/commands were aborted, they may have partially executed.
</turn_aborted>
```

## User

```text
Use the $improving-context-retrieval-skills to work on image context retrieval. Make sure context contamination is properly handled. If you need to use LLM models for image description, use Gemma 4. The model was downloaded to [REDACTED_MODEL_PATH]/Gemma-4-31B-IT-NVFP4/, you can host it with `vllm`. NVIDIA Nemotron does not support image input, so use Gemma for image inputs, but Nemotron for text inputs. Nemotron is better at text, so use that for text-only tasks. Iterate on the $setting-up-rag, $retrieving-context, and $updating-docs skills with real benchmarks to enhance performance for image question retrievals. Make sure there is no regression in code / NL tasks, that won't be worth it, because image retrievals are lower priority than both.
```

## User

```text
<skill>
<name>improving-context-retrieval-skills</name>
<path>./.agents/skills/improving-context-retrieval-skills/SKILL.md</path>
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

It is the [`improving-vcs-skill`](../improving-vcs-skill/SKILL.md) pattern applied to
docs+retrieval. You run rounds; each round produces numbers; you keep the revisions
that move the numbers and revert the ones that don't.

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

`vcs` works because the correct merge is _computable_. Doc/retrieval quality has
**no such oracle** — an LLM authors the corpus, the `setting-up-rag` skill chooses the
config, and a consumer driven by `retrieving-context` does the querying.
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
and **no** eval-time LLM (match the `vcs` harness's restraint).

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

</skill>
```

## User

````text
<skill>
<name>setting-up-rag</name>
<path>./.agents/skills/setting-up-rag/SKILL.md</path>
---
name: setting-up-rag
description: Load when STANDING UP or TUNING a local retrieval (RAG) system over a
  document or code set — provision the stack, chunk, embed, index, and configure
  hybrid (dense+sparse) search, reranking, and vector-DB knobs. Local-first
  (Qdrant + FastEmbed, CPU, no cloud). To merely RETRIEVE context for a task (not
  build the index), load `retrieving-context` instead; it queries this stack.
---

# Setting up RAG — local-first retrieval over a doc set

**Stand up and tune** effective retrieval over a given corpus (markdown docs,
transcripts, or source code) so a downstream agent can answer from it. The
pipeline is **Qdrant + FastEmbed**, CPU-only, no cloud key: chunk → embed
(dense + sparse) → index → hybrid retrieve (RRF) → rerank → top-k. Defaults live
in [`scripts/rag-config.json`](scripts/rag-config.json); the helpers do the
mechanics, so spend tokens on the corpus-specific choices, not the boilerplate.

> **Building the index vs. using it.** This skill is the **operator** side —
> provision the stack, index a corpus, and tune the config. An agent that just
> needs to **retrieve context to answer a question or do a task** should load
> [`retrieving-context`](../retrieving-context/SKILL.md) instead: it routes to
> the best retrieval available and queries _this_ local stack (the `query.py`
> below) when it is running. Come here to build or improve what it queries.

This file assumes local RAG is **already running**. The first two lines below
handle the one case where it isn't — do not read the setup docs otherwise.

## 0. Make sure local RAG is up (one-time per host)

```sh
bash <skill-dir>/scripts/check-local-rag.sh   # prints READY or NOT_READY
```

If it prints **`NOT_READY`**, provision once with
`bash <skill-dir>/scripts/setup-local-rag.sh` (add `--warm` to pre-download
models). Only then open [SETUP.md](SETUP.md) — for Docker/Ollama/offline
specifics or troubleshooting. If it prints **`READY`**, skip all of that and go
to §1. (Qdrant runs as a server when one is up, else embedded on-disk with no
daemon; both use the same code path.)

## 1. Index the corpus

```sh
python3 <skill-dir>/scripts/index.py --corpus <dir> --kind md   # prose/markdown
python3 <skill-dir>/scripts/index.py --corpus <dir> --kind code # source code
```

Indexes into a hybrid collection (named `dense` + `sparse` vectors); point IDs are
time-ordered Snowflakes (`snowflake.py`). **Re-running replaces the prior chunks of
changed and added docs** — each doc's old points are dropped before re-insert, so
no duplicates or orphans accumulate. Pass `--recreate` after a chunking/embedding
change or when docs were **removed**; `--local` forces embedded mode. Use a
distinct `--collection` per corpus or content type. Chunking adapts to `--kind`
(heading-aware for prose, block-packed for code) — see [CHUNKING.md](CHUNKING.md).

The loader prunes nested VCS roots below the selected corpus root. A Jujutsu
workspace created inside a repo (`jj workspace add <name>`) or a Git worktree
inside the repo is not indexed as part of the parent corpus; pass that
workspace/worktree as `--corpus` directly if it is the corpus you want. This keeps
the behavior generic across repositories. A repo-specific `.gitignore` pattern
for predictable workspace directory names is a useful extra guard, but the indexer
does not rely on it.

## 2. Query

```sh
python3 <skill-dir>/scripts/query.py "a natural-language question" --top-k 20
python3 <skill-dir>/scripts/query.py "…" --json        # JSONL for a consumer/eval
python3 <skill-dir>/scripts/query.py "…" --no-rerank   # skip the rerank stage
```

Each query runs a dense and a sparse retrieval, fuses them with RRF, then a local
cross-encoder reranks the top candidates. The how-and-why is in
[RETRIEVAL.md](RETRIEVAL.md).

## 3. The method (what makes retrieval good, in priority order)

1. **Hybrid beats either arm alone.** Dense (semantic, `bge-small`) catches
   paraphrase; sparse (lexical, `bm25`) catches exact identifiers, error codes,
   API names. Fuse rank lists with **RRF** (robust to incompatible score scales).
2. **Chunk on structure, with a size floor.** Split markdown on headings, but
   **merge tiny sections** up to `min_words` so a heading-dense doc doesn't
   explode into hundreds of one-line chunks (a real cost: ~2.5× fewer chunks at
   equal recall on this repo). Code chunks pack whole blocks. → [CHUNKING.md](CHUNKING.md)
3. **Rerank the shortlist.** A cross-encoder re-scores the fused top-N; it sharply
   separates the right chunk from near-misses, at a small CPU cost. Worth it for
   search; drop it when latency is critical. → [RETRIEVAL.md](RETRIEVAL.md)
4. **Right-size top-k and prefetch** to the consumer's context budget.

## 4. Tune and validate against YOUR corpus — don't trust defaults blindly

The defaults are a strong start, **not** a guarantee. A knob that helps one corpus
can hurt another. Before keeping any change: build a small held-out gold query set
and confirm the change **beats the baseline** on recall@k / nDCG / MRR. Method,
gold-set construction, and the keep/revert rule are in [TUNING.md](TUNING.md).

## 5. Config

All knobs are in [`scripts/rag-config.json`](scripts/rag-config.json) (models,
chunk sizes, fusion, prefetch, rerank, top-k) and documented inline. Pass an
edited copy with `--config`. Provider/model alternatives (bigger dense model,
SPLADE sparse, Ollama embeddings) are noted there and in SETUP.md.

## 6. Optional: local-GPU campaign upgrades (not in the CPU default)

The default above is CPU-only and ships as-is. With a local GPU and an
OpenAI-compatible LLM endpoint, **contextual retrieval** is a measured upgrade for
mixed **code**+docs corpora — generate a 1–2-sentence "situating context" per chunk
with a local model and prepend it to the **embedding/sparse** field, keeping
`raw_text` byte-verbatim for citations:

```text
[repo] path :: heading/symbol (lang)     # deterministic header — keep it
<LLM: "Defines the MctsConfig struct … for Monte-Carlo Tree Search.">
                                         # blank line
<verbatim raw_text>                      # embedded AND what is retrieved/cited
```

Measured on a six-repo gold set (held-out): **nDCG +0.031 overall, +0.045 on the code
domain, sentinel coverage +0.080**, and it is **index-time only** — query latency and
answer-context token cost are unchanged (the context is embedded, never packed into the
answer). Lessons that transfer:

- **Contextualize all chunks, code included** — the "it'll dilute identifiers" worry was
  wrong; code is exactly where it helps (prose is usually already near ceiling).
- **Keep the deterministic header** — dropping it regresses prose retrieval.
- **Serve the generator with vLLM** (NVFP4/FP8), not llama.cpp GGUF-Q8: ~25× faster for
  this bulk index-time pass (≈8 vs ≈0.3 chunk/s on a Blackwell GPU).
- It needs an index-time LLM, so it is **campaign-only**; the portable default stays CPU.

Method + numbers: `docs/benchmarks/2026-06-10/0014`–`0015` and the campaign harness
(`wave4_context.py`) under `docs/plans/2026-06-08/0008-…/`. Re-validate on YOUR corpus (§4).

### Other index-time techniques, measured on the same gold set

The **one rule** that explains all of them: index-time context helps only when it **sharpens** a
chunk's identity, and it must apply to **code**, not just prose.

- **Doc2Query / document expansion** (campaign, index-time LLM — `0018`): generate a few search
  queries each chunk answers and append them to a **separate BM25 field** (lexical only — leave
  dense and `raw_text` untouched). A real **code** win (held-out nDCG +0.030, sentinel +0.082) at
  ≈ contextual-retrieval quality, but it regresses some prose slices, so contextual retrieval is the
  cleaner default. Apply to **all** chunks — prose-only **regressed code**.
- **Session metadata capsule** (portable, deterministic, **no LLM** — `0017`): for session **transcripts** (`…/transcripts/…`, `…/llm-sessions-history/…`), prepend `session <id>
<vendor> <date> — <name>; files: <files it touched>` to each chunk. The live signal is the
  **mentioned-file list** (the path already gives date/index/vendor). Optional, corpus-conditional —
  it drove transcript retrieval to near-perfect on a transcript-heavy repo; flat elsewhere. Enable +
  validate on a gold set; don't ship it as a forced default.
- **Late chunking / LLM-free contextual embedding** — **tested and rejected** (`0016`): pooling each
  chunk over whole-document context (bge-m3) **blurs** within-document discrimination and regressed
  every slice (nDCG −0.115). There is no cheap LLM-free substitute for contextual retrieval here.
- **Measurement caveat:** Qdrant HNSW re-indexing is non-deterministic at ~**0.03** per single
  slice — trust domain aggregates + cross-split replication, not a lone small per-slice delta.

</skill>
````

## User

````text
<skill>
<name>retrieving-context</name>
<path>./.agents/skills/retrieving-context/SKILL.md</path>
---
name: retrieving-context
description: >-
  Load when you need to FIND or RETRIEVE context (docs, prior decisions, code) to
  answer a question or do a task — and BEFORE you grind ripgrep blindly or write
  a new doc. Routes to the best retrieval available, best-first: cloud RAG →
  local RAG → navigating the doc structure by hand. Nudges you up a tier when the
  corpus is large or you'll query it repeatedly. Repo-agnostic.
---

# Retrieving context

You need context — a prior decision, the doc that already answers this, the code
that does the thing — before you can act. **Getting that context is its own skill:**
the difference between one good query and an afternoon of blind `rg` is which
retrieval you reach for. This skill **routes you to the best retrieval available**
and, when only a weak one is, tells you when it is worth standing up a better one.

Two failure modes bracket the job, and both are common:

1. **Under-powered.** Grinding keyword `rg` over a large or long-form corpus
   (transcripts, a big `docs/` tree) when a vector index would answer in one shot —
   or _re-grinding_ it on every follow-up question.
2. **Over-powered.** Spinning up a RAG pipeline to find one fact in a five-file
   repo, where a single `rg` or reading the directory index is faster.

So: **pick the most capable retrieval that is actually available, sized to the
corpus and how often you'll query it** — and fall back gracefully when the better
tiers are absent.

## The routing ladder (best-first; fall down it, nudge back up it)

### Tier 1 — Cloud / managed RAG, if the repo wires one

If the host or repo exposes a **managed retrieval service** — a hosted vector DB, a
retrieval MCP tool, an indexed knowledge base, a documented search endpoint —
**prefer it** for any large or shared corpus. It is maintained, it scales past one
machine, and it is shared across agents, so its index is usually fresher and broader
than anything you'd build ad hoc.

- **Detect:** scan for a configured retrieval/search MCP tool, a project retrieval
  endpoint, or a knowledge base named in the repo's docs or agent config. Don't
  assume one exists; don't assume one doesn't — look.
- **Use it, then verify.** Query in the corpus's own words; treat the hits as
  candidates and confirm against the cited source before relying on them.

### Tier 2 — Local RAG (the `setting-up-rag` stack)

No cloud retrieval, but a **medium-to-large local corpus** (a real `docs/` tree,
exported transcripts, a source tree)? Use the local hybrid index from
[`setting-up-rag`](../setting-up-rag/SKILL.md) — Qdrant + FastEmbed, CPU-only, no
cloud key. It beats keyword search on recall because it fuses dense (semantic) and
sparse (lexical) retrieval and reranks the shortlist.

- **Is it up?** Run `setting-up-rag`'s `check-local-rag.sh` (prints `READY` /
  `NOT_READY`), then query with its `query.py`. Both live in the sibling skill —
  `<setting-up-rag-dir>` is `../setting-up-rag` relative to this skill, so its scripts
  are at `../setting-up-rag/scripts/`. If `READY` and the corpus is indexed:

  ```sh
  python3 <setting-up-rag-dir>/scripts/query.py "a natural-language question" --top-k 20
  ```

- **Up but corpus not indexed?** Index it first (one command — see `setting-up-rag`
  §1), then query.
- **Not set up at all?** If the corpus is large or you're about to make many
  queries, **set it up** via `setting-up-rag` rather than grinding `rg` — that is
  the nudge, not a detour. For a one-off lookup, drop to Tier 3 instead.

### Tier 3 — Navigate the doc structure by hand (always available)

When no RAG is available — a small corpus, a quick one-off lookup, a fresh repo, or
RAG simply not set up — find the answer by **understanding the structure**. This is
the floor, and it is often enough:

- **Read the directory index first.** Most doc trees keep an `OVERVIEW.md` /
  `README.md` / `index.md` per directory. Read it — it is the curated map and the
  cheapest way to see what's already covered. Then open the **primary doc** it
  points at; don't stop at the index (it only lists, it rarely states the answer).
- **Search by the concept, not just the keyword.** `rg -i` across the docs/code
  root for the identifier, error string, number, or proper noun you expect the
  answer to contain. If you only know the topic, search the **natural-language
  phrasing a reader would use** — that is how a findable doc is written, so it is
  how it is found.
- **Walk the structure.** Dated / indexed / typed folders (e.g.
  `docs/<type>/<YYYY-MM-DD>/<NNNN>-<slug>`) let you scan by recency and area without
  opening files. A numbered reference ("issue 0042") points straight at one file.

### The nudge — escalate when the floor gets expensive

Tier 3 is the fallback, **not the goal**. Move up a tier the moment manual retrieval
starts costing more than the setup would: you're paging through dozens of `rg` hits,
the corpus is large or long-form (dialog transcripts especially), or you'll query it
repeatedly across the task. Those are the signals to stand up local RAG
(`setting-up-rag`) or reach for a cloud index. Conversely, don't climb the ladder
for a three-file repo — the floor is the right tool there.

## Retrieve well, whatever the tier

- **Phrase the query in the corpus's words.** Paraphrase the need into the
  identifiers, error strings, and proper nouns the answer doc would contain — both
  lexical search and embedders match on shared surface terms.
- **Orient before you dive.** Read the directory map / a top-k skim first; it is
  cheap and stops you deep-reading the wrong file.
- **Prefer the primary source over an aggregator.** The doc that _states_ the
  answer beats an index or a summary that merely _cites_ it.
- **Verify before you rely.** Retrieval surfaces candidates, not ground truth — open
  the source and confirm the fact is actually there, phrased as you'll use it.
- **Preserve provenance when retrieved context feeds an answer.** Keep source IDs,
  paths, headings, and line ranges attached to each chunk; don't paste anonymous
  excerpts into the prompt. Require citations on factual answer sentences and
  mechanically check that the cited chunk exists and contains the claimed support.
- **Pack for the reader, not just the retriever.** For larger answer contexts, start
  with score order or parent/section grouped packs that preserve source IDs. Use
  source-path order only when you have measured it on that corpus; on this repo's
  mixed code/docs benchmark it was worse for both answer sentinel containment and
  citation support. Escalate to raw top-k only when exact literal extraction matters
  more than token budget.

## When retrieval comes up empty — write it down

If you searched well across the available tiers and the answer **isn't** in the
corpus (or lives only in a stale, half-right doc), that is a signal to **record it**.
Hand off to [`updating-docs`](../updating-docs/SKILL.md): this skill satisfies the
"find before you write" precondition (you've confirmed it's missing or needs
updating); that skill writes it so the _next_ retrieval finds it. The two are a pair
— retrieve here, write there.

## Anti-patterns (revert these)

- **Blind grind** — re-running keyword `rg` over a large or long-form corpus when an
  index exists or could be built in one command.
- **Over-engineering** — standing up RAG to find one fact in a handful of files.
- **Stopping at the index** — reading the `OVERVIEW.md` listing and never opening the
  primary doc that actually answers the question.
- **Trusting rank 1** — quoting the top retrieved chunk without opening the source to
  confirm it says what you think.
- **Not looking for the better tier** — assuming no cloud/local index is available
  without checking the repo's tools and config.

</skill>
````

## User

````text
<skill>
<name>updating-docs</name>
<path>./.agents/skills/updating-docs/SKILL.md</path>
---
name: updating-docs
description: Load BEFORE you write or update a doc (issue, plan, design, benchmark,
  session note, runbook, decision record), so you write it where both humans and
  retrieval will actually find it, and update what exists instead of forking it.
  Finding what's already there (the search-before-you-write step) is delegated to
  `retrieving-context`. Repo-agnostic.
---

# Updating docs

**Findability is the whole job.** A doc nobody can retrieve is worth nothing — it
gets rewritten, contradicted, or lost. This skill is the **write** half of that job:
update what already exists rather than forking it, and write so the next reader (a
human skimming, a retriever ranking) actually finds it. The **find** half — checking
what's already there before you write — is [`retrieving-context`](../retrieving-context/SKILL.md);
do that first.

Three empirical anchors drive every rule below; treat them as the _why_:

1. **Having the doc at all is the dominant lever.** The single biggest jump in
   findability is going from no doc to one indexed doc. So the first failure mode
   is a missing or unlinked doc, not an imperfect one — write it, and link it.
2. **Structure only pays off when something reads the structure.** Clean headings
   and one-concept files help a human and help heading-aware retrieval, but they do
   **not** rescue an answer that isn't stated in plain, searchable words. So
   structure is necessary, not sufficient: **anchor the answer lexically** (§5).
3. **Advanced retrieval still needs authored context.** Contextual retrieval, late
   chunking, graph retrieval, parent-document retrieval, and rerankers can recover
   more context than naive chunking, but they work best when the doc itself names
   its parent project/module, source paths, entities, and relationships. Write
   those context clues once, near the top and at section boundaries, instead of
   relying on a retriever to infer them.

## 1. Before you write: search first (don't duplicate)

Never author a doc until you've checked whether it already exists. Use
[`retrieving-context`](../retrieving-context/SKILL.md) to search the corpus the way
a reader would — read the directory index, search by concept (not just keyword),
walk the dated/typed folders. That skill owns the _how_; what matters here is the
rule it enforces:

- If a doc already covers the concept, **update it in place** rather than adding a
  near-duplicate. Two docs that both half-answer a question are worse than one.
- If nothing covers it (or the only doc is stale and half-right), that's your
  signal to write — proceed below.

## 2. Decide where it lives: co-locate vs centralize

- **Co-locate with the code** it explains when it is tightly coupled to one
  module/package (a `README.md` next to the code, a doc comment) — it travels and
  versions with that code and is found by anyone in that directory.
- **Centralize under the docs root** (`docs/`) when it is cross-cutting: a plan, a
  design/decision record, an issue write-up, a benchmark, a runbook, a session
  note. These are not owned by one module and belong in the shared, indexed tree.
- **Add a small source map** when a task, decision, or workflow spans several code
  files and no single file is the obvious home. The source map is a bridge, not a
  replacement for source: it states the answer, names the primary files/functions,
  and links to the code a reader must verify.

When in doubt, prefer the location where the next person _looking for this_ will
look first.

## 3. Match the repo's existing convention

Before inventing a layout, **adopt the host repo's**. Open the docs root and the
nearest `OVERVIEW.md`/`README.md` and copy the pattern already in use: directory
shape, filename scheme, header block, and how the index is kept.

If the repo has **no** convention yet, a durable default is one directory per doc
**type**, dated subfolders, and a zero-padded **globally-unique index** per type:

```text
docs/<type>/<YYYY-MM-DD>/<NNNN>-<kebab-slug>.md   # type ∈ issues, plans, designs, runbooks, …
```

- `NNNN` is unique across the whole type tree (it does **not** restart per day),
  so a numbered reference (e.g. "issue 0042") stays unambiguous. The next index is one more than
  the highest existing one — read from the **filename prefix**, not the `YYYY-`
  date folder, and forced base-10 so a leading-zero index isn't parsed as octal:

  ```sh
  last=$(find docs/<type> -name '[0-9][0-9][0-9][0-9]-*.md' -exec basename {} \; \
         | sed -E 's/^([0-9]{4}).*/\1/' | sort -n | tail -1)
  printf '%04d\n' "$([ -n "$last" ] && echo $((10#$last + 1)) || echo 0)"  # empty tree → 0000
  ```

- `<kebab-slug>` is **descriptive** — `0042-retry-storm-on-token-refresh`, never
  `0042-notes` or `0042-fix`. The filename is the first thing both a human and a
  filename-aware retriever match on.

## 4. One concept per file, with a skimmable shape

- **One concept per file.** A file that answers one question ranks cleanly for
  that question; a grab-bag file dilutes every query it could serve. Split when a
  doc grows a second top-level concern.
- **Open with a descriptive H1** that names the thing in the words a searcher
  would use — not "Notes" or "Update".
- **A short status/metadata block** under the H1 (Date, Status, Area, and
  whatever the repo uses) so staleness and ownership are visible at a glance.
- **A clean heading hierarchy**, one concept per section, no skipped levels.
  Heading-aware retrieval chunks on these boundaries, and humans navigate by them.
- **Keep it tight.** Cut throat-clearing and duplication; long docs bury the
  answer (§5) and rot faster.

## 5. Front-load the answer and anchor it lexically

This is the rule that most often decides whether a doc is found:

- **State the answer in plain prose near the top**, in a `## Summary` or lead
  paragraph — before background, history, or derivation. Retrieval and skimming
  both reward the answer being early.
- **Add a retrieval context line when the doc is not self-evident.** In one short
  sentence near the top, name the parent project/module, the workflow or failure
  mode, and the source paths or identifiers the doc explains. This gives
  contextual retrievers and parent/child chunkers the same disambiguating context a
  human would get from opening the full file.
- **Anchor it lexically.** Put the concrete fact — the number, the identifier, the
  command, the error string, the proper noun — in the prose itself, spelled the way
  someone would search for it. An answer that exists only in a table cell, a
  screenshot, an attached file, or implied between the lines is effectively
  unfindable: a query phrased differently from the document shares no surface terms
  with it and will not retrieve it. When you state a figure, name what it measures
  in the same sentence ("cold-start p95 latency dropped from 1.8s to 0.4s"),
  so the sentence matches both the value query and the topic query.
- **Make sections self-contained.** Start each section with the subject it is about
  ("`XqGame::kPolicySize` maps Xiang Qi actions to 8,100 policy slots"), not only
  "This" or "The fix". Chunk-level retrievers may see the section without the H1.
- **Mirror table-only facts in prose.** Tables are good for scanning, but each
  critical row needs a sentence that repeats the value, what it measures, and the
  entity it belongs to.

## 6. Write for advanced retrieval without bloat

Do the work once in the doc, not once per chunk:

- **Use a compact context capsule.** A good top block is usually `Date`, `Status`,
  `Area`, `Sources`, then `## Summary`. `Sources` should list primary files,
  commands, issue IDs, benchmark data, or `docs/transcripts/` session transcript paths. Keep it short:
  a retriever needs anchors, not a second abstract.
- **Preserve relationship edges.** Say what the doc implements, supersedes,
  depends on, tests, or explains, and link those docs/code paths. Graph-style
  retrieval and rerankers can only use relationships that are explicit in text.
- **Prefer stable names over clever prose.** Use exact API names, config keys,
  file paths, commands, error strings, task IDs, benchmark IDs, and model/version
  names alongside natural-language descriptions.
- **For long transcripts or generated logs, add a human-authored lead summary.**
  Keep the transcript/log faithful, but put the high-signal facts, changed files,
  commands, and outcome near the top so retrieval does not have to mine thousands
  of dialogue tokens before it finds the point.
- **Do not spray boilerplate into every section.** If the same context must repeat
  often, that is a sign the doc wants a source map, glossary, or split file.

## 7. Wire it into the graph

A new doc that nothing points to is nearly as lost as no doc:

- **Add it to the directory index** (`OVERVIEW.md`/`README.md`) — one line, the
  title, and a one-clause hook — in the same change that adds the doc.
- **Cross-link related docs** both ways where it helps. Links are relevance
  edges: they help readers and they let link-aware tooling connect questions to
  answers across files.
- **Mark superseded docs** as such and link forward to what replaced them, rather
  than silently leaving two live versions.

## Anti-patterns (revert these)

- A missing or **unlinked** doc — not in any index, pointed to by nothing.
- A **duplicate** that forks an existing doc instead of updating it.
- An **opaque filename** (`notes.md`, `0042-fix.md`) or a vague H1.
- The **answer buried** below the fold, or living only in a table/figure/attachment
  with no plain-prose, lexically-anchored statement.
- A **context-free chunk**: a section that says "this" or "the change" but does not
  name the project/module, source path, API, command, or error it is about.
- A **grab-bag** file mixing several concepts so it ranks for none.
- A **source map that replaces verification** — it must point to primary code/docs,
  not become an uncited copy that drifts.
- **Bloat** — pages of preamble around a one-paragraph answer.

## Checklist before you finish

- [ ] Searched first (via `retrieving-context`); this isn't a duplicate (or it
      updates the existing doc).
- [ ] Lives in the right place (co-located vs centralized) and follows the repo's
      naming/index convention.
- [ ] One concept; descriptive H1 + status block; clean headings.
- [ ] Answer is in the first screen, in plain prose, with the key fact, source
      path/API/command, and retrieval context spelled out.
- [ ] Linked from its directory index and cross-linked to related docs.

</skill>
````

## Assistant

Using `vcs` plus the requested context-retrieval skills. I’ll work from the isolated jj workspace, inspect the existing harness and benchmark surface, then make only changes that image retrieval benchmarks justify without NL/code regression.

### Tool Calls

- Tool call: `exec_command` — pwd && jj status
- Tool call: `exec_command` — sed -n '1,240p' ./.agents/skills/vcs/SKILL.md
- Tool call: `exec_command` — sed -n '1,260p' .agents/skills/improving-context-retrieval-skills/SKILL.md
- Tool call: `exec_command` — sed -n '1,260p' .agents/skills/setting-up-rag/SKILL.md
- Tool call: `exec_command` — sed -n '1,260p' .agents/skills/retrieving-context/SKILL.md
- Tool call: `exec_command` — sed -n '1,280p' .agents/skills/updating-docs/SKILL.md

## Assistant

The workspace is clean and already isolated by the session hook. I’m renaming the temporary jj workspace now, then I’ll read the harness docs that define the contamination firewall and benchmark procedure before touching scripts or skill text.

### Tool Calls

- Tool call: `exec_command` — bash .agents/skills/vcs/scripts/rename-work.sh codex-image-context-retrieval
- Tool call: `exec_command` — sed -n '261,520p' .agents/skills/improving-context-retrieval-skills/SKILL.md
- Tool call: `exec_command` — sed -n '1,260p' .agents/skills/improving-context-retrieval-skills/LOOP.md
- Tool call: `exec_command` — sed -n '1,280p' .agents/skills/improving-context-retrieval-skills/SCENARIOS.md
- Tool call: `exec_command` — sed -n '1,240p' .agents/skills/improving-context-retrieval-skills/METRICS.md
- Tool call: `exec_command` — sed -n '1,240p' .agents/skills/improving-context-retrieval-skills/MATRIX.md
- Tool call: `exec_command` — sed -n '1,220p' ./.agents/skills/coding-style/SKILL.md

## Assistant

The harness already has an image domain and a clear firewall: image questions must not be written into the image corpus, and supporting image paths are lower-grade evidence than code/docs/session primaries. Next I’m inspecting the concrete loaders, configs, and current benchmark behavior to find an image-specific weakness that can be measured.

### Tool Calls

- Tool call: `exec_command` — sed -n '1,260p' ./.agents/skills/coding-style/styles/python.md
- Tool call: `exec_command` — rg --files .agents/skills/improving-context-retrieval-skills .agents/skills/setting-up-rag .agents/skills/retrieving-context .agents/skills/updating-docs
- Tool call: `exec_command` — sed -n '1,260p' .agents/skills/improving-context-retrieval-skills/scripts/gold.py
- Tool call: `exec_command` — sed -n '1,260p' .agents/skills/improving-context-retrieval-skills/scripts/docs-eval.py
- Tool call: `exec_command` — sed -n '1,220p' .agents/skills/improving-context-retrieval-skills/scripts/mk-corpus.py
- Tool call: `exec_command` — sed -n '1,220p' .agents/skills/improving-context-retrieval-skills/configs/baseline-b.json
- Tool call: `exec_command` — sed -n '1,220p' .agents/skills/improving-context-retrieval-skills/configs/rag-r.json

## Assistant

The current image path is Phase-0 deterministic: no eval-time LLM, with curated image summaries keyed by real image paths. I’m going deeper on `gold.py` and `docs-eval.py` now because the likely fix is in how image summaries, primaries, and qrels are loaded and ranked, not in adding model generation.

### Tool Calls

- Tool call: `exec_command` — sed -n '261,620p' .agents/skills/improving-context-retrieval-skills/scripts/gold.py
- Tool call: `exec_command` — sed -n '621,1040p' .agents/skills/improving-context-retrieval-skills/scripts/gold.py
- Tool call: `exec_command` — sed -n '221,520p' .agents/skills/improving-context-retrieval-skills/scripts/docs-eval.py
- Tool call: `exec_command` — sed -n '1,260p' .agents/skills/improving-context-retrieval-skills/scripts/check-retrieval.py
- Tool call: `exec_command` — sed -n '1,300p' .agents/skills/improving-context-retrieval-skills/scripts/scoreboard.py
- Tool call: `exec_command` — find docs -maxdepth 3 -type f | sed -n '1,160p'

## Assistant

There are recent transcripts and benchmark artifacts about the image harness, so I’ll search those before changing anything. That should show whether the current weakness is already known and keep us from duplicating or contaminating the gold set with fresh eval notes.

### Tool Calls

- Tool call: `exec_command` — sed -n '1041,1400p' .agents/skills/improving-context-retrieval-skills/scripts/gold.py
- Tool call: `exec_command` — rg -n "image|Gemma|Gemma-4|Nemotron|contamination|firewall|qrels|supporting" .agents/skills docs/benchmarks/2026-06-12 docs/transcripts/2026-06-12/0061-codex-image-retrieval-harness.md docs/transcripts/2026-06-12/0062...
- Tool call: `exec_command` — find [REDACTED_LOCAL_PATH] -maxdepth 3 -type d -name 'shuyang-website' -o -type d -name 'website'
- Tool call: `exec_command` — sed -n '1,220p' docs/transcripts/2026-06-12/0061-codex-image-retrieval-harness.md
- Tool call: `exec_command` — sed -n '1,220p' docs/transcripts/2026-06-12/0062-codex-improving-context-retrieval-image-harness.md
- Tool call: `exec_command` — sed -n '1,220p' docs/benchmarks/2026-06-12/0022-wave7-answer-faithfulness-rag.md

## Assistant

I found the previous turn already converted the image domain from caption recall into project-context retrieval. I’m going to run the current Phase-0 benchmark across NL, code, and image first, then use the per-query failures to decide whether a skill or harness change is warranted.

### Tool Calls

- Tool call: `exec_command` — set -euo pipefail SK=.agents/skills/improving-context-retrieval-skills H=[REDACTED_TMP_PATH] ROUND=pre IMAGE_CORPUS=[REDACTED_LOCAL_PATH]/website rm -rf "$H" mkdir -p "$H" python3 "$SK/scripts/check-vcs-boundary.py" p...

## Assistant

Current benchmark says the image domain is the only clear target: `rag-r` improves image nDCG@10 from 0.259 to 0.349 and hit@20 from 0.778 to 1.000, while code improves too. NL is weaker in this tiny Phase-0 factorial, so I’ll treat any config-level change as suspect unless it preserves the existing NL/code numbers.

### Tool Calls

- Tool call: `exec_command` — python3 - <<'PY' import json import sys from pathlib import Path SK=Path('.agents/skills/improving-context-retrieval-skills/scripts').resolve() sys.path.insert(0, str(SK)) import gold H=Path('[REDACTED_TMP_PATH]) corp...

## Assistant

The per-query image failures are specific: the current RAG config helps most image questions but hurts the DOM-layering question, and social preview barely clears top-20. I’m sweeping retrieval knobs against the same corpora now; I’ll keep a config change only if image improves and NL/code do not move backward.

### Tool Calls

- Tool call: `exec_command` — python3 - <<'PY' import copy import importlib.util import json import statistics import sys from pathlib import Path SK=Path('.agents/skills/improving-context-retrieval-skills/scripts').resolve() sys.path.insert(0, st...

## Assistant

The sweep is still running; it is building deterministic in-memory indexes for several config variants over all three domains. I’m letting it finish because this is the regression gate for any `setting-up-rag` change.

### Tool Calls

- Tool call: `write_stdin` — args: chars, max_output_tokens, session_id, yield_time_ms

## Assistant

The sweep found an actionable mismatch: fixed-size chunks beat the current heading chunks across image, NL, and code in Phase 0. That points to the existing heading evaluator over-fragmenting sections, which conflicts with the `setting-up-rag` skill’s own “merge tiny sections” rule, so I’m testing a heading-aware chunker with a `min_words` floor before deciding whether to patch the harness/config.

### Tool Calls

- Tool call: `exec_command` — python3 - <<'PY' import copy import importlib.util import json import statistics import sys from pathlib import Path SK=Path('.agents/skills/improving-context-retrieval-skills/scripts').resolve() sys.path.insert(0, st...

## Assistant

The merged-heading sweep is still running. I’m checking it because it would improve image retrieval while preserving the documented “chunk on structure” behavior, instead of changing the skill-shaped config to a plain fixed-grid workaround.

### Tool Calls

- Tool call: `write_stdin` — args: chars, max_output_tokens, session_id, yield_time_ms

## Assistant

Merged heading chunks look like the better fix. With `size=350` and `min_words=120`, image nDCG@10 rises from 0.350 to 0.437, code rises from 0.584 to 0.596, and NL rises from 0.223 to 0.260 in the same deterministic harness. I’m going to patch the Phase-0 evaluator/config to honor the min section size the skill already recommends, then rerun the full benchmark.

### Tool Calls

- Tool call: `exec_command` — sed -n '1,260p' .agents/skills/setting-up-rag/scripts/rag-config.json
- Tool call: `exec_command` — rg -n "min_words|chunk|heading|image|multimodal|vision|contextual" .agents/skills/setting-up-rag/scripts/rag_lib.py .agents/skills/setting-up-rag/CHUNKING.md .agents/skills/setting-up-rag/RETRIEVAL.md .agents/skills/s...
- Tool call: `exec_command` — sed -n '1,260p' .agents/skills/setting-up-rag/scripts/rag_lib.py
- Tool call: `exec_command` — sed -n '1,220p' .agents/skills/setting-up-rag/CHUNKING.md
- Tool call: `exec_command` — sed -n '1,220p' .agents/skills/setting-up-rag/TUNING.md
- Tool call: `exec_command` — python3 - <<'PY' import copy, importlib.util, json, statistics, sys from pathlib import Path SK=Path('.agents/skills/improving-context-retrieval-skills/scripts').resolve(); sys.path.insert(0,str(SK)); import gold spec...

## Assistant

Here’s the scoped plan I’m following now:

1. Patch the Phase-0 harness so heading chunking actually honors `min_words`, matching the real `setting-up-rag` implementation.
2. Keep the portable default at `min_words=80` because it improves image retrieval without giving up the stronger NL result seen in the sweep.
3. Update the three skills with image-backed retrieval guidance: project context first, image paths as supporting evidence, no eval-QA contamination, Gemma 4 only for image description, Nemotron for text-only context generation.
4. Re-run NL/code/image benchmarks and formatting checks, then record the measured result in a benchmark doc with exclusion-safe naming.

### Tool Calls

- Tool call: `update_plan` — updated task plan

## Assistant

I’m editing the evaluator first. The change is small: the Phase-0 heading chunker will merge tiny adjacent Markdown sections before indexing, and `rag-r.json` will carry the `min_words` knob explicitly so future benchmark changes are attributable.

## Assistant

The evaluator now matches the production chunker’s min-merge behavior. I’m making the corresponding config knob explicit in the harness RAG config.

### Tool Calls

- Tool call: `update_plan` — updated task plan

## Assistant

Now I’m updating the three skill instructions. The rule I’m adding is narrow: image-backed retrieval should still retrieve code/docs/session context first, with real image paths as supporting evidence; generated image descriptions are index-time support documents, not answer keys or eval questions.

## Assistant

The RAG skill now says how to build an image-backed corpus without turning the eval into caption retrieval. I’m adding the consumer-side guidance next: when answering, retrieve and cite primary project context first, then use image paths as corroborating evidence.

## Assistant

The consumer skill now has image-backed retrieval behavior. I’m updating the writing side so future docs make image assets retrievable through explicit purpose, paths, and synchronization rules rather than screenshots or asset names alone.

## Assistant

The three skills are updated. I’m rerunning the same NL/code/image harness now with the patched evaluator and explicit min-merge config; this is the pass that decides whether the change stays.

### Tool Calls

- Tool call: `update_plan` — updated task plan
- Tool call: `exec_command` — set -euo pipefail SK=.agents/skills/improving-context-retrieval-skills H=[REDACTED_TMP_PATH] ROUND=post IMAGE_CORPUS=[REDACTED_LOCAL_PATH]/website rm -rf "$H" mkdir -p "$H" python3 -m py_compile "$SK/scripts/gold.py" ...
- Tool call: `exec_command` — sed -n '84,180p' .agents/skills/improving-context-retrieval-skills/scripts/docs-eval.py
- Tool call: `exec_command` — sed -n '1,60p' .agents/skills/improving-context-retrieval-skills/configs/rag-r.json
- Tool call: `exec_command` — sed -n '180,240p' .agents/skills/improving-context-retrieval-skills/scripts/docs-eval.py

## Assistant

I caught a workspace issue: the manual patch tool applied relative paths to the original checkout, not the isolated jj workspace. I’m correcting that now by applying the same edits with absolute paths in the isolated workspace and removing my accidental edits from the shared checkout.

### Tool Calls

- Tool call: `exec_command` — jj status
- Tool call: `exec_command` — jj status
- Tool call: `exec_command` — rg -n "min-merge floor|Image-backed project context|image-backed project questions|image-backed workflows|Give image assets" ./.agents/skills ./.agents/skills

## Assistant

The isolated workspace is still clean, so no user work there was affected. I’m applying the intended edits to the isolated workspace using absolute paths first.

## Assistant

The intended edits are now in the isolated workspace. I’m removing my accidental copies from the shared checkout by reversing only the lines I just added there.

## Assistant

The shared checkout is being sanity-checked now, then I’ll rerun the benchmark from the isolated workspace so the measured output reflects the actual changes.

### Tool Calls

- Tool call: `exec_command` — jj status
- Tool call: `exec_command` — jj status
- Tool call: `exec_command` — sed -n '84,175p' .agents/skills/improving-context-retrieval-skills/scripts/docs-eval.py
- Tool call: `exec_command` — sed -n '1,22p' .agents/skills/improving-context-retrieval-skills/configs/rag-r.json
- Tool call: `exec_command` — sed -n '175,210p' .agents/skills/improving-context-retrieval-skills/scripts/docs-eval.py

## Assistant

The shared checkout is clean again and the isolated workspace has the intended changes. I’m rerunning the full benchmark now from the isolated workspace; the previous post-run was invalid because it hit the unpatched workspace.

### Tool Calls

- Tool call: `exec_command` — set -euo pipefail SK=.agents/skills/improving-context-retrieval-skills H=[REDACTED_TMP_PATH] ROUND=post IMAGE_CORPUS=[REDACTED_LOCAL_PATH]/website rm -rf "$H" mkdir -p "$H" python3 -m py_compile "$SK/scripts/gold.py" ...

## Assistant

The patched benchmark clears the regression gate: image `rag-r` nDCG@10 went 0.349 to 0.379 and recall@20 0.511 to 0.553, while NL `Dr` nDCG rose 0.223 to 0.358 and code stayed at 0.584. I’m recording that as an excluded benchmark note so it cannot contaminate the NL corpus.

### Tool Calls

- Tool call: `update_plan` — updated task plan

## Assistant

Before writing the benchmark note, I’m checking the existing benchmark index and numbering convention so the new record lands where retrieval and humans will find it.

### Tool Calls

- Tool call: `exec_command` — sed -n '1,240p' docs/benchmarks/OVERVIEW.md
- Tool call: `exec_command` — `find docs/benchmarks -name '[0-9][0-9][0-9][0-9]-*.md' -exec basename {} \; | sed -E 's/^([0-9]{4}).*/\1/' | sort -n | tail -20`
- Tool call: `exec_command` — find docs/benchmarks/2026-06-12 -maxdepth 1 -type f | sort
- Tool call: `exec_command` — sed -n '1,180p' docs/benchmarks/2026-06-10/0014-wave4-contextual-gemma4-rag.md

## Assistant

I’m adding a benchmark report as `0023-setting-up-rag-image-context-min-merge...`; that slug is intentionally covered by the harness’s NL self-reference exclusions, so the report cannot become an answer source in future NL runs.

### Tool Calls

- Tool call: `exec_command` — cp [REDACTED_TMP_PATH] docs/benchmarks/2026-06-12/0023-setting-up-rag-image-context-min-merge-metrics.tsv

## Assistant

The metrics TSV is copied from the generated harness run. I’m writing the short report and linking it from the benchmark overview now.

## Assistant

The report is in place and linked. I’m running formatting and lint checks on the touched Markdown plus Python compile and the benchmark validation checks.

### Tool Calls

- Tool call: `exec_command` — python3 -m py_compile .agents/skills/improving-context-retrieval-skills/scripts/docs-eval.py .agents/skills/improving-context-retrieval-skills/scripts/gold.py .agents/skills/improving-context-retrieval-skills/scripts/...
- Tool call: `exec_command` — python3 .agents/skills/improving-context-retrieval-skills/scripts/check-vcs-boundary.py
- Tool call: `exec_command` — python3 .agents/skills/improving-context-retrieval-skills/scripts/gold.py validate --image-corpus [REDACTED_LOCAL_PATH]/website
- Tool call: `exec_command` — bun --version
- Tool call: `exec_command` — sed -n '1,180p' package.json
- Tool call: `exec_command` — test -x node_modules/.bin/prettier && node_modules/.bin/prettier --version
- Tool call: `exec_command` — test -x node_modules/.bin/markdownlint-cli2 && node_modules/.bin/markdownlint-cli2 --version

## Assistant

The repo dependencies are not installed in this workspace, so I’m using pinned Bun one-shot tools for the touched Markdown/JSON instead of running a repo-wide install or format pass.

### Tool Calls

- Tool call: `exec_command` — bun x prettier@3.8.3 --write .agents/skills/setting-up-rag/SKILL.md .agents/skills/setting-up-rag/CHUNKING.md .agents/skills/setting-up-rag/TUNING.md .agents/skills/retrieving-context/SKILL.md .agents/skills/updating-...

## Assistant

Prettier completed and rewrote the JSON/report formatting. I’m checking whether the one-shot tool changed any dependency metadata before running markdownlint.

### Tool Calls

- Tool call: `exec_command` — jj status
- Tool call: `exec_command` — ls -la | sed -n '1,80p'
- Tool call: `exec_command` — jj diff --stat

## Assistant

The one-shot Prettier run did not change tracked dependency metadata. I’m running markdownlint on the touched Markdown files now.

### Tool Calls

- Tool call: `exec_command` — bun x markdownlint-cli2@0.22.1 .agents/skills/setting-up-rag/SKILL.md .agents/skills/setting-up-rag/CHUNKING.md .agents/skills/setting-up-rag/TUNING.md .agents/skills/retrieving-context/SKILL.md .agents/skills/updatin...

## Assistant

The markdownlint invocation picked up the repo-wide globs from config and reported pre-existing errors across 200 files, not just my files. I’m checking the config and will run a targeted invocation that disables the configured global glob list.

### Tool Calls

- Tool call: `exec_command` — sed -n '1,220p' .markdownlint-cli2.jsonc

## Assistant

I’m looking up the CLI option locally rather than changing config; the goal is just to verify the touched Markdown without sweeping unrelated docs.

### Tool Calls

- Tool call: `exec_command` — bun x markdownlint-cli2@0.22.1 --help

## Assistant

`--no-globs` is the right option. I’m rerunning markdownlint with that so only the named files are checked.

### Tool Calls

- Tool call: `exec_command` — bun x markdownlint-cli2@0.22.1 --no-globs :'.agents/skills/setting-up-rag/SKILL.md' :'.agents/skills/setting-up-rag/CHUNKING.md' :'.agents/skills/setting-up-rag/TUNING.md' :'.agents/skills/retrieving-context/SKILL.md'...

## Assistant

Targeted markdownlint passes. I’m doing a final targeted Prettier check and then I’ll inspect the diff for any unintended changes.

### Tool Calls

- Tool call: `exec_command` — bun x prettier@3.8.3 --check .agents/skills/setting-up-rag/SKILL.md .agents/skills/setting-up-rag/CHUNKING.md .agents/skills/setting-up-rag/TUNING.md .agents/skills/retrieving-context/SKILL.md .agents/skills/updating-...

## Assistant

Formatting and targeted lint are clean. I’m reviewing the final diff and status now, including the generated metrics file, before closing.

### Tool Calls

- Tool call: `exec_command` — jj status
- Tool call: `exec_command` — jj diff --stat
- Tool call: `exec_command` — jj diff -- .agents/skills/improving-context-retrieval-skills/scripts/docs-eval.py .agents/skills/improving-context-retrieval-skills/configs/rag-r.json .agents/skills/setting-up-rag/SKILL.md .agents/skills/setting-up-r...
- Tool call: `exec_command` — sed -n '1,12p' docs/benchmarks/2026-06-12/0023-setting-up-rag-image-context-min-merge-metrics.tsv && wc -l docs/benchmarks/2026-06-12/0023-setting-up-rag-image-context-min-merge-metrics.tsv

## Assistant

The diff is scoped to the harness evaluator/config, three skill docs, and one benchmark report plus TSV. I’m marking the checklist complete; no dev servers or long-running processes are active.

### Tool Calls

- Tool call: `update_plan` — updated task plan

## Assistant

Implemented and benchmarked the image-context retrieval changes in the isolated jj workspace.

Changed:

- [docs-eval.py](./.agents/skills/improving-context-retrieval-skills/scripts/docs-eval.py:88): Phase-0 heading chunking now honors `min_words`, matching the production `setting-up-rag` chunker.
- [rag-r.json](./.agents/skills/improving-context-retrieval-skills/configs/rag-r.json:3): made `min_words: 80` explicit.
- Updated `setting-up-rag`, `retrieving-context`, and `updating-docs` with image-backed project-context guidance: code/docs/session primaries first, real image paths as supporting provenance, and explicit contamination boundaries.
- Added benchmark record: [0023-setting-up-rag-image-context-min-merge.md](./docs/benchmarks/2026-06-12/0023-setting-up-rag-image-context-min-merge.md:1) plus TSV data.

Benchmark result, after patch:

- Image `rag-r` nDCG@10: `0.349 -> 0.379`
- Image `rag-r` recall@20: `0.511 -> 0.553`
- NL `Dr` nDCG@10: `0.223 -> 0.358`
- NL `Dr` recall@20: `0.628 -> 0.782`
- Code `rag-r` nDCG@10 stayed `0.584`; recall@20 stayed `1.000`
- Image chunks dropped `3755 -> 1694`, retrieval p50 `52.7ms -> 38.1ms`

No eval-time LLM was needed, so I did not start vLLM or use Gemma/Nemotron.

Verification:

- `python3 -m py_compile` on harness scripts passed.
- `check-vcs-boundary.py` passed.
- `gold.py validate --image-corpus [REDACTED_LOCAL_PATH]/website` passed.
- Full Phase-0 NL/code/image benchmark passed.
- Targeted Prettier check passed.
- Targeted markdownlint with `--no-globs` passed. A plain markdownlint invocation expands the repo-wide configured globs and still reports pre-existing unrelated lint errors, so I used the targeted form for touched files.

## User

```text
Export transcript, then integrate with $vcs
```

## User

```text
<skill>
<name>vcs</name>
<path>./.agents/skills/vcs/SKILL.md</path>
---
name: vcs
description: Load at the START of new repo work, BEFORE you change any file, so
  you isolate the work in your own workspace/worktree first — and again BEFORE
  any commit, merge, rebase, or publish. Works in any VCS (Jujutsu or Git).
---

# VCS

**Isolate before you edit.** If the prompt gives you an explicit assigned
workspace/worktree path, `cd` there immediately and work in place; that path is
already your isolation, so do **not** create another workspace/worktree. Otherwise,
for any new local work, do not change a single file in the checkout you were
handed. First understand the task well enough to name it `<ide>-<work>` (e.g.
`claude-fix-auth-retry`), then create your own workspace/worktree (§2) and work
there. The one exception: a dedicated cloud/PR session, where you already have
your own clone — then skip isolation.

Then follow this skill for every commit, merge, rebase, and publish too, in
whatever version-control system the repo uses.

## 1. Detect the mode first - before any VCS action

Run `jj root` (or look for a `.jj/` directory).

- **It succeeds -> Jujutsu (jj) mode.** Use jj for everything, **even though Git
  commands also work** — a colocated repo has both `.git` and `.jj`, and a naive
  "is this Git?" check picks the wrong tool. jj is the right tool whenever jj is
  present.
- **It fails / no `.jj` -> Git mode.** Plain Git, including a Git _worktree_ (where
  `.git` is a file pointing into a parent repo). Use Git.

Stay in that mode the whole session and re-confirm it before you publish; never
cross tools (don't run jj in a Git repo, or fall back to raw git in a jj repo).

## 2. For standard flows, run the helper first

Do not spend tokens re-deriving the routine command chain. The bundled helpers
detect the mode and run the standard Git/jj mechanics. Use prose judgment only
when a helper stops for semantic conflict resolution or reports an unexpected
condition.

- **Agent session startup:** local project hooks may run
  `bash <skill-dir>/scripts/session-start.sh --hook <agent> --ide <ide>` before
  you know the task name (`<agent>` is the hook dialect, such as `codex`,
  `claude`, or `agy`). If it prints `NEXT_CWD=...`, `cd` there before edits or
  VCS writes. When the task slug is clear, run
  `bash <skill-dir>/scripts/rename-work.sh <ide>-<work>` from that temporary
  workspace. These helpers record local session ownership outside the tracked
  tree so later guards can reject writes from the shared checkout.
- **Assigned workspace from the user/orchestrator:** if the task gives you an
  explicit workspace/worktree path that is already yours, `cd` there first and
  work in place. Do **not** run `isolate.sh` from the shared checkout and create a
  second workspace; the assigned path is already the isolation.
- **Starting new local work:** from the checkout you were handed, run
  `bash <skill-dir>/scripts/isolate.sh <ide>-<work>`, for example
  `bash <skill-dir>/scripts/isolate.sh codex-fix-auth-retry`. If it prints
  `NEXT_CWD=...` (it created a fresh workspace/worktree), `cd` there **before you
  edit, read, or run anything else** — every command for this work runs from that
  path, not the checkout you started in. Creating the workspace but staying put
  silently writes into the shared checkout. If instead it prints `CREATED=no` you
  are already isolated; work in place. In a dedicated cloud/PR session you already
  have your own clone; skip isolation.
- **Landing committed work on shared `main`:** run
  `bash <skill-dir>/scripts/integrate.sh <branch-or-bookmark>`, for example
  `bash <skill-dir>/scripts/integrate.sh agent-2`. If it prints
  `VCS_CONFLICT=...`, resolve only the listed files using the conflict etiquette
  below, then rerun
  `bash <skill-dir>/scripts/integrate.sh --continue <branch-or-bookmark>`.
  This helper is the standard publish path, not an optional wrapper: raw
  `git push`, `jj bookmark set`, or `jj git push` skip required stale-ref,
  workspace, and `default` cleanup unless the helper explicitly tells you to
  fall back.

`integrate.sh` handles the no-ambiguity finish steps: Git fetch/rebase/push retry,
safe additive Git conflict cleanup for text/JSON files, deterministic
higher-version scalar tie-breaks in config files, jj merge formation, stale
workspace recovery, `main` movement checks, `jj git export`, merged
branch/bookmark deletion when no real remote backs it, parking jj `default` on
`main`, retiring landed jj agent workspaces, and auto-resolving jj conflicts that
are mechanically additive and structurally valid. If it prints `NEXT_CWD=...`,
run any later shell command from that live directory because your jj workspace
was intentionally removed.
In jj mode, `integrate.sh` now also **publishes** `main` to its remote itself
(mirroring git mode) and removes the retired workspace's owner marker, so a clean
run leaves nothing to finish — you are not stranded in the shared `default`. Only
if it reports it could **not** auto-publish (e.g. the remote moved) run exactly
`jj git push --bookmark main` from the live `NEXT_CWD`/`default` workspace as the
fallback. Run it **bare** — that lone push is the one VCS write the guard allows
from the shared checkout; bundling it (`… && jj git push …`) makes the guard
reject it.

Direct file edits, raw VCS writes, and raw publishes may also be guarded by
`vcs-check.sh` through agent hooks. The guard is session-aware: when an agent
runtime omits a tool cwd but the session owns exactly one live, agent-named
workspace/worktree (`claude-*`, `codex-*`, `cursor-*`, `agy-*`, `gemini-*`, ...),
relative shell/file actions are evaluated from that owned workspace instead of
forcing a long `cd <workspace> && ...` prefix on every command. Explicit writes
whose cwd or target is the shared `default`/primary checkout are still refused.
After integration retires the isolated work, use the shared `default`/primary
checkout only when it is clean and parked on `main`.

## 3. Conflict etiquette

When the helper stops for conflicts, the agent's job is semantic resolution:

- Union every additive change. Keep every changelog entry, list/array element,
  and code block that any side added. Do not drop teammates' work.
- For a single-valued field set to different values, keep the higher value.
  Compare values directly; do not rely on "ours" or "theirs" labels.
- Never resolve a whole file with one side (`ours`, `theirs`, `-X ours`).
- Remove every conflict marker: `<<<<<<<`, `=======`, `>>>>>>>`, `|||||||`.
- jj conflicts are diff-style. Drop marker/header lines such as `<<<<<<<`,
  `%%%%%%%`, `\\\\\\\`, `+++++++`, and `>>>>>>>`. If a real content line appears
  with a leading marker prefix like `+- streaming export (...)`, keep the content
  line without that extra marker prefix. When `integrate.sh` prints a
  marker-stripped preview, use it to inspect candidates faster, but still verify
  the final file yourself. For purely additive conflicts, you may apply the
  preview with the printed `conflict-preview.py --write ...` command, then inspect
  structured files and adjust any single-valued fields before `--continue`.
- After editing, rerun the helper with `--continue`; do not invent extra
  publish/cleanup commands unless the helper failed.

## 4. Touch only your own work (shared-checkout etiquette)

Several agents may share one machine, or even one checkout. Act only on the work
**you** authored:

- **Commit and publish only your own changes.** Never `jj describe` / `git commit
-a` a shared checkout's whole dirty tree, and never push a commit that bundles
  edits you didn't make. If the working copy holds changes you don't recognize,
  **stop and surface them** — don't sweep them into your commit or take authorship.
  (Isolating first, §2, is what keeps your working copy yours; the helpers reinforce
  it — `integrate.sh` lands only the branch/bookmark you name, never the live tree.)
- **Clean up only what you created.** An unqualified "clean up" means _your own_
  `<ide>-<work>` workspaces/bookmarks. Do not inspect, reason about, or ask about
  another agent's workspace/bookmark — leave it untouched unless the user names it.
  The one thing you may retire that you didn't create is a sibling jj workspace
  whose work has already **landed on `main`** during an integration task (merged
  residue, handled automatically by `integrate.sh`) — never another agent's
  _unmerged_ work.

## 5. Fallback docs and commits

Detailed fallback markdown lives beside this file. Do not read it up front. Open
the matching fallback only if a helper is missing, reports an unexpected setup
problem, or you are authoring/editing a commit message.

</skill>
```

## Assistant

Using `export-transcript` for the session export, then `vcs` for the integration path. I’ll first read the export procedure, then write the transcript into the repo’s transcript directory before running the integration helper.

### Tool Calls

- Tool call: `exec_command` — sed -n '1,260p' ./.agents/skills/export-transcript/SKILL.md
- Tool call: `exec_command` — sed -n '1,240p' .agents/skills/vcs/SKILL.md
- Tool call: `exec_command` — pwd && jj root && jj status

## Assistant

The workspace is jj-mode and still contains only my intended changes. I’m allocating the transcript filename with the bundled export helper now, then I’ll collect the Codex session log and redact it before integration.

### Tool Calls

- Tool call: `exec_command` — bash .agents/skills/export-transcript/next-index.sh
- Tool call: `exec_command` — ls -la .agents/skills/export-transcript && find .agents/skills/export-transcript -maxdepth 2 -type f -print
- Tool call: `exec_command` — find ~/.codex/sessions -type f -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -10
- Tool call: `exec_command` — jj log -r @ --no-graph --template 'change_id ++ " " ++ commit_id.short() ++ " " ++ description.first_line() ++ "\n"' && git config user.name && git config user.email

## Assistant

The next transcript slot is `0064`, and the latest Codex session log is readable. I’m inspecting its event shape so the export preserves user turns exactly and summarizes tool calls instead of dumping raw JSON.

### Tool Calls

- Tool call: `exec_command` — head -5 [REDACTED_LOCAL_PATH]
- Tool call: `exec_command` — tail -20 [REDACTED_LOCAL_PATH]
- Tool call: `exec_command` — python3 - <<'PY' import json from collections import Counter p='[REDACTED_LOCAL_PATH] c=Counter() with open(p) as f: for line in f: obj=json.loads(line) c[(obj.get('type'), obj.get('role'), obj.get...

## Assistant

I’m generating `0064-codex-image-context-retrieval.md` from the Codex JSONL now. The export will include verbatim user turns with required local-path redactions and summarized tool calls.

### Tool Calls

- Tool call: `exec_command` — python3 - <<'PY' import json import re from pathlib import Path session = Path('[REDACTED_LOCAL_PATH]) out = Path('docs/transcripts/2026-06-12/0064-codex-image-context-retrieval.md') repo_roots = [ '.', '.', ...
