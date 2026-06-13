import { AlertTriangle, FileText, Loader2, Sparkles } from "lucide-react";

import type { SearchPhase, SearchState } from "#/types/rag";
import { assertNever } from "#/types/rag";
import { formatMs } from "#/lib/format";
import { ResultCard } from "#/components/chunk-card";
import { AnswerView } from "#/components/answer-view";

type Props = {
  state: SearchState;
  phase: SearchPhase;
  projectName: string;
};

export function Results({ state, phase, projectName }: Props) {
  // Nothing to show yet: a full loading panel for the first request.
  if (phase !== "idle" && state.status === "idle") {
    return <LoadingPanel phase={phase} />;
  }

  return (
    <div className="flex flex-col gap-3">
      {phase !== "idle" ? <PendingBar phase={phase} /> : null}
      <StateView state={state} projectName={projectName} />
    </div>
  );
}

function StateView({
  state,
  projectName,
}: {
  state: SearchState;
  projectName: string;
}) {
  switch (state.status) {
    case "idle":
      return <EmptyState projectName={projectName} />;
    case "error":
      return <ErrorPanel message={state.message} />;
    case "retrieved":
      return (
        <>
          <MetaRow
            where={state.data.where}
            target={state.data.target}
            count={state.data.results.length}
            ms={state.data.ms}
          />
          {state.data.results.length === 0 ? (
            <EmptyHits />
          ) : (
            <div className="flex flex-col gap-2">
              {state.data.results.map((hit, index) => (
                <ResultCard
                  key={`${hit.collection}:${hit.doc_id}:${hit.chunk_idx}`}
                  index={index + 1}
                  score={hit.score}
                  project={hit.project}
                  kind={hit.kind}
                  docId={hit.doc_id}
                  chunkIdx={hit.chunk_idx}
                  text={hit.text}
                />
              ))}
            </div>
          )}
        </>
      );
    case "answered":
      return (
        <>
          <MetaRow
            where={state.data.where}
            target={state.data.target}
            count={state.data.sources.length}
            ms={state.data.ms}
            countLabel="sources"
          />
          <AnswerView data={state.data} />
        </>
      );
    default:
      return assertNever(state);
  }
}

function MetaRow({
  where,
  target,
  count,
  ms,
  countLabel = "results",
}: {
  where: string;
  target: string;
  count: number;
  ms: number;
  countLabel?: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-1 font-mono text-xs text-faint">
      <span className="text-muted">
        {count} {countLabel}
      </span>
      <span>· {formatMs(ms)}</span>
      <span className="truncate">· {target}</span>
      <span className="ml-auto truncate">{where}</span>
    </div>
  );
}

function EmptyState({ projectName }: { projectName: string }) {
  return (
    <div className="grid place-items-center rounded-2xl border border-dashed border-edge px-6 py-16 text-center">
      <FileText className="mb-3 h-8 w-8 text-faint" />
      <p className="text-sm font-medium text-fg">
        Search <span className="text-accent">{projectName}</span>
      </p>
      <p className="mt-1 max-w-sm text-sm text-muted">
        <span className="font-medium">Retrieve</span> ranks the matching chunks.{" "}
        <span className="font-medium">Answer</span> sends them to an LLM for a
        grounded, cited response.
      </p>
    </div>
  );
}

function EmptyHits() {
  return (
    <div className="rounded-xl border border-dashed border-edge px-4 py-10 text-center text-sm text-muted">
      No matching chunks. Try a different query, source, or a higher result
      count.
    </div>
  );
}

function ErrorPanel({ message }: { message: string }) {
  return (
    <div className="animate-rise rounded-xl border border-danger/40 bg-danger-soft px-4 py-3">
      <div className="flex items-center gap-2 text-sm font-semibold text-danger">
        <AlertTriangle className="h-4 w-4" />
        Request failed
      </div>
      <p className="mt-1 break-words font-mono text-xs text-fg/80">{message}</p>
      <p className="mt-2 text-xs text-muted">{hintFor(message)}</p>
    </div>
  );
}

function hintFor(message: string): string {
  if (message.includes("RAG sidecar")) {
    return "The retrieval service isn't running. Start everything with `bun run dev`.";
  }
  if (message.includes("provider") || /HTTP 50\d/.test(message)) {
    return "The LLM endpoint is unreachable. Check the Base URL, model, and key in the Answer settings — or use Retrieve, which needs no LLM.";
  }
  return "Adjust your query or parameters and try again.";
}

function LoadingPanel({ phase }: { phase: SearchPhase }) {
  const answering = phase === "answering";
  return (
    <div className="grid place-items-center rounded-2xl border border-edge bg-surface px-6 py-16 text-center">
      <Loader2 className="mb-3 h-7 w-7 animate-spin text-accent" />
      <p className="text-sm font-medium text-fg">
        {answering ? "Generating answer…" : "Querying…"}
      </p>
      <p className="mt-1 text-xs text-muted">
        {answering
          ? "Calling the model with the retrieved context."
          : "Embedding the query and ranking matches."}
      </p>
    </div>
  );
}

function PendingBar({ phase }: { phase: SearchPhase }) {
  const answering = phase === "answering";
  return (
    <div className="flex items-center gap-2 rounded-lg border border-edge bg-surface px-3 py-2 text-xs text-muted">
      {answering ? (
        <Sparkles className="h-3.5 w-3.5 animate-pulse text-accent" />
      ) : (
        <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />
      )}
      {answering ? "Generating answer…" : "Querying…"}
    </div>
  );
}
