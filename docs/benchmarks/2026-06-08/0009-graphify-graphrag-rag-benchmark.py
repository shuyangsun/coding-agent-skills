#!/usr/bin/env python3
"""Benchmark Qdrant RAG, local GraphRAG, and graphify on two local projects.

This is a reproducibility artifact for the co-located benchmark report. It keeps
all generated corpora, indexes, and graphify outputs under a scratch directory and
does not modify the `setting-up-rag` skill or either test project.

Expected setup:
  - Run from the `coding-agent-skills` repo root.
  - `setting-up-rag/scripts/setup-local-rag.sh --warm` has provisioned
    `~/.cache/rag-skill/venv/bin/python`.
  - graphify is available as a source checkout passed with `--graphify-project`.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROUND_ID = "800-graphify"
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "the",
    "to",
    "under",
    "what",
    "when",
    "where",
    "which",
    "with",
}
CODE_EXTS = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
    ".js",
    ".jsx",
    ".json",
    ".mjs",
    ".py",
    ".sh",
    ".ts",
    ".tsx",
}
SKIP_DIRS = {
    ".agents",
    ".cache",
    ".claude",
    ".codex",
    ".gemini",
    ".git",
    ".github",
    ".idea",
    ".jj",
    ".pytest_cache",
    ".venv",
    ".vite",
    ".vscode",
    "__pycache__",
    "build",
    "cmake-build-debug",
    "cmake-build-manual",
    "dist",
    "generated",
    "node_modules",
    "third-party",
}
SKIP_PREFIX_PARTS = {"third-party", "build", "cmake-build-manual", ".venv", "generated"}
SKIP_FILES = {"bun.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"}


@dataclass(frozen=True)
class Query:
    project: str
    domain: str
    query_id: str
    question: str
    primary: tuple[str, ...]
    sentinels: tuple[str, ...]


@dataclass(frozen=True)
class Corpus:
    project: str
    domain: str
    kind: str
    root: Path
    files: tuple[str, ...]


QUERIES = [
    Query(
        project="inception",
        domain="history",
        query_id="inception-history-native-preview",
        question=(
            "Which coding session set up the inception app to type-check with "
            "TypeScript 7's native Go compiler instead of plain tsc?"
        ),
        primary=("docs/transcripts/2026-06-07/0028-claude-inception-tanstack-tooling.md",),
        sentinels=("native-preview", "tsgo --noEmit"),
    ),
    Query(
        project="inception",
        domain="history",
        query_id="inception-history-clean-scaffold",
        question=(
            "What TanStack CLI flags kept the inception scaffold clean, avoided "
            "template examples/toolchain/git setup, and enabled the compiler add-on?"
        ),
        primary=("docs/transcripts/2026-06-07/0028-claude-inception-tanstack-tooling.md",),
        sentinels=("--no-examples", "--no-toolchain", "--add-ons compiler"),
    ),
    Query(
        project="inception",
        domain="history",
        query_id="inception-history-react-compiler",
        question=(
            "Which Vite 8 React Compiler wiring did the inception setup record, "
            "including the rolldown Babel plugin and preset?"
        ),
        primary=("docs/transcripts/2026-06-07/0028-claude-inception-tanstack-tooling.md",),
        sentinels=("@rolldown/plugin-babel", "reactCompilerPreset"),
    ),
    Query(
        project="inception",
        domain="code",
        query_id="inception-code-router-preload",
        question=(
            "In the inception app, which router option makes route code and data "
            "prefetch when navigation intent is detected?"
        ),
        primary=("inception/src/router.tsx",),
        sentinels=("defaultPreload", "intent"),
    ),
    Query(
        project="inception",
        domain="code",
        query_id="inception-code-react-compiler",
        question=(
            "Which inception Vite config imports the rolldown Babel plugin and "
            "applies the React Compiler preset?"
        ),
        primary=("inception/vite.config.ts",),
        sentinels=("@rolldown/plugin-babel", "reactCompilerPreset"),
    ),
    Query(
        project="inception",
        domain="code",
        query_id="inception-code-typecheck",
        question=(
            "Which package script type-checks inception using the tsgo binary "
            "rather than tsc?"
        ),
        primary=("inception/package.json",),
        sentinels=("typecheck", "tsgo --noEmit"),
    ),
    Query(
        project="alpha-zero",
        domain="history",
        query_id="alpha-history-action-encoding",
        question=(
            "How does Xiang Qi encode policy actions, including the no-action "
            "sentinel and total policy range?"
        ),
        primary=("az-game-xiang-qi/memory/game_design_details/action_encoding.md",),
        sentinels=("XqA{90, 90}", "Range: `[0, 8100)`"),
    ),
    Query(
        project="alpha-zero",
        domain="history",
        query_id="alpha-history-board-planes",
        question=(
            "How is the Xiang Qi board serialized into neural-network input "
            "planes, including the side-to-move plane?"
        ),
        primary=("az-game-xiang-qi/memory/game_design_details/board_encoding.md",),
        sentinels=("15 planes", "Plane 14"),
    ),
    Query(
        project="alpha-zero",
        domain="history",
        query_id="alpha-history-mirror-augmentation",
        question=(
            "Which geometric symmetry does the Xiang Qi augmenter keep, and what "
            "does it reject as non-symmetry?"
        ),
        primary=("az-game-xiang-qi/memory/game_design.md",),
        sentinels=("left/right mirror", "Rotations break"),
    ),
    Query(
        project="alpha-zero",
        domain="code",
        query_id="alpha-code-inference-policy-map",
        question=(
            "Where does Xiang Qi inference invert augmented actions back into the "
            "original action space using PolicyIndex?"
        ),
        primary=("az-game-xiang-qi/src/xq/inference/inference.cc",),
        sentinels=("slot_for_policy_index", "InverseTransformAction"),
    ),
    Query(
        project="alpha-zero",
        domain="code",
        query_id="alpha-code-training-permute-pi",
        question=(
            "Where does Xiang Qi training augmentation permute target.pi so each "
            "augmented policy vector stays aligned with ValidActions ordering?"
        ),
        primary=("az-game-xiang-qi/src/xq/train/train.cc",),
        sentinels=("permuted", "orig_slot"),
    ),
    Query(
        project="alpha-zero",
        domain="code",
        query_id="alpha-code-ttt-register-pattern",
        question=(
            "Which alpha-zero source file registers TicTacToe board-size patterns "
            "and wires serializer/deserializer functions into the game collection?"
        ),
        primary=("alpha-zero/games/registry.cc",),
        sentinels=("RegisterPattern", "MakeTttSerializerPlayerBoard"),
    ),
]


def run(cmd: list[str], *, env: dict[str, str] | None = None, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=True,
        cwd=Path.cwd(),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def split_words(text: str) -> list[str]:
    rough = re.findall(r"[A-Za-z][A-Za-z0-9_]*|\d+", text)
    out: list[str] = []
    for token in rough:
        token = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", token)
        token = token.replace("_", " ")
        for part in token.lower().split():
            if len(part) > 1 and part not in STOPWORDS:
                out.append(part)
    return out


def file_texts(root: Path) -> dict[str, str]:
    docs: dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if "graphify-out/" in rel:
            continue
        docs[rel] = path.read_text(encoding="utf-8", errors="replace")
    return docs


def contains_any(text: str, sentinels: Iterable[str]) -> bool:
    lower = text.lower()
    return any(s.lower() in lower for s in sentinels)


def copy_selected(files: list[tuple[Path, str]], dest: Path) -> tuple[str, ...]:
    if dest.exists():
        shutil.rmtree(dest)
    copied: list[str] = []
    for src, rel in files:
        if not src.is_file():
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied.append(rel)
    return tuple(sorted(copied))


def has_skipped_part(path: Path) -> bool:
    return any(part in SKIP_PREFIX_PARTS or part in SKIP_DIRS for part in path.parts)


def collect_inception_history(repo: Path) -> list[tuple[Path, str]]:
    root = repo / "docs" / "transcripts"
    files = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(repo).as_posix()
        files.append((path, rel))
    return files


def collect_inception_code(repo: Path) -> list[tuple[Path, str]]:
    root = repo / "inception"
    files = []
    for path in sorted(root.rglob("*")):
        rel_root = path.relative_to(root)
        if not path.is_file() or has_skipped_part(rel_root):
            continue
        if path.name in SKIP_FILES:
            continue
        if path.suffix.lower() not in CODE_EXTS:
            continue
        rel = path.relative_to(repo).as_posix()
        files.append((path, rel))
    return files


def collect_alpha_history(alpha: Path) -> list[tuple[Path, str]]:
    files = []
    for path in sorted(p for p in alpha.rglob("memory/**/*.md") if p.is_file()):
        rel = path.relative_to(alpha)
        if has_skipped_part(rel):
            continue
        files.append((path, rel.as_posix()))
    extra = alpha / "alpha-zero-game" / "docs" / "dev_dependencies.md"
    if extra.is_file():
        files.append((extra, extra.relative_to(alpha).as_posix()))
    return files


def collect_alpha_code(alpha: Path) -> list[tuple[Path, str]]:
    files = []
    for path in sorted(alpha.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(alpha)
        if has_skipped_part(rel):
            continue
        if path.name in SKIP_FILES or path.suffix.lower() not in CODE_EXTS:
            continue
        files.append((path, rel.as_posix()))
    return files


def build_corpora(repo: Path, alpha: Path, scratch: Path) -> dict[tuple[str, str], Corpus]:
    corpora_dir = scratch / "corpora"
    specs = {
        ("inception", "history"): ("md", collect_inception_history(repo)),
        ("inception", "code"): ("code", collect_inception_code(repo)),
        ("alpha-zero", "history"): ("md", collect_alpha_history(alpha)),
        ("alpha-zero", "code"): ("code", collect_alpha_code(alpha)),
    }
    corpora = {}
    for (project, domain), (kind, files) in specs.items():
        root = corpora_dir / f"{project}-{domain}"
        copied = copy_selected(files, root)
        corpora[(project, domain)] = Corpus(project, domain, kind, root, copied)
    return corpora


def validate_queries(corpora: dict[tuple[str, str], Corpus]) -> None:
    for q in QUERIES:
        corpus = corpora[(q.project, q.domain)]
        docs = file_texts(corpus.root)
        for primary in q.primary:
            if primary not in docs:
                raise SystemExit(f"missing primary for {q.query_id}: {primary}")
        primary_text = "\n".join(docs[p] for p in q.primary)
        missing = [s for s in q.sentinels if s.lower() not in primary_text.lower()]
        if missing:
            raise SystemExit(f"missing sentinels for {q.query_id}: {missing}")


def reciprocal_rank(ranked: list[str], relevant: set[str], k: int = 20) -> float:
    for i, doc_id in enumerate(ranked[:k], 1):
        if doc_id in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at(ranked: list[str], relevant: set[str], k: int = 10) -> float:
    dcg = 0.0
    for i, doc_id in enumerate(ranked[:k], 1):
        if doc_id in relevant:
            dcg += 2.0 / math.log2(i + 1)
    ideal_hits = min(len(relevant), k)
    idcg = sum(2.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def score_query(
    q: Query,
    docs: dict[str, str],
    ranked: list[str],
    contexts: list[tuple[str, str]],
    retrieval_ms: float,
) -> dict[str, float | int | str]:
    primary = set(q.primary)
    top20 = ranked[:20]
    primary_hits = len(primary & set(top20))
    first_primary_rank = next((i for i, d in enumerate(ranked, 1) if d in primary), 0)
    first_answer_rank = 0
    cumulative_answer_tokens = 0
    cumulative_source_tokens = 0
    seen_sources: set[str] = set()
    for i, (doc_id, context) in enumerate(contexts, 1):
        cumulative_answer_tokens += estimate_tokens(context)
        source_text = docs.get(doc_id, "")
        if doc_id not in seen_sources:
            cumulative_source_tokens += estimate_tokens(source_text)
            seen_sources.add(doc_id)
        if not first_answer_rank and contains_any(context + "\n" + source_text, q.sentinels):
            first_answer_rank = i
            break
    ctx_top5 = sum(estimate_tokens(text) for _, text in contexts[:5])
    read_to_primary = 0
    for doc_id in ranked:
        read_to_primary += estimate_tokens(docs.get(doc_id, ""))
        if doc_id in primary:
            break
    else:
        read_to_primary = sum(estimate_tokens(docs.get(d, "")) for d in ranked[:20])
    return {
        "round": ROUND_ID,
        "project": q.project,
        "domain": q.domain,
        "query_id": q.query_id,
        "retrieval_ms": round(retrieval_ms, 3),
        "recall@20": round(primary_hits / max(1, len(primary)), 4),
        "primary_hit@20": int(primary_hits > 0),
        "answer_hit@5": int(any(contains_any(c + "\n" + docs.get(d, ""), q.sentinels) for d, c in contexts[:5])),
        "ndcg@10": round(ndcg_at(ranked, primary), 4),
        "primary_mrr": round(reciprocal_rank(ranked, primary), 4),
        "answer_mrr": round(1.0 / first_answer_rank if first_answer_rank else 0.0, 4),
        "ctx_tokens_top5": ctx_top5,
        "ctx_tokens_to_answer": cumulative_answer_tokens if first_answer_rank else 0,
        "read_tokens_to_primary_doc": read_to_primary,
        "first_primary_rank": first_primary_rank,
        "first_answer_rank": first_answer_rank,
    }


class LocalGraphIndex:
    def __init__(self, docs: dict[str, str]) -> None:
        self.docs = docs
        self.doc_tokens: dict[str, list[str]] = {doc: split_words(text + " " + doc) for doc, text in docs.items()}
        self.tf: dict[str, Counter[str]] = {doc: Counter(toks) for doc, toks in self.doc_tokens.items()}
        self.df: Counter[str] = Counter()
        for toks in self.doc_tokens.values():
            self.df.update(set(toks))
        self.file_edges = self._build_file_edges()

    def _idf(self, token: str) -> float:
        n = max(1, len(self.docs))
        return math.log(1 + (n - self.df.get(token, 0) + 0.5) / (self.df.get(token, 0) + 0.5))

    def _build_file_edges(self) -> dict[str, set[str]]:
        by_name = {Path(doc).name: doc for doc in self.docs}
        edges: dict[str, set[str]] = defaultdict(set)
        link_re = re.compile(r"(?:#include\s+[<\"]([^>\"]+)[>\"]|from\s+['\"]([^'\"]+)['\"]|import\s+['\"]([^'\"]+)['\"]|\]\(([^)]+)\))")
        for doc, text in self.docs.items():
            for match in link_re.finditer(text):
                target = next((g for g in match.groups() if g), "")
                if not target:
                    continue
                name = Path(target.split("#", 1)[0]).name
                other = by_name.get(name)
                if other and other != doc:
                    edges[doc].add(other)
                    edges[other].add(doc)
        return edges

    def retrieve(self, question: str, top_k: int = 20) -> tuple[list[str], list[tuple[str, str]], float]:
        t0 = time.perf_counter()
        q_tokens = split_words(question)
        q_counts = Counter(q_tokens)
        direct: dict[str, float] = defaultdict(float)
        for doc, tf in self.tf.items():
            length = max(1, sum(tf.values()))
            for tok, qf in q_counts.items():
                if tok in tf:
                    direct[doc] += qf * (tf[tok] / length) * self._idf(tok) * 100.0
                if tok in doc.lower():
                    direct[doc] += 1.0
        graph_scores = dict(direct)
        for doc, score in direct.items():
            for neighbor in self.file_edges.get(doc, ()):
                graph_scores[neighbor] = graph_scores.get(neighbor, 0.0) + score * 0.20
        ranked = [doc for doc, score in sorted(graph_scores.items(), key=lambda kv: (-kv[1], kv[0])) if score > 0][:top_k]
        contexts = []
        for doc in ranked:
            matched = sorted(set(q_tokens) & set(self.doc_tokens.get(doc, [])))
            neighbors = sorted(self.file_edges.get(doc, ()))[:6]
            excerpt = " ".join(self.docs[doc].split()[:120])
            contexts.append((
                doc,
                f"FILE {doc}\nMATCHED {', '.join(matched)}\nNEIGHBORS {', '.join(neighbors)}\nEXCERPT {excerpt}",
            ))
        return ranked, contexts, (time.perf_counter() - t0) * 1000.0


def run_local_graphrag(corpora: dict[tuple[str, str], Corpus]) -> list[dict]:
    rows = []
    for key, corpus in corpora.items():
        docs = file_texts(corpus.root)
        index_start = time.perf_counter()
        idx = LocalGraphIndex(docs)
        index_ms = (time.perf_counter() - index_start) * 1000.0
        graph_edges = sum(len(v) for v in idx.file_edges.values()) // 2
        for q in [query for query in QUERIES if (query.project, query.domain) == key]:
            ranked, contexts, retrieval_ms = idx.retrieve(q.question)
            row = score_query(q, docs, ranked, contexts, retrieval_ms)
            row.update({
                "method": "local-graphrag",
                "n_docs": len(docs),
                "n_units": len(docs),
                "graph_nodes": len(docs) + len(idx.df),
                "graph_edges": graph_edges,
                "index_ms": round(index_ms, 3),
                "index_input_tokens": 0,
                "index_output_tokens": 0,
            })
            rows.append(row)
    return rows


def write_qdrant_batch_helper(path: Path, rag_scripts: Path) -> None:
    path.write_text(
        f"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
sys.path.insert(0, {str(rag_scripts)!r})
import rag_lib as R
import query as Q

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
cfg = R.load_config(payload["config"])
client, _where = R.get_client(force_local=True)
if not client.collection_exists(payload["collection"]):
    raise SystemExit("missing collection: " + payload["collection"])
Q.retrieve(client, payload["collection"], "__warmup__", cfg, 1, do_rerank=False)
for item in payload["queries"]:
    t0 = time.perf_counter()
    ranked = Q.retrieve(client, payload["collection"], item["question"], cfg, payload["top_k"], do_rerank=True)
    ms = (time.perf_counter() - t0) * 1000.0
    out = {{"query_id": item["query_id"], "retrieval_ms": ms, "hits": []}}
    for hit, score in ranked:
        out["hits"].append({{
            "doc_id": hit.payload.get("doc_id"),
            "chunk_idx": hit.payload.get("chunk_idx"),
            "score": float(score),
            "text": hit.payload.get("text", ""),
        }})
    print(json.dumps(out))
""".lstrip(),
        encoding="utf-8",
    )


