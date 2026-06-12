# Setting-Up-RAG Image Context Min-Merge Check

- **Date:** 2026-06-12
- **Skills:** [`setting-up-rag`](../../../.agents/skills/setting-up-rag/SKILL.md), [`retrieving-context`](../../../.agents/skills/retrieving-context/SKILL.md), [`updating-docs`](../../../.agents/skills/updating-docs/SKILL.md)
- **Harness:** [`improving-context-retrieval-skills`](../../../.agents/skills/improving-context-retrieval-skills/SKILL.md) Phase 0
- **Artifact:** [`0023-setting-up-rag-image-context-min-merge-metrics.tsv`](0023-setting-up-rag-image-context-min-merge-metrics.tsv)
- **Disposition:** Keep. The Phase-0 evaluator now honors the `min_words` floor already used by the production `setting-up-rag` chunker, and the three retrieval skills now describe image-backed project context without making image retrieval higher priority than code or natural-language retrieval.

## Summary

The image-backed website corpus exposed a harness bug: the Phase-0 heading chunker did not merge tiny adjacent sections, so the `rag-r` config was evaluated as 3,755 image chunks averaging 83.6 words instead of the min-merge behavior that `setting-up-rag` already documents and implements.

Honoring `min_words=80` reduced the image index to 1,694 chunks averaging 185.7 words and improved image retrieval while also improving the natural-language structured-doc cell and preserving code.

| slice                 | metric        |  before |   after |    delta |
| --------------------- | ------------- | ------: | ------: | -------: |
| image `rag-r`         | nDCG@10       |   0.349 |   0.379 |   +0.030 |
| image `rag-r`         | recall@20     |   0.511 |   0.553 |   +0.042 |
| image `rag-r`         | MRR           |   0.781 |   0.794 |   +0.012 |
| image `rag-r`         | retrieval p50 | 52.7 ms | 38.1 ms | -14.6 ms |
| natural language `Dr` | nDCG@10       |   0.223 |   0.358 |   +0.136 |
| natural language `Dr` | recall@20     |   0.628 |   0.782 |   +0.154 |
| code `rag-r`          | nDCG@10       |   0.584 |   0.584 |   +0.000 |
| code `rag-r`          | recall@20     |   1.000 |   1.000 |   +0.000 |

## Decision

- Patch the Phase-0 evaluator so `chunker.min_words` is real for heading chunks.
- Keep `min_words=80` in the harness `rag-r` config. A sweep found `min_words=120` can raise image nDCG further, but `min_words=80` is the better balanced default because it gives the stronger natural-language result while still improving image retrieval.
- Update `setting-up-rag` to describe image-backed project corpora as code/docs/session primaries plus real image-path support, not standalone caption retrieval.
- Update `retrieving-context` to tell consumers to retrieve project context first and inspect actual images only when visual detail matters.
- Update `updating-docs` to make image assets findable through explicit paths, purpose, derived-asset relationships, and regeneration rules.

## Contamination

No eval-time LLM was used, so the Gemma 4 / Nemotron split was not invoked in this run. The image corpus was the existing website project context plus already-curated image summaries keyed by real image paths.

The benchmark did not add questions, expected answers, or sentinels to the image corpus. This report is also excluded from the natural-language harness corpus by the existing benchmark self-reference globs because the filename contains `setting-up-rag`.

## Reproduce

```bash
SK=.agents/skills/improving-context-retrieval-skills
H=/tmp/context-retrieval-harness-codex-image-context-post
IMAGE_CORPUS=<website-repo>

python3 "$SK/scripts/check-vcs-boundary.py"
python3 "$SK/scripts/gold.py" validate --image-corpus "$IMAGE_CORPUS"
python3 "$SK/scripts/gold.py" build --out "$H/gold-set" --image-corpus "$IMAGE_CORPUS"
python3 "$SK/scripts/mk-corpus.py" --out "$H/corpora" --image-corpus "$IMAGE_CORPUS"
```

Then run the Phase-0 cells from `LOOP.md` for `Z`, `N/D × b/r`, `code × b/r`, and `image × b/r`, and score with:

```bash
python3 "$SK/scripts/scoreboard.py" --tsv "$H/metrics.tsv" --metric ndcg@10
python3 "$SK/scripts/scoreboard.py" --tsv "$H/metrics.tsv" --metric recall@20
```
