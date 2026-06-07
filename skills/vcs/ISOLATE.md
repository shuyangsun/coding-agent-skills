# Starting new work: isolate first (parallel-agent safety)

Before you start changing files, give yourself your **own working copy** so you
don't collide with other agents/teammates working in the same repository at the
same time. Two agents editing, building, or switching branches in the _same_
working directory trample each other; a per-agent worktree (Git) / workspace (jj)
prevents that. Isolate **unless you are already isolated** — don't nest a second
working copy inside one you already have.

**When this applies:** you're on a **local machine** doing **new** work in a repo
that other agents may also be working in concurrently. **When to skip it:** a
dedicated cloud / CI / PR session already gives you your own clone or checkout —
you're isolated by construction, so just do the work and land it
([INTEGRATE.md](INTEGRATE.md)). Detect the mode first ([SKILL.md](SKILL.md)).

The objective is what matters, not a specific command: **a filesystem-isolated,
cleanly-removable place to work, on your own branch/bookmark.** Anything that
achieves that is correct.

## Git mode

First check whether the tool already started you in a linked worktree (some
agentic tools do this by default):

```sh
[ "$(git rev-parse --git-dir)" != "$(git rev-parse --git-common-dir)" ] && echo "linked worktree" || echo "primary checkout"
```

(A linked worktree's `.git` is a _file_ and its git-dir lives under
`.git/worktrees/<name>`; the primary checkout's git-dir **is** the common dir.)

- **Already in a linked worktree → you're isolated.** Don't create another. Just
  make sure you're on your **own** branch (if you're sitting on a shared branch
  like `main`, `git switch -c agent-X` first), do the work, and clean up the
  branch when you finish.
- **In the primary checkout → carve out your own worktree before working:**

  ```sh
  git fetch origin                                   # if there's a remote
  git worktree add ../<repo>-agent-X -b agent-X origin/main   # or `main` if local-only
  cd ../<repo>-agent-X
  ```

  Work there, then integrate ([INTEGRATE.md](INTEGRATE.md)) and clean up (below).

## jj mode

jj's per-agent isolation primitive is a **workspace** (each has its own
working-copy commit); the shared one is named `default`.

- **Already in your own (non-`default`) workspace → work in place**, make your
  bookmark, clean up at the end.
- **Otherwise → add your own workspace before working:**

  ```sh
  jj workspace add --name agent-X -r main ../<repo>-agent-X
  cd ../<repo>-agent-X
  ```

  Work there, then advance `main` ([INTEGRATE.md](INTEGRATE.md)) and clean up.

## The judgement case: already in a Git worktree **and** jj is available

A Git worktree of a colocated repo does **not** carry its own `.jj` — jj cannot
operate from inside it (`jj root` there fails with "There is no jj repo", which is
also why mode detection run from the worktree reports _git_). You already have
filesystem isolation from the worktree, so the parallel-safety goal is **already
met**. Don't try to force jj against a worktree that has no `.jj`. Pick whichever
of these keeps your work isolated and cleanly removable:

- **Simplest — use Git in the worktree you're in.** You're already isolated; work
  on your own branch, integrate, and delete the branch + remove the worktree when
  done. The worktree + branch + cleanup achieves exactly the parallel-safe outcome
  a jj workspace would.
- **Or, if you specifically want the jj workflow,** step back to the **main repo**
  (where `.jj` lives) and `jj workspace add` a fresh workspace to work in instead —
  operate jj from there, not from the git worktree.

Either way you end with isolated, removable work; choose by which is less friction
in your environment.

## Cleanup (when you finish)

Removing your isolated working copy is part of a clean finish, alongside deleting
your merged branch/bookmark (see
[INTEGRATE.md → Finish](INTEGRATE.md#finish-delete-the-merged-branch-then-stop)):

- **Git worktree you created:** from outside it,
  `git worktree remove ../<repo>-agent-X` (then delete the branch per Finish).
- **jj workspace you created:** `jj workspace forget agent-X` and remove its
  directory (then delete the bookmark per Finish).
- If the tool started you in a worktree you didn't create, leave its removal to
  the tool; just delete your branch/bookmark.

Skip deletion only when a **remote branch backs it** (an open PR) — same carve-out
as Finish.
