# Metrics and the exit bar

Speed and quality are the primary objectives, and **conflict-resolution time is
the single most important cost** — the whole point of the loop is that many
agents handle parallel work, and especially merge conflicts, fast _without_
sacrificing correctness. Record these every round, compare across rounds **and
across model tiers**, and judge each `vcs` revision by whether it moves them.

Crucially, we measure the resolution **immediately after the merge/rebase**. The
briefs forbid any post-merge coding, testing, or "make it work" effort, so these
numbers reflect `vcs`'s conflict etiquette alone, not the agent's coding ability.

## What to measure

**Speed (lower is better):**

- **Batch wall-clock** — when the whole batch of sub-agents has finished
  integrating; the slowest agent determines it. `scoreboard.sh` reports it as
  `wall(max)` = the max per-agent total in the round.
- **Per-agent total** — spawn → final integration, per agent. The orchestrator
  times this directly (it controls spawn and sees the return).
- **Conflict-resolution time** — within an agent's run, the span from first
  detecting a conflict to having it resolved and published. **The headline cost.**
  Self-reported by the agent (only it knows when it hit/cleared the conflict).

**Friction (lower is better):**

- **Retries / stalls / round-trips** — how many times the agent re-tried a VCS
  step, got stuck, or had to re-read `vcs` because a conflict or workflow step was
  unclear. A proxy for where `vcs` is ambiguous — and where smaller tiers suffer.

**Efficiency — token usage (lower is better):**

