---
title: "Claude VCS jj vs Git token & speed benchmark"
date: 2026-06-07
repo: "coding-agent-skills (jj workspace `claude-vcs-benchmark`, target bookmark `main`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Opus 4.8, 1M context, thinking: high)"
summary: >-
  Reproduced the GPT/Codex `vcs`-skill jj-vs-Git benchmark with Claude models across tiers
  (opus/sonnet/haiku) using the `improving-vcs-skill` harness; extracted a
  model/tooling-generic reproduction prompt, ran medium serialized integration plus
  mid-tier start-isolation rounds in both VCS modes, scored time/tokens/quality, and
  merged the Claude results into the renamed generic benchmark file alongside the GPT run.
---

<!-- markdownlint-disable MD013 MD024 -->

# Claude VCS jj vs Git token & speed benchmark

## User

Under `docs/benchmarks/`, the latest benchmarks ran by GPT Codex tested different tiers of GPT models against different conflict scenarios with different difficulties. Find the transcript under `docs/coding-sessions/` that was used to generate this benchmark, and extract a prompt that is model / tooling generic, so it can be used to promote different models and agentic coding tools to run the same benchmark sweep. After that, run the same benchmark with different Claude models at different tiers, focus on time, token usage, and quality. Save the benchmark result in the same file as the GPT one, don't create new file for this. If the benchmark file name is GPT-specific, change it to a more generic name.

## Assistant

Explored `docs/benchmarks/2026-06-07/` and identified the latest GPT benchmark `0004-codex-gpt-jj-vs-git-token-speed.md` plus its raw TSV `0004-codex-gpt-jj-vs-git-metrics.tsv`. Read the report: Codex sub-agents across tiers (`large=gpt-5.5`, `mid=gpt-5.4`, `small=gpt-5.4-mini`), 2 medium serialized integration rounds (jj + git, 3 agents each) and 2 mid-tier start-isolation rounds.

Found the generating transcript at `docs/coding-sessions/2026-06-07/0027-codex-vcs-jj-vs-git-token-benchmark.md`, which used the `improving-vcs-skill` harness.

Read the harness docs (`SKILL.md`, `LOOP.md`, `METRICS.md`, `MATRIX.md`) and the bundled scripts: `new-sandbox.sh`, `check-quality.sh`, `check-isolation.sh`, `_score.py`, `record-metrics.sh`, `scoreboard.sh`, and the workflow runners `_run-baseline.wf.js` / `_run-start.wf.js`. Confirmed the runners already map tiers to Claude models (`large=opus`, `mid=sonnet`, `small=haiku`).

## Assistant

Renamed the session work to `claude-vcs-benchmark`, backed up and reset the live harness metrics log, then provisioned four sandboxes mirroring the GPT run:

- round 601: jj, medium, 3 agents (integrate)
- round 602: git, medium, 3 agents (integrate)
- round 603: jj, start (`--start-from main`), 1 agent
- round 604: git, start (`--start-from main`), 1 agent

## Assistant

Launched two background workflows via the bundled runners:

- `_run-baseline.wf.js` — integration rounds 601 (jj) + 602 (git), each across `large`/`mid`/`small` tiers.
- `_run-start.wf.js` — start rounds 603 (jj) + 604 (git) at mid tier, with the deterministic start briefs passed in.

Each sub-agent received only the `vcs` skill, its brief, and its assigned workspace path — withholding the harness, the mode, and conflict locations.

## Assistant

Both workflows completed. All eight sub-agents published successfully.

Integration results (all PASS):

```text
601 jj  large opus    103s  1,181 tok  retr0 stall1
601 jj  mid   sonnet   33s    326 tok
601 jj  small haiku   112s    515 tok  (conflict 55s — config.yaml version tie-break 1.5.3>1.5.1)
602 git large opus    128s    552 tok  retr1 stall1 (quoted-cd guard mis-detect, corrected)
602 git mid   sonnet   29s    260 tok
602 git small haiku    54s     57 tok
```

Start-isolation results (all PASS, isolation + naming):

```text
603 jj  mid sonnet 111s 944 tok  iso=pass name=pass (claude-streaming-export)
604 git mid sonnet  96s 412 tok  iso=pass name=pass
```

## Assistant

Scored with `_score.py` (running `check-quality.sh` + `check-isolation.sh` per round). Hit two harness gotchas and fixed them:

1. `_score.py`'s token map keys on `round-<N>/ws-agent-<K>`, but start-round prompts bake the repo path — so start tokens recorded as 0. Recomputed per-agent `output_tokens` from the workflow transcript JSONLs (matching `round-<N>` only) and patched rounds 603/604 to 944 / 412.
2. The live `metrics.tsv` had a stale 16-column header while `record-metrics.sh` writes 19 columns, so `scoreboard.sh` read `quality` from the wrong field and showed a bogus 0% pass. Rewrote the header to the canonical 19-column form.

Final scoreboard: 100% pass across all rounds and tiers; `stale`/`orph`/`def`/`iso`/`name` all 0. Conflict time non-zero only for haiku-on-jj (the deliberate version tie-break, resolved correctly).

## Assistant

Renamed the GPT-specific files to generic names and merged both families into one report:

- `0004-codex-gpt-jj-vs-git-token-speed.md` → `0004-vcs-jj-vs-git-token-speed.md`
- `0004-codex-gpt-jj-vs-git-metrics.tsv` → `0004-vcs-jj-vs-git-metrics.tsv`

Rewrote the markdown with: a model/tooling-generic "Reproduce this benchmark" prompt, a cross-family headline comparison, the new Claude run (Run B), and the preserved GPT run (Run A), plus a combined conclusion and limitations. Appended the eight Claude metric rows (rounds 6xx, annotated `family=claude;model=…`) to the renamed TSV alongside the GPT rows (5xx). Updated `docs/benchmarks/OVERVIEW.md`.

Key conclusion: both families resolve correctly in both modes at every tier. GPT's "Git wins" headline came from a single small-tier jj outlier (337s / 29,095 tokens) that did not occur for Claude (haiku jj: 112s / 515 tokens), so the advantage is Codex-specific, not a jj property. Claude also closed the jj naming gap. The shared friction in both families is the `vcs-check` cwd guard's unquoted-`cd` requirement. Noted the cross-vendor token caveat (different tokenizers → indicative, not exact).

Ran Prettier and markdownlint on the changed files (clean), tore down the four sandboxes, and restored the live harness metrics log to its prior state. Recorded a memory about the two harness scoring gotchas.

## User

Export session history, commit and push using /vcs.

## Assistant

Exported this transcript via `export-coding-session`, then used the `vcs` skill to commit and publish the benchmark, renamed files, OVERVIEW update, and this transcript onto `main`.
