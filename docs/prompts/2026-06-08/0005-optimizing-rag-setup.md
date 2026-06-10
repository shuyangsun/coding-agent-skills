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
this machine _before_ starting Wave 3/4 so a LAN or firewall problem surfaces
before a long indexing run. Keep all of this in the **campaign** config; the
portable `setting-up-rag` default stays CPU-only and requires no network LLM.

##### The live endpoint on this workstation (concrete values)

The GPU box already runs this stack, so the harness can target it directly instead
of the `<gpu-host>:<port>` placeholders above:

- **Base URL:** `https://llm.shuyangsun.com/v1` (OpenAI-compatible). A custom DNS
  record points `llm.shuyangsun.com` at the workstation, so the same URL resolves
  from any machine on the `192.168.0.0/24` LAN (and from the box itself). TLS
  terminates at an nginx front (TLS 1.3, HTTP/2 + HTTP/3) that reverse-proxies to
  the LiteLLM proxy on `127.0.0.1:8080`; access is IP-allowlisted to the LAN plus
  localhost, so the port is not open to the public internet.
- **API key:** every request needs `Authorization: Bearer <key>`. Source the
  LiteLLM proxy key from your secret manager into the environment — never hard-code
  it in the harness or commit it:

  ```sh
  export LITELLM_API_KEY="<your-litellm-proxy-key>"      # from your secret manager
  export OPENAI_API_BASE="https://llm.shuyangsun.com/v1"
  export OPENAI_API_KEY="$LITELLM_API_KEY"               # OpenAI-style SDKs read these
  ```

- **Served model name:** `gemma-4` — Gemma-4-31B-IT (NVFP4 quant, 256K context),
  served by vLLM behind the proxy. This is the generative model for contextual
  headers, query rewrites, graph/source-map summaries, answer generation, and
  advisory judges (Wave 4+). Embedding/reranker models are **not** on the proxy yet;
  they are added as extra `model_list` entries on this same LiteLLM gateway when
  Wave 3 brings TEI/Infinity retrieval serving online. Always discover what is live
  with `/v1/models` rather than assuming.

