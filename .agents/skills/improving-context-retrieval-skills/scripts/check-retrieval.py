#!/usr/bin/env python3
"""check-retrieval.py — the READ oracle for the docs+rag harness.

Scores a retrieval run (from docs-eval.py) against the pinned gold qrels and
prints `KEY=VALUE` lines (the harness's machine-readable contract, mirroring the
vcs harness's check-quality.sh). It imports gold.py so the labels and the scorer
are the same source of truth and cannot drift.

Metrics:
  recall@k, precision@k, ndcg@k (graded), mrr  — averaged over the split
  retrieval_hit@K  — fraction of queries with a PRIMARY gold doc in top-K
                     (judge-free answerability signal; plan §6 primary)
  Per-difficulty recall@K and retrieval_hit@K.

Factuality (sentinel containment) requires a generated answer, which Phase-0 has
no LLM to produce, so it is reported as N/A here and computed by the generation
path in Phase 1. retrieval_hit is the Phase-0 answerability proxy.

Pass `--corpus-kind code --domain code` to score a code run against the inception/
corpus, or `--corpus-kind image --domain image` to score image-backed website
project-context retrieval. The emitted TSV carries a `domain` column so the
scoreboard can break code, image, and natural-language metrics apart.

Usage:
  check-retrieval.py --run RUN.jsonl [--corpus DIR] [--split dev|held-out|all]
                     [--corpus-kind md|code|image] [--domain nl|code|image] [--k 5,10,20] [--headline-k 20]
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gold  # noqa: E402

DOMAIN_KIND = {"nl": "md", "code": "code", "image": "image"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--corpus")
    ap.add_argument("--corpus-kind", choices=["md", "code", "image"], default="md",
                    help="md = markdown docs (nl); code = inception/; image = image-backed website project context")
    ap.add_argument("--domain", choices=["nl", "code", "image"], default="nl",
                    help="content type; selects which gold facts are scored")
    ap.add_argument("--split", choices=["dev", "held-out", "all"], default="all")
    ap.add_argument("--k", default="5,10,20")
    ap.add_argument("--headline-k", type=int, default=20)
    ap.add_argument(
        "--qrels-mode",
        choices=["pinned", "sentinel"],
        default="pinned",
        help="pinned: GOLD/D structured paths; sentinel: per-corpus N/D derivation",
    )
    # Optional per-query TSV emission (feeds record-metrics.sh / scoreboard.py).
    ap.add_argument("--tsv-out", help="append one plan-schema row per query to this file")
    ap.add_argument("--round", default="0")
    ap.add_argument("--corpus-tag", default="GOLD", help="N|D|Z|GOLD (Z = the no-doc floor)")
    ap.add_argument("--rag-tag", default="b", help="b|r, or 0 for the no-RAG floor")
    ap.add_argument("--rag-config-id", default="")
    ap.add_argument("--mode", default="rag")
    ap.add_argument("--retrieval-tag", default="plain")
    ap.add_argument("--seed", default="0")
    args = ap.parse_args(argv)

    # Guard: domain and corpus-kind must agree, else the run is scored against the
    # wrong corpus and mis-grades via cross-domain sentinel overlap.
    expected_kind = DOMAIN_KIND[args.domain]
    if args.corpus_kind != expected_kind:
        ap.error(f"--domain {args.domain} requires --corpus-kind {expected_kind}")

    ks = [int(x) for x in args.k.split(",")]
    hk = args.headline_k
    if args.corpus_kind == "code":
        corpus_root = gold.find_code_corpus_root(args.corpus)
        if corpus_root is None:
            ap.error("--corpus-kind code: inception/ corpus not found; pass --corpus DIR")
    elif args.corpus_kind == "image":
        corpus_root = gold.find_image_corpus_root(args.corpus)
        if corpus_root is None:
            ap.error("--corpus-kind image: image corpus not found; pass --corpus DIR")
    else:
        corpus_root = gold.find_corpus_root(args.corpus)
    docs = gold.load_corpus(corpus_root, kind=args.corpus_kind)
    facts = [
        f for f in gold.FACTS
        if args.split in ("all", gold.split_of(f.id)) and f.domain == args.domain
    ]
    qrels = gold.build_qrels(facts, docs, mode=args.qrels_mode)
    runs = gold.load_run(Path(args.run))

    per_query: dict[str, dict[str, float]] = {}
    hit: dict[str, int] = {}
    by_diff_recall: dict[str, list[float]] = defaultdict(list)
    by_diff_hit: dict[str, list[int]] = defaultdict(list)
    missing = []
    for fact in facts:
        ranked = runs.get(fact.id)
        if ranked is None:
            missing.append(fact.id)
            continue
        m = gold.score_query(ranked, qrels[fact.id], ks)
        per_query[fact.id] = m
        grade2 = {d for d, g in qrels[fact.id].items() if g >= 2}
        h = 1 if any(d in grade2 for d in ranked[:hk]) else 0
        hit[fact.id] = h
        by_diff_recall[fact.difficulty].append(m.get(f"recall@{hk}", 0.0))
        by_diff_hit[fact.difficulty].append(h)

    # Optional: append plan-schema per-query rows for the factorial scoreboard.
    # NOTE: the TSV retrieval_hit column is fixed at @20 (what scoreboard.py reads
    # by name); its value is `hit`, computed at --headline-k. Keep --headline-k=20
    # (the default, and what LOOP.md uses) when emitting TSV, or the column label
    # and its value diverge.
    if args.tsv_out:
        cols = [
            "round", "corpus", "domain", "rag", "rag_config_id", "mode", "retrieval", "seed",
            "query_id", "qtype", "difficulty",
            "recall@5", "recall@10", "recall@20", "precision@5", "precision@10",
            "ndcg@10", "mrr", "retrieval_hit@20",
        ]
        out_path = Path(args.tsv_out)
        new = not out_path.exists() or out_path.stat().st_size == 0
        with out_path.open("a", encoding="utf-8") as fh:
            if new:
                fh.write("\t".join(cols) + "\n")
            for fact in facts:
                if fact.id not in per_query:
                    continue
                m = per_query[fact.id]
                row = [
                    args.round, args.corpus_tag, args.domain, args.rag_tag, args.rag_config_id,
                    args.mode, args.retrieval_tag, args.seed,
                    fact.id, fact.qtype, fact.difficulty,
                    f"{m['recall@5']:.4f}", f"{m['recall@10']:.4f}", f"{m['recall@20']:.4f}",
                    f"{m['precision@5']:.4f}", f"{m['precision@10']:.4f}",
                    f"{m['ndcg@10']:.4f}", f"{m['mrr']:.4f}", str(hit[fact.id]),
                ]
                fh.write("\t".join(row) + "\n")

    agg = gold.aggregate(per_query)
    for key in sorted(agg):
        print(f"{key}={agg[key]:.4f}")
    print(f"retrieval_hit@{hk}={(sum(hit.values()) / len(hit)) if hit else 0.0:.4f}")
    for diff in ("easy", "medium", "hard"):
        if by_diff_recall[diff]:
            r = sum(by_diff_recall[diff]) / len(by_diff_recall[diff])
            h = sum(by_diff_hit[diff]) / len(by_diff_hit[diff])
            print(f"recall@{hk}.{diff}={r:.4f}")
            print(f"retrieval_hit@{hk}.{diff}={h:.4f}")
    print("factuality_grounded=NA")  # needs generation (Phase 1)
    print(f"domain={args.domain}")
    print(f"n_scored={len(per_query)}")
    print(f"n_missing={len(missing)}")
    print(f"split={args.split}")
    print(f"gold_set_version={gold.GOLD_SET_VERSION}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