def run_qdrant(corpora: dict[tuple[str, str], Corpus], repo: Path, scratch: Path, rag_python: Path) -> list[dict]:
    rows = []
    rag_scripts = repo / ".agents" / "skills" / "setting-up-rag" / "scripts"
    config = rag_scripts / "rag-config.json"
    helper = scratch / "qdrant_batch_query.py"
    write_qdrant_batch_helper(helper, rag_scripts)
    env = os.environ.copy()
    env["RAG_HOME"] = str(scratch / "rag-home")
    for key, corpus in corpora.items():
        docs = file_texts(corpus.root)
        collection = f"bench_{corpus.project.replace('-', '_')}_{corpus.domain}"
        t0 = time.perf_counter()
        index_proc = run(
            [
                str(rag_python),
                str(rag_scripts / "index.py"),
                "--corpus",
                str(corpus.root),
                "--kind",
                corpus.kind,
                "--collection",
                collection,
                "--config",
                str(config),
                "--recreate",
                "--local",
                "--batch",
                "128",
            ],
            env=env,
            timeout=1200,
        )
        index_ms = (time.perf_counter() - t0) * 1000.0
        match = re.search(r"(\d+) docs -> (\d+) chunks", index_proc.stdout)
        n_units = int(match.group(2)) if match else 0
        queries = [query for query in QUERIES if (query.project, query.domain) == key]
        payload = scratch / f"{collection}-queries.json"
        payload.write_text(
            json.dumps(
                {
                    "collection": collection,
                    "config": str(config),
                    "top_k": 20,
                    "queries": [{"query_id": q.query_id, "question": q.question} for q in queries],
                }
            ),
            encoding="utf-8",
        )
        query_proc = run([str(rag_python), str(helper), str(payload)], env=env, timeout=600)
        by_id = {}
        for line in query_proc.stdout.splitlines():
            if line.strip().startswith("{"):
                rec = json.loads(line)
                by_id[rec["query_id"]] = rec
        for q in queries:
            rec = by_id[q.query_id]
            hits = rec["hits"]
            ranked = []
            contexts = []
            seen = set()
            for hit in hits:
                doc_id = hit["doc_id"]
                if doc_id not in seen:
                    ranked.append(doc_id)
                    seen.add(doc_id)
                contexts.append((doc_id, hit.get("text", "")))
            row = score_query(q, docs, ranked, contexts, float(rec["retrieval_ms"]))
            row.update({
                "method": "qdrant-rag",
                "n_docs": len(docs),
                "n_units": n_units,
                "graph_nodes": 0,
                "graph_edges": 0,
                "index_ms": round(index_ms, 3),
                "index_input_tokens": 0,
                "index_output_tokens": 0,
            })
            rows.append(row)
    return rows