Smoke-test the endpoint before any long Wave-3/4 run (this is the "one completion +
one embedding" health check):

```sh
# 1) list the models the proxy currently serves
curl -s https://llm.shuyangsun.com/v1/models \
  -H "Authorization: Bearer $LITELLM_API_KEY" | jq -r '.data[].id'

# 2) one chat completion against the generative model
curl -s https://llm.shuyangsun.com/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"gemma-4","messages":[{"role":"user","content":"ping"}],"max_tokens":8}' \
  | jq -r '.choices[0].message.content'
```

From Python (the harness uses the OpenAI SDK):

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://llm.shuyangsun.com/v1",
    api_key=os.environ["LITELLM_API_KEY"],
)
print(
    client.chat.completions.create(
        model="gemma-4",
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=8,
    ).choices[0].message.content
)
```

The proxy runs with `drop_params: true`, so Anthropic-only request fields are
silently dropped and OpenAI-style calls just work. Once a Wave-3 embedding model is
registered on the proxy, add a one-shot `client.embeddings.create(...)` to the
health check so a LAN/firewall/serving problem surfaces before a long indexing run.

##### Models staged on the NAS (downloaded and ready)

Embedding and reranker weights are already downloaded to the Synology NAS at
`/mnt/nas/home/ml/model/{embedding,reranker}/` (full HF snapshots, verified
complete; generative LLMs are managed separately under `…/model/llm/`). The
campaign serves these from the GPU box via TEI/Infinity by pointing the server at
the local dir — no re-download. **`license` drives the deliverable split: only
Apache-2.0 / MIT models may ship in the portable `setting-up-rag` default;**
everything else (Gemma-, `other`-, and `cc-by-nc`-licensed) is **campaign-only**,
and non-commercial weights are flagged **NC** so they never leak into the portable
default. The portable defaults (`bge-small`, MiniLM reranker) are also fetched
automatically by FastEmbed on first use; the NAS copies exist for offline/campaign
serving.

Embedding — `…/model/embedding/<dir>`:

| dir                              | HF repo                                 | size  | license             | role                                                                      |
| -------------------------------- | --------------------------------------- | ----- | ------------------- | ------------------------------------------------------------------------- |
| `bge-small-en-v1.5`              | BAAI/bge-small-en-v1.5                  | 0.4 G | MIT                 | **portable dense default** (current), 384-d, ONNX/CPU                     |
| `bge-base-en-v1.5`               | BAAI/bge-base-en-v1.5                   | 1.3 G | MIT                 | portable dense alt, 768-d, ONNX/CPU                                       |
| `splade-pp-en-v1`                | prithivida/Splade_PP_en_v1              | 0.9 G | Apache-2.0          | portable learned-sparse (prose A/B vs BM25), ONNX/CPU                     |
| `mxbai-embed-large-v1`           | mixedbread-ai/mxbai-embed-large-v1      | 5.0 G | Apache-2.0          | portable strong English dense (335 M), ONNX                               |
| `bge-m3`                         | BAAI/bge-m3                             | 4.3 G | MIT                 | portable multilingual + long-context (8 k); dense/sparse/ColBERT          |
| `multilingual-e5-large-instruct` | intfloat/multilingual-e5-large-instruct | 3.2 G | MIT                 | portable multilingual (good for the xiang-qi Chinese slice)               |
| `snowflake-arctic-embed-l-v2.0`  | Snowflake/snowflake-arctic-embed-l-v2.0 | 9.1 G | Apache-2.0          | strong multilingual dense (568 M), Matryoshka; GPU-preferred              |
| `embeddinggemma-300m`            | google/embeddinggemma-300m              | 1.2 G | Gemma               | small strong dense (308 M); Gemma license → campaign, not the OSI default |
| `qwen3-embedding-0.6b`           | Qwen/Qwen3-Embedding-0.6B               | 1.2 G | Apache-2.0          | campaign dense, fast                                                      |
| `qwen3-embedding-4b`             | Qwen/Qwen3-Embedding-4B                 | 7.6 G | Apache-2.0          | **campaign dense sweet spot**                                             |
| `qwen3-embedding-8b`             | Qwen/Qwen3-Embedding-8B                 | 15 G  | Apache-2.0          | campaign dense, MTEB-ceiling quality                                      |
| `bge-code-v1`                    | BAAI/bge-code-v1                        | 5.8 G | Apache-2.0          | **campaign code embedder** (permissive)                                   |
| `sfr-embedding-code-2b-r`        | Salesforce/SFR-Embedding-Code-2B_R      | 4.9 G | cc-by-nc-4.0 **NC** | campaign code embedder (non-commercial)                                   |

Reranker — `…/model/reranker/<dir>`:

| dir                          | HF repo                              | size  | license             | role                                                        |
| ---------------------------- | ------------------------------------ | ----- | ------------------- | ----------------------------------------------------------- |
| `ms-marco-minilm-l6-v2-onnx` | Xenova/ms-marco-MiniLM-L-6-v2        | 0.3 G | Apache-2.0\*        | **portable rerank default** (current), ONNX/CPU             |
| `ms-marco-minilm-l6-v2`      | cross-encoder/ms-marco-MiniLM-L-6-v2 | 0.8 G | Apache-2.0          | same model, PyTorch/sentence-transformers source            |
| `bge-reranker-v2-m3`         | BAAI/bge-reranker-v2-m3              | 2.2 G | Apache-2.0          | **campaign reranker, permissive** (568 M, multilingual)     |
| `qwen3-reranker-0.6b`        | Qwen/Qwen3-Reranker-0.6B             | 1.2 G | Apache-2.0          | campaign reranker, fast                                     |
| `qwen3-reranker-4b`          | Qwen/Qwen3-Reranker-4B               | 7.6 G | Apache-2.0          | **campaign reranker, SOTA** (plan's pick)                   |
| `mxbai-rerank-base-v2`       | mixedbread-ai/mxbai-rerank-base-v2   | 1.0 G | Apache-2.0          | campaign reranker (0.5 B)                                   |
| `mxbai-rerank-large-v2`      | mixedbread-ai/mxbai-rerank-large-v2  | 2.9 G | Apache-2.0          | campaign reranker (1.5 B)                                   |
| `zerank-1-small`             | zeroentropy/zerank-1-small           | 3.3 G | Apache-2.0          | campaign instruction reranker (permissive)                  |
| `zerank-2`                   | zeroentropy/zerank-2                 | 7.6 G | cc-by-nc-4.0 **NC** | campaign instruction reranker, newest SOTA (non-commercial) |

\* `Xenova/ms-marco-MiniLM-L-6-v2` is an ONNX re-export of the Apache-2.0
`cross-encoder/ms-marco-MiniLM-L-6-v2`; its card omits the field but the weights
inherit Apache-2.0.

Starting picks per the plan's hypotheses (Wave 3 embed/rerank sweep):

- **Portable default (ships in the skill — Apache/MIT, CPU-only):** dense
  `bge-small-en-v1.5`, then A/B `bge-base-en-v1.5` and `mxbai-embed-large-v1`;
  sparse BM25 for code with `splade-pp-en-v1` as the prose A/B; rerank
  `ms-marco-MiniLM-L-6-v2`. Promote a heavier model into this default **only** if
  it is Apache/MIT and clears the promotion gate on CPU.
- **Campaign dense (GPU):** `qwen3-embedding-4b` is the primary sweep point
  (`0.6b` for latency, `8b` for the ceiling). For the code-heavy repos add
  `bge-code-v1` (permissive) and, for local-only runs, `sfr-embedding-code-2b-r`
  (**NC**). `bge-m3`, `snowflake-arctic-embed-l-v2.0`, and
  `multilingual-e5-large-instruct` cover long prose and the xiang-qi Chinese terms.
- **Campaign reranker (GPU):** baseline `bge-reranker-v2-m3` (permissive) vs
  `qwen3-reranker-4b` (SOTA) and `mxbai-rerank-large-v2`; `zerank-1-small`
  (Apache) and `zerank-2` (**NC**) add instruction-aware, calibrated reranking.

Remember the Qwen3 decoder embedders/rerankers need the correct query-vs-document
instruction prefixes wired into both the index and query paths before the numbers
are trustworthy (plan Wave 3, step 2).
