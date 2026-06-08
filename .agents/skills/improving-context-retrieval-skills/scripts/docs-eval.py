#!/usr/bin/env python3
"""docs-eval.py — Phase-0 thin in-process retrieval eval (no services, no LLM).

Given a corpus and a `rag-config.json` (the `setting-up-rag` skill's output), it chunks +
indexes the corpus with **BM25 (sparse) + an in-memory hashed-embedding vector
index (dense)**, runs the gold queries, and writes a ranked run plus per-stage
timings. The scorer (`check-retrieval.py`, which imports `gold.py`) turns the run
into precision/recall/nDCG/MRR/retrieval_hit. This is enough to compute all four
factorial cells (corpus N|D × rag b|r) and the interaction without any external
dependency.

The floor (`--no-retrieval`): the absolute baseline is "no doc, no RAG". With
`--no-retrieval` the script builds **no index and runs no retrieval** — every
query returns an empty ranked list (so every IR metric scores 0). Paired with the
empty `Z` corpus (`mk-corpus.py`), this is the genuine floor that the four
treatment cells are lifts above; run it FIRST. `--config` is optional in this mode
since no pipeline runs.

Phase-0 honesty: the dense vectors are a **deterministic hashed lexical
embedding**, not a learned semantic model — a placeholder so the chunking, fusion,
and rerank knobs can be exercised reproducibly. Real semantic embeddings
(Ollama/bge) arrive in Phase 1 behind the same rag-config schema; the BM25 +
chunking axes carry the meaningful Phase-0 signal. Absolute numbers are therefore
host- and placeholder-relative; the *deltas* between cells are what travel.

rag-config.json (the knobs the `setting-up-rag` skill owns):
  {
    "rag_config_id": "baseline-b",
    "chunker":   {"strategy": "fixed|heading|recursive", "size": 512, "overlap": 64},
    "embedding": {"model": "hash", "dim": 256, "idf_weight": true},
    "hybrid":    {"sparse": true, "dense": true, "fusion": "rrf|weighted",
                  "rrf_k": 60, "dense_weight": 0.5},
    "rerank":    {"enabled": false, "top_n": 50},
    "top_k": 20, "prefetch": 50, "provider": "local-inproc"
  }

Content-type axis: `--corpus-kind code --domain code` indexes the inception/
codebase and runs the code gold queries, so code retrieval is measured separately
from natural-language docs (`--corpus-kind md --domain nl`, the default). Only the
loader + which queries run change; the chunk/index/fuse/rerank path is identical,
so code vs nl numbers are comparable.

Usage:
  docs-eval.py --corpus DIR --config rag-config.json --out RUNDIR [--split all]
  docs-eval.py --corpus DIR --no-retrieval --out RUNDIR        # the floor (no RAG)
  docs-eval.py --corpus inception/ --corpus-kind code --domain code --config CFG --out RUNDIR
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import zlib
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gold  # noqa: E402  (sibling module, the single source of truth)

BM25_K1 = 1.5
BM25_B = 0.75


# --- chunking ---------------------------------------------------------------
def _words(text: str) -> list[str]:
    return text.split()


def chunk_fixed(text: str, size: int, overlap: int) -> list[str]:
    """Fixed word-grid windows with overlap (size/overlap counted in words)."""
    words = _words(text)
    if not words:
        return []
    if len(words) <= size:
        return [" ".join(words)]
    step = max(1, size - overlap)
    return [" ".join(words[i : i + size]) for i in range(0, len(words), step) if words[i : i + size]]


def chunk_heading(text: str, size: int, overlap: int) -> list[str]:
    """Split on Markdown headings; over-long sections fall back to fixed windows."""
    sections: list[str] = []
    cur: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("#") and cur:
            sections.append("\n".join(cur))
            cur = [line]
        else:
            cur.append(line)
    if cur:
        sections.append("\n".join(cur))
    chunks: list[str] = []
    for sec in sections:
        if len(_words(sec)) > size:
            chunks.extend(chunk_fixed(sec, size, overlap))
        elif sec.strip():
            chunks.append(sec)
    return chunks or chunk_fixed(text, size, overlap)


def chunk_recursive(text: str, size: int, overlap: int) -> list[str]:
    """Paragraph-pack: greedily merge blank-line paragraphs up to `size` words."""
    paras = [p for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    n = 0
    for p in paras:
        pw = len(_words(p))
        if n + pw > size and buf:
            chunks.append("\n\n".join(buf))
            buf, n = [], 0
        buf.append(p)
        n += pw
    if buf:
        chunks.append("\n\n".join(buf))
    out: list[str] = []
    for c in chunks:
        out.extend(chunk_fixed(c, size, overlap) if len(_words(c)) > size else [c])
    return out or chunk_fixed(text, size, overlap)


CHUNKERS = {"fixed": chunk_fixed, "heading": chunk_heading, "recursive": chunk_recursive}


# --- indexing ---------------------------------------------------------------
class Index:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.chunk_text: list[str] = []
        self.chunk_doc: list[str] = []
        self.chunk_tokens: list[list[str]] = []
        self.df: Counter = Counter()
        self.idf: dict[str, float] = {}
        self.avg_len: float = 0.0
        self.dense: list[dict[int, float]] = []  # sparse dict per chunk (hashed dims)
        self.dim = int(cfg.get("embedding", {}).get("dim", 256))
        self.idf_weight = bool(cfg.get("embedding", {}).get("idf_weight", True))

    def build(self, docs: dict[str, str]) -> float:
        t0 = time.perf_counter()
        ch = self.cfg.get("chunker", {})
        strat = ch.get("strategy", "fixed")
        size = int(ch.get("size", 512))
        overlap = int(ch.get("overlap", 64))
        chunker = CHUNKERS.get(strat, chunk_fixed)
        for doc_id, text in docs.items():
            for c in chunker(text, size, overlap):
                toks = gold.tokens(c)
                if not toks:
                    continue
                self.chunk_text.append(c)
                self.chunk_doc.append(doc_id)
                self.chunk_tokens.append(toks)
        for toks in self.chunk_tokens:
            for t in set(toks):
                self.df[t] += 1
        n = max(1, len(self.chunk_tokens))
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in self.df.items()}
        self.avg_len = sum(len(t) for t in self.chunk_tokens) / n
        for toks in self.chunk_tokens:
            self.dense.append(self._embed(toks))
        return (time.perf_counter() - t0) * 1000.0

    def _embed(self, toks: list[str]) -> dict[int, float]:
        vec: dict[int, float] = defaultdict(float)
        for t, f in Counter(toks).items():
            w = f * (self.idf.get(t, 1.0) if self.idf_weight else 1.0)
            # stable hash (builtin hash() is per-process randomized for str)
            vec[zlib.crc32(t.encode()) % self.dim] += w
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {k: v / norm for k, v in vec.items()}

    def bm25(self, q_toks: list[str]) -> dict[int, float]:
        scores: dict[int, float] = defaultdict(float)
        for i, toks in enumerate(self.chunk_tokens):
            tf = Counter(toks)
            ln = len(toks)
            s = 0.0
            for qt in q_toks:
                f = tf.get(qt, 0)
                if not f:
                    continue
                idf = self.idf.get(qt, 0.0)
                s += idf * (f * (BM25_K1 + 1)) / (f + BM25_K1 * (1 - BM25_B + BM25_B * ln / self.avg_len))
            if s:
                scores[i] = s
        return scores

    def dense_scores(self, q_toks: list[str]) -> dict[int, float]:
        qv = self._embed(q_toks)
        scores: dict[int, float] = defaultdict(float)
        for i, cv in enumerate(self.dense):
            small, big = (qv, cv) if len(qv) < len(cv) else (cv, qv)
            s = sum(val * big.get(k, 0.0) for k, val in small.items())
            if s:
                scores[i] = s
        return scores


# --- fusion + retrieval -----------------------------------------------------
def _rank_map(scores: dict[int, float]) -> dict[int, int]:
    return {cid: r for r, (cid, _) in enumerate(sorted(scores.items(), key=lambda kv: -kv[1]))}


def fuse(sparse: dict[int, float], dense: dict[int, float], cfg: dict) -> dict[int, float]:
    hy = cfg.get("hybrid", {})
    use_sparse = hy.get("sparse", True)
    use_dense = hy.get("dense", True)
    if use_sparse and not use_dense:
        return sparse
    if use_dense and not use_sparse:
        return dense
    if hy.get("fusion", "rrf") == "rrf":
        k = int(hy.get("rrf_k", 60))
        sr, dr = _rank_map(sparse), _rank_map(dense)
        out: dict[int, float] = defaultdict(float)
        for cid, r in sr.items():
            out[cid] += 1.0 / (k + r)
        for cid, r in dr.items():
            out[cid] += 1.0 / (k + r)
        return out
    # weighted sum of min-max normalized scores
    w = float(hy.get("dense_weight", 0.5))

    def norm(d: dict[int, float]) -> dict[int, float]:
        if not d:
            return {}
        lo, hi = min(d.values()), max(d.values())
        rng = (hi - lo) or 1.0
        return {k: (v - lo) / rng for k, v in d.items()}

    sn, dn = norm(sparse), norm(dense)
    out = defaultdict(float)
    for cid, v in sn.items():
        out[cid] += (1 - w) * v
    for cid, v in dn.items():
        out[cid] += w * v
    return out


def rerank(cands: list[int], q_toks: list[str], idx: Index, cfg: dict) -> list[int]:
    """Placeholder cross-encoder: deterministic token-set Jaccard of chunk vs query.
    A stand-in for a real reranker so the on/off knob is exercisable."""
    qset = set(q_toks)

    def jac(cid: int) -> float:
        cset = set(idx.chunk_tokens[cid])
        return len(qset & cset) / len(qset | cset) if (qset | cset) else 0.0

    return sorted(cands, key=jac, reverse=True)


def retrieve(idx: Index, query: str, cfg: dict) -> tuple[list[str], float]:
    t0 = time.perf_counter()
    q_toks = gold.tokens(query)
    sparse = idx.bm25(q_toks) if cfg.get("hybrid", {}).get("sparse", True) else {}
    dense = idx.dense_scores(q_toks) if cfg.get("hybrid", {}).get("dense", True) else {}
    fused = fuse(sparse, dense, cfg)
    prefetch = int(cfg.get("prefetch", 50))
    cand = [cid for cid, _ in sorted(fused.items(), key=lambda kv: -kv[1])[:prefetch]]
    if cfg.get("rerank", {}).get("enabled", False):
        cand = rerank(cand[: int(cfg["rerank"].get("top_n", prefetch))], q_toks, idx, cfg)
    # aggregate chunk -> doc by best rank position
    seen: dict[str, int] = {}
    for pos, cid in enumerate(cand):
        d = idx.chunk_doc[cid]
        if d not in seen:
            seen[d] = pos
    ranked = [d for d, _ in sorted(seen.items(), key=lambda kv: kv[1])]
    top_k = int(cfg.get("top_k", 20))
    return ranked[:top_k], (time.perf_counter() - t0) * 1000.0


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    i = min(len(s) - 1, int(round(p / 100.0 * (len(s) - 1))))
    return s[i]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus")
    ap.add_argument("--config", help="rag-config.json (omit with --no-retrieval)")
    ap.add_argument("--out", required=True, help="output run dir")
    ap.add_argument("--split", choices=["dev", "held-out", "all"], default="all")
    ap.add_argument("--corpus-tag", default="GOLD", help="N|D|Z|code|GOLD label for the row")
    ap.add_argument(
        "--corpus-kind",
        choices=["md", "code"],
        default="md",
        help="md = markdown docs (nl); code = the inception/ codebase",
    )
    ap.add_argument(
        "--domain",
        choices=["nl", "code"],
        default="nl",
        help="content type to evaluate; selects which gold facts (queries) run",
    )
    ap.add_argument(
        "--no-retrieval",
        action="store_true",
        help="the floor: build no index, run no retrieval; every query returns "
        "an empty ranked list (all IR metrics score 0). 'no doc, no RAG'.",
    )
    args = ap.parse_args(argv)

    # Guard: domain and corpus-kind must agree, else a code run could be scored
    # against the nl corpus (or vice-versa) and mis-grade via cross-domain
    # sentinel overlap (e.g. a transcript that quotes code identifiers).
    if (args.domain == "code") != (args.corpus_kind == "code"):
        ap.error("--domain and --corpus-kind must agree: use "
                 "'--domain code --corpus-kind code' or '--domain nl --corpus-kind md'")

    if args.corpus_kind == "code":
        corpus_root = gold.find_code_corpus_root(args.corpus)
        if corpus_root is None:
            ap.error("--corpus-kind code: inception/ corpus not found; pass --corpus DIR")
    else:
        corpus_root = gold.find_corpus_root(args.corpus)
    docs = gold.load_corpus(corpus_root, kind=args.corpus_kind)
    facts = [
        f for f in gold.FACTS
        if args.split in ("all", gold.split_of(f.id)) and f.domain == args.domain
    ]

    if args.no_retrieval:
        # Floor: no index, no retrieval — the absolute "no doc, no RAG" baseline.
        cfg = {"rag_config_id": "none"}
        index_ms = 0.0
        n_chunks = 0
        mean_chunk_words = 0.0
        lat: list[float] = []
        runs = [{"query_id": f.id, "ranked": [], "retrieval_ms": 0.0} for f in facts]
    else:
        if not args.config:
            ap.error("--config is required unless --no-retrieval is given")
        cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
        idx = Index(cfg)
        index_ms = idx.build(docs)
        n_chunks = len(idx.chunk_tokens)
        mean_chunk_words = round(sum(len(t) for t in idx.chunk_tokens) / max(1, n_chunks), 1)
        lat = []
        runs = []
        for fact in facts:
            ranked, ms = retrieve(idx, fact.query, cfg)
            lat.append(ms)
            runs.append({"query_id": fact.id, "ranked": ranked, "retrieval_ms": ms})

    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "run.jsonl").open("w", encoding="utf-8") as fh:
        for rec in runs:
            fh.write(json.dumps(rec) + "\n")

    timings = {
        "rag_config_id": cfg.get("rag_config_id", "unnamed"),
        "corpus_tag": args.corpus_tag,
        "domain": args.domain,
        "corpus_kind": args.corpus_kind,
        "no_retrieval": bool(args.no_retrieval),
        "split": args.split,
        "n_docs": len(docs),
        "n_chunks": n_chunks,
        "mean_chunk_words": mean_chunk_words,
        "index_ms": round(index_ms, 2),
        "retrieval_ms_p50": round(percentile(lat, 50), 3),
        "retrieval_ms_p95": round(percentile(lat, 95), 3),
        "n_queries": len(facts),
    }
    (out_dir / "timings.json").write_text(json.dumps(timings, indent=2) + "\n")
    print(json.dumps(timings, indent=2))
    print(f"docs-eval: wrote {out_dir/'run.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
