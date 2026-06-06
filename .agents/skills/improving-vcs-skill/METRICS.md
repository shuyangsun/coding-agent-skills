# Metrics and the exit bar

Speed and quality are the primary objectives, and **conflict-resolution time is
the single most important cost** — the whole point of the loop is that many
agents handle parallel work, and especially merge conflicts, fast _without_
sacrificing correctness. Record these every round, compare across rounds, and
judge each `vcs` revision by whether it moves them.

## What to measure

**Speed (lower is better):**

- **Batch wall-clock** — when the whole batch of sub-agents has finished and
  integrated all its work; the slowest agent determines it. `scoreboard.sh`
  reports it as `wall(max)` = the max per-agent total in the round.
- **Per-agent total** — spawn → final integration, per agent. The orchestrator
  times this directly (it controls spawn and sees the return).
- **Conflict-resolution time** — within an agent's run, the span from first
  detecting a conflict to having it resolved and verified. **The headline cost.**
  Self-reported by the agent (only it knows when it hit/cleared the conflict).

**Friction (lower is better):**

- **Retries / stalls / round-trips** — how many times the agent re-tried a VCS
  step, got stuck, or had to re-read `vcs` because a conflict or workflow step was
  unclear. A proxy for where `vcs` is ambiguous.

**Quality (must hold or improve):** the four objective `check-quality.sh`
dimensions — mode integrity, no markers, no lost work, no unresolved conflict —
plus a human read of **history cleanliness** and whether same-line conflicts were
resolved _correctly_ (not just silenced). Quality is a gate: a speed win that
fails any quality dimension is **not** an improvement.

## How capture flows

1. Orchestrator notes each sub-agent's spawn time and return time → per-agent
   total and batch wall-clock.
2. Each sub-agent returns the **structured report** below → conflict time,
   retries, stalls, and the effectiveness narrative.
3. `check-quality.sh <round-dir>` → the quality verdict (pass/fail + reasons).
4. `record-metrics.sh` one row per agent; `scoreboard.sh` to compare rounds.

## Structured sub-agent report (paste this into each sub-agent prompt)

```text
=== VCS RUN REPORT ===
mode_detected:   <jj | git>            # what you concluded the repo uses, and how
total_seconds:   <int>                 # start of your work to finished integration
conflict_seconds:<int>                 # time from first conflict to fully resolved+verified (0 if none)
conflicts_hit:   <int>
retries:         <int>                 # VCS steps you had to repeat
stalls:          <int>                 # times you were stuck / had to re-read vcs
clear:           <what in `vcs` was clear and worked>
ambiguous:       <what was unclear, missing, or slow in `vcs`>
mishandled:      <any conflict you suspect you resolved wrong, or "none">
=== END ===
```

The agent's `mode_detected` and `conflict_*` numbers are self-reported; trust
`check-quality.sh` over the agent for whether the result is actually correct.

## Recording and reading the scoreboard

```sh
# one row per agent per round
bash <skill-dir>/scripts/record-metrics.sh --round 1 --agent agent-1 --mode jj \
  --env local-cli --total 180 --conflict 55 --retries 1 --stalls 0 --quality pass

# compare all rounds
bash <skill-dir>/scripts/scoreboard.sh
```

`scoreboard.sh` prints, per round: agent count, pass rate, `wall(max)` and
`mean_tot`, `conflict(max)` and `mean_cnf`, total retries and stalls — with the
round-over-round delta on the two headline costs (`wall(max)`, `conflict(max)`).
**Negative delta = faster = the direction you want.** Use it to confirm a `vcs`
revision actually helped; if a change didn't move these, revert it.

## The exit bar (definition of done)

Stop iterating only when **all** of these hold across **multiple consecutive
rounds** (not one lucky run), in **both** modes:

1. **Quality**: every round PASSes `check-quality.sh` — mode integrity intact,
   no markers, no lost work, no unresolved conflicts — and same-line conflicts
   are resolved correctly on inspection.
2. **Mode detection** holds before _and_ after work: every agent detected its
   mode correctly and never crossed into the wrong tool.
3. **Conflict-resolution time is low and trending down** (or stable at a floor)
   across rounds — this is the primary number.
4. **Batch wall-clock is low and trending down** (or stable at a floor).
5. **Friction is low**: few retries/stalls; conflicts resolved cleanly on the
   first attempt rather than after thrashing.

A revision that speeds things up but breaks a quality dimension, or that doesn't
move the numbers, fails the bar — revert it and keep `vcs` smaller. Don't declare
success on a single good round.
