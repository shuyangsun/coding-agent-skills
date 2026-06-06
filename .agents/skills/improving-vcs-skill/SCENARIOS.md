# Scenario design: deterministic conflicts, objective scoring

How `new-sandbox.sh` (via the `scenario.py` content engine) seeds collisions that
any honest agent will hit, and how `check-quality.sh` proves objectively whether
the integration was clean — without trusting what the agents say, and without
letting an agent's _coding_ ability affect the result.

## Determinism: pre-committed work, integration-only agents

Every agent's change is **generated deterministically** by `scenario.py` and
**committed in advance** on that agent's branch/bookmark (`agent-K`). The
sub-agent writes no code; it only integrates `agent-K` onto `main`. Re-running
`new-sandbox.sh` with the same `--mode/--difficulty/--agents/--round` produces
byte-identical fixtures and commits, so the conflict set — and therefore the
single correct merged result — is reproducible across rounds and tiers. That is
what lets `check-quality.sh` score _resolution quality_, not just _resolution
presence_.

## The fixture project

A tiny but realistic service repo. Baseline is identical across difficulties;
difficulty only changes which regions each agent touches and how big the change
is. Each region has a defined conflict class and a **mechanical** correct
resolution (union the additive parts; for the one same-line field, keep the
higher version) — no code judgment, pure VCS etiquette.

| File                | Hot region                             | Conflict class                  | Correct resolution          |
| ------------------- | -------------------------------------- | ------------------------------- | --------------------------- |
| `docs/CHANGELOG.md` | top of the `## Unreleased` list        | adjacent-insert (union)         | keep every entry            |
| `app/registry.json` | the `plugins` array                    | array append (union)            | keep every plugin object    |
| `app/handlers.py`   | the `HANDLERS` list                    | list append (union)             | keep every entry            |
| `app/config.yaml`   | the `version:` line                    | **same-line (tie-break)**       | keep the **higher** version |
| `app/pipeline.py`   | block after `# >>> pipeline steps <<<` | large multi-line insert (union) | keep every step block       |
| `notes/agent-K.md`  | a per-agent file                       | disjoint (no conflict)          | each file present, intact   |

The CHANGELOG is the **universal** conflict generator: every agent inserts at the
same top-of-list position, so any N ≥ 2 agents collide there. The others add
array/list/large-block union conflicts and one genuine same-line conflict.

## The difficulty ladder

`new-sandbox.sh --difficulty` selects which regions are hot and how many agents:

- **easy** (default 3 agents) — one small union conflict (CHANGELOG) plus a
  per-agent disjoint file. The simplest meaningful collision; verifies the basic
  integrate-and-union flow.
- **medium** (default 4 agents) — CHANGELOG + registry array + handler list (all
  union) **+** a `version` same-line tie-break among a subset of agents (so ≥ 2
  contend on one line). Multiple conflict classes, modest size; structured files
  must still parse after resolution.
- **hard** (default 6 agents) — all of the above for **every** agent **plus** a
  large multi-line block every agent inserts at the same `pipeline.py` marker.
  The result: big, overlapping conflict hunks across several files at once, with
  many parallel agents — a large amount of merge conflict, by design. Use
  concurrent integration here for maximum pressure.

## The resolution rules (deterministic ⇒ checkable)

The briefs state the etiquette without revealing _where_ the conflicts are:

- **Union** every additive change — keep every changelog entry, every array/list
  element, every code block a teammate added; never drop one.
- For a **single-valued field set differently by two teammates** (the version),
  keep the **higher** value.

Because these rules are fixed, the correct final content is fully determined, so
the oracle below can check it exactly. The agent still has to do all the real VCS
work — detect the mode, integrate, find the conflicts, resolve them — to get
there.

## No work after the merge (so we measure the right thing)

Briefs explicitly forbid writing new code, adding/altering tests, running the
app/build/formatters, or amending the committed change. We are timing and scoring
the conflict resolution **immediately** after integration; downstream "make it
work" effort is exactly the coding-ability variance we are removing. The oracle's
"untouched files must equal baseline" check turns that instruction into an
objective signal — an agent that wandered off and edited unrelated code fails it.

## How quality is judged objectively

`check-quality.sh` inspects the integrated `main` and combines VCS-level checks
with the deterministic **resolution oracle** (`scenario.py check`, driven by the
round's `spec.json`):

- **Mode integrity** — a Git-only sandbox must have no `.jj`; a jj sandbox must
  keep `.jj`.
- **No conflict markers** — `main` must contain no `<<<<<<<` / `|||||||` /
  `>>>>>>>` fences.
- **No unresolved conflict** — Git: a conflicted merge can't be published, so
  leftover markers are the tell; jj: no conflicted commit in `::main` (jj will
  happily _commit_ a conflict, so this is checked natively).
- **No lost work** — every agent's sentinel ticket (`VCS-<round>-<k>`) survives.
- **Resolution oracle** — union regions contain every contribution **exactly
  once** (catches both dropped work and duplicate-paste resolutions); the
  same-line tie-break equals the higher version; structured files (`JSON` /
  `Python` / `YAML`) still parse; and files no agent touched are byte-identical
  to baseline (catches clobber and forbidden extra work).

A round PASSes only if all hold. This is a strong, order-independent oracle: the
correct union is the same no matter what order agents integrated in, so it scores
serialized and concurrent rounds alike, across every model tier.

## Hazards these scenarios surface (watch for them)

Real failure modes worth noting when they appear in reports — they're signals for
what `vcs` must teach:

- **jj cross-workspace conflict materialization** — when an operation in one
  workspace conflicts a change checked out in another, jj rewrites that
  workspace's working copy on its _next_ jj command. Editing the file _before_
  letting jj update the working copy gets your edit clobbered. `vcs` should tell
  jj agents to let the working copy settle (run a `jj` command / `jj resolve`)
  before hand-editing.
- **Duplicate-paste resolution** — an agent that "resolves" by keeping both whole
  sides duplicates a teammate's entry; the oracle's exactly-once check catches it.
- **Silent clobber on the same-line field** — taking only one side drops the
  other's value; the tie-break check catches a wrong winner.
- **Fast-forward that skips a merge** — integrating by blind fast-forward/reset
  can erase a teammate's commit; lost-sentinel + union checks catch it.

## Extending the fixtures

All content lives in `scenario.py`, the single source of truth for both the
seeded work and the expected result. To broaden coverage, add a region there:
a `baseline_files` entry, an `apply_*` function + an `agent_touches` clause, the
matching `spec` region, and (if structured) a `structural` check. Keep each
agent's sentinel in an additive location so lost-work detection stays clean.
Candidates not yet covered: **rename/delete vs edit** conflicts and **semantic**
conflicts (two edits that merge textually but break behavior) — add these as
`vcs` starts reliably passing the textual ones.
