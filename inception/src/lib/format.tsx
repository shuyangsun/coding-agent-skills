/* eslint-disable react/no-array-index-key -- answer text is split into positional
   fragments; the list is static and never reorders, so the fragment index is a
   stable key (see §5 of the React coding-style rules). */
import type { ReactNode } from "react";

/** Join class names, dropping falsy values. */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

export function formatScore(score: number): string {
  return score.toFixed(3);
}

export function formatMs(ms: number): string {
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`;
}

export function formatCount(n: number): string {
  return n.toLocaleString("en-US");
}

/** Split a "path/to/file.md" into directory + basename for two-tone display. */
export function splitPath(path: string): { dir: string; base: string } {
  const idx = path.lastIndexOf("/");
  return idx === -1
    ? { dir: "", base: path }
    : { dir: path.slice(0, idx + 1), base: path.slice(idx + 1) };
}

/**
 * Render answer text into React nodes: `[1]` citations become anchor pills
 * (linking to the matching source card) and `` `code` `` becomes inline code.
 * Whitespace is preserved by the caller via `whitespace-pre-wrap`. No HTML is
 * injected — every node is constructed, so this is XSS-safe by construction.
 */
export function renderAnswer(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  // Alternating split on inline-code spans, then citations within plain text.
  const codeParts = text.split(/(`[^`\n]+`)/g);
  codeParts.forEach((part, i) => {
    if (part.startsWith("`") && part.endsWith("`") && part.length > 1) {
      nodes.push(
        <code
          key={`code-${i}`}
          className="rounded bg-code px-1.5 py-0.5 font-mono text-[0.85em] text-fg"
        >
          {part.slice(1, -1)}
        </code>,
      );
      return;
    }
    part.split(/(\[\d+\])/g).forEach((piece, j) => {
      const match = /^\[(\d+)\]$/.exec(piece);
      if (match) {
        const id = Number(match[1]);
        nodes.push(
          <a
            key={`cite-${i}-${j}`}
            href={`#src-${id}`}
            className="mx-0.5 inline-flex items-center rounded bg-accent-soft px-1.5 align-baseline font-mono text-[0.78em] font-medium text-accent no-underline hover:brightness-95"
          >
            {id}
          </a>,
        );
      } else if (piece) {
        nodes.push(<span key={`txt-${i}-${j}`}>{piece}</span>);
      }
    });
  });
  return nodes;
}
