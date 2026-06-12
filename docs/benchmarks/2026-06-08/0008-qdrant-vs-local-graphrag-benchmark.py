#!/usr/bin/env python3
"""Benchmark local Qdrant RAG against a deterministic local GraphRAG arm.

This is a one-off benchmark runner for report 0008. It intentionally lives next
to the benchmark, not inside `setting-up-rag`, because the benchmark should not
change that skill yet.

The Qdrant arm uses the existing `setting-up-rag` runtime: Qdrant embedded mode,
FastEmbed dense+sparse embeddings, RRF fusion, and the configured cross-encoder
reranker. The local GraphRAG arm is deterministic: it builds text units, extracts
identifier/entity co-occurrence edges, creates graph neighborhoods, and combines
BM25 with graph expansion. It is not a full Microsoft GraphRAG LLM index; the
report records that limitation explicitly.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import networkx as nx

try:
    import importlib.metadata as importlib_metadata
except ImportError:  # pragma: no cover
    import importlib_metadata  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
SETTING_UP_RAG = ROOT / ".agents" / "skills" / "setting-up-rag" / "scripts"
sys.path.insert(0, str(SETTING_UP_RAG))

import rag_lib as R  # noqa: E402

try:
    import tiktoken
except ImportError:  # pragma: no cover
    tiktoken = None

WORD_RE = re.compile(r"[A-Za-z0-9_@./:+-]+")
IDENT_RE = re.compile(
    r"`([^`]{2,80})`|"
    r"([A-Za-z_@][A-Za-z0-9_:/.-]{2,80})|"
    r"([A-Z][A-Za-z0-9]+(?:[A-Z][A-Za-z0-9]+)+)"
)
STOP = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "which",
    "when",
    "where",
    "what",
    "how",
    "does",
    "uses",
    "use",
    "are",
    "was",
    "were",
    "can",
    "not",
    "you",
    "its",
    "via",
    "src",
    "include",
    "docs",
    "memory",
}


@dataclass(frozen=True)
class Query:
    id: str
    project: str
    domain: str
    question: str
    relevant_docs: tuple[str, ...]
    sentinels: tuple[str, ...]
    difficulty: str = "medium"


QUERIES: tuple[Query, ...] = (
    Query(
        id="inception-history-native-preview",
        project="inception",
        domain="history",
        question="Which compiler did the inception session wire for TypeScript checks?",
        relevant_docs=("docs/transcripts/2026-06-07/0028-claude-inception-tanstack-tooling.md",),
        sentinels=("native-preview", "tsgo"),
    ),
    Query(
        id="inception-history-clean-state",
        project="inception",
        domain="history",
        question="Which exported session created the clean-state TanStack Start app used as the retrieval harness target?",
        relevant_docs=("docs/transcripts/2026-06-07/0028-claude-inception-tanstack-tooling.md",),
        sentinels=("clean-state", "TanStack Start"),
    ),
    Query(
        id="inception-history-compiler-plugin",
        project="inception",
        domain="history",
        question="Which session records the React Compiler being wired through Vite's Rolldown Babel plugin?",
        relevant_docs=(
            "docs/transcripts/2026-06-07/0028-claude-inception-tanstack-tooling.md",
            "docs/transcripts/2026-06-08/0037-claude-coding-style-skill.md",
        ),
        sentinels=("@rolldown/plugin-babel", "reactCompilerPreset"),
        difficulty="hard",
    ),
    Query(
        id="inception-code-router-preload",
        project="inception",
        domain="code",
        question="In the inception router, how are routes prefetched before navigation?",
        relevant_docs=("src/router.tsx",),
        sentinels=("defaultPreload", "intent"),
    ),
    Query(
        id="inception-code-react-compiler",
        project="inception",
        domain="code",
        question="Where does the inception Vite config enable React Compiler through the Rolldown Babel plugin?",
        relevant_docs=("vite.config.ts",),
        sentinels=("@rolldown/plugin-babel", "reactCompilerPreset"),
        difficulty="hard",
    ),
    Query(
        id="inception-code-typecheck",
        project="inception",
        domain="code",
        question="Which package script type-checks inception with the native TypeScript compiler binary?",
        relevant_docs=("package.json",),
        sentinels=("tsgo --noEmit",),
    ),
    Query(
        id="alpha-zero-history-xq-policy",
        project="alpha-zero",
        domain="history",
        question="How are Xiang Qi actions mapped into fixed policy-vector slots?",
        relevant_docs=("az-game-xiang-qi/memory/game_design_details/action_encoding.md",),
        sentinels=("8100", "PolicyIndex"),
    ),
    Query(
        id="alpha-zero-history-board-planes",
        project="alpha-zero",
        domain="history",
        question="How many planes does the Xiang Qi board serializer emit for network input?",
        relevant_docs=("az-game-xiang-qi/memory/game_design_details/board_encoding.md",),
        sentinels=("15 planes", "1350 floats"),
    ),
    Query(
        id="alpha-zero-history-lookback",
        project="alpha-zero",
        domain="history",
        question="What does the engine-owned history lookback buffer guarantee to serializers?",
        relevant_docs=("az-game-xiang-qi/memory/history_lookback.md",),
        sentinels=("RingBufferView", "most recent"),
        difficulty="hard",
    ),
    Query(
        id="alpha-zero-code-game-concept",
        project="alpha-zero",
        domain="code",
        question="Which alpha-zero API header defines the static game contract with policy size and history lookback?",
        relevant_docs=("alpha-zero-api/src/include/alpha-zero-api/game.h",),
        sentinels=("concept Game", "kHistoryLookback", "kPolicySize"),
        difficulty="hard",
    ),
    Query(
        id="alpha-zero-code-xq-policy",
        project="alpha-zero",
        domain="code",
        question="Where does Xiang Qi declare the 90 by 90 policy head and Markov history lookback?",
        relevant_docs=("az-game-xiang-qi/include/xq/game.h",),
        sentinels=("kPolicySize", "kHistoryLookback"),
        difficulty="hard",
    ),
    Query(
        id="alpha-zero-code-xq-augmentation-inference",
        project="alpha-zero",
        domain="code",
        question="Which Xiang Qi inference implementation inverse-maps augmented action probabilities back to original actions?",
        relevant_docs=("az-game-xiang-qi/src/xq/inference/inference.cc",),
        sentinels=("InverseTransformAction", "slot_for_policy_index"),
    ),
)


def token_count(text: str) -> int:
    if tiktoken is None:
        return max(1, len(text.split()))
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def tokens(text: str) -> list[str]:
    return [t.lower() for t in WORD_RE.findall(text)]


def sparse_modifier(model: str):
    from qdrant_client import models

    if "bm25" in model.lower() or "bm42" in model.lower():
        return models.Modifier.IDF
    return None


def include_inception_history(path: Path) -> bool:
    if path.name == "OVERVIEW.md":
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return "inception" in text.lower() or "tanstack" in text.lower()


def include_alpha_history(path: Path) -> bool:
    rel = path.as_posix()
    if "/third-party/" in rel or "/_deps/" in rel:
        return False
    return any(part in path.parts for part in ("memory", "doc", "docs")) or path.name == "README.md"


def include_code(path: Path) -> bool:
    skip = {
        ".git",
        ".jj",
        "node_modules",
        "dist",
        "build",
        ".output",
        ".vite",
        ".nitro",
        ".turbo",
        "coverage",
        ".cache",
        "__pycache__",
        ".venv",
        ".agents",
        ".claude",
        ".github",
        "third-party",
        "_deps",
        "cmake-build-debug",
        "cmake-build-release",
        "cmake-build-manual",
    }
    if any(part in skip for part in path.parts):
        return False
    if path.name in {"bun.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", ".DS_Store"}:
        return False
    return path.suffix in {
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".json",
        ".css",
        ".html",
        ".py",
        ".h",
        ".hpp",
        ".cc",
        ".cpp",
        ".cxx",
        ".md",
    } or path.name == "CMakeLists.txt"


def load_docs(project: str, domain: str, repo_root: Path, alpha_root: Path) -> tuple[Path, dict[str, str]]:
    if project == "inception" and domain == "history":
        base = repo_root
        paths = sorted((repo_root / "docs" / "transcripts").glob("*/*.md"))
        selected = [p for p in paths if include_inception_history(p)]
    elif project == "inception" and domain == "code":
        base = repo_root / "inception"
        selected = [p for p in base.rglob("*") if p.is_file() and include_code(p)]
    elif project == "alpha-zero" and domain == "history":
        base = alpha_root
        selected = [p for p in alpha_root.rglob("*") if p.is_file() and p.suffix == ".md" and include_alpha_history(p)]
    elif project == "alpha-zero" and domain == "code":
        base = alpha_root
        selected = [
            p
            for p in alpha_root.rglob("*")
            if p.is_file()
            and include_code(p)
            and not any(part in {"memory", "doc", "docs"} for part in p.parts)
        ]
    else:
        raise ValueError(f"unknown corpus {project}/{domain}")

    docs: dict[str, str] = {}
    for path in selected:
        try:
            docs[path.relative_to(base).as_posix()] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return base, docs


def chunk_docs(docs: dict[str, str], cfg: dict, kind: str) -> list[dict]:
    chunks: list[dict] = []
    for doc_id, text in sorted(docs.items()):
        for idx, chunk in enumerate(R.chunk(text, cfg, kind)):
            if not chunk.strip():
                continue
            chunks.append(
                {
                    "chunk_id": len(chunks),
                    "doc_id": doc_id,
                    "chunk_idx": idx,
                    "text": chunk,
                    "tokens": token_count(chunk),
                }
            )
    return chunks


class BM25:
    def __init__(self, chunks: list[dict]):
        self.chunk_tokens = [tokens(c["text"]) for c in chunks]
        self.df: Counter[str] = Counter()
        for toks in self.chunk_tokens:
            self.df.update(set(toks))
        self.avg_len = sum(len(t) for t in self.chunk_tokens) / max(1, len(self.chunk_tokens))
        n = max(1, len(self.chunk_tokens))
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in self.df.items()}

    def score(self, query: str) -> dict[int, float]:
        q = tokens(query)
        scores: dict[int, float] = {}
        for i, toks in enumerate(self.chunk_tokens):
            tf = Counter(toks)
            total = 0.0
            for term in q:
                f = tf.get(term, 0)
                if not f:
                    continue
                total += self.idf.get(term, 0.0) * (f * 2.5) / (
                    f + 1.5 * (1 - 0.75 + 0.75 * len(toks) / max(1.0, self.avg_len))
                )
            if total:
                scores[i] = total
        return scores


def normalize(scores: dict[int, float]) -> dict[int, float]:
    if not scores:
        return {}
    lo = min(scores.values())
    hi = max(scores.values())
    if hi == lo:
        return {k: 1.0 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}


def extract_entities(text: str, limit: int = 32) -> list[str]:
    found: list[str] = []
    for match in IDENT_RE.finditer(text):
        raw = next((g for g in match.groups() if g), "")
        ent = raw.strip("`.,;:()[]{}<>\"'")
        if not ent:
            continue
        low = ent.lower()
        if low in STOP or len(low) < 3 or low.isdigit():
            continue
        if "/" in ent or "." in ent or "_" in ent or any(ch.isupper() for ch in ent) or ent.startswith("@"):
            found.append(ent)
        elif len(ent) >= 6:
            found.append(ent)
    counts = Counter(found)
    return [ent for ent, _ in counts.most_common(limit)]


class LocalGraphRAG:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.bm25 = BM25(chunks)
        self.chunk_entities: list[set[str]] = []
        self.graph = nx.Graph()
        self.entity_to_chunks: dict[str, set[int]] = defaultdict(set)
        t0 = time.perf_counter()
        self._build_graph()
        self.index_ms = (time.perf_counter() - t0) * 1000.0
        self.community_count = nx.number_connected_components(self.graph) if self.graph.number_of_nodes() else 0

    def _build_graph(self) -> None:
        for chunk in self.chunks:
            ents = extract_entities(chunk["text"])
            entset = set(ents)
            self.chunk_entities.append(entset)
            for ent in entset:
                self.graph.add_node(ent)
                self.entity_to_chunks[ent].add(chunk["chunk_id"])
            ordered = list(entset)[:24]
            for i, left in enumerate(ordered):
                for right in ordered[i + 1 :]:
                    if self.graph.has_edge(left, right):
                        self.graph[left][right]["weight"] += 1
                    else:
                        self.graph.add_edge(left, right, weight=1)

    def _expanded_entities(self, query: str) -> set[str]:
        q_terms = set(tokens(query))
        q_ents = set(extract_entities(query, limit=16))
        for ent in self.graph.nodes:
            ent_low = ent.lower()
            parts = set(tokens(ent))
            if ent_low in q_terms or parts & q_terms:
                q_ents.add(ent)
        expanded = set(q_ents)
        for ent in list(q_ents):
            if ent not in self.graph:
                continue
            neighbors = sorted(
                self.graph[ent].items(),
                key=lambda item: item[1].get("weight", 0),
                reverse=True,
            )[:12]
            expanded.update(n for n, _ in neighbors)
        return expanded

    def search(self, query: str, top_k: int = 20) -> tuple[list[dict], float]:
        t0 = time.perf_counter()
        sparse = normalize(self.bm25.score(query))
        expanded = self._expanded_entities(query)
        graph_scores: dict[int, float] = defaultdict(float)
        for ent in expanded:
            for cid in self.entity_to_chunks.get(ent, set()):
                graph_scores[cid] += 1.0
        graph_scores = normalize(graph_scores)
        scores: dict[int, float] = defaultdict(float)
        for cid, score in sparse.items():
            scores[cid] += 0.62 * score
        for cid, score in graph_scores.items():
            scores[cid] += 0.38 * score
        ranked = sorted(scores, key=lambda cid: scores[cid], reverse=True)
        results = [{**self.chunks[cid], "score": scores[cid]} for cid in ranked[:top_k]]
        return results, (time.perf_counter() - t0) * 1000.0


class QdrantRAG:
    def __init__(self, chunks: list[dict], cfg: dict, qdrant_path: Path, collection: str, kind: str):
        self.chunks = chunks
        self.cfg = cfg
        self.collection = collection
        self.kind = kind
        os.environ["QDRANT_PATH"] = str(qdrant_path)
        self.client, self.where = R.get_client(force_local=True)
        self.index_ms = self._index()

    def _index(self) -> float:
        from qdrant_client import models

        coll = self.collection
        emb = self.cfg["embedding"]
        if self.client.collection_exists(coll):
            self.client.delete_collection(coll)
        self.client.create_collection(
            coll,
            vectors_config={
                "dense": models.VectorParams(
                    size=int(emb["dense_dim"]),
                    distance=getattr(models.Distance, emb.get("distance", "cosine").upper()),
                )
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(modifier=sparse_modifier(emb["sparse_model"]))
            },
        )
        t0 = time.perf_counter()
        texts = [c["text"] for c in self.chunks]
        batch_size = 128
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            dense, sparse = R.embed_documents(batch, self.cfg)
            points = []
            for j, text in enumerate(batch):
                chunk = self.chunks[start + j]
                points.append(
                    models.PointStruct(
                        id=int(chunk["chunk_id"]),
                        vector={"dense": dense[j], "sparse": R.to_sparse_vector(sparse[j])},
                        payload={
                            "doc_id": chunk["doc_id"],
                            "chunk_idx": chunk["chunk_idx"],
                            "text": text,
                            "tokens": chunk["tokens"],
                        },
                    )
                )
            self.client.upsert(coll, points=points)
        return (time.perf_counter() - t0) * 1000.0

    def search(self, query: str, top_k: int = 20) -> tuple[list[dict], float]:
        from qdrant_client import models

        t0 = time.perf_counter()
        dv, sv = R.embed_query(query, self.cfg)
        prefetch = int(self.cfg.get("hybrid", {}).get("prefetch", 60))
        rr = self.cfg.get("rerank", {})
        fuse_limit = max(top_k, int(rr.get("top_n", 50))) if rr.get("enabled") else top_k
        hits = self.client.query_points(
            self.collection,
            prefetch=[
                models.Prefetch(query=dv, using="dense", limit=prefetch),
                models.Prefetch(query=R.to_sparse_vector(sv), using="sparse", limit=prefetch),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=fuse_limit,
            with_payload=True,
        ).points
        if rr.get("enabled") and hits:
            texts = [hit.payload.get("text", "") for hit in hits]
            scores = R.rerank(query, texts, self.cfg)
            order = sorted(range(len(hits)), key=lambda i: scores[i], reverse=True)
            ranked = [(hits[i], float(scores[i])) for i in order]
        else:
            ranked = [(hit, float(hit.score)) for hit in hits]
        elapsed = (time.perf_counter() - t0) * 1000.0
        results = []
        for hit, score in ranked[:top_k]:
            results.append(
                {
                    "doc_id": hit.payload.get("doc_id"),
                    "chunk_idx": hit.payload.get("chunk_idx"),
                    "text": hit.payload.get("text", ""),
                    "tokens": int(hit.payload.get("tokens", token_count(hit.payload.get("text", "")))),
                    "score": score,
                }
            )
        return results, elapsed


def unique_ranked_docs(results: list[dict]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for res in results:
        doc = str(res["doc_id"])
        if doc in seen:
            continue
        seen.add(doc)
        out.append(doc)
    return out


def dcg(grades: list[int]) -> float:
    return sum((2**grade - 1) / math.log2(idx + 2) for idx, grade in enumerate(grades))


def score_results(query: Query, results: list[dict], docs: dict[str, str], retrieval_ms: float) -> dict[str, object]:
    ranked_docs = unique_ranked_docs(results)
    relevant = set(query.relevant_docs)
    out: dict[str, object] = {}
    for k in (5, 10, 20):
        top = ranked_docs[:k]
        hits = sum(1 for doc in top if doc in relevant)
        out[f"recall@{k}"] = hits / len(relevant) if relevant else 0.0
        out[f"precision@{k}"] = hits / k
        out[f"primary_hit@{k}"] = 1.0 if hits else 0.0
    grades = [2 if doc in relevant else 0 for doc in ranked_docs[:10]]
    ideal = sorted([2] * len(relevant), reverse=True)[:10]
    out["ndcg@10"] = dcg(grades) / dcg(ideal) if ideal else 0.0
    first_rel = 0
    for idx, doc in enumerate(ranked_docs, 1):
        if doc in relevant:
            first_rel = idx
            break
    out["mrr"] = 1.0 / first_rel if first_rel else 0.0

    first_answer_rank = 0
    tokens_to_answer = 0
    answer_hit5 = 0.0
    answer_hit20 = 0.0
    sentinel_lowers = [s.lower() for s in query.sentinels]
    for idx, res in enumerate(results[:20], 1):
        tokens_to_answer += int(res["tokens"])
        hay = (str(res["text"]) + "\n" + docs.get(str(res["doc_id"]), "")).lower()
        present = sum(1 for sentinel in sentinel_lowers if sentinel in hay)
        if present == len(sentinel_lowers):
            first_answer_rank = idx
            if idx <= 5:
                answer_hit5 = 1.0
            answer_hit20 = 1.0
            break
    if first_answer_rank == 0:
        tokens_to_answer = sum(int(r["tokens"]) for r in results[:20])
    out["answer_hit@5"] = answer_hit5
    out["answer_hit@20"] = answer_hit20
    out["answer_mrr"] = 1.0 / first_answer_rank if first_answer_rank else 0.0
    out["ctx_tokens_top5_chunks"] = sum(int(r["tokens"]) for r in results[:5])
    out["ctx_tokens_to_answer_chunk"] = tokens_to_answer
    out["retrieval_ms"] = retrieval_ms
    out["top_docs"] = "|".join(ranked_docs[:5])
    return out


def mean(rows: list[dict], key: str) -> float:
    values = [float(row[key]) for row in rows if row.get(key) not in ("", "NA", None)]
    return sum(values) / len(values) if values else 0.0


def summarize(rows: list[dict]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(str(row["project"]), str(row["domain"]), str(row["system"]))].append(row)
    summary = []
    for (project, domain, system), items in sorted(groups.items()):
        summary.append(
            {
                "project": project,
                "domain": domain,
                "system": system,
                "queries": len(items),
                "recall@20": round(mean(items, "recall@20"), 4),
                "primary_hit@20": round(mean(items, "primary_hit@20"), 4),
                "answer_hit@5": round(mean(items, "answer_hit@5"), 4),
                "ndcg@10": round(mean(items, "ndcg@10"), 4),
                "mrr": round(mean(items, "mrr"), 4),
                "retrieval_ms_p50": round(percentile([float(i["retrieval_ms"]) for i in items], 50), 3),
                "retrieval_ms_p95": round(percentile([float(i["retrieval_ms"]) for i in items], 95), 3),
                "ctx_tokens_top5_avg": round(mean(items, "ctx_tokens_top5_chunks"), 1),
                "ctx_tokens_to_answer_avg": round(mean(items, "ctx_tokens_to_answer_chunk"), 1),
            }
        )
    return summary


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1))))
    return s[idx]


def write_tsv(path: Path, rows: list[dict]) -> None:
    keys = [
        "project",
        "domain",
        "system",
        "query_id",
        "difficulty",
        "n_docs",
        "n_chunks",
        "index_ms",
        "retrieval_ms",
        "recall@5",
        "recall@10",
        "recall@20",
        "precision@5",
        "precision@10",
        "precision@20",
        "primary_hit@5",
        "primary_hit@10",
        "primary_hit@20",
        "answer_hit@5",
        "answer_hit@20",
        "ndcg@10",
        "mrr",
        "answer_mrr",
        "ctx_tokens_top5_chunks",
        "ctx_tokens_to_answer_chunk",
        "index_input_tokens",
        "index_llm_tokens",
        "top_docs",
    ]
    with path.open("w", encoding="utf-8") as fh:
        fh.write("\t".join(keys) + "\n")
        for row in rows:
            fh.write("\t".join(str(row.get(key, "")) for key in keys) + "\n")


def write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def bench_corpus(
    project: str,
    domain: str,
    docs: dict[str, str],
    cfg: dict,
    workdir: Path,
) -> list[dict]:
    kind = "code" if domain == "code" else "md"
    chunks = chunk_docs(docs, cfg, kind)
    index_input_tokens = sum(token_count(text) for text in docs.values())
    rows: list[dict] = []
    corpus_queries = [q for q in QUERIES if q.project == project and q.domain == domain]
    if not corpus_queries:
        return rows

    graph = LocalGraphRAG(chunks)
    qdrant_dir = workdir / f"qdrant-{project}-{domain}"
    if qdrant_dir.exists():
        shutil.rmtree(qdrant_dir)
    qdrant_dir.mkdir(parents=True, exist_ok=True)
    qdrant = QdrantRAG(chunks, cfg, qdrant_dir, f"{project}_{domain}", kind)

    for system, retriever, index_ms, index_llm_tokens in (
        ("local-graphrag", graph, graph.index_ms, 0),
        ("qdrant-fastembed", qdrant, qdrant.index_ms, 0),
    ):
        for query in corpus_queries:
            results, retrieval_ms = retriever.search(query.question, top_k=20)
            scored = score_results(query, results, docs, retrieval_ms)
            rows.append(
                {
                    "project": project,
                    "domain": domain,
                    "system": system,
                    "query_id": query.id,
                    "difficulty": query.difficulty,
                    "n_docs": len(docs),
                    "n_chunks": len(chunks),
                    "index_ms": round(index_ms, 2),
                    "index_input_tokens": index_input_tokens,
                    "index_llm_tokens": index_llm_tokens,
                    **{
                        key: round(value, 4) if isinstance(value, float) else value
                        for key, value in scored.items()
                    },
                }
            )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(ROOT / "docs" / "benchmarks" / "2026-06-08"))
    parser.add_argument("--work-dir", default=os.environ.get("CONTEXT_RETRIEVAL_HARNESS_DIR", "/tmp/context-retrieval-graphrag-0008"))
    parser.add_argument("--alpha-zero", default="/Users/shuyang/developer/alpha-zero")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir).expanduser().resolve()
    work_dir = Path(args.work_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    cfg = R.load_config(str(SETTING_UP_RAG / "rag-config.json"))
    alpha_root = Path(args.alpha_zero).expanduser().resolve()
    rows: list[dict] = []
    corpus_manifest = []
    for project in ("inception", "alpha-zero"):
        for domain in ("history", "code"):
            base, docs = load_docs(project, domain, ROOT, alpha_root)
            missing = [
                doc
                for q in QUERIES
                if q.project == project and q.domain == domain
                for doc in q.relevant_docs
                if doc not in docs
            ]
            if missing:
                raise SystemExit(f"missing primary docs for {project}/{domain}: {missing}")
            corpus_manifest.append(
                {
                    "project": project,
                    "domain": domain,
                    "root": str(base),
                    "n_docs": len(docs),
                    "tokens": sum(token_count(text) for text in docs.values()),
                }
            )
            print(f"bench: {project}/{domain}: {len(docs)} docs")
            rows.extend(bench_corpus(project, domain, docs, cfg, work_dir))

    tsv = out_dir / "0008-qdrant-vs-local-graphrag-metrics.tsv"
    summary = out_dir / "0008-qdrant-vs-local-graphrag-summary.json"
    meta = {
        "date": "2026-06-08",
        "qdrant_client": importlib_metadata.version("qdrant-client"),
        "fastembed": importlib_metadata.version("fastembed"),
        "microsoft_graphrag": importlib_metadata.version("graphrag"),
        "networkx": importlib_metadata.version("networkx"),
        "rag_config_id": cfg.get("rag_config_id"),
        "corpora": corpus_manifest,
        "summary": summarize(rows),
    }
    write_tsv(tsv, rows)
    write_json(summary, meta)
    print(f"bench: wrote {tsv}")
    print(f"bench: wrote {summary}")
    print(json.dumps(meta["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
