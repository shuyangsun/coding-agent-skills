#!/usr/bin/env python3
"""gold_loader.py — load the 207-query Phase-1 gold set into the Phase-3 harness.

Pre-work for ``0008-consolidated-rag-optimization-phase-2.md`` §"Harness and
Gold-Set Wiring" (items 1, 3, 4) and §"Contamination and Self-Reference Controls".

Loads ``docs/plans/2026-06-08/0003-rag-eval-set-phase-1/eval-set.json`` preserving
every field (id, repo, domain, category, question, answer, sentinels, primary,
difficulty, evidence, source) and adds the deterministic dev/held-out split. It
builds the graded qrels, assembles ONE combined per-repo corpus via the manifest
(code AND docs together — `domain` is a reporting slice, not a corpus partition),
and validates that every gold primary is actually reachable by the corpus loader —
the check that surfaced the C++/CUDA extension gap.

Deterministic IR scoring itself reuses the harness's existing
``improving-context-retrieval-skills/scripts/gold.py`` (``score_query``,
``aggregate``) so there is ONE scorer; this module only loads/labels/validates.
Stdlib-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpus_manifest as M  # noqa: E402

# eval-set.json lives beside the 0008 plan dir: …/2026-06-08/0003-…/eval-set.json.
# This file is …/2026-06-08/0008-…/harness/gold_loader.py, so the date dir is two
# parents up. Resolved relative to this harness so it is checkout-portable.
_HARNESS_DIR = Path(__file__).resolve().parent
EVAL_SET_PATH = (
    _HARNESS_DIR.parent.parent / "0003-rag-eval-set-phase-1" / "eval-set.json"
)

GOLD_SET_VERSION = "rag-eval-phase1-v1"

# The IR task is a SINGLE combined per-repo corpus: code AND docs are indexed and
# retrieved together, because a question is often best answered by both (code
# references docs; docs reference code). `domain` (code|nl) is a REPORTING SLICE
# only — it never partitions the corpus or filters retrieval. Metrics are reported
# total and sliced by domain/category/repo; the retriever stays blind to file type.
CORPUS_KINDS: tuple[str, ...] = ("md", "code")


@dataclass(frozen=True)
class Question:
    id: str
    repo: str
    domain: str  # code | nl
    category: str  # codebase | design-doc | session-prompting
    question: str
    answer: str
    sentinels: tuple[str, ...]
    primary: tuple[str, ...]
    difficulty: str  # easy | medium | hard
    evidence: str
    source: str  # claude | codex
    repo_root: str = ""

    @property
    def split(self) -> str:
        return split_of(self.id)

    @property
    def multiplicity(self) -> str:
        return "multi-primary" if len(self.primary) > 1 else "single-primary"


def split_of(query_id: str) -> str:
    """Stable dev/held-out partition by hash parity — identical algorithm to
    improving-context-retrieval-skills/scripts/gold.py so the convention matches."""
    h = int(hashlib.sha256(query_id.encode()).hexdigest(), 16)
    return "held-out" if h % 2 else "dev"


def load_questions(path: str | Path | None = None) -> list[Question]:
    p = Path(path) if path else EVAL_SET_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    out: list[Question] = []
    for repo in data["repos"]:
        rname = repo["name"]
        root = repo.get("root", "")
        for q in repo.get("questions", []):
            out.append(
                Question(
                    id=q["id"],
                    repo=rname,
                    domain=q["domain"],
                    category=q.get("category", ""),
                    question=q["question"],
                    answer=q.get("answer", ""),
                    sentinels=tuple(q.get("sentinels", [])),
                    primary=tuple(q.get("primary", [])),
                    difficulty=q.get("difficulty", ""),
                    evidence=q.get("evidence", ""),
                    source=q.get("source", ""),
                    repo_root=root,
                )
            )
    return out


def by_repo_domain(questions: list[Question]) -> dict[tuple[str, str], list[Question]]:
    groups: dict[tuple[str, str], list[Question]] = {}
    for q in questions:
        groups.setdefault((q.repo, q.domain), []).append(q)
    return groups


def combined_corpus(repo_name: str, questions: list[Question] | None = None) -> dict[str, dict]:
    """The single combined per-repo corpus the IR task runs over: every code AND
    markdown file under the repo (minus skips/exclusions), plus a backstop of every
    gold primary for that repo so a primary with an unusual extension is still
    present. ONE corpus per repo — never one per (repo, domain). Retrieval ranks
    across code and docs together; `domain` only slices the reported metrics.
    """
    repo = M.REPOS[repo_name]
    qs = questions if questions is not None else load_questions()
    primaries = {p for q in qs if q.repo == repo_name for p in q.primary}
    return M.load_repo_corpus(repo, kinds=CORPUS_KINDS, guarantee=tuple(sorted(primaries)))


def build_file_qrels(
    questions: list[Question], corpus: dict[str, dict], sentinel_grade1: bool = False
) -> dict[str, dict[str, int]]:
    """File-level graded qrels (consolidated plan §3).

    Grade 2: each hand-pinned ``primary`` file. Grade 1 (only if sentinel_grade1):
    any OTHER corpus file whose text contains a sentinel — corroborating, kept
    SEPARATE from the primary-file headline so a short sentinel matching many files
    cannot inflate the gate. Chunk-level grade-1 qrels are produced at index time
    (they need the chunker); this is the file-level layer.
    """
    qrels: dict[str, dict[str, int]] = {}
    for q in questions:
        rel: dict[str, int] = {p: 2 for p in q.primary}
        if sentinel_grade1:
            for doc_id, payload in corpus.items():
                if doc_id in rel:
                    continue
                text = payload["text"]
                if any(s in text for s in q.sentinels):
                    rel[doc_id] = 1
        qrels[q.id] = rel
    return qrels


def validate_reachability(questions: list[Question]) -> list[str]:
    """Return error strings (empty => every primary reachable + sentinel-bearing).

    For each repo: assemble the combined per-repo corpus once, then assert every
    primary loads and every sentinel is a literal substring of one of its primary
    files (as loaded). This is the check verify.py does NOT do — it proves the
    *manifest/loader* will index the file, catching extension/exclusion gaps.
    """
    errors: list[str] = []
    by_repo: dict[str, list[Question]] = {}
    for q in questions:
        by_repo.setdefault(q.repo, []).append(q)
    for repo_name, qs in by_repo.items():
        if repo_name not in M.REPOS:
            errors.append(f"[{repo_name}] not in corpus manifest REPOS")
            continue
        corpus = combined_corpus(repo_name, qs)
        for q in qs:
            for p in q.primary:
                if p not in corpus:
                    errors.append(f"[{q.id}] primary not reachable by loader: {p}")
                    continue
                text = corpus[p]["text"]
                for s in q.sentinels:
                    if s not in text:
                        # sentinel may live in a different primary of the same q
                        if not any(s in corpus[pp]["text"] for pp in q.primary if pp in corpus):
                            errors.append(f"[{q.id}] sentinel not in any primary as loaded: {s!r}")
                            break
    return errors


def summary(questions: list[Question]) -> dict:
    import collections

    def tally(key):
        c = collections.Counter(key(q) for q in questions)
        return dict(sorted(c.items()))

    return {
        "gold_set_version": GOLD_SET_VERSION,
        "n_questions": len(questions),
        "by_repo": tally(lambda q: q.repo),
        "by_domain": tally(lambda q: q.domain),
        "by_category": tally(lambda q: q.category),
        "by_difficulty": tally(lambda q: q.difficulty),
        "by_multiplicity": tally(lambda q: q.multiplicity),
        "by_source": tally(lambda q: q.source),
        "by_split": tally(lambda q: q.split),
    }


def cmd_summary(args) -> int:
    qs = load_questions(args.eval_set)
    print(json.dumps(summary(qs), indent=2))
    return 0


def cmd_validate(args) -> int:
    qs = load_questions(args.eval_set)
    errors = validate_reachability(qs)
    if errors:
        print(f"gold_loader: REACHABILITY FAILED ({len(errors)} errors):", file=sys.stderr)
        for e in errors[:60]:
            print(f"  - {e}", file=sys.stderr)
        if len(errors) > 60:
            print(f"  … and {len(errors) - 60} more", file=sys.stderr)
        return 1
    print(f"gold_loader: OK — all {len(qs)} questions' primaries reachable + sentinel-bearing")
    return 0


def cmd_qrels(args) -> int:
    qs = load_questions(args.eval_set)
    by_repo: dict[str, list[Question]] = {}
    for q in qs:
        by_repo.setdefault(q.repo, []).append(q)
    print("  repo                    docs   q (code/nl)  grade2  multi   [ONE combined corpus per repo]")
    for repo_name in sorted(by_repo):
        gq = by_repo[repo_name]
        corpus = combined_corpus(repo_name, gq)
        qrels = build_file_qrels(gq, corpus, sentinel_grade1=args.sentinel_grade1)
        multi = sum(1 for r in qrels.values() if len(r) > 1)
        ncode = sum(1 for q in gq if q.domain == "code")
        nnl = len(gq) - ncode
        print(f"  {repo_name:22s} {len(corpus):5d}  {len(gq):3d} ({ncode}/{nnl})    "
              f"{sum(len(r) for r in qrels.values()):5d}  {multi}")
    print(f"gold_loader: built file-qrels over {len(by_repo)} COMBINED per-repo corpora "
          f"(code+docs together; domain is a metric slice). sentinel_grade1={args.sentinel_grade1}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--eval-set", help="path to eval-set.json (default: pinned Phase-1 set)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("summary", help="print the slice tallies").set_defaults(func=cmd_summary)
    sub.add_parser("validate", help="assert every primary is loader-reachable").set_defaults(func=cmd_validate)
    pq = sub.add_parser("qrels", help="build + report file-level qrels per (repo,domain)")
    pq.add_argument("--sentinel-grade1", action="store_true", help="add grade-1 corroborating files")
    pq.set_defaults(func=cmd_qrels)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
