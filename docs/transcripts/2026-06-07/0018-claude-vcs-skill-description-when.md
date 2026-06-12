<!-- markdownlint-disable MD013 MD024 -->

# Shorten the vcs skill description and add early isolation mandates

- Date: 2026-06-07
- Repo: coding-agent-skills (bookmark/workspace: claude-vcs-desc-when)
- Author: Shuyang Sun <shuyangsun10@gmail.com>
- Agent: Claude Code (Opus 4.8, 1M context, thinking: high)
- Summary: Rewrote the `vcs` skill's frontmatter description to be shorter and WHEN-focused (load before editing for new work, and before commit/merge/rebase/publish) instead of enumerating WHAT it does, and added a prominent "Isolate before you edit" mandate at the top of the skill body so agents reliably create a workspace/worktree before changing files.

## User

Make sure coding agents create new `jj` workspace or Git worktree after understanding context well enough to come up with a good name. Use the /vcs skill to create a new jj workspace first for this change.

Agents are not reliably creating new workspaces before starting to work (needs context to name workspace first though). This is likely due to the @.agents/skills/vcs/SKILL.md description being too long and not clear, so no early message mandating agents to do that. Change the description to be shorter, emphasize on WHEN the skill should be used (before starting the work, and before committing and merging), instead of WHAT. Add early signals to mandate agents to create new workspaces.

## Assistant

Invoked the `/vcs` skill to isolate the work first, as instructed.

Detected the VCS mode and ran the isolate helper:

- `jj root` succeeded → Jujutsu mode.
- `bash .claude/skills/vcs/scripts/isolate.sh claude-vcs-desc-when` created a new jj workspace at `coding-agent-skills-claude-vcs-desc-when` (WORK_REF `claude-vcs-desc-when`).

Inspected the skill directory layout and confirmed `.claude/skills` is a symlink to `.agents/skills`, so editing the canonical `.agents/skills/vcs/SKILL.md` covers both. (Verified via AGENTS.md: `.agents/skills/` is the canonical home; `.claude/skills` symlinks to it.)

Made two edits to `.agents/skills/vcs/SKILL.md`:

1. **Description — shorter, WHEN not WHAT** (3 lines, down from 7). New text:

   > Load at the START of new repo work, BEFORE you change any file, so you isolate the work in your own workspace/worktree first — and again BEFORE any commit, merge, rebase, or publish. Works in any VCS (Jujutsu or Git).

   Dropped the WHAT enumeration (detect mode, union conflicts, format commits, parallel-agent collaboration, "when in doubt…"), leading instead with the two trigger moments.

2. **New early signal at the top of the body**, the first thing read after the title:
   > **Isolate before you edit.** For any new work, do not change a single file in the checkout you were handed. First understand the task well enough to name it `<ide>-<work>` (e.g. `claude-fix-auth-retry`), then create your own workspace/worktree (§2) and work there. The one exception: a dedicated cloud/PR session, where you already have your own clone — then skip isolation.

Ran `npx markdownlint-cli2` on the file — 0 errors.

Reported the changes, left them unlanded pending confirmation, and flagged that the `improving-vcs-skill` harness is the way to verify the change actually improves isolation behavior rather than just reading better.

## User

Yes, export session transcript, then integrate into main.

## Assistant

Invoked `/export-coding-session`, collected this transcript into `docs/coding-sessions/2026-06-07/0018-claude-vcs-skill-description-when.md`, ran the redaction scan, then integrated the work onto `main` via the `vcs` skill's `integrate.sh` helper.
