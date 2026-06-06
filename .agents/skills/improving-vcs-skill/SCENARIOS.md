# Scenario design: forcing real conflicts, detecting lost work

How `new-sandbox.sh` seeds collisions that any honest agent will hit, and how
`check-quality.sh` proves objectively whether the integration was clean — without
trusting what the agents say.

## The fixture project

Each sandbox is a tiny project whose files have deliberately **hot regions** that
multiple agents are steered into editing at once:

| File                   | Hot region                                       | Conflict class when agents collide                             |
| ---------------------- | ------------------------------------------------ | -------------------------------------------------------------- |
| `docs/CHANGELOG.md`    | top of the `## Unreleased` list                  | **adjacent-insert** (every agent adds a line at the same spot) |
| `app/config.yaml`      | the `version:` line                              | **same-line** (two agents set it differently)                  |
| `app/pipeline.py`      | line after the `# >>> pipeline steps <<<` marker | **insertion into a shared region**                             |
| `app/registry.json`    | the `core` plugin's `summary`                    | **same-line** value edit                                       |
| `app/feature_flags.py` | the `csv_export` flag                            | same-key flip                                                  |

The CHANGELOG is the **universal** conflict generator: every agent inserts at the
same top-of-list position, so any N ≥ 2 agents collide there regardless of their
other work. The other regions add same-line and insertion conflict classes when
≥ 2 agents are assigned the same group.

## The per-agent task model: additive sentinel + converging edit

Each `briefs/agent-K.md` reads like a real ticket and asks for two things:

1. **An additive, sentinel-bearing change** — a CHANGELOG entry tagged with a
   unique ticket id, e.g. `- streaming export (VCS-1-2)`. It's _additive_, so a
   correct integration keeps **every** agent's entry. The ticket id (`VCS-<round>-<k>`)
   is the **sentinel**.
2. **A converging edit** — assigned round-robin across three groups so that
   agents in the same group edit the same line/region:
   - group 1 → bump `version:` in `config.yaml` (same-line),
   - group 2 → add a step after the pipeline marker (shared-region insertion),
   - group 3 → edit the `core` summary + flip `csv_export` (same-line + flag).

Briefs deliberately **do not** mention the VCS mode, the conflicts, or this
harness — only the change to make and "publish onto `main`, resolve conflicts,
keep everyone's work, leave no markers." Detecting the mode and handling the
collision is what `vcs` must supply.

## How quality is judged objectively

`check-quality.sh` reads the round's `manifest.env` (which lists the sentinels)
and inspects the integrated `main`:

- **No lost work** — every sentinel ticket must still be present on `main`. A
  missing one means a teammate's additive entry was clobbered or never
  integrated. Because the entries are additive, a correct merge keeps them all,
  so this is a clean, unambiguous signal independent of the same-line conflicts.
- **No conflict markers** — `main` must contain no `<<<<<<<` / `>>>>>>>` fences
  (Git and jj both use these when a conflict is left in the tree).
- **No unresolved conflict** — Git: no unmerged index entries; jj: no conflicted
  commit in `::main` (jj will happily _commit_ a conflict, so this is checked
  natively, not just by scanning text).
- **Mode integrity** — Git-only sandbox must have no `.jj`; jj sandbox must keep
  `.jj`.

A round PASSes only if all hold. The same-line conflicts (version, summary) are
where agents must make a real judgment call; quality there is captured by "no
markers + no lost additive work + sane history," plus the human read of whether
the resolution is correct.

## Integration patterns (escalate across rounds)

- **Serialized integration** — agents work in parallel, then publish onto `main`
  one at a time; each later agent meets the earlier ones' conflicts. Start here.
- **Concurrent integration** — agents also publish concurrently, contending for
  `main`. Harder; use once serialized rounds pass.
- **Remote / PR flow** — `new-sandbox.sh --remote` adds a bare shared remote so
  cloud/GitHub cells publish by push/PR instead of local integration.

## Hazards these scenarios surface (watch for them)

Real failure modes worth noting when they appear in reports — they're signals for
what `vcs` must teach:

- **jj cross-workspace conflict materialization** — when an operation in one
  workspace conflicts a change checked out in another, jj rewrites that
  workspace's working copy on its _next_ jj command. Editing the file _before_
  letting jj update the working copy gets your edit clobbered. `vcs` should tell
  jj agents to let the working copy settle (run a `jj` command / `jj resolve`)
  before hand-editing.
- **Silent clobber on same-line conflicts** — an agent that "resolves" by taking
  only its own side drops a teammate's value; the additive sentinel catches the
  additive part, but reviewers should still eyeball same-line resolutions.
- **Fast-forward that skips a merge** — integrating by blind fast-forward/reset
  can erase a teammate's commit without a marker. Lost-sentinel detection catches
  it.

## Extending the fixtures

To broaden coverage, add new hot regions to `new-sandbox.sh`'s `seed_fixtures`
and a matching clause in `write_brief` (keep each agent's sentinel in an additive
location so lost-work detection stays clean). Candidates not yet covered:
**rename/delete vs edit** conflicts and **semantic** conflicts (two edits that
merge textually but break behavior) — add these as `vcs` starts passing the
textual ones.
