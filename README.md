# coding-agent-skills

General-purpose, repo-agnostic skills for LLM coding agents (Claude Code, Cursor, Codex, Gemini, and others). Each skill is self-contained and carries no assumptions about a particular project.

## Using these skills in your project

The skills live in `skills/`. To use them, make that directory visible to your agent runtime under the skill directory it reads — `.agents/skills/` (agent-neutral), `.claude/skills/` (Claude Code), etc.

**Git — as a submodule (recommended; keeps the skills updatable):**

```sh
git submodule add https://github.com/<owner>/coding-agent-skills .agents/coding-agent-skills
# symlink an individual skill into your runtime's skill directory:
ln -s ../coding-agent-skills/skills/export-coding-session .agents/skills/export-coding-session
# or, for Claude Code, point its skills dir at the agent-neutral one:
ln -s ../.agents/skills .claude/skills
```

Update later with `git submodule update --remote .agents/coding-agent-skills`.

**Jujutsu (`jj`):** `jj` has no native submodule support, so use the Git submodule command above (it works in a colocated repo, `jj git init --colocate`, and you manage the submodule with `git`).

**Or just copy a skill** out of `skills/` into your own `.agents/skills/` or `.claude/skills/` — works with any VCS.

The bundled scripts resolve the working repo root on their own (Git, then Jujutsu, then the current directory) and create any directories they need, so they work no matter where the `skills/` directory is symlinked from. See [AGENTS.md](AGENTS.md) for the layout details.
