#!/usr/bin/env python3
"""query.py — hybrid retrieval over a Qdrant collection, with optional rerank.

Pipeline (see RETRIEVAL.md):
  1. embed the query (dense + sparse),
  2. Qdrant Query API: a dense prefetch and a sparse prefetch, fused with RRF,
  3. optional in-process cross-encoder rerank of the fused top_n,
  4. return top_k chunks (doc_id, score, snippet).

Usage:
  query.py "your question" [--project NAME_OR_PATH] [--kind md|code|all]
           [--collection docs] [--config rag-config.json] [--top-k 20]
           [--no-rerank] [--json]
  query.py --list-projects [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rag_lib as R  # noqa: E402


def retrieve(client, coll: str, query: str, cfg: dict, top_k: int, do_rerank: bool):
    from qdrant_client import models

    dv, sv = R.embed_query(query, cfg)
    prefetch = int(cfg.get("hybrid", {}).get("prefetch", 60))
    rr = cfg.get("rerank", {})
    # fetch enough to feed the reranker when it is on, else just top_k
    fuse_limit = max(top_k, int(rr.get("top_n", 50))) if (do_rerank and rr.get("enabled")) else top_k
    fusion = models.Fusion.DBSF if cfg.get("hybrid", {}).get("fusion") == "dbsf" else models.Fusion.RRF

    hits = client.query_points(
        coll,
        prefetch=[
            models.Prefetch(query=dv, using="dense", limit=prefetch),
            models.Prefetch(query=R.to_sparse_vector(sv), using="sparse", limit=prefetch),
        ],
        query=models.FusionQuery(fusion=fusion),
        limit=fuse_limit,
        with_payload=True,
    ).points

    if do_rerank and rr.get("enabled") and hits:
        texts = [h.payload.get("text", "") for h in hits]
        scores = R.rerank(query, texts, cfg)  # aligned to `hits`
        order = sorted(range(len(hits)), key=lambda i: scores[i], reverse=True)
        ranked = [(hits[i], scores[i]) for i in order]
    else:
        ranked = [(h, h.score) for h in hits]
    return ranked[:top_k]


def print_projects(as_json: bool) -> int:
    manifest = R.load_project_manifest()
    projects = manifest.get("projects", {})
    if as_json:
        print(json.dumps(projects, indent=2, sort_keys=True))
        return 0
    if not projects:
        print("No local RAG projects registered.")
        return 0
    for key, project in sorted(projects.items()):
        root = project.get("root", "")
        collections = project.get("collections", {})
        kinds = ", ".join(
            f"{kind}:{info.get('collection')}"
            for kind, info in sorted(collections.items())
        )
        print(f"{key}\t{root}\t{kinds}")
    return 0


def project_targets(client, selector: str, kind: str):
    project_key, project = R.resolve_project(selector)
    collections = project.get("collections", {})
    selected_kinds = sorted(collections) if kind == "all" else [kind]
    targets = []
    for selected_kind in selected_kinds:
        info = collections.get(selected_kind)
        if not info:
            continue
        coll = info.get("collection")
        if not coll:
            continue
        if client.collection_exists(coll):
            targets.append((project_key, selected_kind, coll))
        else:
            print(
                f"query: warning: registered collection '{coll}' for "
                f"{project_key}/{selected_kind} does not exist",
                file=sys.stderr,
            )
    if not targets:
        available = ", ".join(sorted(collections)) or "(none)"
        sys.exit(
            f"query: project '{project_key}' has no available collection for "
            f"kind={kind}; registered kinds: {available}"
        )
    return targets


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="?", help="the natural-language query")
    ap.add_argument("--project", help="registered project name or project root path")
    ap.add_argument("--kind", choices=["md", "code", "all"], default="all", help="registered project collection kind")
    ap.add_argument("--collection")
    ap.add_argument("--config")
    ap.add_argument("--top-k", type=int, help="number of results (default: config top_k)")
    ap.add_argument("--no-rerank", action="store_true")
    ap.add_argument("--local", action="store_true", help="force embedded on-disk mode (skip the server probe)")
    ap.add_argument("--json", action="store_true", help="emit JSONL of {doc_id, score, text}")
    ap.add_argument("--list-projects", action="store_true", help="list projects registered by index.py")
    args = ap.parse_args(argv)

    if args.list_projects:
        return print_projects(args.json)
    if not args.query:
        ap.error("query is required unless --list-projects is used")
    if args.project and args.collection:
        ap.error("--project and --collection are mutually exclusive")

    cfg = R.load_config(args.config)
    top_k = args.top_k if args.top_k is not None else int(cfg.get("top_k", 20))
    used_rerank = (not args.no_rerank) and bool(cfg.get("rerank", {}).get("enabled"))
    client, where = R.get_client(force_local=args.local)
    if args.project:
        ranked = []
        targets = project_targets(client, args.project, args.kind)
        for project_key, selected_kind, coll in targets:
            for hit, score in retrieve(client, coll, args.query, cfg, top_k, do_rerank=not args.no_rerank):
                ranked.append((hit, score, project_key, selected_kind, coll))
        ranked.sort(key=lambda item: item[1], reverse=True)
        ranked = ranked[:top_k]
        target_label = f"project '{args.project}' ({', '.join(coll for _, _, coll in targets)})"
    else:
        coll = args.collection or cfg.get("collection", "docs")
        if not client.collection_exists(coll):
            sys.exit(f"query: collection '{coll}' not found ({where}). Run index.py first.")
        ranked = [
            (hit, score, None, None, coll)
            for hit, score in retrieve(client, coll, args.query, cfg, top_k, do_rerank=not args.no_rerank)
        ]
        target_label = f"collection '{coll}'"

    if args.json:
        for hit, score, project_key, selected_kind, coll in ranked:
            print(json.dumps({
                "project": project_key,
                "kind": selected_kind,
                "collection": coll,
                "doc_id": hit.payload.get("doc_id"),
                "chunk_idx": hit.payload.get("chunk_idx"),
                "score": float(score),
                "text": hit.payload.get("text", ""),
            }))
        return 0
    scale = "cross-encoder logits" if used_rerank else "RRF fused score"
    print(f"# {len(ranked)} results for: {args.query}  ({where}, {target_label}, scores: {scale})")
    for rank, (hit, score, project_key, selected_kind, coll) in enumerate(ranked, 1):
        text = (hit.payload.get("text", "") or "").replace("\n", " ")
        snippet = text[:160] + ("…" if len(text) > 160 else "")
        prefix = f"{project_key}/{selected_kind}:" if project_key else ""
        print(
            f"{rank:>2}. [{score:+.4f}] "
            f"{prefix}{hit.payload.get('doc_id')}#{hit.payload.get('chunk_idx')}  {snippet}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
