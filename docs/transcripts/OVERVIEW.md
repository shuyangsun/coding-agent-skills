# transcripts/

Exported, redacted transcripts of the coding-agent sessions that built and tested
this repo's skills. Each is a faithful record of one session — kept verbatim, so
prose is never reflowed and the per-file `<!-- markdownlint-disable MD013 MD024 -->`
directive lets repeated `## User` / `## Assistant` headings lint cleanly.

This is the canonical layout the other `docs/` types now mirror.

## Convention

```text
docs/transcripts/YYYY-MM-DD/NNNN-<ide>-slug.md
```

- **`YYYY-MM-DD/`** — session date.
- **`NNNN`** — zero-padded index, unique and monotonic across the whole tree
  (continues across date folders; allocated by `export-transcript`'s
  `next-index.sh`).
- **`<ide>`** — vendor: `claude`, `cursor`, `codex`, `gemini`.
- Exports are produced by the `export-transcript` skill; never authored by hand.

## Sessions

- [`2026-06-06/`](2026-06-06/) — `0000`–`0016`: skill port, VCS hooks, agent
  permissions, and the first rounds of `improving-vcs-skill`.
- [`2026-06-07/`](2026-06-07/) — `0017`–`0033`: `vcs` guardrails, jj-vs-Git
  benchmarks, the docs/rag harness, docs convention migration, VCS setup, and
  inception tooling.
- [`2026-06-08/`](2026-06-08/) — `0034`–`0044`: context-retrieval skill
  restructuring, RAG/GraphRAG/graphify benchmarks, Phase 1 RAG eval-set
  collection + consolidation, Cursor Phase 2 RAG research, and session-export
  follow-through.
- [`2026-06-09/`](2026-06-09/) — `0045`–`0053`: Codex, Claude, and Agy Phase 2/3
  RAG optimization, consolidated planning, LiteLLM endpoint setup, workstation
  install notes, and deferred judge/model downloads.
- [`2026-06-10/`](2026-06-10/) — `0054`–`0057`: RAG Phase 3 Waves 0–6, contextual
  retrieval generator comparison, late chunking, session metadata, Doc2Query, and
  Qwen reranker work.
- [`2026-06-11/`](2026-06-11/) — `0058`: VCS guard relaxation.
- [`2026-06-12/`](2026-06-12/) — `0059`–`0065`: launch warnings, Wave 7 answer
  faithfulness, image retrieval/context harness work, transcript directory
  renaming, and RAG text-format updates.
