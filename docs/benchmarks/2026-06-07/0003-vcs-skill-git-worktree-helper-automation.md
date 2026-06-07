# Benchmark: `vcs` skill - Git worktree helper automation

**Date:** 2026-06-07
**Harness:** `improving-vcs-skill` (deterministic, pre-committed conflicting work; objective resolution oracle)
**Under test:** the [`vcs`](../../../.agents/skills/vcs/SKILL.md) Git-only worktree integration path.
**Change tested:** move deterministic Git rebase conflict work into `integrate.sh`: safe additive text cleanup, structured JSON union by `id`, and higher-version scalar tie-breaks.
**Scale:** 3 serialized Git/medium rounds, 9 sub-agent runs. Baseline = 1 round before the helper change; optimized = 2 consecutive rounds after the helper change. Tiers were large / mid / small (`gpt-5.5` / `gpt-5.4` / `gpt-5.4-mini` in this Codex run).

Raw metrics: [data/0003-git-worktree-helper-metrics.tsv](0003-git-worktree-helper-metrics.tsv)

---

## Headline

| Metric                                 | Baseline round 301 | Optimized round 302 | Optimized confirmation 303 |
| -------------------------------------- | ------------------ | ------------------- | -------------------------- |
| Objective oracle                       | **FAIL**           | **PASS**            | **PASS**                   |
| Agent pass rate                        | 0%                 | **100%**            | **100%**                   |
| Wall max                               | 67 s               | **30 s**            | **33 s**                   |
| Mean total                             | 48 s               | **26 s**            | **24 s**                   |
| Conflict max                           | 44 s               | **0 s**             | **0 s**                    |
| Mean conflict                          | 26 s               | **0 s**             | **0 s**                    |
| Retries                                | 2                  | **0**               | **0**                      |
| Stale merged branches                  | 0                  | **0**               | **0**                      |
| Manual JSON registry union correctness | **lost entry**     | **correct**         | **correct**                |

The Git helper change produced a meaningful improvement in both quality and
speed. The previous Git path asked agents to manually union every rebase
conflict; that baseline lost `validation-2` from `app/registry.json`, even though
the agents self-reported success. After the change, two consecutive optimized
rounds passed the oracle, removed all manual conflict-resolution time, and kept
branch hygiene clean.

---

## Method

Each round used `new-sandbox.sh --mode git --difficulty medium --agents 3`.
Every agent's feature work was already committed on `agent-K`; the sub-agent was
given only the `vcs` skill and its integration brief, then asked to land
`agent-K` onto shared `main` from its own Git worktree. Agents ran serially so
agent 2 integrated after agent 1 moved `main`, and agent 3 integrated after both
earlier agents moved `main`.

Medium difficulty exercises:

- `docs/CHANGELOG.md`: additive Markdown union.
- `app/handlers.py`: additive Python list union.
- `app/registry.json`: JSON plugin array union by plugin `id`.
- `app/config.yaml`: same-key `version:` tie-break; keep the higher value.

Quality was scored with `check-quality.sh`; the reported times are from the
sub-agent structured reports. Token counts are recorded as `0` because this
manual multi-agent run did not expose transcript JSONL output-token files to
`_score.py`.

---

## Results

### Scoreboard

```text
== BY ROUND (trend: lower is better; delta vs previous round) ==
round diff      n  pass%  wall(max)     d  mean_tot  conf(max)     d  mean_cnf  mean_tok stale  orph  def  iso  name  retr stall
--------------------------------------------------------------------------------------------------------------------------------------
301   medium    3     0%         67              48         44              26         0     0     0    -    -     -     2     0
302   medium    3   100%         30   -37        26          0   -44         0         0     0     0    -    -     -     0     0
303   medium    3   100%         33    +3        24          0    +0         0         0     0     0    -    -     -     0     0
```

### Per-agent timings

| round | arm          | tier  | total | conflict | quality |
| ----- | ------------ | ----- | ----: | -------: | ------- |
| 301   | baseline     | large |  22 s |      0 s | FAIL    |
| 301   | baseline     | mid   |  67 s |     44 s | FAIL    |
| 301   | baseline     | small |  54 s |     34 s | FAIL    |
| 302   | optimized    | large |  22 s |      0 s | PASS    |
| 302   | optimized    | mid   |  30 s |      0 s | PASS    |
| 302   | optimized    | small |  25 s |      0 s | PASS    |
| 303   | confirmation | large |  26 s |      0 s | PASS    |
| 303   | confirmation | mid   |  33 s |      0 s | PASS    |
| 303   | confirmation | small |  14 s |      0 s | PASS    |

### Oracle output

Baseline round 301 failed because the final `main` lost a registry array entry:

```text
FAIL: app/registry.json: lost array element id='validation-2'
RESULT: FAIL
```

Optimized rounds 302 and 303 both passed the full oracle:

```text
ok: docs/CHANGELOG.md: union intact (3 contributions, no dups)
ok: app/registry.json: array union intact (4 elements)
ok: app/handlers.py: union intact (3 contributions, no dups)
ok: app/config.yaml: tie-break correct (version=1.5.3)
STALE_REFS=0
RESULT: PASS
```

---

## Implementation Under Test

The optimized `integrate.sh` Git path now tries deterministic conflict handling
before asking the agent to intervene:

- `conflict-preview.py --write` for additive text files, with `py_compile` guard
  for Python.
- `json-union-merge.py` for conflicted JSON files using Git index stages
  `:1:`, `:2:`, and `:3:`. It recursively merges objects, unions arrays, and
  treats arrays of objects with `id` fields as keyed collections.
- `scalar-version-merge.py` for one-line same-key version assignments in config
  files, keeping the higher numeric/version-like value.

The helper still stops with `VCS_CONFLICT=git` if a file does not match one of
those conservative patterns.

---

## Validation Notes

- `bash -n` passed for `integrate.sh`.
- `python3 -m py_compile` passed for `conflict-preview.py`,
  `json-union-merge.py`, and `scalar-version-merge.py`.
- A direct Git/medium three-agent probe passed `check-quality.sh` before the
  sub-agent reruns.
- A jj/easy two-agent smoke check passed when scored from the helper-reported
  live `NEXT_CWD`; an initial wrapper attempt scored from a retired workspace
  directory and failed only because the parent shell remained in a deleted cwd.

---

## Limitations

- Only Git/medium serialized integration was benchmarked here, because the goal
  was specifically Git + worktrees. The full ladder should be rerun if this Git
  automation is extended to harder conflict shapes.
- Output-token metrics were not captured in this manual multi-agent run.
- The helper intentionally handles only conservative, deterministic patterns.
  Arbitrary semantic conflicts still belong to the agent.
