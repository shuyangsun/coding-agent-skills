import { Sparkles } from "lucide-react";

import type { AnswerResult } from "#/types/rag";
import { formatMs, renderAnswer } from "#/lib/format";
import { Badge } from "#/components/ui";
import { ResultCard } from "#/components/chunk-card";

export function AnswerView({ data }: { data: AnswerResult }) {
  const total = data.usage?.total_tokens;

  return (
    <div className="flex flex-col gap-4">
      <section className="animate-rise rounded-2xl border border-accent/30 bg-accent-soft/40 p-4">
        <header className="mb-3 flex flex-wrap items-center gap-2">
          <span className="flex items-center gap-1.5 text-sm font-semibold text-fg">
            <Sparkles className="h-4 w-4 text-accent" />
            Answer
          </span>
          <Badge tone="accent">{data.model}</Badge>
          <span className="ml-auto flex items-center gap-2 text-xs text-muted">
            <span>{formatMs(data.ms)}</span>
            {typeof total === "number" ? <span>· {total} tokens</span> : null}
          </span>
        </header>
        <div className="whitespace-pre-wrap break-words text-[0.92rem] leading-relaxed text-fg">
          {renderAnswer(data.answer)}
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="px-1 text-xs font-semibold uppercase tracking-wide text-muted">
          Sources · {data.sources.length}
        </h3>
        <div className="flex flex-col gap-2">
          {data.sources.map((source) => (
            <ResultCard
              key={source.source_id}
              anchorId={`src-${source.source_id}`}
              index={source.source_id}
              score={source.score}
              project={source.project}
              kind={source.kind}
              docId={source.doc_id}
              chunkIdx={source.chunk_idx}
              text={source.text}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
