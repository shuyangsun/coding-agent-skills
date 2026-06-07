# Integrating work & resolving conflicts

How to land your committed change onto a shared `main` and resolve the conflicts
that arise when teammates touched the same files. First [detect the
mode](SKILL.md); then follow that mode's steps. The conflict etiquette is the
same in both modes; the mechanics differ.

## The model (read once)

You have a finished change on your branch/bookmark. Several teammates are landing
their own changes on the same `main`. Your job: **integrate your change with the
current `main` and publish the union.** You do not hunt down teammates' branches —
you integrate against `main` as it is *now* and resolve whatever conflicts that
produces. Two no-conflict outcomes are equally valid — don't manufacture work:
if you arrive **first**, your change lands as a clean fast-forward with nothing to
union; if `main` already contains everyone's work, there's nothing to resolve.
Either way, verify and stop.

## Conflict etiquette (both modes)

- **Union every additive change.** Keep every changelog entry, every list/array
  element, every code block any side added — yours *and* every teammate's. Never
  drop one.
- **Single-valued field set two different ways** (e.g. a `version:` line): keep
  the **higher** value. Decide by the value itself, never by which side a marker
  puts it on — under `git rebase` the sides are *inverted* (the `HEAD`/`<<<<<<<`
  side is the teammates' already-landed work, the `>>>>>>>` side labeled with your
  commit is yours), so "keep mine" is the wrong heuristic; compare and keep the
  larger.
- **Never resolve a whole file by taking one side** ("ours"/"theirs",
  `-X ours`, `git checkout --theirs`) — that silently discards the other side's
  additions. Resolve hunk by hunk, keeping both.
