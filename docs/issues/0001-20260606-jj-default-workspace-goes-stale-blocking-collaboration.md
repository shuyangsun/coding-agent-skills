<!-- markdownlint-disable MD013 MD024 -->

# jj multi-workspace lifecycle gaps in multi-agent collaboration

- **Status:** Open — documented, not yet fixed
- **Date:** 2026-06-06
- **Area:** `skills/vcs` (multi-agent jj workflow); affects any session using per-agent `jj` workspaces
- **Severity:** Medium — both are recoverable, but they interrupt and accrete around the consolidate-and-push step of multi-agent collaboration
- **Environment:** Jujutsu (`jj`) 0.41.0 on a Git backend, colocated repo, multiple `jj workspace`s on one machine

## Summary

The multi-agent flow has each agent isolate into its **own** `jj` workspace
(`<ide>-<work>`), do its work, advance the shared `main` bookmark, and then
consolidate in the **`default`** workspace and push from there. Two related gaps
in that workspace **lifecycle** have surfaced — neither has guidance in the `vcs`
skill, and both bite the consolidation step:

- **Gap 1 — `default` goes stale** the moment a sibling workspace records
  operations, blocking every `jj` command there until reconciled.
- **Gap 2 — retired workspaces are never cleaned up** after their work lands on
  `main`; they linger on disk and keep contributing to Gap 1.

Both stem from the same root: `jj` workspace lifecycle is fully manual, and the
`vcs` skill doesn't yet drive the consolidate-and-tidy bookend the way it now
drives session-start isolation.

## Gap 1 — `default` workspace goes stale after sibling-workspace work

### Symptom

The moment another workspace records operations against the shared op log
(advancing `main`, splitting commits, etc.), the `default` workspace's recorded
working copy falls behind, and the **next** `jj` command run there fails:

```text
$ jj
Error: The working copy is stale (not updated since operation bcf0febada2c).
Hint: Run `jj workspace update-stale` to update it.
See https://docs.jj-vcs.dev/latest/working-copy/#stale-working-copy for more information.
```

Every `jj` command in `default` is blocked (not just the one that tripped it)
until `jj workspace update-stale` is run there. An agent that returns to
`default` to consolidate and push hits this wall first, with no guidance about
what it means — so it can stall, or misread it as repo corruption.

### How to reproduce

1. From `default`, add a sibling workspace and leave `default` on its own (e.g.
   empty) working-copy commit:
   `jj workspace add --name <ide>-<work> ../<repo>-<ide>-<work> -r main`
2. In the sibling workspace, do work and advance `main`
   (`jj describe …`, `jj split …`, `jj bookmark set main -r @`, `jj git export`).
3. Back in `default`, run any `jj` command (even read-only `jj st`). It errors
   with `The working copy is stale (not updated since operation …)`.

### Why it happens

`jj` workspaces share one operation log but each has its **own** working-copy
commit and a per-workspace pointer to "the operation at which this working copy
was last synced." When operations originate in another workspace, `default`'s
pointer is now behind the latest operation, so jj declares its on-disk working
copy **stale** and refuses to act until it is reconciled. This is working as
designed in jj, but it is a sharp edge for an automated, multi-workspace flow.

### Immediate remediation (manual, per occurrence)

From inside `default`:

```sh
jj workspace update-stale   # reconcile the working copy to the latest operation
```

It does not lose work — it reconciles the working-copy commit. (To then sit on
the latest mainline, `jj new main`.)

## Gap 2 — retired sibling workspaces are not cleaned up after their work lands

### Symptom

After a sibling workspace's commits are fully merged onto `main`, the workspace
itself **remains** — both as a jj workspace entry and as an on-disk directory.
Concretely this session: `vcs-tune` at `../coding-agent-skills-vcs-tune` was
still present after every one of its commits (the harness/vcs/transcript/issue
work) had landed on `main`. `jj workspace list` still showed it; the directory
still occupied disk and cluttered the parent folder. Nothing in the flow
prompted or performed the teardown.

### Why it happens

`jj` never auto-forgets a workspace — removing one is fully manual
(`jj workspace forget <name>` plus deleting its directory). The `vcs` skill's
`ISOLATE.md` "Cleanup" section documents those commands, but:

- Cleanup is framed as the **owning** agent's end-of-work step; in a multi-agent
  flow the agent consolidating in `default` may not know which sibling
  workspaces exist or that they are now safe to remove.
- There is no measurable enforcement, so it is silently skipped — and every
  leftover workspace is another working copy that re-triggers **Gap 1**
  staleness on the next shared operation. The two gaps compound.

### Immediate remediation (manual, per occurrence)

Once a workspace's work is fully on `main` and it does **not** back an open PR,
from `default` (or anywhere with repo access):

```sh
jj workspace forget <name>          # e.g. vcs-tune
rm -rf ../<repo>-<name>             # remove its on-disk directory
```

(Confirm first with `jj workspace list -T 'name ++ ": " ++ root ++ "\n"'`.) This
instance — `vcs-tune` — was cleaned up this way while documenting the gap.

## Impact on agent collaboration

- `default` is the natural place to **gather sibling workspaces' work and push**
  (it is the colocated checkout carrying `.git` and the `origin` remote). Gap 1
  blocks that consolidation outright; Gap 2 silently grows the set of workspaces
  that trigger Gap 1.
- An agent driving the merge has no `vcs` guidance for either state; it may retry
  blindly, abandon the merge, escalate unnecessarily, or leave orphans behind.
- Both interact with the freshly-added isolation/naming workflow: agents now
  routinely spin up sibling workspaces, so both states will be hit **often**.

## Proposed direction (NOT done here — for a later fix)

The `vcs` skill (likely `ISOLATE.md` / `INTEGRATE.md`) should grow guidance for
the **consolidate-in-`default`** bookend of the multi-workspace flow:

- Expect a `The working copy is stale` error when returning to `default` after
  sibling-workspace operations; treat it as routine, and run
  `jj workspace update-stale` (then `jj new main`) **before** merging or pushing.
- Enumerate sibling workspaces (`jj workspace list`), confirm each one's work is
  on `main`, then **forget + remove** the retired ones (skipping any that back an
  open PR) — making teardown an explicit, non-optional step, not a footnote.
- Spell out the recommended order to merge several agents' workspaces into
  `default` and publish, composed with branch/bookmark cleanup.

A future `improving-vcs-skill` harness round could measure both: that an agent
recovers from a stale `default` and that **no orphan workspaces remain** after a
multi-agent round — the same way isolation and naming are now measured.

## References

- jj stale working copy docs: <https://docs.jj-vcs.dev/latest/working-copy/#stale-working-copy>
- jj workspaces: <https://docs.jj-vcs.dev/latest/working-copy/#workspaces>
- Related skill files: `skills/vcs/ISOLATE.md`, `skills/vcs/INTEGRATE.md`
