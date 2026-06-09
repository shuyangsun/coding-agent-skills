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

Phases 1 and 2 are done. The Phase-1 gold set (207 verified Q&A across the six
repos) lives at `docs/plans/2026-06-08/0003-rag-eval-set-phase-1/eval-set.json`,
and the **consolidated Phase-2 plan is your execution plan**:
`docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md`. It already
holds the operating rules, the ordered 8-wave roadmap (Wave 0 baselines → Wave 7
answer faithfulness), per-repo starting hypotheses, promotion criteria, and exit
criteria, and a reusable benchmark harness is built and passing its readiness gate
under that plan's `…/harness/` subdir. **Do not re-derive any of this — start from
it and extend it.** If the plan needs to change, edit `0008` in place; don't fork a
new plan.

Work in this order:

1. **Confirm readiness.** Run `harness/validate_prework.py` (GO/NO-GO over 6
   checks) and re-run the gold verifier. Before trusting any number, confirm all
   207 gold `primary` files actually load into their corpus — the shipped
   `CODE_EXTS` omits C++/CUDA/CMake and would silently empty the code domain for
   four of six repos (the harness fixes this; verify it still holds).

2. **Build the Wave-0 runner and declare the baseline.** The harness supplies
   data + indexing + scoring + controls; the missing piece is the runner that
   loops the arm configs per the README's "Wave-0 runner contract." Run every
   baseline arm — `closed-book`, `wrong-context`, `manual-simple`, `plain-current`,
   `plain-current-no-rerank`, `bm25-only`, `dense-only`, and the
   prefetch/top_n/top_k sweep — record latency, index time, and context-token
   cost, then declare the **single baseline config every later experiment must
   beat.**

3. **Then run the wave roadmap as a measurement-driven loop**, one variable at a
   time against the current best (Wave 1 re-index-free wins → Wave 2 LLM-free
   index/payload → Wave 3 GPU retrieval substrate → Wave 4 contextual/long-doc →
   Wave 5 graph/source-map overlays → Wave 6 query routing → Wave 7 answer
   generation). Rebuild the index whenever indexed text, model, payload schema, or
   vector schema changes. Tune on the dev split, report held-out. Keep a change
   only if it clears the **promotion criteria in `0008`**: it beats the held-out
   baseline on the gating metrics (recall@20, nDCG@10, MRR, primary-file MRR) or
   clearly improves answer quality at equal retrieval quality, **without
   regressing any repo / domain / category / difficulty slice** and without
   hurting sentinel coverage or citation support.

4. **Report slices, never just averages.** Every benchmark reports total **and**
   sliced by `domain=code` vs `domain=nl` (and repo, category, difficulty, single-
   vs multi-primary). Critically, the retriever stays **type-blind**: index code
   and docs as one combined corpus per repo and let any query retrieve both.
   `domain` is a reporting slice only, never a corpus partition (12 gold questions
   have primaries spanning both code and docs). Do **not** score or tune a domain
   against a code-only or docs-only index.

5. **Honor the contamination controls.** `coding-agent-skills` contains the eval
   set, the plans, and prior benchmark docs. Keep the hard exclusions (eval set +
   consolidated plan), the per-query synthesis-doc check, and the `closed-book` /
   `wrong-context` arms as standing controls — without them this repo's numbers are
   inflated by self-reference.

6. **Record every experiment** under
   `docs/benchmarks/YYYY-MM-DD/NNNN-<technique>-<scope>.md` (+ optional
   `-metrics.tsv` / `-config.json` / `-summary.json`), naming what changed, which
   metrics moved, and the keep/revert decision.

**Deliverable:** not just "better numbers," but two clearly separated outputs — a
**portable, CPU-clean, license-clean `setting-up-rag` default** (Apache/MIT models
only) shippable in the downloadable skill, **plus** an optional **local-GPU
campaign config** that may use heavier or non-commercial models for my own runs.
Promote a technique into `setting-up-rag` / `retrieving-context` only when it meets
the promotion criteria; otherwise keep it campaign-side. Stop when `0008`'s exit
criteria are met (held-out metrics high and stable on both cohorts, controls clean,
single-variable changes stop winning).

#### Local LLM / GPU — when to set it up, and how to reach it over the LAN

The GPU workstation (2× RTX PRO 6000 Blackwell, ~96 GB each, no NVLink — treat as
two independent VRAM pools) is a **separate machine from the one running the
harness and Qdrant; they share a LAN.** So GPU services must be exposed over the
network, not bound to localhost. Sequencing:

- **Waves 0–2: no GPU needed.** Baselines, re-index-free retrieval wins, and
  LLM-free index/payload changes all run on CPU (FastEmbed `bge-small`, BM25,
  deterministic scoring). Don't block these on the GPU box.
- **Wave 3: bring the GPU box online for retrieval serving.** Stronger embedders
  and rerankers (Qwen3-Embedding-0.6B/4B/8B; Qwen3-Reranker / mxbai / bge-reranker)
  are served from the workstation via TEI / Infinity and called over the LAN.
- **Wave 4+: bring the generative LLM online.** Contextual-retrieval headers,
  Doc2Query/query rewrites, graph/source-map summaries, answer generation, and
  advisory judges need a generative model (vLLM serving Qwen3 / Llama-3.3 /
  Gemma-3, etc.).

To expose it over the LAN, on the **GPU workstation**:

1. Serve each model bound to the LAN interface (`--host 0.0.0.0`), not
   `127.0.0.1`: vLLM for the generative model(s); TEI/Infinity for embeddings and
   rerankers.
2. Front them all with a **LiteLLM proxy** (one OpenAI-compatible gateway) bound
   to `0.0.0.0:<port>` with a master/API key, so the harness has a single base URL
   and model-name routing. Give the box a stable LAN hostname or static IP and open
   that one port to the LAN only — keep it off the public internet.
3. Re-verify current model cards/licenses before pinning any default (this prompt
   earlier floated "Gemma 4"; research only verified the Qwen3 / Llama-3.3 /
   Gemma-3 / Lynx / HHEM families).

On the **harness machine**: point the OpenAI-compatible client at
`http://<gpu-host>:<port>/v1` with the shared key (`OPENAI_API_BASE` / the harness
model config), and run a health check (one completion + one embedding call) from
this machine *before* starting Wave 3/4 so a LAN or firewall problem surfaces
before a long indexing run. Keep all of this in the **campaign** config; the
portable `setting-up-rag` default stays CPU-only and requires no network LLM.
