---
name: setting-up-rag
description: Load when STANDING UP or TUNING a local retrieval (RAG) system over a
  document or code set — provision the stack, chunk, contextualize, embed, index,
  and configure hybrid search, Qwen3 reranking, answer packing, and vector-DB
  knobs. Local-first (Qdrant + FastEmbed + local LLM/reranker endpoints, no cloud).
  To merely RETRIEVE context for a task (not build the index), load
  `retrieving-context` instead; it queries this stack.
---

# Setting up RAG — strongest local retrieval over a doc set

**Stand up and tune** effective retrieval over a given corpus (prose/text docs,
transcripts, or source code) so a downstream agent can answer from it. The
default persistent profile is the strongest measured local stack: chunk →
generate a short Nemotron situating context per chunk → embed dense+sparse into
Qdrant → hybrid retrieve (RRF) → **Qwen3-Reranker-4B** rerank → top-k. Answer
tests use **parent-4k + extractive** packing. Defaults live in
[`scripts/rag-config.json`](scripts/rag-config.json); the helpers do the mechanics,
so spend tokens on the corpus-specific choices, not the boilerplate.

> **Building the index vs. using it.** This skill is the **operator** side —
> provision the stack, index a corpus, and tune the config. An agent that just
> needs to **retrieve context to answer a question or do a task** should load
> [`retrieving-context`](../retrieving-context/SKILL.md) instead: it routes to
> the best retrieval available and queries _this_ local stack (the `query.py`
> below) when it is running. Come here to build or improve what it queries.

This file assumes local RAG is **already running**. The first two lines below
handle the one case where it isn't — do not read the setup docs otherwise.

## 0. Make sure local RAG is up (one-time per host)

```sh
bash <skill-dir>/scripts/check-local-rag.sh   # prints READY or NOT_READY
```

If it prints **`NOT_READY`**, provision once with
`bash <skill-dir>/scripts/setup-local-rag.sh` (add `--warm` to pre-download
models). Only then open [SETUP.md](SETUP.md) — for Docker/Ollama/offline
specifics or troubleshooting. If it prints **`READY`**, skip all of that and go
to §1. (Qdrant runs as a server when one is up, else embedded on-disk with no
daemon; both use the same code path.)

## 1. Index the corpus

```sh
python3 <skill-dir>/scripts/index.py --corpus <dir> --kind md   # prose/text docs
python3 <skill-dir>/scripts/index.py --corpus <dir> --kind code # source code
```

Indexes into a hybrid collection (named `dense` + `sparse` vectors); point IDs are
time-ordered Snowflakes (`snowflake.py`). With the shipped config, `index.py`
calls the local OpenAI-compatible Nemotron endpoint at `http://127.0.0.1:8085/v1`
and caches generated contexts under `$RAG_HOME/context/`. The generated context is
embedded and used for reranking, while `raw_text` stays byte-verbatim for answer
citations. **Re-running replaces the prior chunks of changed and added docs** —
each doc's old points are dropped before re-insert, so no duplicates or orphans
accumulate. Pass `--recreate` after a chunking/embedding change or when docs were
**removed**; `--local` forces embedded mode. Use a distinct `--collection` per
corpus or content type. Chunking adapts to `--kind` (heading-aware for prose/text,
block-packed for code) — see [CHUNKING.md](CHUNKING.md).

Every successful index run also registers the corpus in
`$RAG_HOME/projects.json` (default `~/.cache/rag-skill/projects.json`) unless
`--no-register` is passed. Use `--project-name <name>` to give a repo a stable
portable handle, and omit `--collection` to get the default
`rag_<project>_<kind>` collection name. This manifest is local machine state, not
repo state; it lets any project that has this skill query a shared persistent
Qdrant index by project name or root path.

`--kind md` is the historical name for the prose/text corpus. It indexes common
document and transcript formats such as `.md`, `.mdx`, `.txt`, `.rst`, `.adoc`,
`.org`, `.tex`, `.vtt`, `.srt`, and extensionless project docs like `README` or
`LICENSE`. Fixed-name build/config files with text-looking names, especially
`CMakeLists.txt`, stay in `--kind code` with `Makefile` and `Dockerfile`.

The loader prunes nested VCS roots below the selected corpus root. A Jujutsu
workspace created inside a repo (`jj workspace add <name>`) or a Git worktree
inside the repo is not indexed as part of the parent corpus; pass that
workspace/worktree as `--corpus` directly if it is the corpus you want. This keeps
the behavior generic across repositories. A repo-specific `.gitignore` pattern
for predictable workspace directory names is a useful extra guard, but the indexer
does not rely on it.

