<!-- markdownlint-disable MD013 MD024 -->

# Agent inspected (and asked about) another agent's workspace during a "clean up" request instead of scoping to its own changes

- **Status:** Open
- **Date:** 2026-06-07
- **Area:** Multi-agent etiquette; scope of "clean up" instructions; `vcs` cleanup behavior
- **Severity:** Medium — no data was lost (the agent correctly avoided deleting another agent's unmerged work), but it **over-reached the scope of the request**: it inspected a workspace that was clearly not its own, and then spent a user round-trip asking what to do about it. The default should have been to ignore it entirely.
- **Environment:** Jujutsu (`jj`) on a Git backend, colocated `coding-agent-skills` repo. A Claude Code (Opus 4.8) session that had just finished its own `vcs` work; a pre-existing, unrelated `codex-optimize-git-worktrees-vcs` jj workspace/bookmark also present.
- **Related:** [0005](0005-20260607-concurrent-cursor-agent-committed-and-pushed-another-agents-work.md) (the inverse: an agent acting *on* another agent's work). Both stem from the same root rule: an agent should touch only its own work.

## Summary

The user asked the Claude session to "clean up residual workspaces and
bookmarks." The session had created several `claude-*` workspaces/bookmarks
during its run; those were the residuals it owned. Instead of cleaning only
those, the agent **enumerated all workspaces, inspected the unrelated
`codex-optimize-git-worktrees-vcs` workspace** (created by a different agent in a
prior session), discovered it held unmerged work, and **asked the user** whether
to delete it.

The user clarified the expectation: "you didn't even need to check the codex
workspace, since that's clearly not your change. When I asked you to clean up,
you should by default assume I meant your changes only. You should only clean up
other agents' workspaces if I explicitly asked you to."

## Expected behavior

- "Clean up" with no further qualification means **the acting agent's own
  artifacts only** — here, the `claude-*` workspaces/bookmarks this session
  created. Those were in fact already removed during integration.
- Workspaces/bookmarks belonging to other agents (`codex-*`, `cursor-*`, etc.)
  are **out of scope by default**. The agent should not inspect them, reason
  about whether they're safe to delete, or ask about them.
- The agent touches another agent's workspace **only when the user explicitly
  names it** (e.g. "also delete the codex workspace").
- Net result that was expected: confirm the agent's own residuals are gone, leave
  everything else untouched, and report done — no user round-trip.

## Actual behavior

1. After landing its work, the agent ran `jj workspace list` / `jj bookmark
   list` and saw `codex-optimize-git-worktrees-vcs` alongside `default` and `main`.
2. It investigated that workspace's commit: ancestry vs `main`, remote backing,
   and `jj diff --stat` (finding ~543 lines of unmerged work).
3. It then asked the user, via a question prompt, whether to leave or delete the
   codex workspace.
4. The user had to spend a turn answering ("Leave it alone") and correcting the
   scope assumption.

The agent did get the **safety** call right — it refused to delete unmerged work
it didn't create and surfaced it rather than destroying it. The defect is purely
**scope**: it should never have looked at or raised the codex workspace at all.

## Why this matters

- **Wasted user round-trip.** A question that shouldn't have been asked cost the
  user a turn and attention.
- **Scope creep on a destructive verb.** Treating "clean up" as "clean up
  everything I can see" is dangerous; the same over-broad reading, with a less
  cautious agent, leads straight to deleting another agent's work (the harm in
  [0005], from the other side).
- **Cross-agent boundary.** Reinforces the core multi-agent rule: an agent reads
  and writes **only its own** workspaces/branches/commits unless told otherwise.
  Even *inspecting* another agent's workspace is unnecessary and presumes
  ownership it doesn't have.

## Suspected cause

1. **Literal, maximal reading of "residual."** The agent treated every
   non-`default`, non-`main` entry as a candidate "residual" rather than scoping
   to entries it created.
2. **No ownership filter.** It didn't filter the workspace/bookmark list to its
   own `claude-*` prefix before acting.
3. **Diligence misapplied.** Caution that's correct *if* something is in scope
   (don't delete unmerged work) was applied to something that was never in scope,
   producing an unnecessary question instead of a no-op.

## Proposed fix

- **Default scope = own artifacts.** Interpret unqualified "clean up" as the
  acting agent's own workspaces/bookmarks/branches (e.g. those matching its
  `<ide>-<work>` / `claude-*` naming), and nothing else.
- **Don't inspect what you don't own.** Do not enumerate-and-investigate other
  agents' workspaces during a cleanup; skip them silently.
- **Ask only to widen scope, not to narrow it.** Ask the user only if the cleanup
  scope is genuinely ambiguous *within the agent's own work* — never to request
  permission to touch another agent's artifacts (instead, just leave those alone).
- **Encode in `vcs`.** Add a one-line cleanup-scope rule to the `vcs` skill:
  "clean up only the workspaces/bookmarks you created; leave other agents' alone
  unless explicitly named."

## Acceptance criteria for a future fix

- Given "clean up residual workspaces and bookmarks" with other agents'
  workspaces present, the agent removes only its own and reports done — no
  inspection of, or question about, other agents' workspaces.
- The agent touches another agent's workspace only when the user names it.

## Reproduction

1. Have an agent finish a task in a repo that also contains another agent's
   workspace/bookmark (e.g. `codex-*`).
2. Ask it to "clean up residual workspaces and bookmarks."
3. Observe: it inspects the other agent's workspace and/or asks whether to delete
   it, instead of scoping to its own artifacts.
