<!-- markdownlint-disable MD013 MD024 -->

# Create the setup-vcs skill (hooks + guardrails + jj install)

- **Date:** 2026-06-07
- **Repo:** coding-agent-skills (jj workspace `claude-setup-vcs-skill`)
- **Author:** Shuyang Sun <shuyangsun10@gmail.com>
- **Agent:** Claude Code (Opus 4.8, 1M context, thinking: high)
- **Summary:** Authored a new `setup-vcs` method-skill that wires the `vcs` skill's isolation hooks/guardrails into every agent tool (Claude, Codex, Cursor, Antigravity, Gemini) and installs Jujutsu without pinning a version. Read every current setup so the skill mirrors it, captured the motivation/incentive, ran an adversarial verification workflow, and — prompted by that review — fixed a real botched-merge bug in `session-start.sh`/`vcs-check.sh` that silently broke Antigravity and Cursor session-start isolation.

## User

```text
Create a new skill called `setup-vcs` to work with the /vcs skill, which sets up hooks and guardrails for agentic coding tools like Claude Code, GPT Codex, Cursor, and Antigravity. Capture the motivation and incentive, and read current setups so the skill can mirror them.
```

## Assistant

```text
I'll start by understanding the current setup thoroughly before building the skill.
```

Tool: Bash — list repo structure; the `vcs` PreToolUse guard refused the command from the shared jj default workspace ("this session already owns an isolated workspace. Prefix the command with: `cd <your-workspace> && ...`"). Re-ran every command as `cd <workspace> && ...`.

Tool: Bash — surveyed the tree. Skills live in `.agents/skills/` (`.claude/skills` is a symlink to it). Found the per-tool config dirs `.claude/`, `.codex/`, `.cursor/`, `.antigravity/`, `.gemini/`, plus the agent-neutral `.agents/`, and `scripts/setup-vcs-hooks.sh`.

## Assistant

```text
Key insight: scripts/setup-vcs-hooks.sh is about Prettier formatting (lefthook / jj fix), not the isolation guard. The real "hooks and guardrails" wiring lives in each tool's config. Reading them directly for exact fidelity.
```

Tool: Read — `.claude/settings.json` (SessionStart→session-start.sh; PreToolUse/SubagentStart/CwdChanged→vcs-check.sh; exit-code contract; `${CLAUDE_PROJECT_DIR}`).

Tool: Read — `.codex/config.toml` + `.codex/rules/default.rules` (`[[hooks.*]]` with `repo="$(jj root 2>/dev/null || git rev-parse --show-toplevel)"`; Starlark execpolicy for permissions).

Tool: Read — `.cursor/hooks.json` / `permissions.json` / `cli.json` (all events route through `cursor-hook.sh`).

Tool: Read — `.antigravity/settings.json`, `.gemini/settings.json` (permission-only, identical), `.agents/hooks.json` (`vcs-session-isolation` → `antigravity-hook.sh`).

Tool: Read — the hook scripts `session-start.sh`, `vcs-check.sh`, `cursor-hook.sh`, `antigravity-hook.sh`, and `vcs-state.sh` (out-of-tree owner markers; three response dialects: exit-code, Cursor JSON, Antigravity JSON).

Tool: Read — `AGENTS.md`, `README.md` (repo-agnostic discipline), `update-agent-permissions/SKILL.md` (the structural template: intent-over-syntax, "method not snapshot").

Tool: Read — `docs/plans/2026-06-07/0001-vcs-guardrails-for-jj-workspace-isolation.md`, `docs/issues/2026-06-07/0008-...cwd-drift...trap.md`, and the guardrails-plan session (motivation: advisory text loses the moment before the rule is applied; defense-in-depth; the cwd-drift trap that drove the path/owner-aware guard).

## User

```text
Btw, this skill should also install Jujutsu if that's not available on the system. Do not hardcode Jujutsu version, as that changes over time.
```

## Assistant

