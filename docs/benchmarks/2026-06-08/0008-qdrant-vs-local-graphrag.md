# Benchmark: Qdrant/FastEmbed RAG vs Local GraphRAG

**Date:** 2026-06-08
**Status:** Research benchmark; no skill changes made.
**Harness:** [`improving-context-retrieval-skills`](../../../.agents/skills/improving-context-retrieval-skills/SKILL.md), extended with a one-off local runner.
**Test projects:** [`inception/`](../../../inception/) and `/Users/shuyang/developer/alpha-zero/`.
**Raw metrics:** [0008-qdrant-vs-local-graphrag-metrics.tsv](0008-qdrant-vs-local-graphrag-metrics.tsv)
**Machine summary:** [0008-qdrant-vs-local-graphrag-summary.json](0008-qdrant-vs-local-graphrag-summary.json)
**Runner:** [0008-qdrant-vs-local-graphrag-benchmark.py](0008-qdrant-vs-local-graphrag-benchmark.py)

## Summary

Qdrant/FastEmbed remains the better default retrieval substrate for the
`setting-up-rag` skill. It is slower on CPU because the default config reranks with
a cross-encoder, but it has the stronger production path: hybrid dense+sparse
retrieval, Qdrant storage, and measured code-source retrieval. The local GraphRAG
arm was extremely fast and did well on history/prose, but its deterministic entity
graph is too brittle to replace Qdrant for source-code context.

Do not switch the skill to GraphRAG yet. The useful next move is to add GraphRAG as
an optional benchmark arm for multi-hop/global questions after growing the gold set
and deciding whether to pay for LLM graph extraction.

## What Was Actually Compared

The Qdrant arm used the current [`setting-up-rag`](../../../.agents/skills/setting-up-rag/SKILL.md)
runtime without editing it: embedded Qdrant, FastEmbed `BAAI/bge-small-en-v1.5`
dense embeddings, FastEmbed BM25 sparse embeddings, RRF fusion, and the configured
`Xenova/ms-marco-MiniLM-L-6-v2` cross-encoder reranker.

The GraphRAG arm was a local deterministic implementation in the benchmark runner:
text units, regex/identifier entity extraction, entity co-occurrence relationships,
graph-neighborhood expansion, and BM25 fusion. It mirrors the Microsoft GraphRAG
knowledge-model shape enough for a local benchmark, but it is **not** a full
Microsoft GraphRAG Standard/FastGraphRAG index. Microsoft GraphRAG's documented
pipeline uses LLMs to extract entities/relationships and produce community reports,
and the repository warns that indexing can be expensive.

Microsoft `graphrag` was installed in the benchmark venv (`2.7.2`, constrained by
the local Python 3.10 environment), but no API key or configured local LLM/embedding
endpoint was available for a full Microsoft GraphRAG Standard indexing run. An
Ollama installation with local models was present, but GraphRAG was not configured
to use it as an OpenAI-compatible provider. A one-line `graphrag index --method
fast --skip-validation` probe also failed before graph completion because the NLP
extractor attempted to download NLTK data and hit a local certificate verification
error. The report therefore treats the scored graph arm as "local GraphRAG", not
"full Microsoft GraphRAG".

## Corpora And Queries

The run used 12 fixed gold queries, three per slice:

| Slice                | Corpus                                                                          | Docs | Chunks | Input tokens |
| -------------------- | ------------------------------------------------------------------------------- | ---: | -----: | -----------: |
| `inception/history`  | exported coding-session transcripts mentioning inception/TanStack               |    9 |    141 |       45,048 |
| `inception/code`     | `inception/` source, config, and README                                         |   12 |     15 |        2,385 |
| `alpha-zero/history` | alpha-zero `memory/`, `doc/`, `docs/`, and README prose                         |   58 |    195 |       59,780 |
| `alpha-zero/code`    | alpha-zero source/config files, excluding docs, nested skills, and agent config |  247 |    870 |      207,755 |

Alpha-zero has no exported `coding-sessions/` tree, so the benchmark uses its
project-history docs (`memory/`, `doc/`, `docs/`) as the history/prose analogue.

## Results

Each row is the mean over three queries in that slice. `ctx_top5` is the token
count of the top five retrieved chunks. `tokens_to_answer` is the number of
retrieved chunk tokens consumed before the first chunk/doc containing all sentinel
answer strings; when no answer chunk is found, it is the top-20 token total.