- **Output tokens per agent run** — how many output tokens the sub-agent
  generated getting from spawn to finished integration (reasoning + tool calls +
  the final report). A clearer, better-shaped `vcs` lets an agent finish with less
  thrash (fewer tool calls, less re-reasoning), so this is a real efficiency
  signal alongside wall-clock. It is read **exactly and per-agent** from each
  agent's transcript JSONL (`_score.py` sums `output_tokens` across the run and
  maps it to the agent by the `ws-agent-K` path in its prompt) — **never asked of
  the agent** (it can't count its own tokens) and **not** taken from
  `budget.spent()`, whose shared, batched counter mis-attributes per agent (a
  probe measured 1578 vs the transcript's true 4 for the same call). Because the
  source is the per-agent transcript, attribution is **exact in both serialized
  and concurrent rounds**. Caveat: this counts _output_ tokens only — it reflects
  agent effort, not `vcs`'s own size (the input cost of re-reading a bloated skill
  isn't captured here; keep `vcs` compact for that, per [LOOP.md](LOOP.md)).

**Hygiene — stale refs (must be 0):**

- **Surviving merged `agent-*` refs** — after a clean integration each agent's
  `agent-K` branch/bookmark is merged into `main` and redundant; `vcs` must have
  the agent delete it (jj `bookmark delete`; git detach + `branch -d`) **unless it
  backs an open remote PR**, in which case it is kept on purpose. `check-quality.sh`
  reports `STALE_REFS=N` (and `STALE_LIST=` naming them) — the count of merged refs
  left behind that should have been deleted, _excluding_ the PR-backed allowlist;
  it also fails the hygiene line if a PR-backed ref was wrongly deleted. This is
  reported **separately** from the correctness verdict so resolution quality and
  repo hygiene stay distinguishable, and it is attributed **per agent** so the
  by-tier `stale` column shows whether a tier (e.g. `small`) forgets to clean up.

**Session-start isolation — `ISOLATED` (start rounds only; must be pass):**

- **Did the agent isolate before doing new work?** A `--task start` round drops an
  agent into a _shared_ repo and asks it to author one tiny change and land it on
  `main`. For co-located agents on one machine not to trample each other, the
  agent must do its work in its **own** worktree (git) / workspace (jj) on its own
  branch/bookmark — not in the shared primary checkout. `check-isolation.sh`
  reports `ISOLATED=pass/fail` (plus `ISO_FS` / `OVER_ISOLATE` detail), measured
  from **durable** signals that survive the agent's own cleanup: git's primary
  `HEAD` reflog line-count (unchanged ⇒ the agent worked elsewhere) and jj's
  append-only op-log `add workspace` entries. Two arms: `--start-from main` (the
  agent must isolate) and `--start-from worktree` (it was already given an
  isolated area, so it must **not** create a redundant nested one — the
  don't-double-isolate conditional). Reported **separately** from correctness and
  hygiene — "did the work, but in the shared checkout" is an isolation miss, not a
  correctness one — and **separately** from `check-quality.sh`, which still scores
  that the change and the branch cleanup landed right on a start round. This is
  the START bookend to the hygiene metric's FINISH: isolate cleanly, then clean up
  cleanly.

**Quality (must hold or improve):** the objective `check-quality.sh` verdict —
mode integrity, no markers, no unresolved conflict, no lost work, and the
**resolution oracle** (union exactly-once, correct tie-break value, structured
files parse, untouched files unchanged). Quality is a gate: a speed win that
fails any quality dimension is **not** an improvement.

**Dimensions to slice by:** every row carries its **model tier** (large / mid /
small) and **difficulty** (easy / medium / hard). The whole point of recording
them is that a `vcs` revision must work _across_ tiers and difficulties, not just
for the largest model on the easiest scenario.

## How capture flows

1. Orchestrator notes each sub-agent's spawn time and return time → per-agent
   total and batch wall-clock, and the tier it spawned the agent at. The
   **output-token** metric is read afterward from each agent's transcript JSONL
   (`_score.py <result.json> <base> <transcript-dir>`), not self-reported.
2. Each sub-agent returns the **structured report** below → conflict time,
   retries, stalls, and the effectiveness narrative.
3. `check-quality.sh <round-dir>` → the correctness verdict (pass/fail + reasons)
   **plus** the hygiene line `STALE_REFS=N` / `STALE_LIST=…` (reported separately).
   For a `--task start` round, also `check-isolation.sh <round-dir>` → the
   `ISOLATED=pass/fail` session-start verdict (reported separately again).
4. `record-metrics.sh` one row per agent (with `--tier`, `--difficulty`, plus
   `--tokens` and `--stale`, and `--isolate` on start rounds); `scoreboard.sh` to
   compare rounds and tiers.

## Structured sub-agent report (paste this into each sub-agent prompt)

```text
=== VCS RUN REPORT ===
mode_detected:   <jj | git>            # what you concluded the repo uses, and how
tier:            <large | mid | small> # the capability tier you are standing in for
total_seconds:   <int>                 # start of your work to finished integration
conflict_seconds:<int>                 # time from first conflict to fully resolved+published (0 if none)
conflicts_hit:   <int>
retries:         <int>                 # VCS steps you had to repeat
stalls:          <int>                 # times you were stuck / had to re-read vcs
clear:           <what in `vcs` was clear and worked>
ambiguous:       <what was unclear, missing, or slow in `vcs`>
mishandled:      <any conflict you suspect you resolved wrong, or "none">
=== END ===
```

The agent's self-reported fields are inputs; trust `check-quality.sh` over the
agent for whether the result is actually correct. **Token usage, stale-ref count,
and the isolation verdict are deliberately absent from this report** — they're
measured by the orchestrator (transcript output tokens) and the oracles
(`check-quality.sh`, `check-isolation.sh`), because an agent can neither count its
own tokens nor be trusted to grade its own cleanup or isolation. (`tier` appears
in the template for **manual** runs, where you fill it from the cell you're
standing in; the bundled workflow runners instead set it from the orchestrator and
omit it from their `REPORT_SCHEMA`, so a runner-driven agent never reports it.)

## Recording and reading the scoreboard

```sh
# one row per agent per round — include tier, difficulty, tokens, and stale count
bash <skill-dir>/scripts/record-metrics.sh --round 1 --agent agent-1 --mode jj \
  --difficulty hard --tier large --env local-cli \
  --total 180 --conflict 55 --tokens 24000 --stale 0 --retries 1 --stalls 0 \
  --quality pass

# a START round adds the session-start isolation verdict (single agent)
bash <skill-dir>/scripts/record-metrics.sh --round 9 --agent agent-1 --mode git \
  --difficulty easy --tier small --env local-cli \
  --total 40 --tokens 2600 --stale 0 --isolate pass --quality pass

# compare all rounds AND tiers
bash <skill-dir>/scripts/scoreboard.sh
```

`scoreboard.sh` prints three views:

1. **By round** — agent count, pass%, `wall(max)` and `mean_tot`, `conflict(max)`
   and `mean_cnf`, `mean_tok`, `stale`, `iso`, retries/stalls, with the
   round-over-round delta on the two headline costs. **Negative delta = faster =
   the direction you want; `stale` and `iso` should be 0** (`iso` shows `-` on
   integration rounds, where isolation isn't measured).
2. **By model tier** — pass% and the same costs (incl. `mean_tok`, `stale`, and
   `iso`) per tier, so you can see whether `vcs` works for `small` and `mid` or
   only `large`, and whether a tier forgets to isolate or to clean up its branch.
3. **Difficulty × tier pass-rate matrix** — pinpoints exactly where things break
   (e.g. `small` passes `easy` but fails `hard`), which tells you what to fix next.

## The exit bar (definition of done)

Stop iterating only when **all** of these hold across **multiple consecutive
rounds** (not one lucky run), in **both modes**, across the **difficulty ladder**,
and across **model tiers**:

1. **Quality**: every round PASSes `check-quality.sh` — mode integrity, no
   markers, no unresolved conflict, no lost work, and the resolution oracle green
   (union exactly-once, correct tie-break, files parse, nothing extra).
2. **Mode detection** holds before _and_ after work: every agent detected its
   mode correctly and never crossed into the wrong tool.
3. **Conflict-resolution time is low and trending down** (or stable at a floor)
   across rounds — this is the primary number.
4. **Batch wall-clock is low and trending down** (or stable at a floor).
5. **Friction is low**: few retries/stalls; conflicts resolved cleanly on the
   first attempt rather than after thrashing.
6. **Branch/bookmark hygiene is clean**: `stale` is **0** every round, in both
   modes and every tier — each agent deleted its merged `agent-K` ref, and any
   PR-backed ref was correctly kept. A merged ref left behind is a hygiene failure
   even when the resolution was perfect.
7. **Session-start isolation holds** (start rounds): every `--task start` agent
   `ISOLATED=pass` — it carved out its own worktree/workspace before doing new
   work (`--start-from main`) and did **not** create a redundant nested one when
   already isolated (`--start-from worktree`), in both modes and every tier. The
   `iso` column is **0** (no failures). This is the front bookend of "co-located
   agents don't interfere"; the hygiene metric is the back one.
8. **Token usage is low and stable (or trending down)**: `mean_tok` doesn't
   regress as `vcs` changes — a revision that resolves correctly but balloons the
   tokens an agent burns hasn't really improved the skill. Watch it per tier
   (smaller models thrash most when guidance is unclear).
9. **No tier left behind**: the by-tier view and the difficulty×tier matrix show
   `small` and `mid` clearing the bar too — not just `large` — on quality, speed,
   hygiene, **and** tokens. A revision that only helps the largest model has not
   met the bar.

A revision that speeds things up but breaks a quality dimension, leaves stale
refs, balloons tokens, regresses a tier, or doesn't move the numbers fails the
bar — revert it and keep `vcs` smaller. Don't declare success on a single good
round.
