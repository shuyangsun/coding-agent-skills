import { Database } from "lucide-react";

import type { Project } from "#/types/rag";
import { cn, formatCount } from "#/lib/format";
import { Badge } from "#/components/ui";

type Props = {
  projects: Project[];
  selected: string;
  onSelect: (key: string) => void;
};

export function ProjectPicker({ projects, selected, onSelect }: Props) {
  if (projects.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-edge px-3 py-6 text-center text-sm text-muted">
        No indexed projects found. Run the indexer first.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-1">
      {projects.map((project) => {
        const active = project.key === selected;
        return (
          <li key={project.key}>
            <button
              type="button"
              aria-pressed={active}
              onClick={() => onSelect(project.key)}
              className={cn(
                "group w-full rounded-lg border px-3 py-2.5 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/45",
                active
                  ? "border-accent/40 bg-accent-soft"
                  : "border-transparent hover:border-edge hover:bg-base",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span
                  className={cn(
                    "truncate text-sm font-medium",
                    active ? "text-accent" : "text-fg",
                  )}
                >
                  {project.name}
                </span>
                <span className="flex items-center gap-1 text-[0.7rem] text-faint">
                  <Database className="h-3 w-3" />
                  {formatCount(project.total_chunks)}
                </span>
              </div>
              <div className="mt-1 truncate font-mono text-[0.7rem] text-faint">
                {project.root}
              </div>
              <div className="mt-1.5 flex flex-wrap gap-1">
                {project.collections.map((collection) => (
                  <Badge
                    key={collection.kind}
                    tone={active ? "accent" : "neutral"}
                  >
                    {collection.kind} · {formatCount(collection.chunk_count)}
                  </Badge>
                ))}
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
