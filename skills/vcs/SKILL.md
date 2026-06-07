---
name: vcs
description: Version-control etiquette for coding agents — detect the VCS mode
  (Jujutsu vs Git), land work on a shared main, resolve merge conflicts by union,
  and format commit messages. Load before any commit, merge, rebase, or publish.
---

# VCS

Follow this for every commit, merge, rebase, and publish, in whatever
version-control system the repo uses.

## 1. Detect the mode first — before any VCS action

Run `jj root` (or look for a `.jj/` directory).

- **It succeeds → Jujutsu (jj) mode.** Use jj for everything, **even though Git
  commands also work** — a colocated repo has both `.git` and `.jj`, and a naive
  "is this Git?" check picks the wrong tool. jj is the right tool whenever jj is
  present.
- **It fails / no `.jj` → Git mode.** Plain Git, including a Git *worktree* (where
  `.git` is a file pointing into a parent repo). Use Git.

Stay in that mode the whole session and re-confirm it before you publish; never
cross tools (don't run jj in a Git repo, or fall back to raw git in a jj repo).

## 2. Land work & resolve conflicts

To get your committed work onto a shared `main` — and pull in teammates' work
that landed first — follow **[INTEGRATE.md](INTEGRATE.md)**. It has the exact
integrate-and-publish steps for each mode, the conflict etiquette (union every
additive change; keep the higher value for a single-valued field; leave no
markers), the jj rule that **no conflicted commit may remain in `main`'s
history** before you advance the bookmark, and the final tidy-up — **delete your
merged branch/bookmark** (unless it backs an open PR) so it doesn't linger as a
stale ref.

## 3. Write the commit message

Whenever you author or edit a commit message — including the merge commits you
create while integrating — format it as in **[COMMITS.md](COMMITS.md)**.
