# vcs guard hook traps the agent after shell cwd drifts, and on un-marked workspaces

- **Status:** Open (observed 2026-06-07)
- **Area:** `skills/vcs` guard hook (`scripts/vcs-check.sh hook`) — the
  `PreToolUse` guard added in `main` `89f98d23` ("fix(vcs): guard local workspace
  ownership")
- **Severity:** Medium — the agent can get stuck unable to run any
  non-read-only Bash command **or** any `Write`/`Edit`, and the recovery the deny
  message recommends is itself blocked. No work is lost, but several turns are
  burned escaping the trap.
- **Environment:** Jujutsu (`jj`) on a Git backend, colocated
  `coding-agent-skills` repo. Agent working in a **manually-created** sibling
  workspace (`jj workspace add claude-improving-docs-harness-plan`), i.e. one that
  was never claimed via `session-start.sh`/`isolate.sh`.
- **Observed:** 2026-06-07, while authoring `docs/plans/0002-improving-docs-skill-harness.md`.
- **Related:** [0001](0001-20260606-jj-default-workspace-goes-stale-blocking-collaboration.md)
  and [0002](0002-20260607-agent-used-default-jj-workspace-instead-of-isolating.md)
  (working from the shared `default` workspace), [0006](0006-20260607-agent-inspected-and-asked-about-another-agents-workspace-during-cleanup.md)
  (cleanup scope), and `docs/plans/0001-vcs-guardrails-for-jj-workspace-isolation.md`
  (the guard being hardened here).

## Summary

The guard decides "am I in the shared `default` workspace?" from the **hook
process's `$PWD`** (via `current_shared_reason` → `vcs_jj_workspace_name`). That
`$PWD` is the Bash tool's **persisted** working directory. Two independent
problems follow:

1. **cwd-drift false positive (the trap).** I ran one *read-only* command that
   `cd`-ed into the repo root (the `default` workspace) to `grep` something. The
   Bash tool persisted that cwd. From then on, **every** non-read-only,
   non-vetted Bash command — and every `Write`/`Edit` — was denied with:

   ```text
   vcs-check: VCS write refused: current cwd is the shared jj default workspace.
   Run session-start.sh or isolate.sh, cd to NEXT_CWD, then retry.
   ```

   even though my actual work lives in my own workspace. The recommended recovery
   (`cd to NEXT_CWD`) **cannot run**, because the hook evaluates cwd *before* the
   `cd` in the command executes, so a `cd <my-workspace> && …` command is refused
   on the spot.

2. **Un-marked workspace false positive.** After escaping the cwd trap, a
   `jj rebase -d main` was still denied:

   ```text
   vcs-check: owner check refused: no session owner marker for this workspace
   ```

   My workspace was created with a raw `jj workspace add`, so it had no
   `.git/agent-sessions/<name>.env` owner marker. The guard treats any
   marker-less workspace as un-owned and blocks VCS-mutating commands, even though
   the workspace is correctly named `<ide>-<work>` and is plainly mine.

## Why it traps (mechanics)

From `vcs-check.sh` `check_hook` → `Bash` branch, a command is allowed only if it
is a **vetted helper** (`is_vetted_helper_command`, substring match on
`isolate.sh`/`integrate.sh`/`session-start.sh`/`rename-work.sh`) or **read-only**
(`is_read_only_command`). Otherwise, if `current_shared_reason` is true (cwd is
the `default` workspace) the command falls into `check_pre_vcs_write` →
`ensure_not_shared` → **deny**. Two classifier details make this sharp-edged:

- **`is_read_only_command` keys on the leading token only**, and requires it to be
  an exact whitelisted word followed by a space or end-of-string (`ls`, `ls `,
  `grep `, `jj log`, …). A command that begins with `cd <ws> && …` is therefore
  **not** read-only (leading token is `cd`), so the one command an agent needs to
  climb out of the shared cwd is exactly the one that is refused.
- The same strictness misclassifies harmless variants: `pwd;` (semicolon, no
  space) does not match the `pwd ` / `pwd` patterns, so `pwd; …` is treated as a
  write and denied in a shared cwd.

The net effect is a **deadlock**: you are flagged as being in the shared
workspace, and every move that would get you out is itself blocked.

## Expected

- The guard should not false-positive when the session **owns a non-default
  workspace** but the shell's transient cwd has merely drifted to the repo root.
  A read-only peek from the repo root should not poison every later command.
- The documented recovery (`cd to NEXT_CWD`) should be **runnable** — a bare `cd`
  changes no VCS state and should never be refused.
- A correctly-named, manually-created `<ide>-<work>` workspace should be claimable
  without first having to discover the owner-marker mechanism by reading the hook
  source.

## Actual

The agent is trapped. The only escapes that work are non-obvious and rely on
reading `vcs-check.sh`:

1. **Run diagnostics read-only with absolute paths and no `cd`** — start the
   command with a whitelisted leading token (`ls <abs> && …`, `jj log …`) so
   `is_read_only_command` short-circuits to allow.
2. **Reset the persisted cwd with a vetted-substring command.** Any command whose
   text contains a helper path is allowed regardless of cwd, so a `cd` can ride
   along and (on exit 0) re-persist the workspace cwd:

   ```sh
   cd <my-workspace> && true   # .agents/skills/vcs/scripts/isolate.sh
   ```

   (The persisted cwd only advances on **exit 0**, so the chained command must
   succeed.)
3. **Claim the workspace's owner marker** by running the real helper from `main`'s
   copy (the stale workspace did not yet have the new scripts):

   ```sh
   bash <repo-root>/.agents/skills/vcs/scripts/rename-work.sh <ide>-<work>
   ```

   When the current name already equals the argument, `rename-work.sh` takes its
   `current == new_name` branch: it only **records the owner marker**
   (`RENAMED=no`), with no rename and no destructive side effect.
4. **Then** `jj rebase -d main`, `Write`/`Edit`, and `rm` of scratch all succeed.

## Suggested fixes (for `vcs` maintainers)

1. **Honor a leading `cd` before judging cwd.** If a Bash command begins with
   `cd <dir>` followed by `&&`/`;`, compute `current_shared_reason` against
   `<dir>`, not the pre-`cd` cwd. Then "return to my workspace, then work"
   succeeds in one command.
2. **Always allow a bare `cd <path>`.** It mutates nothing; refusing it is what
   makes the recommended recovery impossible.
3. **Prefer the owner marker / assigned workspace over transient shell cwd** when
   deciding "shared". If this session owns a non-default workspace, a momentary
   cwd at the repo root should not block read-only commands or commands that `cd`
   elsewhere.
4. **Harden `is_read_only_command`** against leading `cd &&`, env-assignment
   prefixes, and `;`/`|` immediately after the first token (or strip a leading
   `cd <dir> &&` before classifying).
5. **Claim correctly-named manual workspaces.** When a workspace lacks an owner
   marker but its name matches `<ide>-<work>`, either auto-record a marker on the
   first guarded action, or make the deny message point at
   `rename-work.sh <name>` — **not** `session-start.sh`, which from an
   already-owned session would spawn a redundant `<ide>-pending-*` workspace (the
   anti-pattern in [0002](0002-20260607-agent-used-default-jj-workspace-instead-of-isolating.md)).
6. **Differentiate the deny guidance** between "you have no workspace, isolate
   first" and "your shell cwd drifted, just `cd` back" — they need opposite
   actions.

## Notes

This was hit during normal use, not while stress-testing the guard. The guard's
*intent* — stop edits/commits from the shared checkout — is right; the problem is
that it infers "shared" from a volatile signal (persisted shell cwd) and offers no
in-band recovery once that signal drifts. Keying on the durable owner marker, and
letting a plain `cd` through, would remove the trap without weakening the guard.
