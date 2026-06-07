# VCS guardrails for jj workspace isolation

- **Status:** Plan only; no implementation in this pass
- **Date:** 2026-06-07
- **Working workspace:** `codex-vcs-guardrails`
- **Primary issues:** [0002](../issues/0002-20260607-agent-used-default-jj-workspace-instead-of-isolating.md), [0004](../issues/0004-20260607-benchmark-created-jj-workspace-but-never-used-it.md), [0005](../issues/0005-20260607-concurrent-cursor-agent-committed-and-pushed-another-agents-work.md)

## Problem

The current `vcs` skill has the right rule, but the damaging failures happen
before the agent reliably applies the rule:

- A parent agent starts in a local jj repo's `default` workspace and begins
  reading/editing there instead of isolating first.
- An agent runs `isolate.sh`, but treats workspace creation as a completed
  checklist item and keeps working from the original checkout.
- Harness or IDE sub-agents inherit the parent cwd and run jj commands against
  the real repo instead of their assigned sandbox.
- Permission settings currently allow high-risk VCS writes such as
  `jj bookmark ...`, `jj describe ...`, and `jj git push ...` broadly enough
  that a wrong-cwd agent can still move shared refs or publish.

A standalone `vcs-check.sh` called from other `vcs` scripts would help only
after the agent already remembered to call a `vcs` script. It does not solve the
session-start chicken-and-egg failure by itself.

## Evidence

The local `jj op log` shows the signatures to treat as suspicious when they run
from `default@` during agent/harness work:

- `jj bookmark set main -r @`
- `jj new main`
- `jj describe ...`
- `jj git push --bookmark main`
- `jj bookmark delete <other-work-ref>`
- `jj workspace forget <other-workspace>`
- recovery-only operations such as `--allow-backwards`, `--ignore-immutable`,
  `jj split`, and `jj abandon`

Those commands are not inherently bad. They are high-risk when executed from the
shared host checkout, or when the acting session is not the owner of the work ref.

Tool documentation checked for feasibility:

- Claude Code supports project hooks in `.claude/settings.json`; the current
  official hook lifecycle includes `SessionStart`, `PreToolUse`,
  `SubagentStart`, `CwdChanged`, and related events. See
  <https://code.claude.com/docs/en/hooks>.
- Claude Code permission rules support explicit allowed/disallowed tools and
  `--disallowedTools`. See <https://code.claude.com/docs/en/cli-usage>.
- Codex supports project-local `.codex/config.toml` only for trusted projects,
  and can load project-local hooks/rules from `.codex/`. See
  <https://developers.openai.com/codex/config-advanced>.
- Codex hooks include `SessionStart`, `PreToolUse`, `SubagentStart`, and
  `PermissionRequest`; hook commands run with the session cwd. See
  <https://developers.openai.com/codex/hooks>.
- Codex execpolicy rules can return `allow`, `prompt`, or `forbidden`; the most
  restrictive matching rule wins. See <https://developers.openai.com/codex/rules>.

## Proposal

Use layered mechanical enforcement. The goal is that forgetting `vcs` becomes
hard to act on, not just easy to diagnose later.

User decisions for this plan:

- Always create a new local workspace at session start. The risk of stale
  abandoned workspaces is acceptable compared with the risk of editing `default`.
- Direct `jj git push` and `git push` should remain allowed by default for speed.
  Guard them mechanically by cwd/workspace ownership instead of adding human
  approval prompts.
- Cloud/PR-session opt-outs are out of scope for now. Focus on local multi-agent
  workspaces.

### 1. Add a session-start bootstrap, not just a script-call guard

Add a new `vcs` helper, tentatively
`.agents/skills/vcs/scripts/session-start.sh`, designed for agent startup hooks:

- Detect mode exactly like `vcs`: prefer jj when `.jj`/`jj root` exists.
- In a local jj repo, always create a temporary per-session workspace
  immediately, before the agent has enough context to name the task. If the agent
  starts in `default`, this moves it away from the shared checkout before any
  edit. If the agent starts in a non-`default` workspace, this still creates a
  fresh workspace so ownership is unambiguous.
- Use a neutral temporary name such as `<ide>-pending-<shortid>` or
  `<ide>-session-<shortid>`, create a same-name bookmark, and print `NEXT_CWD`.
- Record a small owner/session marker in an ignored or local-only place inside
  the new workspace so later guards can tell which workspace belongs to this
  session.
