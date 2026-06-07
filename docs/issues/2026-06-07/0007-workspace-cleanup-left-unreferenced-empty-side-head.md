# Workspace cleanup left an unreferenced empty side-head

- **Status:** Resolved (2026-06-07)
- **Area:** `skills/vcs` jj workspace cleanup; multi-agent repository hygiene
- **Severity:** Low/Medium — no work was lost, but `jj log` showed a confusing
  anonymous empty side-head after workspace/bookmark cleanup, which makes it
  harder to tell whether cleanup actually completed
- **Environment:** Jujutsu (`jj`) on a Git backend, colocated
  `coding-agent-skills` repo, multiple short-lived agent workspaces
- **Observed:** 2026-06-07, after a previous `claude-streaming-export`
  workspace/bookmark lifecycle
- **Related:** [0001](../2026-06-06/0001-jj-default-workspace-goes-stale-blocking-collaboration.md)
  (workspace lifecycle), [0003](0003-jj-integrate-forms-degenerate-empty-merge-blocking-push.md)
  (empty orphaned commits after jj integration), [0006](0006-agent-inspected-and-asked-about-another-agents-workspace-during-cleanup.md)
  (cleanup scope)

## Summary

After the `codex-optimize-git-worktrees-vcs` work landed and the temporary
workspace/bookmark was cleaned up, `jj log` still showed an older anonymous
side-head:

```text
│ ○  urruyqxt shuyangsun10@gmail.com 2026-06-07 04:43:16 b4b4027a
├─╯  (empty) (no description set)
```

Inspection showed it was not a real change:

```text
Commit ID: b4b4027a77d9d1e6e2264521cb780c014db47ccc
Change ID: urruyqxtulxkzmnvlnkovqwymoqvlsxx

    (no description set)

0 files changed, 0 insertions(+), 0 deletions(-)
```

It had no bookmark, no workspace pointed at it, and it was not on `main`. It was
abandoned manually:

```sh
jj abandon urruyqxt
```

## Expected

When a workspace/bookmark cleanup is complete:

- no retired workspace remains registered;
- no retired workspace directory remains on disk;
- no purely local merged bookmark remains;
- no anonymous empty side-head remains visible in `jj log` from that cleanup.

An empty current working-copy commit on top of `main` is fine. An old empty
side-head with no bookmark/workspace is not useful; it is cleanup residue.

## Actual

The workspace and bookmark had already been removed, but the empty working-copy
commit still existed as an unreferenced side-head. It made `jj log` look dirty
even though no real work was present.

The operation history around that commit showed it came from a short-lived
workspace/bookmark lifecycle:

```text
create bookmark claude-streaming-export pointing to commit b4b4027a...
...
forget workspace claude-streaming-export
delete bookmark claude-streaming-export
```

After those cleanup operations, the empty commit remained until explicitly
abandoned.

## Why This Matters

**Operator confidence.** The `vcs` skill uses `jj log` and hygiene checks to tell
whether multi-agent cleanup is complete. Anonymous empty side-heads are visual
noise that look like unfinished cleanup.

**Follow-up friction.** A later agent had to inspect the commit, verify it had no
files, verify no workspace/bookmark referenced it, and ask or decide whether to
abandon it.

**Harness coverage gap.** The current hygiene metrics cover stale refs,
workspace entries, workspace directories, and `default` readiness. They do not
explicitly fail a round for orphaned empty side-heads that are no longer attached
to a workspace/bookmark.

## Likely Cause

`jj workspace add` creates an initial working-copy commit. If that commit stays
empty and later receives a temporary bookmark, deleting the bookmark and
forgetting the workspace can leave the empty commit as an anonymous side-head.
This is distinct from issue 0003's degenerate empty merge on `main`: here the
commit was not on `main` and did not block push, but it still polluted the graph.

## Proposed Fix

Tighten the jj cleanup path in `vcs` and/or the helper:

1. After forgetting a retired workspace and deleting its bookmark, look for
   empty, description-less side-heads associated with that retired work.
2. If the candidate has no bookmark, no workspace, no diff, and is not on
   `main`, abandon it.
3. Keep the cleanup conservative: never abandon non-empty commits, described
   commits, commits with bookmarks, commits on `main`, or commits referenced by
   another active workspace.

For the harness, add an objective hygiene metric such as `ORPHAN_EMPTY_HEADS=0`
so this class of cleanup residue is measured separately from workspace-directory
cleanup.

## Acceptance Criteria

- After a jj workspace/bookmark integration cleanup, `jj log` does not show
  anonymous empty side-heads from the retired workspace.
- `check-quality.sh` or a companion hygiene check reports a failure if such an
  empty side-head remains.
- The cleanup rule is conservative enough that real unmerged work is never
  abandoned automatically.

## Resolution

Fixed in `scripts/integrate.sh`; measured by the `improving-vcs-skill` harness.

- **Sweep in the helper.** `jj_finish` now calls `jj_abandon_orphan_empty_heads`
  after retiring landed workspaces. It abandons every commit that is,
  conservatively, **empty AND description-less AND unbookmarked AND not an ancestor
  of `main` AND not any live workspace's working copy** — the revset
  `heads(all()) ~ ::main ~ bookmarks()` filtered by an `empty`/`description`
  template, minus the working-copy commit of every registered workspace
  (`<name>@`). So real work, named commits, bookmarked commits, `main`, and active
  working copies are never touched, while the anonymous residue is removed.
- **Stable anchor + cwd fix.** The sweep runs `jj -R <anchor>` against the
  `default` workspace root resolved _before_ the agent's own workspace is removed,
  and `cd`s into that live root first — because retiring the agent's workspace
  `rm -rf`s the cwd. This also surfaced and fixed a latent bug: the retire step's
  cwd-guard compared the shell `PWD` (`/tmp/…`) against jj's canonical root
  (`/private/tmp/…`) and silently missed on macOS, leaving the agent in a deleted
  directory and breaking the `NEXT_CWD` hand-off; it now also compares `pwd -P`.
- **Objective metric + seed.** `check-quality.sh` reports `ORPHAN_EMPTY_HEADS=N`
  (+ `ORPHAN_EMPTY_LIST`) with the same predicate and fails `WORKSPACE_HYGIENE` if
  any remain; `new-sandbox.sh` deterministically **seeds** exactly this residue in
  every jj integration round (`ORPHAN_SEEDED=1`: a bookmark pinned on an empty
  workspace commit, then the workspace forgotten and the bookmark deleted), and
  `_score.py` folds the count into the scoreboard's `orph` column.

Verified with the harness on Claude **Haiku**: jj/easy and jj/medium integration
rounds (seeded with an orphan each) both finish with `ORPHAN_EMPTY_HEADS=0`,
`WORKSPACE_HYGIENE: PASS`, and `RESULT: PASS` — the agents' `vcs` finish swept the
seeded side-head. A pre-integration `check-quality.sh` run reports
`ORPHAN_EMPTY_HEADS=1` (the seed), confirming the metric detects the defect the
fix removes.

## Reproduction Sketch

1. Create a jj workspace from `main`.
2. Leave its initial working-copy commit empty.
3. Create a temporary bookmark on that empty workspace commit.
4. Forget the workspace and delete the bookmark.
5. Run `jj log`.
6. Observe an unreferenced empty side-head still visible until
   `jj abandon <change>` is run.
