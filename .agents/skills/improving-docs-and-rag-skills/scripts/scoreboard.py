#!/usr/bin/env python3
"""scoreboard.py — aggregate metrics.tsv into the harness's reporting views.

Three views, in order:

  1. **Floor first** — the absolute "no doc, no RAG" baseline (corpus `Z`,
     `--no-retrieval`): every metric scores 0. The four treatment cells are then
     read as **lifts above this floor**, in the named order
     floor → docs-only (`Db`) → RAG-only (`Nr`) → docs+RAG (`Dr`).
  1b. **Content-type comparison** (when code rows are present) — code vs natural
     language on each domain's real corpus (nl = structured `D` docs incl.
     transcripts, code = the inception/ app), per rag config, so the difference
     between code and NL retrieval is directly visible (separate metrics).
  2. **Cell means** — the floor plus the four cells (corpus N|D × rag b|r).
  3. **2×2 factorial (headline)** (plan §3, §9 view 4): the two marginal effects
     (`docs`, `rag`) and the **interaction (coupling)** — each paired per query
     with a seeded-bootstrap CI:

        docs marginal   = mean_q(D − N) at fixed rag
        rag  marginal   = mean_q(r − b) at fixed corpus
        coupling (×)    = mean_q[(Dr−Db) − (Nr−Nb)]   # > 0 ⇒ co-design beats additive

The floor is the reference, NOT part of the interaction math (the factorial is over
the four populated cells only). Pairing is by query_id (rows averaged across seeds
first). With a small gold set the CIs are wide — that is honest, not a bug; widen N
(more gold queries) to tighten them.

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
# The absolute floor: empty corpus + no retrieval ("no doc, no RAG"). Reported
# first as the reference the four cells lift above; never part of the factorial.
FLOOR_CORPUS = "Z"
# The user-facing named conditions, in baseline-first order, mapped to the cells.
NAMED_CONDITIONS = [
    ("docs-only", ("D", "b")),   # docs skill, baseline (no rag skill)
    ("RAG-only", ("N", "r")),    # rag skill, naive corpus (no docs skill)
    ("docs+RAG", ("D", "r")),    # both skills (co-designed)
]
# Content-type axis: each domain's "real" corpus tag for the code-vs-nl comparison
# (nl = the structured D docs; code = the inception/ codebase, corpus tag "code").
DOMAIN_REAL_CORPUS = {"nl": "D", "code": "code"}
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


def select_round(rows, round_sel):
    if round_sel not in ("all", "latest"):
        return [r for r in rows if r.get("round") == round_sel]
    if round_sel == "latest" and rows:
        last = max(r.get("round", "0") for r in rows)
        return [r for r in rows if r.get("round") == last]
    return rows


def per_query_cell(rows, metric, round_sel):
    """-> {(corpus,rag): {query_id: mean_metric_over_seeds}}."""
    rows = select_round(rows, round_sel)
    acc = defaultdict(lambda: defaultdict(list))
    for r in rows:
        cell = (r["corpus"], r["rag"])
        try:
            acc[cell][r["query_id"]].append(float(r[metric]))
        except (KeyError, ValueError):
            continue
    # `if v` drops query buckets left empty by a non-numeric/missing metric cell
    # (the defaultdict read inserts the key before float() can raise).
    return {cell: {q: statistics.mean(v) for q, v in qs.items() if v} for cell, qs in acc.items()}


def floor_per_query(rows, metric, round_sel):
    """Per-query floor metric (corpus Z, any rag tag), averaged over rows."""
    rows = select_round(rows, round_sel)
    acc = defaultdict(list)
    for r in rows:
        if r.get("corpus") != FLOOR_CORPUS:
            continue
        try:
            acc[r["query_id"]].append(float(r[metric]))
        except (KeyError, ValueError):
            continue
    return {q: statistics.mean(v) for q, v in acc.items() if v}


def cell_mean(d):
    """Mean over a {query_id: value} dict, or None if empty."""
    return statistics.mean(d.values()) if d else None


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

    # de-dupe (preserve order) so `--metric ndcg@10|retrieval_hit@20|mrr` doesn't
    # render the chosen metric as two identical columns.
    key_metrics = list(dict.fromkeys([args.metric, "ndcg@10", "retrieval_hit@20", "mrr"]))
    pqc = {m: per_query_cell(rows, m, args.round) for m in key_metrics}
    floor = {m: floor_per_query(rows, m, args.round) for m in key_metrics}

    # Baseline-first view: the floor, then each named condition as a lift above it.
    def lift_line(label, val, fl):
        if val is None:
            return f"  {label:<24}{'-':>8}"
        s = f"  {label:<24}{val:>8.3f}"
        return s if fl is None else s + f"   (Δ {val - fl:+.3f} vs floor)"

    print(f"## Baseline-first view — {args.metric} (lift above the no-doc/no-RAG floor)")
    fl = cell_mean(floor[args.metric])
    if fl is None:
        print(f"  {'floor (no doc, no RAG)':<24}{'(not run — add Z/--no-retrieval cell)'}")
    else:
        print(f"  {'floor (no doc, no RAG)':<24}{fl:>8.3f}")
    for name, cell in NAMED_CONDITIONS:
        print(lift_line(f"{name} ({cell[0]}{cell[1]})", cell_mean(pqc[args.metric].get(cell, {})), fl))
    print(lift_line("naive ref (Nb)", cell_mean(pqc[args.metric].get(("N", "b"), {})), fl))

    # Content-type comparison: code vs natural language, each on its own real
    # corpus (nl = structured D docs, code = inception/), per rag config. The
    # headline for the content-type axis — separate metrics so the difference
    # between code and natural-language retrieval is directly visible.
    if any(r.get("domain") == "code" or r.get("corpus") == "code" for r in select_round(rows, args.round)):
        print("\n## Content-type comparison — code vs natural language")
        print("  domain@rag" + "".join(f"{m:>18}" for m in key_metrics) + "      n")
        for domain in ("nl", "code"):
            corp = DOMAIN_REAL_CORPUS[domain]
            for rag in ("b", "r"):
                dm = {m: pqc[m].get((corp, rag), {}) for m in key_metrics}
                n = max((len(v) for v in dm.values()), default=0)
                vals = "".join(f"{cell_mean(dm[m]):>18.3f}" if dm[m] else f"{'-':>18}" for m in key_metrics)
                print(f"  {domain + ' @ ' + rag:<10}" + vals + f"   {n:>4}")
        print("  (nl = structured D docs incl. transcripts; code = inception/ app. Same eval")
        print("   path, but absolute recall is NOT cross-domain comparable while the code")
        print("   corpus is tiny: with ~12 files < top_k, code recall@k & retrieval_hit@20 sit")
        print("   at ceiling — only ndcg@10 / mrr / precision discriminate code rankers.)")

    # Cell means for the key metrics (floor row first, then the four cells).
    print("\n## Cell means (corpus × rag)")
    hdr = "  cell   " + "".join(f"{m:>18}" for m in key_metrics)
    print(hdr)
    floor_cells = [f"{cell_mean(floor[m]):>18.3f}" if floor[m] else f"{'-':>18}" for m in key_metrics]
    print(f"  {'Z*':<6}" + "".join(floor_cells))
    for cell in CELLS:
        label = f"{cell[0]}{cell[1]}"
        cells = []
        for m in key_metrics:
            d = pqc[m].get(cell, {})
            cells.append(f"{statistics.mean(d.values()):>18.3f}" if d else f"{'-':>18}")
        print(f"  {label:<6}" + "".join(cells))
    print("  (Z* = floor: empty corpus + --no-retrieval; 'no doc, no RAG')")

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
