---
title: "RAG: document the live LiteLLM endpoint + stage embedding/reranker models on the NAS"
date: 2026-06-09
repo: "`coding-agent-skills` (jj workspace `claude-rag-models`, off `main`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Opus 4.8, 1M context, effort: max)"
summary: >-
  Documented how to call the already-live local LiteLLM endpoint in
  `0005-optimizing-rag-setup.md` (placeholder-keyed, no secret-manager reference),
  researched + HF-verified the current SOTA embedding/reranker models, downloaded a
  curated 22-model set (embedding + reranker only) to the Synology NAS, updated the doc
  with a portable-vs-campaign "models staged on the NAS" section, and reconciled the
  consolidated Phase-2 plan (`0008`) against the new live-endpoint/staged-model reality.
---

<!-- markdownlint-disable MD013 MD024 MD034 -->

# RAG: document the live LiteLLM endpoint + stage embedding/reranker models on the NAS

> Session was started with `/model` → Opus 4.8 (1M context), `/effort max`, and `/remote-control rag-setup`, which delivered the task prompt below.

## User

You are running on the Ubuntu local workstaion with two GPUs. GPU0 is already used to host local gemma-4 model, with LiteLLM as proxy. https://llm.shuyangsun.com:443 is the OpenAI endpoint (using custom DNS to route the address to local IP, works on any local macine), which requires a secret key from 1Password CLI (doesn't matter which one for now). Read @docs/prompts/2026-06-08/0005-optimizing-rag-setup.md, understand the context and what needs to be installed, then do the following:

1. Modify / add details above on how to call the LiteLLM endpoint, but do not expose the `op` CLI reference, use a placeholder value for now.
2. Read other dependencies like embedding models and reranker to understand what needs to be downloaded, then download them and store them in `/mnt/nas/home/ml/model/`. This is a storage mounted from my Synology NAS, so it's actually a remote path, you should have read write access to it. Beyond what is mentioned in the doc, do some research and find out about the latest most powerful alternative models, download them to `/tmp/` then move them under a sub-directory in `/mnt/nas/home/ml/model/` with an intuitive folder name. Only download models with reasonable size, I'll download different LLM models later, just download embedding and reranker models for now.

After you're done, update the doc on which models to use (ones that were downloaded and exists).

## Assistant

Gathered context and set up the work.

- Read `0005-optimizing-rag-setup.md` and the `setting-up-rag` SKILL. Initial environment probes were refused by the VCS guard because the shared jj default workspace already had a session-owned workspace, so I loaded the **vcs** skill and `cd`'d into the assigned workspace, renaming it `claude-rag-models`.
- **Environment findings:** two RTX PRO 6000 Blackwell GPUs (GPU0 ~92/98 GB used by the local model, GPU1 free); `/mnt/nas/home` is a **CIFS mount from the Synology NAS** (confirmed via `findmnt` — a different device than root, ~50 TB free, writable; the earlier `df /mnt/nas` was misleading because only `/mnt/nas/home` is the mount). Tools present: `python3` (pyenv), `hf`/`huggingface_hub`, `git-lfs`, `op` (but **not** signed in non-interactively).
- Read the consolidated plan `0008` + its harness README, and grepped the plan for model references (Qwen3-Embedding/Reranker, mxbai, SPLADE, bge-reranker).
- **Probed the endpoint:** `llm.shuyangsun.com` resolves to a local IP; `GET /v1/models` with a dummy key returned a real LiteLLM `401` ("Invalid proxy server token"), confirming a genuine proxy that requires a valid key.
- **Mapped the live serving topology** (process list + the proxy config, secrets masked): vLLM serves `Gemma-4-31B-IT-NVFP4` as model name **`gemma-4`** on `:8083` → **LiteLLM** proxy on `:8080` → **nginx** TLS front (TLS 1.3 / HTTP-2 / HTTP-3) for `llm.shuyangsun.com:443`, **IP-allowlisted to the private LAN subnet + localhost** (plus a Cloudflare tunnel). A Qdrant server is already running in Docker on `:6333`. The LiteLLM `model_list` currently exposes only `gemma-4` (two Qwen models commented out). [DB connection string and master key were visible in the config but are **not reproduced here** — redacted.]
- Created a task list and **researched current SOTA** embedding + reranker models (web search). The SEO results contained some likely-fabricated names ("Harrier-OSS", "Jina v5"), so I **verified every candidate repo ID against the live HuggingFace API** (existence, size, license) with a throwaway script — 26 repos checked, real sizes/licenses recorded. This cleanly separated **portable (Apache/MIT, CPU)** from **campaign (GPU, possibly non-commercial)** models and added dedicated **code embedders** (4 of 6 corpora are code-heavy).
- Wrote a **resumable background download driver** (`/tmp` stage → verify weights → `mv` to `/mnt/nas/home/ml/model/{embedding,reranker}/`, idempotent skip-if-present, summary TSV) and launched it; added a harness-tracked waiter to be notified on completion.
- **Edited `0005`:** added a "The live endpoint on this workstation" subsection — base URL `https://llm.shuyangsun.com/v1`, served model `gemma-4`, `curl` + OpenAI-SDK smoke tests, and auth via a **placeholder key sourced from a secret manager** (no `op`/`op://` reference, per the request).
- Posted a status: 5/22 models downloaded so far; the rest (larger campaign models) were still in flight.

