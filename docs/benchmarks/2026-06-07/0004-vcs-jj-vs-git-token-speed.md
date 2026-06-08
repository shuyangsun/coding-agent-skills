# Benchmark: `vcs` skill — jj workspaces vs Git worktrees (token & speed, by model tier)

**Date:** 2026-06-07
**Harness:** `improving-vcs-skill` (deterministic sandboxes, objective quality and isolation checks)
**Under test:** the [`vcs`](../../../.agents/skills/vcs/SKILL.md) Jujutsu workspace flow vs Git worktree flow.
**Agent families measured so far:**

- **GPT / Codex Desktop** — `large=gpt-5.5`, `mid=gpt-5.4`, `small=gpt-5.4-mini` (Run A).
- **Claude / Claude Code** — `large=opus`, `mid=sonnet`, `small=haiku` (Run B).
- **Cursor / Composer 2.5** — `large=mid=small=composer-2.5-fast` (Run C; one model, three serialized agent slots).

**Scale (per family):** 8 sub-agent runs — 2 medium serialized integration rounds
(jj and Git, 3 agents each, one per tier) plus 2 mid-tier start-isolation rounds
(jj and Git, 1 agent each).

Raw metrics (all families, one row per agent): [0004-vcs-jj-vs-git-metrics.tsv](0004-vcs-jj-vs-git-metrics.tsv)
(GPT = rounds `5xx`, Claude = rounds `6xx`, Composer = rounds `7xx`; the concrete model per row is in the `notes` column).

This file is **agent- and model-agnostic**: the same harness, sandboxes, and
scoring drive any model or coding tool. The reproduction prompt below is written
so a new family can be added with only a tier→model mapping change.

---

## Reproduce this benchmark (model- and tool-agnostic)

This benchmark measures how well a coding agent collaborates **through version
control** — isolating its own work area and integrating teammates' work while
resolving merge conflicts — using the repo's [`vcs`](../../../.agents/skills/vcs/SKILL.md)
skill as its only version-control guidance. It is deliberately **not** a coding
test: every change under integration is pre-generated and pre-committed, so the
only variable is the quality and cost of the VCS workflow itself. Any model or
agentic coding tool can run it; only the tier→model mapping changes.

Drive it with the `improving-vcs-skill` harness (measurement-only — do **not**
edit the `vcs` skill):

1. **Provision deterministic sandboxes** with `new-sandbox.sh`, one per (mode ×
   difficulty) cell, outside any real repo. Cover **both VCS modes every run** —
   `--mode jj` (Jujutsu on a colocated Git backend, where a naive check would
   wrongly pick Git) and `--mode git` (plain Git + worktree, the cloud/PR path) —
   and a difficulty (`easy`/`medium`/`hard`). For the integration task each
   agent's "finished PR" is pre-committed on its own `agent-K` ref; for
   `--task start` the agent authors one tiny specified edit and must isolate
   before touching anything.