```text
Naming this work properly, then authoring. The skill is a method-skill (sibling of update-agent-permissions) that wires the vcs skill's existing scripts into each tool and installs jj when missing.
```

Tool: Bash — `rename-work.sh claude-setup-vcs-skill` (renamed the temporary `claude-pending-*` jj workspace).

Tool: Write — `.agents/skills/setup-vcs/SKILL.md`. Sections: "Why this exists (the incentive)", "What you are wiring (the enforcement model)" with the three-dialects table, "Prerequisite: install Jujutsu (no pinned version)", "When to run", a 6-step procedure (understand → install jj → research each tool's current hook syntax via parallel subagents → wire two events per tool → align permissions → verify), Principles, and a "Current wiring reference (snapshot — verify before reuse)" mirroring today's per-tool wiring.

Tool: Bash — `bunx prettier --write` + `markdownlint-cli2 --no-globs`: both clean.

## Assistant

```text
Since ultracode is on, running an adversarial verification workflow: cross-check the "current wiring" snapshot against the actual config files for fidelity, and critique the skill against the repo's conventions and the source motivation.
```

Tool: Workflow — `verify-setup-vcs-skill` (2 parallel agents, structured findings).

Tool: Write — memory: `setup-vcs-skill.md` (+ `MEMORY.md` index entry) capturing the enforcement model and per-tool config locations.

## User

```text
After you're done, /export-coding-session then use /vcs to merge, clean up, and push.
```

## Assistant

```text
The verification surfaced one high-severity, real bug — not in my skill, but in the vcs skill's session-start.sh it wires up: two contradictory --hook validation gates that both run, so --hook agy and --hook cursor both die. That silently breaks Antigravity and Cursor session-start isolation. Confirming empirically before fixing.
```

Tool: TaskOutput — workflow results. Fidelity agent verdict `fix-then-ship` (the high-sev source bug + a few low-sev precision notes); conventions agent verdict `ship` (jj-install requirement fully satisfied, motivation faithful, intent-over-syntax consistent).

Tool: Bash — confirmed: from `session-start.sh` lines 56–57, `--hook agy` dies with "must be codex, claude, cursor, or plain" and `--hook cursor` dies with "must be codex, claude, agy, or plain" — the intersection of the two gates excludes both. The same merge residue (a stray `-` diff marker) sits in `vcs-check.sh`'s usage text.

## Assistant

```text
The fix is unambiguous and safe — it only widens acceptance to the union of both gates. Repairing the source so the wiring my skill documents actually works.
```

Tool: Edit — `session-start.sh`: collapsed the duplicate usage lines and the two `--hook` `case` gates into one accepting `codex|claude|cursor|agy|plain`.

Tool: Edit — `vcs-check.sh`: removed the stray `-` diff marker and the duplicated description paragraph in the usage heredoc; unified the `hook [--agent codex|claude|cursor|agy]` line.

Tool: Bash — `bash -n` on both scripts (OK); re-ran `--hook agy` and `--hook cursor` (now accepted, clean no-op outside a repo).

Tool: Edit ×5 — precision fixes to `SKILL.md` from the review: session-start bases off the trunk (`main`/`origin/main`); owner-marker path generalized to the repo's Git admin dir; Codex `repo=...` quoted verbatim with `2>/dev/null`; Cursor JSON contract notes `continue:true` + message keys; Gemini noted as a byte-identical copy of Antigravity's posture; step 5 notes the owned-cleanup commands the guard vets are allow-listed (not prompted); the issue-0008 rationale made self-contained/portable.

Tool: Bash — re-format + re-lint `SKILL.md`: both clean.

Tool: Edit — memory: recorded the session-start.sh dual-gate bug fix and the valid `--hook`/`--agent` dialects.

## Assistant

```text
Exporting the session, then using /vcs to merge, clean up, and push.
```

Tool: Skill — `export-coding-session`; `next-index.sh` → index 0033; wrote this transcript and ran the redaction scan.