## 2. Query

```sh
python3 <skill-dir>/scripts/query.py "a natural-language question" --top-k 20
python3 <skill-dir>/scripts/query.py "…" --project <name-or-path> --kind all
python3 <skill-dir>/scripts/query.py --list-projects
python3 <skill-dir>/scripts/query.py "…" --json        # JSONL for a consumer/eval
python3 <skill-dir>/scripts/query.py "…" --no-rerank   # skip the rerank stage
```

Each query runs dense and sparse retrieval, fuses them with RRF, then reranks the
top candidates with the configured Qwen3 `/rerank` endpoint at
`http://127.0.0.1:8086`. Use `--no-rerank` when that service is not running or
latency matters more than quality. The how-and-why is in [RETRIEVAL.md](RETRIEVAL.md).

### Optional: test answer generation with an OpenAI-compatible LLM

For manual tests and future GUI/backend experiments, `answer.py` can retrieve
chunks and ask a locally hosted or cloud LLM to synthesize a cited answer through
an OpenAI-compatible `/v1/chat/completions` endpoint. This is deliberately
separate from the default retrieval workflow; do not use it as the normal
`retrieving-context` consumer path.

```sh
export RAG_LLM_BASE_URL=http://127.0.0.1:8085/v1
export RAG_LLM_MODEL=model
python3 <skill-dir>/scripts/answer.py "…" --project <name-or-path> --kind all
python3 <skill-dir>/scripts/answer.py "…" --collection docs --model <model> --json
python3 <skill-dir>/scripts/answer.py "…" --project <name> --dry-run --show-context
```

`RAG_LLM_API_KEY` is optional for local servers and required only when the target
provider expects a bearer token. For cloud providers, set `RAG_LLM_BASE_URL` to
the provider's OpenAI-compatible API base URL and set `RAG_LLM_API_KEY` (or pass
`--api-key-env`). Local vLLM or TensorRT-LLM servers should be started separately
with the model path or served model name they expect.

## 3. The method (what makes retrieval good, in priority order)

1. **Contextualize at index time when the local LLM is available.** Nemotron writes
   1-2 situating sentences per chunk. That context sharpens identifier-dense code
   chunks before embedding/sparse indexing; raw chunks remain the citation payload.
2. **Hybrid beats either arm alone.** Dense (semantic, `bge-small`) catches
   paraphrase; sparse (lexical, `bm25`) catches exact identifiers, error codes,
   API names. Fuse rank lists with **RRF** (robust to incompatible score scales).
3. **Chunk on structure, with a size floor.** Split markdown on headings, but
   **merge tiny sections** up to `min_words` so a heading-dense doc doesn't
   explode into hundreds of one-line chunks (a real cost: ~2.5× fewer chunks at
   equal recall on this repo). Code chunks pack whole blocks. → [CHUNKING.md](CHUNKING.md)
4. **Rerank the shortlist with Qwen3.** Qwen3-Reranker-4B with its required
   instruction template was the largest measured retrieval win; without the
   template it anti-ranks. → [RETRIEVAL.md](RETRIEVAL.md)
5. **Pack answers as parent-4k + extractive** for cited answer generation. Keep
   source IDs, group nearby chunks, and ask the model to preserve exact literals.

### Image-backed project context

For questions about a project that uses images, **do not build an image-caption
index by itself**. Index the project context that answers the question — source
files, docs, session transcripts, asset manifests, generation specs, and tooling —
plus compact image-summary documents whose doc ids are the real image paths.
Treat code/docs/session files as the primary answer evidence and image paths as
supporting visual provenance unless the user explicitly asks to inspect the image.

Keep the contamination boundary clear: benchmark questions, expected answers,
sentinels, and scoring notes must not be indexed into the corpus being evaluated.
Image summaries should state visible facts, purpose in the project, source paths,
derived-asset relationships, and synchronization rules in plain words. If summary
generation needs a model, use a vision-capable local model for image inputs and a
strong text model for text-only contextualization; never send image-only work to a
text-only generator.

## 4. Tune and validate against YOUR corpus — don't trust defaults blindly

