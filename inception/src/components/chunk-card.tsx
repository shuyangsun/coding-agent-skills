import { useState } from "react";
import { Check, Copy } from "lucide-react";

import { cn, formatScore, splitPath } from "#/lib/format";
import { Badge } from "#/components/ui";

type Props = {
  index: number;
  score: number;
  project: string | null;
  kind: string | null;
  docId: string | null;
  chunkIdx: number | null;
  text: string;
  anchorId?: string;
};

const LONG_TEXT = 420;

export function ResultCard({
  index,
  score,
  project,
  kind,
  docId,
  chunkIdx,
  text,
  anchorId,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const isCode = kind === "code";
  const isLong = text.length > LONG_TEXT;
  const path = docId ?? "(unknown)";
  const { dir, base } = splitPath(path);
  const ref = chunkIdx === null ? path : `${path}#${chunkIdx}`;

  function copyRef() {
    const clipboard = navigator.clipboard;
    if (!clipboard) return;
    void clipboard.writeText(ref).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    });
  }

  return (
    <article
      id={anchorId}
      className="animate-rise scroll-mt-24 rounded-xl border border-edge bg-surface transition hover:border-edge-strong"
    >
      <header className="flex items-center gap-2 border-b border-edge px-3 py-2">
        <span className="grid h-6 min-w-6 place-items-center rounded-md bg-accent-soft px-1.5 font-mono text-xs font-semibold text-accent">
          {index}
        </span>
        <div className="min-w-0 flex-1 truncate font-mono text-xs">
          <span className="text-faint">{dir}</span>
          <span className="text-fg">{base}</span>
          {chunkIdx !== null ? (
            <span className="text-faint">#{chunkIdx}</span>
          ) : null}
        </div>
        {kind ? <Badge tone={isCode ? "code" : "md"}>{kind}</Badge> : null}
        {project ? <Badge>{project}</Badge> : null}
        <Badge tone="neutral" className="tabular-nums">
          {formatScore(score)}
        </Badge>
        <button
          type="button"
          onClick={copyRef}
          title="Copy path"
          aria-label="Copy path"
          className="grid h-6 w-6 place-items-center rounded-md text-faint transition hover:bg-base hover:text-fg"
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-ok" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </button>
      </header>

      <div className="px-3 py-2.5">
        <pre
          className={cn(
            "whitespace-pre-wrap break-words font-sans text-[0.82rem] leading-relaxed text-fg/90",
            isCode && "font-mono text-xs",
            !expanded && isLong && "line-clamp-[10]",
          )}
        >
          {text}
        </pre>
        {isLong ? (
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="mt-1.5 text-xs font-medium text-accent transition hover:brightness-110"
          >
            {expanded ? "Show less" : "Show more"}
          </button>
        ) : null}
      </div>
    </article>
  );
}
