---
title: "Codex skill discovery and canonical `.agents/skills` layout"
date: 2026-06-06
repo: "coding-agent-skills (jj; work in the default workspace)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Codex Desktop (GPT-5.5, reasoning effort: xhigh)"
summary: >-
  Investigated why Codex could not see the repo-local `vcs` skill, tried a `.codex/skills
  -> ../skills` symlink, then moved `export-coding-session` and `vcs` into real
  directories under `.agents/skills/`, removed the old `skills/` tree, updated the repo
  docs, verified the two skills parse from the new canonical location, and prepared this
  transcript before commit and push.
---

<!-- markdownlint-disable MD013 MD024 -->

# Codex skill discovery and canonical `.agents/skills` layout

## User

> Why can't I access the /vcs skill? I thought it's symlinked to @.agents/skills/?

## Assistant

Checked the repo layout and confirmed the original symlink existed:

- `.agents/skills/vcs -> ../../skills/vcs`
- `skills/vcs/SKILL.md` existed with valid-looking frontmatter.
- `.claude/skills` pointed to `.agents/skills`.

Compared the repo-local skill folders with the skills loaded in the current Codex session. `export-coding-session`, `improving-vcs-skill`, and `update-agent-permissions` were visible, but `vcs` was not. Also checked global skill locations (`~/.agents/skills`, `~/.codex/skills`) and found `vcs` was not installed globally.

Because this was a Codex behavior question, used the local `openai-docs` skill to fetch the Codex manual. The manual said Codex scans `.agents/skills` from the working directory up to the repo root and supports symlinked skill folders. It also clarified that skills are invoked through `/skills` or `$skill-name`, not as `/skill-name` slash commands.

Conclusion at that point: the filesystem symlink was valid, so the issue looked like a Codex loader or selector problem rather than a broken repo link.

## User

> I restarted Codex but still doesn't see it. Fix it by linking @.codex/skills/ to @skills/. Verify that you can see both skills afterwards.

## Assistant

Created a repo-local symlink:

```text
.codex/skills -> ../skills
```

Verified both skills resolved through that path:

- `.codex/skills/export-coding-session/SKILL.md`
- `.codex/skills/vcs/SKILL.md`

Left the symlink unstaged at that point.

## User

> I restarted Codex, still not seeing those skills. You know what, just move both skills under the @.agents/skills folder, and delete the @skills/ folder. Update [README.md](README.md) and [AGENTS.md](AGENTS.md) to reflect that.

## Assistant

Converted the two canonical skills from symlinked entries into real directories under `.agents/skills/`:

- `skills/export-coding-session/` -> `.agents/skills/export-coding-session/`
- `skills/vcs/` -> `.agents/skills/vcs/`

Removed the old `skills/` directory and the failed `.codex/skills` symlink so it would not point at a deleted path.

Updated `README.md` and `AGENTS.md` to describe `.agents/skills/` as the canonical, agent-neutral home for skills. Also updated the `export-coding-session` skill wording so it no longer referred to this repo's old `skills/` directory as the symlink target.

Verified the resulting layout:

- `skills/` no longer existed.
- `.codex/skills` no longer existed.
- `.agents/skills/export-coding-session/SKILL.md` existed in a real directory.
- `.agents/skills/vcs/SKILL.md` existed in a real directory.
- No symlinks remained directly under `.agents/skills`.

Ran verification:

- Targeted Prettier check on the changed and moved files passed.
- Parsed both requested skills from `.agents/skills` and confirmed their `name` and `description` frontmatter were present.
- Repo-wide `bun run lint:md` still failed on an unrelated existing table alignment issue in `.agents/skills/improving-vcs-skill/SKILL.md`, mirrored through `.claude/skills`.

Staged the skill-layout move and documentation updates.

## User

> Export chat session history, commit and push.

## Assistant

Loaded the current `export-coding-session` skill and the local `vcs` skill from their new `.agents/skills/` locations. Detected that the repository is in Jujutsu mode with `jj root`, so the commit and push flow should use `jj`.

Checked the working copy:

- Current change was an unnamed jj change on top of `main`.
- It contained the staged skill-layout move, documentation updates, and removal of the failed `.codex/skills` symlink.

Generated the next transcript path with the bundled script:

```text
docs/coding-sessions/2026-06-06/0013-codex-skill-layout.md
```

Rendered this concise transcript from the current Codex session JSONL, summarizing tool calls rather than dumping large command outputs verbatim.
