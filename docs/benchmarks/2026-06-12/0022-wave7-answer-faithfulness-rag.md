# Wave 7 - Answer Faithfulness on the Qwen Caveat Slice

- **Date:** 2026-06-12
- **Wave:** 7, answer generation and faithfulness
- **Plan:** [`0008` consolidated RAG optimization Phase 2](../../plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md)
- **Harness:** `docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/harness/wave7_answer.py`
- **Artifacts:** [`0022-wave7-caveat-metrics.tsv`](0022-wave7-caveat-metrics.tsv), [`0022-wave7-caveat-summary.json`](0022-wave7-caveat-summary.json), [`0022-wave7-caveat-answers.jsonl`](0022-wave7-caveat-answers.jsonl), [`0022-wave7-caveat-extractive-metrics.tsv`](0022-wave7-caveat-extractive-metrics.tsv), [`0022-wave7-caveat-extractive-summary.json`](0022-wave7-caveat-extractive-summary.json), [`0022-wave7-caveat-extractive-answers.jsonl`](0022-wave7-caveat-extractive-answers.jsonl)
- **Generator:** `NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4`, TensorRT-LLM Docker `nvcr.io/nvidia/tensorrt-llm/release:1.3.0rc12`, TP=2 across both RTX PRO 6000 Blackwell GPUs, OpenAI-compatible endpoint `http://127.0.0.1:8085/v1`, `enable_thinking=false`.
- **Retriever:** Wave-6 campaign best, `w6-rrk-qwen4b` (`w4-ctx-llm-gemma4-all` contextual index plus instruction-templated `Qwen3-Reranker-4B`).

## Scope

This run targets the open Wave-6 caveats, not the whole 207-query gold set:

- `alpha-zero`, where Qwen reranking slightly regressed pMRR while improving pack coverage.
- `category=session-prompting`, where ranking regressed slightly while hit@5 improved.
- hard `nl` questions, because they are the answer-stage stress case.

That produces **38 held-out queries** and **152 answer generations** per prompt style: four context packs for each query.

The retrieved pack is saved first, then generation runs over those fixed packs. The answer generator never sees gold answers or sentinels. Sentinels are used only after generation as a deterministic answer-quality proxy.

## Arms

All arms use the same retrieved top-20 chunks and differ only in how those chunks are packed for the reader:

| arm           | context order                | token budget                  |
| ------------- | ---------------------------- | ----------------------------- |
| `score-raw20` | reranker score order         | raw top 20, about 7.6k tokens |
| `score-4k`    | reranker score order         | about 4k tokens               |
| `parent-4k`   | parent/section grouped order | about 4k tokens               |
| `source-4k`   | source path and line order   | about 4k tokens               |

Two answer prompts were tested:

- `citation`: concise answer, every factual sentence cited.
- `extractive`: same, plus instruction to copy exact source identifiers, constants, numbers, file names, quoted strings, commands, and error text instead of paraphrasing.

## Results

### Citation Prompt

| arm           | nDCG  | pMRR  | pack sentCov | answer sentinel | citation support | abstain | context tokens | gen ms |
| ------------- | ----- | ----- | ------------ | --------------- | ---------------- | ------- | -------------- | ------ |
| `parent-4k`   | 0.818 | 0.757 | 0.978        | 0.478           | **0.730**        | 0.000   | 3,923          | 4,784  |
| `score-4k`    | 0.818 | 0.757 | 0.978        | 0.513           | 0.680            | 0.000   | 3,930          | 5,143  |
| `score-raw20` | 0.818 | 0.757 | 0.978        | **0.531**       | 0.649            | 0.000   | 7,562          | 5,320  |
| `source-4k`   | 0.818 | 0.757 | 0.978        | 0.439           | 0.638            | 0.053   | 3,925          | 4,820  |

### Extractive Prompt Delta

| pack          | answer sentinel, citation | answer sentinel, extractive | delta      | citation support, citation | citation support, extractive | delta  |
| ------------- | ------------------------- | --------------------------- | ---------- | -------------------------- | ---------------------------- | ------ |
| `parent-4k`   | 0.478                     | **0.517**                   | **+0.039** | **0.730**                  | 0.716                        | -0.014 |
| `score-4k`    | 0.513                     | 0.522                       | +0.009     | 0.680                      | 0.672                        | -0.007 |
| `score-raw20` | **0.531**                 | 0.500                       | -0.031     | 0.649                      | 0.645                        | -0.004 |
| `source-4k`   | 0.439                     | 0.447                       | +0.009     | 0.638                      | 0.610                        | -0.029 |

The extractive prompt is not a universal win. It is a narrow keeper for `parent-4k`: answer sentinel containment rises by +0.039 with only -0.014 citation-support loss, while keeping the 4k context budget.

### Caveat Slices

For `session-prompting`, the `parent-4k + extractive` combination is the cleanest answer-stage fix:

| arm                    | answer sentinel | citation support |
| ---------------------- | --------------- | ---------------- |
| `parent-4k` citation   | 0.544           | 0.640            |
| `parent-4k` extractive | **0.596**       | **0.715**        |
| `score-4k` citation    | 0.588           | 0.570            |
| `score-4k` extractive  | **0.623**       | 0.602            |

For `alpha-zero`, answer-stage metrics show the pMRR caveat is not primarily a pack-coverage problem:

