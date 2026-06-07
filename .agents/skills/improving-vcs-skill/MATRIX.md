# Coverage matrix: tiers × agents × environments × modes

What each round should represent, and how to simulate cells you can't literally
run. The goal is that `vcs` works for **any** model, in **any** agent/tool, in
**any** environment — so a round samples across this space rather than testing
one happy path. Three axes are mandatory every round: **VCS mode**, **difficulty**
([SCENARIOS.md](SCENARIOS.md)), and **model tier**.

## Model tier (vendor-agnostic — vary it every round)

A smaller model can sail through a clean fast-forward yet mangle a large
multi-file conflict that a frontier model resolves in one pass. If you only ever
test the biggest model, `vcs` will quietly come to depend on inference smaller
models can't supply. So stand in for a spread of capability tiers and **report
per tier**.

| Tier      | Stands for                 | What to watch                                                       |
| --------- | -------------------------- | ------------------------------------------------------------------- |
| **large** | frontier / flagship model  | Should pass everything; sets the speed/quality ceiling.             |
| **mid**   | mainstream workhorse model | The realistic common case; should pass with clear guidance.         |
| **small** | fast / cheap / small model | The stress test for `vcs` clarity — where vague steps cause stalls. |

Keep the labels exactly `large` / `mid` / `small` so `scoreboard.sh` can compare
across rounds and print the difficulty×tier pass-rate matrix. Map them to
whatever your platform exposes for model selection; the point is the **capability
spread**, not any one vendor. State which concrete model backed each tier in the
round notes so results are reproducible. A `vcs` revision has met the bar only
when **every tier** clears it — if `small` lags on `hard`, that cell is the next
thing to fix.

## The two VCS modes (both mandatory every round)

| Mode    | Sandbox shape (`new-sandbox.sh --mode`)                                            | Detection signal an agent should use                     | Isolation + shared integration point                  |
| ------- | ---------------------------------------------------------------------------------- | -------------------------------------------------------- | ----------------------------------------------------- |
| **jj**  | Jujutsu on a Git backend, **colocated** (`.git` + `.jj`; both `git` and `jj` work) | `jj` repo present ⇒ use jj, _even though Git also works_ | `jj workspace add`; shared local `main` bookmark      |
| **git** | Plain Git, **no `.jj`**                                                            | no jj ⇒ Git only                                         | `git worktree`; shared **bare `origin`** to push onto |

The colocated jj case is the subtle one: Git commands succeed there too, so a
naive "is this Git?" check would wrongly pick Git. `vcs` must prefer jj when jj
is present. `check-quality.sh` fails a Git-only round that grew a `.jj`, catching
the opposite error (an agent reaching for jj where it shouldn't).

Git mode integrates onto a shared bare `origin` the worktrees push to — this
models both Git + worktree teams and the cloud/PR publish flow in one shape, so
there is no separate remote flag. jj mode is local: all workspaces share one
repo and advance the `main` bookmark.

The "Isolation" column above is what the **integration** task pre-provisions _for_
the agent. The `--task start` task flips it: the agent must create that isolation
**itself** before doing new work, and the two `--start-from` arms test the
conditional — **main** (begins in the shared checkout → must isolate) and
**worktree** (already isolated → must not double-isolate). Cross start rounds with
the tier axis too, so e.g. a `small`-tier jj/start and a `large`-tier git/start
both appear over a few rounds. See [SCENARIOS.md](SCENARIOS.md).

## Agents and environments to represent

Sample several cells per round; rotate so that, over a few rounds, the
combinations below are all covered. Map each cell to a mode + tier and assign it
to a sub-agent (one per workspace).

| Agent / tool (stand-in)      | Environment                        | Typical mode | Notes for the sub-agent                               |
| ---------------------------- | ---------------------------------- | ------------ | ----------------------------------------------------- |
| Claude Code                  | local-only CLI                     | jj or git    | full local tooling; best cell to exercise the jj path |
| Claude Code (remote-control) | localhost remote control           | jj or git    | same machine, driven remotely; tooling still local    |
| GPT Codex                    | cloud remote control               | git          | treat jj as unavailable unless proven present         |
| Cursor / Antigravity         | local IDE agent                    | jj or git    | local; can use either mode                            |
| GitHub Copilot               | fully-remote cloud (GitHub-hosted) | **git only** | **no jj**; publish via push / PR to the shared origin |

Rule of thumb: **cloud/GitHub cells are Git-only** (assume no jj, publish by
push/PR to the shared origin); **local cells** should bias toward the **jj** mode
so the jj workflow gets real exercise, with at least one local Git-only cell per
round for contrast. Cross these with the tier axis so, e.g., a `small`-tier
cloud-Git cell and a `large`-tier local-jj cell both appear over a few rounds.

## Simulating faithfully when you can't run the real tool

You usually can't literally launch Codex, Cursor, Antigravity, or a GitHub-hosted
session from here, and you may not have every model. Simulate representatively
and **say so** in the report:

- Spawn a sub-agent **at the chosen tier's model** and **constrain it to the
  cell's limits** in its prompt — e.g. "you are in a fully-remote cloud session;
  `jj` is not installed" (so it must take the Git path and publish to the shared
  origin), or "you are a local IDE agent with both git and jj available."
- Do **not** hand it knowledge a real agent in that cell wouldn't have: not the
  mode, not the conflict locations, not this harness. The point is to see whether
  `vcs` alone gets it to the right workflow.
- What varies meaningfully per cell is the **model tier**, the **environment
  constraint**, and the **VCS mode** — vary those deliberately and label each
  cell (tier + real-or-simulated) so the per-tier scoreboard is honest.

## How many sub-agents

Enough to force real contention and to populate several cells, few enough to
measure cleanly. `new-sandbox.sh` defaults scale with difficulty (**easy 3,
medium 4, hard 6**); `--agents N` overrides. Hard rounds should run more agents
so the large shared blocks produce big, genuinely contended conflicts. Scale up
only once a config is passing, to test that `vcs` holds under more contention.
