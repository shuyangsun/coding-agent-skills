<!-- markdownlint-disable MD013 -->

# jj default workspace goes stale after sibling-workspace work, blocking collaboration

- **Status:** Open — documented, not yet fixed
- **Date:** 2026-06-06
- **Area:** `skills/vcs` (multi-agent jj workflow); affects any session using per-agent `jj` workspaces
- **Severity:** Medium — recoverable, but interrupts the consolidate-and-push step of multi-agent collaboration
- **Environment:** Jujutsu (`jj`) 0.41.0 on a Git backend, colocated repo, multiple `jj workspace`s on one machine

## Summary

In the intended multi-agent flow, each agent isolates into its **own** `jj`
workspace (`<ide>-<work>`), does its work, and advances the shared `main`
bookmark. The plan is then to return to the **`default`** workspace to merge the
sibling workspaces' work together and push from there. But the moment another
workspace records operations against the shared op log (advancing `main`,
splitting commits, etc.), the `default` workspace's recorded working copy falls
behind, and the **next** `jj` command run there fails:

```text
$ jj
Error: The working copy is stale (not updated since operation bcf0febada2c).
Hint: Run `jj workspace update-stale` to update it.
See https://docs.jj-vcs.dev/latest/working-copy/#stale-working-copy for more information.
```

Every `jj` command in `default` is blocked (not just the one that tripped it)
until `jj workspace update-stale` is run there. An agent that returns to
`default` to consolidate and push hits this wall first, with no guidance in the
`vcs` skill about what it means or how to proceed — so it can stall, or worse,
misread it as repo corruption.

## How to reproduce

1. From the `default` workspace, add a sibling workspace and leave `default`
   sitting on its own (e.g. empty) working-copy commit:
   `jj workspace add --name <ide>-<work> ../<repo>-<ide>-<work> -r main`
2. In the sibling workspace, do work and advance `main`
   (`jj describe …`, `jj split …`, `jj bookmark set main -r @`, `jj git export`).
3. Switch back to the `default` workspace and run any `jj` command (even read-only
   `jj st`). It errors with `The working copy is stale (not updated since
   operation …)`.

## Why it happens

`jj` workspaces share one operation log but each has its **own** working-copy
commit and a per-workspace pointer to "the operation at which this working copy
was last synced." When operations originate in another workspace, the
`default` workspace's pointer is now behind the latest operation, so jj declares
its on-disk working copy **stale** and refuses to act until the working copy is
reconciled with `jj workspace update-stale`. This is working as designed in jj,
but it is a sharp edge for an automated, multi-workspace agent workflow.

## Impact on agent collaboration

- The `default` workspace is the natural place to **gather sibling workspaces'
  work and push** (it is the colocated checkout that carries `.git` and the
  `origin` remote). Staleness blocks exactly that consolidation step.
- An agent driving the merge has no `vcs` guidance for this state; it may retry
  blindly, abandon the merge, or escalate unnecessarily.
- It interacts with the freshly-added isolation/naming workflow: agents now
  routinely spin up sibling workspaces, so this state will be hit **often**.

## Immediate remediation (manual, per occurrence)

Run, from inside the `default` workspace:

```sh
jj workspace update-stale
```

This re-points the working copy to the latest operation and unblocks subsequent
`jj` commands. (It does not lose work — it reconciles the working-copy commit.)

## Proposed direction (NOT done here — for a later fix)

The `vcs` skill (likely `ISOLATE.md` / `INTEGRATE.md`) should grow guidance for
the **consolidate-in-`default`** step of the multi-workspace flow, covering:

- Expect a `The working copy is stale` error when returning to `default` after
  sibling-workspace operations; treat it as routine, not corruption.
- Run `jj workspace update-stale` in `default` **before** trying to merge sibling
  work or push.
- The recommended order to merge several agents' workspaces into `default` and
  publish from there, and how this composes with the
  `jj workspace forget` / branch-cleanup steps.

A future revision of the `improving-vcs-skill` harness could also add a
measurable check that an agent recovers from a stale `default` workspace and
completes the consolidate-and-push, the same way isolation/naming are measured.

## References

- jj stale working copy docs: <https://docs.jj-vcs.dev/latest/working-copy/#stale-working-copy>
- Related skill files: `skills/vcs/ISOLATE.md`, `skills/vcs/INTEGRATE.md`
