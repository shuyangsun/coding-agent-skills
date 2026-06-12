# SCENARIOS — corpora, gold facts, traps, and the firewall

## Corpora (the factorial's corpus axis)

- **Z** — the **floor**: an empty corpus (zero documents) scored with retrieval
  turned off (`docs-eval.py --no-retrieval`). The absolute "no doc, no RAG"
  baseline; every metric is identically 0. Built by `mk-corpus.py` (an empty `Z/`
  dir) and run **first** so all other cells read as lifts above nothing.
- **GOLD** — a frozen snapshot of today's `docs/` at a pinned revision, scored by
  the **frozen retrieval gate** (Plane 1). Moves here flag _instrument_ drift, not
  skill quality. `check-retrieval.py --qrels-mode pinned`.
- **D** — `updating-docs`-skill-authored: well-structured (clean headings, one
  concept per file, descriptive filenames, front-matter). The Phase-0 stand-in
  (`mk-corpus.py`) preserves the structured docs verbatim.
- **N** — naive dump: identical content and sentinels, structure destroyed
  (front-matter dropped, headings demoted, opaque filenames). Same doc count as D
  in `--mode perdoc` so doc-level recall is not saturated.

N and D carry the **same fact payload**, so any retrieval difference is
attributable to **structure** — the docs-axis signal. Labels for N/D are
**sentinel-derived per corpus** (`check-retrieval.py --qrels-mode sentinel`),
never taken from GOLD's paths (plan §3). (The pinned/sentinel logic lives in
`gold.py`'s `build_qrels`; the `--qrels-mode` flag is exposed on `check-retrieval.py`.)

## The content-type axis: natural language vs code vs image

The corpora above are all **natural language** (`domain = nl`). A second content
type and an image-backed type are scored separately:

- **code** (`domain = code`) — the repo's own [`inception/`](../../../inception)
  TanStack Start app (source + config), loaded by `gold.py`'s code loader (skips
  `node_modules`/build output/lockfiles), snapshot to `corpora/code/` by
  `mk-corpus.py`. "inception only for now."
- **image** (`domain = image`) — selected image assets from a project passed with
  `--image-corpus`, currently exercised with website hero/cookie assets. The image
  loader indexes curated summary text keyed by the real image path, and
  `mk-corpus.py` copies the actual image files into `corpora/image/` so READ
  consumers can inspect the image file when it is relevant.

Code facts pin primaries relative to the `inception/` root (e.g. `src/router.tsx`,
`vite.config.ts`, `package.json`) and are validated against the code corpus, never
the docs corpus. Image facts pin primaries relative to the image corpus root (for
example `shuyang-website/public/hero.webp`) and are validated against the image
summary corpus, never the markdown docs. Coding-session **transcripts** are the
emphasized `nl` content type — long, dialog-shaped prose, a distinct retrieval
challenge from the terse issue/benchmark docs. The scoreboard reports `nl`, `code`,
and `image` with separate metrics so the difference is visible rather than averaged
away.

## The gold facts (the seed table in `gold.py`)

Grounded in this repo's own machine-checkable facts, verified at build time
(every sentinel must still occur in its pinned primary doc):

