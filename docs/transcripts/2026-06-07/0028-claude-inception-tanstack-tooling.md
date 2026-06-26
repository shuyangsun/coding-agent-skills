---
title: "inception — TanStack Start scaffold + root Prettier/oxlint/jj-fix tooling"
date: 2026-06-07
repo: "coding-agent-skills (jj workspace/bookmark `claude-inception-tanstack`, parent `main` `52354eb4`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Opus 4.8, 1M context)"
summary: >-
  Scaffolded a clean-state `inception` TanStack Start app (Vite 8, Bun, React 19 + React
  Compiler, TypeScript 7 native `tsgo` via `@typescript/native-preview`) as a target
  codebase for the `improving-docs-and-rag-skills` harness, then extended the repo-root
  tooling so Prettier formats and oxlint lints code + JSON through both the lefthook
  pre-commit hook and `jj fix`. Verified typecheck, production build, lint (clean +
  catches a planted violation), formatter, `jj fix` round-trip, and the dev server.
---

<!-- markdownlint-disable MD013 MD024 -->

# inception — TanStack Start scaffold + root Prettier/oxlint/jj-fix tooling

## User

Set up TanStack Start project using Bun and Vite.

To prepare for the /improving-docs-and-rag-skills harness, we need to create a TanStack Start project in the project's root directory. The project should be called "inception", representing the recursive abstraction and self-improving philosophy of this skill repository.

Use the latest versions of everything - TanStack Start, Vite, and Bun. Use React and do not use starting template code, make it a clean state website. Use React compiler and do not use memoization. Use TypeScript 7 beta, which is the Go version.

Once the initialization is done, setup prettier, linter, and pre-commit hook for code and json files at the project root directory (not within inception). Make sure it will work with "jj fix".

## Assistant

Confirmed I was already isolated: the SessionStart hook had created a jj workspace, which I renamed to `claude-inception-tanstack` with the `vcs` skill's `rename-work.sh`. Checked the toolchain (Bun 1.3.11, Node 24) and read the existing root tooling — `package.json`, `lefthook.yml`, `.prettierrc.json`, `.prettierignore`, `.markdownlint-cli2.jsonc`, `scripts/setup-vcs-hooks.sh`, and `AGENTS.md`. Found the root is already a Bun project with Prettier 3.8.3, lefthook, and markdownlint, and that `jj fix` is wired (via `setup-vcs-hooks.sh`) to run Prettier on Markdown only. The plan became: scaffold `inception` as a subdirectory, then extend the existing root tooling to also cover code + JSON rather than duplicating config inside `inception`.

Because these tools move fast, I researched current setup before building: parallel web searches plus the TanStack CLI's own `--help`. Key findings — scaffold via `bunx @tanstack/cli create`; React Compiler now wires into Vite 8 / `@vitejs/plugin-react` v6 through `@rolldown/plugin-babel` + `reactCompilerPreset()` (v6 dropped Babel for oxc); TypeScript 7 ships as `@typescript/native-preview` providing the `tsgo` binary. The CLI also exposes an official `compiler` add-on ("auto-memoize … no manual useMemo/useCallback"), which is exactly the requested behavior and wires the compiler in correctly.

Scaffolded with:

```bash
bunx @tanstack/cli@latest create inception --framework React \
  --package-manager bun --no-examples --no-toolchain --no-git \
  --no-intent --add-ons compiler --non-interactive
```

`--no-examples` keeps it clean-state (no demo code), `--no-toolchain` leaves linting/formatting to the root, `--no-git` avoids a nested repo. Inspected the output: Vite 8.0.16, React 19.2, the React Compiler correctly wired in `vite.config.ts`, minimal routes with no memoization. The generated `typescript ^6.0.2` was the one thing to change — I swapped it for `@typescript/native-preview` (resolved to `7.0.0-dev.20260607.1`) and added a `typecheck` script running `tsgo --noEmit`. After reinstalling, `tsgo` typechecked cleanly (exit 0) and `vite build` succeeded; I also confirmed the React Compiler is genuinely active by finding its compiler-runtime reference in the client bundle, then cleaned the build artifacts.

With the app done, I paused before the root tooling: which linter to add was a genuine fork (the project leans toward fast native tooling, but "linter for JSON" pulls toward ESLint), so I asked.

## User

(Answering the linter question) oxlint (Rust, oxc) — fast Rust-native linter from the oxc team; JSON handled by Prettier.

## Assistant

oxlint it is. Noted `routeTree.gen.ts` is a committed _generated_ file, so it must be excluded from both formatter and linter. Then wired up the root tooling, extending the existing setup rather than duplicating it:

- **`package.json`** — added `oxlint` 1.68.0 plus `lint:code` / `lint:code:fix` scripts.
- **`.oxlintrc.json`** (new) — `correctness: error`, plugins for typescript/react/import, and `ignorePatterns` for `**/routeTree.gen.ts` / `**/*.gen.ts`.
- **`.prettierignore`** — added build outputs (`dist/`, `.output/`, `.nitro/`, `.tanstack/`, …) and the generated route tree.
- **`lefthook.yml`** — added a `prettier-code` (format) job and an `oxlint --fix` job alongside the existing Markdown jobs, sequential so two tools never touch the same staged file.
- **`scripts/setup-vcs-hooks.sh`** — registered a second `jj fix` tool, `prettier-code`, covering `js,jsx,mjs,cjs,ts,tsx,mts,cts,json,jsonc,css`. The whole-file linters (markdownlint, oxlint) can't be `jj fix` stdin formatters, so they run via `bun run lint:*`, mirroring the existing markdownlint convention.

Reinstalled (the `prepare` hook re-ran `setup-vcs-hooks.sh` and reconfigured `jj fix`). Verified oxlint passes clean on the inception source and that it genuinely analyzes — a planted `debugger` statement was caught as `no-debugger` (exit 1). Ran Prettier only over the `inception/` subtree (Prettier flagged 25 files, but most were pre-existing `docs/**` and `.agents/skills/**` outside my change set, which I deliberately left untouched). Re-verified `tsgo` and oxlint after formatting. Replaced the generated marketing README with a concise, lint-clean one (the original tripped MD041).

Finally, verified the key requirement end-to-end: created mis-formatted `.ts` and `.json` probe files, ran `jj fix -s @`, and confirmed both were reformatted while `routeTree.gen.ts` (also `*.ts`) was left untouched via Prettier's ignore passthrough — then removed the probes. Did a final clean build and a `lefthook.yml` YAML sanity check (`lefthook validate` can't run in a jj workspace with no `.git` toplevel, but the YAML parses and mirrors the existing working jobs). Reported the full result and offered to run the dev server.

## User

Yes, run dev.

## Assistant

Started `bun --bun run dev` in the background and polled until the port answered. Vite 8.0.16 came up in 560 ms on port 3000, TanStack Start's SSR environment connected, and the readiness probe got an HTTP 2xx on the first try. Fetching the rendered HTML body was blocked by the sandbox's network permission, but the 2xx response plus the clean SSR boot (no errors, warnings, or unhandled rejections in the dev log) confirm the route serves. Stopped the server cleanly.

## User

Export coding session, then use /vcs to commit and push.

## Assistant

Ran the `export-coding-session` skill: took the next global index (0028) and today's dated folder, collected this session's transcript, and wrote it here in the repo's house style (verbatim user turns, summarized assistant turns), with in-repo absolute paths relativized and home-directory paths removed. Ran the redaction scanner (no sensitive patterns) and confirmed the file lints clean. Next: switch to the `vcs` skill to commit this work on the `claude-inception-tanstack` workspace and push.