- **Leave no conflict markers** (`<<<<<<<`, `=======`, `>>>>>>>`, `|||||||`).
- **Verify before you publish** (see each mode's verify step).

## Git mode

Your work is on branch `agent-K`, checked out in your worktree. `main` is the
shared line — usually a remote `origin` (a worktree team pushes to it; a cloud/PR
session publishes to it). Do **not** `git checkout main`: in a worktree `main` is
often checked out elsewhere and the checkout fails. Publish by pushing `HEAD:main`.

1. `git fetch origin` — get the current shared `main`.
2. Integrate it into your branch: `git rebase origin/main` (or
   `git merge origin/main`). Either is fine; be consistent.
3. If it stops on conflicts, resolve each per the etiquette above, then
   `git add -A` and `git rebase --continue` (or, for a merge, `git commit`).
   Repeat until clean. (`git rebase --continue` keeps the existing message and
   won't take `-m`; if it tries to open an editor, prefix `GIT_EDITOR=true`.)
4. Publish: `git push origin HEAD:main`.
5. If the push is **rejected (non-fast-forward)** — a teammate landed first —
   re-run from step 1 (`git fetch` then rebase onto the new `origin/main`) and
   push again. Repeat until it lands.
6. **Verify:** `git show origin/main:docs/CHANGELOG.md` (or `git log origin/main`)
   shows your change *and* the teammates' already there, with no markers.
7. **Finish:** delete `agent-K` *unless a remote branch backs it* — if
   `git ls-remote --heads origin agent-K` prints nothing, `git switch --detach &&
   git branch -d agent-K`; if it prints a ref, keep it (open PR). Details in
   [Finish](#finish-delete-the-merged-branch-then-stop).

## jj mode (Jujutsu, usually on a Git backend)

Your work is on bookmark `agent-K`. `main` is a local bookmark (jj sessions are
typically local — there may be no remote; "publish" means advancing the `main`
bookmark). jj records conflicts as **commit state**, so it will happily *commit* a
conflict — you must resolve it *in the commit*, not paper over it in a child.

1. If jj warns the working copy is stale, run `jj workspace update-stale` (or any
   `jj` command) first so the working copy reflects current `main`.
2. Create the integration commit as a merge of `main` and your work:
   `jj new main agent-K`. (Equivalently `jj rebase -b agent-K -d main` then edit
   that commit.) The new commit `@` becomes your merge.
3. If `@` is conflicted, jj writes conflict markers into the working-copy files.
   **Let the working copy settle first** (the `jj new`/`jj status` already did
   this) — then edit the files to resolve per the etiquette, removing every
   marker. jj records your resolution into `@` on its next snapshot; you don't run
   `git add`. (`jj resolve --list` shows the conflicted paths if you want help.)
4. **Confirm no conflict remains in the commit**, not just in the text. Run
   `jj log -r '::@'` and check the merge `@` is not marked `conflict`; or list
   conflicts explicitly with
   `jj log -r '::@' -T 'if(conflict, change_id.shortest(8) ++ " CONFLICT\n", "")'`
   (it must print nothing). A clean working tree on top of a still-conflicted
   commit is the #1 jj integration failure — fix the conflict *in* the commit
   (step 3), don't leave it behind.
5. Advance `main` to your resolved merge — **but first re-check that `main` didn't
   move under you.** With no server to reject a bad update, `jj bookmark set` will
   silently **clobber** a teammate who advanced `main` after your step 2. Look at
   `main` now (`jj log -r main`): your merge `@` must be a **descendant of the
   current `main`** (it already contains main's latest commit). If `main` moved and
   `@` no longer descends from it, your merge is stale — **re-form** it against the
   new `main` with `jj new main agent-K` (re-merging your `agent-K` work with the
   updated `main`), then re-resolve any conflict and re-run the step-4 check before
   advancing. Do **not** try to recover with `jj rebase -r @ -d main`: if `@` is a
   bare merge with no changes of its own, rebasing just that commit drops your
   `agent-K` parent's work — re-forming from `agent-K` keeps it. Only when `@`
   descends from the current `main`:
   `jj bookmark set main -r @` (use `--allow-backwards` only if jj asks and you've
   confirmed it's correct), then `jj new` for a clean working copy. Under
   contention, loop this re-check until `main` is unchanged at the moment you set
   it — this is the jj equivalent of Git's non-fast-forward retry.
6. If the repo is colocated with Git tooling, run `jj git export` so the Git
   `main` ref matches.
7. **Verify** with jj (not git): `jj log -r '::main'` shows no conflicted commit;
   the files on `main` contain your change and the teammates' (no markers); and
   `jj resolve --list` reports nothing to resolve. In a local (non-colocated) jj
   repo the `main` *bookmark* is the shared line — a missing plain-git `main` ref
   is expected, not a publish failure.
8. **Finish:** delete `agent-K` *unless a **real** remote backs it* (`jj git
   remote list` is non-empty and the bookmark tracks one of those — `agent-K@git`
   is the local backend, **not** a remote, so it doesn't count):
   `jj bookmark delete agent-K` then `jj git export`. Details in
   [Finish](#finish-delete-the-merged-branch-then-stop).

## Finish: delete the merged branch, then stop

Once your work is verified on `main`, your `agent-K` branch/bookmark is merged and
redundant — leaving it behind is a **stale ref** that clutters the repo. Decide
its fate with **one check, run first**: does a branch of that name still exist on a
remote?

- **git:** `git ls-remote --heads origin agent-K`
- **jj:** first list real remotes with `jj git remote list`; a branch is
  remote-backed only if it tracks one of *those* — `agent-K@<remote-name>` in
  `jj bookmark list`. **`agent-K@git` does NOT count:** `@git` is jj's local
  colocated Git backend, not a network remote, and it's present for *every*
  bookmark in a git-backed repo. If `jj git remote list` is empty, there is **no**
  remote, so nothing is remote-backed — always delete.

**If a real remote ref backs it → KEEP the local branch.** A remote branch is
what a pull request is built on, so deleting your local copy throws away a ref a
reviewer may still need. A bare / self-hosted remote still counts — don't try to
judge whether a PR is "really" open (you usually can't from the CLI, and the
remote branch itself *is* the PR's head). But a purely local backend (`@git`, or a
jj repo with no remotes at all) is **not** a remote — delete in that case.

**If it prints nothing → the branch is purely local and merged, so DELETE it:**

- **git:** detach first (the branch is checked out in your worktree), then delete:
  `git switch --detach && git branch -d agent-K` (or `git checkout --detach`). The
  lowercase `-d` refuses a branch that isn't fully merged — a safety net; if it
  refuses, the branch didn't land, so fix the integration rather than forcing `-D`.
- **jj:** `jj bookmark delete agent-K`; in a colocated repo follow with
  `jj git export` so the Git ref disappears too.

Then **stop.** You are done the moment your work is on `main`, the union is
preserved, the verify step is clean, and the merged branch is resolved (deleted,
or kept because a remote backs it). Do not write new code, run
builds/tests/formatters, or amend the committed change — integration is the whole
job.
