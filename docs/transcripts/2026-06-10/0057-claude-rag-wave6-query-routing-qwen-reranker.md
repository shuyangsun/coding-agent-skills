---
title: "Phase 3 RAG — Wave 6 (query routing rejects; faithfully-served Qwen3-Reranker-4B becomes the campaign best)"
date: 2026-06-10
repo: "coding-agent-skills (bookmark `main`; work changes `feat(rag): Phase 3 Wave 6 …` and `docs(rag): pin Wave-7 generator candidates …`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Fable 5, 1M context, effort: max)"
summary: >-
  Executed Wave 6 of the consolidated RAG optimization (plan `0008`): built the
  query-routing toolkit (router features, self-query soft filters, LLM/deterministic
  decomposition, HyDE/multi-query, a dev-fitted CRAG confidence gate, rerank guards) and
  measured **every adaptive mechanism to a REJECT** — while the wave's reranker A/B,
  prompted by the user mid-session, found that **`Qwen3-Reranker-4B` served faithfully
  (vLLM seq-cls conversion + mandatory instruction template) is the campaign's largest
  single-variable win** (held-out nDCG 0.848 (+0.090), pMRR 0.800, hit@5 0.991,
  replicated) and promoted it campaign-side. Recorded benchmark `0021`, updated plan
  `0008` (including pinning Wave-7 generators to locally-downloaded models), landed two
  commits on `main`, then exported this session.
---

<!-- markdownlint-disable MD013 MD024 -->

# Phase 3 RAG — Wave 6 (query routing rejects; faithfully-served Qwen3-Reranker-4B becomes the campaign best)

## User

Read @docs/prompts/2026-06-08/0005-optimizing-rag-setup.md and @docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md, start working on wave 6. If local LLM is needed, use Nemotron 120B since that's the best performing model, unless you think it should be done with a different model.

_(Session model set to Fable 5, effort max; session attached via `/remote-control wave-6`. The session-start hook created jj workspace `claude-pending-8543a69b`, later renamed `claude-rag-wave6`.)_

## Assistant

**Orientation.** Read the two attached docs plus my serving-memory notes, the harness (`run_benchmark.py`, `metrics.py`, `wave4_analyze.py`, `wave4_context.py`), the Wave-5 report `0020` (the latest query-time methodology: shared collections, twin-baseline jitter control, repeated-cells replication standard) and `0015` (Nemotron serving). Renamed the workspace to `claude-rag-wave6` and built a task list.

- **Environment validation:** `validate_prework.py` → GO. Qdrant `:6343` (phase3-qdrant container) up; gemma-4 vLLM live on GPU0 (direct `:8083`, no proxy key needed); GPU1 free; Nemotron checkpoint found at `…/model/llm/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4`.
- **Corpus drift:** 5 of 6 repos' `corpus_sig` unchanged; `coding-agent-skills` drifted (the Wave-5 docs landed after the last gemma-4 context refresh) → topped up the wave-4 situating-context cache via direct vLLM (254 new chunks, 0 empty) so the campaign arm could re-index cleanly.
- **Design mining (before building anything):** joined `0020`'s per-query rows (`w4llm-rrk` − base). The bge-m3 reranker helps weak first-pass queries (base pMRR 0.330) and hurts strong ones (0.689; **37/70 hurt queries had the primary at rank 1** before rerank demoted it). Query-TEXT features don't separate the populations at all; an **oracle gate** would be worth held-out **nDCG +0.057 / pMRR +0.075** while keeping coverage gains → the gate must run on retrieval-STATE confidence (the plan's CRAG step 5). Trigger-rate scan: self-query filters fire on ~17% of gold queries, multipart markers ~26%, naive domain inference useless (34% agreement) → gate LLM transforms on exact-identifier presence instead.
- **Implementation (all query-time; every arm shares its base collection):** new `harness/wave6_query.py` — router features, self-query lang/kind/path extraction, first-pass confidence features (`agree10`, head concentration, `d_top`, `d_gap`), LLM transform generation + on-disk cache (decomp / multiquery / hyde; mirrors `wave4_context.py`; the runner never calls the network), deterministic decomposition control. `run_benchmark.py` hooks: `query_transform` (per-subquery hybrid retrieval, lists fused by **weighted RRF — rank-based, never an additive boost**, the Wave-5 lesson; HyDE swaps only the dense vector, sparse keeps the original query), `selfquery` (filtered prefetch / path-subsequence arms rank-fused at w=0.5), `rerank.gate` + `rerank.guard`. `metrics.py`: new `route.*` TSV channel. 11 arm configs + a guard grid; `wave6_fit_gate.py` for the offline threshold search.
- **Serving:** Infinity (`bge-reranker-v2-m3`) up on GPU1 `:7997`. Launched Nemotron-120B via TRT-LLM Docker on GPU1 (TP=1): first attempt failed (`mamba_ssm_cache_dtype` must be **nested inside `kv_cache_config`** on image 1.3.0rc12), second loaded all 74 GB of weights then **OOM'd on a single 160 GiB Mamba-SSM-cache allocation** (default max_batch_size) — relaunched with `--max_batch_size 16`.
- **Dev sweep 1** (11 no-LLM arms × 96): self-query **regresses hit@5 −0.031**; deterministic decomposition marginal; `protect_top1` guard at margin 0.05 the best guard arm but margins non-monotonic (noise); always-rerank reference reproduced; `w6-rrk-log` captured per-query confidence features for the gate fit.

## User

I'm not sure if you can run Nemotron on only 1 GPU. I don't know what's running on GPU0, if you don't need it, kill it and use both GPUs to serve Nemotron.

## Assistant

Identified GPU0's occupant: the **gemma-4 vLLM server** (the LiteLLM endpoint's only model). Confirmed nothing left in the session needs it (the context cache was already topped up; benchmarks read the cache, not the endpoint), saved its exact relaunch command, killed it, and relaunched Nemotron with **TP=2 across both clean GPUs** (`--gpus all`, `--max_batch_size 64 --max_num_tokens 16384`) — the serving shape proven in `0015`, now with the cache-bound fix so the 160 GiB Mamba-cache allocation can't recur. Also noted the user was right to doubt TP=1: weights fit, the default-batch SSM cache didn't.

