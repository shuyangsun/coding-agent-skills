#!/usr/bin/env python3
"""metrics.py — slice-aware metrics schema + writer for the Phase-3 benchmark.

Pre-work for ``0008-consolidated-rag-optimization-phase-2.md`` §"Harness and
Gold-Set Wiring" items 6-7 ("one row per query × repo × domain × config";
"separate retrieval, packing, generation, and verification metrics") and the
"Required Slices" rules.

ONE row per (query × config-arm). Columns are grouped into CHANNELS by prefix so a
stronger answer prompt can never hide a weaker retriever:

  slice.*  — query_id, repo, domain, category, difficulty, multiplicity, split, source
             (domain=code|nl is a REPORTING slice; aggregate rows total AND by domain —
             the retrieval task itself is one combined code+docs index, type-blind)
  arm.*    — run_id, config_id, arm, index_mode, header, reranked
  ret.*    — retrieval quality (recall@k, precision@k, ndcg@10, mrr, primary_mrr, sentinel_cov)
             + frac_code_retrieved / frac_md_retrieved (diagnostic: the code/doc mix
             actually retrieved, showing cross-type retrieval happens)
  pack.*   — context packing (context_tokens, n_packed)        [filled by Wave 7]
  gen.*    — answer generation (abstained, answer_len)          [filled by Wave 7]
  ver.*    — verification (sentinel_contained, citation_support, unsupported_rate, contamination_hits)
  eff.*    — efficiency (retrieval_ms, index_ms)

Retrieval scoring REUSES the harness's existing scorer
(improving-context-retrieval-skills/scripts/gold.py: score_query) so there is one
deterministic IR core; this module adds the primary-file split + sentinel coverage
+ the slice columns + the TSV writer. Stdlib-only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gold_loader as G  # noqa: E402


def _harness_gold():
    """Import the canonical IR scorer from improving-context-retrieval-skills."""
    for anc in Path(__file__).resolve().parents:
        cand = anc / ".agents/skills/improving-context-retrieval-skills/scripts"
        if (cand / "gold.py").is_file():
            sys.path.insert(0, str(cand))
            import gold  # noqa
            return gold
    raise RuntimeError("could not locate improving-context-retrieval-skills/scripts/gold.py")


DEFAULT_KS = (5, 10, 20, 100)

SLICE_FIELDS = ["slice.query_id", "slice.repo", "slice.domain", "slice.category",
                "slice.difficulty", "slice.multiplicity", "slice.split", "slice.source"]
ARM_FIELDS = ["arm.run_id", "arm.config_id", "arm.arm", "arm.index_mode", "arm.header", "arm.reranked"]
RET_FIELDS = ["ret.recall@5", "ret.recall@20", "ret.recall@100", "ret.precision@5",
              "ret.precision@10", "ret.ndcg@10", "ret.mrr", "ret.primary_mrr",
              "ret.primary_recall@20", "ret.sentinel_cov", "ret.answer_hit@5", "ret.n_ranked",
              # diagnostic: of the retrieved chunks, the code/md mix. The retriever is
              # type-blind (one combined index), so a code question SHOULD pull docs too
              # and vice versa — these make that visible. Not a quality gate.
              "ret.frac_code_retrieved", "ret.frac_md_retrieved"]
PACK_FIELDS = ["pack.context_tokens", "pack.n_packed"]
GEN_FIELDS = ["gen.abstained", "gen.answer_len"]
VER_FIELDS = ["ver.sentinel_contained", "ver.citation_support", "ver.unsupported_rate",
              "ver.contamination_hits"]
EFF_FIELDS = ["eff.retrieval_ms", "eff.index_ms"]
# route.* — Wave-6 query routing diagnostics: which adaptive action ran for this query
# (action), whether its gate fired (triggered), subquery count, and the compact
# first-pass confidence feature string (feat: k=v;k=v) used to fit gates on dev.
ROUTE_FIELDS = ["route.action", "route.triggered", "route.n_sub", "route.feat"]

ROW_FIELDS = (SLICE_FIELDS + ARM_FIELDS + RET_FIELDS + PACK_FIELDS + GEN_FIELDS
              + VER_FIELDS + EFF_FIELDS + ROUTE_FIELDS)


def slice_columns(q: G.Question) -> dict:
    return {
        "slice.query_id": q.id, "slice.repo": q.repo, "slice.domain": q.domain,
        "slice.category": q.category, "slice.difficulty": q.difficulty,
        "slice.multiplicity": q.multiplicity, "slice.split": q.split, "slice.source": q.source,
    }


def retrieval_metrics(ranked: list[str], qrels_q: dict[str, int], ks=DEFAULT_KS,
                      retrieved_texts: list[str] | None = None,
                      sentinels: tuple[str, ...] = (),
                      retrieved_kinds: list[str] | None = None) -> dict:
    """ret.* metrics for one query. `ranked` is the ordered doc-id list; `qrels_q`
    maps doc_id -> grade (2 primary, 1 corroborating). `retrieved_texts` (chunk
    raw_text aligned to `ranked`) enables sentinel coverage / answer_hit@5.
    `retrieved_kinds` (each chunk's `code`/`md` tag, aligned to `ranked`) reports the
    code/doc mix actually retrieved — the retriever never filters on it."""
    gold = _harness_gold()
    base = gold.score_query(ranked, qrels_q, list(ks))
    primaries = {d for d, g in qrels_q.items() if g >= 2}
    # primary-only MRR + recall@20 (the headline-protected slice)
    pmrr = 0.0
    for i, d in enumerate(ranked):
        if d in primaries:
            pmrr = 1.0 / (i + 1)
            break
    p_hits20 = sum(1 for d in ranked[:20] if d in primaries)
    out = {
        "ret.recall@5": base.get("recall@5", 0.0),
        "ret.recall@20": base.get("recall@20", 0.0),
        "ret.recall@100": base.get("recall@100", 0.0),
        "ret.precision@5": base.get("precision@5", 0.0),
        "ret.precision@10": base.get("precision@10", 0.0),
        "ret.ndcg@10": base.get("ndcg@10", 0.0),
        "ret.mrr": base.get("mrr", 0.0),
        "ret.primary_mrr": pmrr,
        "ret.primary_recall@20": (p_hits20 / len(primaries)) if primaries else 0.0,
        "ret.n_ranked": len(ranked),
    }
    if retrieved_texts is not None and sentinels:
        joined = "\n".join(retrieved_texts)
        covered = sum(1 for s in sentinels if s in joined)
        out["ret.sentinel_cov"] = covered / len(sentinels)
        # answer_hit@5: any sentinel present in the top-5 chunk texts
        top5 = "\n".join(retrieved_texts[:5])
        out["ret.answer_hit@5"] = 1.0 if any(s in top5 for s in sentinels) else 0.0
    if retrieved_kinds:
        nk = len(retrieved_kinds)
        out["ret.frac_code_retrieved"] = sum(1 for k in retrieved_kinds if k == "code") / nk
        out["ret.frac_md_retrieved"] = sum(1 for k in retrieved_kinds if k == "md") / nk
    return out


class TsvWriter:
    """Append one row per (query × arm) with the fixed ROW_FIELDS header."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        new = not self.path.exists()
        self.fh = self.path.open("a", encoding="utf-8")
        if new:
            self.fh.write("\t".join(ROW_FIELDS) + "\n")

    def row(self, **cols) -> None:
        unknown = set(cols) - set(ROW_FIELDS)
        if unknown:
            raise KeyError(f"unknown metric columns: {sorted(unknown)}")
        self.fh.write("\t".join(str(cols.get(f, "")) for f in ROW_FIELDS) + "\n")

    def close(self) -> None:
        self.fh.close()


def cmd_schema(args) -> int:
    print(f"{len(ROW_FIELDS)} columns across channels (one row per query × arm):\n")
    for name, fields in [("slice", SLICE_FIELDS), ("arm", ARM_FIELDS), ("ret", RET_FIELDS),
                         ("pack", PACK_FIELDS), ("gen", GEN_FIELDS), ("ver", VER_FIELDS),
                         ("eff", EFF_FIELDS), ("route", ROUTE_FIELDS)]:
        print(f"  {name:6s} ({len(fields)}): {', '.join(f.split('.', 1)[1] for f in fields)}")
    print("\npack./gen./ver.citation_support are filled by Wave 7 (answer generation); "
          "retrieval-only baselines leave them blank.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("schema", help="print the TSV column schema by channel").set_defaults(func=cmd_schema)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
