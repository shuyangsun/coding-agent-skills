<!-- markdownlint-disable MD013 MD024 -->

# Codex VCS jj vs Git token benchmark

- **Date:** 2026-06-07
- **Repo:** coding-agent-skills (jj workspace `codex-benchmark-vcs-workflows-run`, target bookmark `main`)
- **Author:** Shuyang Sun <shuyangsun10@gmail.com>
- **Agent:** Codex Desktop (`gpt-5.5`, reasoning: not recorded in session metadata)
- **Summary:** Benchmarked the `vcs` skill's Jujutsu workspace workflow against the Git worktree workflow with Codex sub-agents, captured speed and output-token data across model tiers, documented the conclusion under `docs/benchmarks/`, then prepared the benchmark and transcript for landing on `main`.

## User

Provided repository instructions from `AGENTS.md` for `coding-agent-skills`, including the skill layout, repo-agnostic constraints, Prettier/markdownlint workflow, and VCS hook setup.

## User

Asked to benchmark agents using the `improving-vcs-skill` harness without changing the skill code, focusing on token usage and speed comparison between the Jujutsu workspace workflow and the Git worktree workflow, and to save findings under `docs/benchmarks/`.

The user also provided the full `improving-vcs-skill` instructions, including the deterministic integration harness, model-tier matrix, metrics definitions, and start-isolation flow.

## Assistant

Loaded the `improving-vcs-skill` and `vcs` instructions, confirmed the benchmark should be measurement-only, and worked from an isolated jj workspace. The local VCS guard initially treated some tool calls as if they were in the shared default workspace, so disposable harness operations were run with explicit cwd handling through the Node REPL rather than by editing the shared checkout.

Tool calls summarized:

- Read `improving-vcs-skill/SKILL.md`, `LOOP.md`, `METRICS.md`, `MATRIX.md`, and `SCENARIOS.md`.
- Read `vcs/SKILL.md`.
- Provisioned disposable benchmark sandboxes under a temporary harness directory for jj integration, Git integration, jj start isolation, and Git start isolation.

## Assistant

Ran medium serialized integration rounds in both modes with three Codex sub-agents mapped to model tiers:

- `large`: `gpt-5.5`
- `mid`: `gpt-5.4`
- `small`: `gpt-5.4-mini`

The sub-agents received only the `vcs` skill, their generated brief, and their assigned workspace path. They landed pre-committed `agent-K` work onto shared `main` and returned structured reports.

Integration results:

```text
jj large:  total 40s,  output tokens 1,482,  quality PASS
jj mid:    total 55s,  output tokens 2,718,  quality PASS
jj small:  total 337s, output tokens 29,095, quality PASS

git large: total 40s,  output tokens 1,633,  quality PASS
git mid:   total 48s,  output tokens 2,317,  quality PASS
git small: total 39s,  output tokens 3,158,  quality PASS
```

The harness quality oracle passed in both modes. Jj also passed default-workspace readiness and retired-workspace cleanup; Git had no stale branches.

## Assistant

Ran one mid-tier start-isolation round per mode to compare the front of the workflow. Both agents isolated correctly and landed the tiny requested change.

Start-isolation results:

```text
jj mid:  total 135s, output tokens 5,189, retries 3, stalls 1, isolation PASS, naming FAIL
git mid: total 111s, output tokens 5,260, retries 1, stalls 0, isolation PASS, naming PASS
```

The jj naming failure was that the harness observed an `agent-pending-*` workspace/bookmark name instead of a `codex-*` name. The Git worktree path used a `codex-pending-*` name and passed.

## Assistant

Saved the benchmark report and raw TSV:

- `docs/benchmarks/0004-codex-gpt-jj-vs-git-token-speed.md`
- `docs/benchmarks/data/0004-codex-gpt-jj-vs-git-metrics.tsv`

The conclusion recorded there: Git worktrees had the practical speed/token advantage in this Codex run. With powerful models the gap was small or nonexistent; the headline Git advantage came mostly from the small-tier jj run, where guard and YAML conflict-resolution friction caused a large token and wall-clock spike.

Validation summarized:

- Both integration rounds passed `check-quality.sh`.
- Both start rounds passed correctness; both passed isolation; jj failed naming, Git passed naming.
- Output tokens were read from Codex transcript `token_count` events.
- The raw TSV had 8 data rows and a consistent 19-column shape.
- The benchmark Markdown passed targeted Prettier and targeted markdownlint checks.

## User

Asked whether the benchmark used both smaller and powerful models or only small ones.

## Assistant

Answered that the integration benchmark covered all three tiers: `large=gpt-5.5`, `mid=gpt-5.4`, and `small=gpt-5.4-mini`. Also clarified that the start-isolation comparison used only the mid tier.

## User

Asked whether the gap was smaller with more powerful models.

## Assistant

Answered yes and summarized the tier table:

```text
large / gpt-5.5:      jj 40s / 1,482 tokens, git 40s / 1,633 tokens
gpt-5.4 / mid:        jj 55s / 2,718 tokens, git 48s / 2,317 tokens
gpt-5.4-mini / small: jj 337s / 29,095 tokens, git 39s / 3,158 tokens
```

The assistant noted that the large tier was effectively tied, the mid tier had only a small Git edge, and the headline Git advantage was mostly a small-model friction case in the jj flow.

## User

Asked to document that tier-gap table in the benchmark Markdown if it was not already present, then advance `main`, export the session, and use `vcs` to commit to `main`.

## Assistant

Added a dedicated `Gap by model tier` section to `docs/benchmarks/0004-codex-gpt-jj-vs-git-token-speed.md`, formatted the report with pinned Prettier, and began this session export using the `export-coding-session` skill.
