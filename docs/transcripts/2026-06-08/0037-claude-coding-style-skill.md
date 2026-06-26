---
title: "Coding-style skill: non-negotiable React + TypeScript rules with oxlint enforcement"
date: 2026-06-08
repo: "coding-agent-skills (jj workspace / bookmark `claude-coding-style`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Opus 4.8, 1M context, thinking: high)"
summary: >-
  Started as a request for an `inception/docs/coding-style.md` doc plus linter/formatter
  enforcement of modern React 19 + TypeScript practices; pivoted (per follow-up turns)
  into a reusable, repo-agnostic `coding-style` skill that declares style rules
  non-negotiable and routes by technology to `styles/react.md` / `styles/typescript.md`,
  with the oxlint rules extracted into reusable `*.oxlintrc.json` fragments consumed via
  `extends`. Research was fan-out + adversarially verified; the headline "ban memoization"
  was implemented as an error-level ban with a documented escape hatch for three real
  exceptions.
---

<!-- markdownlint-disable MD013 MD024 -->

# Coding-style skill: non-negotiable React + TypeScript rules with oxlint enforcement

## User

Create a new file @inception/docs/coding-style.md, then research and write modern React and TypeScript development best practices. For example, ban memoization for React and only use React compiler. Keep it concise and clear. Also setup linters and formatters under the @inception/ project (or project root) to enforce these rules whenever possible.

_(The message was interrupted once and then resent verbatim.)_

## Assistant

Scouted the `inception` project and the repo root before acting:

- Renamed the session's isolated jj workspace to `claude-coding-style` via the vcs skill's `rename-work.sh`.
- Read `inception/package.json`, `tsconfig.json`, `vite.config.ts`, `README.md`, `.cta.json`, and the `src/` tree. Findings: TanStack Start + Router, **React 19.2 with the React Compiler already enabled** (`babel-plugin-react-compiler` + `reactCompilerPreset()`), **TypeScript 7** via `tsgo` (native preview), Bun, Tailwind v4. tsconfig already strict (`verbatimModuleSyntax`, `noUnusedLocals/Parameters`).
- Read the repo-root toolchain: **oxlint** (`.oxlintrc.json`), **Prettier**, **markdownlint-cli2**, **lefthook** (+ `jj fix`). Decided to **extend the existing oxlint config** rather than introduce a competing toolchain.

Validated the enforcement approach locally before writing any config:

- `bun install` at root to get the pinned tooling.
- Enumerated oxlint 1.68's actual rule set from `node_modules/oxlint/configuration_schema.json` (the `--rules` flag printed nothing). Confirmed `react/rules-of-hooks`, `react/exhaustive-deps`, a rich React + TypeScript rule set, **no** react-compiler rule, **no** `no-restricted-syntax`, but `no-restricted-imports` is supported.
- Proved with throwaway files that `no-restricted-imports` flags `useMemo`/`useCallback`/`memo`/`forwardRef` from `react`, and that oxlint `overrides` scoping works.

Launched a background research **Workflow** (9 agents): four parallel dimensions (React 19/Compiler, modern TypeScript, TanStack/Tailwind/Bun ecosystem, enforcement tooling) → per-dimension adversarial fact-checkers → a synthesis agent returning a structured outline + an oxlint rule map. Key verified result: a **literal blanket ban on memoization contradicts react.dev's own escape-hatch guidance** — `useMemo`/`useCallback`/`memo` remain legitimate in three documented cases (effect-dependency stability, non-React reference-identity libraries, measured-expensive computation).

Wrote `inception/docs/coding-style.md`: a concise DO/DON'T guide leading with "trust the React Compiler," covering Rules of React/Hooks, React 19 APIs (ref-as-prop, `<Context>`, inline metadata, Actions/`use()`), effects & data (loaders over `useEffect`), components/keys, TypeScript (imports/nullability, modeling, compiler config), and an enforcement section.

