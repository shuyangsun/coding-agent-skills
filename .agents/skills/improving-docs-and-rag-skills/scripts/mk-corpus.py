#!/usr/bin/env python3
"""mk-corpus.py — build the factorial's corpus axis (N=naive, D=docs-skill).

The 2×2 factorial needs the SAME fact payload authored two ways:
  - **D** (docs-skill): well-structured docs — clean Markdown headings, one
    concept per file, descriptive filenames, front-matter. Stands in for
    `docs`-skill output.
  - **N** (naive dump): the identical text content with structure destroyed —
    front-matter dropped and heading markers demoted to plain lines, under opaque
    filenames (`n-0001.md`). Same count of docs and same sentinels as D, so the
    only thing that varies is **structure** (heading-aware chunking and the
    filename/front-matter signal). With `--mode flat` the docs are instead
    concatenated into a few big opaque files (a cruder dump); `perdoc` (default)
    keeps doc granularity comparable to D so doc-level recall is not saturated.

Because the *content* (and therefore every sentinel) is preserved byte-for-byte
except for heading markers and file packing, `gold.py --qrels-mode sentinel`
derives correct per-corpus labels for both, and any retrieval difference is
attributable to **structure**, not to different facts — the docs-axis signal.

This is a deterministic Phase-0 stand-in so the full factorial can be measured
*before* the real `docs` skill exists. Once `docs`/`rag` exist, `new-corpus.sh`
will author D with the actual skill and synthesize N from the same fact payload.

Usage:
  mk-corpus.py --out DIR [--corpus SRC] [--naive-files 6]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gold  # noqa: E402

_HEADING = re.compile(r"^#{1,6}[ \t]+", re.MULTILINE)
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def naive_text(text: str) -> str:
    """Destroy structure but preserve content/sentinels: drop front-matter and
    demote heading markers to plain lines."""
    text = _FRONTMATTER.sub("", text)
    text = _HEADING.sub("", text)
    return text.strip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--corpus")
    ap.add_argument("--mode", choices=["perdoc", "flat"], default="perdoc")
    ap.add_argument("--naive-files", type=int, default=6, help="only used with --mode flat")
    args = ap.parse_args(argv)

    src = gold.find_corpus_root(args.corpus)
    docs = gold.load_corpus(src)  # excludes self-reference/meta docs already
    out = Path(args.out).expanduser().resolve()

    # D: structured — preserve relative paths and content verbatim.
    d_root = out / "D"
    for rel, text in docs.items():
        p = d_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    # N: naive — de-structured content under opaque filenames.
    n_root = out / "N"
    n_root.mkdir(parents=True, exist_ok=True)
    items = sorted(docs.items())
    if args.mode == "perdoc":
        for i, (_, text) in enumerate(items):
            (n_root / f"n-{i + 1:04d}.md").write_text(naive_text(text), encoding="utf-8")
        n_count = len(items)
    else:
        buckets: list[list[str]] = [[] for _ in range(max(1, args.naive_files))]
        for i, (_, text) in enumerate(items):
            buckets[i % len(buckets)].append(naive_text(text))
        for i, chunks in enumerate(buckets):
            if chunks:
                (n_root / f"notes-{i + 1:02d}.md").write_text("\n\n".join(chunks), encoding="utf-8")
        n_count = sum(1 for b in buckets if b)

    print(f"mk-corpus: D={len(docs)} structured docs -> {d_root}")
    print(f"mk-corpus: N={n_count} naive files ({args.mode}) -> {n_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
