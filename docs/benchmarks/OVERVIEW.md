# benchmarks/

Measurement reports that put the repo's skills under test. For `vcs`:
conflict-resolution speed/quality, branch hygiene, token cost, and Jujutsu
workspaces vs Git worktrees across vendors. For `docs`: retrieval findability of
the repo's documentation (floor-vs-doc, structure, and — later — the docs×rag
interaction). Each report records its **Date** and links the SKILL under test;
raw metrics live in a co-located `.tsv` sharing the report's `NNNN` and date
folder.

Naming: `YYYY-MM-DD/NNNN-slug.md`, `NNNN` unique across the whole `benchmarks/`
tree (does not restart per day).

## Reports

### 2026-06-06

- [`0000` — multi-agent conflict resolution](2026-06-06/0000-vcs-skill-conflict-resolution.md)
- [`0001` — branch/bookmark hygiene + token efficiency](2026-06-06/0001-vcs-skill-branch-hygiene-and-tokens.md)

### 2026-06-07

- [`0002` — jj workspaces vs Git worktrees (Cursor Composer 2.5)](2026-06-07/0002-vcs-skill-composer-2.5-jj-vs-git.md) · [data](2026-06-07/0002-composer-2.5-metrics.tsv)
- [`0003` — Git worktree helper automation](2026-06-07/0003-vcs-skill-git-worktree-helper-automation.md) · [data](2026-06-07/0003-git-worktree-helper-metrics.tsv)
- [`0004` — jj vs Git token & speed, by model tier (GPT/Codex + Claude)](2026-06-07/0004-vcs-jj-vs-git-token-speed.md) · [data](2026-06-07/0004-vcs-jj-vs-git-metrics.tsv)

### 2026-06-08

- [`0005` — `docs` skill: floor (no doc) vs with-doc findability (Phase 0)](2026-06-08/0005-docs-skill-floor-vs-doc.md) · [data](2026-06-08/0005-docs-skill-floor-vs-doc-metrics.tsv)