2. **Spawn one sub-agent per workspace, across three capability tiers** —
   `large` (frontier), `mid` (workhorse), `small` (fast/cheap) — mapped to
   whatever models the tool under test exposes. Give each sub-agent **only**: the
   `vcs` skill (told to load and follow it for all VCS decisions), its
   integration-only brief, and its assigned workspace path. **Withhold** the
   harness, the fact that it is a test, the VCS mode, and where conflicts are —
   detecting the mode and resolving conflicts from `vcs` alone is the test.
   Serialize agents within a round (agent 2 integrates over agent 1, etc.) so
   later agents meet earlier conflicts; resolve by **union** (keep every
   teammate's additive change) with the **higher value** winning any single-valued
   tie-break. Each agent stops the moment its work is on `main` and the `vcs`
   tidy-up is done, and returns the structured run report.

3. **Score objectively, never from self-reports.** Run `check-quality.sh` (mode
   integrity, no markers/unresolved, no lost work, the union/tie-break resolution
   oracle, plus stale-ref and jj-lifecycle hygiene) and, for start rounds,
   `check-isolation.sh` (did it carve its own worktree/workspace first, and name
   it `<ide>-<work>`). Read **output tokens per agent exactly** from each agent's
   transcript JSONL — never ask the agent to count its own tokens.

4. **Record and compare** per agent with `record-metrics.sh` and `scoreboard.sh`,
   broken down **by round and by model tier**. The headline axes are **time**
   (per-agent total and batch wall-clock), **token usage** (output tokens), and
   **quality** (the objective oracle), each reported per tier so a result that
   only holds for the largest model is visibly incomplete.

State which concrete model backed each tier in the writeup so the run is
reproducible, and note any host/guard behavior (e.g. cwd guards) that was part of
the measured workflow rather than raw VCS latency.

---

## Cross-family headline (medium integration + easy start)

| Metric                         |   GPT jj | GPT git | Claude jj | Claude git | Composer jj | Composer git |
| ------------------------------ | -------: | ------: | --------: | ---------: | ----------: | -----------: |
| Integration oracle             |     PASS |    PASS |      PASS |       PASS |        PASS |         PASS |
| Integration agents passing     |    3 / 3 |   3 / 3 |     3 / 3 |      3 / 3 |       3 / 3 |        3 / 3 |
| Integration wall max           |    337 s |    48 s |     112 s |      128 s |       460 s |         27 s |
| Integration serialized total   |    432 s |   127 s |     248 s |      211 s |       892 s |         59 s |
| Integration mean output tokens |   11,098 |   2,369 |       674 |        290 |       3,193 |          631 |
| Start oracle                   |     PASS |    PASS |      PASS |       PASS |        PASS |         PASS |
| Start total                    |    135 s |   111 s |     111 s |       96 s |       174 s |         26 s |
| Start output tokens            |    5,189 |   5,260 |       944 |        412 |       1,825 |        2,220 |
| Start naming (`<ide>-<work>`)  | **FAIL** |    PASS |  **PASS** |       PASS |    **FAIL** |     **FAIL** |
| Hygiene (stale / orph / def)   |    0/0/0 | 0/0/n/a |     0/0/0 |    0/0/n/a |       0/0/0 |      0/0/n/a |

**Read this comparison with one caveat:** output-token counts come from each
vendor's own transcript (`token_count.output_tokens` for Codex,
`usage.output_tokens` for Claude; for Composer, assistant-output characters ÷ 4
because Cursor subagent JSONL lacks a `usage` field). Different tokenizers and reasoning verbosity
make absolute cross-vendor token numbers **indicative, not exact**. The reliable
signals are the objective pass/fail oracle and the **within-family, per-tier**
trends; cross-family token gaps should be read as order-of-magnitude, not
to-the-digit.

Four things stand out across families:

- **All three families resolve correctly in both modes, at every tier.** Quality
  and hygiene are clean throughout; this benchmark is now about cost, not
  correctness.
- **GPT's headline came from a single small-tier jj outlier** (337 s / 29,095
  tokens). **Claude's small tier did not blow up** — haiku on jj resolved the
  same single-valued version tie-break in 112 s / 515 tokens. Composer's small
  tier also passed cleanly (273 s / 3,303 est. tokens) but spent 240 s on the
  YAML tie-break. So the "Git wins" story is GPT-specific to that cell, not a
  property of jj.
- **Claude fixed the jj naming miss.** GPT's jj start produced an
  `agent-pending-*` working copy (NAME_OK fail); Claude named its jj workspace
  `claude-streaming-export` (NAME_OK pass). **Composer failed naming in both
  modes** (`composer-pending-*` on jj, `composer-agent-1` on git) — same class
  of miss as GPT, not the clean `cursor-<work>` slug `vcs` expects.
- **Composer's jj integration wall max (460 s) was a mid-tier workspace-lifecycle
  stall**, not a small-tier blowup: agent 2 had to recreate a retired `ws-agent-2`
  after agent 1's tidy-up removed it. Git integration for Composer was the
  fastest family measured (27 s wall max, 631 mean est. tokens).

The friction common to all families is the `vcs-check` cwd guard: it only tracks
an **unquoted** leading `cd <abs-path> &&`; quoted paths and `-C`/`-R` forms were
rejected, costing retries/stalls. Composer additionally hit guard blocks when
the start-round assigned path was the shared jj default workspace, forcing
`isolate.sh` before any edit. That is guard/skill interaction in the measured
workflow, not raw VCS latency.

---

## Run B — Claude (Claude Code)