def load_graphify_graph(path: Path) -> tuple[list[dict], list[dict], int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    nodes = data.get("nodes", [])
    edges = data.get("edges", data.get("links", []))
    return nodes, edges, int(data.get("input_tokens", 0) or 0), int(data.get("output_tokens", 0) or 0)


def source_from_node(node: dict) -> str:
    source = str(node.get("source_file") or "")
    return source.replace("\\", "/").lstrip("./")


def retrieve_graphify(
    graph_path: Path,
    docs: dict[str, str],
    question: str,
    top_k: int = 20,
) -> tuple[list[str], list[tuple[str, str]], float, int, int]:
    t0 = time.perf_counter()
    nodes, edges, input_tokens, output_tokens = load_graphify_graph(graph_path)
    q_tokens = split_words(question)
    node_by_id = {str(n.get("id")): n for n in nodes}
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        src = str(edge.get("source") or edge.get("from") or "")
        tgt = str(edge.get("target") or edge.get("to") or "")
        if src and tgt:
            adjacency[src].append(tgt)
            adjacency[tgt].append(src)
    scores: dict[str, float] = defaultdict(float)
    matched_nodes: list[str] = []
    for node_id, node in node_by_id.items():
        source = source_from_node(node)
        if not source:
            continue
        text = " ".join(str(node.get(k, "")) for k in ("id", "label", "source_file", "source_location"))
        toks = set(split_words(text))
        score = len(toks & set(q_tokens))
        if score:
            scores[source] += score
            matched_nodes.append(node_id)
        if any(tok in source.lower() for tok in q_tokens):
            scores[source] += 0.5
    for node_id in matched_nodes:
        for neighbor in adjacency.get(node_id, []):
            source = source_from_node(node_by_id.get(neighbor, {}))
            if source:
                scores[source] += 0.35
    ranked = [doc for doc, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0])) if doc in docs][:top_k]
    contexts = []
    for doc in ranked:
        labels = []
        rel_edges = []
        for node_id, node in node_by_id.items():
            if source_from_node(node) == doc and len(labels) < 16:
                labels.append(str(node.get("label") or node.get("id") or ""))
        for edge in edges[:2000]:
            src = str(edge.get("source") or edge.get("from") or "")
            tgt = str(edge.get("target") or edge.get("to") or "")
            src_node = node_by_id.get(src, {})
            tgt_node = node_by_id.get(tgt, {})
            if source_from_node(src_node) == doc or source_from_node(tgt_node) == doc:
                rel_edges.append(
                    f"{src_node.get('label', src)} --{edge.get('relation', '')}-- {tgt_node.get('label', tgt)}"
                )
                if len(rel_edges) >= 8:
                    break
        contexts.append((doc, f"GRAPHIFY FILE {doc}\nNODES {', '.join(labels)}\nEDGES {'; '.join(rel_edges)}"))
    return ranked, contexts, (time.perf_counter() - t0) * 1000.0, input_tokens, output_tokens


