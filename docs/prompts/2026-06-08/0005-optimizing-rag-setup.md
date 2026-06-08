# Optimizing RAG Setup

Use the [$improving-context-retrieval-skills](/Users/shuyang/developer/coding-agent-skills/.agents/skills/improving-context-retrieval-skills/SKILL.md) harness to improve the [$setting-up-rag](/Users/shuyang/developer/coding-agent-skills/.agents/skills/setting-up-rag/SKILL.md) and the $retrieving-context skill.

## Methodology

Some prior benchmarks were done, but at a very limited scope. This time, use the following repos:

1. `~/developer/coding-agent-skills` (this repository).
2. `~/developer/alpha-zero/alpha-zero`.
3. `~/developer/alpha-zero/alpha-zero-api`.
4. `~/developer/alpha-zero/az-game-tic-tac-toe`.
5. `~/developer/alpha-zero/az-game-xiang-qi`.
6. `~/developer/website`

Use the existing docs files as-is; do not modify the [$updating-docs](/Users/shuyang/developer/coding-agent-skills/.agents/skills/updating-docs/SKILL.md) skill. Focus on RAG.

## Phases

### Phase 1: Collect Eval Set

1. Start with sub-agents and go through ALL 6 repos above. For each repo, come up with 10 to 20 very detailed question-and-answer pairs that require in-depth knowledge to answer.
2. For repos with both code and session transcripts (like `~/developer/coding-agent-skills`), split the question-and-answer pairs into two halves: half about the codebase, half about prompting techniques and historical session recollection.
3. Store these questions per repo in a plan under @docs/plans/, which will be used to optimize RAG setup.

### Phase 2: Research Potential Optimizations

Previous attempts restricted the benchmark to GraphRAG and graphify. This time,
do WHATEVER you want to optimize the important metrics. Research the most recent
SOTA techniques to improve context retrieval and answer generation metrics,
store your findings under @docs/research/, and store your plan in the same plan
file generated from Phase 1.

Document what local dependencies I need to install in advance before starting to
optimize.

Tell me whether you need a local LLM for cheap context generation. I have a
local workstation with two NVIDIA RTX Pro 6000 Blackwell workstation GPUs, so I
can host a local Gemma 4 or other models if you need me to, so we don't waste
money on API call tokens.

### Phase 3: Optimize RAG Setup

The goal is to maximize both retrieval quality and answer-generation quality on
the Phase 1 eval set across all six repositories, run as a measurement-driven
loop rather than a one-shot guess. Establish a baseline first, then change one
variable at a time — chunking, embedding model, hybrid search weights,
reranking, query expansion — re-measure, and keep the change only when the
numbers improve. Continuously explore different optimization techniques, and
record findings under @docs/benchmarks/ as you go, one file per experiment that
names what changed and which metrics moved. Keep improving the metrics until
they reach SOTA on my repositories and further changes stop helping. During the
benchmark, split codebase questions from session transcript questions and
report each cohort separately, so we understand how the system behaves between
code and memory, and can tune each independently rather than averaging away a
regression in one to flatter the other.
