<!-- markdownlint-disable MD013 MD024 -->

# `integrate.sh` forms a degenerate empty merge for fast-forwardable jj work, then can't push it

- **Status:** Resolved (2026-06-07)
- **Date:** 2026-06-07
- **Area:** `skills/vcs` — `scripts/integrate.sh`, jj publish path (`jj_form_merge`, `jj_publish_loop`)
- **Severity:** Medium — work lands correctly, but the helper leaves `main` on an empty, description-less merge commit that `jj git push` refuses, forcing manual recovery and leaving orphaned commits in the graph
- **Environment:** Jujutsu (`jj`) on a Git backend, colocated repo, single local agent landing linear work onto `main`

## Summary

When `integrate.sh` lands jj work, it **always** forms an explicit two-parent
integration merge (`jj new <main> <work>`) and advances `main` to that merge
commit. When the work is already linear on top of `main` — the common
single-agent case — that merge is **degenerate**: it has no diff (empty) and no
description. jj then refuses to push it (`Won't push commit … since it has no
description`), so the operator must manually move `main` back onto the real work
commit. That manual move leaves the empty merge and the empty working-copy
commit orphaned above the `main` bookmark, producing a confusing graph.

This was hit live while landing the `docs(vcs): tighten skill description and
mandate isolate-first` change. It is the publish/land counterpart to the
isolation gap in [0002](0002-20260607-agent-used-default-jj-workspace-instead-of-isolating.md).

## Expected behavior

When `main` is already an ancestor of the work bookmark (nothing to merge), the
helper should **fast-forward**: `jj bookmark set <main> -r <work>`. It should
only form a merge (`jj new <main> <work>`) when `main` has genuinely diverged
from the work. After integration, `main` should point at a real, described
commit that pushes without manual intervention, and the graph should be linear.

## Actual behavior

`jj_form_merge` (integrate.sh:335-345) unconditionally creates the merge:

```sh
jj new "$main_ref" "$work_ref" >/dev/null 2>&1 ||
  die "could not create jj integration merge from '$main_ref' and '$work_ref'"
```

`jj_publish_loop` (integrate.sh:418-449) then advances `main` onto that commit
(`@`) and opens a fresh empty working copy:

```sh
if jj bookmark set "$main_ref" -r @ >/dev/null 2>&1; then
  jj new "$main_ref" >/dev/null 2>&1 || true
  ...
```

Because the work (`ecad11af → 945627d → 59a9bdb1`) was already linear on top of
`main` (`59a9bdb1`), the merge `jj new 59a9bdb1 ecad11af` produced an **empty,
description-less** commit `7eec19e5`, and `main` was set to it.

The push then failed:

```text
$ jj git push --bookmark main
Error: Won't push commit 7eec19e53876 since it has no description
Hint: Rejected commit: pmoslpzk 7eec19e5 main* | (empty) (no description set)
```

Manual recovery was required — move `main` back onto the real work commit, then
push:

```text
jj bookmark set main -r ecad11af --allow-backwards
jj git push --bookmark main      # succeeds
```

That left the graph with the empty merge (`pmoslpzk 7eec19e5`) and a new empty
working copy (`trokzwlp`) floating **above** the `main` bookmark, unreachable
from it:

```text
@  trokzwlp  a49d068a  (empty) (no description set)
○    pmoslpzk  7eec19e5  (empty) (no description set)
├─╮
│ ◆  vvrxrkpo  main ecad11af  docs(vcs): tighten skill description and mandate isolate-first
│ ~  (elided revisions)
├─╯
◆  svunznxk  59a9bdb1  chore(codex): allow trusted push commands
```

The relevant op-log slice, confirming no Git mutations were involved — only jj
and the helper:

```text
point bookmark main → ecad11af     # manual recovery
new empty commit
forget workspace claude-vcs-desc-when
delete bookmark claude-vcs-desc-when
new empty commit
point bookmark main → 7eec19e5     # helper set main onto the empty merge
new empty commit                   # jj_form_merge: jj new main work
describe commit …
split commit …
```

## Why this matters

- **Broken happy path.** The single-agent, linear-work case is the most common
  way the helper is used, and it does not complete cleanly — it dead-ends at an
  un-pushable `main` and needs manual `jj bookmark set` recovery the skill never
  documents.
- **Confusing, dirty graph.** Empty merge + empty working-copy commits are left
  orphaned above `main`. An operator inspecting `jj log` sees a "merge" that
  implies divergence that never happened.
