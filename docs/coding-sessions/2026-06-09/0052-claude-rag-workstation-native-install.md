<!-- markdownlint-disable MD013 MD024 -->

# Native RAG software install on the Ubuntu workstation (Waves 0–3)

- **Date:** 2026-06-09
- **Repo:** `coding-agent-skills` (isolated jj workspace `claude-pending-94508a16`)
- **Author:** Shuyang Sun <shuyangsun10@gmail.com>
- **Agent:** Claude Code (Opus 4.8, 1M context, thinking: high)
- **Summary:** Installed all software the consolidated RAG-optimization plan (`0008`) needs for Waves 0–3 natively (no Docker) on the Ubuntu GPU workstation `delos` — three uv/CPython-3.12 venvs (portable skill stack, campaign harness tooling, Infinity GPU embed/rerank serving), verified each, recorded the install state in plan `0008` and in memory, and filed a `docs/issues/` note about the `vcs` PreToolUse friction. Then exported this transcript and integrated/committed via the `vcs` skill.

## User

You are running on the Ubuntu workstation PC with local LiteLLM host and powerful GPUs. Read @docs/prompts/2026-06-08/0005-optimizing-rag-setup.md and @docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md, install the latest version of other software needed like qdrant (already exists, actually) locally, instead of running them in Docker containers to maximize performance. Once you install all required software for all waves, update the plan doc on what was installed where needed, but specify this is only for the Ubuntu workstation PC. Keep the doc update concise.

## Assistant

Read the prompt (`0005`) and the consolidated plan (`0008`), then surveyed the host before installing anything.

- **OS / GPU:** Ubuntu (`delos`), 2× RTX PRO 6000 Blackwell (~96 GB each), driver 590.44.01, CUDA 13.1, `nvcc` present. GPU0 (PCI bus `21:00`) saturated (~92 GB) by a `VLLM::EngineCore` (the live `gemma-4` server); GPU1 (bus `4B:00`) had ~94 GB free.
- **Binaries present:** `docker`, `bun`, `rg`, `uv`, `cargo`, `nvcc`. **Missing:** `qdrant` on PATH, `ctags`, `vllm`/`tei`/`infinity_emb` on PATH.
- **Qdrant:** a native root-owned `./qdrant` (pid 6586) plus a Docker `face-embed-qdrant` (v1.17.1, a different project) — `localhost:6333` answers `healthz` with v1.17.1. This is the "already exists" Qdrant.
- **Serving stack:** nginx (`:443`/`:80`), vLLM (`:8083`), LiteLLM proxy (`:8080`) — all from `~/developer/third-party/python_venvs/llm_env/.venv` (CPython 3.12.13, vLLM 0.20.0 + LiteLLM 1.83.14 + torch 2.11.0).
- **Python:** system `python3` is pyenv **3.14.2** — too new for ML wheels; uv has a managed **3.12.13**.
- **sudo:** needs a password (so no `apt install`).
- **Disk:** ~550 GB free on `/`; NAS mounted.

(Tool calls: `uname`/`nvidia-smi`, `command -v` sweep, `pgrep`/`docker ps`/`curl :6333`, `ss -tlnp`, reading `setup-local-rag.sh`, inspecting the `llm_env` venv, `df`, `uv python list`, `sudo -n`.)

## User

[Interrupt] Actually, spin up a small subagent to document your issues with Error: PreToolUse first under @docs/issues/, then continue with what you were doing before while the subagent runs in parallel.

## Assistant

Launched a background subagent to document the `vcs` PreToolUse friction (the harness resets the shell cwd to the shared workspace between every Bash call, and `vcs-check.sh`'s read-only allowlist doesn't include diagnostic commands like `pgrep`/`curl`/`ss`/`nvidia-smi`, so every such call must be re-prefixed with `cd <workspace> &&`). It wrote `docs/issues/2026-06-09/0009-vcs-hook-refuses-read-only-bash-after-claude-cwd-reset.md`, cross-linked it to the related `0008`, and added a dated entry to `docs/issues/OVERVIEW.md`.

