#!/usr/bin/env python3
"""run_benchmark.py — the Phase-3 RAG benchmark runner (Wave 0 onward).

This is the runner the harness README calls the "Wave-0 runner contract". The
pre-work harness supplies data + indexing + scoring + controls; this script wires
them into a measurement loop and is reused for every later wave (it takes arbitrary
arm configs, not just the Wave-0 set).

Per arm config it:
  1. resolves an INDEX IDENTITY from (dense_model, sparse_model, chunker, header) so
     arms that share a representation share ONE combined per-repo collection — the
     7 Wave-0 retrieval arms reuse a single base index; only a model/chunker/header
     change forces a re-index (keep/revert discipline);
  2. retrieves per query in the arm's `retrieval_mode`
     (hybrid | dense-only | bm25-only | closed-book | wrong-context | manual-rg);
  3. collapses retrieved CHUNKS to a file-level ranked list (qrels are file-level),
     scores it with metrics.retrieval_metrics (the single gold.py IR core) against
     primary-only graded qrels, and measures sentinel coverage over the REAL packed
     top_k chunk context (answer-string presence, immune to short-sentinel file
     inflation), the retrieved code/doc mix, and per-query synthesis-doc
     contamination;
  4. emits one metrics.TsvWriter row per (query × arm) and a sliced summary.json
     (total AND by domain/repo/category/difficulty/split/multiplicity), plus index
     time, query latency, and packed context-token cost.

Retrieval task is ONE combined code+docs corpus per repo; `domain` is a reporting
slice only (README "Code and docs are one retrieval task"). Needs the skill venv
(FastEmbed + Qdrant): run with ~/.cache/rag-skill/venv/bin/python. Points at the
dedicated Phase-3 Qdrant ($QDRANT_URL, default http://localhost:6343) so it never
touches the unrelated face-embed Qdrant on :6333.
"""
from __future__ import annotations

import argparse
import collections
import copy
import functools
import hashlib
import itertools
import json
import os
import re
import sys
import time
from pathlib import Path

_HARNESS = Path(__file__).resolve().parent
sys.path.insert(0, str(_HARNESS))
import corpus_manifest as M  # noqa: E402
import gold_loader as G  # noqa: E402
import metrics as MET  # noqa: E402
import contamination as C  # noqa: E402
import enriched_index as E  # noqa: E402
import wave5_graph as W5  # noqa: E402
import wave6_query as W6  # noqa: E402

# default to the dedicated, isolated Phase-3 Qdrant (NOT the face-embed :6333)
os.environ.setdefault("QDRANT_URL", "http://localhost:6343")


def _skill_scripts_dir() -> Path:
    for anc in _HARNESS.parents:
        cand = anc / ".agents/skills/setting-up-rag/scripts"
        if (cand / "rag_lib.py").is_file():
            return cand
    raise RuntimeError("could not locate setting-up-rag/scripts")


sys.path.insert(0, str(_skill_scripts_dir()))
import rag_lib as R  # noqa: E402

KS = (5, 10, 20, 100)
DEFAULT_DEPTH = 200


# --- index identity (arms that share a representation share a collection) -----
def index_key(cfg: dict) -> str:
    emb = cfg["embedding"]
    ch = cfg.get("chunker", {})
    cl = cfg.get("contextual_llm", {})
    sig = {
        "dense": emb["dense_model"], "sparse": emb["sparse_model"],
        "dim": emb.get("dense_dim"), "dist": emb.get("distance", "cosine"),
        "chunker": {k: ch.get(k) for k in ("size", "overlap", "min_words",
                                           "code_size", "code_overlap", "strategy")},
        "header": bool(cfg.get("contextual_header", False)),
    }
    # Wave-4: LLM situating context changes the embedded text -> new index. Added
    # ONLY when enabled, so non-LLM arms keep their pre-Wave-4 key and reuse indices.
    if cl.get("enabled"):
        sig["llm_ctx"] = {"model": cl.get("model"),
                          "apply": sorted(cl.get("apply_to", ["md", "code"])),
                          "pv": cl.get("prompt_version", "v1")}
    # Wave-4 late chunking: precomputed dense source (naive vs late pooling) is part of
    # the index identity so the two modes never share a collection. Added only when set.
    ds = emb.get("dense_source")
    if ds:
        sig["dense_source"] = {"kind": ds.get("kind"), "mode": ds.get("mode"),
                               "model": ds.get("model")}
    # Wave-4 Doc2Query: lexical expansion changes the BM25 (or both) field -> new index.
    dq = cfg.get("doc2query", {})
    if dq.get("enabled"):
        sig["d2q"] = {"model": dq.get("model"), "field": dq.get("field", "sparse"),
                      "apply": sorted(dq.get("apply_to", ["md", "code"])),
                      "n": dq.get("n"), "pv": dq.get("prompt_version", "d2q-v1")}
    # Wave-4 session metadata: deterministic transcript capsule changes the embedded text.
    sm = cfg.get("session_meta", {})
    if sm.get("enabled"):
        sig["sess"] = {"pv": sm.get("prompt_version", "sess-v1")}
    return hashlib.sha256(json.dumps(sig, sort_keys=True).encode()).hexdigest()[:10]


