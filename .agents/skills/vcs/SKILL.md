---
name: vcs
description: Jujutsu (jj) squash workflow only — no Git. New sibling workspaces under the parent directory before editing.
---

# VCS

## Preparation

Create a sibling workspace with `jj workspace add ../<REPO>-<ASSISTANT-NAME>-<WORK-SHORT-NAME>` before editing. `<REPO>` is the basename of the default workspace directory; `<ASSISTANT-NAME>` is the assistant (e.g. `gpt`, `claude`, `cursor`, `agy`); `<WORK-SHORT-NAME>` is a short work label (e.g. `backend-refactor`, `feature-abc`, `gui-design`). Keep the name short but identifiable.

## Editing

1. `jj new main`, then `jj describe -m "..."` using the `commit` skill.
2. `jj new` again — edit there, not on the parent.
3. `jj squash` into the parent with a description.
4. `jj rebase -s <parent> -d main` (`<parent>` = parent change ID). Resolve conflicts, then rebase again.

## Advancing main

When ready: `jj edit <parent> && jj desc -m "..."` (via `commit`), `jj rebase -s <parent> -d main`, then `jj bookmark set main -r <parent>`. If asked to push: `jj git push -b main`.

## Cleanup

Once main is advanced or pushed: `jj workspace forget <REPO>-<ASSISTANT-NAME>-<WORK-SHORT-NAME>`, `cd ../<REPO>/`, then `rm -rf ../<REPO>-<ASSISTANT-NAME>-<WORK-SHORT-NAME>`. Never delete `<REPO>` or the parent directory.
