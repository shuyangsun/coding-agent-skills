# Setting up persistent local RAG

Use the $setting-up-rag skill to set up a _persistent_ local RAG for the following projects:

- ~/developer/website
- ~/developer/llm-presentation
- ~/developer/coding-agent-skills
- ~/developer/power-monitor
- ~/developer/alpha-zero/alpha-zero
- ~/developer/alpha-zero/alpha-zero-api
- ~/developer/alpha-zero/alpha-zero-game
- ~/developer/alpha-zero/az-game-tic-tac-toe
- ~/developer/alpha-zero/az-game-xiang-qi

## Phase 1:

Spin up powerful subagents (GPT 5.5 medium or high) to update docs using the $updating-docs skill. If the repository already have good docs coverage, then skip this phase and the subagent can just return.

Once agents are done with updating docs, detect whether `jj` or `git` should be used to commit and push the changes. Follow the commit guide in `.agents/skills/vcs/COMMITS.md` to commit and push the changes.

## Phase 2:

Use the $setting-up-rag skill to set up RAG, we want to persist the RAG system so that it can be used for future tasks. For image-to-text tasks, you can use the downloaded model at /mnt/nas/home/ml/model/llm/Gemma-4-31B-IT-NVFP4/, served by `vllm`; for pure text-based tasks, you should use /mnt/nas/home/ml/model/llm/Gemma-4-31B-IT-NVFP4/, served on both GPUs using Docker and TensorRT. You won't be able to host both models at the same time on this machine given the size of the Nemotron model, so be strategic about how you index files and generate embeddings with contexual retrieval (if needed). I recommend using the Gemma 4 model first for image tasks, then switch to the Nemotron model for text tasks, since that will be used later. Make sure the RAG is persisted.

This is a real RAG system, not one used for benchmarking, so it's okay if the golden eval set itself is also indexed.

## Phase 3:

Test the $retrieving-context skill with the local RAG system. Make sure persistency is working, and try to retrieve context from the RAG system by referencing the golden set in the $improving-context-retrieval-skills harness.

The $retrieving-context skill should be usable by other projects on the same machine, make sure it's portable.
