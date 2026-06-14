#!/usr/bin/env python3
"""query.py — hybrid retrieval over a Qdrant collection, with optional rerank.

Pipeline (see RETRIEVAL.md):
  1. embed the query (dense + sparse),
  2. Qdrant Query API: a dense prefetch and a sparse prefetch, fused with RRF,
  3. optional rerank of the fused top_n (Qwen3 /rerank by default),
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
        targets = R.project_targets(client, args.project, args.kind)
        for project_key, selected_kind, coll in targets:
            for hit, score in R.retrieve_chunks(client, coll, args.query, cfg, top_k, do_rerank=not args.no_rerank):
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
            for hit, score in R.retrieve_chunks(client, coll, args.query, cfg, top_k, do_rerank=not args.no_rerank)
        ]
        target_label = f"collection '{coll}'"

    if args.json:
        for hit, score, project_key, selected_kind, coll in ranked:
            payload = hit.payload or {}
            print(json.dumps({
                "project": project_key,
                "kind": selected_kind,
                "collection": coll,
                "doc_id": payload.get("doc_id"),
                "chunk_idx": payload.get("chunk_idx"),
                "score": float(score),
                "text": R.payload_display_text(payload),
            }))
        return 0
    rr = cfg.get("rerank", {})
    scale = (
        f"{rr.get('model', 'reranker')} scores"
        if used_rerank
        else "RRF fused score"
    )
    print(f"# {len(ranked)} results for: {args.query}  ({where}, {target_label}, scores: {scale})")
    for rank, (hit, score, project_key, selected_kind, coll) in enumerate(ranked, 1):
        payload = hit.payload or {}
        text = R.payload_display_text(payload).replace("\n", " ")
        snippet = text[:160] + ("…" if len(text) > 160 else "")
        prefix = f"{project_key}/{selected_kind}:" if project_key else ""
        print(
            f"{rank:>2}. [{score:+.4f}] "
            f"{prefix}{payload.get('doc_id')}#{payload.get('chunk_idx')}  {snippet}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