**Models:** `large=opus`, `mid=sonnet`, `small=haiku`. Rounds 601 (jj medium),
602 (git medium), 603 (jj start), 604 (git start). Tokens read per-agent from the
workflow transcript JSONLs; quality/isolation/naming from the oracles.

### Headline

| Metric                                      | Jujutsu workspaces | Git worktrees   |
| ------------------------------------------- | ------------------ | --------------- |
| Integration oracle                          | **PASS**           | **PASS**        |
| Integration agents passing                  | **3 / 3**          | **3 / 3**       |
| Integration wall max                        | **112 s**          | 128 s           |
| Integration serialized total                | 248 s              | **211 s**       |
| Integration mean output tokens              | 674                | **290**         |
| Start-isolation oracle                      | **PASS**           | **PASS**        |
| Start-isolation total                       | 111 s              | **96 s**        |
| Start-isolation output tokens               | 944                | **412**         |
| Start-isolation naming (`<ide>-<work>`)     | **PASS**           | **PASS**        |
| Hygiene (`stale` / `orph` / `def failures`) | **0 / 0 / 0**      | **0 / 0 / n/a** |

For Claude, both modes pass cleanly with very low output-token use, and the
jj-vs-Git gap is small. jj actually had the lower integration **wall max** (112 s
vs 128 s) because the only slow Claude cell was opus on Git hitting the quoted-cd
guard. Git is leaner on tokens (mean 290 vs 674), driven mostly by haiku-on-Git
finishing in 57 output tokens.

### Scoreboard

```text
== BY ROUND (trend: lower is better; delta vs previous round) ==
round diff      n  pass%  wall(max)     d  mean_tot  conf(max)     d  mean_cnf  mean_tok stale  orph  def  iso  name  retr stall
--------------------------------------------------------------------------------------------------------------------------------------
601   medium    3   100%        112              83         55              18       674     0     0    0    -     -     0     1
602   medium    3   100%        128   +16        70          0   -55         0       290     0     0    -    -     -     1     1
603   easy      1   100%        111   -17       111          0    +0         0       944     0     0    -    0     0     0     0
604   easy      1   100%         96   -15        96          0    +0         0       412     0     0    -    0     0     0     0

== BY MODEL TIER ==
tier      n  pass%  mean_tot  conf(max)  mean_cnf  mean_tok stale  orph  def  iso  name  retr stall
---------------------------------------------------------------------------------------------------
large     2   100%       116          0         0       866     0     0    0    -     -     1     2
mid       4   100%        67          0         0       486     0     0    0    0     0     0     0
small     2   100%        83         55        28       286     0     0    0    -     -     0     0

== PASS-RATE MATRIX (rows = tier, cols = difficulty) ==
tier\diff       easy    medium
------------------------------
large              -      100%
mid             100%      100%
small              -      100%
```

`conf(max)` is non-zero only for haiku on jj (55 s): the single-valued
`config.yaml` version tie-break, the one conflict `integrate.sh` deliberately
stops on for a human decision. Every other conflict in the run auto-resolved.

### Integration Results

| mode | tier  | model    | total | output tokens | retries | stalls | quality | note                                                     |
| ---- | ----- | -------- | ----: | ------------: | ------: | -----: | ------- | -------------------------------------------------------- |
| jj   | large | `opus`   | 103 s |         1,181 |       0 |      1 | PASS    | one-shot integrate.sh; guard blocked post-retire verify  |
| jj   | mid   | `sonnet` |  33 s |           326 |       0 |      0 | PASS    | additive conflict auto-resolved                          |
| jj   | small | `haiku`  | 112 s |           515 |       0 |      0 | PASS    | version tie-break resolved 1.5.3 > 1.5.1 (conflict 55 s) |
| git  | large | `opus`   | 128 s |           552 |       1 |      1 | PASS    | quoted-cd guard mis-detect, corrected to unquoted cd     |
| git  | mid   | `sonnet` |  29 s |           260 |       0 |      0 | PASS    | additive conflict auto-resolved                          |
| git  | small | `haiku`  |  54 s |            57 |       0 |      0 | PASS    | helper completed without manual stop                     |

#### Integration deltas

