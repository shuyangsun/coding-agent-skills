#!/usr/bin/env python3
"""wave4_latechunk.py — LLM-free contextual embedding via *late chunking* (Wave 4, steps 2-3).

Wave 4 of ``0008-consolidated-rag-optimization-phase-2.md`` asks two things the LLM
contextual-retrieval arm (``wave4_context.py`` / benchmark 0014) does NOT answer:
  * step 2 "LLM-free contextual embedding" — can we situate a chunk in its document
    *without* a generative LLM pass?
  * step 3 "late chunking" — embed the whole document once with a long-context encoder,
    then mean-pool each chunk's token embeddings, so every chunk vector carries
    document context (Günther et al., Jina "late chunking").

This module is the GPU GENERATION half (mirrors wave4_context's split): it precomputes
per-chunk dense vectors with **bge-m3** (BAAI, MIT, 8192-ctx XLM-RoBERTa; staged on the
NAS) in two modes and caches them, plus the 207 gold query vectors. The benchmark runner
and indexer then read these caches — so the runner stays torch-free (the portable
FastEmbed baseline arms are byte-identical) and ONLY the dense doc/query vectors swap:

  * ``naive`` — each chunk embedded ALONE (mean-pool its own tokens). The control: a
    bge-m3 embedder swap with NO document context.
  * ``late``  — the whole document embedded in 8192-token windows, then each chunk
    mean-pooled from its tokens' contextual hidden states. The treatment: document
    context with no LLM.

naive→late is the clean single-variable A/B (same model, dim, chunker, sparse, header):
the delta is the late-chunking *method*. Cross-referencing bge-small (portable best) and
``w4-llm-all`` (LLM contextual, campaign best) positions it absolutely and answers "does
LLM-free late chunking recover the LLM contextual win?".

Pooling is mean-pool over a chunk's tokens for BOTH documents and queries (late chunking
needs per-token states; using mean-pool consistently on the query keeps the spaces
comparable — the absolute MTEB number may differ from bge-m3's official CLS dense, but
the naive/late A/B is internally valid). Vectors are L2-normalized (Qdrant cosine).

Cache (kept OUT of the repo — large, derived):
    $LATECHUNK_CACHE/<model_slug>-<mode>/<repo>.npz   (keys=byte-span ids, vecs=fp16 N×1024)
    $LATECHUNK_CACHE/<model_slug>-query/queries.npz   (keys=query sha1, vecs=fp16 Nq×1024)
default $LATECHUNK_CACHE=~/.cache/rag-skill/wave4-latechunk

GENERATION (campaign venv, GPU — torch+transformers):
    CUDA_VISIBLE_DEVICES=1 python wave4_latechunk.py precompute --repo all --mode naive,late
    CUDA_VISIBLE_DEVICES=1 python wave4_latechunk.py precompute-queries
The READ path (load_doc_cache / lookup_query) is numpy-only (no torch) for the runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

_HARNESS = Path(__file__).resolve().parent
sys.path.insert(0, str(_HARNESS))
import corpus_manifest as M  # noqa: E402
import enriched_index as E  # noqa: E402
import gold_loader as G  # noqa: E402

DEFAULT_MODEL_DIR = os.environ.get("BGE_M3_DIR", "/mnt/nas/home/ml/model/embedding/bge-m3")
MODEL_TAG = "bge-m3"  # cache + index identity tag
DENSE_DIM = 1024
WINDOW_TOKENS = 8192  # bge-m3 max sequence (incl. CLS/SEP)
NAIVE_MAX_TOKENS = 1024  # a single chunk never needs more


def cache_root() -> Path:
    return Path(os.environ.get(
        "LATECHUNK_CACHE",
        str(Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
            / "rag-skill" / "wave4-latechunk"))).expanduser()


def _doc_cache_path(model_tag: str, mode: str, repo: str) -> Path:
    return cache_root() / f"{model_tag}-{mode}" / f"{repo}.npz"


def _query_cache_path(model_tag: str) -> Path:
    return cache_root() / f"{model_tag}-query" / "queries.npz"


def chunk_key(path: str, start_byte: int, end_byte: int) -> str:
    return f"{path}\t{start_byte}\t{end_byte}"


def query_key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


# --- read path (numpy only; used by the indexer + runner, no torch) ----------
def load_doc_cache(model_tag: str, mode: str, repo: str) -> dict[str, np.ndarray]:
    p = _doc_cache_path(model_tag, mode, repo)
    if not p.is_file():
        raise FileNotFoundError(f"late-chunk doc cache missing: {p} (run `precompute`)")
    d = np.load(p, allow_pickle=True)
    return {str(k): v for k, v in zip(d["keys"].tolist(), d["vecs"].astype(np.float32))}


_QCACHE: dict[str, dict[str, np.ndarray]] = {}


def lookup_query(text: str, model_tag: str = MODEL_TAG) -> list[float]:
    if model_tag not in _QCACHE:
        p = _query_cache_path(model_tag)
        if not p.is_file():
            raise FileNotFoundError(f"late-chunk query cache missing: {p} (run `precompute-queries`)")
        d = np.load(p, allow_pickle=True)
        _QCACHE[model_tag] = {str(k): v for k, v in zip(d["keys"].tolist(), d["vecs"].astype(np.float32))}
    qc = _QCACHE[model_tag]
    k = query_key(text)
    if k not in qc:
        raise KeyError(f"query not in late-chunk cache (regenerate): {text[:80]!r}")
    return qc[k].tolist()


# --- GPU generation (campaign venv only) -------------------------------------
def _load_model(model_dir: str):
    import torch
    from transformers import AutoModel, AutoTokenizer

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModel.from_pretrained(model_dir, dtype=torch.float16).to(dev).eval()
    return tok, model, dev


def _normalize_rows(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    n[n == 0] = 1.0
    return v / n


def embed_naive(tok, model, dev, texts: list[str], batch: int = 48) -> np.ndarray:
    """Each text embedded alone, mean-pooled over its tokens (the no-context control)."""
    import torch

    out = []
    for i in range(0, len(texts), batch):
        chunk = [t if t.strip() else " " for t in texts[i:i + batch]]
        enc = tok(chunk, return_tensors="pt", padding=True, truncation=True,
                  max_length=NAIVE_MAX_TOKENS).to(dev)
        with torch.no_grad():
            hs = model(**enc).last_hidden_state  # [B,T,H]
        m = enc["attention_mask"].unsqueeze(-1)
        v = (hs * m).sum(1) / m.sum(1).clamp(min=1)
        out.append(v.float().cpu().numpy())
    return _normalize_rows(np.concatenate(out, 0)) if out else np.zeros((0, DENSE_DIM), np.float32)


def embed_doc_late(tok, model, dev, doc_text: str, spans: list[tuple[int, int]]) -> np.ndarray:
    """Embed the whole doc in non-overlapping 8192-token windows, then mean-pool each
    chunk's tokens from their *contextual* hidden states. Each token belongs to exactly
    one window (CLS/SEP added per window); a chunk straddling a window boundary pools
    across both — rare (chunks are <=~600 tokens, windows ~8190)."""
    import torch

    enc = tok(doc_text, return_offsets_mapping=True, add_special_tokens=False, truncation=False)
    ids = enc["input_ids"]
    offs = enc["offset_mapping"]
    T = len(ids)
    H = np.zeros((max(T, 1), DENSE_DIM), dtype=np.float32)
    cls, sep = tok.cls_token_id, tok.sep_token_id
    step = WINDOW_TOKENS - 2  # leave room for CLS/SEP
    ws = 0
    while ws < T:
        we = min(ws + step, T)
        win = [cls] + ids[ws:we] + [sep]
        input_ids = torch.tensor([win], device=dev)
        attn = torch.ones_like(input_ids)
        with torch.no_grad():
            hs = model(input_ids=input_ids, attention_mask=attn).last_hidden_state[0]
        H[ws:we] = hs[1:1 + (we - ws)].float().cpu().numpy()
        ws = we
    vecs = np.zeros((len(spans), DENSE_DIM), dtype=np.float32)
    for j, (s, e) in enumerate(spans):
        idx = [i for i, (a, b) in enumerate(offs) if b > a and a < e and b > s]
        if not idx and T:
            mid = (s + e) // 2
            idx = [min(range(T), key=lambda i: abs((offs[i][0] + offs[i][1]) // 2 - mid))]
        if idx:
            vecs[j] = H[idx].mean(0)
    return _normalize_rows(vecs)


def _chunks_for_repo(repo: str, cfg: dict):
    """(path, kind, spans[list[(sb,eb)]], raw_texts[list]) per doc — chunker-identical to the indexer."""
    corpus = M.load_repo_corpus(M.REPOS[repo], kinds=("md", "code"))
    for path in sorted(corpus):
        payload = corpus[path]
        chunks = E.span_chunks(payload["text"], payload["kind"], cfg)
        spans = [(c.start_byte, c.end_byte) for c in chunks]
        yield path, payload["kind"], payload["text"], spans, [c.raw_text for c in chunks]


def precompute_repo(repo: str, cfg: dict, modes: list[str], tok, model, dev) -> dict:
    naive_keys, naive_vecs = [], []
    late_keys, late_vecs = [], []
    n_docs = 0
    for path, _kind, doc_text, spans, raw_texts in _chunks_for_repo(repo, cfg):
        n_docs += 1
        keys = [chunk_key(path, sb, eb) for sb, eb in spans]
        if "naive" in modes:
            v = embed_naive(tok, model, dev, raw_texts)
            naive_keys.extend(keys)
            naive_vecs.append(v)
        if "late" in modes:
            v = embed_doc_late(tok, model, dev, doc_text, spans)
            late_keys.extend(keys)
            late_vecs.append(v)
    res = {"repo": repo, "docs": n_docs}
    if "naive" in modes:
        _save(_doc_cache_path(MODEL_TAG, "naive", repo), naive_keys, np.concatenate(naive_vecs, 0))
        res["naive"] = len(naive_keys)
    if "late" in modes:
        _save(_doc_cache_path(MODEL_TAG, "late", repo), late_keys, np.concatenate(late_vecs, 0))
        res["late"] = len(late_keys)
    return res


def _save(path: Path, keys: list[str], vecs: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, keys=np.array(keys, dtype=object), vecs=vecs.astype(np.float16))


def cmd_precompute(args) -> int:
    cfg = E._load_cfg(args.config)
    modes = args.mode.split(",")
    repos = list(M.REPOS) if args.repo == "all" else args.repo.split(",")
    tok, model, dev = _load_model(args.model_dir)
    print(f"late-chunk precompute: model={args.model_dir} dev={dev} modes={modes}")
    t0 = time.time()
    for repo in repos:
        rt = time.time()
        res = precompute_repo(repo, cfg, modes, tok, model, dev)
        print(f"  {repo:24s} docs={res['docs']:4d} "
              + " ".join(f"{m}={res.get(m,0)}" for m in modes)
              + f"  {time.time()-rt:.0f}s")
    print(f"late-chunk precompute done in {time.time()-t0:.0f}s -> {cache_root()}")
    return 0


def cmd_precompute_queries(args) -> int:
    cfg = E._load_cfg(args.config)
    qs = G.load_questions()
    texts = [q.question for q in qs]
    tok, model, dev = _load_model(args.model_dir)
    t0 = time.time()
    vecs = embed_naive(tok, model, dev, texts)  # queries: plain mean-pool (no late chunking)
    keys = [query_key(t) for t in texts]
    # dedupe identical query strings (keep one vec each)
    seen: dict[str, np.ndarray] = {}
    for k, v in zip(keys, vecs):
        seen.setdefault(k, v)
    _save(_query_cache_path(MODEL_TAG), list(seen), np.stack(list(seen.values())))
    print(f"late-chunk query cache: {len(seen)} unique / {len(texts)} questions "
          f"in {time.time()-t0:.0f}s -> {_query_cache_path(MODEL_TAG)}")
    return 0


def cmd_stats(args) -> int:
    for mode in ("naive", "late"):
        tot = 0
        for repo in M.REPOS:
            p = _doc_cache_path(MODEL_TAG, mode, repo)
            if p.is_file():
                d = np.load(p, allow_pickle=True)
                tot += len(d["keys"])
        print(f"  {mode:6s} cached vecs: {tot}")
    qp = _query_cache_path(MODEL_TAG)
    if qp.is_file():
        print(f"  query  cached vecs: {len(np.load(qp, allow_pickle=True)['keys'])}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("precompute", help="GPU: cache naive/late chunk vectors per repo")
    p.add_argument("--repo", default="all")
    p.add_argument("--mode", default="naive,late")
    p.add_argument("--model-dir", default=DEFAULT_MODEL_DIR)
    p.add_argument("--config", default=None)
    p.set_defaults(func=cmd_precompute)
    pq = sub.add_parser("precompute-queries", help="GPU: cache the 207 gold query vectors")
    pq.add_argument("--model-dir", default=DEFAULT_MODEL_DIR)
    pq.add_argument("--config", default=None)
    pq.set_defaults(func=cmd_precompute_queries)
    ps = sub.add_parser("stats", help="numpy-only: cache coverage")
    ps.set_defaults(func=cmd_stats)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
