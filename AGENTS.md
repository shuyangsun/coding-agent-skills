# coding-agent-skills

General-purpose, repo-agnostic skills for LLM coding agents (Claude Code, Cursor, Codex, Gemini, and others).

## Layout

- `skills/` — the canonical home for every skill. Each skill is one directory containing a `SKILL.md` plus any helper scripts. Add new skills here.
- `.agents/skills/` — agent-neutral runtime directory. Each entry symlinks to the matching directory under `skills/` (e.g. `.agents/skills/export-coding-session -> ../../skills/export-coding-session`).
- `.claude/skills` — symlinks to `.agents/skills` so Claude Code picks up the same set.

## Consuming this repo from another project

This repo is meant to be downloaded, copied, or added as a Git submodule, then symlinked into a host project's agent skill directory (under `.agents/` or `.claude/`). Because of that, skills must stay repo-agnostic:

- No hardcoded absolute paths, usernames, or assumptions about the host project's VCS or directory structure.
- Helper scripts resolve the working repo root themselves (Git → Jujutsu → current directory) and create any output directories they need, so they run correctly regardless of where `skills/` is symlinked from.
- Skills reference their own bundled scripts relative to the skill directory the runtime loaded, not a fixed `.agents/` or `.claude/` path, since either (or a different host-project path) may be the install location.
