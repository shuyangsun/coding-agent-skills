# inception

A clean-state [TanStack Start](https://tanstack.com/start) application — named for the
recursive, self-improving philosophy of this skill repository. It exists as a realistic
target codebase for the `improving-docs-and-rag-skills` harness.

## Stack

- **TanStack Start** + **TanStack Router** (file-based routing) on **Vite 8**
- **React 19** with the **React Compiler** enabled (automatic memoization — no manual
  `useMemo` / `useCallback`)
- **Bun** as the runtime and package manager
- **TypeScript 7** (the native Go compiler, `tsgo`, via `@typescript/native-preview`)
- **Tailwind CSS** for styling

Formatting (Prettier) and linting (oxlint) are configured at the repository root, not
inside this project.

## Develop

```bash
bun install        # from the repo root
bun run dev        # start the dev server on http://localhost:3000
```

## Other commands

```bash
bun run build      # production build
bun run preview    # preview the production build
bun run typecheck  # type-check with tsgo (TypeScript 7)
bun run test       # run tests with Vitest
```

## Routing

Routes live in `src/routes`. Add a file there and TanStack Router regenerates
`src/routeTree.gen.ts` automatically (that file is generated — do not edit it by hand).