## User

Also, is infinity reranker the best reranker? Wasn't there a better reranker that won the benchmarks? Why are we not using that one?

## Assistant

**Answered the premise first:** Infinity is the serving _engine_; the model behind it, `bge-reranker-v2-m3`, is the best reranker _measured so far_ (`0013`: strictly beats shipped MiniLM, 4.5× faster; `0020`: measured as a coverage-vs-precision lever). The "better" ones — `qwen3-reranker-4b` (the plan's "SOTA pick") and `zerank-2` — were **staged on the NAS but never benchmarked**: Wave 3's "representation ≫ model swap" finding deprioritized the sweep, and they're decoder-based rerankers needing instruction-template plumbing the plain cross-encoder path lacks. Added a time-boxed task to serve it faithfully and A/B it. Then continued the wave:

- **Gate fit + dev confirm:** `wave6_fit_gate.py` over sweep-1 rows — oracle +0.083 nDCG/+0.107 pMRR at fire-rate 0.38; froze `w6-rrk-gate` (`d_top≤0.752 OR d_gap≤0.0215`, 38% fire — and a counter-intuitive direction: rerank helps when dense+sparse **agree**) and a coverage-lean variant. Live dev confirm: gate **+0.053 nDCG / +0.070 pMRR** vs same-draw base; fire rates match the simulation exactly (0.38/0.75); gate+guard redundant.
- **Nemotron transforms:** all 3 kinds × 207 queries generated in ~2.5 min (TP=2), cached. Samples: decompositions exact-term-preserving; multi-query rewrites near-identical to the originals; **HyDE invents a plausible identifier** (`source_transcript_id`) — the predicted dilution risk.
- **Dev sweep 2 (LLM arms):** HyDE-all best transform (+0.030/+0.034), decomp gated mild (+0.013/+0.017), decomp-all regresses hit@5 −0.031, multi-query flat at R@20 1.000 without one new sentinel chunk. Transform arms raise the contamination-exposure diagnostic (1.22 → 1.4–1.5 flagged synthesis paths in top-20).
- **Held-out finals + replicate (10 frozen arms × 207, two independent draws):** the gate is the only arm positive on every overall metric (nDCG +0.008, pMRR +0.007, sentinel **+0.033**, hit@5 **+0.036**) and **dominates always-bge-rerank everywhere** (which pays nDCG −0.045 for sentinel +0.015) — but the **repeated-cells test fails it**: 10 cells regress in BOTH draws (hard×nl pMRR −0.095/−0.095 identical, alpha-zero-code −0.109/−0.155) vs the twin's worst −0.033 — adverse selection (it routes to the reranker exactly where the reranker is worst). HyDE's dev win **did not replicate** (held-out −0.009, sentinel −0.027); decomposition flat; all REJECT.
- **The reranker A/B (the user's question pays off):** served `Qwen3-Reranker-4B` via vLLM (`--runner pooling`; `--task score` is gone in vLLM 0.20) with the official seq-cls `hf_overrides` and wired the **mandatory instruction template** into the harness rerank client (`rerank.template="qwen3"`). Score sanity: templated **0.9994 / 0.0092 / 0.0000** (relevant / near / off-topic) — **untemplated the same model's scores are inverted** (0.137 < 0.907), which is exactly why Wave 3 never measured it. Dev: **nDCG 0.828 (+0.166), pMRR 0.797 (+0.206), hit@5 0.979** — exceeding the oracle ceiling of gating bge. Held-out record + replicate: **nDCG 0.848 (+0.090), pMRR 0.800 (+0.107), sentinel 0.955 (+0.042), hit@5 0.991 (+0.144)**, replicated to the third decimal; every single-axis slice positive except two named caveats (alpha-zero pMRR −0.008/−0.067; `session-prompting` −0.012/−0.018 — both with _improved_ pack coverage). `protect_top1` guards on qwen cost −0.044 dev (most of its value IS overruling wrong fused top-1s) — rejected; the gate now only caps the win (latency knob).
- **Decisions:** all Wave-6 adaptive mechanisms REJECT; **`w6-rrk-qwen4b` always-on promoted as the campaign reranker** (Apache-2.0, GPU/vLLM → campaign, not portable; 555 ms/query); the `0020` lever framing retired; the agentic loop (step 6) closed by evidence into Wave 7. Synthesis: _adaptivity was compensating for a weak arbiter — serving fidelity beat a wave of clever routing._
- **Documentation + landing:** wrote `docs/benchmarks/2026-06-10/0021-wave6-query-routing-rag.md` (+ 5 TSVs, 9 summaries; pruned dev-only TSVs per the `0020` convention), updated plan `0008` in place (status, two progress-table rows, current-best campaign config, per-step Wave-6 dispositions, a Wave-6 synthesis, the embedder-revisit note), updated the serving memory (gemma-4 down + restart cmdline, Nemotron TP=2 recipe corrections, qwen serving recipe, transform-cache paths). Restored 38 files churned by a repo-wide prettier run so the commit stayed scoped. Committed `feat(rag): Phase 3 Wave 6 — adaptive routing rejects; faithfully-served Qwen3-Reranker-4B is the new campaign best` and published `main` via `integrate.sh`. Left **Nemotron TP=2 running** on `:8085` (smoke-tested end-to-end) per the user's instruction; Infinity on `:7997`; gemma-4 down with its restart command documented.

## User

Also change wave 7 models that need to be tested to be locally downloaded ones - Gemma-4-31B-IT-NVFP4, NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4, Qwen3.6-27B, Qwen3.6-35B-A3B-FP8, Qwen3-Coder-Next-UD-Q8_K_XL.

## Assistant

Created a fresh workspace (`claude-wave7-models` — the Wave-6 one was retired on integrate), and updated plan `0008` in two places: **Wave 7 step 7** now pins the generator candidate set to the five locally-downloaded models with their proven serving paths (gemma-4 = vLLM NVFP4 workhorse; Nemotron = TRT-LLM TP=2 ceiling; Qwen3.6-27B GGUF via llama.cpp, per-answer only; Qwen3.6-35B-A3B-FP8 = vLLM MoE latency candidate; Qwen3-Coder-Next GGUF = code-cohort candidate) and points at the `0015` matched-window comparison method; the **"Local Dependencies" model-pulls note** now reads "nothing generative left to pull" and records judge status (HHEM complete/Apache, MiniCheck NC, Lynx cancelled). Committed `docs(rag): pin Wave-7 generator candidates to locally-downloaded models` and published `main`.

## User

Export session transcript, commit and push, then clean up (/vcs).

## Assistant

Ran the `export-coding-session` skill: created workspace `claude-export-wave6-session`, got index `0057`, wrote this transcript, ran the redaction scan plus a manual pass, formatted/linted, committed, published `main` via `integrate.sh`, and cleaned up the retired session workspaces and agent-session markers.
