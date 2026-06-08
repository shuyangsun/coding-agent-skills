#!/usr/bin/env python3
"""mk-corpus.py — build the corpus axis: Z (empty baseline), N (naive), D (docs-skill).

Three corpus variants from the same fact payload:
  - **Z** (zero / empty): no documents at all — the absolute zero baseline before
    any docs or RAG. Every retrieval metric scores 0. Run this *first* so every
    other cell is measured as a lift above zero.
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

It also snapshots a **code** corpus from the `inception/` app (content-type axis,
`domain="code"`), so retrieval over CODE is measured on the same eval path as the
natural-language docs and the two can be compared. Skipped if `inception/` is absent.

This is a deterministic Phase-0 stand-in so the full factorial can be measured
*before* the real `docs` skill exists. Once `docs`/`rag` exist, `new-corpus.sh`
will author D with the actual skill and synthesize N from the same fact payload.

Usage:
  mk-corpus.py --out DIR [--corpus SRC] [--code-corpus inception/] [--naive-files 6]
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
    ap.add_argument("--code-corpus", help="inception/ root for the code domain (default: auto-locate)")
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

    # Z: empty corpus — no documents at all (the absolute zero baseline).
    z_root = out / "Z"
    z_root.mkdir(parents=True, exist_ok=True)

    # code: snapshot the inception/ codebase verbatim (content-type axis,
    # domain="code"), so code retrieval is measured on the same eval path as the
    # natural-language docs. Skipped if inception/ is absent.
    code_src = gold.find_code_corpus_root(args.code_corpus)
    n_code = 0
    code_root = out / "code"
    if code_src is not None:
        code_docs = gold.load_corpus(code_src, kind="code")
        for rel, text in code_docs.items():
            p = code_root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        n_code = len(code_docs)

    print(f"mk-corpus: Z=0 docs (empty baseline) -> {z_root}")
    print(f"mk-corpus: N={n_count} naive files ({args.mode}) -> {n_root}")
    print(f"mk-corpus: D={len(docs)} structured docs -> {d_root}")
    if code_src is not None:
        print(f"mk-corpus: code={n_code} files (inception/) -> {code_root}")
    else:
        print("mk-corpus: code=skipped (inception/ not found)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
