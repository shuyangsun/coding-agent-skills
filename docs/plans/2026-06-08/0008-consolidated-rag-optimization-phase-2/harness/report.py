#!/usr/bin/env python3
"""report.py — render a benchmark summary.json into markdown tables.

Reused across every wave so reported numbers are transcribed mechanically (never by
hand) from run_benchmark.py's summary.json. Emits:
  - an arm-comparison table (overall slice) for all arms in the run;
  - for a chosen --focus arm, by-domain (code|nl) and by-repo breakdowns;
  - optionally a delta table vs a --baseline arm (held-out aware via --split-summary).

Stdlib-only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# (column header, metric key, format)
COLS = [
    ("R@5", "ret.recall@5", "{:.3f}"),
    ("R@20", "ret.recall@20", "{:.3f}"),
    ("R@100", "ret.recall@100", "{:.3f}"),
    ("nDCG@10", "ret.ndcg@10", "{:.3f}"),
    ("MRR", "ret.mrr", "{:.3f}"),
    ("pMRR", "ret.primary_mrr", "{:.3f}"),
    ("pR@20", "ret.primary_recall@20", "{:.3f}"),
    ("sentCov", "ret.sentinel_cov", "{:.3f}"),
    ("hit@5", "ret.answer_hit@5", "{:.3f}"),
    ("contam", "ver.contamination_hits", "{:.2f}"),
    ("ctxTok", "pack.context_tokens", "{:.0f}"),
    ("ms", "eff.retrieval_ms", "{:.0f}"),
]


def _row(label: str, cell: dict, cols=COLS) -> str:
    out = [label, str(cell.get("n", ""))]
    for _h, key, fmt in cols:
        v = cell.get(key)
        out.append(fmt.format(v) if isinstance(v, (int, float)) else "")
    return "| " + " | ".join(out) + " |"


def _header(cols=COLS) -> str:
    head = ["arm", "n"] + [h for h, _k, _f in cols]
    sep = ["---"] * len(head)
    return "| " + " | ".join(head) + " |\n| " + " | ".join(sep) + " |"


def arm_table(summary: dict, axis="overall", val="all") -> str:
    lines = [_header()]
    for arm, info in summary["arms"].items():
        cell = info["agg"].get(axis, {}).get(val)
        if cell:
            lines.append(_row(arm, cell))
    return "\n".join(lines)


def focus_axis(summary: dict, arm: str, axis: str) -> str:
    info = summary["arms"][arm]
    head = [axis, "n"] + [h for h, _k, _f in COLS]
    lines = ["| " + " | ".join(head) + " |", "| " + " | ".join(["---"] * len(head)) + " |"]
    for val, cell in sorted(info["agg"].get(axis, {}).items()):
        lines.append(_row(val, cell))
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("summary", help="path to a run's -summary.json")
    ap.add_argument("--focus", help="arm to break down by domain+repo")
    ap.add_argument("--axes", default="domain,repo,category,difficulty",
                    help="comma axes for the focus arm")
    args = ap.parse_args(argv)
    summary = json.loads(Path(args.summary).read_text())

    print(f"### Arm comparison (overall, split={summary.get('split')})\n")
    print(arm_table(summary))
    focus = args.focus or next(iter(summary["arms"]))
    print(f"\n### `{focus}` by slice\n")
    for axis in args.axes.split(","):
        print(f"\n**by {axis}**\n")
        print(focus_axis(summary, focus, axis))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
