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
   total and batch wall-clock, and the tier it spawned the agent at.
2. Each sub-agent returns the **structured report** below → conflict time,
   retries, stalls, and the effectiveness narrative.
3. `check-quality.sh <round-dir>` → the quality verdict (pass/fail + reasons).
4. `record-metrics.sh` one row per agent (with `--tier` and `--difficulty`);
   `scoreboard.sh` to compare rounds and tiers.

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
agent for whether the result is actually correct.

## Recording and reading the scoreboard

```sh
# one row per agent per round — include tier and difficulty
bash <skill-dir>/scripts/record-metrics.sh --round 1 --agent agent-1 --mode jj \
  --difficulty hard --tier large --env local-cli \
  --total 180 --conflict 55 --retries 1 --stalls 0 --quality pass

# compare all rounds AND tiers
bash <skill-dir>/scripts/scoreboard.sh
```

`scoreboard.sh` prints three views:

1. **By round** — agent count, pass%, `wall(max)` and `mean_tot`, `conflict(max)`
   and `mean_cnf`, retries/stalls, with the round-over-round delta on the two
   headline costs. **Negative delta = faster = the direction you want.**
2. **By model tier** — pass% and the same costs per tier, so you can see whether
   `vcs` works for `small` and `mid` or only `large`.
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
6. **No tier left behind**: the by-tier view and the difficulty×tier matrix show
   `small` and `mid` clearing the bar too — not just `large`. A revision that
   only helps the largest model has not met the bar.

A revision that speeds things up but breaks a quality dimension, regresses a
tier, or doesn't move the numbers fails the bar — revert it and keep `vcs`
smaller. Don't declare success on a single good round.
