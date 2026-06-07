<!-- markdownlint-disable MD013 MD024 -->

# Concurrent Cursor/Composer agent committed another agent's uncommitted work, bundled it with its own change, and pushed to shared `main`

- **Status:** Reopened (2026-06-07) — the failure mode **recurred during the
  fixing session** (a Claude Haiku sub-agent moved this repo's `main`; see
  [Update: recurrence](#update-2026-06-07-recurrence-during-the-fixing-session)),
  so partial `vcs`-skill mitigations are in place but the root cause is not closed.
- **Date:** 2026-06-07
- **Area:** Multi-agent etiquette in a shared checkout; `vcs` skill isolation invariant; cross-agent interference
- **Severity:** High — a second agent swept a first agent's **uncommitted, in-progress, not-yet-tested** edits into a commit the first agent did not author, gave it a generated message, **and pushed it to the public GitHub remote** (`origin/main`). The work happened to be correct, but nothing guaranteed that; this is silent, unreviewed publication of another agent's working tree.
- **Environment:** Jujutsu (`jj`) on a Git backend, colocated `coding-agent-skills` repo. Two agents operating in the **same `default` checkout at the same time**: a Claude Code (Opus 4.8) session actively editing the `vcs` skill, and a Cursor / Composer 2.5 session.
- **Related:** [0002](0002-20260607-agent-used-default-jj-workspace-instead-of-isolating.md), [0004](0004-20260607-benchmark-created-jj-workspace-but-never-used-it.md) (isolation failures); [0006](0006-20260607-agent-inspected-and-asked-about-another-agents-workspace-during-cleanup.md) (the inverse over-reach during cleanup).

## Summary

While a Claude Code session was midway through editing the `vcs` skill —
changes were **on disk but deliberately uncommitted**, because they were still
being written and tested — a **concurrent Cursor / Composer 2.5 session in the
same `default` checkout** snapshotted that working tree, committed it together
with its own unrelated change, authored a commit message describing work it did
not do, and **pushed the result to `origin/main`** on GitHub.

The Claude session only discovered this after the fact: its working copy was
unexpectedly clean and `origin/main` had advanced by a commit it never made.

## Expected behavior

An agent must commit and publish **only the work it itself performed**, and must
not absorb another agent's in-progress changes:

- If two agents share one checkout, each isolates first (the `vcs` rule), so
  their working trees don't overlap. Neither should `jj describe` / `git commit`
  a working copy that contains another agent's unstaged edits.
- An agent should never compose a commit message for, or take authorship of,
  changes it did not make.
- Publishing to a shared/public branch (`origin/main`) is an outward-facing,
  hard-to-reverse action; it must cover only the acting agent's reviewed work,
  not whatever else happens to be dirty in the checkout.

## Actual behavior

1. The Claude session had edited three files (`.agents/skills/vcs/scripts/integrate.sh`,
   `.agents/skills/vcs/scripts/isolate.sh`, `.agents/skills/vcs/SKILL.md`) and
   left them **uncommitted** on disk in the shared `default` workspace.
2. The Cursor / Composer 2.5 session, in that same checkout, created commit
   `b30c66a2` that bundled **two unrelated things**:
   - the Claude session's three uncommitted `vcs` edits, **plus**
   - the Cursor session's own change — a 118-line reorder of an unrelated
     transcript, `docs/coding-sessions/2026-06-07/0017-codex-vcs-script-first-jj-workspaces.md`.
3. It wrote a message describing the `vcs` work it did not author:

   ```text
   fix(vcs): fast-forward linear jj land and emit NEXT_CWD on isolate

   …
   Author: Shuyang Sun <shuyangsun10@gmail.com>
   Co-Authored-By: Composer 2.5 (Cursor) <cursoragent@cursor.com>
   ```

4. It **pushed `b30c66a2` to `origin/main`** (a real GitHub remote,
   `git@github.com:shuyangsun/coding-agent-skills.git`), publishing the Claude
   session's untested working tree.
5. It left the local `main` bookmark moved onto an empty commit (`ea6e6a09`),
   so the Claude session's local `main` was diverged from `origin/main`.

## Why this matters

- **Unreviewed publication.** The swept-in edits were mid-development and not yet
  tested when they were committed and pushed. They turned out correct only by
  luck; the mechanism would publish broken or half-written code just as readily.
- **False authorship / provenance.** The commit credits a model (Composer 2.5)
  and message to work another agent (Claude) actually did. Anyone reading history
  is misled about who changed what and why.
- **Bundled, unseparable changes.** Two logically distinct changes (a `vcs` fix
  and a transcript reorder) landed as one commit, so they can't be reviewed,
  reverted, or attributed independently without history surgery.
- **Public-history cleanup forced.** Recovering required rewriting an already-
  pushed commit on a public branch (force-push), which is destructive and risky —
  especially while the interfering agent may still be active.
- **Isolation invariant defeated.** This is the exact failure the `vcs` "isolate
  before you edit" rule exists to prevent, but from the *other* direction: it's
  not that the victim failed to isolate, it's that a co-located agent reached
  into the shared working copy and acted on changes that weren't its own.

## Suspected cause

1. **Both agents in the shared `default` checkout.** Neither isolated into its
   own workspace, so one `jj` snapshot captured the union of both agents' edits.
2. **"Commit everything dirty" behavior.** The Cursor agent committed the entire
   working-copy state (`jj` auto-snapshots the whole tree) rather than scoping to
   the files it touched, so it could not tell its own change from the neighbor's.
3. **Auto-push to `main`.** The agent published to a shared/public branch as part
   of its routine finish, without confirming the commit contained only its work.
4. **No working-tree ownership check.** Nothing made the agent notice that most
   of the staged content (the three `vcs` files) was authored by a different
   active session.

## Proposed fix

- **Isolate, always — enforced, not advisory.** Co-located agents must each work
  in their own `jj` workspace / `git` worktree (the `vcs` rule). A pre-commit
  guard that refuses to commit from `default`/shared when the tree is dirty with
  files outside the agent's declared scope would prevent the sweep.
- **Scope commits to own changes.** When committing in a possibly-shared
  checkout, restrict to the specific paths the agent edited (e.g. `jj` filesets /
  `git add <paths>`), never "commit the whole dirty tree."
- **Never author for others.** Don't generate messages or take `Co-Authored-By`
  credit for changes the agent didn't make; if the working tree contains
  unexplained edits, stop and surface them rather than committing them.
- **Gate publication.** Before pushing to a shared/public branch, verify the
  commit's diff is entirely the acting agent's work; bail loudly otherwise.

## Acceptance criteria for a future fix

- A second agent running in a shared checkout cannot commit or push a first
  agent's uncommitted edits; at minimum it stops and surfaces the foreign changes.
- Commits contain only the acting agent's own work, with accurate authorship.
- No agent auto-pushes a bundle of unrelated changes to `origin/main`.
- Distinct logical changes land as distinct commits.

## Partial mitigations so far (NOT a fix)

These reduce blast radius but do **not** close the root cause — an agent can still
reach into a checkout/refs that aren't its own. Kept here for traceability; the
issue stays open.

- **SKILL.md §4 "Touch only your own work".** "Commit and publish only your own
  changes. Never `jj describe` / `git commit -a` a shared checkout's whole dirty
  tree, and never push a commit that bundles edits you didn't make. If the working
  copy holds changes you don't recognize, **stop and surface them** — don't sweep
  them into your commit or take authorship."
- **Helpers scope by construction.** `integrate.sh` lands only the branch/bookmark
  you **name** onto `main`, never the live working tree.
- **Isolate-before-you-edit** (§2, measured by the harness `ISOLATED` start-round
  metric) remains the primary defense — and is exactly what made the recurrence
  below recoverable.

These are advisory/affordance changes. Nothing yet **prevents** a process from
running `jj`/`git` against a repo it doesn't own, which is the actual mechanism in
both the original report and the recurrence below.

## Update (2026-06-07): recurrence during the fixing session

The same failure mode happened again **while this very issue was being worked on**,
which is why the issue is reopened rather than closed.

- **Context.** A Claude (Opus) session was editing the `vcs` skill on the colocated
  `coding-agent-skills` repo, with its in-flight work isolated on a
  `claude-vcs-issues-567` bookmark in the `default` workspace. It launched the
  `improving-vcs-skill` harness as a background **workflow** that spawned 10 Claude
  **Haiku** integration sub-agents, each meant to operate only inside its own
  throwaway sandbox under `$TMPDIR/vcs-harness-haiku/round-*/ws-agent-*`.
- **What went wrong.** One sub-agent ran `jj` commands against the **real**
  `coding-agent-skills` checkout instead of (or before `cd`-ing into) its sandbox
  workspace — the documented **sub-agent cwd-hazard**: Agent-tool/workflow
  sub-agents inherit the parent's real-repo cwd. The op log shows, ~9–11 minutes
  into the run, `point bookmark main → <claude-vcs-issues-567 commit>`, then two
  `new empty commit` ops, then `point bookmark main → <empty commit>`. Net effect:
  local `main` was advanced **onto another agent's in-flight work plus empty
  commits** — the same "act on a checkout/work that isn't yours" defect as the
  original Cursor incident, here via a colocated background sub-agent rather than a
  second IDE.
- **Why it was recoverable (and what that confirms).** Damage was contained
  entirely to *local* refs: `main@origin` was never moved and **nothing was
  pushed**. Because the victim work was already isolated on its own named bookmark,
  recovery was exact — `jj bookmark set main -r main@origin --allow-backwards` plus
  abandoning the stray empty commits restored the correct state with no work lost.
  This is the difference from the original report, where the swept-in work was
  pushed to public `origin/main`: **isolation + not auto-pushing is what turned a
  potential silent publication into a clean local rollback.**
- **What this proves about the fix.** The advisory rules above govern how an agent
  *should* treat its own commits, but they cannot stop a sub-agent that simply
  starts in the wrong directory. The missing piece is a **mechanical** guard:
  sub-agents must be pinned to their sandbox (e.g. `cd` enforced / `-R`/`-C`
  required / refuse VCS writes when cwd is outside the assigned workspace), and the
  orchestrator should detect a sub-agent that mutated refs outside its sandbox. See
  the memory note "vcs harness subagent cwd hazard". Until such a guard exists,
  this class of cross-agent interference remains open.

## New acceptance criteria (from the recurrence)

- A spawned sub-agent cannot move bookmarks/branches or commit in a repository
  outside its assigned workspace; a VCS write attempted from a cwd outside the
  sandbox fails loudly instead of mutating the host repo.
- The harness/orchestrator surfaces (and ideally blocks) any sub-agent operation
  that touches refs outside its sandbox path.

## Reproduction

1. In one shared colocated checkout, have Agent A begin editing files and leave
   them uncommitted on disk.
2. Concurrently, have Agent B (a different tool/session) run its
   commit-and-publish flow in the same checkout.
3. Observe: Agent B's commit contains Agent A's uncommitted edits plus B's own,
   under a message B authored, and B pushes it to the shared branch.

## How it was resolved this session (for reference)

The Claude session, with the user's explicit approval to rewrite public history,
used `jj split --ignore-immutable` to break `b30c66a2` into two clean commits —
`fix(vcs): …` (the `vcs` work, re-authored with the correct Claude trailer) and
`docs(coding-sessions): …` (the 0017 reorder, kept attributed to Cursor) — then
force-pushed (jj lease-protected). The bundled commit no longer exists on
`origin/main`. This recovery only worked because the swept-in code was, in
hindsight, correct; the underlying interference must not recur.
