# vcs guard hook refuses every read-only Bash call after Claude Code resets shell cwd to the shared workspace

- **Status:** Fixed (implemented 2026-06-11)
- **Area:** `skills/vcs` guard hook (`.agents/skills/vcs/scripts/vcs-check.sh hook --agent claude`),
  `PreToolUse:Bash` branch — interaction with the Claude Code harness's per-call
  cwd reset.
- **Severity:** Low–Medium — no work is lost and no VCS state is at risk, but it
  imposes a constant tax: a `cd <workspace> && ...` prefix must be re-typed on
  **every** Bash call, and any call that forgets it burns a full tool round-trip.
- **Environment:** Jujutsu (`jj`) on a Git backend, colocated `coding-agent-skills`
  repo. Claude Code session that **already owns** an isolated jj workspace
  (`/home/ssun/developer/coding-agent-skills-claude-pending-94508a16`); the shared
  jj `default` workspace is `/home/ssun/developer/coding-agent-skills`.
- **Observed:** 2026-06-09, during a session running read-only diagnostics
  (`pgrep`, `curl`, `ss`, `nvidia-smi`) against the workstation RAG / LiteLLM
  endpoint.
- **Related:** [0008](../2026-06-07/0008-vcs-guard-hook-cwd-drift-and-missing-owner-marker-trap.md)
  (cwd-drift trap on the same hook; partially addressed since by
  `maybe_chdir_leading_cd`) and
  `docs/plans/0001-vcs-guardrails-for-jj-workspace-isolation.md` (the guard).

## Summary

Fixed in `.agents/skills/vcs/scripts/vcs-check.sh` and
`.agents/skills/vcs/scripts/vcs-state.sh`: the hook now evaluates relative actions
from the session's single live, agent-named workspace/worktree when no tool cwd is
provided, broadens read-only command-chain detection, and keeps explicit
shared-default writes denied. Regression probes covered the
`jj --version && git --version` chain, an `rg ... | head` pipeline, implicit
no-cwd writes routed to the owned workspace, explicit default-cwd writes denied,
and `find . -delete` denied.

The hook refuses a Bash command when the shell's cwd is the shared `default`
workspace and the session already owns an isolated workspace, with:

```text
PreToolUse:Bash hook error: [.../vcs/scripts/vcs-check.sh hook --agent claude]:
vcs-check: VCS write refused: current cwd is the shared jj default workspace, but
this session already owns an isolated workspace. Prefix the command with:
cd <your-workspace> && ... (or target an absolute path inside it).
```

That guard is correct for VCS/file writes. The friction is that the **Claude Code
harness resets the shell's cwd back to the shared `default` workspace
(`/home/ssun/developer/coding-agent-skills`) after every Bash tool call** — the
tool output ends with `Shell cwd was reset to /home/ssun/developer/coding-agent-skills`.
So the cwd is the shared workspace at the *start of every call*, regardless of any
`cd` from the previous call.

The result: even **purely read-only** commands that perform no VCS write and no
file write — `pgrep`, `curl`, `ss`, `nvidia-smi`, and similar — are refused,
because they are not on the hook's read-only allowlist and the cwd is shared. Each
such command must be manually prefixed with
`cd /home/ssun/developer/coding-agent-skills-claude-pending-94508a16 && ...`.
Forgetting the prefix wastes a full tool round-trip on a deny. This is pure
friction: the commands change nothing the guard is meant to protect.

## Steps to reproduce

1. In a Claude Code session, isolate into a workspace (so
   `vcs_session_owns_isolated_workspace` is true).
2. Run a read-only command that is **not** on the hook allowlist, e.g.
   `pgrep -af litellm` or `curl -s http://localhost:.../health` or `nvidia-smi`,
   **without** a `cd` prefix.
3. The harness's cwd is the shared `default` workspace at call start, so the hook
   denies the command with the "VCS write refused … already owns an isolated
   workspace" message above.