In parallel, continued the install work. Decisions:

- Leave the live `llm_env` untouched; reuse its `gemma-4` endpoint for Wave-4+ generation.
- Create three dedicated **uv / CPython 3.12.13** venvs (system 3.14 is too new for the wheels).
- Use the native Qdrant on `:6333` as-is (the skill's `setup-local-rag.sh` Docker path is skipped because `healthz` answers).

**1. Portable skill stack** — `~/.cache/rag-skill/venv`: `uv pip install "qdrant-client[fastembed]"` → qdrant-client 1.18.0 + fastembed 0.8.0. Ran `setup-local-rag.sh --warm` to download ONNX weights (bge-small, BM25/SPLADE, MiniLM). `check-local-rag.sh` → `STATUS=READY (server)`.

**2. Campaign harness venv** — `~/developer/third-party/python_venvs/rag_campaign_env/.venv`: `ranx` 0.3.21, `ir-measures` 0.4.3, `pytrec_eval`, `rapidfuzz` 3.14.5, `tree-sitter` + `tree-sitter-language-pack` 1.8.1, `networkx` 3.6.1, `scikit-learn` 1.9.0, `umap-learn` 0.5.12, `hdbscan` 0.8.44, `openai`, `ragas`, plus `qdrant-client[fastembed]`. `ragas` 0.3.1 failed to import (referenced `langchain_community.chat_models.vertexai`, removed in langchain v1.3); resolved by jointly pinning `ragas==0.2.15` with the langchain 0.3 family (`langchain==0.3.27`, `langchain-community==0.3.27`, `langchain-core==0.3.74`, `langchain-openai==0.2.14`; this pinned `openai` to 1.109.1, fine for the endpoint). Verified all imports + tree-sitter grammars for cpp/cuda/c/python/typescript/bash/markdown. SQLite FTS5 confirmed present in the stdlib.

**3. Wave-3 GPU embed/rerank serving** — `~/developer/third-party/python_venvs/infinity_env/.venv`: installed `torch==2.11.0+cu130` from the PyTorch cu130 index (arch list includes Blackwell `sm_120`), then `infinity-emb[all]` → 0.0.77. CLI import failed on `optimum.bettertransformer` (removed in optimum 2.x); pinned `optimum==1.23.3`. **Smoke tests on the free card** (`CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1`): loaded NAS-staged `bge-small-en-v1.5` → 384-d embeddings at ~1.6–5k emb/s; loaded `ms-marco-minilm-l6-v2` → rerank scored the relevant doc 0.464 vs 0.0 for the distractor. **TEI not installed** (no Blackwell `sm_120` prebuilt; torch-based Infinity is the native path).

**Reused as-is:** native Qdrant 1.17.1, NVIDIA 590/CUDA 13.1, `llm_env` vLLM/LiteLLM serving `gemma-4`, `bun`/`rg`/`uv`/`cargo`. **Deferred:** `universal-ctags` (needs sudo — user to run `sudo apt install -y universal-ctags`), SGLang (vLLM already covers generation), generative judges + `pplx-embed-context-v1` (HF pulls for Wave 4/7).

Updated plan `0008` with a concise workstation-only subsection **"Installed on the Ubuntu workstation PC (2026-06-09)"** under *Local Dependencies*, and updated the `workstation-rag-serving` memory with the three venv paths and the Infinity serving recipe.

## User

/usage

## User

Export session transcript, integrate using the /vcs skill, commit and push, then cleanup residual workspaces and bookmarks (including the session workspace on disk).

## Assistant

Ran the `export-coding-session` skill (this file, index `0052`), redaction-scanned it, then used the `vcs` skill to integrate the isolated workspace, commit, and push, and cleaned up the residual workspace and bookmarks.
