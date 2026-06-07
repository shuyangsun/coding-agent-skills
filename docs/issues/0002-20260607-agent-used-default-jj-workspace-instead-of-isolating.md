<!-- markdownlint-disable MD013 MD024 -->

# Agent used `default` jj workspace instead of isolating first

- **Status:** Open
- **Date:** 2026-06-07
- **Area:** `skills/vcs` adherence; affects agent sessions doing repo edits in a jj repo
- **Severity:** Medium — work landed in the shared workspace, defeating the local parallel-agent safety rule even though no collision was observed in this session
- **Environment:** Jujutsu (`jj`) on a Git backend, colocated repo, `default` workspace on `main`

## Summary

During the `vcs` skill optimization session, the agent made repository edits
directly in the `default` jj workspace instead of first creating its own per-agent
workspace. This violated the `vcs` skill's intended local parallel-agent workflow:
detect jj, isolate into a named workspace (`<ide>-<work>`), do the work there,
then integrate back onto shared `main`.

This issue documents the behavior only. It was not fixed in the same session.

## Expected behavior

At the start of a repo-editing task in a local jj repo, the agent should:

1. Detect jj mode before changing files (`jj root` succeeds).
2. Create or move into a dedicated jj workspace named `<ide>-<work>` unless it is
   already in a non-`default` workspace.
3. Make edits in that isolated workspace.
4. Integrate the work onto `main`, then clean up the workspace/bookmark as the
   `vcs` skill prescribes.

For this session, an appropriate workspace name would have been something like
`codex-vcs-script-first` or `codex-vcs-jj-helpers`.

## Actual behavior

The agent edited the repo directly from the `default` workspace. A later check
showed only the default workspace registered:

```text
$ jj workspace list -T 'name ++ "\t" ++ root ++ "\n"'
default    .
```

The working copy changes were also on `@` in `default`:

```text
Working copy changes:
M .agents/skills/vcs/INTEGRATE.md
M .agents/skills/vcs/ISOLATE.md
M .agents/skills/vcs/SKILL.md
A .agents/skills/vcs/scripts/conflict-preview.py
A .agents/skills/vcs/scripts/integrate.sh
A .agents/skills/vcs/scripts/isolate.sh
```

No separate jj workspace was created for the session.

## Why this matters

The `default` workspace is shared coordination surface in this repo. Editing
there directly reintroduces the same local collision risk that the `vcs` skill is
supposed to prevent:

- another local agent or teammate could also use `default`;
- generated files, build artifacts, branch/bookmark changes, and working-copy
  state can interfere across agents;
- later cleanup/retirement metrics do not help if the work was never isolated in
  the first place.

This is especially important because the session was specifically improving
`vcs` to make jj workspaces faster and safer; the agent failed to follow the
workflow it was changing.

## Suspected cause

The agent loaded and followed the `improving-vcs-skill` harness, but did not
apply `vcs`'s session-start isolation rule to its own workspace before authoring
changes. The task centered on editing the `vcs` skill itself, and the agent
treated the existing checkout as the working area rather than first isolating.

This suggests a meta-workflow gap: when authoring or testing a VCS skill, the
agent may focus on the harness instructions and forget that ordinary repo-edit
work should still begin with workspace isolation.

## Reproduction from this session

1. Start in a jj repo where `jj workspace list` shows only `default`.
2. Ask the agent to modify files under `.agents/skills/vcs/`.
3. Agent edits files directly.
4. Ask whether it is in a different jj workspace.
5. Agent checks `jj workspace list` and confirms it has been using `default`.

## Acceptance criteria for a future fix

- A coding agent applying repo edits in a local jj repo creates or uses a
  non-`default` jj workspace before changing files.
- If the agent intentionally cannot isolate, it states why before editing.
- A future harness or checklist catches "edited in `default`" as a failure for
  local jj repo-editing sessions, not just for synthetic `--task start` rounds.
- Documentation distinguishes harness sub-agents under test from the parent agent
  authoring `vcs`: both need clear workspace rules, but the parent currently has
  no enforced guard.
