import type { KeyboardEvent } from "react";
import { Search, Sparkles } from "lucide-react";

import type { SearchMode, SearchPhase } from "#/types/rag";
import { Button, Segmented, Spinner, TextArea } from "#/components/ui";

type Props = {
  query: string;
  onQuery: (query: string) => void;
  mode: SearchMode;
  onMode: (mode: SearchMode) => void;
  onSubmit: () => void;
  phase: SearchPhase;
  canSubmit: boolean;
  hint: string;
};

export function SearchBar({
  query,
  onQuery,
  mode,
  onMode,
  onSubmit,
  phase,
  canSubmit,
  hint,
}: Props) {
  const pending = phase !== "idle";
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      if (canSubmit) onSubmit();
    }
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (canSubmit) onSubmit();
      }}
      className="rounded-2xl border border-edge bg-surface p-2 shadow-sm focus-within:border-edge-strong"
    >
      <TextArea
        value={query}
        onChange={(event) => onQuery(event.target.value)}
        onKeyDown={handleKeyDown}
        rows={2}
        placeholder="Ask a question about this project…"
        aria-label="Query"
        className="border-0 bg-transparent px-2 py-1.5 text-base focus-visible:ring-0"
      />
      <div className="flex items-center justify-between gap-3 px-1 pt-1">
        <div className="flex items-center gap-3">
          <Segmented<SearchMode>
            ariaLabel="Search mode"
            size="sm"
            value={mode}
            onChange={onMode}
            options={[
              {
                value: "retrieve",
                title: "Return the matching chunks",
                label: (
                  <span className="flex items-center gap-1.5">
                    <Search className="h-3.5 w-3.5" />
                    Retrieve
                  </span>
                ),
              },
              {
                value: "answer",
                title: "Generate a grounded answer with an LLM",
                label: (
                  <span className="flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5" />
                    Answer
                  </span>
                ),
              },
            ]}
          />
          <span className="hidden text-xs text-faint sm:inline">{hint}</span>
        </div>
        <Button
          type="submit"
          variant="primary"
          disabled={!canSubmit || pending}
        >
          {pending ? (
            <>
              <Spinner className="h-4 w-4" />
              {phase === "answering" ? "Generating…" : "Querying…"}
            </>
          ) : mode === "answer" ? (
            "Answer"
          ) : (
            "Retrieve"
          )}
        </Button>
      </div>
    </form>
  );
}
