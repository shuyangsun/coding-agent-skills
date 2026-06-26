---
title: "Agent permission settings across Claude Code, Codex, Cursor, and Antigravity"
date: 2026-06-06
repo: "coding-agent-skills (jj change `knmqwnroyvvt`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Opus 4.8, 1M context, effort: max)"
summary: >-
  Built a checked-in Claude Code `settings.json` permission policy, simplified it, then
  mirrored the same allow/deny/prompt posture into Codex, Cursor, and Antigravity configs
  — researched via parallel subagents and verified against primary docs. Finally reworked
  the accompanying skill from a static snapshot into a reusable, intent-focused procedure
  (`update-agent-permissions`), and repaired an externally-corrupted ignore file.
---

<!-- markdownlint-disable MD013 MD024 -->

# Agent permission settings across Claude Code, Codex, Cursor, and Antigravity

## User

(`/clear`)

Read Claude local settings and this project. Based on your understanding, add common safe commands that were used or will be needed in the future to a Claude settings file that can be checked in and used safely by other people who clone this repository. Search the internet for Claude's latest security setting recommendations, it may have changed.

## Assistant

Explored the repo and the current settings, then researched the latest guidance before writing anything.

- Inspected `.claude/` — found only `.claude/settings.local.json` (gitignored via `*.local.json`) and a `skills` symlink. There was no checked-in `settings.json`.
- Read `AGENTS.md` (repo is a collection of repo-agnostic agent skills; toolchain is Bun + Prettier + markdownlint + lefthook + git/Jujutsu).
- Web search + fetched the official **Configure permissions** docs. Key 2026 points: rules evaluate **deny → ask → allow** (deny wins); read-only commands (incl. read-only `git`) are auto-allowed; aggressively **deny secret reads**; prefer **denying `curl`/`wget`** and routing fetches through `WebFetch` domain allowlists; Bash wildcards use a space word-boundary.

Created `.claude/settings.json` (checked-in) with a `$schema`, an `allow` list (scoped bun/git/jj subcommands + `WebSearch`/`WebFetch` to doc domains) and a `deny` list (secret reads, `curl`/`wget`). Verified valid JSON, not gitignored, and Prettier-clean.

## User

(`/effort max`)

Does it need to be that long? Can't we simplify it a bit more?

## Assistant

Yes — most of it was redundant.

- Dropped every read-only rule (Claude Code auto-allows `ls`/`cat`/`grep`/read-only `git`).
- Collapsed bun verbs and the secret denies (one gitignore-style `Read(.env*)` covers `.env`, `.env.local`, `.envrc` at any depth).
- First attempt used blanket `Bash(git *)` / `Bash(bun *)` — the **auto-mode classifier blocked the write**, because a single wildcard silently authorizes `git push --force`, `git clean -fdx`, `bun <arbitrary-file>`. Good guardrail, and it settled the trade-off.
- Rewrote with **scoped safe subcommands** instead; `git push`/`reset`/`rm` and the like intentionally still prompt. `curl`/`wget` stay denied.

Result: cut from ~36 allow + 24 deny down to **18 allow + 9 deny**, verified Prettier-clean.

## User

(`/effort ultracode` then `/effort` → max)

Great! Lookup the internet to check how to configure it for the following agentic-coding tools: GPT Codex, Antigravity, and Cursor. Settings may have changed, so make sure you understand the latest standards first. Add files to also enable the same or similar permission levels for these IDEs. Once you're done, encapsulate your research and permission level summary into `.agents/skills/agent-permission-settings/SKILL.md`. Do NOT put it in the `skills/` directory, this skill is only meant to be used by this repository only, not something other people should link to by default when using this repo.

## Assistant

Inspected the skill directory layout (existing entries under `.agents/skills/` are symlinks into `skills/`; created the new one as a **real** directory so it stays repo-local but is still discovered via `.claude/skills → .agents/skills`).

Because exact config syntax for these fast-moving tools matters (Antigravity is brand new), fanned out **three parallel research subagents** (Codex, Antigravity, Cursor), each instructed to quote official docs, cite URLs, and flag recency/uncertainty. Then **verified the riskiest claims myself** before writing:

