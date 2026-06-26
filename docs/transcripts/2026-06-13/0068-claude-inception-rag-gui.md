---
title: "inception — local RAG web GUI"
date: 2026-06-13
repo: "coding-agent-skills (jj bookmark: `claude-inception-rag-gui`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Opus 4.8, 1M context, thinking: max)"
summary: >-
  Built a modern, minimal TanStack Start + React 19 GUI in `inception/` for the repo's
  local RAG system, backed by a warm stdlib-Python sidecar that keeps the
  embedding/reranker models hot. Verified end-to-end (typecheck, oxlint, production build,
  and a real headless-browser drive). Removed the scaffold's TanStack devtools after the
  browser drive caught a hydration mismatch they caused.
---

<!-- markdownlint-disable MD013 MD024 -->

# inception — local RAG web GUI

## User

Create a modern and minimalistic web GUI in @inception to allow users to interact with the RAG system. The GUI should be able to:

- Set different query-time parameters
- View the list of projects
- Query the RAG system
- Display queried results in a readable format
- Answer the question with local or cloud LLM
- Support both light and dark mode

Keep it simple and easy to use. Use Bun, TanStack Start, and modern React best practices. Do NOT use memoization, use React compiler instead. Also do not use other outdated practices.

## Assistant

Loaded the `coding-style` skill and read its React + TypeScript rules (memoization banned — trust the React Compiler; `import type` mandatory under `verbatimModuleSyntax`; discriminated unions + `assertNever`; no `enum`/`any`/non-null assertions). Explored the `inception/` scaffold: a clean TanStack Start app on Vite 8, React 19 with the React Compiler preset, Bun, `tsgo`, Tailwind v4 — memoization already lint-banned. Read the two RAG memory notes (workstation serving + the staged model set).

Then mapped the RAG backend the GUI must drive — first via an `Explore` subagent, then verified the real source directly rather than trusting the paraphrase:

- Scripts live in `.agents/skills/setting-up-rag/scripts/`: `query.py`, `answer.py`, `rag_lib.py`, `rag-config.json`.
- `query.py --json` emits JSONL of `{project, kind, collection, doc_id, chunk_idx, score, text}`; `answer.py --json` emits `{question, answer, model, sources[], usage, ...}` and selects local-vs-cloud via `--base-url`/`--model`/`$RAG_LLM_*`.
- Registry at `~/.cache/rag-skill/projects.json`; Qdrant live on `localhost:6333` with **9 indexed projects** (each `code` + `md` collections).
- Query-time knobs: `--project`, `--kind {md,code,all}`, `--top-k`, `--no-rerank`; answer adds model/base-url/key/temperature/max-tokens/max-context-chars/system-prompt.

## Assistant

Two measurements decided the architecture:

1. **Latency** — a cold `query.py` subprocess is ~3.4–4.3 s because it reloads the FastEmbed dense/sparse + cross-encoder models every call. `rag_lib` caches models via `@lru_cache`, so a long-lived process stays warm. A warm probe showed **rerank-off ~0.03 s, rerank-on ~1.5 s** (the rerank cost is the CPU cross-encoder over ~50 candidates — inherent, matches the memory note). → Build a **warm Python sidecar**, don't shell out per request.
2. **Environment** — the cloud endpoint `https://llm.shuyangsun.com/v1` returns 502 (proxy parked) and no local LLM is up. → Answering must be fully configurable (base URL / model / key) and fail gracefully; retrieval works great live.

Confirmed the installed TanStack Start API (`createServerFn({method}).inputValidator(d=>d).handler(async ({data})=>…)`, called as `fn({data})`) and the `#/*` → `./src/*` path alias. Renamed the jj workspace to `claude-inception-rag-gui` and ran `bun install`.

Plan: warm sidecar (stdlib HTTP) ← dev launcher spawns it + Vite (one command) ← TanStack server-fn proxies ← React UI (route loader for projects, `useActionState` for search, `useSyncExternalStore` for theme).

## Assistant

**Warm sidecar — `inception/rag-service/serve.py`.** stdlib `ThreadingHTTPServer`, imports `rag_lib` + `answer` once, warms models in a background thread. Endpoints: `GET /health`, `GET /projects`, `POST /query`, `POST /answer`. Reuses `rag_lib.retrieve_chunks/project_targets` and `answer.pack_sources/build_context/build_messages`, but writes its **own** resilient LLM call (the stock `answer.call_chat_completions` does `sys.exit` on errors, which would crash the sidecar). Every handler traps `SystemExit` + `Exception` → JSON error with an HTTP status.

Exercised it live: `/projects` returns all 9 projects with counts; `/query` returns real ranked chunks; a bad project → 404 with the available list; `/answer` with no LLM → a clean 502. Warm timings confirmed: rerank-on ~1.5 s, **rerank-off ~0.03 s**.

