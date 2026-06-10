# Wave 4 — contextual-retrieval generator-model comparison

- **Date:** 2026-06-10
- **Wave:** 4, step 1b — does the **choice of context-generation LLM** matter?
- **Plan:** [`0008`](../../plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md) §"Wave 4"; builds on [`0014`](0014-wave4-contextual-gemma4-rag.md)
- **Generators:** `gemma-4` (Gemma-4-31B-IT NVFP4, vLLM) · `Qwen3.6-27B-UD-Q8_K_XL` (llama.cpp GGUF) · `NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4` (TensorRT-LLM, Docker)
- **Artifacts:** `0015-wave4-model-comparison-{metrics.tsv,summary.json}` (gemma + Nemotron full corpus; Qwen full-corpus row diluted — see below), `0015-qwen-spotcheck-*` (clean Qwen on 2 repos)
- **Disposition:** **generator capability DOES scale the code-domain lift** — Nemotron-120B ≈ 2× the 31B/27B models on code. gemma-4 stays the campaign **default** (fast, balanced); Nemotron is the **quality ceiling** for code-heavy corpora that justify the heavier serving.

## Question

`0014` proved gemma-4 contextual retrieval works (held-out code nDCG +0.045). Does a
larger / different generator change the lift? Three generators, **same prompt, same
chunks, same embedder (bge-small), same arms**, matched **12k-char document window**.

**Window control — 12k ≈ 48k (a wash), so the matched-window comparison is fair:**

| gemma-4 window | nDCG@10 | pMRR | sentCov | hit@5 |
| --- | --- | --- | --- | --- |
| 48k (`0014`) | 0.721 | 0.655 | 0.919 | 0.865 |
| 12k | 0.720 | 0.658 | 0.909 | 0.855 |

## Result 1 — full-corpus held-out (gemma-4 vs Nemotron-120B)

Both generators have **full chunk coverage** on all 6 repos, so these held-out numbers
are clean (n=111; Qwen excluded here — only 2 repos covered, see Result 2):

| generator (held-out) | nDCG@10 | pMRR | sentCov | hit@5 |
| --- | --- | --- | --- | --- |
| `w2-ctx-header` (no LLM) | 0.733 | 0.669 | 0.833 | 0.793 |
| gemma-4 (31B) | 0.761 (+0.028) | 0.700 (+0.031) | 0.901 (+0.068) | 0.847 (+0.054) |
| **Nemotron-120B-A12B** | **0.792 (+0.059)** | **0.728 (+0.059)** | **0.934 (+0.101)** | **0.874 (+0.081)** |

**Code domain (n=73) — where the generator gap is largest:**

| generator | nDCG@10 | pMRR | sentCov | hit@5 |
| --- | --- | --- | --- | --- |
| `w2-ctx-header` | 0.679 | 0.607 | 0.751 | 0.712 |
| gemma-4 | 0.715 (+0.037) | 0.647 (+0.040) | 0.856 (+0.105) | 0.795 (+0.082) |
| **Nemotron-120B** | **0.768 (+0.089)** | **0.696 (+0.089)** | **0.909 (+0.158)** | **0.822 (+0.110)** |

Nemotron (120B) roughly **doubles** gemma-4's (31B) code lift (nDCG +0.089 vs +0.037,
sentinel +0.158 vs +0.105). The bigger model writes more precise situating context for
identifier-dense code. **NL is at ceiling for all** (nDCG ≈ 0.84, flat).

**Regression scan (held-out):** the two generators trade *different* slices —

