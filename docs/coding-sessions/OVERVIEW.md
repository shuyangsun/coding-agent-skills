# coding-sessions/

Exported, redacted transcripts of the coding-agent sessions that built and tested
this repo's skills. Each is a faithful record of one session — kept verbatim, so
prose is never reflowed and the per-file `<!-- markdownlint-disable MD013 MD024 -->`
directive lets repeated `## User` / `## Assistant` headings lint cleanly.

This is the canonical layout the other `docs/` types now mirror.

## Convention

```text
docs/coding-sessions/YYYY-MM-DD/NNNN-<ide>-slug.md
```

- **`YYYY-MM-DD/`** — session date.
- **`NNNN`** — zero-padded index, unique and monotonic across the whole tree
  (continues across date folders; allocated by `export-coding-session`'s
  `next-index.sh`).
- **`<ide>`** — vendor: `claude`, `cursor`, `codex`, `gemini`.
- Exports are produced by the `export-coding-session` skill; never authored by hand.

## Sessions

- [`2026-06-06/`](2026-06-06/) — `0000`–`0016`: skill port, VCS hooks, agent
  permissions, and the first rounds of `improving-vcs-skill`.
- [`2026-06-07/`](2026-06-07/) — `0017`–`0028`: `vcs` guardrails, jj-vs-Git
  benchmarks, the docs/rag harness, and inception tooling.
- [`2026-06-08/`](2026-06-08/) — `0034`–`0040`: context-retrieval skill
  restructuring, RAG benchmarks, and session-export follow-through.
