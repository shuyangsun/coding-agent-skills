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


def infinity_rerank(query: str, texts: list[str], endpoint: str, model: str) -> list[float]:
    """Rerank via an Infinity server's /rerank (Wave 3 GPU rerankers served from the
    NAS, e.g. bge-reranker-v2-m3 / qwen3-reranker). Returns scores aligned to `texts`.
    Campaign-only (network LLM); the portable default uses the in-process FastEmbed path."""
    import json as _json
    import urllib.request

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


def retrieve_chunks(client, coll: str, query: str, cfg: dict, mode: str, depth: int):
    """Return a ranked list of Qdrant points (chunks) for the arm's mode.

    Hybrid fusion has two paths: Qdrant server-side RRF/DBSF (the Wave-0 default), or
    in-process weighted RRF (Wave 1) when `hybrid.weights` or `hybrid.rrf_k` is set —
    that path issues the two arms as separate searches and fuses with tunable k/weights.
    """
    from qdrant_client import models

    dv, sv = _embed_query(query, cfg)
    hyb = cfg.get("hybrid", {})
    prefetch = int(hyb.get("prefetch", 60))
    sp = _search_params(cfg)

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
        fusion = models.Fusion.DBSF if hyb.get("fusion") == "dbsf" else models.Fusion.RRF
        hits = client.query_points(
            coll,
            prefetch=[
                models.Prefetch(query=dv, using="dense", limit=prefetch, params=sp),
                models.Prefetch(query=R.to_sparse_vector(sv), using="sparse", limit=prefetch, params=sp),
            ],
            query=models.FusionQuery(fusion=fusion),
            limit=depth, with_payload=True,
        ).points

    rr = cfg.get("rerank", {})
    if rr.get("enabled") and hits:
        top_n = int(rr.get("top_n", 50))
        head = hits[:top_n]
        texts = [h.payload.get("text", "") for h in head]
        if rr.get("backend") == "infinity":
            scores = infinity_rerank(query, texts, rr["endpoint"], rr["model"])
        else:
            scores = R.rerank(query, texts, cfg)
        order = sorted(range(len(head)), key=lambda i: scores[i], reverse=True)
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
                    qrels_q, arm_cols, retrieval_ms, index_ms):
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

        if mode == "wrong-context":
            # real hybrid run for this repo, then donor rotation (within-repo,
            # same corpus = a strong distractor), scored against each query's OWN qrels.
            real = {}
            for q in qs:
                t0 = time.time()
                hits = retrieve_chunks(client, coll, q.question, cfg, "hybrid", depth)
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
                hits = retrieve_chunks(client, coll, q.question, cfg, mode, depth)
                dt = (time.time() - t0) * 1000.0
                rf, fk, ct, ck = derive_ranking(hits, top_k)
            rows.append(score_query_row(q, rf, fk, ct, ck, qrels[q.id], arm_cols, dt, index_ms))

    for r in rows:
        writer.row(**r)
    return rows


# --- aggregation --------------------------------------------------------------
AGG_METRICS = ["ret.recall@5", "ret.recall@20", "ret.recall@100", "ret.ndcg@10",
               "ret.mrr", "ret.primary_mrr", "ret.primary_recall@20",
               "ret.sentinel_cov", "ret.answer_hit@5", "ret.frac_code_retrieved",
               "ret.frac_md_retrieved", "ver.contamination_hits",
               "pack.context_tokens", "eff.retrieval_ms"]
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
