# Prompt: Creating improving-vcs-skill

## Original Multi-part Prompts

In June 2026, for multi-session agentic workflows working on the same repository in parallel, if I want to use localhost remote control from `claude remote-control` or GPT Codex, should I use Git + worktree, or Jujutsu + same dir + a VCS skill instructing agents on how to commit / merge / upload? I know that most agentic coding tools have native Git + worktree support, but Git was not designed for high-parallelism workflows, Jujutsu has advantage in that regard.

If I use Jujutsu and a vcs skill, which instructs the agent to create a new workspace each time by using jj workspace add, would that solve the problem? The main reason I'm considering Jujutsu is that the Git merge workflow is not ideal for multi-agent workflow. Although there is the extra cost of using vcs skill, maybe the benefit of better rebase / merge behavior is worth it? Does Jujutsu provide any benefit for multi-agent workflow at all compared to Git? I would like to create a completely multi-session agentic workflow and a set of skills solely for pure agentic development.

I created a git repo `jj-setup-test` to test and iterate on this skill, and I already started a Claude session in the repo. Give me a prompt to kick start the creation and test of a skill called `vcs`, which at a high-level instructs the agents to achieve goals I created. Note that there are different coding agents - Claude Code, GPT Codex, Cursor, Antigravity, etc. There are also different environments - local-only CLI, localhost remote control, cloud remote control, GitHub copilot in cloud, etc. Make sure the skill is compact enough and reference other markdown files based on the situation. For example, I'm not sure if using `jj` is even possible or desired on a fully remote cloud session running in GitHub. Instruct the agent to strictly abide to this rule before and after starting work. In the prompt, ask agents to create scripts for common operations at the start or the end of the coding session with intuitive bookmark / branch names. Instruct the agent to create a separate markdown file just on how to write better commit messages. Basically, this skill should optimize and improve multi-agent workflows in all possible agentic-coding environments.

I changed my mind. Modify the prompt to provide context, but instead of creating the VCS skill itself, I need to create a skill to test the `vcs` skill. Call it `improving-vcs-skill`. This skill should be used to instruct the agent to create sub-agents to use the `vcs` skill in these different environments and scenarios, report back the effectiveness of the `vcs` skill, and continuously iterate until multiple subagents can more efficiently handle parallel work and hand effectively handle merge conflicts among them. Make it clear that this new skill I'm asking the agent to create should only be used during skill authoring or change ONLY for the `vcs` skill.

I am also now working in a repo named `coding-agent-skills`, where the `jj-setup-test` repo lives in `../jj-setup-test`. Change the prompt to work in `coding-agent-skills` repo, where the skill should be added to `.agents/skills/` (not `.claude/skills`), the agent can still use the `jj-setup-test` repo to test the skill if it chooses to, but it's not required.

## Consolidated

A single prompt to paste into the LLM chat tool. It asks the chatbot to produce
the kick-start prompt I will then hand to a coding agent in this repo to author
and test `improving-vcs-skill`. It does not ask anyone to build the skill yet — the
deliverable is the prompt, not the skill.

```text
You are helping me write ONE self-contained prompt, which will be added to
<./0002-20260606-creating-improving-vcs-skill.md>.

Do NOT design or write any skill yourself — your only output is that kick-start
prompt, ready for me to copy. The prompt must direct the agent to author and then
iteratively test a new skill called `improving-vcs-skill`.

Context (why this exists):

- I'm building a fully agentic, multi-session development workflow — multiple
  coding agents working the same repository in parallel — plus a set of skills
  made purely for agentic development.
- Most agentic tools natively support Git + worktree, but Git wasn't designed for
  high-parallelism work. Jujutsu (`jj`) on a Git backend offers better
  rebase/merge ergonomics and clean per-agent isolation (e.g. `jj workspace add`
  lets each agent take its own workspace in a shared directory). The open question
  I'm probing is whether `jj` + a VCS skill beats Git + worktree for multi-agent
  work, or whether the skill's overhead outweighs the benefit.
- I already have a `vcs` skill in this repo, but today it only covers
  commit-message formatting (`skills/vcs/COMMITS.md`). It needs to grow into a
  compact skill that teaches any agent the VCS mechanics and etiquette for
  committing, merging, rebasing, and publishing work cleanly during parallel,
  multi-session development — staying compact by referencing supplementary
  markdown files per situation.

The intent to emphasize above everything else:

`improving-vcs-skill` exists to validate and harden the `vcs` skill by using
MULTIPLE agentic coding tools to exercise it across DIFFERENT environments, and
specifically across two VCS modes:

- WITH `jj` (Jujutsu) on a Git backend — e.g. per-agent isolation via
  `jj workspace add` in a shared working directory.
- WITHOUT `jj`, using only `Git` — e.g. Git + worktree; this is the path for
  environments where `jj` isn't available or wanted, notably fully-remote cloud
  sessions (e.g. GitHub-hosted ones).

The harness must confirm the `vcs` skill makes each agent correctly detect which
mode it's in and strictly abide by the right workflow both before and after it
starts work.

What the kick-start prompt should tell the agent to build — `improving-vcs-skill`:

- Scope it tightly as a meta / authoring harness: it is used ONLY while authoring
  or changing the `vcs` skill, never during normal development. State this in the
  skill itself.
- The orchestrating agent spawns sub-agents that each load the `vcs` skill and
  perform realistic parallel work in both VCS modes above, standing in for a range
  of agents (Claude Code, GPT Codex, Cursor, Antigravity, …) and environments
  (local-only CLI, localhost remote control, cloud remote control, GitHub Copilot
  in the cloud, …). Where it can't literally run a given agent or environment, it
  should representatively simulate it and say so.
- Drive the sub-agents into overlapping, deliberately conflicting changes, then
  have them commit / merge / rebase / publish using only the `vcs` skill, and
  report back on the skill's effectiveness — what was clear, what was ambiguous,
  where they stalled, where conflicts were mishandled.
- The orchestrator aggregates those reports and iterates on the `vcs` skill,
  looping until multiple sub-agents can reliably handle parallel work efficiently
  AND resolve merge conflicts among themselves cleanly. That bar is the exit
  condition.
- Use the testing to push the `vcs` skill toward these properties and verify they
  hold: compactness with situation-specific referenced markdown files; a strict
  "detect the VCS mode, then abide before and after work" rule; helper scripts for
  common session-start and session-end operations using intuitive bookmark /
  branch names; and a dedicated markdown on writing better commit messages
  (`COMMITS.md` already exists — refine, don't duplicate).

Repo specifics to bake into the prompt:

- Work in the `coding-agent-skills` repo. The canonical home for a skill is
  `skills/<name>/SKILL.md`, symlinked into `.agents/skills/<name>` (and
  `.claude/skills` symlinks to `.agents/skills`). Add `improving-vcs-skill`
  following that convention — it must land under `.agents/skills/`, not
  `.claude/skills`.
- The `vcs` skill under test is at `skills/vcs/` (symlinked at `.agents/skills/vcs`).
- A scratch repo `jj-setup-test` exists at `../jj-setup-test`; the agent may use it
  for live testing if helpful, but it is not required.
- Keep everything repo-agnostic: no hardcoded absolute paths or usernames, and any
  helper scripts should resolve the repo root themselves (Git → Jujutsu → current
  directory).

Output requirements:

- Return ONLY the kick-start prompt, as a single block I can copy and paste — no
  preamble, no explanation, no skill content.
- Write it to emphasize intent and goals over rigid step-by-step instructions, so
  the coding agent has latitude to design the harness and the `vcs` skill itself.
```