@functools.lru_cache(maxsize=None)
def corpus_sig(repo: str) -> str:
    """6-hex signature of a repo's indexable FILE LIST (sorted relpaths). Folded into
    the collection name so a corpus-membership change (e.g. the .gitignore fix that
    dropped alpha-zero's artifacts/) yields a new collection and auto-reindexes
    instead of silently reusing a stale one — index_key only hashes model/chunker."""
    rels = sorted(rel for rel, _k, _l in M.iter_repo_files(M.REPOS[repo]))
    return hashlib.sha256("\n".join(rels).encode()).hexdigest()[:6]


def collection_name(repo: str, key: str) -> str:
    return f"phase3_{repo.replace('-', '_')}_{key}_{corpus_sig(repo)}"


def ensure_index(repo: str, cfg: dict, key: str, reindex: bool) -> tuple[str, float]:
    """Build (or reuse) the combined code+docs collection for (repo, index_key).
    Returns (collection_name, index_ms) — index_ms is 0.0 when an existing
    collection is reused (the name encodes the schema, so reuse is safe)."""
    coll = collection_name(repo, key)
    client, _where = R.get_client()
    if client.collection_exists(coll) and not reindex:
        return coll, 0.0
    t0 = time.time()
    E.index_repo(repo, coll, cfg, kinds=("md", "code"),
                 header=bool(cfg.get("contextual_header", False)), force_local=False)
    return coll, (time.time() - t0) * 1000.0


# --- retrieval ----------------------------------------------------------------
def _search_params(cfg: dict):
    """Optional Qdrant HNSW search knobs (Wave 1): {"exact": true} for brute-force
    (removes ANN approximation as a recall-loss source at this small scale) or
    {"hnsw_ef": N} for a wider beam. None => Qdrant defaults (Wave-0 behaviour)."""
    from qdrant_client import models

    s = cfg.get("hybrid", {}).get("search")
    if not s:
        return None
    if s.get("exact"):
        return models.SearchParams(exact=True)
    if s.get("hnsw_ef"):
        return models.SearchParams(hnsw_ef=int(s["hnsw_ef"]))
    return None


def weighted_rrf(arm_hits: list[tuple[str, list]], weights: dict, k: int) -> list:
    """In-process weighted Reciprocal Rank Fusion over per-arm chunk lists, keyed by
    point id. score(d) = Σ_arm w_arm / (k + rank_arm(d)) (rank 1-based). Subsumes plain
    RRF (weights=1) and lets Wave 1 tune k (Qdrant's server RRF hard-codes k=2 — the
    plan's note) and per-cohort weights (up-weight sparse for code, dense for prose)."""
    score: dict = {}
    point: dict = {}
    for using, hits in arm_hits:
        w = float(weights.get(using, 1.0))
        for rank, h in enumerate(hits, start=1):
            score[h.id] = score.get(h.id, 0.0) + w / (k + rank)
            point[h.id] = h
    order = sorted(score, key=lambda i: score[i], reverse=True)
    return [point[i] for i in order]


_QWEN3_RR_PREFIX = ('<|im_start|>system\nJudge whether the Document meets the requirements '
                    'based on the Query and the Instruct provided. Note that the answer can '
                    'only be "yes" or "no".<|im_end|>\n<|im_start|>user\n')
_QWEN3_RR_SUFFIX = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
_QWEN3_RR_TASK = ('Given a search query over a software repository, retrieve code and '
                  'documentation passages that answer the query')