| metric             |    jj |   git | git advantage             |
| ------------------ | ----: | ----: | ------------------------- |
| Wall max           | 112 s | 128 s | jj 16 s faster            |
| Serialized total   | 248 s | 211 s | git 37 s faster           |
| Mean total         |  83 s |  70 s | git 13 s faster per agent |
| Output tokens      | 2,022 |   869 | git 1,153 fewer tokens    |
| Mean output tokens |   674 |   290 | git 384 fewer per run     |

#### Gap by model tier

| tier              | jj total | git total | jj output tokens | git output tokens | gap                          |
| ----------------- | -------: | --------: | ---------------: | ----------------: | ---------------------------- |
| `large` / `opus`  |    103 s |     128 s |            1,181 |               552 | jj faster, git fewer tokens  |
| `mid` / `sonnet`  |     33 s |      29 s |              326 |               260 | tie; git slightly leaner     |
| `small` / `haiku` |    112 s |      54 s |              515 |                57 | git edge, but jj still clean |

Unlike the GPT run, no Claude tier produced a token or time blowup. The largest
single cost was opus-on-Git's guard retry (128 s); the largest jj cost was
haiku's 55 s on the deliberate version tie-break, which it resolved correctly.

### Start-Isolation Results

| mode | tier | model    | total | output tokens | retries | stalls | isolation | name | quality |
| ---- | ---- | -------- | ----: | ------------: | ------: | -----: | --------- | ---- | ------- |
| jj   | mid  | `sonnet` | 111 s |           944 |       0 |      0 | PASS      | PASS | PASS    |
| git  | mid  | `sonnet` |  96 s |           412 |       0 |      0 | PASS      | PASS | PASS    |

