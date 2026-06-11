#!/usr/bin/env python3
"""wave6_fit_gate.py — fit the Wave-6 CRAG-style rerank confidence gate on dev rows.

Input: a run TSV containing BOTH the no-rerank base arm and the always-rerank arm
with logged confidence features (`w6-rrk-log`, rerank.gate.log_only). For every
candidate gate rule (single-feature thresholds + OR-pairs of the best singles) it
simulates per-query routing — take the always-rerank row when the gate fires, the
base row otherwise — and reports the dev frontier vs never-rerank and always-rerank.

The chosen rule is then FROZEN into configs/wave6/w6-rrk-gate.json by hand before
any held-out run (tune on dev, report held-out — plan 0008 operating rules).

    wave6_fit_gate.py <metrics.tsv> --base w4-ctx-llm-gemma4-all --rrk w6-rrk-log \
        [--split dev] [--top 12]
"""
from __future__ import annotations

import argparse
import csv
import itertools
from pathlib import Path

METRICS = ["ret.ndcg@10", "ret.primary_mrr", "ret.answer_hit@5", "ret.sentinel_cov",
           "ret.recall@20"]
SHORT = {"ret.ndcg@10": "nDCG", "ret.primary_mrr": "pMRR", "ret.answer_hit@5": "hit5",
         "ret.sentinel_cov": "sent", "ret.recall@20": "R20"}


def parse_feat(s: str) -> dict:
    out = {}
    for kv in (s or "").split(";"):
        if "=" in kv:
            k, v = kv.split("=", 1)
            try:
                out[k] = float(v)
            except ValueError:
                pass
    return out


def load(tsv: Path, base: str, rrk: str, split: str):
    rows = list(csv.DictReader(tsv.open(), delimiter="\t"))
    rows = [r for r in rows if r["slice.split"] == split]
    b = {r["slice.query_id"]: r for r in rows if r["arm.arm"] == base}
    a = {r["slice.query_id"]: r for r in rows if r["arm.arm"] == rrk}
    qids = sorted(set(b) & set(a))
    recs = []
    for qid in qids:
        feats = parse_feat(a[qid].get("route.feat", ""))
        if not feats:
            continue
        recs.append({
            "qid": qid, "feats": feats, "domain": b[qid]["slice.domain"],
            "base": {m: float(b[qid][m]) for m in METRICS},
            "rrk": {m: float(a[qid][m]) for m in METRICS},
        })
    return recs


def simulate(recs, fires) -> dict:
    n = len(recs)
    out = {}
    for m in METRICS:
        out[m] = sum((r["rrk"][m] if f else r["base"][m]) for r, f in zip(recs, fires)) / n
    out["rate"] = sum(fires) / n
    return out


def candidate_gates(recs):
    feats = sorted(recs[0]["feats"])
    singles = []
    for f in feats:
        vals = sorted({r["feats"][f] for r in recs})
        # candidate thresholds at observed values (≤ for low-confidence features,
        # ≥ for dispersion-style ones)
        for v in vals:
            singles.append((f"{f}<={v:g}", lambda r, f=f, v=v: r["feats"][f] <= v))
            singles.append((f"{f}>={v:g}", lambda r, f=f, v=v: r["feats"][f] >= v))
    return singles


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tsv")
    ap.add_argument("--base", required=True)
    ap.add_argument("--rrk", required=True)
    ap.add_argument("--split", default="dev")
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args(argv)

    recs = load(Path(args.tsv), args.base, args.rrk, args.split)
    if not recs:
        print("no joined rows with features — is w6-rrk-log in the TSV?")
        return 1
    n = len(recs)
    never = simulate(recs, [False] * n)
    always = simulate(recs, [True] * n)

    def fmt(tag, sim, ref):
        cells = " ".join(f"{SHORT[m]}={sim[m]:.3f}({sim[m]-ref[m]:+.3f})" for m in METRICS)
        return f"{tag:34s} rate={sim['rate']:.2f}  {cells}"

    print(f"# gate fit on split={args.split}  n={n}")
    print(fmt("NEVER (base)", never, never))
    print(fmt("ALWAYS (rrk)", always, never))

    # ORACLE: per-query best (upper bound a deterministic gate cannot exceed)
    oracle_fires = [sum(r["rrk"][m] - r["base"][m] for m in METRICS) > 0 for r in recs]
    print(fmt("ORACLE (per-query best)", simulate(recs, oracle_fires), never))
    print()

    # score gates: ranking improvement vs base + coverage retention vs always
    def score(sim):
        rank_gain = (sim["ret.ndcg@10"] - never["ret.ndcg@10"]) + \
                    (sim["ret.primary_mrr"] - never["ret.primary_mrr"])
        cov_gain = (sim["ret.answer_hit@5"] - never["ret.answer_hit@5"]) + \
                   (sim["ret.sentinel_cov"] - never["ret.sentinel_cov"])
        return rank_gain + 0.5 * cov_gain

    singles = candidate_gates(recs)
    scored = []
    for name, fn in singles:
        fires = [fn(r) for r in recs]
        rate = sum(fires) / n
        if rate < 0.05 or rate > 0.95:
            continue
        sim = simulate(recs, fires)
        scored.append((score(sim), name, sim, fires))
    scored.sort(key=lambda x: -x[0])

    print(f"## top single-feature gates (of {len(scored)} candidates)")
    for s, name, sim, _f in scored[:args.top]:
        print(fmt(name, sim, never))

    # OR-pairs of the top 8 singles
    print("\n## top OR-pair gates")
    pair_scored = []
    seen = set()
    for (s1, n1, _m1, f1), (s2, n2, _m2, f2) in itertools.combinations(scored[:8], 2):
        feat1, feat2 = n1.split("<=")[0].split(">=")[0], n2.split("<=")[0].split(">=")[0]
        if feat1 == feat2:
            continue
        fires = [a or b for a, b in zip(f1, f2)]
        key = tuple(fires)
        if key in seen:
            continue
        seen.add(key)
        sim = simulate(recs, fires)
        pair_scored.append((score(sim), f"{n1} OR {n2}", sim))
    pair_scored.sort(key=lambda x: -x[0])
    for s, name, sim in pair_scored[:args.top]:
        print(fmt(name, sim, never))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
