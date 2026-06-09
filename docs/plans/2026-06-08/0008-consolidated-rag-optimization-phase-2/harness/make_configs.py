#!/usr/bin/env python3
"""make_configs.py — emit the Wave-0 baseline config arms (consolidated plan
§"Baseline and Benchmark Harness"). Each arm is the shipped rag-config plus a few
harness fields, written self-contained into ../configs/ so the Wave-0 runner (and
rag_lib.load_config) can load any one directly. Re-run to regenerate after the
shipped config changes. These DEFINE the baselines; running them is Wave 0.

Harness fields added on top of the shipped rag-config schema:
  arm             — the benchmark arm name (matches the filename / report scope)
  retrieval_mode  — hybrid | dense-only | bm25-only | closed-book | wrong-context | manual-rg
  index_mode      — combined: ONE rich per-repo index over code AND docs together. The
                    retriever is type-blind; code-vs-doc is a metric slice, never a
                    corpus partition. (The only Wave-0 mode — no per-type indexes.)
  contextual_header — bool: prepend the deterministic "[repo] path :: heading (lang)"
                      header to contextualized_text before embedding (LLM-free,
                      Wave-2 item 1). False for every Wave-0 baseline.
The Wave-0 runner honors retrieval_mode (single-arm / control / manual) and
index_mode; the shipped query.py only implements the `hybrid` path, so single-arm
and control modes are the runner's responsibility (documented in the README).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


def _skill_scripts_dir() -> Path:
    for anc in Path(__file__).resolve().parents:
        cand = anc / ".agents/skills/setting-up-rag/scripts"
        if (cand / "rag-config.json").is_file():
            return cand
    raise RuntimeError("setting-up-rag scripts dir not found")


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


# arm -> overrides on top of the shipped config (+ the harness fields)
ARMS: dict[str, dict] = {
    "plain-current": {
        "_doc": "Shipped setting-up-rag defaults: hybrid bge-small + bm25, RRF, MiniLM rerank, top_k=20. The reference every experiment must beat.",
        "retrieval_mode": "hybrid", "index_mode": "combined", "contextual_header": False,
    },
    "plain-current-no-rerank": {
        "_doc": "Isolates the cross-encoder reranker's lift.",
        "retrieval_mode": "hybrid", "rerank": {"enabled": False},
    },
    "bm25-only": {
        "_doc": "Sparse arm alone (no dense, no rerank) — lexical/identifier baseline.",
        "retrieval_mode": "bm25-only", "rerank": {"enabled": False},
    },
    "dense-only": {
        "_doc": "Dense arm alone (no sparse, no rerank) — semantic baseline.",
        "retrieval_mode": "dense-only", "rerank": {"enabled": False},
    },
    "closed-book": {
        "_doc": "No retrieval; empty context. Detects parametric answer leakage (answer-side control).",
        "retrieval_mode": "closed-book", "rerank": {"enabled": False},
    },
    "wrong-context": {
        "_doc": "Distractor: each query gets ANOTHER query's context (deterministic rotation). Detects low retrieval dependence.",
        "retrieval_mode": "wrong-context",
    },
    "manual-simple": {
        "_doc": "The retrieving-context manual floor: ripgrep over the repo, no index. Comparison point for whether RAG earns its cost.",
        "retrieval_mode": "manual-rg", "rerank": {"enabled": False},
    },
}

# prefetch / rerank-top_n / final top_k sweep — a grid the runner expands, NOT a
# single config. Tuned on dev before any new model is introduced (plan Wave-0 item).
SWEEP = {
    "arm": "prefetch-topn-sweep",
    "_doc": "Grid over prefetch, rerank.top_n, top_k on the dev split. Note Qdrant RRF k default is 2 (not 60) — pass/tune explicitly (Wave-1).",
    "base_arm": "plain-current",
    "grid": {
        "hybrid.prefetch": [30, 60, 120, 200],
        "rerank.top_n": [20, 50, 100],
        "top_k": [10, 20, 50],
        "hybrid.rrf_k": [2, 10, 60],
    },
}


def main() -> int:
    base = json.loads((_skill_scripts_dir() / "rag-config.json").read_text())
    out_dir = Path(__file__).resolve().parent.parent / "configs"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for arm, over in ARMS.items():
        cfg = deep_merge(base, {k: v for k, v in over.items() if k != "_doc"})
        cfg["rag_config_id"] = arm
        cfg["arm"] = arm
        cfg["_doc"] = over.get("_doc", "")
        cfg.setdefault("index_mode", "combined")
        cfg.setdefault("contextual_header", False)
        cfg["collection"] = f"phase3_{arm.replace('-', '_')}"
        (out_dir / f"{arm}.json").write_text(json.dumps(cfg, indent=2) + "\n")
        written.append(f"{arm}.json")
    (out_dir / "prefetch-topn-sweep.json").write_text(json.dumps(SWEEP, indent=2) + "\n")
    written.append("prefetch-topn-sweep.json")
    print(f"make_configs: wrote {len(written)} arm configs to {out_dir}:")
    for w in written:
        print(f"  {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
