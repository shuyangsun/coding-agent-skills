#!/usr/bin/env python3
"""scoreboard.py — aggregate metrics.tsv into the harness's reporting views.

The headline is the **2×2 factorial** (plan §3, §9 view 4): four cell means
(corpus N|D × rag b|r), the two marginal effects (`docs`, `rag`), and the
**interaction (coupling)** — each paired per query with a seeded-bootstrap CI:

    docs marginal   = mean_q(D − N) at fixed rag
    rag  marginal   = mean_q(r − b) at fixed corpus
    coupling (×)    = mean_q[(Dr−Db) − (Nr−Nb)]   # > 0 ⇒ co-design beats additive

Pairing is by query_id (rows averaged across seeds first). With a small gold set
the CIs are wide — that is honest, not a bug; widen N (more gold queries) to
tighten them. Also prints cell means for the key metrics and a by-difficulty view.

Usage:
  scoreboard.py --tsv metrics.tsv [--metric recall@20] [--round latest|all|N]
"""
from __future__ import annotations

import argparse
import random
import statistics
from collections import defaultdict
from pathlib import Path

CELLS = [("N", "b"), ("N", "r"), ("D", "b"), ("D", "r")]
BOOTSTRAP_B = 2000
BOOTSTRAP_SEED = 12345


def read_tsv(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return []
    header = lines[0].split("\t")
    rows = []
    for ln in lines[1:]:
        if ln.strip():
            rows.append(dict(zip(header, ln.split("\t"))))
    return rows


def per_query_cell(rows, metric, round_sel):
    """-> {(corpus,rag): {query_id: mean_metric_over_seeds}}."""
    if round_sel not in ("all", "latest"):
        rows = [r for r in rows if r.get("round") == round_sel]
    elif round_sel == "latest" and rows:
        last = max(r.get("round", "0") for r in rows)
        rows = [r for r in rows if r.get("round") == last]
    acc = defaultdict(lambda: defaultdict(list))
    for r in rows:
        cell = (r["corpus"], r["rag"])
        try:
            acc[cell][r["query_id"]].append(float(r[metric]))
        except (KeyError, ValueError):
            continue
    return {cell: {q: statistics.mean(v) for q, v in qs.items()} for cell, qs in acc.items()}


def paired_diff(cell_a: dict, cell_b: dict) -> list[float]:
    """Per-query (a − b) over the shared queries."""
    return [cell_a[q] - cell_b[q] for q in sorted(set(cell_a) & set(cell_b))]


def boot_ci(diffs: list[float], conf=0.90):
    if not diffs:
        return (0.0, 0.0, 0.0)
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(diffs)
    means = []
    for _ in range(BOOTSTRAP_B):
        means.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    lo = means[int((1 - conf) / 2 * BOOTSTRAP_B)]
    hi = means[int((1 + conf) / 2 * BOOTSTRAP_B) - 1]
    return (statistics.mean(diffs), lo, hi)


def fmt_effect(name: str, diffs: list[float]) -> str:
    mean, lo, hi = boot_ci(diffs)
    star = "*" if (lo > 0 or hi < 0) else " "
    return f"  {name:<24} {mean:+.3f}  90% CI [{lo:+.3f}, {hi:+.3f}] {star}  (n={len(diffs)})"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tsv", required=True)
    ap.add_argument("--metric", default="recall@20")
    ap.add_argument("--round", default="latest")
    args = ap.parse_args(argv)

    rows = read_tsv(Path(args.tsv))
    if not rows:
        print("scoreboard: no rows")
        return 1

    print(f"# scoreboard — metric={args.metric}  round={args.round}  rows={len(rows)}\n")

    # Cell means for the key metrics
    print("## Cell means (corpus × rag)")
    key_metrics = [args.metric, "ndcg@10", "retrieval_hit@20", "mrr"]
    pqc = {m: per_query_cell(rows, m, args.round) for m in key_metrics}
    hdr = "  cell   " + "".join(f"{m:>18}" for m in key_metrics)
    print(hdr)
    for cell in CELLS:
        label = f"{cell[0]}{cell[1]}"
        cells = []
        for m in key_metrics:
            d = pqc[m].get(cell, {})
            cells.append(f"{statistics.mean(d.values()):>18.3f}" if d else f"{'-':>18}")
        print(f"  {label:<6}" + "".join(cells))

    # Factorial effects on the chosen metric
    c = per_query_cell(rows, args.metric, args.round)
    have = all(cell in c and c[cell] for cell in CELLS)
    print(f"\n## Factorial effects on {args.metric} (paired per query)")
    if not have:
        print("  (need all four cells Nb/Nr/Db/Dr populated; have: "
              + ", ".join(f"{a}{b}" for (a, b) in CELLS if c.get((a, b))) + ")")
        return 0
    Nb, Nr, Db, Dr = c[("N", "b")], c[("N", "r")], c[("D", "b")], c[("D", "r")]
    print(fmt_effect("docs marginal @ b (Db−Nb)", paired_diff(Db, Nb)))
    print(fmt_effect("docs marginal @ r (Dr−Nr)", paired_diff(Dr, Nr)))
    print(fmt_effect("rag  marginal @ N (Nr−Nb)", paired_diff(Nr, Nb)))
    print(fmt_effect("rag  marginal @ D (Dr−Db)", paired_diff(Dr, Db)))
    qs = sorted(set(Nb) & set(Nr) & set(Db) & set(Dr))
    inter = [(Dr[q] - Db[q]) - (Nr[q] - Nb[q]) for q in qs]
    print(fmt_effect("coupling/interaction (×)", inter))
    print("\n  (* = 90% bootstrap CI excludes zero. Small gold set ⇒ wide CIs; "
          "grow the fact table to tighten.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
