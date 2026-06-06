# Coverage matrix: agents × environments × modes

What each round should represent, and how to simulate cells you can't literally
run. The goal is that `vcs` works for **any** agent in **any** environment, so a
round samples across this space rather than testing one happy path.

## The two VCS modes (both mandatory every round)

| Mode    | Sandbox shape (`new-sandbox.sh --mode`)                                            | Detection signal an agent should use                     | Isolation primitive |
| ------- | ---------------------------------------------------------------------------------- | -------------------------------------------------------- | ------------------- |
| **jj**  | Jujutsu on a Git backend, **colocated** (`.git` + `.jj`; both `git` and `jj` work) | `jj` repo present ⇒ use jj, _even though Git also works_ | `jj workspace add`  |
| **git** | Plain Git, **no `.jj`**                                                            | no jj ⇒ Git only                                         | `git worktree add`  |

The colocated jj case is the subtle one: Git commands succeed there too, so a
naive "is this Git?" check would wrongly pick Git. `vcs` must prefer jj when jj
is present. `check-quality.sh` fails a Git-only round that grew a `.jj`, catching
the opposite error (an agent reaching for jj where it shouldn't).

## Agents and environments to represent

Sample several cells per round; rotate so that, over a few rounds, the
combinations below are all covered. Map each cell to a mode and assign it to a
sub-agent (one per workspace).

| Agent / tool (stand-in)      | Environment                        | Typical mode | Notes for the sub-agent                               |
| ---------------------------- | ---------------------------------- | ------------ | ----------------------------------------------------- |
| Claude Code                  | local-only CLI                     | jj or git    | full local tooling; best cell to exercise the jj path |
| Claude Code (remote-control) | localhost remote control           | jj or git    | same machine, driven remotely; tooling still local    |
| GPT Codex                    | cloud remote control               | git          | treat jj as unavailable unless proven present         |
| Cursor / Antigravity         | local IDE agent                    | jj or git    | local; can use either mode                            |
| GitHub Copilot               | fully-remote cloud (GitHub-hosted) | **git only** | **no jj**; publish via push / PR to a shared remote   |

Rule of thumb: **cloud/GitHub cells are Git-only** (assume no jj, use the
`--remote` sandbox and a push/PR publish flow); **local cells** should bias
toward the **jj** mode so the jj workflow gets real exercise, with at least one
local Git-only cell per round for contrast.

## Simulating faithfully when you can't run the real tool

You usually can't literally launch Codex, Cursor, Antigravity, or a GitHub-hosted
session from here. Simulate representatively and **say so** in the report:

- Spawn a sub-agent and **constrain it to the cell's limits** in its prompt — e.g.
  "you are in a fully-remote cloud session; `jj` is not installed" (so it must
  take the Git path and publish via remote), or "you are a local IDE agent with
  both git and jj available."
- Do **not** hand it knowledge a real agent in that cell wouldn't have: not the
  mode, not the conflict locations, not this harness. The point is to see whether
  `vcs` alone gets it to the right workflow.
- Different stand-in agents are still all driven by the same underlying model
  here; that's an accepted fidelity limit. What varies meaningfully per cell is
  the **environment constraint** and the **VCS mode**, which is what `vcs` has to
  handle — so vary those deliberately and label each cell as real or simulated.

## How many sub-agents

Enough to force real contention and to populate several cells, few enough to
measure cleanly. **3–5 agents per mode** is a good default (so ≥ 2 agents share
each hot region — see [SCENARIOS.md](SCENARIOS.md)). Scale up only once a config
is passing, to test that `vcs` holds under more contention. `new-sandbox.sh
--agents N` sets the count.