def infinity_rerank(query: str, texts: list[str], endpoint: str, model: str,
                    template: str | None = None) -> list[float]:
    """Rerank via a /rerank endpoint (Infinity, or vLLM's Jina-compatible route).
    Returns scores aligned to `texts`. Campaign-only (network LLM); the portable
    default uses the in-process FastEmbed path. `template="qwen3"` wraps query and
    documents in the official Qwen3-Reranker instruction template (decoder-based
    reranker scored on the yes-token — without this plumbing its scores are
    meaningless; plan Wave 3 step 5 / Wave 6 reranker A/B)."""
    import json as _json
    import urllib.request

    if template == "qwen3":
        query = f"{_QWEN3_RR_PREFIX}<Instruct>: {_QWEN3_RR_TASK}\n<Query>: {query}\n"
        texts = [f"<Document>: {t}{_QWEN3_RR_SUFFIX}" for t in texts]
    body = _json.dumps({"model": model, "query": query, "documents": texts,
                        "return_documents": False}).encode()
    req = urllib.request.Request(endpoint.rstrip("/") + "/rerank", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        res = _json.loads(r.read())
    scores = [0.0] * len(texts)
    for item in res.get("results", []):
        scores[item["index"]] = float(item.get("relevance_score", item.get("score", 0.0)))
    return scores


def apply_graph_overlay(client, coll, hits, dv, sv, cfg, graph, depth: int):
    """Wave-5 graph overlay (query-time; the index is untouched). Seeds = the top
    files of the fused candidate list; their deterministic graph neighbors
    (wave5_graph) get a lambda-scaled file-level boost added to every candidate
    chunk's rank-based base score. With ``fetch`` on, strong unseen neighbors get
    their best chunks pulled in via a doc_id-filtered hybrid query and merged
    BEHIND the originals (base rank > depth) so they surface on graph strength
    alone. Runs BEFORE the reranker — the plan's "expand candidates, then rerank"."""
    from qdrant_client import models

    ocfg = cfg.get("graph_overlay", {})
    n_seeds = int(ocfg.get("seeds", 10))
    lam = float(ocfg.get("lambda", 1.0))
    rrf_k = 60.0

    file_rank: dict[str, int] = {}
    for h in hits:
        did = h.payload.get("doc_id")
        if did and did not in file_rank:
            file_rank[did] = len(file_rank) + 1
    seeds = {f: 1.0 / (rrf_k + r) for f, r in file_rank.items() if r <= n_seeds}
    g = W5.expansion_scores(graph, seeds, ocfg)
    if not g:
        return hits

    merged = list(hits)
    if ocfg.get("fetch", True):
        unseen = sorted((f for f in g if f not in file_rank), key=lambda f: g[f], reverse=True)
        unseen = unseen[: int(ocfg.get("fetch_files", 30))]
        if unseen:
            flt = models.Filter(must=[models.FieldCondition(
                key="doc_id", match=models.MatchAny(any=unseen))])
            lim = min(100, 4 * len(unseen))
            dh = client.query_points(coll, query=dv, using="dense", limit=lim,
                                     with_payload=True, query_filter=flt).points
            sh = client.query_points(coll, query=R.to_sparse_vector(sv), using="sparse",
                                     limit=lim, with_payload=True, query_filter=flt).points
            fused = weighted_rrf([("dense", dh), ("sparse", sh)], {}, 60)
            have = {h.id for h in hits}
            per_file: collections.Counter = collections.Counter()
            for h in fused:
                did = h.payload.get("doc_id")
                if h.id in have or per_file[did] >= 2:  # at most 2 fetched chunks per file
                    continue
                per_file[did] += 1
                merged.append(h)

    def final_score(item: tuple[int, object]) -> float:
        i, h = item
        base = (1.0 / (rrf_k + i + 1) if i < len(hits)
                else 1.0 / (rrf_k + depth + (i - len(hits)) + 1))
        return base + lam * g.get(h.payload.get("doc_id"), 0.0)

    # head_lock freezes the top-H fused chunks (the precise head RRF already got
    # right — its rank-score curve is so flat that any useful boost otherwise
    # leapfrogs dozens of ranks); the graph re-sorts only the tail, where base
    # ranking is weak and the recall headroom lives.
    head_lock = int(ocfg.get("head_lock", 0))
    locked = merged[:head_lock]
    rest = sorted(list(enumerate(merged))[head_lock:], key=final_score, reverse=True)
    return locked + [h for _i, h in rest]


def _embed_query(query: str, cfg: dict):
    """(dense, sparse) for a query. Wave-4 late-chunk arms read the dense query vector
    from the bge-m3 cache (precomputed on GPU by wave4_latechunk) so the runner needs no
    torch; sparse/BM25 stays FastEmbed. All other arms use the shipped FastEmbed path."""
    emb = cfg["embedding"]
    ds = emb.get("dense_source")
    if ds and ds.get("kind") == "latechunk":
        import wave4_latechunk as LC
        dv = LC.lookup_query(query, ds.get("model", LC.MODEL_TAG))
        sv = list(R._sparse(emb["sparse_model"]).query_embed(query))[0]
        return dv, sv
    return R.embed_query(query, cfg)


def _server_fused(client, coll: str, dv, sv, cfg, limit: int, sp, flt=None):
    """One server-side RRF/DBSF hybrid call (the Wave-0 default path), optionally
    with a per-prefetch payload filter (Wave-6 self-query soft-filter arm)."""
    from qdrant_client import models

    hyb = cfg.get("hybrid", {})
    prefetch = int(hyb.get("prefetch", 60))
    fusion = models.Fusion.DBSF if hyb.get("fusion") == "dbsf" else models.Fusion.RRF
    return client.query_points(
        coll,
        prefetch=[
            models.Prefetch(query=dv, using="dense", limit=prefetch, params=sp, filter=flt),
            models.Prefetch(query=R.to_sparse_vector(sv), using="sparse", limit=prefetch,
                            params=sp, filter=flt),
        ],
        query=models.FusionQuery(fusion=fusion),
        limit=limit, with_payload=True,
    ).points


def _wave6_transform_hits(client, coll, query, cfg, depth, sp, qid, route):
    """Wave-6 query transforms (steps 3-4): decomposition / multi-query fuse the
    per-subquery server-fused candidate LISTS with weighted RRF (rank-based — never
    an additive score boost, the Wave-5 lesson); HyDE swaps only the DENSE query
    vector (sparse keeps the original query so exact identifiers stay protected).
    Returns None when the arm's gate doesn't trigger (caller falls back to plain)."""
    tcfg = cfg["query_transform"]
    kind = tcfg["kind"]
    feats = W6.query_features(query)
    if not W6.gate_triggers(tcfg.get("gate", "all"), feats):
        route.update(action=kind, triggered=0, n_sub=0)
        return None

    if kind == "hyde":
        passages = W6.lookup(tcfg["cache_model"], "hyde", qid)
        if not passages:
            route.update(action=kind, triggered=0, n_sub=0)
            return None
        hv, _ = R.embed_query(passages[0], cfg)   # dense from the hypothetical passage
        _, sv = _embed_query(query, cfg)          # sparse from the original query
        route.update(action=kind, triggered=1, n_sub=1)
        return _server_fused(client, coll, hv, sv, cfg, depth, sp)

    if kind == "decomp-det":
        subs = W6.decompose_det(query, int(tcfg.get("max_sub", 3)))
    else:  # decomp | multiquery via the LLM cache (generated offline, never live)
        cache_kind = "decomp" if kind == "decomp" else "multiquery"
        subs = W6.lookup(tcfg["cache_model"], cache_kind, qid)[: int(tcfg.get("max_sub", 4))]
    if not subs:
        route.update(action=kind, triggered=0, n_sub=0)
        return None

    dv, sv = _embed_query(query, cfg)
    lists = [("orig", _server_fused(client, coll, dv, sv, cfg, depth, sp))]
    for i, s in enumerate(subs):
        sdv, ssv = R.embed_query(s, cfg)
        lists.append((f"sub{i}", _server_fused(client, coll, sdv, ssv, cfg, depth, sp)))
    weights = {"orig": float(tcfg.get("w_orig", 1.0))}
    weights.update({f"sub{i}": float(tcfg.get("w_sub", 0.5)) for i in range(len(subs))})
    route.update(action=kind, triggered=1, n_sub=len(subs))
    return weighted_rrf(lists, weights, int(tcfg.get("rrf_k", 60)))[:depth]


def _wave6_selfquery_hits(client, coll, query, cfg, depth, sp, route):
    """Wave-6 self-query soft filters (step 2): when the query names a language /
    doc kind / path token, fuse the plain candidate list with (a) a payload-filtered
    hybrid arm (lang/kind) and/or (b) the path-matching SUBSEQUENCE of the plain
    list — both rank-fused at a sub-1.0 weight so a filter misfire can only nudge,
    never veto (filters stay soft per the plan)."""
    from qdrant_client import models

    dv, sv = _embed_query(query, cfg)
    base_hits = _server_fused(client, coll, dv, sv, cfg, depth, sp)
    filt = W6.selfquery_filter(query)
    if not filt:
        route.update(action="selfquery", triggered=0, n_sub=0)
        return base_hits

    lists = [("base", base_hits)]
    must = []
    if "lang" in filt:
        must.append(models.FieldCondition(key="lang",
                                          match=models.MatchAny(any=list(filt["lang"]))))
    if "kind" in filt:
        must.append(models.FieldCondition(key="kind",
                                          match=models.MatchValue(value=filt["kind"])))
    if must:
        lists.append(("filtered", _server_fused(client, coll, dv, sv, cfg,
                                                min(60, depth), sp,
                                                flt=models.Filter(must=must))))
    if "path_tokens" in filt:
        toks = filt["path_tokens"]
        sub = [h for h in base_hits
               if any(t in (h.payload.get("path") or "").lower() for t in toks)][:60]
        if sub:
            lists.append(("pathsub", sub))
    if len(lists) == 1:
        route.update(action="selfquery", triggered=0, n_sub=0)
        return base_hits
    w = float(cfg["selfquery"].get("weight", 0.5))
    weights = {"base": 1.0, "filtered": w, "pathsub": w}
    route.update(action="selfquery", triggered=1, n_sub=len(lists) - 1)
    return weighted_rrf(lists, weights, 60)[:depth]


def retrieve_chunks(client, coll: str, query: str, cfg: dict, mode: str, depth: int,
                    graph=None, qid: str | None = None, route: dict | None = None):
    """Return a ranked list of Qdrant points (chunks) for the arm's mode.

    Hybrid fusion has two paths: Qdrant server-side RRF/DBSF (the Wave-0 default), or
    in-process weighted RRF (Wave 1) when `hybrid.weights` or `hybrid.rrf_k` is set —
    that path issues the two arms as separate searches and fuses with tunable k/weights.
    `graph` (a wave5_graph.RepoGraph, passed when the arm enables `graph_overlay`)
    expands/rescores the fused list before the reranker sees it. Wave-6 blocks
    (`query_transform`, `selfquery`, `rerank.gate`/`rerank.guard`) are query-time-only
    and share the base collection; `qid` keys the offline transform cache and `route`
    is an out-param dict logged to the route.* TSV columns.
    """
    route = route if route is not None else {}
    hyb = cfg.get("hybrid", {})
    prefetch = int(hyb.get("prefetch", 60))
    sp = _search_params(cfg)

    hits = None
    if mode == "hybrid" and cfg.get("query_transform", {}).get("enabled"):
        hits = _wave6_transform_hits(client, coll, query, cfg, depth, sp, qid, route)
    elif mode == "hybrid" and cfg.get("selfquery", {}).get("enabled"):
        hits = _wave6_selfquery_hits(client, coll, query, cfg, depth, sp, route)

    if hits is None:
        dv, sv = _embed_query(query, cfg)
        if mode == "dense-only":
            hits = client.query_points(coll, query=dv, using="dense", limit=depth,
                                       with_payload=True, search_params=sp).points
        elif mode == "bm25-only":
            hits = client.query_points(coll, query=R.to_sparse_vector(sv), using="sparse",
                                       limit=depth, with_payload=True, search_params=sp).points
        elif hyb.get("weights") is not None or hyb.get("rrf_k") is not None:  # in-process weighted RRF
            dense_hits = client.query_points(coll, query=dv, using="dense", limit=prefetch,
                                             with_payload=True, search_params=sp).points
            sparse_hits = client.query_points(coll, query=R.to_sparse_vector(sv), using="sparse",
                                              limit=prefetch, with_payload=True, search_params=sp).points
            hits = weighted_rrf([("dense", dense_hits), ("sparse", sparse_hits)],
                                hyb.get("weights", {"dense": 1.0, "sparse": 1.0}),
                                int(hyb.get("rrf_k", 60)))[:depth]
        else:  # server-side RRF/DBSF (Wave-0 default)
            hits = _server_fused(client, coll, dv, sv, cfg, depth, sp)

    if graph is not None and cfg.get("graph_overlay", {}).get("enabled"):
        dv, sv = _embed_query(query, cfg)
        hits = apply_graph_overlay(client, coll, hits, dv, sv, cfg, graph, depth)

    rr = cfg.get("rerank", {})
    if rr.get("enabled") and hits:
        do_rerank = True
        gate_cfg = rr.get("gate")
        if gate_cfg:
            # CRAG-style confidence gate (Wave-6 step 5): two cheap single-arm calls
            # expose per-arm scores + top-file agreement that server-side fusion hides.
            dvg, svg = _embed_query(query, cfg)
            dh = client.query_points(coll, query=dvg, using="dense", limit=60,
                                     with_payload=True, search_params=sp).points
            sh = client.query_points(coll, query=R.to_sparse_vector(svg), using="sparse",
                                     limit=60, with_payload=True, search_params=sp).points
            conf = W6.confidence_features(dh, sh, hits)
            route["feat"] = ";".join(f"{k}={v}" for k, v in conf.items())
            if not gate_cfg.get("log_only"):
                do_rerank = W6.gate_decision(gate_cfg, conf)
            route.update(action="rerank-gate", triggered=int(do_rerank))
        if do_rerank:
            top_n = int(rr.get("top_n", 50))
            head = hits[:top_n]
            texts = [h.payload.get("text", "") for h in head]
            if rr.get("backend") == "infinity":
                scores = infinity_rerank(query, texts, rr["endpoint"], rr["model"],
                                         rr.get("template"))
            else:
                scores = R.rerank(query, texts, cfg)
            order = sorted(range(len(head)), key=lambda i: scores[i], reverse=True)
            guard = rr.get("guard")
            if guard and order:
                # Wave-6 rerank guard: 0020 mining shows the reranker's damage is
                # mostly demoting an already-correct fused top-1 (37/70 hurt queries
                # had pMRR==1 at base). Keep the fused head unless the reranker
                # overrules it by a confident margin / clears a floor.
                if guard.get("min_top_score") is not None and \
                        max(scores) < float(guard["min_top_score"]):
                    order = list(range(len(head)))  # reranker unsure about everything
                    route.update(action="rerank-guard", triggered=1)
                elif guard.get("protect_top1") and order[0] != 0 and \
                        scores[order[0]] < scores[0] + float(guard.get("margin", 0.0)):
                    order.remove(0)
                    order.insert(0, 0)
                    route.update(action="rerank-guard", triggered=1)
                else:
                    route.setdefault("action", "rerank-guard")
                    route.setdefault("triggered", 0)
            hits = [head[i] for i in order] + hits[top_n:]
    return hits


def derive_ranking(hits, top_k: int):
    """Collapse ranked chunks -> file-level ranking + the packed top_k chunk context.
    ranked_files: unique doc_ids in best-rank order (for file-level IR metrics).
    file_kind: best chunk's kind per file. ctx_*: the REAL packed top_k chunks
    (raw_text + kind) — what a consumer would actually read; drives sentinel
    coverage / answer_hit@5 / the retrieved code-doc mix / context-token cost."""
    ranked_files: list[str] = []
    file_kind: dict[str, str] = {}
    seen = set()
    for h in hits:
        did = h.payload.get("doc_id")
        if did is None or did in seen:
            continue
        seen.add(did)
        ranked_files.append(did)
        file_kind[did] = h.payload.get("kind", "")
    ctx = hits[:top_k]
    ctx_texts = [h.payload.get("raw_text", h.payload.get("text", "")) for h in ctx]
    ctx_kinds = [h.payload.get("kind", "") for h in ctx]
    return ranked_files, file_kind, ctx_texts, ctx_kinds


# --- manual ripgrep floor (no index) ------------------------------------------
_STOP = set(
    "the a an of to in on for and or is are was were be been being do does did how "
    "what which why when where who whom this that these those with from by as at it "
    "its into your you i we they he she them their our about over under between within "
    "if then else than so such not no yes can could would should may might will shall "
    "have has had get got make made use used using one two each any all some more most "
    "via per up out off down also only just but using does".split()
)
_TERM = re.compile(r"[A-Za-z_][A-Za-z0-9_.:]*")


def extract_terms(q: str, cap: int = 14) -> list[str]:
    """Deterministic keyword set for the manual ripgrep floor: identifier-shaped
    tokens (snake/camel/dotted/scoped) are always kept; otherwise content words of
    length >=4 that are not stopwords."""
    out: list[str] = []
    seen = set()
    for t in _TERM.findall(q):
        ident = any(c in t for c in "_.:") or re.search(r"[a-z][A-Z]", t) is not None
        keep = ident or (len(t) >= 4 and t.lower() not in _STOP)
        if keep and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out[:cap]


def manual_rg_rank(corpus: dict[str, dict], query: str, depth: int):
    """Rank files by (#distinct query terms matched, total hits) — the lexical
    floor the retrieving-context skill falls back to. Whole files are 'retrieved'."""
    terms = extract_terms(query)
    scored = []
    for path, payload in corpus.items():
        low = payload["text"].lower()
        distinct = 0
        total = 0
        for t in terms:
            tl = t.lower()
            c = low.count(tl)
            if c:
                distinct += 1
                total += c
        if distinct:
            scored.append((path, distinct, total))
    scored.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return [p for p, _d, _t in scored[:depth]]


# --- token estimate (char/4 proxy, consistent across arms) --------------------
def est_tokens(texts: list[str]) -> int:
    return sum((len(t) + 3) // 4 for t in texts)


# --- one query's metric row ---------------------------------------------------
def score_query_row(q: G.Question, ranked_files, file_kind, ctx_texts, ctx_kinds,
                    qrels_q, arm_cols, retrieval_ms, index_ms, route: dict | None = None):
    m = MET.retrieval_metrics(
        ranked_files, qrels_q, ks=KS,
        retrieved_texts=ctx_texts, sentinels=q.sentinels, retrieved_kinds=ctx_kinds,
    )
    contam = C.check_query(ranked_files[:20], q.primary)
    row = {}
    row.update(MET.slice_columns(q))
    row.update(arm_cols)
    row.update({k: round(v, 6) if isinstance(v, float) else v for k, v in m.items()})
    row["pack.context_tokens"] = est_tokens(ctx_texts)
    row["pack.n_packed"] = len(ctx_texts)
    row["ver.contamination_hits"] = len(contam)
    row["eff.retrieval_ms"] = round(retrieval_ms, 2)
    row["eff.index_ms"] = round(index_ms, 1)
    route = route or {}
    row["route.action"] = route.get("action", "")
    row["route.triggered"] = route.get("triggered", "")
    row["route.n_sub"] = route.get("n_sub", "")
    row["route.feat"] = route.get("feat", "")
    return row


# --- run one arm over selected repos/questions --------------------------------
def run_arm(cfg: dict, questions: list[G.Question], repos: list[str], run_id: str,
            depth: int, reindex: bool, writer: MET.TsvWriter) -> list[dict]:
    arm = cfg.get("arm", cfg.get("rag_config_id", "arm"))
    mode = cfg.get("retrieval_mode", "hybrid")
    top_k = int(cfg.get("top_k", 20))
    key = index_key(cfg)
    arm_cols = {
        "arm.run_id": run_id, "arm.config_id": cfg.get("rag_config_id", arm),
        "arm.arm": arm, "arm.index_mode": cfg.get("index_mode", "combined"),
        "arm.header": bool(cfg.get("contextual_header", False)),
        "arm.reranked": bool(cfg.get("rerank", {}).get("enabled", False)),
    }
    by_repo = collections.defaultdict(list)
    for q in questions:
        by_repo[q.repo].append(q)

    rows: list[dict] = []
    needs_index = mode in ("hybrid", "dense-only", "bm25-only", "wrong-context")
    client = None
    if needs_index:
        client, _ = R.get_client()

    for repo in repos:
        qs = by_repo.get(repo, [])
        if not qs:
            continue
        corpus = G.combined_corpus(repo, qs)
        qrels = G.build_file_qrels(qs, corpus, sentinel_grade1=False)
        index_ms = 0.0
        coll = None
        if needs_index:
            coll, index_ms = ensure_index(repo, cfg, key, reindex)
        # Wave-5 graph overlay: build (cached) the repo's deterministic file graph.
        graph = (W5.build_graph(repo) if cfg.get("graph_overlay", {}).get("enabled")
                 else None)

        if mode == "wrong-context":
            # real hybrid run for this repo, then donor rotation (within-repo,
            # same corpus = a strong distractor), scored against each query's OWN qrels.
            real = {}
            for q in qs:
                t0 = time.time()
                hits = retrieve_chunks(client, coll, q.question, cfg, "hybrid", depth, graph,
                                       qid=q.id)
                dt = (time.time() - t0) * 1000.0
                rf, fk, ct, ck = derive_ranking(hits, top_k)
                real[q.id] = (rf, fk, ct, ck, dt)
            ids = sorted(real)
            donor_of = {qid: ids[(i + 1) % len(ids)] for i, qid in enumerate(ids)} if len(ids) > 1 else {ids[0]: ids[0]}
            for q in qs:
                rf, fk, ct, ck, dt = real[donor_of[q.id]]
                rows.append(score_query_row(q, rf, fk, ct, ck, qrels[q.id], arm_cols, dt, index_ms))
            continue

        for q in qs:
            route: dict = {}
            if mode == "closed-book":
                rf, fk, ct, ck, dt = [], {}, [], [], 0.0
            elif mode == "manual-rg":
                t0 = time.time()
                rf = manual_rg_rank(corpus, q.question, depth)
                dt = (time.time() - t0) * 1000.0
                fk = {p: corpus[p]["kind"] for p in rf}
                ct = [corpus[p]["text"] for p in rf[:top_k]]
                ck = [corpus[p]["kind"] for p in rf[:top_k]]
            else:  # hybrid | dense-only | bm25-only
                t0 = time.time()
                hits = retrieve_chunks(client, coll, q.question, cfg, mode, depth, graph,
                                       qid=q.id, route=route)
                dt = (time.time() - t0) * 1000.0
                rf, fk, ct, ck = derive_ranking(hits, top_k)
            rows.append(score_query_row(q, rf, fk, ct, ck, qrels[q.id], arm_cols, dt,
                                        index_ms, route))

    for r in rows:
        writer.row(**r)
    return rows


# --- aggregation --------------------------------------------------------------
AGG_METRICS = ["ret.recall@5", "ret.recall@20", "ret.recall@100", "ret.ndcg@10",
               "ret.mrr", "ret.primary_mrr", "ret.primary_recall@20",
               "ret.sentinel_cov", "ret.answer_hit@5", "ret.frac_code_retrieved",
               "ret.frac_md_retrieved", "ver.contamination_hits",
               "pack.context_tokens", "eff.retrieval_ms", "route.triggered"]
SLICE_AXES = [("overall", lambda r: "all"), ("domain", lambda r: r["slice.domain"]),
              ("repo", lambda r: r["slice.repo"]), ("category", lambda r: r["slice.category"]),
              ("difficulty", lambda r: r["slice.difficulty"]), ("split", lambda r: r["slice.split"]),
              ("multiplicity", lambda r: r["slice.multiplicity"])]


def _mean(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return round(sum(vals) / len(vals), 4) if vals else 0.0


def aggregate(rows: list[dict]) -> dict:
    out: dict = {}
    for axis, keyfn in SLICE_AXES:
        groups = collections.defaultdict(list)
        for r in rows:
            groups[keyfn(r)].append(r)
        out[axis] = {}
        for gv, grp in sorted(groups.items()):
            out[axis][gv] = {"n": len(grp)}
            for met in AGG_METRICS:
                out[axis][gv][met] = _mean([r.get(met) for r in grp])
    return out


def _set_dotted(d: dict, path: str, val) -> None:
    keys = path.split(".")
    cur = d
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    cur[keys[-1]] = val


def _arm_sig(combo: list[tuple[str, object]]) -> str:
    parts = []
    for path, val in combo:
        name = path.split(".")[-1]
        v = "_".join(f"{k}{val[k]}" for k in sorted(val)) if isinstance(val, dict) else str(val)
        parts.append(f"{name}{v}")
    return "-".join(parts)


def expand_configs(configs: list[dict], cfg_dir: Path) -> list[dict]:
    """Expand any config carrying a `grid` (e.g. prefetch-topn-sweep.json) into one
    concrete arm per cartesian combination, overlaid on its `base_arm` config. Grid
    keys are dotted paths (`hybrid.prefetch`, `rerank.top_n`, `hybrid.rrf_k`,
    `hybrid.weights`, …). All sweep arms share the base index (these are query-time
    knobs, absent from index_key), so a 100-arm sweep indexes nothing new."""
    out: list[dict] = []
    for cfg in configs:
        if "grid" not in cfg:
            out.append(cfg)
            continue
        base = json.loads((cfg_dir / f"{cfg['base_arm']}.json").read_text())
        keys = list(cfg["grid"].keys())
        for vals in itertools.product(*(cfg["grid"][k] for k in keys)):
            c = copy.deepcopy(base)
            combo = list(zip(keys, vals))
            for path, val in combo:
                _set_dotted(c, path, val)
            c["arm"] = f"{cfg.get('arm', 'sweep')}:{_arm_sig(combo)}"
            c["rag_config_id"] = c["arm"]
            out.append(c)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", action="append", default=[], help="arm config json (repeatable)")
    ap.add_argument("--arm", action="append", default=[], help="arm name in configs/ (repeatable)")
    ap.add_argument("--repos", default="all", help="all | comma list")
    ap.add_argument("--split", default="all", choices=["all", "dev", "held-out"])
    ap.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    ap.add_argument("--reindex", action="store_true")
    ap.add_argument("--tag", required=True, help="output basename, e.g. 0010-wave0-baseline")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)

    cfg_dir = _HARNESS.parent / "configs"
    cfg_paths = list(args.config) + [str(cfg_dir / f"{a}.json") for a in args.arm]
    if not cfg_paths:
        ap.error("pass at least one --config or --arm")
    configs = expand_configs([json.loads(Path(p).read_text()) for p in cfg_paths], cfg_dir)

    questions = G.load_questions()
    if args.split != "all":
        questions = [q for q in questions if q.split == args.split]
    repos = list(M.REPOS) if args.repos == "all" else args.repos.split(",")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tsv = out_dir / f"{args.tag}-metrics.tsv"
    if tsv.exists():
        tsv.unlink()
    writer = MET.TsvWriter(tsv)

    run_id = args.tag
    summary = {"run_id": run_id, "split": args.split, "repos": repos,
               "depth": args.depth, "arms": {}}
    print(f"=== run {run_id}  split={args.split}  repos={len(repos)}  arms={len(configs)} ===")
    for cfg in configs:
        arm = cfg.get("arm", cfg.get("rag_config_id", "arm"))
        t0 = time.time()
        rows = run_arm(cfg, questions, repos, run_id, args.depth, args.reindex, writer)
        agg = aggregate(rows)
        summary["arms"][arm] = {"n_rows": len(rows), "wall_s": round(time.time() - t0, 1),
                                "agg": agg, "index_key": index_key(cfg),
                                "retrieval_mode": cfg.get("retrieval_mode")}
        o = agg["overall"]["all"]
        print(f"  {arm:26s} n={len(rows):4d}  R@20={o['ret.recall@20']:.3f} "
              f"nDCG@10={o['ret.ndcg@10']:.3f} pMRR={o['ret.primary_mrr']:.3f} "
              f"sent={o['ret.sentinel_cov']:.3f} hit@5={o['ret.answer_hit@5']:.3f} "
              f"contam={o['ver.contamination_hits']:.2f} ms={o['eff.retrieval_ms']:.0f}")
    writer.close()
    (out_dir / f"{args.tag}-summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {tsv}")
    print(f"wrote {out_dir / f'{args.tag}-summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