| Slice              | System           | Recall@20 | Answer hit@5 | nDCG@10 |   MRR | p50 ms | ctx_top5 | tokens_to_answer |
| ------------------ | ---------------- | --------: | -----------: | ------: | ----: | -----: | -------: | ---------------: |
| inception/history  | local-graphrag   |     1.000 |        1.000 |   1.000 | 1.000 |    2.9 |    1,977 |              514 |
| inception/history  | qdrant-fastembed |     1.000 |        0.667 |   0.807 | 0.778 |  2,916 |    2,358 |            1,151 |
| inception/code     | local-graphrag   |     1.000 |        1.000 |   0.544 | 0.389 |    0.3 |      912 |              618 |
| inception/code     | qdrant-fastembed |     1.000 |        0.667 |   0.629 | 0.511 |    807 |    1,100 |              699 |
| alpha-zero/history | local-graphrag   |     1.000 |        1.000 |   0.754 | 0.667 |    3.6 |    1,419 |              371 |
| alpha-zero/history | qdrant-fastembed |     0.667 |        1.000 |   0.667 | 0.667 |  2,769 |    1,682 |              678 |
| alpha-zero/code    | local-graphrag   |     0.667 |        0.667 |   0.354 | 0.250 |    9.9 |    1,007 |            1,686 |
| alpha-zero/code    | qdrant-fastembed |     0.667 |        0.333 |   0.333 | 0.357 |  1,992 |    1,140 |            2,666 |

Index time was the main cost gap:

| Slice              | local-graphrag index | qdrant-fastembed index |
| ------------------ | -------------------: | ---------------------: |
| inception/history  |                58 ms |                 15.3 s |
| inception/code     |                 3 ms |                  1.7 s |
| alpha-zero/history |                67 ms |                 21.4 s |
| alpha-zero/code    |               251 ms |                 83.1 s |

Qdrant query latency is dominated by CPU cross-encoder reranking. This is a real
cost of the current `rag-config.json`; disabling rerank or reducing `rerank.top_n`
would change the latency/quality tradeoff and should be tested as its own knob.

## Interpretation

History/prose favored the local graph arm in this tiny benchmark because identifiers
and repeated project terms form strong co-occurrence edges. The local graph arm also
uses no cross-encoder, so it is much faster and uses fewer tokens before the answer
chunk on the history slices.

Code retrieval is less settled. Qdrant/FastEmbed ranked the `inception` code
answers better (`nDCG@10` 0.629 vs 0.544, MRR 0.511 vs 0.389), and both systems
struggled on alpha-zero code because the repo contains repeated templates, generated
game packages, and similar Tic Tac Toe/Xiang Qi APIs. Qdrant found two of three
alpha-zero primary source files in top 20; the local graph arm also found two of
three but ranked one source fact better and one source fact worse.

The important failure mode for the local graph arm is brittleness: regex entities
do not know which identifiers matter, and graph expansion can over-reward repeated
scaffolding names. Full Microsoft GraphRAG would use LLM-extracted entities,
relationships, claims, and community reports, but that moves cost from retrieval
time to indexing time and requires a reliable local or remote LLM.

## Decision Signal

- Keep Qdrant/FastEmbed as the default local RAG setup.
- Do not add Microsoft GraphRAG to `setting-up-rag` yet.
- Add a future optional GraphRAG benchmark arm only after the gold set grows beyond
  12 queries and includes explicitly multi-hop/global questions.
- If GraphRAG is tested again, test full Microsoft GraphRAG with a real configured
  local LLM or API key, not only deterministic graph extraction.
- Tune Qdrant reranking separately: this run shows good ranking but high CPU p50
  latency (`~0.8s` on tiny code, `~2-3s` on prose/alpha-zero).

## Reproduce

The benchmark venv was created outside the repo:

```sh
python3 -m venv "$HOME/.cache/context-retrieval-graphrag-bench/venv"
"$HOME/.cache/context-retrieval-graphrag-bench/venv/bin/python" -m pip install \
  "qdrant-client[fastembed]" networkx pandas pyarrow graphrag
```

Run from the isolated repo workspace:

```sh
CONTEXT_RETRIEVAL_HARNESS_DIR=/tmp/context-retrieval-graphrag-0008 \
  "$HOME/.cache/context-retrieval-graphrag-bench/venv/bin/python" \
  docs/benchmarks/2026-06-08/0008-qdrant-vs-local-graphrag-benchmark.py
```

The script writes the TSV and JSON summary next to this report.

## Sources

- [Microsoft GraphRAG repository](https://github.com/microsoft/graphrag)
- [GraphRAG indexing overview](https://microsoft.github.io/graphrag/index/overview/)
- [GraphRAG query overview](https://microsoft.github.io/graphrag/query/overview/)
- [GraphRAG output schema](https://microsoft.github.io/graphrag/index/outputs/)
- [GraphRAG indexing methods](https://microsoft.github.io/graphrag/index/methods/)
