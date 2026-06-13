import { Zap } from "lucide-react";

import type { Kind } from "#/types/rag";
import { Field, Segmented, Slider, Toggle } from "#/components/ui";

type Props = {
  kind: Kind;
  onKind: (kind: Kind) => void;
  topK: number;
  onTopK: (topK: number) => void;
  rerank: boolean;
  onRerank: (rerank: boolean) => void;
};

const KIND_OPTIONS: Array<{ value: Kind; label: string; title: string }> = [
  { value: "all", label: "All", title: "Docs and code" },
  { value: "md", label: "Docs", title: "Markdown / prose only" },
  { value: "code", label: "Code", title: "Source code only" },
];

export function ParamsPanel({
  kind,
  onKind,
  topK,
  onTopK,
  rerank,
  onRerank,
}: Props) {
  return (
    <div className="flex flex-col gap-4">
      <Field label="Source">
        <Segmented<Kind>
          ariaLabel="Document kind"
          className="w-full"
          value={kind}
          onChange={onKind}
          options={KIND_OPTIONS.map((option) => ({
            ...option,
            label: <span className="flex-1">{option.label}</span>,
          }))}
        />
      </Field>

      <Field label="Results" htmlFor="topk" hint={`${topK}`}>
        <Slider id="topk" min={1} max={50} value={topK} onChange={onTopK} />
      </Field>

      <div className="flex items-start justify-between gap-3 rounded-lg border border-edge bg-base/60 px-3 py-2.5">
        <div className="flex flex-col gap-0.5">
          <span className="flex items-center gap-1.5 text-sm font-medium text-fg">
            <Zap className="h-3.5 w-3.5 text-accent" />
            Rerank
          </span>
          <span className="text-xs text-muted">
            {rerank
              ? "Cross-encoder reorder · higher quality, ~1.5 s"
              : "Hybrid fusion only · instant"}
          </span>
        </div>
        <Toggle checked={rerank} onChange={onRerank} label="Rerank results" />
      </div>
    </div>
  );
}