| Fact                             | Domain | Sentinel(s)                                     | Primary doc (relative to its domain's corpus root)  | difficulty |
| -------------------------------- | ------ | ----------------------------------------------- | --------------------------------------------------- | ---------- |
| benchmark conflict time          | nl     | `380s`, `85s`                                   | `benchmarks/2026-06-06/0000-…`                      | medium     |
| orphan empty head                | nl     | `urruyqxt`                                      | `issues/2026-06-07/0007-…`                          | hard       |
| name-metric durability           | nl     | `reference-transaction`                         | `coding-sessions/2026-06-06/0012-…`                 | medium     |
| Composer 2.5 benchmark           | nl     | `Composer 2.5`                                  | `benchmarks/2026-06-07/0002-…`                      | medium     |
| integrate degenerate merge       | nl     | `degenerate`                                    | `issues/2026-06-07/0003-…`                          | medium     |
| inception toolchain (transcript) | nl     | `native-preview`                                | `coding-sessions/2026-06-07/0028-…`                 | medium     |
| router preload                   | code   | `defaultPreload`                                | `src/router.tsx`                                    | medium     |
| React Compiler wiring            | code   | `@rolldown/plugin-babel`, `reactCompilerPreset` | `vite.config.ts`                                    | hard       |
| typecheck compiler               | code   | `tsgo --noEmit`                                 | `package.json`                                      | medium     |
| resting hero image               | image  | `HERO_RESTING_TEA_LANDING`                      | `shuyang-website/public/hero.webp`                  | medium     |
| resting arm mask                 | image  | `RESTING_ARM_TEXT_MASK`                         | `shuyang-website/public/hero_arm.webp`              | medium     |
| arm-out pose registration        | image  | `HERO_ARM_OUT_CUP_LIFT`                         | `shuyang-website/public/hero_arm_out.webp`          | hard       |
| pointing cutout re-trace         | image  | `POINTING_ARM_CUTOUT_1122`                      | `shuyang-website/public/hero_point_arm.webp`        | hard       |
| pointing idle nudge              | image  | `POINTING_SHIRT_PROMPT_POSE`                    | `shuyang-website/public/hero_point.webp`            | medium     |
| cookie selector figure           | image  | `COOKIE_SELECTOR_PICK_A_COOKIE`                 | `shuyang-website/public/hero_cookie_selection.webp` | medium     |
| essential cookie option          | image  | `COOKIE_OPTION_ESSENTIAL_PLAIN`                 | `shuyang-website/public/cookie_plain.webp`          | medium     |
| analytics cookie option          | image  | `COOKIE_OPTION_ANALYTICS_CHOCOLATE`             | `shuyang-website/public/cookie_chocolate.webp`      | medium     |
| no-cookie option                 | image  | `COOKIE_OPTION_NO_AI_EMPTY_PLATE`               | `shuyang-website/public/cookie_none.webp`           | medium     |
| social preview card              | image  | `LINK_PREVIEW_ASK_ME_ANYTHING`                  | `shuyang-website/public/link-preview.webp`          | medium     |

This is a **seed**. The plan calls for 50–100+ queries (a power calc): enumerate
the cross-link graph as relevance pairs and add anchored paraphrases. Growing the
`FACTS` table in `gold.py` is ordinary round work; validation + the firewall keep
it honest.

## The non-circularity firewall (plan §6, enforced by `gold.py`)

1. **No echoes.** A query may not contain its own sentinel verbatim, and its
   token-trigram Jaccard with the primary doc must stay below `LEXICAL_OVERLAP_MAX`
   (queries are paraphrases, not lookups). Violations fail `gold.py validate`.
2. **Dev/held-out split.** Stable `hash(query_id)` parity (even=dev, odd=held-out),
   never regenerated per round. Tune on dev; clear the bar only on held-out.
3. **Self-reference + index exclusion.** The harness's own plan + its session
   transcript (which quote the gold facts as worked examples) **and every
   `OVERVIEW.md`** directory index are excluded from every corpus
   (`EXCLUDE_GLOBS`), so the gold set never points at a doc that merely cites a
   fact, and a retriever can't score a hit by surfacing the directory listing
   instead of the answer (index docs aggregate many facts' sentinels, which would
   inflate sentinel-mode qrels). Nested VCS roots are also excluded: if
   `jj workspace add <workspace-name>` creates a workspace under the repo, or a
   Git worktree lives under the selected corpus root, its files are not treated as
   newly added corpus files. Selecting that workspace/worktree directly as the
   corpus still works. `.agents/` (skills/harness) is never in the corpus.
   Image-domain eval questions are not written into the image corpus; the only
   indexed image-domain text is the curated image summary keyed to the actual image
   path, so the test cannot be answered by retrieving its own Q&A.
4. **Closed-book control (Phase 1).** Generate with empty context; if the model
   emits a sentinel from parametric memory, exclude that query from factuality.
   `retrieval_hit` (judge-free) is the primary answerability signal regardless.

## The WRITE convention trap (the `--task write` loop)

A sub-agent with **only** `updating-docs` authors into an empty `docs/` from a fixed
fact payload, against a seeded trap: a pre-existing `NNNN` index forcing a
globally-unique number, and a divergent flat doc to standardize. Scored on
`CONV_OK` (durable file signals) and `WRITE_FINDABLE` (the just-authored doc,
indexed against a fixed background index, surfaces in top-k). `next-index.sh` and
`check-convention.sh` (future) own this.

## Contamination firewall (the agents under test)

Sub-agents see **only** the skill under test (`updating-docs`, `setting-up-rag`, _or_
`retrieving-context`) and a realistic task — never this harness, never the gold
queries, never `metrics.tsv`. The RAG-setup agent in particular is **blind to the
gold queries** so it tunes to doc-set properties, not to the test; the READ consumer
sees only `retrieving-context` and the corpus, never the labels it is scored against.
