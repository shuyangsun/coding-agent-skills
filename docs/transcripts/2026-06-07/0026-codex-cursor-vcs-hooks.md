---
title: "Codex Cursor VCS hooks"
date: 2026-06-07
repo: "coding-agent-skills (jj workspace/bookmark `codex-cursor-vcs-hooks`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Codex Desktop (GPT-5, reasoning: high)"
summary: >-
  Added Cursor project hooks for the `vcs` skill, validated the guard behavior, then
  prepared the change for integration.
---

<!-- markdownlint-disable MD013 MD024 -->

# Codex Cursor VCS hooks

## User

Runtime context provided the repository instructions for `coding-agent-skills`: keep skills repo-agnostic, use `.agents/skills/` as the canonical skill home, preserve formatting with Bun/Prettier/markdownlint, and respect Git/Jujutsu hook setup.

## Assistant

Loaded the `vcs` skill, moved into the hook-created isolated jj workspace, and renamed the temporary workspace/bookmark from `codex-pending-dc48b6ac` to `codex-cursor-vcs-hooks`.

_Tool summary:_ Read `vcs/SKILL.md`; ran `rename-work.sh codex-cursor-vcs-hooks`; checked `jj status`.

## User

Asked whether the existing Claude and Codex hooks for the `vcs` skill could also be set up for Cursor, and asked Codex to work on it. The user explicitly allowed taking over the computer to test Cursor behavior and provided the `vcs` skill content.

## Assistant

Inspected the repo's current agent configuration and guard scripts. Found Claude and Codex hook wiring, existing Cursor permission files, and the shared `vcs-check.sh` policy. Checked Cursor hook documentation and local Cursor availability.

_Tool summary:_ Searched for Claude/Codex/Cursor hook config; read `.claude/settings.json`, `.codex/config.toml`, `.codex/rules/default.rules`, `.cursor/permissions.json`, `.cursor/cli.json`, `vcs-check.sh`, `session-start.sh`, and `vcs-state.sh`; checked local Cursor commands.

## Assistant

Implemented Cursor support by adding a Cursor hook adapter and project hook config:

- Added `.agents/skills/vcs/scripts/cursor-hook.sh`.
- Added `.cursor/hooks.json` with `sessionStart`, `beforeShellExecution`, `preToolUse`, and `afterFileEdit` hooks.
- Updated `session-start.sh` and `vcs-check.sh` usage text to recognize Cursor.
- Tightened `.cursor/permissions.json` and `.cursor/cli.json` so read-only VCS commands and vetted `vcs` helpers are allowed, while raw high-risk jj mutation commands are no longer broadly auto-approved.
- Documented the Cursor limitation in `vcs/ISOLATE.md`: Cursor project hooks can create/report `NEXT_CWD` and block risky actions, but cannot change the open Cursor folder automatically.

## Assistant

Validated the implementation. The local `cursor` command reported version `3.7.12`; no separate `cursor-agent` binary was available on PATH, so direct hook simulation was used.

_Tool summary:_ Ran shell syntax checks, JSON validation, targeted Prettier checks, and simulated Cursor hook payloads. The owned workspace allowed `jj describe`; the shared `default` checkout returned Cursor-compatible `permission: "deny"` JSON for a raw mutating jj command and for file-edit payloads.

## Assistant

Reported completion: Cursor support had been added and validated, with the note that whole-repo formatting/linting still failed on pre-existing unrelated docs/transcript issues.

## User

Asked to advance `main`, export the session, commit, and clean up using the `vcs` skill. The user also provided the current `vcs` and `export-coding-session` skill instructions.

## Assistant

Loaded the requested `vcs` and `export-coding-session` workflows. Opened `vcs/COMMITS.md` because a commit message would be authored. Reconfirmed the working copy changes and attempted to run the export index helper.

_Tool summary:_ `next-index.sh` was initially blocked by the Codex hook because the app-level hook evaluated the original shared checkout cwd for that writing command. Reopened a plain shell anchored in the owned workspace and reran `next-index.sh`, which assigned `docs/coding-sessions/2026-06-07/0026-codex-cursor-vcs-hooks.md`.

## Assistant

Exported this reconstructed transcript. The raw Codex log was readable but too noisy to commit safely without over-including large opaque tool payloads, so the transcript was reconstructed from the current thread with summarized tool calls and no sensitive raw payloads.
