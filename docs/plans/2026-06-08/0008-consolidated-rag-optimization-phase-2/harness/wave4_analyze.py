#!/usr/bin/env python3
"""wave4_analyze.py — slice-aware A/B analysis over a run's per-query metrics TSV.

run_benchmark's summary.json aggregates each slice axis INDEPENDENTLY, so it cannot
answer "held-out AND code" (the cross of two axes) — which is exactly the promotion
gate (held-out, no domain/repo/difficulty slice regresses). This reads the per-query
TSV (one row per query x arm, with all slice columns) and crosses split x domain x
arm, printing each arm's headline metrics and the delta vs a chosen baseline arm,
then flags any (repo|difficulty x domain) cell where a candidate REGRESSES on the
gating metrics. Stdlib-only.

    wave4_analyze.py <metrics.tsv> --baseline w2-ctx-header [--split held-out] [--metrics ...]
"""
from __future__ import annotations

import argparse
import collections
import csv
from pathlib import Path

GATING = ["ret.ndcg@10", "ret.primary_mrr", "ret.recall@20", "ret.mrr"]
SHOW = ["ret.recall@20", "ret.ndcg@10", "ret.mrr", "ret.primary_mrr",
        "ret.sentinel_cov", "ret.answer_hit@5"]
SHORT = {"ret.recall@20": "R@20", "ret.ndcg@10": "nDCG@10", "ret.mrr": "MRR",
         "ret.primary_mrr": "pMRR", "ret.sentinel_cov": "sentCov", "ret.answer_hit@5": "hit@5"}


def load(tsv: Path) -> list[dict]:
    with tsv.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def fnum(row, k):
    try:
        return float(row[k])
    except (KeyError, ValueError, TypeError):
        return None


def mean(rows, k):
    vals = [fnum(r, k) for r in rows]
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else 0.0


def arms_in_order(rows):
    seen = []
    for r in rows:
        a = r["arm.arm"]
        if a not in seen:
            seen.append(a)
    return seen


def table(rows, arms, baseline, metrics, title):
    print(f"\n### {title}  (n={len(rows)//max(1,len(arms))} per arm)\n")
    hdr = ["arm"] + [SHORT.get(m, m) for m in metrics]
    print("| " + " | ".join(hdr) + " |")
    print("| " + " | ".join(["---"] * len(hdr)) + " |")
    base = {m: mean([r for r in rows if r["arm.arm"] == baseline], m) for m in metrics}
    for a in arms:
        arows = [r for r in rows if r["arm.arm"] == a]
        if not arows:
            continue
        cells = [a]
        for m in metrics:
            v = mean(arows, m)
            d = v - base[m]
            cells.append(f"{v:.3f}" if a == baseline else f"{v:.3f} ({d:+.3f})")
        print("| " + " | ".join(cells) + " |")


def regression_scan(rows, arms, baseline, split):
    """For the chosen split, flag (axis-value x domain) cells where a candidate arm
    drops vs baseline on any gating metric by more than a noise epsilon."""
    EPS = 0.005
    srows = [r for r in rows if r["slice.split"] == split]
    print(f"\n### Regression scan (split={split}, eps={EPS}) — gating metrics, by repo x domain and difficulty x domain\n")
    for cand in arms:
        if cand == baseline:
            continue
        hits = []
        for axis in ("slice.repo", "slice.difficulty"):
            cells = collections.defaultdict(lambda: collections.defaultdict(list))
            for r in srows:
                cells[(r[axis], r["slice.domain"])][r["arm.arm"]].append(r)
            for (av, dom), byarm in sorted(cells.items()):
                if baseline not in byarm or cand not in byarm:
                    continue
                for m in GATING:
                    b = mean(byarm[baseline], m)
                    c = mean(byarm[cand], m)
                    if c < b - EPS:
                        hits.append(f"    {axis.split('.')[1]}={av:24s} domain={dom:4s} {SHORT.get(m,m):8s} {b:.3f} -> {c:.3f} ({c-b:+.3f})")
        print(f"  [{cand}] vs [{baseline}]: {'CLEAN (no slice regresses)' if not hits else str(len(hits))+' regressed cell(s):'}")
        for h in hits[:40]:
            print(h)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tsv")
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--splits", default="held-out,dev")
    ap.add_argument("--metrics", default=",".join(SHOW))
    args = ap.parse_args(argv)
    rows = load(Path(args.tsv))
    arms = arms_in_order(rows)
    metrics = args.metrics.split(",")
    print(f"# A/B analysis: {Path(args.tsv).name}\nbaseline = {args.baseline}\narms = {arms}")
    for split in args.splits.split(","):
        srows = [r for r in rows if r["slice.split"] == split]
        table(srows, arms, args.baseline, metrics, f"split={split} — OVERALL")
        for dom in ("code", "nl"):
            drows = [r for r in srows if r["slice.domain"] == dom]
            table(drows, arms, args.baseline, metrics, f"split={split} — domain={dom}")
    regression_scan(rows, arms, args.baseline, "held-out")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
