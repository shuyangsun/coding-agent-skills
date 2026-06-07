<!-- markdownlint-disable MD013 MD024 -->

# VCS guardrails plan for jj workspace isolation

- **Date:** 2026-06-07
- **Repo:** coding-agent-skills (bookmark `codex-vcs-guardrails`)
- **Author:** Shuyang Sun <shuyangsun10@gmail.com>
- **Agent:** Codex Desktop (GPT-5.5, reasoning: xhigh)
- **Summary:** Created a plan for mechanical `vcs` guardrails around jj workspace isolation, validated the current happy path with a small model, updated the plan with user decisions, and prepared it for merge.

## User

````text
# AGENTS.md instructions for [REDACTED_LOCAL_PATH]/coding-agent-skills

<INSTRUCTIONS>
# coding-agent-skills

General-purpose, repo-agnostic skills for LLM coding agents (Claude Code, Cursor, Codex, Gemini, and others).

## Layout

- `.agents/skills/` — the canonical, agent-neutral home for every skill. Each skill is one directory containing a `SKILL.md` plus any helper scripts. Add new skills here.
- `.claude/skills` — symlinks to `.agents/skills` so Claude Code picks up the same set.

## Consuming this repo from another project

This repo is meant to be downloaded, copied, or added as a Git submodule, then individual skill directories under `.agents/skills/` are symlinked into a host project's agent skill directory (under `.agents/` or `.claude/`). Because of that, skills must stay repo-agnostic:

- No hardcoded absolute paths, usernames, or assumptions about the host project's VCS or directory structure.
- Helper scripts resolve the working repo root themselves (Git → Jujutsu → current directory) and create any output directories they need, so they run correctly regardless of where the skill directory is symlinked from.
- Skills reference their own bundled scripts relative to the skill directory the runtime loaded, not a fixed `.agents/` or `.claude/` path, since either (or a different host-project path) may be the install location.

## Formatting