| arm                    | answer sentinel | citation support |
| ---------------------- | --------------- | ---------------- |
| `parent-4k` citation   | 0.431           | **0.838**        |
| `parent-4k` extractive | **0.461**       | 0.743            |
| `score-raw20` citation | **0.500**       | 0.784            |

Raw top-20 improves literal answer containment on alpha-zero, but costs about 1.9x context tokens and lowers citation support versus the best parent pack. This is a reader/generator tradeoff, not a reason to reopen retrieval routing.

## Decisions

- **Keep source-preserving answer packs in the harness.** The fixed-pack design cleanly separates retrieval, packing, generation, and verification. It also caught that pack coverage is high while answer literal containment is not.
- **Prefer `parent-4k + extractive` for citation-sensitive answer runs.** It is the best 4k Pareto point on this caveat slice: answer sentinel 0.517 and citation support 0.716.
- **Use `score-raw20` only when exact literal containment matters more than context cost.** It has the highest answer sentinel under the citation prompt (0.531) but uses 7,562 tokens and has weaker citation support.
- **Reject source-order packing as a default.** It is worst on answer sentinel and citation support and is the only arm that abstained on this slice.
- **Do not reopen query-time agentic retrieval for these caveats.** The retrieved pack already contains sentinel evidence (`sentCov` 0.978, hit@5 1.0). The remaining headroom is answer verification, citation discipline, and possible answer regeneration from the same pack.

## Skill Impact

The portable `setting-up-rag` retrieval default does not change from this Wave-7 run. The measured change belongs to the consumer side:

- `retrieving-context` should tell agents answering from RAG to preserve source IDs in the context, cite every factual sentence, and verify cited chunks mechanically.
- For larger answer contexts, use parent/section grouped packs before source-order packs.
- Escalate to raw top-20 only when literal extraction is more important than token budget.

## Reproduce

```bash
H=docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/harness
CFG=docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2/configs
RAG=~/.cache/rag-skill/venv/bin/python
CAMP=~/developer/third-party/python_venvs/rag_campaign_env/.venv/bin/python

# Qwen reranker on GPU 1, with the served name matching the Wave-6 config.
CUDA_VISIBLE_DEVICES=1 ~/developer/third-party/python_venvs/llm_env/.venv/bin/vllm serve \
  /mnt/nas/home/ml/model/reranker/qwen3-reranker-4b \
  --served-model-name qwen3-reranker-4b \
  --host 0.0.0.0 --port 8086 --runner pooling --trust-remote-code \
  --gpu-memory-utilization 0.30 \
  --hf_overrides '{"architectures":["Qwen3ForSequenceClassification"],"classifier_from_token":["no","yes"],"is_original_qwen3_reranker":true}'

$RAG $H/wave7_answer.py pack --split held-out --caveat-slice \
  --tag 0022-wave7-caveat --out /tmp/0022-wave7-caveat-packs.jsonl \
  --arm wave6/w6-rrk-qwen4b \
  --pack score:raw --pack score:4000 --pack source:4000 --pack parent:4000

# Stop Qwen, then start Nemotron TP=2 on both GPUs.
cat >/tmp/trtllm-wave7.yaml <<'YAML'
kv_cache_config:
  dtype: fp8
  free_gpu_memory_fraction: 0.8
  enable_block_reuse: false
  mamba_ssm_cache_dtype: float16
moe_config:
  backend: CUTLASS
cuda_graph_config:
  enable_padding: true
  max_batch_size: 64
YAML

docker run -d --name trtllm-nemotron --gpus all --ipc=host --shm-size=16g \
  -v /mnt/nas/home/ml/model/llm/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4:/model:ro \
  -v /tmp/trtllm-wave7.yaml:/config.yaml:ro -p 8085:8000 \
  nvcr.io/nvidia/tensorrt-llm/release:1.3.0rc12 trtllm-serve serve /model \
  --backend pytorch --tp_size 2 --trust_remote_code \
  --extra_llm_api_options /config.yaml --max_batch_size 64 \
  --max_num_tokens 16384 --host 0.0.0.0 --port 8000

$CAMP $H/wave7_answer.py generate \
  --packs /tmp/0022-wave7-caveat-packs.jsonl \
  --answers docs/benchmarks/2026-06-12/0022-wave7-caveat-answers.jsonl \
  --metrics docs/benchmarks/2026-06-12/0022-wave7-caveat-metrics.tsv \
  --summary docs/benchmarks/2026-06-12/0022-wave7-caveat-summary.json \
  --tag 0022-wave7-caveat --split held-out --model model \
  --base-url http://127.0.0.1:8085/v1 --no-think --workers 8 --max-tokens 512

$CAMP $H/wave7_answer.py generate --prompt-style extractive \
  --packs /tmp/0022-wave7-caveat-packs.jsonl \
  --answers docs/benchmarks/2026-06-12/0022-wave7-caveat-extractive-answers.jsonl \
  --metrics docs/benchmarks/2026-06-12/0022-wave7-caveat-extractive-metrics.tsv \
  --summary docs/benchmarks/2026-06-12/0022-wave7-caveat-extractive-summary.json \
  --tag 0022-wave7-caveat-extractive --split held-out --model model \
  --base-url http://127.0.0.1:8085/v1 --no-think --workers 8 --max-tokens 512
```
