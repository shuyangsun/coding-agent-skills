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
  and concurrent rounds**. Caveat: this counts *output* tokens only — it reflects
  agent effort, not `vcs`'s own size (the input cost of re-reading a bloated skill
  isn't captured here; keep `vcs` compact for that, per [LOOP.md](LOOP.md)).

**Hygiene — stale refs (must be 0):**

- **Surviving merged `agent-*` refs** — after a clean integration each agent's
  `agent-K` branch/bookmark is merged into `main` and redundant; `vcs` must have
  the agent delete it (jj `bookmark delete`; git detach + `branch -d`) **unless it
  backs an open remote PR**, in which case it is kept on purpose. `check-quality.sh`
  reports `STALE_REFS=N` (and `STALE_LIST=` naming them) — the count of merged refs
  left behind that should have been deleted, *excluding* the PR-backed allowlist;
  it also fails the hygiene line if a PR-backed ref was wrongly deleted. This is
  reported **separately** from the correctness verdict so resolution quality and
  repo hygiene stay distinguishable, and it is attributed **per agent** so the
  by-tier `stale` column shows whether a tier (e.g. `small`) forgets to clean up.

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
4. `record-metrics.sh` one row per agent (with `--tier`, `--difficulty`, plus
   `--tokens` and `--stale`); `scoreboard.sh` to compare rounds and tiers.

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
agent for whether the result is actually correct. **Token usage and stale-ref
count are deliberately absent from this report** — both are measured by the
orchestrator (`budget.spent()` delta) and the oracle (`check-quality.sh`), because
an agent can neither count its own tokens nor be trusted to grade its own cleanup.

## Recording and reading the scoreboard

```sh
# one row per agent per round — include tier, difficulty, tokens, and stale count
bash <skill-dir>/scripts/record-metrics.sh --round 1 --agent agent-1 --mode jj \
  --difficulty hard --tier large --env local-cli \
  --total 180 --conflict 55 --tokens 24000 --stale 0 --retries 1 --stalls 0 \
  --quality pass

# compare all rounds AND tiers
bash <skill-dir>/scripts/scoreboard.sh
```

`scoreboard.sh` prints three views:

1. **By round** — agent count, pass%, `wall(max)` and `mean_tot`, `conflict(max)`
   and `mean_cnf`, `mean_tok`, `stale`, retries/stalls, with the round-over-round
   delta on the two headline costs. **Negative delta = faster = the direction you
   want; `stale` should be 0.**
2. **By model tier** — pass% and the same costs (incl. `mean_tok` and `stale`) per
   tier, so you can see whether `vcs` works for `small` and `mid` or only `large`,
   and whether a tier forgets to clean up its branch.
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
7. **Token usage is low and stable (or trending down)**: `mean_tok` doesn't
   regress as `vcs` changes — a revision that resolves correctly but balloons the
   tokens an agent burns hasn't really improved the skill. Watch it per tier
   (smaller models thrash most when guidance is unclear).
8. **No tier left behind**: the by-tier view and the difficulty×tier matrix show
   `small` and `mid` clearing the bar too — not just `large` — on quality, speed,
   hygiene, **and** tokens. A revision that only helps the largest model has not
   met the bar.

A revision that speeds things up but breaks a quality dimension, leaves stale
refs, balloons tokens, regresses a tier, or doesn't move the numbers fails the
bar — revert it and keep `vcs` smaller. Don't declare success on a single good
round.
