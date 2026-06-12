# Benchmark: `updating-docs` for Contextual Retrieval

**Date:** 2026-06-08
**Harness:** [`improving-context-retrieval-skills`](../../../.agents/skills/improving-context-retrieval-skills/SKILL.md), Phase-0 deterministic retrieval core.
**Under test:** [`updating-docs`](../../../.agents/skills/updating-docs/SKILL.md), specifically whether source-map/context-capsule docs make history and code context easier to retrieve.
**Test projects:** [`inception/`](../../../inception/) and `/Users/shuyang/developer/alpha-zero/`.
**Raw metrics:** [0007-updating-docs-contextual-retrieval-metrics.tsv](0007-updating-docs-contextual-retrieval-metrics.tsv)

## Summary

The existing harness confirms the old result: `inception` code recall is saturated
because the corpus has only 12 files, while natural-language coding-session
retrieval improves mainly when `rag-r` is enabled. The custom project matrix adds
a source-map treatment that represents the new `updating-docs` guidance: a compact
doc that names the parent project, exact primary source paths, and retrieval
anchors.

The strongest signal is token efficiency. On alpha-zero code with `rag-r`, a
source map cut chunk tokens-to-answer from `199` to `99` while keeping
`primary_hit@20 = 1.000`. On inception code with `rag-r`, source-map docs cut
tokens-to-answer from `396` to `75`. For history/prose, source maps lifted
`answer_hit@5` to `1.000` on both projects under `rag-r`.

## Method

The benchmark used two planes:

1. The shipped harness gold set, unchanged, with `docs/` natural-language facts and
   `inception/` code facts. This is the normal 2x2 `N/D x b/r` run and uses
   `gold.py`, `mk-corpus.py`, `docs-eval.py`, `check-retrieval.py`, and
   `scoreboard.py`.
2. A custom matrix using the same `docs-eval.py` retrieval core and the same
   `baseline-b` / `rag-r` configs. It tested four corpora: `inception` coding
   sessions, `inception` code, alpha-zero project memory docs, and alpha-zero code.
   Each corpus was run in a `raw` condition and a synthetic `source-map` condition.

`retrieving-context` was not edited. It was used only as the search-before-write
rule and as the conceptual consumer plane. The available Phase-0 harness does not
ship the workflow runners that would generate real consumer transcripts, so token
usage here is a deterministic proxy: `ctx_tokens_top5_chunks`,
`ctx_tokens_to_answer_chunk`, and `read_tokens_to_primary_doc`.

Alpha-zero has no exported `transcripts/` tree, so its `memory/` project docs
were used as the long-form project-history analogue. No alpha-zero files were
modified during this run.

## Shipped Harness Result

Round `702`, `recall@20` (post-skill-edit rerun; `docs/` corpus = 58 docs):

| Cell | Meaning                             | Recall@20 | Retrieval hit@20 |
| ---- | ----------------------------------- | --------: | ---------------: |
| `Z`  | no docs, no retrieval               |     0.000 |            0.000 |
| `Db` | structured docs, baseline retrieval |     0.642 |            0.833 |
| `Nr` | naive docs, `rag-r`                 |     0.775 |            1.000 |
| `Dr` | structured docs, `rag-r`            |     0.742 |            1.000 |
| `Nb` | naive docs, baseline retrieval      |     0.642 |            0.833 |

The docs marginal stayed flat at baseline and slightly negative under `rag-r`
(`Dr - Nr = -0.033`, 90% CI `[-0.100, 0.000]`) on the tiny six-query NL set. This
does not mean structured docs are bad; it means the current gold set is small and
the existing D corpus lacks explicit retrieval source maps for cross-cutting code
questions.

Content-type split:

| Domain/config | Recall@20 | nDCG@10 | Hit@20 |   MRR |
| ------------- | --------: | ------: | -----: | ----: |
| NL @ `b`      |     0.642 |   0.274 |  0.833 | 0.338 |
| NL @ `r`      |     0.742 |   0.283 |  1.000 | 0.350 |
| code @ `b`    |     1.000 |   0.443 |  1.000 | 0.333 |
| code @ `r`    |     1.000 |   0.584 |  1.000 | 0.478 |

## Custom Source-Map Result

Source maps improved answerability and token-to-answer, but sometimes ranked the
bridge doc above the primary source. That is acceptable only if the source map
links to primary code and the consumer verifies the source.

| Project/domain     | Config  | Condition  | Answer hit@5 | Primary hit@20 | Answer MRR | Primary MRR | Tokens to answer chunk |
| ------------------ | ------- | ---------- | -----------: | -------------: | ---------: | ----------: | ---------------------: |
| inception/history  | `rag-r` | raw        |        0.333 |          1.000 |      0.437 |       0.437 |                    213 |
| inception/history  | `rag-r` | source-map |        1.000 |          1.000 |      1.000 |       0.251 |                    119 |
| inception/code     | `rag-r` | raw        |        0.667 |          1.000 |      0.222 |       0.222 |                    396 |
| inception/code     | `rag-r` | source-map |        1.000 |          1.000 |      1.000 |       0.181 |                     75 |
| alpha-zero/history | `rag-r` | raw        |        1.000 |          1.000 |      0.556 |       0.465 |                     81 |
| alpha-zero/history | `rag-r` | source-map |        1.000 |          1.000 |      1.000 |       0.271 |                     92 |
| alpha-zero/code    | `rag-r` | raw        |        1.000 |          1.000 |      0.417 |       0.226 |                    199 |
| alpha-zero/code    | `rag-r` | source-map |        1.000 |          1.000 |      1.000 |       0.165 |                     99 |

The alpha-zero code corpus is large enough to show a real code-retrieval effect:
`rag-r` improved primary source hits from `0.667` to `1.000` versus `baseline-b`.
Adding a source map then improved answer MRR and reduced tokens-to-answer, but it
lowered primary MRR because the bridge doc ranked first. The skill therefore now
states that source maps must point to verification sources and must not replace
primary code/docs.

## Decision

Keep the `updating-docs` change. The measured treatment supports three added rules:

- add a compact retrieval context line/source capsule near the top;
- use source maps for cross-cutting code context;
- make relationship edges and primary source paths explicit.

Do not change `retrieving-context` from this benchmark. The consumer still needs
the existing "verify against the primary source" behavior because source maps can
rank above code.

## Limitations

- The source-map treatment is synthetic and deterministic, not generated by a blind
  sub-agent using the revised skill.
- Token usage is a Phase-0 proxy over retrieved chunks/docs, not transcript token
  usage from `_score.py`.
- The shipped gold set is still small. The confidence intervals are too wide to
  claim a final factorial win.
- Inception code recall is saturated because there are fewer code files than
  `top_k`; MRR and nDCG are the useful code signals there.
