# docs/

Long-lived project documentation for **coding-agent-skills**: benchmarks, plans,
issues, prompts, research notes, and exported agent sessions. Source-of-truth for
_why_ the skills look the way they do and _how_ they were measured.

## Convention

Every doc lives at:

```text
docs/<type>/YYYY-MM-DD/NNNN-slug.md
```

- **`YYYY-MM-DD/`** — date the doc was created, as a subdirectory.
- **`NNNN`** — zero-padded index, unique and monotonic _within each type_
  (preserved across the date subdirs; numbering does not restart per day).
- **`slug`** — short, descriptive, lower-case-kebab. Co-located data files
  (e.g. benchmark `.tsv`) share their doc's `NNNN` and date folder.
- `coding-sessions/` additionally tags the vendor: `NNNN-<ide>-slug.md`.

Each `type/` directory carries its own `OVERVIEW.md`. Front-load the high-signal
material (dates, status, scope) so an agent skimming the first ~100 lines can judge
relevance fast.

## Types

| Type                                              | Holds                                                    |
| ------------------------------------------------- | -------------------------------------------------------- |
| [`coding-sessions/`](coding-sessions/OVERVIEW.md) | Exported agent session transcripts, by date.             |
| [`benchmarks/`](benchmarks/OVERVIEW.md)           | Measurement reports (+ `.tsv` data) for the skills.      |
| [`issues/`](issues/OVERVIEW.md)                   | Documented failure modes observed in agent VCS sessions. |
| [`plans/`](plans/OVERVIEW.md)                     | Design/plan docs framing _what_ to build and _why_.      |
| [`prompts/`](prompts/OVERVIEW.md)                 | Prompts used to kick off skill-authoring work.           |
| [`research/`](research/OVERVIEW.md)               | External research notes that inform skill design.        |