## Assistant

**Dev launcher.** `scripts/_rag.mjs` resolves the rag-skill venv Python (`~/.cache/rag-skill/venv/bin/python`, else `python3`), the scripts dir, and the service URL. `scripts/dev.mjs` spawns the sidecar + Vite with colored `[rag]`/`[web]` prefixes and clean shutdown; `scripts/rag-service.mjs` runs the sidecar alone. Wired `package.json`: `dev` (both), `dev:web`, `dev:rag`.

**Server layer.** `src/types/rag.ts` — wire shapes (snake_case, mirroring the sidecar) + app types (camelCase) + a `SearchState` discriminated union + `assertNever`. `src/server/rag-service.ts` — `ragFetch` that retries connection failures for ~20 s (covers the sidecar's startup race) and surfaces backend errors. `src/server/rag.ts` — `listProjects`/`runQuery`/`runAnswer` server fns that map camel→snake and **return an outcome union** (`{ok:true,data} | {ok:false,error,status}`) so real backend error text always reaches the UI.

## Assistant

**Theme + design system.** Tailwind v4 with `@custom-variant dark` (class-based) and semantic tokens via `@theme inline`, so flipping the `:root`/`.dark` variables re-themes every utility at once. `src/lib/theme.ts` is a `useSyncExternalStore` store plus a no-FOUC `THEME_INIT_SCRIPT` inlined in `<head>`. Updated `__root.tsx` with the script + metadata.

**UI** (`src/components/`, all plain function components, ref-as-prop, zero manual memoization): `ui.tsx` primitives (Button, Segmented, Toggle, Badge, Spinner, Slider, inputs); `theme-toggle.tsx` (Sun/Monitor/Moon); `project-picker.tsx`; `params-panel.tsx` (source · top-k · rerank with a speed/quality hint); `llm-panel.tsx` (Local/Cloud, base URL, model, key, advanced — persisted to `localStorage`); `search-bar.tsx` (Retrieve/Answer modes, ⏎ to run); `chunk-card.tsx` (rank, score, path, badges, copy, expand); `answer-view.tsx` (answer with `[n]` citation pills + sources); `results.tsx` (switches on `SearchState` with loading/empty/error states); `app.tsx` (composition + `useActionState` search action). `index.tsx` loads projects in a route loader with an error boundary.

## Assistant

Verification pass. Fixed a few issues found by inspection (JSX file must be `.tsx`; clipboard guard; React `KeyboardEvent` type import). `tsgo` typecheck: clean. Ran `bun run dev` — both processes came up; the SSR loader fetched `/projects` and **all 9 projects rendered into the server HTML** (the loader → server-fn → sidecar path works end-to-end). Switched `.inputValidator()` → `.validator()` after a runtime deprecation warning (honoring "no outdated practices"). Production `bun run build`: clean (client + SSR, 1801 modules).

Playwright + Chromium were already installed, so I wrote a headless drive (select project → query → Retrieve → assert ranked cards; toggle dark/light; test the Answer error path) and ran it. The **first run caught a real bug**: the page wasn't hydrating, and the dev log was flooded with hydration `console.error`s. Root cause: the scaffold's **TanStack devtools Vite plugin** injects `data-tsd-source` attributes that differ between server and client on every element. That's boilerplate this GUI doesn't need, and shipping with hydration errors violates "modern best practices" — so I removed the devtools plugin + panel (and added `suppressHydrationWarning` to `<html>`, the standard theme-script pattern).

After restarting the stack, the hydration-aware drive went **all green** with 0 hydration / console / page errors: retrieval rendered 20 live cards (top hit `setting-up-rag/SKILL.md#7`), dark/light toggles work, and the Answer error path renders the real backend message (`Connection refused`) plus a guiding hint. Captured light/dark screenshots.

Finished with docs + hygiene: rewrote `inception/README.md` for the RAG GUI (architecture, run, env, layout) with a hero screenshot under `docs/_assets/`; ran Prettier (formatted), then oxlint (fixed a data-only result key, escaped an apostrophe, and applied the documented index-key escape-hatch for the static answer-fragment list). Final state: `tsgo` clean, oxlint clean, build clean.

Every requirement met: query-time params, project list, query, readable results, local/cloud answering, light + dark, Bun + TanStack Start, React Compiler (no manual memoization), no outdated practices. Noted that `inception` was previously a clean fixture for the `improving-context-retrieval-skills` harness and that the README now reflects its new purpose.

## User

After you're done, /export-transcript then integrate with /vcs.

## Assistant

Exported this transcript via the `export-transcript` skill (this file), then handed off to the `vcs` skill to integrate the work — review the diff in the `claude-inception-rag-gui` workspace and publish.
