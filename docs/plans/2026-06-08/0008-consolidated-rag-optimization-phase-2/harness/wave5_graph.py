#!/usr/bin/env python3
"""wave5_graph.py — Wave-5 deterministic repo file graph for query-time overlay expansion.

Plan §"Wave 5 - Code Graphs, Source Maps, and Hierarchy" steps 1-2: recover
cross-file dependencies (includes/imports/tests/header-impl pairs) and the
doc↔code source-map signal (markdown links, path mentions — the deterministic
core of the benchmark-0009 local-GraphRAG prototype) as an OVERLAY on hybrid
retrieval, never a replacement. This module builds the per-repo file graph and
computes graph-expansion scores; the query-time merge/fetch lives in
run_benchmark.py (``apply_graph_overlay``) because it needs the Qdrant client
and the query vectors. Query-time only: the index, its text, and its vectors
are untouched, so overlay arms share the baseline's collection byte-for-byte
(same HNSW build — the A/B is immune to the ~0.03 re-index noise floor that
0017 measured).

Nodes are corpus files (exactly the indexed set: corpus_manifest.load_repo_corpus).
Edges are extracted with deterministic regexes (no LLM, no AST dependency):

  import   code -> code     ``#include "x.h"``, ``from a.b import c``, ``import x from './y'``
  link     md   -> any      ``[text](relative/path.md)``
  mention  any  -> any      repo-relative path tokens + corpus-resolvable bare filenames
  test     test <-> impl    ``test_x.py`` / ``x_test.cc`` / ``x.test.ts`` naming conventions
  pair     header <-> impl  same-stem ``.h/.hpp/.cuh`` <-> ``.cc/.cpp/.cu``

One edge per (src, dst): when several extractors fire the highest-priority type
wins (import > pair > test > link > mention) so expansion never double-counts a
neighbor. Expansion is direction-aware — following a reference OUT of a
highly-ranked file (its includes, the files a transcript touched) is precise,
while the REVERSE direction (everything that points AT a seed) is fan-in-heavy
(headers included everywhere, files cited by many docs), so reverse edges get
roughly half weight plus a per-seed log-degree damp. Weights are fixed by
judgment, not dev-tuned — the Wave-1 lesson is that many-knob query-time tuning
does not replicate held-out; the only swept knobs are the overlay strength
``lambda`` and ``fetch``. Stdlib-only; ``report``/``neighbors`` run without the venv.
"""
from __future__ import annotations

import argparse
import collections
import functools
import math
import posixpath
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpus_manifest as M  # noqa: E402

EDGE_TYPES = ("import", "pair", "test", "link", "mention")
_PRIORITY = {t: i for i, t in enumerate(EDGE_TYPES)}  # lower index = stronger claim
# Expansion weights per (edge type, direction). Forward = src -> dst (follow the
# reference out of a seed); reverse = dst -> src (walk back to referrers).
W_FWD = {"import": 1.0, "pair": 1.0, "test": 0.7, "link": 1.0, "mention": 0.8}
W_REV = {"import": 0.5, "pair": 1.0, "test": 0.7, "link": 0.5, "mention": 0.4}

_INCLUDE = re.compile(r'^[ \t]*#[ \t]*include[ \t]*["<]([^">]+)[">]', re.M)
_PY_FROM = re.compile(r"^[ \t]*from[ \t]+([\w.]+)[ \t]+import\b", re.M)
_PY_IMPORT = re.compile(r"^[ \t]*import[ \t]+([\w.]+(?:[ \t]*,[ \t]*[\w.]+)*)", re.M)
_TS_FROM = re.compile(r"""\bfrom[ \t]+['"]([^'"\n]+)['"]""")
_TS_CALL = re.compile(r"""\b(?:require|import)\(\s*['"]([^'"\n]+)['"]\s*\)""")
_MD_LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)\s]*)?\)")
_PATH_TOKEN = re.compile(r"(?:[\w.\-]+/){1,}[\w.\-]+\.[A-Za-z0-9]{1,8}\b")
_FILE_TOKEN = re.compile(
    r"\b[\w\-]+\.(?:py|cc|cpp|cxx|c|cu|cuh|h|hpp|hh|ts|tsx|js|jsx|mjs|cjs|md|json|jsonc"
    r"|ya?ml|toml|sh|cmake|rs|go)\b")
_TS_EXTS = ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
            "/index.ts", "/index.tsx", "/index.js")
_HDR_EXTS = frozenset({".h", ".hpp", ".hh", ".hxx", ".cuh"})
_IMPL_EXTS = frozenset({".cc", ".cpp", ".cxx", ".c", ".cu"})
_STEM_FANOUT_CAP = 4  # generic stems (util.*, index.*) pair/test-match at most this many files