4. Re-run the same command prefixed with
   `cd /home/ssun/developer/coding-agent-skills-claude-pending-94508a16 && ...` —
   it now passes (the hook's `maybe_chdir_leading_cd` re-evaluates from the
   workspace dir). After the call, the harness resets cwd again, so step 2 repeats
   for the next command.

## Why it happens (mechanics)

In `vcs-check.sh`, the `Bash` branch of `check_hook` allows a command only if it
is empty, a vetted helper (`is_vetted_helper_command`), or read-only
(`is_read_only_command`). Otherwise the catch-all on this line sends it to the
write guard whenever the cwd is shared:

```sh
if is_vcs_mutating_command "$command" || is_file_mutating_command "$command" \
   || current_shared_reason >/dev/null 2>&1; then
  check_pre_vcs_write "$command"
```

`is_read_only_command` is a fixed leading-token allowlist:
`pwd`, `date`, `true`, `false`, `ls`, `rg`, `grep`, `sed -n`, `cat`, `head`,
`tail`, `wc`, `find`, and specific `git …` / `jj …` read subcommands. Diagnostic
tools like `pgrep`, `curl`, `ss`, `nvidia-smi`, `ps`, `lsof`, `df`, `free`,
`uname`, `env`, `which` are **not** on it. So when `current_shared_reason` is true
(cwd is the shared `default` workspace), any such command falls through to
`check_pre_vcs_write` → `ensure_not_shared` → **deny**, even though it mutates
nothing.

`maybe_chdir_leading_cd` (added after [0008](../2026-06-07/0008-vcs-guard-hook-cwd-drift-and-missing-owner-marker-trap.md))
already lets a `cd <ws> && ...` prefix re-point the cwd check, which is exactly
why the prefix works. The remaining friction is that the harness's per-call cwd
reset forces that prefix onto *every* call rather than letting an earlier `cd`
persist.

## Expected

A read-only command that performs no file write and no VCS write should be allowed
from the shared cwd without a workspace prefix — especially in a session that
already owns an isolated workspace, where the guard's write protection is not at
stake.

## Actual

Every non-allowlisted read-only Bash call is denied from the shared cwd and must
be re-issued with a `cd <workspace> && ...` prefix. Because the harness resets cwd
to the shared workspace between calls, the prefix cannot be set once; it must be
repeated on each call, and any omission costs a round-trip.

## Candidate remedies (discussion, not a decided fix)

These are options to weigh, not a chosen direction:

1. **Broaden / restructure the read-only classifier.** Allow-list more obviously
   read-only tools (`pgrep`, `ps`, `curl`, `wget`, `ss`, `lsof`, `df`, `free`,
   `nvidia-smi`, `uname`, `which`, `env` with no assignment, …), or invert the
   logic so a command is refused only when it is actually VCS- or file-mutating,
   rather than refused-by-default whenever the cwd is shared. The current
   `current_shared_reason`-as-catch-all is what pulls innocent reads into the
   write guard.
2. **Persist cwd between calls / honor `NEXT_CWD`.** If the Claude Code harness
   kept the shell's cwd across Bash calls (or honored a `NEXT_CWD`-style hint), a
   single `cd <workspace>` would hold and the prefix would not be needed per call.
   This is a harness-side change, not a `vcs` change.
3. **Improve the deny guidance.** At minimum, have the deny message note that,
   under the Claude Code harness, the cwd resets to the shared workspace between
   calls, so the `cd <workspace> && ...` prefix must be **re-applied on every
   command** — so the agent stops expecting an earlier `cd` to stick.

## Notes

The guard's intent — block edits/commits/writes from the shared `default`
checkout — is right and is not in question here. The issue is narrow: read-only
diagnostics get caught by the shared-cwd catch-all, and the harness's per-call cwd
reset turns the documented `cd`-prefix recovery into a per-command tax rather than
a one-time fix.
