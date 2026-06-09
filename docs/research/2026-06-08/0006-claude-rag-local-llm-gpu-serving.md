# Research: Local-LLM and GPU Serving Plan for the 2× RTX PRO 6000 Blackwell Workstation

**Date:** 2026-06-08 (last updated 2026-06-09)
**Status:** Research complete — input to [`0005-claude-rag-optimization-phase-2`](../../plans/2026-06-08/0005-claude-rag-optimization-phase-2.md); no skill changes made.
**Area:** local LLM serving (vLLM / SGLang / TEI / Infinity), model selection, quantization (FP8 / NVFP4 / AWQ), prefix caching, two-card topology, the "do I need a local LLM?" decision
**Parent campaign:** "Optimizing RAG Setup" Phase 2 — improving [`setting-up-rag`](../../../.agents/skills/setting-up-rag/SKILL.md) and [`retrieving-context`](../../../.agents/skills/retrieving-context/SKILL.md).
**Sibling notes:** [`0004` retrieval substrate](0004-claude-rag-retrieval-substrate.md), [`0005` contextual indexing + routing + faithfulness](0005-claude-rag-contextual-routing-faithfulness.md).

## Summary — the direct answer

**Yes, host a local LLM. It is worth it, and your hardware is more than enough.** But scope it
precisely:

- **A local generative LLM is NEEDED for** three roles — (1) **index-time contextualization**
  (Anthropic Contextual Retrieval, the single best-supported retrieval lever, one cheap call per
  chunk), (2) **answer generation** (the answer-quality cohort), and (3) **faithfulness judging**
  (Lynx / FaithJudge, advisory). It is also needed for the optional query transforms
  (Doc2Query, decomposition, HippoRAG triple extraction).
- **A local LLM is NOT needed for retrieval itself.** Embedding, sparse, and reranking are
  **not** generative — they are GPU-*served* models (TEI/Infinity), not chat LLMs. And the
  router / self-query / CRAG-evaluator are tiny and CPU-fine.
- **Net:** a local LLM eliminates **all API token cost** for the campaign (contextualizing all
  6 repos and generating + judging 207 answers runs at electricity cost), and unlocks GPU-served
  SOTA embedders/rerankers that are impractical on CPU. There is **also an LLM-free path** for
  contextualization (`pplx-embed-context`, [`0004` §A](0005-claude-rag-contextual-routing-faithfulness.md)) if you'd rather not stand up a generator — but answer-gen and judging still want one.

So: **stand up the local stack.** The rest of this note is the concrete plan.

## 1. The hardware (confirmed) and the one constraint that shapes everything

**2× NVIDIA RTX PRO 6000 Blackwell Workstation Edition:**
- **96 GB GDDR7 ECC each → 192 GB total**, ~1.79 TB/s/card, 24,064 CUDA cores, 752 5th-gen
  Tensor Cores, native **FP8 + NVFP4 (FP4)**, ~126 TFLOPS FP32, ~4000 AI TOPS (FP4), PCIe Gen5,
  600 W, SM 12.0 desktop silicon.
- **CRITICAL: there is NO NVLink.** Inter-GPU traffic crosses **PCIe Gen5 only**. So the right
  pattern is **one model per card (role/data parallel)** — **never tensor-parallel a single
  model across both cards** for latency-sensitive serving (PCIe-only TP collapses throughput to
  ~⅓). Treat the 192 GB as **two independent 96 GB pools**, not one.

**Two consequences:**
- A 70B FP8 model (~70 GB) fits **one** card with ~26 GB KV headroom — but **at the eval's long
  (128K) contexts the KV cache can force TP across both cards**, which then conflicts with
  "pin the embedder+reranker on the spare card." Budget context length accordingly.
- The 235B-class flagship (Qwen3-235B-A22B) is **~235 GB at FP8** and will **not** fit 192 GB —
  it needs 4-bit (AWQ/NVFP4) to fit across both cards. **Out of scope** for latency-sensitive
  serving; skip it.
- **vLLM's certified Blackwell support targets the *Server* Edition.** Same GB202 silicon,
  different board — plan on **source/nightly builds** with `torch_cuda_arch_list` including
  `12.0` for FP4 on the Workstation Edition, and keep **FP8 as the dependable path** (native
  NVFP4 SM120 MoE kernels are newer and have open bugs).

## 2. The model shopping list (all Apache-2.0 unless noted)