Extended the root `.oxlintrc.json` with an `inception/**`-scoped `overrides` block: the memoization ban (error + custom message), React-hooks/correctness rules, and TypeScript style rules. Deliberately **excluded `react-perf` rules** (flagging inline props contradicts the "let the compiler memoize" thesis).

## User

Actually, create a new `coding-style` skill, which instructs agents to treat coding style rules as non-negotiable rules in the main SKILL.md file, but the skill body only references other files based on Technology (e.g., styles/react.md, styles/typescript.md, styles/cpp.md, etc.). Move your research to @.agents/skills/coding-style/styles/react.md (and @.agents/skills/coding-style/styles/typescript.md if applicable).

## Assistant

Studied repo skill conventions (`.agents/skills/docs/SKILL.md` frontmatter; confirmed `.claude/skills` is a single directory symlink to `.agents/skills`, so a new skill dir is auto-discovered). Built the skill:

- `.agents/skills/coding-style/SKILL.md` — declares the rules **non-negotiable** with an explicit precedence (user instruction > the matching rules file > habits/defaults), tells the agent to read the file matching _each_ technology it touches (a `.tsx` is both React and TypeScript), and documents how to add new `styles/<tech>.md` files.
- `styles/react.md` and `styles/typescript.md` — moved the verified research in, generalized to be repo-agnostic, each ending in an **Enforcement** section. The escape hatch for the memoization ban is shown as a `// eslint-disable-next-line no-restricted-imports -- <reason>` comment.

Removed the now-superseded `inception/docs/coding-style.md` ("moved" into the skill).

## User

Extract related parts of `.oxlintrc.json` into the style/ directory under the skill as well, so it can be reused by other projects.

## Assistant

Checked oxlint's `extends` semantics against its schema: **`extends` is top-level only** — the `OxlintOverride` schema has no `extends` key, so a shared fragment can't be scoped inside an `overrides` entry. Confirmed only `inception/` has React/TS code (three `.wf.js` workflow scripts elsewhere contain no JSX and don't import React), so applying the fragments globally via top-level `extends` is equivalent to the prior scoping.

- Created reusable, unscoped fragments `styles/react.oxlintrc.json` and `styles/typescript.oxlintrc.json` (plugins + rules, no `$schema` path so they stay portable).
- Rewrote the root `.oxlintrc.json` to consume both via top-level `extends`, dropping the inline override.
- Updated `styles/react.md` / `styles/typescript.md` Enforcement sections to point at the fragments and show the `extends` usage, and updated `SKILL.md` to tell future tech files to ship a fragment too.

Verification (all from the workspace):

- `bun run lint:code` (oxlint, whole repo): **PASS**. The one warning that surfaced — `consistent-type-definitions` on `inception/src/router.tsx`'s TanStack `Register` interface — is a _required_ module augmentation (`interface` is mandatory there), so I added a documented `// eslint-disable-next-line typescript/consistent-type-definitions -- module augmentation requires interface` opt-out (which also demonstrates the skill's escape-hatch pattern in real code).
- Re-confirmed the memoization ban fires on all four imports as errors and the escape hatch suppresses it.
- `bun run format:check` (Prettier): **PASS** on all new/changed files (formatted `SKILL.md`'s table).
- markdownlint: the new skill files are clean; the failures `bun run lint:md` reports are pre-existing debt in committed `docs/` transcripts, untouched by this change.
- Typecheck not run — the only inception code edit is a lint-disable comment with zero type-surface impact.

Recorded two agent-memory notes (the `coding-style` skill; oxlint config gotchas) and indexed them.

Final change set in the `claude-coding-style` workspace: added `SKILL.md`, `styles/react.md`, `styles/typescript.md`, `styles/react.oxlintrc.json`, `styles/typescript.oxlintrc.json`; modified `.oxlintrc.json` and `inception/src/router.tsx`.

## User

/export-coding-session then integrate using the /vcs skill.

## Assistant

Exported this transcript to `docs/coding-sessions/2026-06-08/0037-claude-coding-style-skill.md`, ran the redaction scan, and proceeded to integrate the work via the vcs skill.
