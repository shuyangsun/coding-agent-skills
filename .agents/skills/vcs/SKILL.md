---
name: vcs
description: Version-control etiquette for coding agents — detect the VCS mode
  (Jujutsu vs Git), isolate new work in your own workspace/worktree (named
  <ide>-<work>) for safe parallel-agent collaboration, land work on a shared
  main, resolve merge conflicts by union, and format commit messages. Load this
  at the START of almost any repo task: before you change a single file for new
  work (so you isolate first), and before any commit, merge, rebase, or publish.
  When in doubt, load it — nearly all coding work touches version control.
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
- **It fails / no `.jj` → Git mode.** Plain Git, including a Git _worktree_ (where
  `.git` is a file pointing into a parent repo). Use Git.

Stay in that mode the whole session and re-confirm it before you publish; never
cross tools (don't run jj in a Git repo, or fall back to raw git in a jj repo).

## 2. Starting new work? Isolate first (local parallel-agent safety)

Before you change any files on a machine you share with other agents/teammates
working in the same repo, give yourself your **own** workspace (jj) / worktree
(Git) on your own branch/bookmark — **unless you're already in one** (some agentic
tools start you in a worktree by default; don't nest another). This is what keeps
co-located agents from trampling each other's working tree. Name the
workspace/worktree and its branch/bookmark `<ide>-<work>` — your coding tool
(`claude`, `codex`, `agy`, `cursor`, …) plus a short intuitive description of the
task, e.g. `claude-streaming-export`. Full per-mode recipes,
the already-in-a-git-worktree-with-jj judgement case, and the matching cleanup are
in **[ISOLATE.md](ISOLATE.md)**. In a dedicated cloud/PR session you already have
your own clone — skip this and go straight to landing your work.

## 3. Land work & resolve conflicts

To get your committed work onto a shared `main` — and pull in teammates' work
that landed first — follow **[INTEGRATE.md](INTEGRATE.md)**. It has the exact
integrate-and-publish steps for each mode, the conflict etiquette (union every
additive change; keep the higher value for a single-valued field; leave no
markers), the jj rule that **no conflicted commit may remain in `main`'s
history** before you advance the bookmark, and the final tidy-up — **delete your
merged branch/bookmark** (unless it backs an open PR), and in jj multi-workspace
flows recover/park `default` and retire landed sibling workspaces, so stale
working copies don't block the next consolidation.

## 4. Write the commit message

Whenever you author or edit a commit message — including the merge commits you
create while integrating — format it as in **[COMMITS.md](COMMITS.md)**.
