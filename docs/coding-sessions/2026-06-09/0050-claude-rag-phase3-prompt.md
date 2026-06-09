<!-- markdownlint-disable MD013 MD024 -->

# Improve the Phase 3 RAG-optimization prompt

- **Date:** 2026-06-09
- **Repo:** coding-agent-skills (bookmark `claude-rag-phase3-prompt`)
- **Author:** Shuyang Sun <shuyangsun10@gmail.com>
- **Agent:** Claude Code (Opus 4.8, 1M context, thinking: high)
- **Summary:** Reviewed the 3-phase RAG-optimization prompt against the consolidated Phase-2 plan (`0008`) and the just-landed pre-work harness, recommended six targeted improvements to the Phase 3 prompt, then drafted and applied a full replacement Phase 3 section — anchoring it to `0008` + the harness, fixing the outdated cohort-split wording, naming the gates/controls, and adding local-LLM/GPU sequencing with the corrected LAN topology. Also patched `0008`'s GPU section for the separate-LAN-machine fact, then exported this transcript.

## User

In the @docs/prompts folder, the last one should be about a 3-phase RAG optimization prompt. Based on what was already done for Phase 2 and Phase 3 prep work in the last commit, what's your recommendation to improve the Phase 3 prompt? You can reference the new plan doc under @docs/plans/. Don't make the change, keep it concise, just show me.

## Assistant

Explored the relevant files (tool calls summarized):

- Listed `docs/prompts/2026-06-08/` → found `0005-optimizing-rag-setup.md`; listed `docs/plans/2026-06-08/` → found the consolidated `0008-consolidated-rag-optimization-phase-2.md` plus its `harness/` and `configs/` subdirs.
- Read the prompt (`0005-optimizing-rag-setup.md`), the consolidated plan (`0008-…-phase-2.md`), the harness `README.md`, and `harness/corpus_manifest.py`.

Diagnosis: the Phase 3 prompt predates `0008` and the pre-work harness, so it under-specifies the work and, in one place, contradicts a 2026-06-09 owner revision (the cohort-split wording). Gave six prioritized recommendations:

1. **Anchor Phase 3 to `0008` + the harness** as the source of truth and starting point (the prompt references neither).
2. **Fix the cohort-split sentence** (correctness) — `0008` was revised to index one combined code+docs corpus per repo with `domain` as a reporting slice only, never a corpus partition; the prompt's "tune each independently" risks re-introducing the rejected per-domain-corpus design. Also fix the taxonomy: `domain=code` vs `domain=nl`, not "codebase vs session transcript."
3. **Name the gates** (recall@20, nDCG@10, MRR, primary-file MRR; sentinel/citation support; no slice regression) instead of "reach SOTA."
4. **Require the contamination controls** (closed-book, wrong-context, per-query synthesis-doc check, eval-file exclusion) — without them `coding-agent-skills`'s numbers are inflated by self-reference.
5. **Make the deliverable explicit** — a portable CPU-clean `setting-up-rag` default plus an optional local-GPU campaign config — with keep/revert and portable-vs-campaign promotion discipline, and GPU/LLM sequencing.
6. (Minor) Add a corpus-reachability check / extension-gap warning (shipped `CODE_EXTS` drops C++/CUDA → code domain empty for 4/6 repos).

Closed by offering to draft the full replacement Phase 3 section.

## User

Yes, go ahead.

Also note when I need to setup the local LLM on my GPU and expose the LiteLLM endpoint to my machine (correction - they are not on the same machine, but they can communicate through LAN).

## Assistant

Drafted the full replacement Phase 3 section (shown inline): anchored to `0008` + the harness, an ordered "work in this order" list (confirm readiness → build Wave-0 runner + declare baseline → run the wave roadmap → report slices type-blind → honor contamination controls → record each experiment), an explicit portable-default-plus-campaign-config deliverable, and a new "Local LLM / GPU — when to set it up, and how to reach it over the LAN" subsection.

Incorporated the LAN correction: the GPU workstation (2× RTX PRO 6000 Blackwell, no NVLink) is a **separate machine** from the harness/Qdrant host, reachable over LAN. Sequencing: Waves 0–2 CPU-only; Wave 3 brings the GPU box online for embed/rerank serving (TEI/Infinity); Wave 4+ adds the generative LLM (vLLM). To expose it: bind servers to `0.0.0.0`, front them with a LiteLLM proxy on the GPU box (one OpenAI-compatible base URL, master key, LAN-only port), and point the harness at `http://<gpu-host>:<port>/v1` with a pre-run health check.

Recorded the LAN topology to memory (`rag-gpu-box-lan-remote.md`) and noted that `0008`'s GPU section still assumes co-location and should be corrected. Did **not** edit the prompt file yet (per the earlier "just show me"); offered to apply it and to patch `0008` in the same pass.

## User

Yes. After you do that, export session transcript, then integrate and push with the VCS skill.

## Assistant

Loaded the `vcs` skill; the session-start hook had already created an isolated jj workspace, renamed it to `claude-rag-phase3-prompt` via `rename-work.sh`. Applied both edits in the workspace:

- **`docs/prompts/2026-06-08/0005-optimizing-rag-setup.md`** — replaced the Phase 3 section (old lines 42–56) with the full rewrite plus the Local LLM / GPU LAN subsection.
- **`docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md`** — added a bullet to "Local LLM and GPU Setup" recording that the GPU workstation is a separate LAN machine: bind vLLM + TEI/Infinity to `0.0.0.0`, front with a LiteLLM proxy, harness hits `http://<gpu-host>:<port>/v1`; embed/rerank at Wave 3, generative LLM at Wave 4; campaign-side only.

Then loaded `export-coding-session` and wrote this transcript, and proceeded to integrate and push via the `vcs` skill's `integrate.sh`.
