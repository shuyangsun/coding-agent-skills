# Starting new work: isolate first (parallel-agent safety)

Before you start changing files, give yourself your **own working copy** so you
don't collide with other agents/teammates working in the same repository at the
same time. Two agents editing, building, or switching branches in the _same_
working directory trample each other; a per-agent workspace (jj) / worktree (Git)
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

**Name it `<ide>-<work>`.** Name your workspace/worktree **and** its
branch/bookmark for who is doing the work and what it is: `<ide>-<work>`, where
`<ide>` is the coding tool you are running in — `claude`, `codex`, `agy`,
`cursor`, etc. — and `<work>` is a short, intuitive, hyphenated description of
the task (e.g. `claude-streaming-export`, `codex-fix-auth-retry`). This makes it
obvious at a glance which agent owns which working copy when several share a
machine. The examples below use `<ide>-<work>` as that placeholder — substitute
your own tool name and task.

## Fast path: let the helper decide whether to isolate

Run this from the checkout you were handed, before editing:

```sh
bash <skill-dir>/scripts/isolate.sh <ide>-<work>
```

The helper detects Git vs jj, checks whether you are already in a linked
worktree/non-`default` workspace, creates a correctly named worktree/workspace
only when needed, and prints `WORKSPACE=` plus `WORK_REF=`. If `CREATED=yes`,
`cd` to `WORKSPACE` before editing. Use the manual recipes below only if the
helper is missing or reports an unexpected setup problem.

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
  like `main`, `git switch -c <ide>-<work>` first), do the work, and clean up the
  branch when you finish.
- **In the primary checkout → carve out your own worktree before working:**

  ```sh
  git fetch origin                                   # if there's a remote
  git worktree add ../<repo>-<ide>-<work> -b <ide>-<work> origin/main   # or `main` if local-only
  cd ../<repo>-<ide>-<work>
  ```

  Work there, then integrate ([INTEGRATE.md](INTEGRATE.md)) and clean up (below).

## jj mode

jj's per-agent isolation primitive is a **workspace** (each has its own
working-copy commit); the shared one is named `default`. List every workspace and
its on-disk path with
`jj workspace list -T 'name ++ ": " ++ root ++ "\n"'` — handy to find (or `cd`
back to) the path of yours.

- **Already in your own (non-`default`) workspace → work in place**, make your
  bookmark, clean up at the end.
- **Otherwise → add your own workspace before working:**

  ```sh
  jj workspace add --name <ide>-<work> -r main ../<repo>-<ide>-<work>
  cd ../<repo>-<ide>-<work>
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
  `git worktree remove ../<repo>-<ide>-<work>` (then delete the branch per Finish).
- **jj workspace you created:** `jj workspace forget <ide>-<work>` and remove its
  directory (then delete the bookmark per Finish).
- If the tool started you in a worktree you didn't create, leave its removal to
  the tool; just delete your branch/bookmark.

If you are doing an integration/consolidation task and `INTEGRATE.md` identifies
a sibling jj workspace as retired (its work is on `main` and it does not back open
review work), you are responsible for forgetting that workspace and removing its
directory even if another agent originally created it. Confirm with
`jj workspace list -T 'name ++ ": " ++ root ++ "\n"'`, move outside the directory
being removed, then forget and delete it.

Skip deletion only when a **remote branch backs it** (an open PR) — same carve-out
as Finish.