def run_graphify(corpora: dict[tuple[str, str], Corpus], graphify_project: Path, scratch: Path) -> list[dict]:
    rows = []
    graphify_root = scratch / "graphify"
    env = os.environ.copy()
    env["GRAPHIFY_QUERY_LOG_DISABLE"] = "1"
    for key, corpus in corpora.items():
        docs = file_texts(corpus.root)
        out_dir = graphify_root / f"{corpus.project}-{corpus.domain}"
        if out_dir.exists():
            shutil.rmtree(out_dir)
        cmd = [
            "uv",
            "run",
            "--project",
            str(graphify_project),
            "--extra",
            "gemini",
            "python",
            "-m",
            "graphify",
            "extract",
            str(corpus.root),
            "--no-cluster",
            "--out",
            str(out_dir),
            "--max-workers",
            "4",
            "--token-budget",
            "60000",
            "--max-concurrency",
            "4",
            "--api-timeout",
            "180",
        ]
        if corpus.kind == "md":
            cmd.extend(["--backend", "gemini"])
        t0 = time.perf_counter()
        proc = run(cmd, env=env, timeout=1800)
        index_ms = (time.perf_counter() - t0) * 1000.0
        graph_path = out_dir / "graphify-out" / "graph.json"
        if not graph_path.is_file():
            raise SystemExit(f"graphify did not write graph: {graph_path}\n{proc.stdout}")
        nodes, edges, index_input, index_output = load_graphify_graph(graph_path)
        queries = [query for query in QUERIES if (query.project, query.domain) == key]
        for q in queries:
            ranked, contexts, retrieval_ms, _, _ = retrieve_graphify(graph_path, docs, q.question)
            row = score_query(q, docs, ranked, contexts, retrieval_ms)
            row.update({
                "method": "graphify",
                "n_docs": len(docs),
                "n_units": len(nodes),
                "graph_nodes": len(nodes),
                "graph_edges": len(edges),
                "index_ms": round(index_ms, 3),
                "index_input_tokens": index_input,
                "index_output_tokens": index_output,
            })
            rows.append(row)
    return rows


