<!-- markdownlint-disable MD013 MD024 -->

# Inception GUI: fix black-page flash and add staged querying/answering indicators

- **Date:** 2026-06-13
- **Repo:** coding-agent-skills (bookmark `claude-pending-eb9b37e0`, change `xulrozktupss`)
- **Author:** Shuyang Sun <shuyangsun10@gmail.com>
- **Agent:** Claude Code (Opus 4.8, 1M context, thinking: high)
- **Summary:** Diagnosed why the inception RAG GUI blanks to black on submit (a `useActionState` transition re-rendering the route subtree), replaced it with a plain async handler that exposes distinct `querying` → `answering` stages, and raised the default `maxTokens` from 800 to 16384.

## User

Fix an issue on the @inception/ GUI. When I hit enter after typing in a query, the whole page goes black, after the query returns, the page shows up again. I'm not sure why, but there should be some type of "querying" indicator and "answering" indicator to indicate different stages. Also, set the default max token to 16384 instead of 800.

## Assistant

Explored the `inception/` app structure and read the relevant source: `src/components/app.tsx`, `results.tsx`, `search-bar.tsx`, `answer-view.tsx`, `llm-panel.tsx`, `ui.tsx`, the routes (`__root.tsx`, `index.tsx`), `router.tsx`, `src/server/rag.ts`, `src/lib/settings.ts`, `src/lib/theme.ts`, `src/types/rag.ts`, and `styles.css`.

Root-cause analysis: the request was driven by React's `useActionState`, whose action runs inside a React **transition**. In this TanStack Start SSR setup the transition briefly re-renders the route subtree and commits nothing, so in dark mode the bare `--base: #0a0b0d` body shows through (the "black") until the action resolves. No Chrome DevTools MCP was available to reproduce live, so the fix was reasoned from the code.

Implemented changes:

- **`src/types/rag.ts`** — added `SearchPhase = "idle" | "querying" | "answering"`.
- **`src/components/app.tsx`** — replaced `useActionState` with a plain `async` `submit()` handler backed by `useState` for `state` and `phase`, guarded by an `inFlight` ref and wrapped in `try/catch`. In answer mode it retrieves first (`querying`), renders the matched chunks, then runs the LLM call (`answering`); retrieve mode is a single `querying` phase.
- **`src/components/results.tsx`** — `Results` now takes `phase` instead of `pending`/`mode`; `LoadingPanel` and `PendingBar` show **Querying…** vs **Generating answer…** by phase.
- **`src/components/search-bar.tsx`** — takes `phase`; submit button reads **Querying… / Generating…**.
- **`src/lib/settings.ts`** — `DEFAULT_LLM.maxTokens` 800 → 16384.
- **`src/components/llm-panel.tsx`** — Max-tokens clamp fallback 800 → 16384.

Verification: `tsgo --noEmit` passed (via a temporary `node_modules` symlink, since the jj worktree has no installed deps); no test files exist. Flagged one tradeoff — answer mode now does a separate retrieval call before `/answer` (which re-retrieves internally), so retrieval runs twice; cheap locally and it lets chunks appear while the model generates. Offered to collapse back to a single `/answer` call, to verify live with `bun run dev`, or to commit.

## User

Export transcript then integrate with /vcs

## Assistant

Exported this transcript to `docs/transcripts/2026-06-13/0069-claude-inception-gui-querying-indicator.md`, then proceeded to integrate the work via the `vcs` skill.
