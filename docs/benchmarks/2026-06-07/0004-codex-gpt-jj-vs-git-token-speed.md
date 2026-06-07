# Benchmark: `vcs` skill - Codex GPT token and speed comparison for jj workspaces vs Git worktrees

**Date:** 2026-06-07
**Harness:** `improving-vcs-skill` (deterministic sandboxes, objective quality and isolation checks)
**Under test:** the [`vcs`](../../../.agents/skills/vcs/SKILL.md) Jujutsu workspace flow vs Git worktree flow.
**Agents/models:** Codex sub-agents across tiers: `large=gpt-5.5`, `mid=gpt-5.4`, `small=gpt-5.4-mini`.
**Scale:** 8 sub-agent runs: 2 medium serialized integration rounds (jj and Git, 3 agents each) plus 2 mid-tier start-isolation rounds (jj and Git, 1 agent each).

Raw metrics: [data/0004-codex-gpt-jj-vs-git-metrics.tsv](0004-codex-gpt-jj-vs-git-metrics.tsv)

---

## Headline

| Metric                                      | Jujutsu workspaces | Git worktrees   |
| ------------------------------------------- | ------------------ | --------------- |
| Integration oracle                          | **PASS**           | **PASS**        |
| Integration agents passing                  | **3 / 3**          | **3 / 3**       |
| Integration wall max                        | 337 s              | **48 s**        |
| Integration serialized total                | 432 s              | **127 s**       |
| Integration mean output tokens              | 11,098             | **2,369**       |
| Start-isolation oracle                      | **PASS**           | **PASS**        |
| Start-isolation total                       | 135 s              | **111 s**       |
| Start-isolation output tokens               | **5,189**          | 5,260           |
| Start-isolation naming (`<ide>-<work>`)     | **FAIL**           | **PASS**        |
| Hygiene (`stale` / `orph` / `def failures`) | **0 / 0 / 0**      | **0 / 0 / n/a** |

In this Codex/GPT run, Git worktrees showed the practical advantage. Both modes
produced correct integrated `main` results, but Git used much less wall-clock and
many fewer output tokens on the medium integration benchmark. Jujutsu did not
provide a token or speed advantage here.

The result is not "jj is bad" in general. The data says that, for this current
`vcs` skill plus Codex Desktop guard environment, jj's extra lifecycle and guard
friction can dominate its helper advantages, especially for the small-tier model.

---

## Method

The integration rounds used `new-sandbox.sh --difficulty medium --agents 3` in
both modes. Agents ran serially within each mode: agent 1 landed first, then
agent 2 integrated over agent 1, then agent 3 integrated over both earlier
agents. Each agent received only the `vcs` skill, its generated brief, and its
assigned workspace path.

The start rounds used `new-sandbox.sh --task start --start-from main` in both
modes with one mid-tier agent. These measure the front of the workflow: whether
the agent isolates into its own jj workspace or Git worktree before editing.

Token counts came from Codex transcript JSONL `token_count` events, using the
final per-agent `output_tokens` total. This run captured actual output tokens,
unlike earlier manual shell-driven benchmark reports.

Quality was checked with:

- `check-quality.sh` for integration correctness, stale refs, default readiness,
  and orphan workspace cleanup.
- `check-isolation.sh` for start-round isolation and naming.

---

## Scoreboard

```text
== BY ROUND (trend: lower is better; delta vs previous round) ==
round diff      n  pass%  wall(max)     d  mean_tot  conf(max)     d  mean_cnf  mean_tok stale  orph  def  iso  name  retr stall
--------------------------------------------------------------------------------------------------------------------------------------
501   medium    3   100%        337             144          0               0     11098     0     0    0    -     -     1     0
502   medium    3   100%         48  -289        42          0    +0         0      2369     0     0    -    -     -     0     0
503   easy      1   100%        135   +87       135          0    +0         0      5189     0     0    -    0     1     3     1
504   easy      1   100%        111   -24       111          0    +0         0      5260     0     0    -    0     0     1     0
```

`conflict_s` is not informative in this run: helpers auto-resolved many
conflicts, and the jj small-tier agent explicitly missed the first-conflict
timestamp while resolving the YAML scalar conflict. Total time, retries, stalls,
tokens, and the objective oracle are the reliable signals.

---

## Integration Results

| mode | tier  | model          | total | output tokens | retries | quality | note                                  |
| ---- | ----- | -------------- | ----: | ------------: | ------: | ------- | ------------------------------------- |
| jj   | large | `gpt-5.5`      |  40 s |         1,482 |       0 | PASS    | first landing, no conflict stop       |
| jj   | mid   | `gpt-5.4`      |  55 s |         2,718 |       0 | PASS    | additive conflict auto-resolved       |
| jj   | small | `gpt-5.4-mini` | 337 s |        29,095 |       1 | PASS    | YAML scalar conflict plus guard retry |
| git  | large | `gpt-5.5`      |  40 s |         1,633 |       0 | PASS    | first landing, no conflict stop       |
| git  | mid   | `gpt-5.4`      |  48 s |         2,317 |       0 | PASS    | additive conflict auto-resolved       |
| git  | small | `gpt-5.4-mini` |  39 s |         3,158 |       0 | PASS    | helper completed without manual stop  |