- **Nemotron: no code regression**, but **regresses some NL** (coding-agent-skills nl
  −0.046, website nl −0.043 nDCG): its verbose ~340-char contexts dilute the already-strong
  prose signal. (gemma's contexts average ~210 chars.)
- **gemma: regresses some code** (az-game-xiang-qi code −0.051, alpha-zero code −0.014) —
  its lighter context helps code less, and the Chinese xiang-qi slice least of all.
- `easy`×`nl` shows large deltas for both (e.g. −0.217) but those cells are ~6 ceiling-bound
  questions (noise), not in the domain aggregates.

## Result 2 — Qwen3.6-27B (spot-check, 2 repos) and the convergence effect

Qwen GGUF throughput (~0.3 chunk/s) made a full-corpus run impractical, so Qwen was
contextualized only on `alpha-zero-api` + `az-game-tic-tac-toe` (n=54, full coverage).
On **these two small repos all three generators converge** (`0015-qwen-spotcheck` +
the api+ttt slice of the 4-way TSV):

| generator (api+ttt, n=54) | nDCG@10 | pMRR | sentCov | hit@5 |
| --- | --- | --- | --- | --- |
| `w2-ctx-header` | 0.666 | 0.584 | 0.914 | 0.852 |
| gemma-4 | 0.744 (+0.079) | 0.672 (+0.088) | 0.948 | 0.907 |
| Qwen3.6-27B | 0.761 (+0.096) | 0.692 (+0.108) | 0.957 | 0.926 |
| Nemotron-120B | 0.742 (+0.076) | 0.672 (+0.088) | 0.960 | 0.926 |

The takeaway is the **contrast with Result 1**: on small/easy repos generator size barely
matters (all ≈ +0.08, Qwen nominally best); Nemotron's advantage only materializes on the
**full, harder corpus** (coding-agent-skills, alpha-zero, website). So "any decent model
works" is true for easy corpora but **understates the ceiling** a larger generator reaches
on a demanding one.

## Serving findings — throughput spans ~25×

The index-time generation pass (~9k chunks) is where the generators differ most in cost:

| generator | engine / quant | GPUs | throughput | notes |
| --- | --- | --- | --- | --- |
| gemma-4-31B | **vLLM**, NVFP4 + fp8 KV | 1 | **~8 chunk/s** | automatic prefix caching across a doc's chunks; the workhorse |
| Qwen3.6-27B | **llama.cpp**, GGUF Q8_K_XL | 1 | **~0.3–0.8 chunk/s** | ~5 s/req fixed overhead, no cross-slot prefix reuse |
| Nemotron-120B-A12B | **TensorRT-LLM** (Docker), NVFP4 + fp8 KV | 2 (TP) | **~2.6–3.4 chunk/s** | 82 tok/s decode; hybrid Mamba-MoE; ~36 GB/rank |

Hard-won serving lessons:

- **vLLM/TRT-LLM NVFP4 ≫ llama.cpp GGUF-Q8 for a bulk pass.** llama.cpp re-prefills the
  shared document per chunk; forcing reuse with `--slot-prompt-similarity`/`--kv-unified`
  triggered 6 s KV-checkpoint thrashing (`--cache-idle-slots`) and made it *slower*. Bound
  the document window instead.
- **Reasoning models must have thinking disabled** (`chat_template_kwargs={"enable_thinking":
  false}` via OpenAI `extra_body`) or the budget is spent on a stripped `<think>` block.
  Qwen3.6 and Nemotron both require this; Nemotron's default mode leaks reasoning into content.
- **Nemotron via TensorRT-LLM needed Docker.** Native `trtllm-serve` (pip `tensorrt_llm`
  1.2.1; CUDA-13.1 box matched NVIDIA's wheel exactly, installed from `--extra-index-url
  https://pypi.nvidia.com --index-strategy unsafe-best-match`; `libopenmpi-dev` for TP) **hung
  at the MpiPoolSession/IPC bootstrap** every way (TP=2, TP=1, `trtllm-llmapi-launch`) — the
  worker spun before loading weights. The official container fixed it:
  `docker run -d --gpus all --ipc=host --shm-size=16g -v <ckpt>:/model:ro -v <yaml>:/config.yaml
  -p 8085:8000 nvcr.io/nvidia/tensorrt-llm/release:1.3.0rc12 trtllm-serve serve /model
  --backend pytorch --tp_size 2 --trust_remote_code --extra_llm_api_options /config.yaml
  --host 0.0.0.0 --port 8000` (yaml: `kv_cache_config.dtype=fp8`, `mamba_ssm_cache_dtype=float16`,
  `moe_config.backend=CUTLASS`). `--ipc=host` is the key — it gives the IPC executor the shared
  memory the native launch lacked. (Some sm120 CUTLASS MoE autotuner tactics fail and fall
  back — benign.)

## Decision

- **Generator capability matters on a demanding corpus.** Nemotron-120B is the **quality
  ceiling** (code nDCG +0.089, ~2× the 31B/27B models), with no code regression — best where
  the corpus is code-heavy and the extra retrieval quality is worth a heavier, slower,
  two-GPU Docker serving path.
- **gemma-4 stays the campaign default generator** — it captures the bulk of the lift
  (code nDCG +0.037, sentinel +0.105) at ~3× Nemotron's throughput on one GPU via the
  already-running vLLM endpoint, and it does **not** regress NL the way Nemotron's verbose
  contexts do.
- **Qwen3.6-27B ≈ gemma-4** in quality (similar size) but is impractical to serve for a bulk
  pass via llama.cpp GGUF — not recommended as the generator.
- The technique (`0014`) and the portable CPU default are unchanged; this only informs the
  **campaign generator choice**.

## Reproduce

```bash
H=docs/plans/2026-06-08/0008-…/harness ; CAMP=…/rag_campaign_env/.venv/bin/python
# contexts per generator endpoint at the matched 12k window (e.g. Nemotron via Docker :8085)
$CAMP $H/wave4_context.py generate --repo all --model model --cache-model nemotron-w12k \
  --base-url http://127.0.0.1:8085/v1 --no-think --max-doc-chars 12000 --workers 16
# 4-way score (configs/wave4/w4-ctx-llm-{gemma4-w12k,nemotron-w12k,qwen}-all.json)
~/.cache/rag-skill/venv/bin/python $H/run_benchmark.py --split all \
  --tag 0015-wave4-model-comparison --out-dir docs/benchmarks/2026-06-10 --config …
python3 $H/wave4_analyze.py docs/benchmarks/2026-06-10/0015-wave4-model-comparison-metrics.tsv \
  --baseline w2-ctx-header --splits held-out   # held-out × domain + regression scan
```
