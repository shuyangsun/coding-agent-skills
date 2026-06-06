# Kick-start prompt: testing-vcs-skill

You are working in the `coding-agent-skills` repo. Your job has two parts,
in order: first author a brand-new skill called `testing-vcs-skill`, then
use that skill to validate and harden the existing `vcs` skill, iterating
until it measurably works. Treat building the harness as the means and
hardening `vcs` as the end.

Before anything else, read `AGENTS.md` (repo layout, plus the hard rule
that skills stay repo-agnostic) and the current `vcs` skill at
`skills/vcs/SKILL.md` and `skills/vcs/COMMITS.md`. That is your starting
point: `vcs` today covers commit-message formatting only and must grow.

Why this exists:

- I'm building a fully agentic, multi-session development workflow —
  multiple coding agents working the same repository in parallel — plus a
  set of skills made purely for agentic development. Git wasn't designed
  for high-parallelism work; Jujutsu (`jj`) on a Git backend offers better
  rebase/merge ergonomics and clean per-agent isolation (e.g.
  `jj workspace add` gives each agent its own workspace in a shared
  directory). An open question I want this work to help answer: does `jj`
  plus a `vcs` skill actually beat Git + worktree for multi-agent work, or
  does the skill's overhead outweigh the benefit?
- The `vcs` skill needs to become a compact skill that teaches any agent
  the VCS mechanics and etiquette for committing, merging, rebasing, and
  publishing work cleanly during parallel, multi-session development —
  staying compact by pushing situation-specific detail into referenced
  markdown files.

The invariant to validate above everything else:

The `vcs` skill must make every agent (1) detect which VCS mode it is in
before it starts work, and (2) strictly abide by the correct workflow for
that mode both before and after doing work. There are two modes, and both
must be exercised:

- WITH `jj` (Jujutsu) on a Git backend — per-agent isolation via
  `jj workspace add` in a shared working directory.
- WITHOUT `jj`, Git only — e.g. Git + worktree; the path for environments
  where `jj` isn't available or wanted, notably fully-remote cloud sessions
  (e.g. GitHub-hosted ones).

Mode detection must be automatic and correct: an agent in a Git-only
checkout must never reach for `jj`, and an agent where `jj` is present must
use the `jj` workflow. Verify both branches actually hold under test.

What to build — `testing-vcs-skill`:

- Scope it tightly as a meta / authoring harness: it is used ONLY while
  authoring or changing the `vcs` skill, never during normal development.
  Say this plainly in the skill itself.
- It directs an orchestrating agent to spawn parallel sub-agents that each
  load the `vcs` skill and do realistic work, standing in for a range of
  agents (Claude Code, GPT Codex, Cursor, Antigravity, …) and environments
  (local-only CLI, localhost remote control, cloud remote control, GitHub
  Copilot in the cloud, …), across both VCS modes above. Where you can't
  literally run a given agent or environment, simulate it representatively
  and say so.
- Each sub-agent should see only what a real downstream agent would — the
  `vcs` skill, not this harness. Deliberately drive the sub-agents into
  overlapping, conflicting changes (same files, same lines), then have them
  commit / merge / rebase / publish using ONLY the `vcs` skill, with no
  out-of-band help. Each reports back on two things: the skill's
  effectiveness (what was clear, what was ambiguous, where it stalled,
  where conflicts were mishandled) and hard measurements — wall-clock time
  to finish the work end to end, how much of that went to detecting and
  resolving conflicts, the number of retries / stalls / round-trips a
  conflict caused, and the quality of the result (correct, no lost or
  clobbered work, conflicts genuinely resolved rather than silenced, clean
  history).
- The skill has the orchestrator aggregate those reports, revise the `vcs`
  skill, and loop: re-run, re-measure time and quality, revise again.

Then run it for real. Act as the orchestrator yourself: spawn the
sub-agents, gather their reports, and improve `vcs` (its `SKILL.md`,
referenced files, helper scripts, and `COMMITS.md`) between rounds. The
point isn't to write a harness that could work — it's to actually drive
`vcs` to the bar below.

What the closed loop optimizes for:

Speed and quality are the primary objectives — the whole point is that
sub-agents handle parallel work, and especially merge conflicts, fast and
efficiently without sacrificing correctness. Treat two things as
first-class metrics: the wall-clock time for the whole batch of sub-agents
to finish and integrate all their work (with conflict detection and
resolution time called out separately, since that is the key cost) and the
quality of the output. Record them every round, compare across rounds, and
judge each `vcs` revision by whether it moves the numbers — faster overall,
fewer stalls and retries, conflicts resolved cleanly on the first attempt —
not by how the skill reads. A change that doesn't improve the measurements,
or that buys speed with botched merges, is not an improvement; revert it.

Definition of done (the exit condition for the loop):

Multiple sub-agents can reliably (a) complete parallel work efficiently and
(b) resolve merge conflicts among themselves quickly and cleanly, using
only the `vcs` skill — in both VCS modes, with mode detection holding before
and after work. "Efficiently" and "quickly" are measured, not asserted:
time to completion and, above all, conflict-resolution time are low and
trending down across rounds while output quality holds or improves. Keep
iterating until that bar is met; don't declare success on one lucky run.

Use the testing to push `vcs` toward these properties, and verify they
hold rather than asserting them:

- A compact `SKILL.md` that delegates situation-specific detail to
  referenced markdown files.
- The strict "detect the mode, then abide before and after work" rule,
  front and center.
- Helper scripts for common session-start and session-end operations,
  using intuitive bookmark / branch names, that resolve the repo root
  themselves (Git → Jujutsu → current directory) and hardcode no paths or
  usernames (see `AGENTS.md`). They should respect the repo's existing
  formatting/hooks, which differ by mode (lefthook under Git, `jj fix`
  under Jujutsu — see `AGENTS.md`).
- A dedicated markdown on writing better commit messages —
  `skills/vcs/COMMITS.md` already exists, so refine it, don't duplicate it.

Repo conventions and guardrails:

- A skill's canonical home is `skills/<name>/SKILL.md`, symlinked into
  `.agents/skills/<name>` (e.g. `.agents/skills/<name> -> ../../skills/<name>`);
  `.claude/skills` already symlinks to `.agents/skills`. Add
  `testing-vcs-skill` this way — it must land under `.agents/skills/`, not
  `.claude/skills`.
- The `vcs` skill under test lives at `skills/vcs/` (symlinked at
  `.agents/skills/vcs`).
- A scratch Git repo exists at `../jj-setup-test`; you may use it for live
  testing if it helps, but it's not required. Whatever you do, isolate
  experiments (scratch repo, temp dirs, throwaway branches/workspaces) so
  you don't pollute `coding-agent-skills`, and clean up after.
- Everything stays repo-agnostic per `AGENTS.md`: no absolute paths, no
  usernames, scripts resolve their own root.

Latitude:

The above is intent and guardrails, not a rigid recipe. You decide the
harness design, how many sub-agents and which scenarios, the simulation
fidelity, and how to factor the `vcs` skill into referenced files — make
those calls and justify them briefly as you go.

When you're done, summarize: what `testing-vcs-skill` does and how to run
it; what changed in `vcs` and why; the evidence that the exit condition was
met (both modes, conflicts resolved cleanly, detection correct before and
after), including the time and quality measurements and how they improved
across rounds; and an honest verdict on the original question — whether
`jj` plus
the `vcs` skill beats Git + worktree for multi-agent work, or whether the
overhead isn't worth it.