| Role | Primary pick | Alt / ceiling | VRAM (FP8) | Notes |
| --- | --- | --- | ---: | --- |
| **Index-time contextualizer** | Qwen3-30B-A3B (MoE, ~3B active) or Gemma-3-12B-it | — | ~32 GB / ~13 GB | quality bar low; **prefix caching critical** |
| **Answer generator** | **Qwen3-32B** | Llama-3.3-70B (ceiling), Gemma-3-27B (xiangqi/Chinese) | ~38 GB / ~70 GB / ~27 GB | Qwen3-32B strong on code, fits one card with big KV |
| **Faithfulness judge** | Patronus **Lynx-70B** (AWQ ~40 GB) or **Lynx-8B** | Llama-3.3-70B / Qwen-2.5-72B (FaithJudge) | ~40 GB / ~16 GB | advisory; **don't** share family with the generator for the headline |
| **NLI faithfulness core** | **HHEM-2.1-Open** (~600 MB) | — | CPU | permissive, deterministic, default-friendly |
| **Dense embedder** | **Qwen3-Embedding-4B** (2560-d) | 0.6B (cheap) / 8B (ceiling) | ~8 GB | served via TEI/Infinity, **not** a chat LLM |
| **Reranker** | **mxbai-rerank-v2** (Apache) or **Qwen3-Reranker-4B** | jina-reranker-v3 (NC, GPU-only) | ~1–9 GB | GPU-served kills the CPU latency |
| **Learned sparse (prose A/B)** | `Splade_PP_en_v1` (Apache) | SPLADE-v3 (NC, internal only) | <2 GB | TEI native SPLADE pooling |

**Skip:** Qwen3-235B-A22B (needs 4-bit across both cards, impractical without NVLink),
non-commercial models for anything that ships in the *published* skill default (jina-reranker-v3,
SPLADE-v3, Provence, NV-Embed-v2, jina-v4). They are fine for the **local GPU campaign**, off the
table for the portable default.

> **Re-pull every leaderboard at campaign time.** Search surfaced apparently-newer families
> (Gemma 4, Qwen3.6/35B-A3B, Mistral 3, GPT-OSS-120B) from aggregator blogs, not official cards.
> The **verifiable** picks today are Qwen3-32B, Llama-3.3-70B, Qwen-2.5-72B, Gemma-3-27B,
> Lynx-8B/70B, Qwen3-Embedding, mxbai-rerank-v2. Confirm exact version strings on HuggingFace
> before pinning, and pick the generator/judge on your own corpus eval — the circulating Qwen3
> faithfulness/SimpleQA numbers are **unsourced/contested**.

## 3. Serving engines and the prefix-caching trick

- **vLLM** — broad default for **answer-gen + judge**: FP8, continuous batching, Automatic
  Prefix Caching (APC), and **structured output** (`guided_json` via xgrammar — use it so judge
  verdicts parse deterministically).
- **SGLang** — for the **prefix-heavy contextualization** pass: RadixAttention reuses the shared
  document prefix across all of a document's chunk calls, and SGLang ships **batch-invariant
  deterministic** serving (good for reproducible judging).
