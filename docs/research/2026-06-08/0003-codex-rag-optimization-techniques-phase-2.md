# Research: Codex Phase 2 RAG Optimization Techniques

**Date:** 2026-06-09
**Status:** Codex Phase 2 research note, expanded with parallel subagent research.
**Area:** context retrieval, code retrieval, long-memory retrieval, RAG answer generation, evaluation, local LLMs
**Sources:** [Optimizing RAG Setup prompt](../../prompts/2026-06-08/0005-optimizing-rag-setup.md), [Phase 1 eval set](../../plans/2026-06-08/0003-rag-eval-set-phase-1.md), [Anthropic Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval), [CoIR](https://github.com/CoIR-team/coir), [FreshStack](https://fresh-stack.github.io/), [TREC 2025 RAG Track](https://pages.nist.gov/trec-browser/trec34/rag/proceedings/), [BGE-M3](https://arxiv.org/abs/2402.03216), [Qwen3 Embedding and Reranker](https://arxiv.org/abs/2506.05176), [jina-embeddings-v4](https://arxiv.org/abs/2506.18902), [jina-code-embeddings](https://arxiv.org/abs/2508.21290), [CodeXEmbed](https://openreview.net/forum?id=z3lG70Azbg), [CodeR](https://arxiv.org/abs/2505.12697), [CoREB](https://arxiv.org/abs/2605.04615), [Nomic Embed Code](https://huggingface.co/nomic-ai/nomic-embed-code), [cAST](https://arxiv.org/abs/2506.15655), [Late Code Chunking](https://openreview.net/forum?id=hY1USmqQou), [RANGER](https://arxiv.org/abs/2509.25257), [GRACE](https://arxiv.org/abs/2509.05980), [GrepRAG](https://arxiv.org/abs/2601.23254), [Late Chunking](https://arxiv.org/abs/2409.04701), [Reconstructing Context](https://arxiv.org/abs/2504.19754), [RAPTOR](https://arxiv.org/abs/2401.18059), [LongRAG](https://arxiv.org/abs/2406.15319), [LightRAG](https://arxiv.org/abs/2410.05779), [HippoRAG2](https://arxiv.org/abs/2502.14802), [PathRAG](https://arxiv.org/abs/2502.14902), [Deep GraphRAG](https://arxiv.org/abs/2601.11144), [HyDE](https://arxiv.org/abs/2212.10496), [Self-RAG](https://arxiv.org/abs/2310.11511), [CoRAG](https://arxiv.org/abs/2501.14342), [CRAG](https://arxiv.org/abs/2401.15884), [RankRAG](https://arxiv.org/abs/2407.02485), [ARES](https://aclanthology.org/2024.naacl-long.20/), [RAGAS](https://arxiv.org/abs/2309.15217), [MiniCheck](https://arxiv.org/abs/2404.10774), [RePCS](https://arxiv.org/abs/2506.15513)

## Summary

Phase 2 should optimize `setting-up-rag` and `retrieving-context` by running a
measured, modular retrieval stack against the 207 verified Phase 1 gold facts
across all six repositories. The likely winning system is not a single GraphRAG
or vector-database switch. The strongest path is to keep the current hybrid
dense+sparse baseline with reranking, then benchmark cheap lexical retrieval,
stronger embeddings/rerankers, contextualized chunks, parent-document expansion,
code-specific retrieval, long-memory retrieval, graph/source-map overlays,
adaptive query planning, and citation-grounded answer generation as separate
arms.

Parallel subagent research changed the priority order. `domain=code` must not be
treated as prose retrieval over source files; it needs lexical, AST, symbol,
dependency, graph, code-embedding, and code-reranker arms. Long coding-session
history also needs temporal/session metadata and parent windows, not only
markdown heading chunks. Evaluation should remain deterministic first, but Phase
2 should add nugget and sentence-citation support metrics so retrieval and answer
quality are not conflated.

The user does need a local LLM for the full optimization loop, but not for the
first baseline. A local instruction model should generate index-time chunk
context, session summaries, graph/source-map capsules, query rewrites,
hypothetical documents, adaptive retrieval plans, and optional claim checks
cheaply. The gate for accepting a change should remain deterministic: Phase 1
sentinels, primary-file `qrels`, nDCG/MRR/recall, unsupported-claim rate,
latency, and context-token cost.

## Retrieval Findings

Anthropic-style Contextual Retrieval remains directly applicable. It prepends
short chunk-specific context before embedding and BM25 indexing, then combines
dense retrieval, BM25, rank fusion, and reranking. Anthropic reported top-20
retrieval failure reductions of 49% for contextual embeddings plus contextual
BM25, and 67% when reranking was added. For these repos, the context generator
should include source path, repo, section, date/status, symbols, mentioned files,
and transcript provenance, while preserving the raw source chunk for citations
and verification.

The baseline embedding stack should be challenged, not trusted. `setting-up-rag`
currently defaults to `BAAI/bge-small-en-v1.5` plus Qdrant BM25 and a small
MiniLM cross-encoder. Candidate upgrades include `BAAI/bge-m3`, which supports
dense, sparse, and multi-vector retrieval; Qwen3 Embedding and Qwen3 Reranker,
which provide 0.6B, 4B, and 8B retrieval/reranking sizes; and Jina v4, which
supports single-vector and late-interaction multi-vector retrieval. These should
be measured as plain model swaps before adding generated context.

Code retrieval needs a separate stack. CoIR has become a standard code retrieval
benchmark with 10 curated datasets, 8 retrieval tasks, and a BEIR/MTEB-compatible
shape. FreshStack similarly focuses on realistic technical-document retrieval
with community questions, code/docs corpora, nugget support, and hybrid
retrieval. For this repo, those findings map directly to the Phase 1 schema:
evaluate code and technical docs separately, use graded relevance, and report
per-query slices instead of one averaged score.

Code-specific embedding candidates now include CodeXEmbed, Jina code embeddings,
Qwen3 Embedding, CodeR, Nomic Embed Code, and optional hosted baselines such as
Voyage Code 3. CoREB is the warning label: code-specialized embeddings dominate
some code-to-code tasks, but no single model wins everything, and off-the-shelf
rerankers can hurt code retrieval. Add no-rerank, current MiniLM, BGE/Jina/Qwen,
and CoREB-style reranker arms where local dependencies allow.

Chunking is a first-class retrieval variable for source code. cAST recursively
splits and merges AST nodes to preserve semantic structure, and Late Code
Chunking separates retrieval context from comprehension context to reduce
semantic loss. Phase 2 should test current block packing against tree-sitter
function/class chunks, cAST-style recursive AST chunks, and LC2-style dual
contexts before heavier graph retrieval is attempted.

Cheap lexical retrieval is still a serious baseline. GrepRAG shows that
LLM-generated `ripgrep` plus identifier-weighted reranking and structure-aware
deduplication can rival heavier graph/vector methods in repository code
completion. For Phase 2, a local `rg`/SQLite FTS5/BM25 arm with path, symbol, and
identifier weighting is a required control, not a fallback.

Parent-document retrieval is likely the highest-return first change for
transcripts and docs. Retrieve precise child chunks, then pass the parent
section, file window, or session-turn window to the generator. This requires
payload fields such as `parent_id`, `heading_path`, `session_id`, byte offsets,
turn indexes, and mentioned-file lists, but no heavy new model. It directly
targets the failure mode where a chunk says "this fix" or "the helper" without
the surrounding session context.

Late chunking is a strong candidate for long coding-session transcripts. Instead
of chunking first and embedding isolated text, late chunking embeds the long
document first and pools chunk vectors afterward, preserving surrounding context
without a per-chunk LLM call. It should be tested on the `nl` domain for
`coding-agent-skills` and `website` transcripts before it is used for code.
Reconstructing Context suggests contextual retrieval can be stronger, but late
chunking is cheaper and avoids index-time generation.

Long-context reader arms should be measured, not assumed. LongRAG-style larger
retrieval units can help whole-session or whole-file questions when the reader
model can handle them, but long contexts are vulnerable to ordering effects and
"lost in the middle" behavior. Test `score-order`, `source-order`, and
parent-before-child context layouts.

Graph retrieval is useful for the right slice. Microsoft GraphRAG targets global
sensemaking questions with entity graphs and community summaries; LightRAG
combines graph structures with vector retrieval and incremental updates; RAPTOR
retrieves over a recursive summary tree; HippoRAG2 and PathRAG focus on
associative memory and path pruning; Deep GraphRAG adds hierarchical
global-to-local filtering and dynamic reranking. These are promising for
multi-hop history, architecture, and "what changed across the project?" questions.
They should not replace hybrid Qdrant retrieval for exact source-path, symbol,
command, and error-string lookups unless held-out metrics prove they win.

Repository code graphs should start as overlays. RANGER and GRACE show that
repository knowledge graphs, call/import/class/data-flow edges, and
graph-neighborhood reranking can recover cross-file dependencies that plain
similarity misses. The practical Phase 2 design is to test deterministic
source-graph expansion, path/symbol boosting, import/include neighborhood
expansion, and graph-to-Qdrant reranking before full LLM GraphRAG.

Diversity-aware retrieval is a cheap next arm. MMR or dynamic diversity over RRF
results can reduce redundant near-matches and recover complementary evidence for
hard multi-file questions. This should be measured before adding expensive
agentic query planning.

Query transforms should be gated carefully. HyDE can help when a terse query
lacks the corpus vocabulary by generating a hypothetical answer document and
embedding that. Multi-query expansion can recover synonyms and alternate
phrasings. Both can hurt exact code and identifier queries by diluting lexical
signal, so they should run only for query classes that prove a dev-split lift.

Adaptive routing belongs in `retrieving-context`. RAGRouter-style and
LLM-independent adaptive RAG research argues for choosing routes by query shape,
corpus type, and cost, not by a blanket "always use RAG" rule. A feature router
can start with deterministic features: repo, `domain`, query length, code
identifier density, path mentions, difficulty estimate, multi-hop markers,
available local index, and previous retrieval confidence.

## Answer-Generation Findings

Answer quality should be optimized after retrieval quality is measurable. The
answer loop should pack evidence by reranked primary chunks, source diversity,
parent-child relationships, source order, and token budget; enforce sentence-level
source citations; deduplicate near-identical chunks; and run deterministic
sentinel and citation-support checks.

Current public RAG evaluations are moving toward decomposition, evidence
coverage, and attribution. The TREC 2025 RAG track emphasizes long narrative
queries, transparency, factual grounding, relevance assessment, response
completeness, attribution verification, and agreement analysis. Several runs use
sparse+dense fusion, late-interaction reranking, nugget decomposition, and
sentence-level citations. Phase 2 should mirror that locally with deterministic
surrogates: subquery/nugget coverage for multi-part questions, sentence support
against citations, and explicit citation reliability.

Agentic RAG techniques are useful only after the static baseline is clear. CoRAG
dynamically reformulates retrieval queries through a chain of retrieval steps;
CRAG grades retrieved evidence and corrects low-quality retrieval; RankRAG uses
an instruction-tuned LLM for both context ranking and generation; Self-RAG
supports adaptive retrieval and reflection. These should become later adaptive
arms that trigger only when the first-pass evidence is weak, because they add
local LLM latency and can obscure whether the base index improved.

Context packing should become a measured stage. Compare raw top-20 chunks against
2k, 4k, and 8k token extractive packs that preserve source IDs, parent headers,
source order, and deduplicated spans. Score sentinel coverage per token,
unsupported-claim rate, and tokens-to-primary, not just answer hit.

Claim and citation verification should be layered. Phase 1 sentinel containment
is a strong deterministic guard, but it does not catch a fluent answer that cites
a real chunk for an unsupported claim. Add sentence-level citation schemas first,
then optional MiniCheck/HHEM-style local claim classifiers or ARES/RAGAS-style
advisory evaluators. LLM judges should diagnose, not gate.

## Evaluation Findings

The primary gate should remain deterministic IR. Use graded `qrels` from Phase 1
primary paths and sentinel-bearing chunks, then report nDCG@10, recall@5/20/100,
MRR, precision@k, MAP, primary-file MRR, answer hit@5, and sentinel coverage.
`ranx`, `ir-measures`, or `pytrec_eval` are appropriate local dependencies.

Evaluation must report slices, not only global means. Required slices are repo,
`domain=code` vs `domain=nl`, session transcript vs design doc vs codebase,
easy/medium/hard, single-hop vs multi-hop, one-primary vs multi-primary,
answerable vs abstain/unanswerable, and source agent (`claude` vs `codex`) where
useful. A global average can hide the exact regressions Phase 2 is trying to fix.

Contamination controls should be explicit. Keep the existing non-echo query rule
and self-reference exclusions, but add closed-book generation, wrong-context
distractor runs, and shuffled-citation runs. RePCS-style comparison between
parametric-only and RAG paths can flag answers that do not depend on retrieved
evidence.

Cost and latency are first-class metrics. Track index time, query embedding time,
sparse/dense retrieval time, fusion time, graph expansion time, rerank time,
generation time, p50/p95 end-to-end latency, context tokens, prompt/output tokens,
reranker calls, judge calls, model size/download size, and cost per correct
faithful answer.

## Local LLM Need

Use a local LLM in Phase 3 for cost control. It is needed for:

- index-time contextual retrieval text for markdown docs and transcripts;
- source-map, graph-context, or symbol-context capsules for code chunks;
- session summaries and RAPTOR/GraphRAG/LightRAG summaries;
- HyDE documents and multi-query rewrites at query time;
- adaptive retrieval policies such as CoRAG or CRAG;
- optional claim-level answer checks for diagnostics.

Do not require the local LLM for the first baseline run. It is not needed for
plain hybrid retrieval, BM25/FTS5/`rg`, parent-document retrieval, code-symbol
indexing, late chunking, embedding swaps, or reranker swaps. Once the baseline is
recorded, the local LLM can be introduced as a measured variable with its own
index-time tokens, latency, cache hit rate, and model-quality sensitivity.

## Recommendation

Phase 2 should turn the research into benchmarkable arms:

1. `plain-current`: current FastEmbed dense + Qdrant BM25 + RRF + MiniLM rerank.
2. `plain-strong`: stronger local dense/rerank model sweep, no generated context.
3. `lexical-code`: `rg`/FTS5/BM25 plus identifier weighting and deduplication.
4. `code-specialized`: code chunking plus code-specific embeddings/rerankers.
5. `ast-code`: tree-sitter, cAST-style, and LC2-style chunking for source files.
6. `parent-window`: child retrieval plus parent section/file/session windows.
7. `contextual`: local-LLM chunk context added before dense and sparse indexing.
8. `late-chunk`: late chunking for transcript-heavy `nl` corpora.
9. `long-reader`: large retrieved units with source-order and score-order packing.
10. `diverse-rerank`: RRF plus MMR/static and dynamic diversity.
11. `repo-graph-code`: import/include/call/symbol graph expansion with reranking.
12. `graph-hierarchical`: GraphRAG, LightRAG, RAPTOR, HippoRAG2, or PathRAG only
    for multi-hop/global slices.
13. `query-transform`: HyDE or multi-query expansion only where dev metrics lift.
14. `adaptive-router`: deterministic feature router across manual, RAG, graph,
    long-context, and corrective routes.
15. `adaptive-rag`: CoRAG/CRAG/RankRAG-style iterative retrieval and evidence
    grading after static retrieval arms.
16. `context-packer`: source-preserving extractive packing at fixed token budgets.
17. `citation-verifier`: sentence-level citation support plus optional local claim
    verification.

Promote a technique into `setting-up-rag` or `retrieving-context` only after it
improves held-out Phase 1 metrics without regressing another repo/domain slice or
making index/query cost unacceptable. Avoid starting with RL-trained retrievers,
full LLM GraphRAG, or heavy compressors; first prove cheap inference-time variants
beat the current config on the 207-query gold set.
