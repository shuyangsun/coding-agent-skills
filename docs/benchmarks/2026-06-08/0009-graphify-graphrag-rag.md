# Benchmark: Graphify vs Qdrant RAG vs Local GraphRAG

**Date:** 2026-06-08
**Status:** Complete; no `setting-up-rag` skill changes made
**Area:** context retrieval, RAG, GraphRAG, graphify
**Sources:** [graphify v8 how-it-works](https://github.com/safishamsi/graphify/blob/v8/docs/how-it-works.md), [graphify README](https://github.com/safishamsi/graphify/blob/v8/README.md), [Anthropic Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval), [GraphRAG paper](https://arxiv.org/abs/2404.16130), [Microsoft GraphRAG project](https://www.microsoft.com/en-us/research/project/graphrag/), [LightRAG](https://arxiv.org/abs/2410.05779), [Late Chunking](https://arxiv.org/abs/2409.04701)
**Artifacts:** [raw metrics](0009-graphify-graphrag-rag-metrics.tsv), [benchmark script](0009-graphify-graphrag-rag-benchmark.py)

## Summary

This benchmark compared three retrieval paths over `inception/` and `~/developer/alpha-zero/`, using both project code context and coding-session or project-history context.

The current local Qdrant RAG remains the best proven default for history retrieval and small TypeScript app code. It reached `1.000` recall@20 on both history corpora and on `inception` code, but failed all three `alpha-zero` code gold queries. The failure mode was code-specific: natural-language dense/sparse retrieval ranked templates, config, generated-looking files, and adjacent services ahead of the C++ files containing the target implementation.

The local GraphRAG prototype had the best recall profile. It reached `1.000` recall@20 on both domains across both projects with no LLM indexing tokens. It is promising as a source-map or graph-overlay layer, but it is not yet a drop-in replacement because alpha-zero code ranking was weak and the top-5 context was larger than graphify's.

Graphify produced compact query contexts and strong results on the small `inception` code corpus, but it was unreliable for coding-session history. In the final fresh run, graphify's inception history graph pointed many nodes at files mentioned inside transcripts instead of the transcript files containing the evidence, so all three inception history queries missed their primary session file despite a nontrivial LLM extraction cost.

The practical decision is not to replace `setting-up-rag` with graphify. The next likely improvement path is code-aware retrieval for Qdrant plus an optional graph/source-map overlay. Graphify is worth watching or mining for ideas, but it needs provenance fixes and better code query seeding before it can be trusted for this repo's context-retrieval skills.

## Methodology

The benchmark used the `improving-context-retrieval-skills` harness pattern: fixed gold queries, primary source paths, answer sentinels, and repeatable metrics written to TSV. The reproducer script builds isolated scratch corpora and indexes; it does not edit `setting-up-rag`, `inception`, or `alpha-zero`.

Corpora:

| Project      | Domain  | Input corpus                                                                                                                            |
| ------------ | ------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `inception`  | history | 47 markdown files under `docs/coding-sessions/**/*.md`                                                                                  |
| `inception`  | code    | 10 source/config files under `inception/`                                                                                               |
| `alpha-zero` | history | 44 project-history files from `memory/**/*.md` plus `alpha-zero-game/docs/dev_dependencies.md`                                          |
| `alpha-zero` | code    | 181 curated source/config files, excluding hidden agent/editor dirs, build outputs, generated files, dependencies, and third-party code |

Gold set:

- 12 total queries: 3 per project/domain pair.
- Each query has one primary file and one or more answer sentinels.
- History queries target session or memory documents; code queries target implementation/config files.

Methods:

- `qdrant-rag`: the existing `setting-up-rag` scripts, using embedded Qdrant plus FastEmbed on CPU. The active config uses dense `BAAI/bge-small-en-v1.5`, sparse `Qdrant/bm25`, reciprocal-rank fusion, and local cross-encoder reranking with `Xenova/ms-marco-MiniLM-L-6-v2`.
- `local-graphrag`: a local prototype implemented in the benchmark script. It creates file nodes, token/entity nodes, and file-file edges from imports, includes, Markdown links, path mentions, and lexical overlap. Retrieval combines a BM25-like direct score with graph-neighbor expansion. It uses no LLM, no vector DB, and no external API.
- `graphify`: graphify `0.8.35` from branch `v8` at commit `29e57cd295219773b8d300f1c134e41cc7133f05`. The script ran `graphify extract ... --no-cluster` from a local checkout. Markdown/history extraction used the Gemini backend; code-only extraction used graphify's local tree-sitter path and therefore used no LLM tokens. Retrieval scored the generated `graph.json` by source-file provenance, graph node labels, and one-hop graph expansion.

Metrics:

- `recall@20`: whether the primary file was retrieved in the top 20 source-file ranks.
- `answer_hit@5`: whether answer sentinels appeared in the top-5 retrieved context text.
- `primary_mrr`: reciprocal rank of the primary file.
- `ndcg@10`: ranking quality with the primary file as the relevant item.
- `ctx_tokens_top5`: approximate top-5 retrieval context token load, using `chars / 4`.
- `read_tokens_to_primary_doc`: approximate raw-file reading budget needed to reach the primary file by rank; if the primary was absent, this falls back to broad corpus-read cost.
- `index_input_tokens` and `index_output_tokens`: graphify-reported LLM extraction tokens. Qdrant/local GraphRAG used local CPU indexing and record `0` LLM indexing tokens.

## Aggregate Results

Across both projects:

| Method           | Domain  | Queries | Recall@20 | Answer Hit@5 | Primary MRR | NDCG@10 | Ctx Tokens Top5 | Read Tokens To Primary | Retrieval ms |
| ---------------- | ------- | ------: | --------: | -----------: | ----------: | ------: | --------------: | ---------------------: | -----------: |
| `qdrant-rag`     | history |       6 |     1.000 |        0.833 |       0.569 |   0.675 |          1858.8 |                 3125.2 |      1989.71 |
| `qdrant-rag`     | code    |       6 |     0.500 |        0.500 |       0.417 |   0.438 |          1044.0 |                 3381.2 |      1049.70 |
| `local-graphrag` | history |       6 |     1.000 |        0.833 |       0.569 |   0.675 |          1390.8 |                 3975.8 |         2.15 |
| `local-graphrag` | code    |       6 |     1.000 |        0.833 |       0.487 |   0.603 |          1349.7 |                 3882.2 |         1.01 |
| `graphify`       | history |       6 |     0.167 |        0.167 |       0.167 |   0.167 |           259.3 |                23934.0 |         1.18 |
| `graphify`       | code    |       6 |     0.667 |        0.500 |       0.232 |   0.285 |           555.2 |                18842.8 |        25.92 |

By project/domain:

| Method           | Project      | Domain  | Recall@20 | Answer Hit@5 | Primary MRR | Ctx Tokens Top5 | Read Tokens To Primary | Retrieval ms |
| ---------------- | ------------ | ------- | --------: | -----------: | ----------: | --------------: | ---------------------: | -----------: |
| `qdrant-rag`     | `inception`  | history |     1.000 |        1.000 |       0.833 |          2445.7 |                 2572.0 |      1983.80 |
| `qdrant-rag`     | `inception`  | code    |     1.000 |        1.000 |       0.833 |           861.7 |                  239.3 |       493.33 |
| `qdrant-rag`     | `alpha-zero` | history |     1.000 |        0.667 |       0.306 |          1272.0 |                 3678.3 |      1995.62 |
| `qdrant-rag`     | `alpha-zero` | code    |     0.000 |        0.000 |       0.000 |          1226.3 |                 6523.0 |      1606.07 |
| `local-graphrag` | `inception`  | history |     1.000 |        1.000 |       0.833 |          1382.3 |                 2572.0 |         3.04 |
| `local-graphrag` | `inception`  | code    |     1.000 |        1.000 |       0.833 |           868.0 |                  252.0 |         0.14 |
| `local-graphrag` | `alpha-zero` | history |     1.000 |        0.667 |       0.306 |          1399.3 |                 5379.7 |         1.26 |
| `local-graphrag` | `alpha-zero` | code    |     1.000 |        0.667 |       0.141 |          1831.3 |                 7512.3 |         1.88 |
| `graphify`       | `inception`  | history |     0.000 |        0.000 |       0.000 |           279.0 |                43895.7 |         2.03 |
| `graphify`       | `inception`  | code    |     1.000 |        1.000 |       0.444 |           619.0 |                  986.3 |         2.42 |
| `graphify`       | `alpha-zero` | history |     0.333 |        0.333 |       0.333 |           239.7 |                 3972.3 |         0.32 |
| `graphify`       | `alpha-zero` | code    |     0.333 |        0.000 |       0.019 |           491.3 |                36699.3 |        49.42 |

Graphify indexing tokens:

| Project      | Domain  | Graph Nodes | Graph Edges | Index ms | Input Tokens | Output Tokens |
| ------------ | ------- | ----------: | ----------: | -------: | -----------: | ------------: |
| `inception`  | history |          67 |          45 |  24362.4 |       141756 |         11016 |
| `inception`  | code    |         109 |         163 |    284.9 |            0 |             0 |
| `alpha-zero` | history |           9 |           9 |  10425.3 |        52525 |          2015 |
| `alpha-zero` | code    |        1266 |        3180 |   1339.4 |            0 |             0 |

## Findings

Qdrant is still the strongest baseline for natural-language project history. Both history corpora reached perfect recall@20, with answer sentinels in the top five for five of six queries. Its top-5 history context was larger than graphify's, but still reasonable for agent use.

Qdrant needs a code-specific retrieval improvement. The alpha-zero code corpus exposed a failure that natural-language chunking and generic embeddings do not handle well: the relevant C++ files contain symbols and domain terms that are easy to miss when the query is phrased in task language. Path, symbol, language, and build-target signals should be indexed or boosted separately before considering a graphify replacement.

The local GraphRAG prototype is the most promising incremental layer from this run. It found every primary file in the top 20 and cost no LLM tokens. The weakness is rank quality on the larger alpha-zero code corpus: primaries were found, but often below the top few results, and top-5 context was larger than graphify's.

Graphify's compression story is real but conditional. Once a graph exists, graphify context was compact: `259.3` top-5 tokens for history and `555.2` for code on average. The cost moves to indexing for non-code inputs: the two history corpora consumed `194281` input tokens and `13031` output tokens during extraction.

Graphify's coding-session provenance is the blocking issue. The final inception history graph had nodes whose `source_file` values were files mentioned by transcripts, such as `.agents/skills/...`, instead of the transcript file that contained the evidence. That makes graphify poor at answering "which session recorded this?" unless the extraction prompt or graph schema preserves both "evidence file" and "mentioned file".

Graphify's code extraction was useful on the small TypeScript project but weak on the larger mixed C++/Python project. Code-only graphify cost no LLM tokens, but `alpha-zero` code retrieval had `0.333` recall@20 and no answer sentinel hits in the top five. Graph topology alone did not solve code-context retrieval without better query expansion, symbol/path seeding, or a vector sidecar.

## Decision Notes

Do not change `setting-up-rag` yet based on graphify alone. The safer direction is:

- Keep Qdrant/FastEmbed as the default retrieval substrate.
- Add code-aware fields or side indexes: path tokens, symbols, language, build targets, imports/includes, and doc-to-code source maps.
- Consider a small graph overlay, closer to the local GraphRAG prototype, as a routing and expansion layer before Qdrant reranking.
- Re-test graphify only after provenance is fixed for transcripts and query seeding is improved for code.

## Limitations

This is a small benchmark: 12 gold queries total, with 3 queries per project/domain pair. It is enough to expose failure modes, not enough to select a final retrieval architecture.

The benchmark uses deterministic primary-file and sentinel metrics, not an LLM judge. That keeps the results auditable, but it does not measure final answer quality directly.

Graphify LLM extraction is nondeterministic. The final fresh run is reported here, and its provenance failure is reproducible from the saved `graph.json`, but a different backend/model run may produce a different graph.

Latency is machine- and configuration-dependent. Qdrant retrieval includes local embedding and reranking work; graphify query time here is graph JSON traversal after extraction; local GraphRAG is an in-memory prototype.

`alpha-zero` does not have the same exported coding-session history shape as this repo, so its `memory/**/*.md` files were used as the project-history analogue.
