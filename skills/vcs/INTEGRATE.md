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
5. Advance `main` to the resolved merge: `jj bookmark set main -r @`
   (use `--allow-backwards` only if jj asks and you've confirmed it's correct).
   Then `jj new` to leave yourself a clean empty working copy on top.
6. If the repo is colocated with Git tooling, run `jj git export` so the Git
   `main` ref matches.
7. **Verify** with jj (not git): `jj log -r '::main'` shows no conflicted commit;
   the files on `main` contain your change and the teammates' (no markers); and
   `jj resolve --list` reports nothing to resolve. In a local (non-colocated) jj
   repo the `main` *bookmark* is the shared line — a missing plain-git `main` ref
   is expected, not a publish failure.

## Stop after integrating

You are done the moment your work is on `main`, the union is preserved, and the
verify step is clean. Do not write new code, run builds/tests/formatters, or amend
the committed change — integration quality is the whole job.