- **TEI** (HuggingFace Text-Embeddings-Inference) **or Infinity** — for the **GPU embedder +
  reranker** (and SPLADE via TEI's native `--pooling splade`). Comparable throughput; Infinity
  also serves late-interaction/ColPali if you ever test ColBERT.
- **llama.cpp / Ollama** — the **CPU-portable fallback** the *published* skill must keep
  (`bge-small` + MiniLM + BM25 via FastEmbed). Not for max throughput.

**Prefix caching is what makes index-time contextualization effectively free locally.** Every
chunk of a document shares the document's prefix — the canonical APC/RadixAttention case. **Two
caveats from the verification:**
- The throughput multipliers that circulate (SGLang 29% / 6.4×, vLLM APC 1.67×/3.58×) are
  **generic-benchmark ceilings that collapse on unique-prompt workloads** — treat as
  directional, **measure the realized speedup locally**.
- **Offline-batch prefix grouping matters** (vLLM #12080): the indexer **must emit each
  document's chunks contiguously, sorted by shared prefix**, or the cache-hit rate (and the win)
  shrinks substantially.

The "contextualize all 6 repos in well under an hour" estimate is **back-of-envelope** (it
divides by an *aggregate batched* throughput number from a single 403-blocked vendor benchmark)
— **time it on the actual hardware** before quoting a wall-clock.

## 4. Two-card topology (no-NVLink-aware)

```
Card A (96 GB)                         Card B (96 GB)
─────────────────────                  ──────────────────────────────────
Answer-gen / judge LLM                 Index-time contextualizer (SGLang)
  Qwen3-32B FP8 (~38 GB)               + GPU embedder (TEI/Infinity)
  or Llama-3.3-70B FP8 (~70 GB)          Qwen3-Embedding-4B (~8 GB)
  on vLLM (APC on, kv fp8)             + GPU reranker
                                         mxbai-v2 / Qwen3-Reranker (~1–9 GB)
                                       + SPLADE (TEI, <2 GB)  [prose A/B]
```

Index-time and answer-time are **different phases**, so during a bulk re-index Card A can host a
**second contextualizer replica**. Pin with `CUDA_VISIBLE_DEVICES=0` / `=1`, expose two ports,
point `index.py` (embedder + contextualizer) and the answer/judge steps at the right endpoints.
**Exception:** when running the 70B answer model at long context, its KV may need both cards —
then run embedding/reranking on CPU or in a separate phase.

## 5. Quantization

- **FP8 is the default sweet spot** on Blackwell (native, near-lossless, ~1 byte/param). Use
  `--kv-cache-dtype fp8` to roughly halve KV memory.
- **AWQ/GPTQ INT4** for the largest models (70B) or to free KV headroom.
- **NVFP4 (FP4):** ~2× throughput on Blackwell, but **accuracy-neutrality is unverified for
  retrieval** (the vendor's "no measurable loss" was English MCQ only). Use FP4 for the
  high-throughput **contextualization** pass; **validate before FP4 for the answer model or the
  scorers** (quantizing embedder/reranker is riskier for retrieval quality than quantizing the
  generator). Prefer **FP8 over FP4 for precise-code answer-gen.**

## 6. Local dependencies to install in advance

**Already in the skill (`setting-up-rag` SETUP.md) — keep as the CPU-portable default:**
- Python venv + `qdrant-client[fastembed]`; Qdrant (Docker server or embedded on-disk).

**GPU campaign additions (this workstation):**
- **NVIDIA driver + CUDA 12.x/13.x** for Blackwell (SM 12.0); confirm FP4 kernel support.
- **vLLM** (source/nightly build with `torch_cuda_arch_list=12.0` for the Workstation Edition) —
  answer-gen + judge endpoints.
- **SGLang** — prefix-heavy contextualization (RadixAttention, deterministic serving).
- **Text-Embeddings-Inference (TEI)** and/or **Infinity** — GPU embedder + reranker (+ SPLADE).
- **Models (HuggingFace pulls):** Qwen3-Embedding-{0.6B,4B,8B}, Qwen3-Reranker-4B,
  mxbai-rerank-v2, `Splade_PP_en_v1`, Qwen3-32B (FP8), Llama-3.3-70B (FP8), Gemma-3-27B,
  Qwen3-30B-A3B or Gemma-3-12B (contextualizer), Lynx-8B/70B, HHEM-2.1-Open. (`pplx-embed-context-v1`
  if testing the LLM-free contextual arm.)
- **Chunking/eval libs:** `tree-sitter` + grammars (C++/CUDA/TS/Python/shell) **or** Chonkie
  (`chonkie[code]`) for AST chunking; `ragas` (point its LLM/embeddings at the local endpoints);
  optionally the Patronus/Lynx + HHEM packages.
- **Disk:** budget for FP8 70B (~70 GB) + embedder + reranker weights + the Qdrant index
  (a 4096-d 8B embedder is ~10.7× the 384-d baseline — enable int8 quantization).

## 7. The local-LLM decision, stated for the plan

| Need a local LLM? | For what | Size | Engine |
| --- | --- | --- | --- |
| **Yes** | index-time contextualization (Anthropic CR) | 12–30B | SGLang (prefix cache) |
| **Yes** | answer generation | 32–70B | vLLM (APC) |
| **Yes (advisory)** | faithfulness judge | 8–70B + HHEM CPU | vLLM (guided_json) |
| Optional | Doc2Query / decomposition / HippoRAG triples | 7–70B | vLLM |
| **No** | dense/sparse/rerank retrieval | n/a (served models) | TEI / Infinity |
| **No** | router / self-query / CRAG evaluator | 22M–770M / rules | CPU |

**Bottom line for the owner:** stand up vLLM + SGLang + TEI/Infinity on the two cards, pull the
shopping-list models, and the entire Phase-3 optimization loop — contextualize, index, generate,
judge — runs **locally at zero API cost**. The published `setting-up-rag` default stays
CPU-portable (bge-small + MiniLM + BM25 via FastEmbed); the GPU stack is the **opt-in campaign
upgrade** with a documented CPU fallback.

## Sources

- RTX PRO 6000 Blackwell: [NVIDIA product page](https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000/), [StorageReview](https://www.storagereview.com/)
- vLLM: [Automatic Prefix Caching](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching.html), [structured outputs](https://docs.vllm.ai/en/latest/features/structured_outputs.html); offline prefix grouping [vLLM #12080](https://github.com/vllm-project/vllm/issues/12080)
- SGLang RadixAttention: [LMSYS blog](https://lmsys.org/blog/2024-01-17-sglang/); deterministic serving (batch-invariant, Sept 2025)
- TEI: [github](https://github.com/huggingface/text-embeddings-inference); Infinity: [github](https://github.com/michaelfeil/infinity)
- Qwen3-Reranker on vLLM caveats: [vLLM #20532](https://github.com/vllm-project/vllm/issues/20532)
- Models: [Qwen3](https://qwenlm.github.io/blog/qwen3/), [Gemma 3](https://huggingface.co/google), [Llama 3.3](https://huggingface.co/meta-llama), [Patronus Lynx](https://arxiv.org/abs/2407.08488), [HHEM-2.1-Open](https://huggingface.co/vectara/hallucination_evaluation_model)
