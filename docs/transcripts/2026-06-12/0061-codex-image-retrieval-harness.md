---
title: "Codex Image Retrieval Harness"
date: 2026-06-12
repo: "coding-agent-skills (`codex-improve-image-retrieval-harness`)"
author: "Shuyang Sun"
agent: "GPT-5 (Codex CLI 0.139.0, reasoning effort: high)"
summary: >-
  Extended only the `improving-context-retrieval-skills` harness so it can model image
  files as retrievable context, added website image summaries and image-dependent eval
  facts, verified the eval/reporting path, then exported the session for VCS integration.
---

<!-- markdownlint-disable MD013 MD024 -->

# Codex Image Retrieval Harness

## User

Extend the $improving-context-retrieval-skills skill to suport retrieving image files. There are some image files under the [REDACTED_LOCAL_PATH]/website/ project. Spin up subagents to query documentation (markdown files) that reference the particular image file, so subagents have context. Then read both the context and the image file, to generate a summary of the image file, and **why is it in the project, and what it is for**. On top of that, extend the eval set to include a few questions and answers about the `website` project, which requires use knowledge about these images to answer. Make sure there is not contamination from this new set of eval Q&A. In the reporting metric slices, on top of the existing code vs. natural language retrieval, add a new slice for image retrieval. Note that the goal is not to blindly retrieve images from the RAG system, but let LLMs know that these images _can_ be used to answer questions about the project, so they can make a decision to use them or not.

Do NOT edit skills related to context retrieval, only modify the harness skill $improving-context-retrieval-skills.

## User

**AGENTS.md Instructions For [REPO_ROOT]**

`coding-agent-skills` is a repo of repo-agnostic skills for LLM coding agents. The active repo instructions said to keep canonical skill sources under `.agents/skills/`, keep skills portable for symlinked host projects, avoid hardcoded absolute paths, resolve helper scripts relative to the loaded skill directory, and use the repo's pinned Bun/Prettier/markdownlint workflow for Markdown formatting.

## Assistant

Loaded the `improving-context-retrieval-skills` harness skill and the `vcs` skill before making changes. Created an isolated jj workspace named `codex-improve-image-retrieval-harness`.

Read the harness documents and scripts, then inspected the existing gold-set and scoring architecture:

- `.agents/skills/improving-context-retrieval-skills/SKILL.md`
- `.agents/skills/improving-context-retrieval-skills/SCENARIOS.md`
- `.agents/skills/improving-context-retrieval-skills/METRICS.md`
- `.agents/skills/improving-context-retrieval-skills/MATRIX.md`
- `.agents/skills/improving-context-retrieval-skills/LOOP.md`
- `.agents/skills/improving-context-retrieval-skills/scripts/gold.py`
- `.agents/skills/improving-context-retrieval-skills/scripts/docs-eval.py`
- `.agents/skills/improving-context-retrieval-skills/scripts/check-retrieval.py`
- `.agents/skills/improving-context-retrieval-skills/scripts/mk-corpus.py`
- `.agents/skills/improving-context-retrieval-skills/scripts/scoreboard.py`

Spawned two subagents to query Markdown documentation in the website project for image references:

- One subagent researched the hero image family and related docs/session notes.
- One subagent researched the cookie picker, social preview, and static asset docs.

Visually inspected the referenced website image files and combined the image evidence with the documentation context. Added curated image summaries for these actual assets:

- `shuyang-website/public/hero.webp`
- `shuyang-website/public/hero_arm.webp`
- `shuyang-website/public/hero_arm_out.webp`
- `shuyang-website/public/hero_point.webp`
- `shuyang-website/public/hero_point_arm.webp`
- `shuyang-website/public/hero_cookie_selection.webp`
- `shuyang-website/public/cookie_plain.webp`
- `shuyang-website/public/cookie_chocolate.webp`
- `shuyang-website/public/cookie_none.webp`
- `shuyang-website/public/link-preview.webp`

Implemented the harness changes in the improving skill only:

- Added an `image` retrieval domain and `--corpus-kind image --domain image` usage to the skill docs.
- Documented that image eval facts live in curated summaries keyed to real image paths, while eval questions and answers are generated separately so they are not indexed into the corpus.
- Extended the matrix, loop, scenarios, and metric docs to cover the image slice alongside code and natural-language retrieval.
- Added `IMAGE_SUMMARIES` and ten image facts in `scripts/gold.py`, each anchored by retrieval sentinels and primary image paths.
- Added `--image-corpus` handling so validation/build can locate the website image corpus without hardcoding the local path.
- Extended `scripts/mk-corpus.py` to copy referenced image files into `corpora/image`.
- Extended `scripts/docs-eval.py` and `scripts/check-retrieval.py` so the image domain can be evaluated through the same deterministic BM25-plus-invariants path.
- Updated `scripts/scoreboard.py` to report an image retrieval slice on top of the existing code and natural-language slices, including image-only TSV output.

Did not edit the `updating-docs`, `setting-up-rag`, or `retrieving-context` skills.

Verification run:

- `python3 -m py_compile` for changed Python harness scripts: passed.
- `python3 .agents/skills/improving-context-retrieval-skills/scripts/gold.py validate --image-corpus [REDACTED_LOCAL_PATH]/website`: passed with `image 10 facts 10 docs`.
- `gold.py build` with the image corpus: passed.
- `mk-corpus.py --image-corpus [REDACTED_LOCAL_PATH]/website`: copied the expected image files into the temp harness corpus.
- `docs-eval.py` and `check-retrieval.py` against the image domain for `baseline-b` and `rag-r`: passed.
- `scoreboard.py` on combined natural-language plus image TSV input: printed the image slice.
- `scoreboard.py` on image-only TSV input: printed the image slice.
- `check-vcs-boundary.py`: passed.
- Targeted Prettier and markdownlint checks for the changed harness Markdown files: passed.
- Repo-wide `bun run format:check`: failed on pre-existing unrelated exported session docs; those files were not changed.

## User

$export-coding-session then integrate with $vcs

## Assistant

Loaded `export-coding-session` and `vcs`. Allocated export index `0061` for `docs/coding-sessions/2026-06-12/0061-codex-image-retrieval-harness.md`.

This transcript was written with local-only paths redacted. Next steps in the same turn were to run the export redaction scan, lint the transcript, and integrate the isolated jj workspace back through the VCS helper.