- If workspace creation is impossible, fail loudly before any repo edit. Stale
  abandoned workspaces are acceptable; silent shared-checkout edits are not.
- In Git-only repos, either no-op or create a Git worktree only when the hook can
  tell this is a local shared checkout. Do not rely on IDE Git worktree features
  for jj repos.

Owner-marker design:

- Store session ownership in local VCS admin state, never in the tracked
  worktree. For Git and colocated jj-on-Git, use the common Git admin dir:
  `$(git rev-parse --git-common-dir)/agent-sessions/<workspace>.env`.
- For a non-colocated jj repo without a Git admin dir, fall back to
  `$XDG_STATE_HOME/coding-agent-skills/vcs-sessions/<repo-hash>/<workspace>.env`
  (or `$HOME/.local/state/...` when `XDG_STATE_HOME` is unset).
- The marker should contain `session_id`, `agent_id`, `workspace_name`,
  `workspace_root`, `work_ref`, `parent_repo_root`, `created_at`, and
  `skill_version`.
- `vcs-check.sh` reads this marker to decide whether a write/publish operation is
  from the workspace this session owns. Missing marker means "not owned" for
  write and publish checks.

Then add a rename helper for the post-context step:

- `rename-work.sh <ide>-<work>` uses `jj workspace rename` and
  `jj bookmark rename` for the temporary session workspace.
- It refuses to rename `default` and refuses names that do not match
  `<ide>-<work>`.
- `isolate.sh` can call or share logic with this helper, but the startup helper
  must be usable independently by hooks.

This handles the "I do not know the work slug yet" gap without letting the agent
stay in `default` while it gathers context.

### 2. Wire the bootstrap through Claude and Codex hooks

Add project-local hook configs after verifying exact syntax against current docs:

- Claude Code: `SessionStart` hook runs the bootstrap and emits visible context
  if `NEXT_CWD` is produced. `PreToolUse` hook blocks `Edit`, `Write`, and
  mutating `Bash` commands when cwd is a jj `default` workspace. `SubagentStart`
  and `CwdChanged` hooks re-check that background agents are inside their
  assigned workspace.
- Codex: project-local `.codex/hooks.json` or inline `.codex/config.toml` hook
  equivalents. `SessionStart` runs the bootstrap; `PreToolUse` blocks file edits,
  `apply_patch`, and mutating VCS commands from `default`; `SubagentStart` checks
  cwd. Because project-local Codex hooks only load in trusted projects, keep the
  `AGENTS.md`/skill instruction as the fallback for untrusted projects.

The hook should fail closed for edits and VCS writes, but stay quiet for read-only
commands. Context gathering can continue, but file changes and shared-ref writes
cannot happen from `default`.

### 3. Add a real `vcs-check.sh`, but use it as the second line of defense

Add `.agents/skills/vcs/scripts/vcs-check.sh` with subcommands such as:

- `vcs-check.sh pre-edit`
- `vcs-check.sh pre-vcs-write`
- `vcs-check.sh pre-publish`
- `vcs-check.sh assert-owner <work-ref>`

Expected checks:

- Refuse `pre-edit` in jj `default` unless an explicit override env var is set
  for documented read-only or cloud/PR cases.
- Refuse `pre-vcs-write` in `default` for commands that move refs, create commits,
  describe commits, delete/forget workspaces, abandon commits, or export/push.
- Refuse `pre-publish` unless the current workspace is non-`default`, the current
  bookmark/workspace matches the acting session's owner marker, and the diff is
  limited to known session-owned files.
- Allow `integrate.sh`'s deliberate cleanup paths only through explicit helper
  context, not arbitrary manual commands.

Then call it at the start of `isolate.sh`, `integrate.sh`, and any future helper
where it makes sense. This does not solve missed skill loading, but it prevents
the helpers from becoming bypasses.

### 4. Tighten agent permission settings around dangerous VCS writes

Current repo settings are too permissive for the failure in issue 0005:

- `.claude/settings.json` allows `Bash(jj describe *)`, `Bash(jj new *)`,
  `Bash(jj bookmark *)`, and implicitly leaves push-like commands to prompts.
- `.codex/rules/default.rules` currently allows `git push` and `jj git push`
  outright in trusted local Codex sessions.

Plan for permission posture:

- Allow read-only VCS commands: `jj status`, `jj log`, `jj diff`, `jj show`,
  `jj workspace list`, `git status`, `git log`, `git diff`.
- Allow direct `jj git push` and `git push` by default for local sessions, but
  have hooks/guards deny them when cwd is `default`, outside the session-owned
  workspace, or when the commit/ref being published is not session-owned.
