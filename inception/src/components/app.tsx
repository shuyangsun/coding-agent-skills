import { useRef, useState } from "react";
import type { ReactNode } from "react";
import { Boxes } from "lucide-react";

import type {
  Kind,
  LlmSettings,
  Project,
  SearchMode,
  SearchPhase,
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

  const [state, setState] = useState<SearchState>({ status: "idle" });
  const [phase, setPhase] = useState<SearchPhase>("idle");

  const selected = projects.find((p) => p.key === projectKey) ?? projects[0];
  const hasModel = llm.model.trim().length > 0;
  const pending = phase !== "idle";
  const canSubmit =
    !pending &&
    query.trim().length > 0 &&
    Boolean(selected) &&
    (mode === "retrieve" || hasModel);

  // A plain async handler (no useActionState/transition): transitions briefly
  // re-render the route subtree and blank the page during the request. This
  // also lets us surface the two stages — `querying` then `answering` — and
  // show the retrieved chunks while the model is still generating.
  const inFlight = useRef(false);
  async function submit() {
    if (inFlight.current) return;
    if (!selected) {
      setState({ status: "error", message: "No project selected." });
      return;
    }
    const base = {
      query: query.trim(),
      project: selected.key,
      kind,
      topK,
      rerank,
    };
    inFlight.current = true;
    try {
      setPhase("querying");
      const retrieval = await runQuery({ data: base });
      if (!retrieval.ok) {
        setState({ status: "error", message: retrieval.error });
        return;
      }
      if (mode === "retrieve") {
        setState({ status: "retrieved", data: retrieval.data });
        return;
      }

      // Answer mode: show the retrieved chunks, then generate the answer.
      setState({ status: "retrieved", data: retrieval.data });
      setPhase("answering");
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
      setState(
        outcome.ok
          ? { status: "answered", data: outcome.data }
          : { status: "error", message: outcome.error },
      );
    } catch (error) {
      setState({
        status: "error",
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setPhase("idle");
      inFlight.current = false;
    }
  }

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
              phase={phase}
              canSubmit={canSubmit}
              hint={hint}
            />
            <Results
              state={state}
              phase={phase}
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