class _Resolver:
    """Resolve referenced tokens (include paths, dotted modules, bare filenames) to
    corpus relpaths. Suffix matching handles include roots (``game/board.h`` ->
    ``include/game/board.h``); any ambiguity (>1 candidate) drops the edge."""

    def __init__(self, paths: set[str]):
        self.paths = paths
        self.by_suffix: dict[str, list[str]] = collections.defaultdict(list)
        for p in paths:
            parts = p.split("/")
            for n in range(1, min(4, len(parts)) + 1):
                self.by_suffix["/".join(parts[-n:])].append(p)

    def resolve(self, token: str) -> str | None:
        token = token.strip()
        while token.startswith("./"):
            token = token[2:]
        if token in self.paths:
            return token
        cands = self.by_suffix.get(token, [])
        return cands[0] if len(cands) == 1 else None

    def resolve_relative(self, src: str, token: str) -> str | None:
        cand = posixpath.normpath(posixpath.join(posixpath.dirname(src), token))
        return cand if cand in self.paths else None


def _test_stem(stem: str) -> str | None:
    """The implementation stem a test filename targets, or None if not test-named."""
    if stem.startswith("test_"):
        return stem[5:]
    for suf in ("_tests", "_test", ".test", ".spec", "_spec"):
        if stem.endswith(suf):
            return stem[: -len(suf)]
    return None


def _edges_for(src: str, payload: dict, res: _Resolver, mention_cap: int):
    """Yield (dst, type) reference edges extracted from one file's text."""
    text, kind, lang = payload["text"], payload["kind"], payload["lang"]
    out: list[tuple[str, str]] = []

    def add(dst: str | None, t: str) -> bool:
        if dst and dst != src:
            out.append((dst, t))
            return True
        return False

    if lang in ("c", "cpp", "cuda"):
        for tok in _INCLUDE.findall(text):
            add(res.resolve(tok), "import")
    elif lang == "python":
        mods = _PY_FROM.findall(text)
        for grp in _PY_IMPORT.findall(text):
            mods.extend(m.strip() for m in grp.split(","))
        for mod in mods:
            base = mod.strip().lstrip(".").replace(".", "/")
            if not base:
                continue
            for cand in (base + ".py", base + "/__init__.py"):
                if add(res.resolve(cand), "import"):
                    break
    elif lang in ("typescript", "javascript"):
        for tok in _TS_FROM.findall(text) + _TS_CALL.findall(text):
            if not tok.startswith("."):
                continue  # bare specifiers are packages/aliases, not repo files
            for ext in _TS_EXTS:
                if add(res.resolve_relative(src, tok + ext), "import"):
                    break
    if kind == "md":
        for tok in _MD_LINK.findall(text):
            if "://" in tok:
                continue
            add(res.resolve_relative(src, tok) or res.resolve(tok), "link")
    # Path-token + bare-filename mentions (any kind) — the 0009 "source map" signal:
    # transcripts/docs name the files they touched; code names its configs and docs.
    counts: collections.Counter = collections.Counter()
    for m in _PATH_TOKEN.finditer(text):
        tok = m.group(0)
        if "://" in tok or len(tok) > 120:
            continue
        r = res.resolve(tok)
        if r and r != src:
            counts[r] += 1
    for m in _FILE_TOKEN.finditer(text):
        r = res.resolve(m.group(0))
        if r and r != src:
            counts[r] += 1
    for dst, _n in counts.most_common(mention_cap):
        add(dst, "mention")
    return out


def _stem_edges(paths: set[str]) -> list[tuple[str, str, str]]:
    """Header<->impl pairs and test<->impl links from filename conventions."""
    by_stem: dict[str, list[str]] = collections.defaultdict(list)
    for p in paths:
        base = posixpath.basename(p)
        stem = base[: -len(posixpath.splitext(base)[1])] if posixpath.splitext(base)[1] else base
        by_stem[stem].append(p)
    edges: list[tuple[str, str, str]] = []
    for stem, ps in by_stem.items():
        if len(ps) <= _STEM_FANOUT_CAP:
            hs = [p for p in ps if posixpath.splitext(p)[1] in _HDR_EXTS]
            cs = [p for p in ps if posixpath.splitext(p)[1] in _IMPL_EXTS]
            edges.extend((c, h, "pair") for h in hs for c in cs)
        target_stem = _test_stem(stem)
        if not target_stem or target_stem == stem:
            continue
        targets = by_stem.get(target_stem, [])
        if not targets or len(targets) > _STEM_FANOUT_CAP:
            continue
        edges.extend((s, d, "test") for s in ps for d in targets)
    return edges