def write_rows(rows: list[dict], out_path: Path) -> None:
    fieldnames = [
        "round",
        "method",
        "project",
        "domain",
        "query_id",
        "n_docs",
        "n_units",
        "graph_nodes",
        "graph_edges",
        "index_ms",
        "retrieval_ms",
        "recall@20",
        "primary_hit@20",
        "answer_hit@5",
        "ndcg@10",
        "primary_mrr",
        "answer_mrr",
        "ctx_tokens_top5",
        "ctx_tokens_to_answer",
        "read_tokens_to_primary_doc",
        "index_input_tokens",
        "index_output_tokens",
        "first_primary_rank",
        "first_answer_rank",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def summarize(rows: list[dict]) -> str:
    buckets: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        buckets[(str(row["method"]), str(row["project"]), str(row["domain"]))].append(row)
    lines = []
    for key in sorted(buckets):
        vals = buckets[key]
        n = len(vals)
        avg = lambda col: sum(float(v[col]) for v in vals) / max(1, n)
        lines.append(
            "\t".join(
                [
                    *key,
                    f"n={n}",
                    f"recall@20={avg('recall@20'):.3f}",
                    f"answer_hit@5={avg('answer_hit@5'):.3f}",
                    f"primary_mrr={avg('primary_mrr'):.3f}",
                    f"ctx_tokens_top5={avg('ctx_tokens_top5'):.1f}",
                    f"read_tokens_to_primary={avg('read_tokens_to_primary_doc'):.1f}",
                    f"retrieval_ms={avg('retrieval_ms'):.2f}",
                    f"index_input_tokens={max(int(v['index_input_tokens']) for v in vals)}",
                    f"index_output_tokens={max(int(v['index_output_tokens']) for v in vals)}",
                ]
            )
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--alpha-zero", type=Path, default=Path("~/developer/alpha-zero").expanduser())
    parser.add_argument("--graphify-project", type=Path, required=True)
    parser.add_argument(
        "--rag-python",
        type=Path,
        default=Path("~/.cache/rag-skill/venv/bin/python").expanduser(),
    )
    parser.add_argument("--scratch", type=Path, default=None)
    parser.add_argument(
        "--tsv",
        type=Path,
        default=Path("docs/benchmarks/2026-06-08/0009-graphify-graphrag-rag-metrics.tsv"),
    )
    args = parser.parse_args(argv)

    repo = args.repo.expanduser().resolve()
    alpha = args.alpha_zero.expanduser().resolve()
    graphify_project = args.graphify_project.expanduser().resolve()
    if not repo.is_dir():
        raise SystemExit(f"repo not found: {repo}")
    if not alpha.is_dir():
        raise SystemExit(f"alpha-zero not found: {alpha}")
    if not graphify_project.is_dir():
        raise SystemExit(f"graphify project not found: {graphify_project}")
    if not args.rag_python.is_file():
        raise SystemExit(f"rag python not found: {args.rag_python}")

    scratch = args.scratch.expanduser().resolve() if args.scratch else Path(tempfile.mkdtemp(prefix="graphify-rag-bench."))
    scratch.mkdir(parents=True, exist_ok=True)
    corpora = build_corpora(repo, alpha, scratch)
    validate_queries(corpora)

    rows: list[dict] = []
    rows.extend(run_qdrant(corpora, repo, scratch, args.rag_python))
    rows.extend(run_local_graphrag(corpora))
    rows.extend(run_graphify(corpora, graphify_project, scratch))
    write_rows(rows, args.tsv)

    summary = summarize(rows)
    (scratch / "summary.tsv").write_text(summary + "\n", encoding="utf-8")
    print(f"scratch={scratch}")
    print(f"metrics={args.tsv}")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