- Allow the vetted helpers: `bash .agents/skills/vcs/scripts/isolate.sh ...`,
  `bash .agents/skills/vcs/scripts/integrate.sh ...`,
  `bash .agents/skills/vcs/scripts/session-start.sh ...`.
- Prompt or forbid direct high-risk commands unless issued by a helper:
  `jj describe`, `jj new`, `jj bookmark set/delete/move/rename`, `jj workspace
forget`, `jj abandon`, `jj split`, `git reset`, `git checkout`, `git switch`,
  `git branch -D`.
- Do not add a human-approval prompt for ordinary pushes. The enforcement target
  is "pushes are fast from the right workspace and impossible from the wrong
  workspace."

Where a tool cannot express "allowed only when called by helper", use hooks to
inspect the actual command/cwd and permission rules to make direct dangerous
forms prompt or forbidden. Push commands are the carve-out: permission rules may
allow them, but hooks must still block wrong-cwd or wrong-owner pushes.

### 5. Make the improving harness test the real failure modes

Extend `improving-vcs-skill` with tests that measure the parent/hook problem,
not just synthetic sub-agent start rounds:

- Add a `--task parent-start` or equivalent scorer that creates a real host repo,
  launches the agent in `default`, asks it to gather context and write a plan, and
  fails if any tracked repo file changes before an `add workspace` op.
- Add a hook-enabled start round that verifies `SessionStart` creates a temporary
  workspace before the agent edits.
- Add a "wrong cwd sub-agent" round: the orchestrator assigns a sandbox path but
  starts the lower-tier agent from the host repo. The expected result is a hook or
  guard denial before any host-repo `jj bookmark set main`, `jj describe`,
  `jj new main`, or `jj git push`.
- Add an op-log audit scorer that fails when suspicious write ops happen in a
  repo path outside the assigned sandbox.
- Add metrics lines separate from existing `ISOLATED`: `PARENT_ISOLATED`,
  `HOOK_BLOCKED_DEFAULT_WRITE`, `CWD_GUARD_OK`, and `HOST_REPO_MUTATIONS`.

Keep using lower-tier models for this because the point is not whether a frontier
model can infer the rule. The bar should be that a small/cheap model cannot make
the damaging mistake even when it forgets the instruction.

## Baseline validation run

I ran one current-baseline `improving-vcs-skill` start round with a lower-tier
agent:

```text
new-sandbox.sh --mode jj --task start --start-from main --round 7002
model: gpt-5.4-mini, reasoning: low, tier: small
```

Objective results:

```text
ISOLATED=pass
ISO_FS=pass
NAME_OK=pass
RESULT: PASS
STALE_REFS=0
ORPHAN_WS=0
ORPHAN_DIRS=0
ORPHAN_EMPTY_HEADS=0
```

The agent created `codex-streaming-export` and landed the tiny change correctly.
This confirms the current `vcs` skill can guide a small model through the happy
path when the harness prompt tells it to load `vcs` and starts it in the sandbox.
It does **not** prove the issue is fixed: the open failure is when the parent
agent or a spawned sub-agent starts acting before it applies `vcs`, or starts in
the wrong cwd. The next validation must target those paths directly.

## Implementation sequence

1. Build `session-start.sh` and `rename-work.sh`; test manually in a disposable
   jj repo and Git-only repo.
2. Add `vcs-check.sh` and wire it into existing helpers.
3. Update Claude and Codex hook configs to call the guard, keeping exact syntax
   verified against current official docs.
4. Tighten `.claude/settings.json` and `.codex/rules/default.rules` so direct
   dangerous VCS writes prompt/deny while helper commands remain allowed; keep
   `jj git push` and `git push` allowed, with hook/guard enforcement for cwd and
   ownership.
5. Add harness parent-start and wrong-cwd sub-agent scenarios.
6. Re-run lower-tier validation across jj start, Git start, hook-enabled
   parent-start, and wrong-cwd sub-agent rounds. Keep changes only if lower-tier
   agents cannot mutate `default` or the host repo, and existing integration
   quality/hygiene metrics stay green.

## Deferred questions

- How should cloud/PR sessions opt out? Deferred; this plan intentionally focuses
  on local jj/Git multi-agent workspaces first.
- How aggressive should stale temporary workspace cleanup be? Deferred; stale
  abandoned workspaces are acceptable until the isolation failure is mechanically
  closed.