@dataclass
class RepoGraph:
    repo: str
    n_files: int
    fwd: dict[str, list[tuple[str, str]]]  # src -> [(dst, type)]
    rev: dict[str, list[tuple[str, str]]]  # dst -> [(src, type)]
    n_by_type: dict[str, int]

    def degree(self, f: str) -> int:
        return len(self.fwd.get(f, ())) + len(self.rev.get(f, ()))


@functools.lru_cache(maxsize=None)
def build_graph(repo_name: str, mention_cap: int = 50) -> RepoGraph:
    """Build (and cache) the file graph over EXACTLY the indexed corpus file set,
    so every node maps to a retrievable doc_id and excluded files can never enter."""
    corpus = M.load_repo_corpus(M.REPOS[repo_name])
    paths = set(corpus)
    res = _Resolver(paths)
    best: dict[tuple[str, str], str] = {}

    def keep(s: str, d: str, t: str) -> None:
        k = (s, d)
        if k not in best or _PRIORITY[t] < _PRIORITY[best[k]]:
            best[k] = t

    for src, payload in corpus.items():
        for dst, t in _edges_for(src, payload, res, mention_cap):
            keep(src, dst, t)
    for s, d, t in _stem_edges(paths):
        keep(s, d, t)
    fwd: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    rev: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    n_by_type: collections.Counter = collections.Counter()
    for (s, d), t in sorted(best.items()):
        fwd[s].append((d, t))
        rev[d].append((s, t))
        n_by_type[t] += 1
    return RepoGraph(repo_name, len(paths), dict(fwd), dict(rev), dict(n_by_type))


def expansion_scores(graph: RepoGraph, seed_sigma: dict[str, float], ocfg: dict) -> dict[str, float]:
    """Graph-neighbor expansion scores: G(f) = Σ_seeds σ_s · w(type, direction) /
    log2(2 + degree(s)). σ_s is the seed's retrieval strength (1/(60+file_rank));
    the log-degree damp makes a transcript that mentions 50 files spread less per
    neighbor than a focused 4-include code file. ``rev_scale`` scales every reverse
    weight (0 = forward-only); ``edge_types`` restricts the edge inventory (the
    step-1 code-graph vs step-2 source-map ablation)."""
    etypes = frozenset(ocfg.get("edge_types") or EDGE_TYPES)
    rev_scale = float(ocfg.get("rev_scale", 1.0))
    g: dict[str, float] = collections.defaultdict(float)
    for s, sigma in seed_sigma.items():
        damp = math.log2(2 + graph.degree(s))
        for d, t in graph.fwd.get(s, ()):
            if t in etypes:
                g[d] += sigma * W_FWD[t] / damp
        if rev_scale > 0:
            for d, t in graph.rev.get(s, ()):
                if t in etypes:
                    g[d] += sigma * W_REV[t] * rev_scale / damp
    return dict(g)


# --- CLI: graph stats + per-file debugging (stdlib-only) ---------------------
def cmd_report(args) -> int:
    for repo in ([args.repo] if args.repo else list(M.REPOS)):
        g = build_graph(repo, args.mention_cap)
        nedges = sum(g.n_by_type.values())
        connected = len(set(g.fwd) | set(g.rev))
        print(f"{repo:22s} files={g.n_files:4d} edges={nedges:6d} "
              f"connected={connected:4d} ({connected / max(1, g.n_files):4.0%})  "
              + " ".join(f"{t}={g.n_by_type.get(t, 0)}" for t in EDGE_TYPES))
        if args.top:
            deg = sorted(((g.degree(f), f) for f in set(g.fwd) | set(g.rev)), reverse=True)
            for d, f in deg[: args.top]:
                print(f"    deg={d:4d}  {f}")
    return 0


def cmd_neighbors(args) -> int:
    g = build_graph(args.repo, args.mention_cap)
    print(f"[{args.repo}] {args.file}  degree={g.degree(args.file)}")
    for label, adj in (("->", g.fwd), ("<-", g.rev)):
        for d, t in sorted(adj.get(args.file, []), key=lambda x: (_PRIORITY[x[1]], x[0])):
            print(f"  {label} {t:8s} {d}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mention-cap", type=int, default=50,
                    help="max outgoing mention edges per file (default 50)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("report", help="per-repo node/edge tallies by type")
    pr.add_argument("--repo", choices=list(M.REPOS))
    pr.add_argument("--top", type=int, default=0, help="also list the N highest-degree files")
    pr.set_defaults(func=cmd_report)
    pn = sub.add_parser("neighbors", help="dump one file's edges (debug)")
    pn.add_argument("--repo", required=True, choices=list(M.REPOS))
    pn.add_argument("--file", required=True)
    pn.set_defaults(func=cmd_neighbors)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
