---
title: "Codex Git worktree helper automation"
date: 2026-06-07
repo: "coding-agent-skills (jj workspace `codex-optimize-git-worktrees-vcs`, `main` bookmark)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Codex Desktop (`gpt-5.5`, reasoning: xhigh)"
summary: >-
  Optimized the `vcs` skill's Git + worktrees integration path by moving deterministic
  rebase conflict handling into helper scripts, benchmarked the before/after with the
  `improving-vcs-skill` harness, saved benchmark results, rebased onto updated `main`, and
  prepared the change for merge/push.
---

<!-- markdownlint-disable MD013 MD024 -->

# Codex Git worktree helper automation

## Transcript

## User

Provided repository instructions from `AGENTS.md` for `coding-agent-skills`, including the repo layout, skill portability requirements, and formatting/linting workflow.

## User

```text
In a previous coding session @docs/coding-sessions/2026-06-07/0017-codex-vcs-script-first-jj-workspaces.md, we optimized Jujutsu + workspaces workflow using the [$improving-vcs-skill](./.agents/skills/improving-vcs-skill/SKILL.md) harness. Use the same principle to optimize the [$vcs](./.agents/skills/vcs/SKILL.md) skill for the Git + worktrees workflow. Benchmark to make sure it actually made meaningful improvements, save benchmark results under @docs/benchmarks/.
```

## User

Provided the full `improving-vcs-skill` and `vcs` skill contents for runtime context.

## Assistant

Loaded `vcs` and `improving-vcs-skill`, detected this repository as jj-backed, and created an isolated workspace with:

```sh
bash .agents/skills/vcs/scripts/isolate.sh codex-optimize-git-worktrees-vcs
```

The helper created `coding-agent-skills-codex-optimize-git-worktrees-vcs`, and all subsequent work happened from that workspace.

## Assistant

Read the previous session transcript, the `improving-vcs-skill` loop/metrics docs, and the current `vcs` files. The key finding was an asymmetry: the jj path in `integrate.sh` already auto-resolved mechanically additive conflicts, while the Git path stopped on every conflict and pushed semantic resolution back to the model.

## Assistant

Provisioned a fresh Git-only medium integration round with three serialized agents using the harness. This gave the current Git helper a baseline before any changes.

Tool calls summarized:

- `new-sandbox.sh --mode git --difficulty medium --agents 3 --round 301`
- Spawned three sub-agents using only the `vcs` skill, one each for tiers large, mid, and small.

Baseline sub-agent reports:

```text
agent-1 large: total 22s, conflict 0s, published=true
agent-2 mid:   total 67s, conflict 44s, retries=1, published=true
agent-3 small: total 54s, conflict 34s, retries=1, published=true
```

The oracle did not agree with the agents' self-reports:

```text
FAIL: app/registry.json: lost array element id='validation-2'
RESULT: FAIL
```

## Assistant

Reproduced the failing Git conflict locally in a disposable harness sandbox. The `conflict-preview.py` marker-stripper was useful for Markdown/Python text conflicts, but produced invalid JSON for plugin array conflicts because two objects were collapsed into one object. The remaining deterministic YAML conflict was exactly the `version:` higher-value tie-break that `vcs` already defines.

## Assistant

Patched the Git path in `vcs`:

- Added `.agents/skills/vcs/scripts/json-union-merge.py` to resolve conflicted JSON from Git index stages `:1:`, `:2:`, and `:3:` by recursively merging objects and unioning arrays of objects by `id`.
- Added `.agents/skills/vcs/scripts/scalar-version-merge.py` to resolve conservative one-line same-key numeric/version assignments by keeping the higher value.
- Updated `.agents/skills/vcs/scripts/integrate.sh` so Git rebase conflicts try deterministic helper resolution before stopping with `VCS_CONFLICT=git`.
- Updated `.agents/skills/vcs/SKILL.md` and `.agents/skills/vcs/INTEGRATE.md` to document the new helper-owned Git fast path.

After a final safety review, tightened the JSON resolver so delete-vs-keep conflicts are refused instead of auto-resolved.

## Assistant

Ran direct validation before sub-agent benchmarking:

```text
bash -n integrate.sh: pass
python3 -m py_compile helper scripts: pass
direct Git/medium 3-agent probe: RESULT: PASS
```

The direct probe showed all three Git branches landed, no conflict markers remained, the JSON registry array was intact, the YAML version tie-break was correct, and `STALE_REFS=0`.

## Assistant

Reran the Git medium benchmark twice after the patch.

Round 302 optimized reports:

```text
agent-1 large: total 22s, conflict 0s, published=true
agent-2 mid:   total 30s, conflict 0s, published=true
agent-3 small: total 25s, conflict 0s, published=true
RESULT: PASS
```

Round 303 confirmation reports:

```text
agent-1 large: total 26s, conflict 0s, published=true
agent-2 mid:   total 33s, conflict 0s, published=true
agent-3 small: total 14s, conflict 0s, published=true
RESULT: PASS
```

The scoreboard delta was:

```text
301 baseline:     pass 0%,   wall(max) 67s, mean_tot 48s, conflict(max) 44s, mean_cnf 26s, retries 2
302 optimized:    pass 100%, wall(max) 30s, mean_tot 26s, conflict(max) 0s,  mean_cnf 0s,  retries 0
303 confirmation: pass 100%, wall(max) 33s, mean_tot 24s, conflict(max) 0s,  mean_cnf 0s,  retries 0
```

## Assistant

Saved benchmark artifacts:

- `docs/benchmarks/0003-vcs-skill-git-worktree-helper-automation.md`
- `docs/benchmarks/data/0003-git-worktree-helper-metrics.tsv`

The benchmark note records the failed baseline oracle, the two consecutive optimized PASS rounds, the raw metrics, implementation details, validation notes, and limitations.

## Assistant

Ran final validation for the touched files:

```text
prettier --check on touched Markdown files: pass
markdownlint-cli2 --no-globs on touched Markdown files: pass
bash -n integrate.sh: pass
python3 -m py_compile helper scripts: pass
JSON delete-conflict guard probe: refused as expected
```

Repo-wide `bun run format:check` and `bun run lint:md` still failed on pre-existing unrelated Markdown files under `docs/coding-sessions` and `docs/issues`, so those files were left untouched.

## Assistant

Reported completion: the Git + worktrees optimization was implemented in the isolated workspace, benchmarked, and documented. The headline result was baseline Git/medium `FAIL`, wall max `67s`, conflict max `44s`; optimized Git/medium `PASS`, wall max `30s`, conflict max `0s`; confirmation `PASS`, wall max `33s`, conflict max `0s`.

## User

```text
Main has changed, update it and export session transcript, commit merge push.
```

## Assistant

Loaded `vcs` for merge/publish and `export-coding-session` for transcript export. The first jj status check reported a stale working copy. Ran:

```sh
jj workspace update-stale
```

This updated the working copy and showed `main` had moved to a newer commit. The current change was still based on the previous parent, so it was rebased onto current `main`:

```sh
jj rebase -r @ -d main
```

The rebase succeeded with no conflicts. The transcript index helper first returned `0020`, but after updating from `main`, an existing `0020-claude-vcs-jj-ff-and-isolate-cd-fixes.md` was present. The helper was rerun and returned `0021`, so this transcript was written as `docs/coding-sessions/2026-06-07/0021-codex-git-worktree-helper-automation.md`.

Tool calls summarized:

- Read `export-coding-session/SKILL.md`.
- Ran `next-index.sh`.
- Collected author metadata from Git/jj config.
- Located the readable Codex session log and used it to reconstruct this compact transcript with summarized tool calls and sub-agent reports.