### Integration deltas

| metric             |     jj |   git | git advantage              |
| ------------------ | -----: | ----: | -------------------------- |
| Wall max           |  337 s |  48 s | 289 s faster               |
| Serialized total   |  432 s | 127 s | 305 s faster               |
| Mean total         |  144 s |  42 s | 102 s faster per agent     |
| Output tokens      | 33,295 | 7,108 | 26,187 fewer output tokens |
| Mean output tokens | 11,098 | 2,369 | 8,729 fewer tokens per run |

The main divergence was the small-tier jj run. Excluding the small-tier outlier,
jj and Git are close: jj large+mid totaled 95 s / 4,200 output tokens, while Git
large+mid totaled 88 s / 3,950 output tokens. The small-tier cell changed the
conclusion because it is exactly where ambiguous workflow edges matter most.

### Gap by model tier

| tier                     | jj total | git total | jj output tokens | git output tokens | gap                           |
| ------------------------ | -------: | --------: | ---------------: | ----------------: | ----------------------------- |
| `large` / `gpt-5.5`      |     40 s |      40 s |            1,482 |             1,633 | tie; jj slightly fewer tokens |
| `mid` / `gpt-5.4`        |     55 s |      48 s |            2,718 |             2,317 | small Git edge                |
| `small` / `gpt-5.4-mini` |    337 s |      39 s |           29,095 |             3,158 | huge Git edge                 |

The jj-vs-Git gap was much smaller with more powerful models. The `large` tier
was effectively tied, the `mid` tier had only a modest Git edge, and the
headline Git advantage came mostly from the small-tier jj run.

---

## Start-Isolation Results

| mode | tier | model     | total | output tokens | retries | stalls | isolation | name | quality |
| ---- | ---- | --------- | ----: | ------------: | ------: | -----: | --------- | ---- | ------- |
| jj   | mid  | `gpt-5.4` | 135 s |         5,189 |       3 |      1 | PASS      | FAIL | PASS    |
| git  | mid  | `gpt-5.4` | 111 s |         5,260 |       1 |      0 | PASS      | PASS | PASS    |

Both agents correctly isolated before editing and landed the requested change.
Git was 24 s faster. Token usage was effectively tied, with jj 71 output tokens
lower, but jj had more retries and missed the naming convention: the harness saw
`agent-pending-*` rather than a `codex-*` workspace/bookmark name. Git created a
`codex-pending-*` worktree/branch and passed naming.

---

## Observations

### Git worktrees have the current speed/token edge

With the current helper automation, Git worktrees passed the same medium
integration oracle while using substantially less wall-clock and fewer output
tokens. The Git helper path now handles the deterministic medium conflicts well
enough that jj's usual conflict-preview advantage did not show up in the final
agent-level cost.

### Jj remains correct and hygienic, but has more workflow surface

The jj integration round passed default readiness and workspace hygiene:
`DEFAULT_OK=pass`, no stale bookmarks, no orphan workspace entries, no orphan
directories, and no orphan empty side-heads. That is the good news.

The cost is that jj exposes more lifecycle states to the agent: stale default
recovery, retired workspace cleanup, `NEXT_CWD` after a workspace is removed, and
guarded direct edits. In this run those edges were expensive for the small model.

### Codex guard cwd behavior affected both modes

Several agents reported that tool-level `workdir` was not enough for guarded
write commands; they had to use an explicit `cd` inside the shell command. This
is not purely a jj-vs-Git property, but jj was hit harder in the cells that
needed manual intervention. Treat these numbers as a benchmark of the practical
Codex agent workflow, not raw VCS command latency.

---

## Conclusion

For the current `vcs` skill in Codex Desktop, the data does **not** support
switching to Jujutsu for token or speed efficiency. Git worktrees delivered equal
quality with lower wall-clock on both measured workflow bookends, and much lower
output-token use on the integration benchmark.

Jujutsu's advantage is still semantic and operational rather than measured speed
here: it gives explicit workspace semantics and the harness proved the cleanup
path can be correct. But unless the jj small-tier/guard friction is reduced,
that advantage does not translate into better agent throughput.

The next benchmark should rerun `hard` and concurrent rounds with transcript
token capture. If jj wins anywhere, it should be under heavier multi-file
conflict pressure where conflict-preview and workspace semantics have more room
to offset lifecycle overhead.

---

## Limitations

- Single benchmark run, not multiple consecutive rounds.
- Medium integration plus easy start only; no hard or concurrent stress round.
- Codex Desktop guard behavior was part of the measured workflow and may not
  match another agent host.
- `conflict_seconds` was unreliable because helper auto-resolution and missed
  conflict-start timestamps collapsed it to zero.
- The jj start-round naming failure may be a skill/guard interaction rather than
  inherent to Jujutsu, but it is still a real workflow miss in this run.