## User

Are you still downloading things?

## Assistant

Checked the driver and summary TSV: still running, in the home stretch — 16/22 complete and on the rerankers (downloading `Qwen3-Reranker-4B`), ~20 GB to go. Flagged one issue: `snowflake-arctic-embed-l-v2.0`'s move to the NAS had failed partway (its `onnx/` files dropped under concurrent CIFS load — a transient SMB error), leaving it incomplete; I would re-copy it alone once the other downloads finished to avoid the contention that caused it.

## User

Are you still downloading? The network traffic dropped.

## Assistant

Confirmed downloads had **finished** (hence the traffic drop): the driver processed all 22 — 21 succeeded, plus the flagged `arctic` move failure. Then finalized:

- **Re-copied `arctic`** alone (fresh download → `rsync`). A 1-file count mismatch turned out to be a stale **CIFS readdir cache** (`cache=strict,actimeo=1`): `find`/`ls` omitted a just-written `README.md` that explicit `stat` could see. Verified completeness via **per-file `stat`** instead of `find` — all 22 files present, `model.safetensors` byte-identical. Lesson recorded.
- **Verified all 22 models** (weight + tokenizer + config present): 13 embedding (60 G) + 9 reranker (27 G) = **87 G**, no stray files.
- **Edited `0005`:** added a "Models staged on the NAS" section — two tables (embedding/reranker) with local dirs, sizes, licenses, and **portable (Apache/MIT, CPU) vs campaign (GPU)** roles, **NC** flags for non-commercial weights (`sfr-embedding-code-2b-r`, `zerank-2`), and per-role starting picks tied to the plan's hypotheses.
- **Formatted (prettier 3.8.3) + linted (markdownlint-cli2 0.22.1)** via `bunx` (no `node_modules` present); my file was clean — all reported lint errors were pre-existing in other docs.
- **Committed** in the isolated jj workspace (not pushed). Saved the workstation serving topology + NAS model layout + the CIFS readdir gotcha to agent memory for the ongoing campaign.

Curated set downloaded to `/mnt/nas/home/ml/model/`:

- **`embedding/` (13):** `bge-small/base-en-v1.5`, `splade-pp-en-v1`, `mxbai-embed-large-v1`, `bge-m3`, `multilingual-e5-large-instruct`, `snowflake-arctic-embed-l-v2.0`, `embeddinggemma-300m`, `qwen3-embedding-0.6b/4b/8b`, `bge-code-v1`, `sfr-embedding-code-2b-r`.
- **`reranker/` (9):** `ms-marco-minilm-l6-v2` (+`-onnx`), `bge-reranker-v2-m3`, `qwen3-reranker-0.6b/4b`, `mxbai-rerank-base/large-v2`, `zerank-1-small`, `zerank-2`.

## User

Is there anything in @docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md that needs to be updated given the new context?

## Assistant

Yes — four spots were stale against what's now live/staged. Edited `0008` **in place with dated notes** (matching the doc's existing `_(Revised 2026-06-09 …)_` convention), formatted, lint-clean:

1. **Local Dependencies → model pulls (L124):** embed/rerank pulls marked **already downloaded** to the NAS (links `0005`); only generative + judge LLMs remain; noted `gemma-4` already served.
2. **Local LLM/GPU Setup → LAN serving (L135):** added "Realized 2026-06-09" — proxy live at `https://llm.shuyangsun.com/v1` serving `gemma-4`, LAN-allowlisted; embed/rerank serving still Wave 3.
3. **Re-verify model versions (L136):** Gemma-4-31B-IT is now the deployed generative model; embed/rerank cards/licenses HF-verified; still re-pull generative/judge cards before pinning.
4. **Wave 3 goal (L216):** noted the Wave-3 models are staged, plus new options — code embedders (`bge-code-v1`, `SFR-Embedding-Code-2B_R`) and `zerank-1-small`/`zerank-2` instruction rerankers.

Left the roadmap/strategy untouched (these are factual status reconciliations). Re-described the workspace commit to cover both `0005` + `0008`. Flagged that the sibling `0008-…/README.md` has one parallel stale line that could get the same treatment if wanted.

## User

Export the session transcript, then use the /vcs skill to integrate, commit and push from main, then cleanup residual workspaces and bookmarks.

## Assistant

Ran the **export-coding-session** skill to write this transcript (sealed the docs work into its own commit first, then created this `docs/coding-sessions/2026-06-09/0051-…` file in a fresh change, redacting the DB connection string, proxy master key, and internal NAS host IP). Then used the **vcs** skill's `integrate.sh` to land both commits — `docs(rag): …` and `docs(coding-sessions): …` — onto `main`, pushed `main` to the remote, and cleaned up the landed `claude-rag-models` workspace and bookmark.