The defaults are a strong start, **not** a guarantee. A knob that helps one corpus
can hurt another. Before keeping any change: build a small held-out gold query set
and confirm the change **beats the baseline** on recall@k / nDCG / MRR. Method,
gold-set construction, and the keep/revert rule are in [TUNING.md](TUNING.md).

## 5. Config

All knobs are in [`scripts/rag-config.json`](scripts/rag-config.json) (models,
chunk sizes, fusion, prefetch, rerank, top-k) and documented inline. Pass an
edited copy with `--config`. Provider/model alternatives (bigger dense model,
SPLADE sparse, Ollama embeddings) are noted there and in SETUP.md.

## 6. Strong local profile and measured alternatives

The shipped persistent profile uses the strongest measured local combination:
**Nemotron-generated contextual retrieval + Qwen3 reranking + parent-4k extractive
answer packing**. It remains local-first and cloud-free, but it requires the local
Nemotron OpenAI-compatible chat endpoint for indexing/answer tests and the local
Qwen3 `/rerank` endpoint for reranked queries.

Contextual retrieval generates a 1–2-sentence "situating context" per chunk and
prepends it to the **embedding/sparse** field, keeping `raw_text` byte-verbatim
for citations:

```text
[repo] path :: heading/symbol (lang)     # deterministic header — keep it
<LLM: "Defines the MctsConfig struct … for Monte-Carlo Tree Search.">
                                         # blank line
<verbatim raw_text>                      # embedded AND what is retrieved/cited
```

Measured on a six-repo gold set (held-out): Gemma contextual retrieval gave
**nDCG +0.031 overall, +0.045 on the code domain, sentinel coverage +0.080**.
Nemotron was the best context generator: **nDCG +0.059 overall, code nDCG +0.089,
code sentinel +0.158**. Qwen3-Reranker-4B on a contextual index was the largest
single retrieval win: held-out **nDCG 0.848, pMRR 0.800, sentinel 0.955, hit@5
0.991**. Parent-4k + extractive was the best citation-sensitive answer pack on
the Wave-7 caveat slice. Lessons that transfer:

- **Contextualize all chunks, code included** — the "it'll dilute identifiers" worry was
  wrong; code is exactly where it helps (prose is usually already near ceiling).
- **Keep the deterministic header** — dropping it regresses prose retrieval.
- **Serve the generator with vLLM or TensorRT-LLM** (NVFP4/FP8), not llama.cpp
  GGUF-Q8: ~25× faster for this bulk index-time pass.
- **Use Qwen3's required reranker template.** The benchmark found scores inverted
  without it; the shipped `rag_lib.py` applies the template when
  `rerank.template=qwen3`.

Method + numbers: `docs/benchmarks/2026-06-10/0014`–`0015`, `0021`, and
`docs/benchmarks/2026-06-12/0022`. Re-validate on YOUR corpus (§4).

### Other index-time techniques, measured on the same gold set

The **one rule** that explains all of them: index-time context helps only when it **sharpens** a
chunk's identity, and it must apply to **code**, not just prose.

- **Doc2Query / document expansion** (campaign, index-time LLM — `0018`): generate a few search
  queries each chunk answers and append them to a **separate BM25 field** (lexical only — leave
  dense and `raw_text` untouched). A real **code** win (held-out nDCG +0.030, sentinel +0.082) at
  ≈ contextual-retrieval quality, but it regresses some prose slices, so contextual retrieval is the
  cleaner default. Apply to **all** chunks — prose-only **regressed code**.
- **Session metadata capsule** (portable, deterministic, **no LLM** — `0017`): for session **transcripts** (`…/transcripts/…`, `…/llm-sessions-history/…`), prepend `session <id>
<vendor> <date> — <name>; files: <files it touched>` to each chunk. The live signal is the
  **mentioned-file list** (the path already gives date/index/vendor). Optional, corpus-conditional —
  it drove transcript retrieval to near-perfect on a transcript-heavy repo; flat elsewhere. Enable +
  validate on a gold set; don't ship it as a forced default.
- **Late chunking / LLM-free contextual embedding** — **tested and rejected** (`0016`): pooling each
  chunk over whole-document context (bge-m3) **blurs** within-document discrimination and regressed
  every slice (nDCG −0.115). There is no cheap LLM-free substitute for contextual retrieval here.
- **Measurement caveat:** Qdrant HNSW re-indexing is non-deterministic at ~**0.03** per single
  slice — trust domain aggregates + cross-split replication, not a lone small per-slice delta.
