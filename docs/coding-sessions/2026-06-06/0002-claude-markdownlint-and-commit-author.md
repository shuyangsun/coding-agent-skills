<!-- markdownlint-disable MD013 MD024 -->

# markdownlint config + commit-author attribution

- **Date:** 2026-06-06
- **Repo:** coding-agent-skills (colocated Git + Jujutsu repo; parent commit on `main`)
- **Author:** Shuyang Sun <shuyangsun10@gmail.com>
- **Agent:** Claude Code (Opus 4.8, 1M context)
- **Summary:** Resolved markdownlint errors across the repo by aligning the linter with our Prettier setup (a root `.markdownlint-cli2.jsonc` disabling `MD013`, a per-transcript `MD013`/`MD024` disable directive emitted by the export skill) and wired markdownlint into the dependency/script/lefthook toolchain. Then added human-author attribution: an `Author:` commit trailer and a transcript-header `Author:` line (both derived from VCS config), plus a "focus the message on content, not the transcript" rule in the commit skill. Made the markdownlint directive an explicit idempotent check in the export skill, then exported this session and committed/pushed it with `jj`.

---

## User

There are still markdown linter errors in `docs/coding-sessions/2026-06-06/0001-claude-prettier-bun-vcs-hooks.md`. Follow principles we used in that file (read human prompts and intents), modify the skill and our setup to clean up all markdown linter errors as well before commit or running `jj fix`.

## Assistant

Investigated what linter was in play and what was failing.

- **Bash** — checked git/jj status, read `package.json` / `.prettierrc.json` / `.prettierignore`, and searched for any markdownlint config or install. Found no markdownlint anywhere, so the errors were coming from the editor's markdownlint extension.
- **Bash** — ran `bunx markdownlint-cli2` on the transcript: **33 errors**, all `MD013` (line-length, 80) and `MD024` (no-duplicate-heading). Ran it across the whole repo — `MD013` hit nearly every Markdown file; `MD024` only the transcripts.

Key insight: these were the exact rules the previously-deleted `docs/coding-sessions/.markdownlint.jsonc` used to disable. They aren't real defects — `MD013` conflicts with our deliberate `proseWrap: preserve` (we don't reflow prose) and `MD024` conflicts with the transcript format (repeated `## User` / `## Assistant`). So the fix is configuration, not mangling content.

- **Bash** — empirically tested that a leading `<!-- markdownlint-disable -->` HTML comment does **not** trip `MD041` (first-line-heading). Confirmed safe.
- **Bash** — `bun add --dev --exact markdownlint-cli2` (pinned `0.22.1`, matching the Prettier pinning approach).
- **Write `.markdownlint-cli2.jsonc`** — root config disabling `MD013` repo-wide with rationale; honored by both the CLI and the VS Code extension; `gitignore: true` + ignore `node_modules`.
- **Edit `package.json`** — added `lint:md` and `lint:md:fix` scripts.
- **Edit `lefthook.yml`** — added a `markdownlint` pre-commit job after Prettier; switched `parallel` to `false` so the two tools never write the same staged file at once.
- **Edit `scripts/setup-vcs-hooks.sh`** + **Edit `AGENTS.md`** — documented that `jj fix` only hosts stdin→stdout formatters, so markdownlint runs via `bun run lint:md` under jj; added a Linting section.
- **Edit `skills/export-coding-session/SKILL.md`** — Step 4 now emits `<!-- markdownlint-disable MD013 MD024 -->` at the top of every transcript, so transcripts lint clean in any host project without dropping config files into it.
- **Edit** — retrofitted both existing transcripts with the directive.
- **Bash** — `bun run format`, `bun run lint:md` (0 errors), `bun run format:check` (clean). Ran the actual `lefthook run pre-commit` against a deliberately messy file: Prettier fixed it, markdownlint passed — both jobs green.

Left the work uncommitted for review.

## User

In `skills/vcs/COMMITS.md`, ask the agent to focus on the changed content, not the exported coding session transcript, since every change has the transcript. Also, make sure the commit message has `Author: AUTHOR_FULL_NAME <AUTHOR_EMAIL>` in the transcript header. After the skill is updated, modify existing transcripts to add author information.

## Assistant

Planned the change in plan mode (read-only exploration first).

- **Read** — `skills/vcs/COMMITS.md`, the export skill, and both transcript headers.
- **Bash** — read author identity from VCS config: `git config` and `jj config` both return `Shuyang Sun <shuyangsun10@gmail.com>` (note: this differs from the harness-recorded email — confirming the author line must come from VCS config). Saw transcripts were committed as separate `docs(coding-sessions): …` changes.
- **AskUserQuestion** — clarified where the `Author:` line belongs, since the request mentioned both "commit message" and "transcript header." Answer: **both**.
- **Write** the plan file, then **ExitPlanMode** — approved.

Implemented:

- **Edit `skills/vcs/COMMITS.md`** — added a **session transcripts** guideline bullet (describe the substantive change, ignore the accompanying transcript); renamed the trailer section to "Author and Co-Authored-By trailers" and documented an `Author: Full Name <email>` trailer (first in the block, derived from VCS config); updated the format template, the feature example, and the HEREDOC mechanics block to show it.
- **Edit `skills/export-coding-session/SKILL.md`** — Step 4 now adds an `Author:` bullet read from VCS config, with the header ordered `Date · Repo · Author · Agent · Summary`.
- **Edit** — added `- **Author:** Shuyang Sun <shuyangsun10@gmail.com>` to both existing transcripts (between `Repo:` and `Agent:`).
- **Bash** — `bun run format`, `format:check` (clean), `lint:md` (0 errors).

## User

Also, in `skills/export-coding-session/SKILL.md`, instruct the agent to add `<!-- markdownlint-disable MD013 MD024 -->` at the top of the exported transcript if that's not already done.

## Assistant

The directive instruction was already in Step 4; made it an explicit idempotent check.

- **Edit `skills/export-coding-session/SKILL.md`** — added: "Always confirm that exact directive is the file's first line — if you're (re)writing or editing a transcript that lacks it, add it; never assume it's already there."
- **Bash** — `format:check` (clean), `lint:md` (0 errors).

## User

Export coding session, commit and push with `jj`.

## Assistant

Ran the `export-coding-session` skill: resolved the dated dir and global index (`0002`), reconstructed this transcript, scanned for sensitive data, then committed and pushed the work with `jj`.