Markdown (and other supported files) are formatted with [Prettier](https://prettier.io), pinned to an exact version in `package.json` and run with [Bun](https://bun.sh).

```sh
bun install        # install Prettier + markdownlint + lefthook, then wire up VCS hooks
bun run format     # format everything in place
bun run format:check   # verify formatting without writing (use in CI)
bun run lint:md    # lint Markdown (use in CI)
bun run lint:md:fix    # lint Markdown and apply auto-fixes
```

Prettier config lives in `.prettierrc.json`; `.prettierignore` excludes dependencies, lockfiles, and verbatim documents. Prose wrapping and embedded-code formatting are disabled so exported session transcripts stay faithful to the original.

### Linting

Markdown is also linted with [markdownlint](https://github.com/DavidAnson/markdownlint) via `markdownlint-cli2`, configured in `.markdownlint-cli2.jsonc` (honored by both the CLI and the VS Code markdownlint extension). The config keeps markdownlint's defaults except for one rule that conflicts with our Prettier setup: `MD013` (line length) is off because we never reflow prose (`proseWrap: preserve`). Session transcripts additionally repeat `## User` / `## Assistant` headings (`MD024`); rather than relax that rule repo-wide, each exported transcript carries its own `<!-- markdownlint-disable MD013 MD024 -->` directive so it lints cleanly even when the skill is used in another project. Prettier owns formatting and markdownlint catches the structural issues it doesn't.

### Pre-commit formatting (Git and Jujutsu)

`bun install` runs `scripts/setup-vcs-hooks.sh` (via the `prepare` script), which configures whichever VCS the clone uses. You can re-run it any time with `bun run setup:hooks`.

- **Git** — [lefthook](https://lefthook.dev) installs a `pre-commit` hook (see `lefthook.yml`) that runs Prettier and then markdownlint on staged `*.md` files and re-stages any fixes.
- **Jujutsu** — jj has no commit hooks (commits are implicit and must stay fast), so the script configures `jj fix` to run Prettier on Markdown instead. Format changed files with `jj fix` (e.g. `jj fix -s @`). jj stores this config per-clone outside the repo, which is why the setup script must run after each fresh clone. `jj fix` only hosts stdin→stdout formatters, so markdownlint isn't wired into it — run `bun run lint:md` to lint under jj.

</INSTRUCTIONS><environment_context>
  <cwd>[REDACTED_LOCAL_PATH]/coding-agent-skills</cwd>
  <shell>zsh</shell>
  <current_date>2026-06-07</current_date>
  <timezone>America/New_York</timezone>
  <filesystem><workspace_roots><root>[REDACTED_LOCAL_PATH]/coding-agent-skills</root></workspace_roots><permission_profile type="disabled"><file_system type="unrestricted" /></permission_profile></filesystem>
</environment_context>
````

## User

```text
Follow [$vcs]([REDACTED_LOCAL_PATH]/coding-agent-skills/.agents/skills/vcs/SKILL.md) skill and create a new Jujutsu workspace named `codex-vcs-guardrails` before you start working.

The issue documented in [0002-20260607-agent-used-default-jj-workspace-instead-of-isolating.md](docs/issues/0002-20260607-agent-used-default-jj-workspace-instead-of-isolating.md) still happens quite often - agents start working after gathering enough context, but forgot to create new `jj` workspace. This is by far the most problematic behavior. Go through the [$vcs]([REDACTED_LOCAL_PATH]/coding-agent-skills/.agents/skills/vcs/SKILL.md) skill and see if we can inject more hardcoded checks in code. One idea I have is to add a `vcs-check.sh` script, which will be used and referenced at the start of every other script in @.agents/skills/vcs/ where it would make sense. This `vcs-check.sh` script would return an error if the agent is working on the default workspace. However, this idea likely won't work because it's a chicken and egg problem - agents forgot to do things as [$vcs]([REDACTED_LOCAL_PATH]/coding-agent-skills/.agents/skills/vcs/SKILL.md) instructed in the first place. Think of ways to improve this situation, and validate it with the [$improving-vcs-skill]([REDACTED_LOCAL_PATH]/coding-agent-skills/.agents/skills/improving-vcs-skill/SKILL.md) using a lower-tier model that's not very smart. Do not solely rely on agentic coding IDE's create worktree feature, that works only with Git. However, maybe we can add a hook to Claude Code or Codex at the beginning of the session to create a new Jujutsu workspace, then rename it after the agent gathers enough context. For other issues that can be damaging (e.g., [0005-20260607-concurrent-cursor-agent-committed-and-pushed-another-agents-work.md](docs/issues/0005-20260607-concurrent-cursor-agent-committed-and-pushed-another-agents-work.md)), maybe we can stop this can of action with disallowing certain types of actions in agent permission settings? Read `jj op log` to see which commands are signs of sub-agents causing issues. Don't implement anything yet, just give me a plan and document it under @docs/plans/.
```

## User

```text
<skill>
<name>improving-vcs-skill</name>
<path>[REDACTED_LOCAL_PATH]/coding-agent-skills/.agents/skills/improving-vcs-skill/SKILL.md</path>
---
name: improving-vcs-skill
description: Iterative, measurement-driven harness for IMPROVING the `vcs` skill. Use ONLY while authoring or changing `vcs` — never during normal development. It spawns parallel sub-agents that exercise `vcs` (and only `vcs`) on deterministic, pre-committed conflicting work across both VCS modes (Jujutsu-on-Git and Git-only) and a difficulty ladder, measures conflict-resolution speed and quality broken down by model tier, then drives rounds of revise-and-re-measure until the numbers meet the bar.
---

# Improving the `vcs` skill

This is a **meta-skill**: a closed loop that makes the [`vcs`](../vcs/SKILL.md)
skill measurably better at letting many coding agents do parallel work and
resolve merge conflicts cleanly. The harness is the means; a faster, safer `vcs`
is the end. You run rounds, each round produces numbers, and you keep the
revisions that move the numbers and revert the ones that don't.

> **Scope — authoring only.** Use this skill _only_ when authoring or changing
> `vcs`. It is never loaded during ordinary development, and sub-agents under
> test must never see it — they see `vcs` and a realistic task, nothing else.

## Test the VCS, not the coding (the determinism principle)

The only thing under test is whether agents **collaborate through version
control** — integrate each other's work and resolve merge conflicts cleanly and
fast. So the harness removes coding-ability variance entirely:

- Every agent's change is **generated deterministically and pre-committed** on
  that agent's own branch/bookmark (`agent-K`) — a realistic "finished PR". The
  sub-agent **writes no code**; its sole job is to integrate `agent-K` onto the
  shared `main`, resolving the conflicts that arise because teammates touched
  the same files and lines.
- Sub-agents are told **not to do any coding work after integrating** — no new
  code, no tests, no running the app, no "make it work" verification. We measure
  the quality and speed of the conflict resolution **immediately** after the
  merge/rebase, because that — not downstream patching — is what `vcs` governs.
  The one allowed finish step is the VCS tidy-up `vcs` prescribes (deleting the
  merged `agent-K` branch/bookmark), which has its own hygiene metric.
- Because the inputs are deterministic, the **correct merged result is
  deterministic too**, so `check-quality.sh` scores resolution quality
  objectively (union preserved, tie-break value correct, files still parse,
  nothing lost or clobbered) rather than just scanning for conflict markers.

## The invariant you are driving into `vcs`

Above all else, every revision of `vcs` must make an agent:

1. **Detect its VCS mode before starting work** — Jujutsu-on-a-Git-backend
   (jj present; use jj even though Git also works in a colocated repo) vs.
   **Git-only** (no `.jj`; e.g. Git + worktree, the path for cloud/GitHub
   sessions where jj isn't available).
2. **Abide by that mode's workflow, before and after work** — a Git-only agent
   must never reach for jj; a jj agent must use the jj workflow throughout.

Both modes are exercised every round, and `check-quality.sh` fails any round
where mode integrity broke. **Verify this holds — never assert it.**

## Difficulty ladder and model tiers (both varied every loop)

- **Difficulty** (`new-sandbox.sh --difficulty`): `easy` (one small union
  conflict), `medium` (several union conflicts + a same-line tie-break), `hard`
  (every agent rewrites the same large blocks across several files → big,
  overlapping, multi-file conflicts with many parallel agents). See
  [SCENARIOS.md](SCENARIOS.md).
- **Model tier** (vendor-agnostic): each sub-agent stands in for a capability
  tier — **large** (frontier), **mid** (workhorse), **small** (fast/cheap).
  Different-sized models behave very differently on big conflicts, so results
  are recorded and reported **per tier**: a `vcs` revision that only works for
  large models has **not** met the bar. See [MATRIX.md](MATRIX.md).

## The loop (one round)

1. **Provision** an isolated sandbox per mode + difficulty with `new-sandbox.sh`
   — deterministic fixtures, each agent's work pre-committed on `agent-K`, an
   integration point (`main`), and integration-only briefs.
2. **Brief & spawn** sub-agents (one per workspace) that load **only** `vcs`,
   spread across model tiers and environments ([MATRIX.md](MATRIX.md)). Each
   integrates its pre-committed `agent-K` onto `main` using only `vcs`.
3. **Run** them: each resolves conflicts, publishes, **stops**, and returns a
   structured report.
4. **Measure** with `check-quality.sh` (objective pass/fail incl. the resolution
   oracle, plus `STALE_REFS`, `DEFAULT_OK`, `ORPHAN_WS`, `ORPHAN_DIRS`, and `ORPHAN_EMPTY_HEADS`
   lifecycle hygiene lines) and `record-metrics.sh` / `scoreboard.sh` (speed,
   conflict cost, **output tokens**, stale-ref hygiene, **jj default readiness**,
   and **retired-workspace cleanup**, broken down by round and by tier) —
   [METRICS.md](METRICS.md).
5. **Revise** `vcs` (its `SKILL.md`, referenced files, helper scripts, `COMMITS.md`)
   to fix what stalled, then **re-run and re-measure**. Keep changes that improve
   the numbers; revert changes that don't, or that buy speed with botched merges.
6. **Repeat** until the exit bar is met — [LOOP.md](LOOP.md) and [METRICS.md](METRICS.md).

The loop above is the `--task integrate` flow (land work, resolve conflicts). A
symmetric `--task start` flow measures the other bookend — **session-start
isolation**: whether an agent carves out its own worktree/workspace before doing
new work so co-located agents don't interfere. Run start rounds alongside
integration rounds; details in [LOOP.md](LOOP.md) and [SCENARIOS.md](SCENARIOS.md).

## Bundled scripts

Run these from this skill's own directory (the path the runtime loaded it from);
below that is written `<skill-dir>/scripts/`. They keep every sandbox in one
disposable work area outside any real repo (`$VCS_HARNESS_DIR`, default
`$TMPDIR/vcs-harness`), so the harness never pollutes the project under test.
They require `python3` (the deterministic content engine) plus `git`, and `jj`
for jj-mode rounds.

| Script               | Purpose                                                                                                                                                                                                                                                                                                               |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `new-sandbox.sh`     | Provision one round: `--task integrate` (fixtures + pre-committed per-agent work + integration briefs; jj rounds deliberately stale `default`) or `--task start` (shared repo + a one-edit brief that tests session-start isolation).                                                                                 |
| `check-quality.sh`   | Objectively score an integrated round: mode integrity, no markers/unresolved, no lost work, correct resolution, **+ branch/bookmark hygiene** (`STALE_REFS`), **jj default readiness** (`DEFAULT_OK`), and **retired workspace cleanup** (`ORPHAN_WS` / `ORPHAN_DIRS` / `ORPHAN_EMPTY_HEADS`). Also scores a start round's change + cleanup. |
| `check-isolation.sh` | Score a `--task start` round's **session-start isolation** (`ISOLATED`) — did the agent carve out its own worktree/workspace before working — from durable git-reflog / jj-op-log signals. Also scores the **`<ide>-<work>` naming** convention (`NAME_OK`, main arm only).                                           |
| `scenario.py`        | Deterministic content engine: seeds fixtures, applies each agent's diff, emits the plan, runs the oracle, and prints the start-task edit instructions.                                                                                                                                                                |
| `record-metrics.sh`  | Append one agent's measurements (time, conflict time, **tokens**, **stale refs**, **orphan workspaces**, **default readiness**, **isolation**, retries, quality, **tier**, **difficulty**) to the log.                                                                                                                |
| `scoreboard.sh`      | Aggregate the log by round (trend) **and by model tier** (incl. `mean_tok`, `stale`, `orph`, `def`, and a difficulty×tier pass-rate matrix).                                                                                                                                                                          |
| `rm-sandbox.sh`      | Tear down a round or the whole work area (guarded to the harness work area only).                                                                                                                                                                                                                                     |

Run `bash <skill-dir>/scripts/<name>.sh --help` for usage. Full round procedure,
sub-agent briefing, and the revise/revert discipline are in [LOOP.md](LOOP.md).

## Exit condition (the bar)

Stop only when, across **multiple consecutive rounds** (not one lucky run),
sub-agents using only `vcs` reliably (a) complete parallel work and (b) resolve
merge conflicts among themselves quickly and cleanly — **in both modes, across
the difficulty ladder, and across model tiers** — with mode detection holding
before and after work, while batch wall-clock and, above all, conflict-resolution
time are low and **trending down**, and output quality holds or improves. The
precise thresholds and how to read them are in [METRICS.md](METRICS.md).

</skill>
```

## User

```text
<skill>
<name>vcs</name>
<path>[REDACTED_LOCAL_PATH]/coding-agent-skills/.agents/skills/vcs/SKILL.md</path>
---
name: vcs
description: Load at the START of new repo work, BEFORE you change any file, so
  you isolate the work in your own workspace/worktree first — and again BEFORE
  any commit, merge, rebase, or publish. Works in any VCS (Jujutsu or Git).
---

# VCS

**Isolate before you edit.** For any new work, do not change a single file in
the checkout you were handed. First understand the task well enough to name it
`<ide>-<work>` (e.g. `claude-fix-auth-retry`), then create your own
workspace/worktree (§2) and work there. The one exception: a dedicated cloud/PR
session, where you already have your own clone — then skip isolation.

Then follow this skill for every commit, merge, rebase, and publish too, in
whatever version-control system the repo uses.

## 1. Detect the mode first - before any VCS action

Run `jj root` (or look for a `.jj/` directory).

- **It succeeds -> Jujutsu (jj) mode.** Use jj for everything, **even though Git
  commands also work** — a colocated repo has both `.git` and `.jj`, and a naive
  "is this Git?" check picks the wrong tool. jj is the right tool whenever jj is
  present.
- **It fails / no `.jj` -> Git mode.** Plain Git, including a Git _worktree_ (where
  `.git` is a file pointing into a parent repo). Use Git.

Stay in that mode the whole session and re-confirm it before you publish; never
cross tools (don't run jj in a Git repo, or fall back to raw git in a jj repo).

## 2. For standard flows, run the helper first

Do not spend tokens re-deriving the routine command chain. The bundled helpers
detect the mode and run the standard Git/jj mechanics. Use prose judgment only
when a helper stops for semantic conflict resolution or reports an unexpected
condition.

- **Starting new local work:** from the checkout you were handed, run
  `bash <skill-dir>/scripts/isolate.sh <ide>-<work>`, for example
  `bash <skill-dir>/scripts/isolate.sh codex-fix-auth-retry`. If it prints
  `NEXT_CWD=...` (it created a fresh workspace/worktree), `cd` there **before you
  edit, read, or run anything else** — every command for this work runs from that
  path, not the checkout you started in. Creating the workspace but staying put
  silently writes into the shared checkout. If instead it prints `CREATED=no` you
  are already isolated; work in place. In a dedicated cloud/PR session you already
  have your own clone; skip isolation.
- **Landing committed work on shared `main`:** run
  `bash <skill-dir>/scripts/integrate.sh <branch-or-bookmark>`, for example
  `bash <skill-dir>/scripts/integrate.sh agent-2`. If it prints
  `VCS_CONFLICT=...`, resolve only the listed files using the conflict etiquette
  below, then rerun
  `bash <skill-dir>/scripts/integrate.sh --continue <branch-or-bookmark>`.

`integrate.sh` handles the no-ambiguity finish steps: Git fetch/rebase/push retry,
safe additive Git conflict cleanup for text/JSON files, deterministic
higher-version scalar tie-breaks in config files, jj merge formation, stale
workspace recovery, `main` movement checks, `jj git export`, merged
branch/bookmark deletion when no real remote backs it, parking jj `default` on
`main`, retiring landed jj agent workspaces, and auto-resolving jj conflicts that
are mechanically additive and structurally valid. If it prints `NEXT_CWD=...`,
run any later shell command from that live directory because your jj workspace
was intentionally removed.

## 3. Conflict etiquette

When the helper stops for conflicts, the agent's job is semantic resolution:

- Union every additive change. Keep every changelog entry, list/array element,
  and code block that any side added. Do not drop teammates' work.
- For a single-valued field set to different values, keep the higher value.
  Compare values directly; do not rely on "ours" or "theirs" labels.
- Never resolve a whole file with one side (`ours`, `theirs`, `-X ours`).
- Remove every conflict marker: `<<<<<<<`, `=======`, `>>>>>>>`, `|||||||`.
- jj conflicts are diff-style. Drop marker/header lines such as `<<<<<<<`,
  `%%%%%%%`, `\\\\\\\`, `+++++++`, and `>>>>>>>`. If a real content line appears
  with a leading marker prefix like `+- streaming export (...)`, keep the content
  line without that extra marker prefix. When `integrate.sh` prints a
  marker-stripped preview, use it to inspect candidates faster, but still verify
  the final file yourself. For purely additive conflicts, you may apply the
  preview with the printed `conflict-preview.py --write ...` command, then inspect
  structured files and adjust any single-valued fields before `--continue`.
- After editing, rerun the helper with `--continue`; do not invent extra
  publish/cleanup commands unless the helper failed.

## 4. Touch only your own work (shared-checkout etiquette)

Several agents may share one machine, or even one checkout. Act only on the work
**you** authored:

- **Commit and publish only your own changes.** Never `jj describe` / `git commit
  -a` a shared checkout's whole dirty tree, and never push a commit that bundles
  edits you didn't make. If the working copy holds changes you don't recognize,
  **stop and surface them** — don't sweep them into your commit or take authorship.
  (Isolating first, §2, is what keeps your working copy yours; the helpers reinforce
  it — `integrate.sh` lands only the branch/bookmark you name, never the live tree.)
- **Clean up only what you created.** An unqualified "clean up" means *your own*
  `<ide>-<work>` workspaces/bookmarks. Do not inspect, reason about, or ask about
  another agent's workspace/bookmark — leave it untouched unless the user names it.
  The one thing you may retire that you didn't create is a sibling jj workspace
  whose work has already **landed on `main`** during an integration task (merged
  residue, handled automatically by `integrate.sh`) — never another agent's
  *unmerged* work.

## 5. Fallback docs and commits

Detailed fallback markdown lives beside this file. Do not read it up front. Open
the matching fallback only if a helper is missing, reports an unexpected setup
problem, or you are authoring/editing a commit message.

</skill>
```

## Assistant

```text
Using `vcs` first because this is repo work, and `improving-vcs-skill` because the request is about improving the `vcs` skill. I’m going to create the requested `codex-vcs-guardrails` jj workspace before reading or editing project files.
```

Tool: Bash `jj root && bash [REDACTED_LOCAL_PATH]/coding-agent-skills/.agents/skills/vcs/scripts/isolate.sh codex-vcs-guardrails`

## Assistant

```text
The workspace was created at `.`, and I’m switching all work there. Next I’m reading the existing `vcs` and harness docs plus the recorded incident files so the plan is grounded in the repo’s current mechanics.
```

Tool: Bash `sed -n '1,220p' .agents/skills/vcs/SKILL.md`

Tool: Bash `sed -n '1,260p' .agents/skills/improving-vcs-skill/SKILL.md`

Tool: Bash `sed -n '1,220p' docs/issues/0002-20260607-agent-used-default-jj-workspace-instead-of-isolating.md`

Tool: Bash `sed -n '1,260p' docs/issues/0005-20260607-concurrent-cursor-agent-committed-and-pushed-another-agents-work.md`

## Assistant

```text
The two incident notes point to the same root: advisory instructions are losing to session-start/cwd mistakes. I’m checking the helper scripts and jj operation history now to identify what can be converted into mechanical guardrails and what has to be enforced by IDE/session hooks.
```

Tool: Bash `ls .agents/skills/vcs/scripts`

Tool: Bash `sed -n '1,260p' .agents/skills/vcs/scripts/isolate.sh`

Tool: Bash `sed -n '1,320p' .agents/skills/vcs/scripts/integrate.sh`

Tool: Bash `jj op log --limit 80`

## Assistant

```text
The op log already shows the damaging signatures: `jj bookmark set main -r @`, `jj new main`, `jj describe`, and `jj git push --bookmark main` executed from `default@` during agent/harness work. I’m going to inspect the rest of the integration helper and the harness start/isolation checks before drafting the plan.
```

Tool: Bash `sed -n '320,760p' .agents/skills/vcs/scripts/integrate.sh`

Tool: Bash `sed -n '1,260p' .agents/skills/improving-vcs-skill/scripts/check-isolation.sh`

Tool: Bash `sed -n '1,320p' .agents/skills/improving-vcs-skill/scripts/new-sandbox.sh`

Tool: Bash `sed -n '1,280p' .agents/skills/improving-vcs-skill/LOOP.md`

## Assistant

```text
The harness already has `--task start` plus `check-isolation.sh`, which is the right validation surface for the “forgot to isolate” problem. I’m checking whether this session exposes a lower-tier sub-agent runner; if not, the plan will document the exact harness validation command and the missing execution dependency.
```

Tool: ToolSearch tool search

## Assistant

```text
I found a lower-tier sub-agent runner. I’m going to run one focused `improving-vcs-skill` start-round validation in a disposable jj sandbox: it tests whether a small model starting in shared `default` creates its own jj workspace before making the tiny change.
```

Tool: Bash `bash .agents/skills/improving-vcs-skill/scripts/new-sandbox.sh --mode jj --task start --start-from main --round 7002 --workdir /tmp/vcs-harness-codex-vcs-gua...`

Tool: Bash `sed -n '1,220p' /tmp/vcs-harness-codex-vcs-guardrails/round-7002/briefs/agent-1.md`

Tool: Bash `sed -n '1,80p' /tmp/vcs-harness-codex-vcs-guardrails/round-7002/manifest.env`

## Assistant

```text
I’m keeping the validation narrow: one small-model agent, one jj start round, and only the `vcs` skill plus the ticket brief. That checks the weakest current behavior without changing the real repo.
```

Tool: Bash `rg -n "STRUCTURED|Report|report back|When done|TEMPLATE|format" .agents/skills/improving-vcs-skill/METRICS.md .agents/skills/improving-vcs-skill -g '*.md'`

Tool: Bash `sed -n '1,220p' .agents/skills/improving-vcs-skill/METRICS.md`

## Assistant

```text
Starting the lower-tier validation agent now. I’ll let it do only the sandbox ticket, then I’ll score the result with `check-isolation.sh` and `check-quality.sh`.
```

Tool: Subagent spawn `gpt-5.4-mini` validation agent

## Assistant

```text
While the validation agent runs, I’m checking the repo’s plan-doc style and existing permission/guardrail files. The plan should separate repo-local `vcs` changes from agent-environment controls like Codex/Claude permissions.
```

Tool: Bash `ls docs/plans`

Tool: Bash `rg -n "permission|permissions|allow|deny|disallow|sandbox|safe|hook|hooks|preTool|PreTool|command" .agents docs scripts .claude -g '!docs/coding-sessions/**'`

Tool: Bash `rg -n "vcs-check|guard|default workspace|workspace add|jj op log|op log|bookmark set main|git push|forbid|deny" .agents/skills/vcs .agents/skills/improving-v...`

Tool: Bash `jj status`

## Assistant

```text
The repo only has `.claude/settings.json` checked in for permissions right now, and no `docs/plans/` directory yet. Because the plan touches agent permission/hook formats, I’m also going to verify current official docs rather than assume the hook syntax.
```

Tool: Bash `sed -n '1,220p' .claude/settings.json`

Tool: Bash `sed -n '1,180p' .agents/skills/update-agent-permissions/SKILL.md`

Tool: Bash `rg --files -g '.codex/**' -g '.cursor/**' -g '.gemini/**' -g '.antigravity/**' -g '.claude/**'`

Tool: Bash `sed -n '1,220p' docs/issues/0004-20260607-benchmark-created-jj-workspace-but-never-used-it.md`

Tool: WebSearch site:docs.anthropic.com Claude Code hooks PreToolUse settings.json permissions allow deny

Tool: WebSearch site:docs.anthropic.com/en/docs/claude-code hooks PreToolUse settings.json

Tool: WebSearch web search

Tool: WebSearch web search

Tool: WebSearch web search

Tool: WebSearch site:developers.openai.com codex cli config.toml approval_policy sandbox_mode hooks rules

## Assistant

```text
For Claude Code, the official docs confirm lifecycle hooks including `SessionStart`, `PreToolUse`, `SubagentStart`, and `CwdChanged`, plus project-shareable `.claude/settings.json`. For Codex, I’m checking the local CLI/config surface before making any recommendation because per-project hook support is not something to guess at.
```

Tool: Bash `command -v codex`

Tool: Bash `codex --help`

Tool: Bash `find . -maxdepth 3 -iname '*codex*' -o -path './.codex/*'`

Tool: Bash `find ~/.codex -maxdepth 3 -type f \( -name 'config.toml' -o -name '*.rules' -o -name 'AGENTS.md' \) 2>/dev/null`

## User

```text
<subagent_notification>
{"agent_path":"019ea235-92a5-7521-b018-a05e60458fee","status":{"completed":"=== VCS RUN REPORT ===\nmode_detected:   jj\ntier:            small\ntotal_seconds:   26\nconflict_seconds:0\nconflicts_hit:   0\nretries:         0\nstalls:          0\nclear:           `vcs` clearly required isolating first, then using `isolate.sh` and `integrate.sh`; the helper flow worked cleanly and fast-forwarded `main` without a merge.\nambiguous:       The exact changelog layout in `docs/CHANGELOG.md` differed slightly from the ticket wording, so I had to inspect the file before inserting the new first list item.\nmishandled:      none\n=== END ==="}}
</subagent_notification>
```

## Assistant

```text
The small-model validation agent finished and reported it used jj isolation. I’m scoring that objectively now, then I’ll fold the result into the plan doc.
```

Tool: Bash `bash .agents/skills/improving-vcs-skill/scripts/check-isolation.sh /tmp/vcs-harness-codex-vcs-guardrails/round-7002`

Tool: Bash `bash .agents/skills/improving-vcs-skill/scripts/check-quality.sh /tmp/vcs-harness-codex-vcs-guardrails/round-7002`

Tool: Bash `sed -n '1,220p' .codex/config.toml`

Tool: Bash `sed -n '1,260p' .codex/rules/default.rules`

Tool: WebSearch web search

Tool: WebSearch web search

Tool: WebSearch web search

Tool: WebSearch web search

## Assistant

```text
I have enough to draft the plan. The shape I’m proposing is defense in depth: a session-start bootstrap, edit/write-time guards, publish-time permission gates, and harness metrics that specifically score parent-agent and sub-agent cwd mistakes.
```

Tool: Bash `jj workspace --help`

Tool: Bash `codex debug --help`

Tool: Bash `codex execpolicy check --help`

Tool: Bash `jj op log --limit 35 --no-graph`

## Assistant

```text
One useful jj detail: `jj workspace rename` exists, so a two-phase bootstrap is feasible. The plan can create a temporary session workspace before the agent knows the task name, then rename it once the task slug is clear.
```

Tool: Bash `jj bookmark --help`

Tool: Bash `jj workspace rename --help`

Tool: Bash `codex --version`

Tool: Bash `jj workspace list -T 'name ++ "\t" ++ root ++ "\n"'`

Tool: WebSearch web search

Tool: WebSearch web search

## Assistant

```text
I’m adding a plan document only. No `vcs` helper, hook, permission, or harness code will be changed in this pass.
```

Tool: Bash `mkdir -p docs/plans`

Tool: apply_patch

## Assistant

```text
The plan file is in place. I’m formatting just that new Markdown file and then I’ll verify the workspace diff.
```

Tool: Bash `sed -n '1,260p' package.json`

Tool: Bash `jj diff --stat`

## Assistant

```text
`jj diff --stat` was empty, so I’m checking whether the new `docs/plans/` path is ignored or if jj hasn’t snapshotted it yet.
```

Tool: Bash `jj status`

Tool: Bash `ls -l docs/plans && sed -n '1,80p' docs/plans/0001-vcs-guardrails-for-jj-workspace-isolation.md`

Tool: Bash `jj file list docs/plans`

Tool: Bash `rg -n "docs/plans|plans" .gitignore .ignore .jjignore .prettierignore .markdownlint-cli2.jsonc 2>/dev/null`

## Assistant

```text
The `apply_patch` tool applied relative to the original checkout rather than the jj workspace. I’m correcting that now: removing the accidental file from `default` and adding the same plan under the `codex-vcs-guardrails` workspace.
```

Tool: Bash `ls -l [REDACTED_LOCAL_PATH]/coding-agent-skills/docs/plans && sed -n '1,40p' [REDACTED_LOCAL_PATH]/coding-agent-skills/docs/plans/0001-vcs-guardrails-f...`

Tool: Bash `jj -R [REDACTED_LOCAL_PATH]/coding-agent-skills status`

Tool: apply_patch

## Assistant

```text
The patch mover cannot handle an empty cross-workspace move hunk, so I’m using a filesystem move for the file I just created by mistake. This moves my own accidental addition out of `default` into the requested workspace.
```

Tool: Bash `mv [REDACTED_LOCAL_PATH]/coding-agent-skills/docs/plans/0001-vcs-guardrails-for-jj-workspace-isolation.md [REDACTED_LOCAL_PATH]/coding-agent-skills-cod...`

Tool: Bash `rmdir [REDACTED_LOCAL_PATH]/coding-agent-skills/docs/plans 2>/dev/null || true`

## Assistant

```text
The accidental default-workspace addition has been moved out and the empty directory removed. I’m verifying both workspaces now before formatting/checking the final plan file.
```

Tool: Bash `jj -R [REDACTED_LOCAL_PATH]/coding-agent-skills status`

Tool: Bash `jj status`

Tool: Bash `ls -l docs/plans && sed -n '1,120p' docs/plans/0001-vcs-guardrails-for-jj-workspace-isolation.md`

Tool: Bash `bunx prettier --write docs/plans/0001-vcs-guardrails-for-jj-workspace-isolation.md`

## Assistant

```text
Prettier completed, but `bunx` reported a lockfile write, so I’m checking whether it changed any dependency metadata. If it did, I’ll remove that unrelated output from this plan-only change.
```

Tool: Bash `jj status`

Tool: Bash `jj diff --stat`

Tool: Bash `ls -la | sed -n '1,80p'`

Tool: Bash `git status --short`

## Assistant

```text
Only the plan file is changed in the `codex-vcs-guardrails` workspace. I’m running targeted format and Markdown lint checks now.
```

Tool: Bash `bunx prettier --check docs/plans/0001-vcs-guardrails-for-jj-workspace-isolation.md`

Tool: Bash `bunx markdownlint-cli2 docs/plans/0001-vcs-guardrails-for-jj-workspace-isolation.md`

## Assistant

```text
Prettier passed. Markdownlint did not report the new plan file, but the command exits nonzero because the repo’s current config lints the whole tree and there are pre-existing errors in other Markdown files. I’m checking the diff one last time.
```

Tool: Bash `jj status`

Tool: Bash `jj diff --stat`

Tool: Bash `sed -n '1,260p' .markdownlint-cli2.jsonc`

Tool: Bash `jj -R [REDACTED_LOCAL_PATH]/coding-agent-skills status`

Tool: Bash `bunx markdownlint-cli2 --help | sed -n '1,180p'`

## Assistant

```text
`markdownlint-cli2` has a `--no-globs` switch, so I’m rerunning it against only the new plan file instead of the repo-wide configured glob.
```

Tool: Bash `bunx markdownlint-cli2 docs/plans/0001-vcs-guardrails-for-jj-workspace-isolation.md --no-globs`

## Assistant

```text
The targeted lint check passed with zero errors. I’m closing the validation sub-agent and then I’ll summarize the plan location and validation result.
```

Tool: Subagent close validation agent

## Assistant

```text
Created the plan under [docs/plans/0001-vcs-guardrails-for-jj-workspace-isolation.md](./docs/plans/0001-vcs-guardrails-for-jj-workspace-isolation.md). I did not implement helper, hook, permission, or harness changes.

I also ran one lower-tier `improving-vcs-skill` validation round with `gpt-5.4-mini` on `jj --task start --start-from main`; it passed objectively: `ISOLATED=pass`, `NAME_OK=pass`, `RESULT: PASS`. The plan notes the caveat: this validates the current happy path, not the parent-agent/wrong-cwd failure path we need to add next.

Verification:
- `bunx prettier --check docs/plans/0001-vcs-guardrails-for-jj-workspace-isolation.md` passed.
- `bunx markdownlint-cli2 docs/plans/0001-vcs-guardrails-for-jj-workspace-isolation.md --no-globs` passed.
- The default workspace is clean; the only change is the new plan file in `codex-vcs-guardrails`.

Docs checked: [Claude hooks](https://code.claude.com/docs/en/hooks), [Claude CLI permissions](https://code.claude.com/docs/en/cli-usage), [Codex config](https://developers.openai.com/codex/config-advanced), [Codex hooks](https://developers.openai.com/codex/hooks), and [Codex rules](https://developers.openai.com/codex/rules).
```

## User

```text
Answers to the open question:

1. Always create new workspace, it's okay to risk stale abandoned workspaces.
2. I don't know, come up with an idea.
3. jj and git push should be allowed by default without human approval, otherwise things are too slow.
4. Don't worry about cloud PRs, focus on local for now.
```

## User

```text
<turn_aborted>
The user interrupted the previous turn on purpose. Any running unified exec processes may still be running in the background. If any tools/commands were aborted, they may have partially executed.
</turn_aborted>
```

## User

```text
Update the plan, then export chat session, commit and merge using the [$vcs]([REDACTED_LOCAL_PATH]/coding-agent-skills/.agents/skills/vcs/SKILL.md) skill.
```

## User

```text
<skill>
<name>vcs</name>
<path>[REDACTED_LOCAL_PATH]/coding-agent-skills/.agents/skills/vcs/SKILL.md</path>
---
name: vcs
description: Load at the START of new repo work, BEFORE you change any file, so
  you isolate the work in your own workspace/worktree first — and again BEFORE
  any commit, merge, rebase, or publish. Works in any VCS (Jujutsu or Git).
---

# VCS

**Isolate before you edit.** For any new work, do not change a single file in
the checkout you were handed. First understand the task well enough to name it
`<ide>-<work>` (e.g. `claude-fix-auth-retry`), then create your own
workspace/worktree (§2) and work there. The one exception: a dedicated cloud/PR
session, where you already have your own clone — then skip isolation.

Then follow this skill for every commit, merge, rebase, and publish too, in
whatever version-control system the repo uses.

## 1. Detect the mode first - before any VCS action

Run `jj root` (or look for a `.jj/` directory).

- **It succeeds -> Jujutsu (jj) mode.** Use jj for everything, **even though Git
  commands also work** — a colocated repo has both `.git` and `.jj`, and a naive
  "is this Git?" check picks the wrong tool. jj is the right tool whenever jj is
  present.
- **It fails / no `.jj` -> Git mode.** Plain Git, including a Git _worktree_ (where
  `.git` is a file pointing into a parent repo). Use Git.

Stay in that mode the whole session and re-confirm it before you publish; never
cross tools (don't run jj in a Git repo, or fall back to raw git in a jj repo).

## 2. For standard flows, run the helper first

Do not spend tokens re-deriving the routine command chain. The bundled helpers
detect the mode and run the standard Git/jj mechanics. Use prose judgment only
when a helper stops for semantic conflict resolution or reports an unexpected
condition.

- **Starting new local work:** from the checkout you were handed, run
  `bash <skill-dir>/scripts/isolate.sh <ide>-<work>`, for example
  `bash <skill-dir>/scripts/isolate.sh codex-fix-auth-retry`. If it prints
  `NEXT_CWD=...` (it created a fresh workspace/worktree), `cd` there **before you
  edit, read, or run anything else** — every command for this work runs from that
  path, not the checkout you started in. Creating the workspace but staying put
  silently writes into the shared checkout. If instead it prints `CREATED=no` you
  are already isolated; work in place. In a dedicated cloud/PR session you already
  have your own clone; skip isolation.
- **Landing committed work on shared `main`:** run
  `bash <skill-dir>/scripts/integrate.sh <branch-or-bookmark>`, for example
  `bash <skill-dir>/scripts/integrate.sh agent-2`. If it prints
  `VCS_CONFLICT=...`, resolve only the listed files using the conflict etiquette
  below, then rerun
  `bash <skill-dir>/scripts/integrate.sh --continue <branch-or-bookmark>`.

`integrate.sh` handles the no-ambiguity finish steps: Git fetch/rebase/push retry,
safe additive Git conflict cleanup for text/JSON files, deterministic
higher-version scalar tie-breaks in config files, jj merge formation, stale
workspace recovery, `main` movement checks, `jj git export`, merged
branch/bookmark deletion when no real remote backs it, parking jj `default` on
`main`, retiring landed jj agent workspaces, and auto-resolving jj conflicts that
are mechanically additive and structurally valid. If it prints `NEXT_CWD=...`,
run any later shell command from that live directory because your jj workspace
was intentionally removed.

## 3. Conflict etiquette

When the helper stops for conflicts, the agent's job is semantic resolution:

- Union every additive change. Keep every changelog entry, list/array element,
  and code block that any side added. Do not drop teammates' work.
- For a single-valued field set to different values, keep the higher value.
  Compare values directly; do not rely on "ours" or "theirs" labels.
- Never resolve a whole file with one side (`ours`, `theirs`, `-X ours`).
- Remove every conflict marker: `<<<<<<<`, `=======`, `>>>>>>>`, `|||||||`.
- jj conflicts are diff-style. Drop marker/header lines such as `<<<<<<<`,
  `%%%%%%%`, `\\\\\\\`, `+++++++`, and `>>>>>>>`. If a real content line appears
  with a leading marker prefix like `+- streaming export (...)`, keep the content
  line without that extra marker prefix. When `integrate.sh` prints a
  marker-stripped preview, use it to inspect candidates faster, but still verify
  the final file yourself. For purely additive conflicts, you may apply the
  preview with the printed `conflict-preview.py --write ...` command, then inspect
  structured files and adjust any single-valued fields before `--continue`.
- After editing, rerun the helper with `--continue`; do not invent extra
  publish/cleanup commands unless the helper failed.

## 4. Touch only your own work (shared-checkout etiquette)

Several agents may share one machine, or even one checkout. Act only on the work
**you** authored:

- **Commit and publish only your own changes.** Never `jj describe` / `git commit
  -a` a shared checkout's whole dirty tree, and never push a commit that bundles
  edits you didn't make. If the working copy holds changes you don't recognize,
  **stop and surface them** — don't sweep them into your commit or take authorship.
  (Isolating first, §2, is what keeps your working copy yours; the helpers reinforce
  it — `integrate.sh` lands only the branch/bookmark you name, never the live tree.)
- **Clean up only what you created.** An unqualified "clean up" means *your own*
  `<ide>-<work>` workspaces/bookmarks. Do not inspect, reason about, or ask about
  another agent's workspace/bookmark — leave it untouched unless the user names it.
  The one thing you may retire that you didn't create is a sibling jj workspace
  whose work has already **landed on `main`** during an integration task (merged
  residue, handled automatically by `integrate.sh`) — never another agent's
  *unmerged* work.

## 5. Fallback docs and commits

Detailed fallback markdown lives beside this file. Do not read it up front. Open
the matching fallback only if a helper is missing, reports an unexpected setup
problem, or you are authoring/editing a commit message.

</skill>
```

## Assistant

```text
I’m continuing in the existing `codex-vcs-guardrails` jj workspace and will use `vcs` again before commit/merge. I’ll first update the plan with your answers, then export the session transcript, verify, describe the work, and land it through `integrate.sh`.
```

Tool: Plan update task checklist

## Assistant

```text
Using `export-coding-session` because you explicitly asked to export this chat session. I’m reading its instructions now so the export lands in the repo’s expected transcript format.
```

Tool: Bash `sed -n '1,260p' [REDACTED_LOCAL_PATH]/coding-agent-skills/.agents/skills/export-coding-session/SKILL.md`

Tool: Bash `jj root && jj workspace list -T 'name ++ "\t" ++ root ++ "\n"' && jj status`

Tool: Bash `sed -n '1,280p' docs/plans/0001-vcs-guardrails-for-jj-workspace-isolation.md`

## Assistant

```text
I’m applying your decisions directly into the plan: always bootstrap a workspace, use a local VCS-admin/session-state marker, keep pushes allowed by default but guarded by cwd/ownership checks, and defer cloud/PR handling.
```

Tool: apply_patch

## Assistant

```text
The plan now reflects your answers and removes the resolved open questions. Next I’m exporting the session transcript using the repo’s export helper and then I’ll scan it for redaction issues.
```

Tool: Plan update task checklist

## Assistant

```text
The export helper determines the next global transcript index, so I’m using that rather than choosing a filename manually.
```

Tool: Bash `bash [REDACTED_LOCAL_PATH]/coding-agent-skills/.agents/skills/export-coding-session/next-index.sh`

## Assistant

```text
I’m locating the current Codex JSONL transcript now. I’ll render a concise Markdown transcript with summarized tool calls, then run the bundled redaction scanner.
```

Tool: Bash `find ~/.codex/sessions -type f -name '*.jsonl' -print0 2>/dev/null | xargs -0 ls -t | head -20`

Tool: Bash `jj config get user.name && jj config get user.email`

Tool: Bash `sed -n '1,120p' docs/coding-sessions/2026-06-07/0022-claude-vcs-issues-567-orphan-heads.md`

## Assistant

```text
The transcript JSONL is large and structured, so I’m using a small parser to extract user/assistant turns and summarize tool calls. I’ll keep the export concise like the existing session logs rather than dumping raw tool output.
```

Tool: Bash `head -5 [REDACTED_LOCAL_PATH]/.codex/[REDACTED]`

Tool: Bash `wc -l [REDACTED_LOCAL_PATH]/.codex/[REDACTED] [REDACTED_LOCAL_PATH]/.codex/[REDACTED]`

Tool: Bash `tail -5 [REDACTED_LOCAL_PATH]/.codex/[REDACTED]`

Tool: Bash `python3 - <<'PY' import json p='[REDACTED_LOCAL_PATH]/.codex/[REDACTED]' from collec...`

## Assistant

```text
I’m generating the transcript at `docs/coding-sessions/2026-06-07/0023-codex-vcs-guardrails-plan.md`. The renderer normalizes local absolute paths and omits raw tool outputs so the transcript stays useful and reviewable.
```

Tool: Bash `python3 - <<'PY' import json, pathlib, re, shlex from datetime import datetime  session = pathlib.Path('[REDACTED_LOCAL_PATH]/.codex/[REDACTED]`

## Assistant

```text
The transcript file has been generated. I’m running the export skill’s redaction scanner and reviewing the rendered file for any remaining local paths or sensitive material.
```

Tool: Bash `bash [REDACTED_LOCAL_PATH]/coding-agent-skills/.agents/skills/export-coding-session/redaction-scan.sh docs/coding-sessions/2026-06-07/0023-codex-vcs-guard...`

Tool: Bash `sed -n '1,220p' docs/coding-sessions/2026-06-07/0023-codex-vcs-guardrails-plan.md`

Tool: Bash `rg redaction-patterns docs/coding-sessions/2026-06-07/0023-codex-vcs-guardrails-plan.md`

## Assistant

```text
The redaction scanner found no obvious sensitive patterns, and a manual path scan found no remaining local absolute paths. I’m checking formatting and Markdown lint on both changed files now.
```

Tool: Bash `bunx prettier --check docs/plans/0001-vcs-guardrails-for-jj-workspace-isolation.md docs/coding-sessions/2026-06-07/0023-codex-vcs-guardrails-plan.md`

Tool: Bash `bunx markdownlint-cli2 docs/plans/0001-vcs-guardrails-for-jj-workspace-isolation.md docs/coding-sessions/2026-06-07/0023-codex-vcs-guardrails-plan.md --no-globs`

Tool: Bash `jj diff --stat && jj status`

## Assistant

```text
The first transcript render preserved raw skill/context blocks, which made markdownlint parse embedded XML/headings as document structure. I’m regenerating it with each turn body fenced as text so the transcript remains faithful and lint-clean.
```

Tool: Bash `python3 - <<'PY' import json, pathlib, re  session = pathlib.Path('[REDACTED_LOCAL_PATH]/.codex/[REDACTED]`