- The agents' Codex report claimed repo-local `.codex/config.toml` + Starlark `prefix_rule` rules; the aggregated `llms-full.txt` appeared to deny both. Fetching `config-advanced` and `rules` directly **confirmed both are real** (the summarized file had a false-negative).
- Confirmed Antigravity's exclusion file: `.aiexclude` is the Google-standard cross-product file; `.antigravityignore` is the native variant — both gitignore-syntax.

Wrote the config files, mirroring the Claude posture into each tool's native mechanism:

- **Codex** — `.codex/config.toml` (`approval_policy = on-request`, `sandbox_mode = workspace-write`, `network_access = false`) and `.codex/rules/default.rules` (`forbid` `rm -rf`/`curl`/`wget`, `prompt` pushes).
- **Cursor** — `.cursor/cli.json` (Claude-style `allow`/`deny`), `.cursor/permissions.json` (IDE allowlist + classifier block-instructions), `.cursorignore`.
- **Antigravity** — `.aiexclude` and `.antigravityignore` (secret exclusion). Command allow/deny is GUI-configured and the committable `.antigravity/settings.json` schema is unverifiable, so I **documented** it rather than fabricate a file.
- **Reference** — `.agents/skills/agent-permission-settings/SKILL.md`.

Fixed markdown table alignment (Prettier) so markdownlint passed (0 errors), confirmed full-repo `format:check` clean, and that nothing was gitignored. Flagged the three honest caveats: Antigravity has no committed permission file; enforcement layers differ in strength (hard sandbox/deny vs. soft classifier/ignore hints); Codex needs folder-trust and has no per-file read denylist.

## User

For the skill, focus on the intent. I want to run it in the future if current IDE settings change, or another future IDE comes into the market. It will be used to update these permission settings, so maybe another name that's more concise and focused on adding / updating permission settings is better. Focus on the methodology — understand repo context first, then spin up subagents to do research, then update settings file. Do not have too many hardcoded information that can be outdated in the future, that defeats the purpose. Commands ran in this repo can also expand in the future, do not hardcode specific commands. Use your best judgement on what will likely be dynamic in the future, focus on intent and outcome, not the specific requirement. Modify the skill based on above feedback.

## Assistant

Reworked the skill from a static snapshot into a reusable procedure, renamed `agent-permission-settings` → **`update-agent-permissions`**.

- **Kept (durable):** the three-bucket intent (allow safe dev / deny secret-reads + shell net-exfil / prompt outward+destructive) stated at the category level; a 4-step method (understand the repo & _derive_ specifics → research current tool docs via parallel subagents & verify load-bearing syntax → translate posture into each tool's native config → verify); and judgment principles.
- **Stripped (perishable):** command lists, per-tool syntax, version numbers, file tables, source URLs — all re-derived each run. The config files stay as the output and are self-documenting via header comments.

While doing this, a system notice revealed `.antigravityignore` had been **externally corrupted** — its glob patterns were markdown-escaped (`.env.*` → `.env._`, `**/*.pem` → `\*\*/_.pem`), which silently breaks the secret-exclusion. Diagnosed it: the identical-content `.aiexclude`/`.cursorignore` were untouched, so **prettier wasn't the cause** — something keyed to the `.antigravityignore` filename (likely Antigravity itself or an editor extension). Repaired the file, confirmed the fix at the byte level with `od -c` (real UTF-8 em-dash + clean ASCII globs), and added the gitignore-syntax/Starlark files to `.prettierignore` as defensive hygiene. Removed the old skill directory.

Verified: `format:check` and `lint:md` both clean; new skill discoverable; full change set intact. Saved a memory capturing the "intent/method over hardcoded specifics" authoring preference. Offered to drop `.antigravityignore` in favor of `.aiexclude` if the external tool keeps mangling it.

## User

Export session, commit with `jj`, don't push.

## Assistant

Invoked the `export-coding-session` skill, wrote this transcript under `docs/coding-sessions/2026-06-06/`, ran the redaction scan, then committed the full change set with `jj` (no push).