Both Claude start agents isolated before editing, named their working copy
`claude-streaming-export` (prefix `claude` ⇒ NAME_OK pass in **both** modes,
closing the gap where GPT's jj arm failed naming), landed the change on `main`,
and cleaned up — with no retries or stalls.

### Observations (Claude)

- **No small-tier cliff.** The cell that decided the GPT benchmark (small on jj)
  was a clean, cheap pass for haiku. The `vcs` jj helper path plus haiku's
  one-pass tie-break resolution kept it to 112 s / 515 tokens.
- **jj and Git are close for Claude.** Git is marginally faster/leaner on the
  serialized integration, but jj won wall-clock here because the slow cell was an
  opus/Git guard retry, not a jj-lifecycle cost. There is no Claude analogue to
  GPT's jj penalty.
- **The cwd guard is the shared friction.** Both opus cells (and, in the GPT run,
  multiple cells) lost time to the guard requiring an unquoted leading
  `cd <abs> &&`. opus on jj also found the guard refused VCS _reads_ from the
  default workspace after its own workspace was retired, forcing a non-VCS read of
  `.git/refs/heads/main` to verify publication. This is the clearest skill/guard
  improvement target surfaced by the run.

---

## Run C — Cursor (Composer 2.5)

**Models:** `large=mid=small=composer-2.5-fast` (single model; three serialized
integration slots stand in for the tier ladder). Rounds 701 (jj medium), 702 (git
medium), 703 (jj start), 704 (git start). Tokens read per-agent from Cursor
subagent transcript JSONL (assistant-output characters ÷ 4 — Cursor does not emit
`usage.output_tokens` in subagent transcripts); quality/isolation/naming from the
oracles.

### Headline

| Metric                                      | Jujutsu workspaces | Git worktrees   |
| ------------------------------------------- | ------------------ | --------------- |
| Integration oracle                          | **PASS**           | **PASS**        |
| Integration agents passing                  | **3 / 3**          | **3 / 3**       |
| Integration wall max                        | 460 s              | **27 s**        |
| Integration serialized total                | 892 s              | **59 s**        |
| Integration mean output tokens (est.)       | 3,193              | **631**         |
| Start-isolation oracle                      | **PASS**           | **PASS**        |
| Start-isolation total                       | 174 s              | **26 s**        |
| Start-isolation output tokens (est.)        | 1,825              | 2,220           |
| Start-isolation naming (`<ide>-<work>`)     | **FAIL**           | **FAIL**        |
| Hygiene (`stale` / `orph` / `def failures`) | **0 / 0 / 0**      | **0 / 0 / n/a** |

For Composer, Git worktrees had a decisive speed and token advantage on
integration — the largest jj-vs-git gap of any family in this benchmark. jj still
passed every oracle; the cost was orchestration friction (workspace recreation,
session-start hangs, YAML tie-break time) not incorrect merges.

### Scoreboard

```text
== BY ROUND (trend: lower is better; delta vs previous round) ==
round diff      n  pass%  wall(max)     d  mean_tot  conf(max)     d  mean_cnf  mean_tok stale  orph  def  iso  name  retr stall
--------------------------------------------------------------------------------------------------------------------------------------
701   medium    3   100%        460              297        240              80      3193     0     0    0    -     -     0     3
702   medium    3   100%         27  -433        20          0  -240         0       631     0     0    -    -     -     0     0
703   easy      1   100%        174  +147       174          0    +0         0      1825     0     0    -    0     1     0     1
704   easy      1   100%         26  -148        26          0    +0         0      2220     0     0    -    0     1     0     1

== BY MODEL TIER ==
tier      n  pass%  mean_tot  conf(max)  mean_cnf  mean_tok stale  orph  def  iso  name  retr stall
---------------------------------------------------------------------------------------------------
large     2   100%        87          0         0      1317     0     0    0    -     -     0     0
mid       4   100%       169          0        60      2591     0     0    0    0     2     0     4
small     2   100%       150        240       120      2030     0     0    0    -     -     0     1

== PASS-RATE MATRIX (rows = tier, cols = difficulty) ==
tier\diff       easy    medium
------------------------------
large              -      100%
mid             100%      100%
small              -      100%
```

`conf(max)` is non-zero only for the small-tier jj cell (240 s): the deliberate
`config.yaml` version tie-break. The mid-tier jj cell (460 s) recorded
`conflict_seconds=0` in its self-report because `integrate.sh` auto-resolved
additive files before the agent timed the YAML span; wall-clock still reflects
the workspace-recreation stall.

### Integration Results

| mode | tier  | model               | total | output tokens (est.) | retries | stalls | quality | note                                                      |
| ---- | ----- | ------------------- | ----: | -------------------: | ------: | -----: | ------- | --------------------------------------------------------- |
| jj   | large | `composer-2.5-fast` | 159 s |                2,172 |       0 |      0 | PASS    | fast-forward integrate; no conflict stop                  |
| jj   | mid   | `composer-2.5-fast` | 460 s |                4,105 |       0 |      2 | PASS    | ws-agent-2 retired by agent 1; recreation + session hangs |
| jj   | small | `composer-2.5-fast` | 273 s |                3,303 |       0 |      1 | PASS    | YAML tie-break 1.5.3 > 1.5.1 (conflict 240 s)             |
| git  | large | `composer-2.5-fast` |  15 s |                  462 |       0 |      0 | PASS    | clean integrate.sh; pushed origin/main                    |
| git  | mid   | `composer-2.5-fast` |  17 s |                  675 |       0 |      0 | PASS    | additive conflicts auto-resolved                          |
| git  | small | `composer-2.5-fast` |  27 s |                  756 |       0 |      0 | PASS    | helper completed without manual stop                      |

#### Integration deltas

| metric             |    jj |  git | git advantage              |
| ------------------ | ----: | ---: | -------------------------- |
| Wall max           | 460 s | 27 s | git 433 s faster           |
| Serialized total   | 892 s | 59 s | git 833 s faster           |
| Mean total         | 297 s | 20 s | git 277 s faster per agent |
| Output tokens      | 9,580 | 1893 | git 7,687 fewer (est.)     |
| Mean output tokens | 3,193 |  631 | git 2,562 fewer per run    |

#### Gap by model tier

| tier                   | jj total | git total | jj output tokens (est.) | git output tokens (est.) | gap                              |
| ---------------------- | -------: | --------: | ----------------------: | -----------------------: | -------------------------------- |
| `large` / composer-2.5 |    159 s |      15 s |                   2,172 |                      462 | git much faster and leaner       |
| `mid` / composer-2.5   |    460 s |      17 s |                   4,105 |                      675 | jj dominated by lifecycle stall  |
| `small` / composer-2.5 |    273 s |      27 s |                   3,303 |                      756 | git edge; jj YAML tie-break cost |

Unlike GPT's small-tier jj blowup, Composer's small tier resolved correctly — but
the mid-tier jj agent paid the price when the serialized chain retired workspaces
early. Git's advantage here is the largest cross-family gap in the benchmark.

### Start-Isolation Results

| mode | tier | model               | total | output tokens (est.) | retries | stalls | isolation | name | quality |
| ---- | ---- | ------------------- | ----: | -------------------: | ------: | -----: | --------- | ---- | ------- |
| jj   | mid  | `composer-2.5-fast` | 174 s |                1,825 |       0 |      1 | PASS      | FAIL | PASS    |
| git  | mid  | `composer-2.5-fast` |  26 s |                2,220 |       0 |      1 | PASS      | FAIL | PASS    |

Both Composer start agents isolated before editing and landed the requested
change. Git was 148 s faster. Naming failed in both modes: jj captured
`composer-pending-*` (pending workspace slug) rather than `cursor-streaming-export`;
git used `composer-agent-1` instead of a `<ide>-<work>` work slug.

### Observations (Composer)

- **Git wins decisively on integration cost** — 27 s vs 460 s wall max and ~5×
  fewer estimated output tokens. This is the strongest Git advantage measured
  across GPT, Claude, and Composer in this file.
- **Quality and hygiene are clean** — every integration and start round passed
  the objective oracle with zero stale refs, orphan workspaces, or default failures.
- **Naming matches GPT, not Claude** — both start arms failed `NAME_OK`; the
  `composer-*` prefix is recognized but the work slug did not follow `<ide>-<work>`.
- **jj friction is workflow/orchestration, not merge correctness** — workspace
  retirement between serialized agents and guard-blocked default writes dominated
  jj time; the YAML tie-break on the small tier was the only real conflict-resolution
  work.

## Run A — GPT (Codex Desktop)

In this Codex/GPT run, Git worktrees showed the practical advantage. Both modes
produced correct integrated `main` results, but Git used much less wall-clock and
many fewer output tokens on the medium integration benchmark. Jujutsu did not
provide a token or speed advantage here.

The result is not "jj is bad" in general. The data says that, for this current
`vcs` skill plus Codex Desktop guard environment, jj's extra lifecycle and guard
friction can dominate its helper advantages, especially for the small-tier model.
(Run B shows that with Claude, the same small-tier jj cell is cheap — so the
conclusion below is Codex-specific.)

### Headline (GPT)

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

### Method

The integration rounds used `new-sandbox.sh --difficulty medium --agents 3` in
both modes. Agents ran serially within each mode: agent 1 landed first, then
agent 2 integrated over agent 1, then agent 3 integrated over both earlier
agents. Each agent received only the `vcs` skill, its generated brief, and its
assigned workspace path.

The start rounds used `new-sandbox.sh --task start --start-from main` in both
modes with one mid-tier agent. These measure the front of the workflow: whether
the agent isolates into its own jj workspace or Git worktree before editing.

Token counts came from Codex transcript JSONL `token_count` events, using the
final per-agent `output_tokens` total.

Quality was checked with `check-quality.sh` (integration correctness, stale refs,
default readiness, orphan workspace cleanup) and `check-isolation.sh` (start-round
isolation and naming).

### Scoreboard (GPT)

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

### Integration Results (GPT)

| mode | tier  | model          | total | output tokens | retries | quality | note                                  |
| ---- | ----- | -------------- | ----: | ------------: | ------: | ------- | ------------------------------------- |
| jj   | large | `gpt-5.5`      |  40 s |         1,482 |       0 | PASS    | first landing, no conflict stop       |
| jj   | mid   | `gpt-5.4`      |  55 s |         2,718 |       0 | PASS    | additive conflict auto-resolved       |
| jj   | small | `gpt-5.4-mini` | 337 s |        29,095 |       1 | PASS    | YAML scalar conflict plus guard retry |
| git  | large | `gpt-5.5`      |  40 s |         1,633 |       0 | PASS    | first landing, no conflict stop       |
| git  | mid   | `gpt-5.4`      |  48 s |         2,317 |       0 | PASS    | additive conflict auto-resolved       |
| git  | small | `gpt-5.4-mini` |  39 s |         3,158 |       0 | PASS    | helper completed without manual stop  |

#### Integration deltas (GPT)

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

#### Gap by model tier (GPT)

| tier                     | jj total | git total | jj output tokens | git output tokens | gap                           |
| ------------------------ | -------: | --------: | ---------------: | ----------------: | ----------------------------- |
| `large` / `gpt-5.5`      |     40 s |      40 s |            1,482 |             1,633 | tie; jj slightly fewer tokens |
| `mid` / `gpt-5.4`        |     55 s |      48 s |            2,718 |             2,317 | small Git edge                |
| `small` / `gpt-5.4-mini` |    337 s |      39 s |           29,095 |             3,158 | huge Git edge                 |

The jj-vs-Git gap was much smaller with more powerful models. The `large` tier
was effectively tied, the `mid` tier had only a modest Git edge, and the
headline Git advantage came mostly from the small-tier jj run.

### Start-Isolation Results (GPT)

| mode | tier | model     | total | output tokens | retries | stalls | isolation | name | quality |
| ---- | ---- | --------- | ----: | ------------: | ------: | -----: | --------- | ---- | ------- |
| jj   | mid  | `gpt-5.4` | 135 s |         5,189 |       3 |      1 | PASS      | FAIL | PASS    |
| git  | mid  | `gpt-5.4` | 111 s |         5,260 |       1 |      0 | PASS      | PASS | PASS    |

Both agents correctly isolated before editing and landed the requested change.
Git was 24 s faster. Token usage was effectively tied, but jj had more retries
and missed the naming convention: the harness saw `agent-pending-*` rather than a
`codex-*` workspace/bookmark name. Git created a `codex-pending-*` worktree/branch
and passed naming.

---

## Conclusion

Across all three families the `vcs` skill is **correct and hygienic in both modes,
at every tier** — every integration and start round passed the objective oracle
with clean stale-ref, orphan, and default-workspace hygiene. The interesting story
is cost, and it differs by family:

- **GPT / Codex:** Git worktrees had the practical speed/token advantage, driven
  almost entirely by a small-tier jj outlier (337 s / 29,095 tokens). With
  powerful models the gap nearly vanished. The data did **not** support switching
  to jj for token/speed efficiency _in Codex Desktop_.
- **Claude / Claude Code:** jj and Git are close and both cheap; the small-tier
  jj cell that decided the GPT run was a clean, low-token pass for haiku, and
  Claude also closed the jj naming gap. There is no Claude penalty for jj — the
  only notable slowdown was a large-tier Git cell hitting the cwd guard.
- **Cursor / Composer 2.5:** Git worktrees had the **largest** speed/token
  advantage of any family (27 s vs 460 s wall max; ~631 vs ~3,193 mean est.
  tokens). jj passed every oracle but mid-tier serialized integration paid a
  heavy workspace-lifecycle tax. Naming failed like GPT, not Claude.

So "Git is faster" is **not universal** — Claude nearly ties — but it holds for
Codex (small-tier jj outlier) and **strongly** for Composer (mid-tier lifecycle
stall). The improvement targets all families agree on are the **`vcs-check` cwd
guard** (unquoted-leading-`cd`, post-retirement read refusal) and clearer
**`<ide>-<work>` naming** guidance so Cursor/GPT agents stop using
`composer-pending-*` / `agent-pending-*` slugs.

### Next benchmark

- Add the `hard` difficulty and concurrent (not just serialized) integration for
  both families, with transcript token capture — that is where jj's
  conflict-preview and workspace semantics have the most room to pay off.
- Cross more tiers into the start rounds (currently mid only).
- Treat the cwd-guard friction as a `vcs`/guard fix and re-measure, since it is
  the dominant non-VCS cost in both families.

---

## Limitations

- Single benchmark run per family, not multiple consecutive rounds.
- Composer tokens are **estimated** (assistant chars ÷ 4); Cursor subagent
  transcripts lack vendor `usage` fields.
- Medium integration plus easy start only; no hard or concurrent stress round.
- Cross-vendor **output-token** comparison is indicative, not exact (different
  tokenizers and transcript accounting per vendor); trust within-family per-tier
  trends and the pass/fail oracle for cross-family claims.
- Host guard behavior (Codex Desktop / Claude Code cwd guard) was part of the
  measured workflow and may not match another agent host.
- `conflict_seconds` was unreliable in the GPT run (helper auto-resolution and a
  missed conflict-start timestamp); in the Claude run only one cell recorded a
  real conflict span.
