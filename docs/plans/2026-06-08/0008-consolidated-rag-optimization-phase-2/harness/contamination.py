#!/usr/bin/env python3
"""contamination.py — self-reference / leakage controls for the Phase-3 benchmark.

Pre-work for ``0008-consolidated-rag-optimization-phase-2.md`` §"Contamination and
Self-Reference Controls". Two layers:

  HARD exclusion (already wired, NOT here): the eval set + the consolidated plan are
  dropped from the corpus by corpus_manifest.exclude_globs and gold.py EXCLUDE_GLOBS.
  Those files quote every answer and are never a legitimate primary (verified).

  PER-QUERY contamination check (here): agent plans, research notes, and benchmark
  reports CAN be legitimate primaries for some coding-agent-skills questions (12 of
  them cite docs/{benchmarks,plans,research,prompts}), so they must NOT be globally
  excluded. Instead, for each query, flag any retrieved synthesis doc that is NOT in
  that query's `primary` list — report it separately (default) or drop it for that
  query. This catches a retriever "answering" via a doc that merely restates a fact.

Plus deterministic CONTROL-RUN generators (closed-book, wrong-context) for the
Wave-0 leakage controls. Report-only by default; nothing is dropped unless asked.
Stdlib-only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpus_manifest as M  # noqa: E402
import gold_loader as G  # noqa: E402

# Docs prone to RESTATING facts from other files (synthesis/secondary sources).
# A retrieved synthesis doc that is not the query's own primary is a contamination
# hit. Conservative on purpose (report-only). Repo-root-relative, '*' spans '/'.
SYNTHESIS_GLOBS: tuple[str, ...] = (
    "docs/plans/*",
    "docs/research/*",
    "docs/benchmarks/*",
)


def is_synthesis(path: str, globs: tuple[str, ...] = SYNTHESIS_GLOBS) -> bool:
    import fnmatch

    return any(fnmatch.fnmatch(path, g) for g in globs)


def check_query(retrieved: list[str], primary: tuple[str, ...] | list[str],
                globs: tuple[str, ...] = SYNTHESIS_GLOBS) -> list[str]:
    """Synthesis docs in `retrieved` that are not this query's primary (flagged)."""
    pset = set(primary)
    return [d for d in retrieved if is_synthesis(d, globs) and d not in pset]


def filtered(retrieved: list[str], primary, globs=SYNTHESIS_GLOBS) -> list[str]:
    """`retrieved` with contamination hits removed (the 'exclude for this query' option)."""
    flagged = set(check_query(retrieved, primary, globs))
    return [d for d in retrieved if d not in flagged]


def contamination_report(run: dict[str, list[str]], questions: list[G.Question]) -> dict:
    """Per-query + aggregate contamination over a retrieval run ({qid: [doc_id,...]})."""
    qby = {q.id: q for q in questions}
    per_query = {}
    n_hit = 0
    for qid, ranked in run.items():
        q = qby.get(qid)
        if q is None:
            continue
        flags = check_query(ranked, q.primary)
        if flags:
            n_hit += 1
            per_query[qid] = flags
    return {
        "n_queries": len(run),
        "n_queries_with_contamination": n_hit,
        "contamination_rate": n_hit / len(run) if run else 0.0,
        "per_query": per_query,
    }


# --- deterministic control-run generators (Wave-0 leakage controls) ---------
def closed_book_run(questions: list[G.Question]) -> dict[str, list[str]]:
    """No retrieval: every query gets an empty context. Drives the closed-book
    control — any answer correctness here is parametric leakage, not retrieval."""
    return {q.id: [] for q in questions}


def wrong_context_run(real_run: dict[str, list[str]]) -> dict[str, list[str]]:
    """Distractor control: each query keeps a ranked list, but it is ANOTHER query's
    (deterministic rotation by sorted id). High scores here mean the metric is not
    actually retrieval-dependent. No RNG (resume-safe, reproducible)."""
    ids = sorted(real_run)
    if len(ids) < 2:
        return {k: list(v) for k, v in real_run.items()}
    rotated = {}
    for i, qid in enumerate(ids):
        donor = ids[(i + 1) % len(ids)]
        rotated[qid] = list(real_run[donor])
    return rotated


def cmd_surface(args) -> int:
    """Report the contamination surface from the gold set + corpora (no run needed):
    how many synthesis docs each repo corpus holds, and which questions legitimately
    cite one (the per-query check must spare these)."""
    qs = G.load_questions()
    by_repo: dict[str, list[G.Question]] = {}
    for q in qs:
        by_repo.setdefault(q.repo, []).append(q)
    print("repo                    synthesis-docs-in-corpus  questions-with-synthesis-primary")
    for repo_name, repo in M.REPOS.items():
        corpus = M.load_repo_corpus(repo)
        n_synth = sum(1 for d in corpus if is_synthesis(d))
        legit = [q.id for q in by_repo.get(repo_name, []) if any(is_synthesis(p) for p in q.primary)]
        print(f"  {repo_name:22s} {n_synth:6d}                    {len(legit)}")
        for qid in legit:
            q = next(x for x in by_repo[repo_name] if x.id == qid)
            synth_primaries = [p for p in q.primary if is_synthesis(p)]
            print(f"        legit: {qid}  -> {synth_primaries}")
    print("\nNote: hard-excluded eval set + consolidated plan are already absent from every "
          "corpus (corpus_manifest.exclude_globs). The per-query check spares the 'legit' "
          "primaries above and flags only retrieved-but-not-primary synthesis docs.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("surface", help="report contamination surface from gold + corpora").set_defaults(func=cmd_surface)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
