import { useActionState, useState } from "react";
import type { ReactNode } from "react";
import { Boxes } from "lucide-react";

import type {
  Kind,
  LlmSettings,
  Project,
  SearchMode,
  SearchState,
} from "#/types/rag";
import { runAnswer, runQuery } from "#/server/rag";
import {
  DEFAULT_LLM,
  LLM_STORAGE_KEY,
  usePersistentState,
} from "#/lib/settings";
import { ThemeToggle } from "#/components/theme-toggle";
import { ProjectPicker } from "#/components/project-picker";
import { ParamsPanel } from "#/components/params-panel";
import { LlmPanel } from "#/components/llm-panel";
import { SearchBar } from "#/components/search-bar";
import { Results } from "#/components/results";

export function App({ projects }: { projects: Project[] }) {
  const [projectKey, setProjectKey] = useState(() => projects[0]?.key ?? "");
  const [kind, setKind] = useState<Kind>("all");
  const [topK, setTopK] = useState(20);
  const [rerank, setRerank] = useState(true);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("retrieve");
  const [llm, setLlm] = usePersistentState<LlmSettings>(
    LLM_STORAGE_KEY,
    DEFAULT_LLM,
  );

  const selected = projects.find((p) => p.key === projectKey) ?? projects[0];
  const hasModel = llm.model.trim().length > 0;
  const canSubmit =
    query.trim().length > 0 &&
    Boolean(selected) &&
    (mode === "retrieve" || hasModel);

  const [state, submit, pending] = useActionState<SearchState, void>(
    async (): Promise<SearchState> => {
      if (!selected)
        return { status: "error", message: "No project selected." };
      const base = {
        query: query.trim(),
        project: selected.key,
        kind,
        topK,
        rerank,
      };
      if (mode === "answer") {
        const outcome = await runAnswer({
          data: {
            ...base,
            baseUrl: llm.baseUrl,
            model: llm.model.trim(),
            apiKey: llm.apiKey,
            temperature: llm.temperature,
            maxTokens: llm.maxTokens,
            maxContextChars: llm.maxContextChars,
            systemPrompt: llm.systemPrompt,
          },
        });
        return outcome.ok
          ? { status: "answered", data: outcome.data }
          : { status: "error", message: outcome.error };
      }
      const outcome = await runQuery({ data: base });
      return outcome.ok
        ? { status: "retrieved", data: outcome.data }
        : { status: "error", message: outcome.error };
    },
    { status: "idle" },
  );

  const hint =
    mode === "answer" && !hasModel
      ? "Set a model in Answer settings →"
      : "↵ to run · ⇧↵ for newline";

  return (
    <div className="flex min-h-dvh flex-col">
      <Header projectCount={projects.length} />

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-16 pt-6">
        <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
          <aside className="flex flex-col gap-5 lg:sticky lg:top-[4.75rem] lg:max-h-[calc(100dvh-6rem)] lg:overflow-y-auto lg:pr-1">
            <Panel title="Projects" trailing={`${projects.length}`}>
              <ProjectPicker
                projects={projects}
                selected={projectKey}
                onSelect={setProjectKey}
              />
            </Panel>
            <Panel title="Retrieval">
              <ParamsPanel
                kind={kind}
                onKind={setKind}
                topK={topK}
                onTopK={setTopK}
                rerank={rerank}
                onRerank={setRerank}
              />
            </Panel>
            <Panel title="Answer">
              <LlmPanel settings={llm} onChange={setLlm} />
            </Panel>
          </aside>

          <section className="flex min-w-0 flex-col gap-4">
            <SearchBar
              query={query}
              onQuery={setQuery}
              mode={mode}
              onMode={setMode}
              onSubmit={submit}
              pending={pending}
              canSubmit={canSubmit}
              hint={hint}
            />
            <Results
              state={state}
              pending={pending}
              mode={mode}
              projectName={selected?.name ?? "this project"}
            />
          </section>
        </div>
      </main>
    </div>
  );
}

function Header({ projectCount }: { projectCount: number }) {
  return (
    <header className="sticky top-0 z-20 border-b border-edge bg-base/80 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl items-center gap-3 px-4 py-3">
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent text-accent-fg">
          <Boxes className="h-5 w-5" />
        </span>
        <div className="flex items-baseline gap-2">
          <span className="text-base font-semibold tracking-tight text-fg">
            inception
          </span>
          <span className="hidden text-xs text-faint sm:inline">
            local RAG · {projectCount} projects
          </span>
        </div>
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

function Panel({
  title,
  trailing,
  children,
}: {
  title: string;
  trailing?: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-edge bg-panel p-3.5">
      <div className="mb-3 flex items-center justify-between px-0.5">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
          {title}
        </h2>
        {trailing ? (
          <span className="font-mono text-xs text-faint">{trailing}</span>
        ) : null}
      </div>
      {children}
    </div>
  );
}