- **The skill can't self-recover.** `jj_publish_loop` treats `jj bookmark set
  main -r @` succeeding as success and exits; it never notices that the pushed
  target is an empty, unpublishable commit. The failure only surfaces at
  `jj git push`, which is outside `integrate.sh`.
- **Coverage gap.** The `improving-vcs-skill` harness exercises conflict
  resolution heavily but the publish/land path lightly, so this defect was not
  caught by measurement — it was caught by hand.

## Suspected cause

`integrate.sh` models every land as a non-fast-forward merge (always create a
merge node, then move `main` to it). That is reasonable when `main` has moved
under concurrent work, but it is applied unconditionally, so the
already-ancestor case yields an empty, description-less merge. Two compounding
factors:

1. No fast-forward branch: the helper never checks "is `main` already an ancestor
   of `work`?" before forming the merge.
2. The formed merge carries no description, which jj's push safety (correctly)
   rejects — so even if a merge were desired, it would still need a message.

## Proposed fix

In the jj publish path, branch on whether a merge is actually needed:

1. **Fast-forward when linear.** Before `jj_form_merge`, test whether `main` is
   an ancestor of the work bookmark (e.g. `jj log -r "<work> & descendants(<main>)"`
   non-empty, or the equivalent `jj`/revset check). If so, land by moving the
   bookmark directly:

   ```sh
   jj bookmark set "$main_ref" -r "$work_ref"
   ```

   No merge commit, no empty working-copy detour, `main` lands on the real
   described work commit, and `jj git push` succeeds with no manual step.

2. **Only merge on real divergence.** Keep `jj new "$main_ref" "$work_ref"` for
   the case where `main` has advanced independently of the work. When that path
   runs, give the merge a description so it is pushable, e.g.:

   ```sh
   jj new "$main_ref" "$work_ref" -m "merge: integrate ${work_ref} into ${main_ref}"
   ```

   (Follow `COMMITS.md`: `Author:` trailer, and `Co-Authored-By:` when authored
   by an agent.)

3. **Validate the publish target.** Before declaring success in
   `jj_publish_loop`, assert the commit `main` now points at is non-empty *or*
   described — i.e. would pass `jj git push` — and fail loudly with a clear hint
   otherwise, instead of exiting and letting the push fail later out of band.

4. **Tidy on success.** After landing, ensure no orphaned empty merge/working-copy
   commits are left dangling above `main` (the post-land `jj new "$main_ref"` for
   the fresh working copy is fine; an empty *merge* parent is not).

## Acceptance criteria for a future fix

- Landing linear jj work produces a fast-forward: `main` moves to the work
  commit, no merge node is created, and `jj git push` succeeds with zero manual
  steps.
- When `main` has genuinely diverged, the helper forms a **described** merge that
  pushes cleanly and follows `COMMITS.md` trailer rules.
- `integrate.sh` never leaves `main` on an empty, description-less commit; if it
  cannot produce a pushable `main`, it exits non-zero with an actionable message.
- No orphaned empty merge/working-copy commits remain above `main` after a
  successful land.
- The `improving-vcs-skill` harness gains a publish/land assertion (linear land
  fast-forwards; diverged land merges-with-message) so this is caught by
  measurement, not by hand.

## Resolution

Fixed in `scripts/integrate.sh`. The jj land path now branches on whether a
merge is actually needed:

- **Fast-forward when linear.** `jj_work_contains_main` (`work & descendants(main)`)
  detects that `main` is already an ancestor of the work; when so, `jj_land`
  advances the bookmark directly (`jj bookmark set main -r <work>`) — no merge
  node, no empty working-copy detour, `main` lands on the real described commit.
- **Described merge only on divergence.** When `main` moved independently,
  `jj_land` forms `jj new main work -m "$(jj_merge_message)"`, where
  `jj_merge_message` emits a `chore(merge): …` subject with an `Author:` trailer
  per [COMMITS.md](../../.agents/skills/vcs/COMMITS.md), so it pushes cleanly.
- **Publish-target validation.** `jj_finish` calls `jj_is_pushable` and refuses
  to finish (exit 3, actionable message) if `main` would point at an empty,
  description-less commit, instead of letting `jj git push` fail out of band.
- **No orphans.** The fast-forward path never creates the empty merge/working-copy
  commits the bug left dangling above `main`.

Verified with the `improving-vcs-skill` harness on Claude Haiku: a single-agent
jj integrate round (linear work) now fast-forwards — `check-quality.sh` reports
`RESULT: PASS` with **0 merges** on `main` and `DEFAULT_OK=pass` (previously an
empty merge that `jj git push` rejected). The divergent-merge and `--continue`
paths were also confirmed to produce described, pushable merges.

## Reproduction from this session

1. In a colocated jj repo, isolate work: `bash scripts/isolate.sh <ide>-<work>`.
2. Commit linear work on top of `main` (here: a split into a transcript commit
   plus the substantive change), leaving `main` unmoved.
3. Run `bash scripts/integrate.sh <work>`; it forms `jj new main work` (empty
   merge) and sets `main` to it.
4. `jj git push --bookmark main` → rejected: "no description".
5. Recover manually: `jj bookmark set main -r <work-commit> --allow-backwards`,
   then push.
6. `jj log` shows the orphaned empty merge and working-copy commits above `main`.
