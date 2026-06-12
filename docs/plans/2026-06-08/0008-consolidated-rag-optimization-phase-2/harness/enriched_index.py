#!/usr/bin/env python3
"""enriched_index.py — rich-payload, dual-field indexer for the Phase-3 benchmark.

Pre-work for ``0008-consolidated-rag-optimization-phase-2.md`` §"Index Payload and
Storage Changes". The shipped ``setting-up-rag`` payload is only
``{doc_id, chunk_idx, kind, text}`` and its chunker word-joins text (losing source
offsets), so it cannot support metadata filtering, parent-window retrieval, byte/
line citations, or source-preserving answer generation. This HARNESS-side indexer
adds them WITHOUT modifying the shipped skill (keep/revert discipline: promote the
schema into the skill only once a benchmark proves a win).

Each point carries:
  repo, kind, lang, doc_id(=path), heading_path, symbol, parent_id, chunk_idx,
  n_chunks, start_byte/end_byte, start_line/end_line, parent_start/parent_end,
  raw_text (VERBATIM source slice — citations + sentinel matching),
  contextualized_text (retrieval field; == raw_text unless --contextual-header),
  text (== contextualized_text, for shipped query.py compatibility).

The span-tracking chunker mirrors the shipped chunking *strategy* (heading-aware md
with a min-merge floor; blank-line block packing for code) but operates on CHARACTER
SPANS so raw_text is byte-exact. Embedding/Qdrant reuse rag_lib (one stack). The
``chunk-report`` command is stdlib-only (no venv) so the chunker is testable in CI;
``index`` needs the FastEmbed/Qdrant venv.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpus_manifest as M  # noqa: E402
import gold_loader as G  # noqa: E402


def _skill_scripts_dir() -> Path:
    """Locate the shipped setting-up-rag scripts dir by walking up to the repo
    root (the ancestor holding .agents/skills/…). Works from any checkout/workspace."""
    for anc in Path(__file__).resolve().parents:
        cand = anc / ".agents/skills/setting-up-rag/scripts"
        if (cand / "rag_lib.py").is_file():
            return cand
    raise RuntimeError("could not locate .agents/skills/setting-up-rag/scripts (rag_lib.py)")

_HEADING = re.compile(r"^[ \t]*(#{1,6})[ \t]+(.*)$")
_WORD = re.compile(r"\S+")
# light, language-agnostic symbol heuristic for code chunks (best-effort metadata)
_SYMBOL = re.compile(
    r"^[ \t]*(?:export\s+|public\s+|static\s+|inline\s+|virtual\s+|template<[^>]*>\s*)*"
    r"(?:class|struct|namespace|def|func|fn|function|interface|enum|"
    r"[A-Za-z_][\w:<>,&*\s]*?\b)([A-Za-z_]\w*)\s*[\(\{:]",
    re.MULTILINE,
)


@dataclass
class Chunk:
    raw_text: str
    start_byte: int
    end_byte: int
    start_line: int
    end_line: int
    heading_path: str
    symbol: str
    parent_start: int
    parent_end: int


def _line_index(text: str) -> list[int]:
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _line_of(line_starts: list[int], pos: int) -> int:
    import bisect

    return bisect.bisect_right(line_starts, pos)  # 1-based line number


def _word_count(s: str) -> int:
    return len(s.split())


def _window_spans(base_start: int, sub: str, size: int, overlap: int) -> list[tuple[int, int]]:
    """Char spans of word-windows over `sub` (offsets relative to base_start)."""
    words = list(_WORD.finditer(sub))
    if not words:
        return [(base_start, base_start + len(sub))]
    if len(words) <= size:
        return [(base_start + words[0].start(), base_start + words[-1].end())]
    step = max(1, size - overlap)
    spans = []
    for i in range(0, len(words), step):
        w = words[i:i + size]
        if not w:
            continue
        spans.append((base_start + w[0].start(), base_start + w[-1].end()))
    return spans


def _md_sections(text: str) -> list[tuple[int, int, str]]:
    """(start, end, heading_path) per heading-led section, headings nested by level."""
    lines = text.splitlines(keepends=True)
    sections: list[tuple[int, int, str]] = []
    stack: list[tuple[int, str]] = []  # (level, title)
    cur_start = 0
    cur_path = ""
    pos = 0
    started = False
    for ln in lines:
        m = _HEADING.match(ln)
        if m and started:
            sections.append((cur_start, pos, cur_path))
            cur_start = pos
        if m:
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, m.group(2).strip()))
            cur_path = " > ".join(t for _l, t in stack)
            cur_start = pos if not started else cur_start
            started = True
        pos += len(ln)
    sections.append((cur_start, pos, cur_path))
    return [s for s in sections if text[s[0]:s[1]].strip()]


def span_chunks(text: str, kind: str, cfg: dict) -> list[Chunk]:
    ch = cfg.get("chunker", {})
    line_starts = _line_index(text)

    def mk(s: int, e: int, hpath: str, p_start: int, p_end: int) -> Chunk:
        raw = text[s:e]
        sym = ""
        if kind == "code":
            m = _SYMBOL.search(raw)
            if m:
                sym = m.group(1)
        return Chunk(raw, s, e, _line_of(line_starts, s), _line_of(line_starts, max(s, e - 1)),
                     hpath, sym, p_start, p_end)

    out: list[Chunk] = []
    if kind == "code":
        size, overlap = int(ch.get("code_size", 120)), int(ch.get("code_overlap", 20))
        blocks = [(m.start(), m.end()) for m in re.finditer(r"[^\n].*?(?=\n\s*\n|\Z)", text, re.DOTALL)]
        buf: list[tuple[int, int]] = []
        nwords = 0
        groups: list[tuple[int, int]] = []
        for bs, be in blocks:
            bw = _word_count(text[bs:be])
            if nwords + bw > size and buf:
                groups.append((buf[0][0], buf[-1][1]))
                buf, nwords = [], 0
            buf.append((bs, be))
            nwords += bw
        if buf:
            groups.append((buf[0][0], buf[-1][1]))
        for gs, ge in groups:
            if _word_count(text[gs:ge]) > size:
                for ws, we in _window_spans(gs, text[gs:ge], size, overlap):
                    out.append(mk(ws, we, "", gs, ge))
            else:
                out.append(mk(gs, ge, "", gs, ge))
    else:  # md
        size = int(ch.get("size", 350))
        overlap = int(ch.get("overlap", 40))
        min_words = int(ch.get("min_words", 80))
        # merge tiny adjacent sections up to the min-words floor
        merged: list[tuple[int, int, str]] = []
        cur: tuple[int, int, str] | None = None
        for s, e, hp in _md_sections(text):
            if cur is None:
                cur = (s, e, hp)
            else:
                cur = (cur[0], e, cur[2])
            if _word_count(text[cur[0]:cur[1]]) >= min_words:
                merged.append(cur)
                cur = None
        if cur is not None:
            if merged:
                merged[-1] = (merged[-1][0], cur[1], merged[-1][2])
            else:
                merged.append(cur)
        for s, e, hp in merged:
            if _word_count(text[s:e]) > size:
                for ws, we in _window_spans(s, text[s:e], size, overlap):
                    out.append(mk(ws, we, hp, s, e))
            else:
                out.append(mk(s, e, hp, s, e))
    return out or [mk(0, len(text), "", 0, len(text))]


def _header_line(repo: str, path: str, c: Chunk, kind: str) -> str:
    loc = c.heading_path or c.symbol
    return f"[{repo}] {path}" + (f" :: {loc}" if loc else "") + f" ({kind})"


def contextual_text(repo: str, path: str, c: Chunk, kind: str, header: bool,
                    llm_ctx: str | None = None) -> str:
    """Build the retrieval/embedding field. Optional deterministic header (Wave-2 win)
    + optional LLM situating context (Wave-4 contextual retrieval) prepended to the
    verbatim chunk. With neither, returns raw_text (the plain baseline)."""
    head = _header_line(repo, path, c, kind) if header else ""
    if not head and not llm_ctx:
        return c.raw_text
    import wave4_context as W4  # lazy: keeps chunk-report stdlib-only when no LLM ctx
    return W4.compose_embedded(head, llm_ctx, c.raw_text)


# --- Wave-4 step 5: deterministic session metadata capsule (LLM-free) --------
# Transcripts (docs/transcripts/<date>/<NNNN>-<vendor>-<name>.md and
# llm-sessions-history/<date>/...) bury the session's identity + the files it touched
# inside a long User/Assistant turn stream; a chunk mid-transcript loses that anchor.
# This capsule (session tag + the mentioned-file list parsed from the WHOLE doc) is
# prepended to every chunk of the session. Purely deterministic -> portable-eligible.
_SESSION_RE = re.compile(
    r"(?:^|/)(?:transcripts|llm-sessions-history)/(\d{4}-\d{2}-\d{2})/"
    r"(\d{2,4})-([a-z]+)-(.+)\.md$")
_PATHTOKEN = re.compile(r"(?:[\w.\-]+/){1,}[\w.\-]+\.[A-Za-z]{1,5}\b")
_FILETOKEN = re.compile(
    r"\b[\w\-]+\.(?:py|cc|cpp|cu|cuh|h|hpp|ts|tsx|js|jsx|md|json|jsonc|ya?ml|toml|sh|cmake|rs|go)\b")


def _mentioned_files(text: str, cap: int = 10) -> list[str]:
    from collections import Counter

    c: Counter = Counter()
    for m in _PATHTOKEN.finditer(text):
        tok = m.group(0)
        if len(tok) <= 80 and "://" not in tok:
            c[tok] += 1
    if len(c) < cap:  # backfill with bare filenames when few full paths are present
        for m in _FILETOKEN.finditer(text):
            c[m.group(0)] += 1
    return [f for f, _n in c.most_common(cap)]


def session_capsule(path: str, text: str) -> str | None:
    """`session <idx> <vendor> <date> — <name>; files: a.py, b.cc, …` or None (not a transcript)."""
    m = _SESSION_RE.search(path)
    if not m:
        return None
    date, idx, vendor, name = m.groups()
    cap = f"session {idx} {vendor} {date} — {name.replace('-', ' ')}"
    files = _mentioned_files(text)
    if files:
        cap += "; files: " + ", ".join(files)
    return cap


def doc_points(repo: str, path: str, kind: str, lang: str, text: str, cfg: dict,
               header: bool, llm_cache: dict | None = None,
               apply_to: tuple[str, ...] = ("md", "code"),
               d2q_cache: dict | None = None, d2q_apply_to: tuple[str, ...] = ("md", "code"),
               d2q_field: str = "sparse", session_meta: dict | None = None) -> list[dict]:
    chunks = span_chunks(text, kind, cfg)
    n = len(chunks)
    # Wave-4 step 5: per-doc session capsule (deterministic; same for every chunk of the doc).
    sess_cap = session_capsule(path, text) if (session_meta and session_meta.get("enabled")) else None
    points = []
    for i, c in enumerate(chunks):
        ck = f"{path}\t{c.start_byte}\t{c.end_byte}"  # == wave4_context.chunk_key
        llm_ctx = (llm_cache.get(ck) or None) if (llm_cache is not None and kind in apply_to) else None
        if llm_ctx is None and sess_cap:  # deterministic capsule reuses the situating-context slot
            llm_ctx = sess_cap
        ctx = contextual_text(repo, path, c, kind, header, llm_ctx)
        # Wave-4 Doc2Query: predicted queries expand the LEXICAL field only (field="sparse")
        # so code identifiers/dense are untouched, OR both fields (field="both").
        d2q = (d2q_cache.get(ck) or None) if (d2q_cache is not None and kind in d2q_apply_to) else None
        pt = {
            "repo": repo, "kind": kind, "lang": lang,
            "doc_id": path, "path": path,
            "heading_path": c.heading_path, "symbol": c.symbol,
            "parent_id": f"{path}#parent@{c.parent_start}",
            "chunk_idx": i, "n_chunks": n,
            "start_byte": c.start_byte, "end_byte": c.end_byte,
            "start_line": c.start_line, "end_line": c.end_line,
            "parent_start": c.parent_start, "parent_end": c.parent_end,
            "raw_text": c.raw_text,
            "contextualized_text": ctx,
            "text": ctx,  # retrieval/display field (shipped query.py reads "text")
        }
        if d2q:
            exp = d2q.strip()
            if d2q_field == "both":
                pt["contextualized_text"] = pt["text"] = f"{ctx}\n{exp}"
                pt["bm25_text"] = f"{ctx}\n{exp}"
            else:  # sparse-only (faithful Doc2Query: lexical expansion, dense stays clean)
                pt["bm25_text"] = f"{ctx}\n{exp}"
        points.append(pt)
    return points


# --- indexing (needs the FastEmbed/Qdrant venv) -----------------------------
def index_repo(repo_name: str, collection: str, cfg: dict, kinds: tuple[str, ...],
               header: bool, force_local: bool, batch: int = 256) -> dict:
    sys.path.insert(0, str(_skill_scripts_dir()))
    import rag_lib as R  # the shipped stack (FastEmbed + Qdrant)
    from snowflake import Snowflake
    from qdrant_client import models

    repo = M.REPOS[repo_name]
    corpus = M.load_repo_corpus(repo, kinds=kinds)
    # Wave-4 contextual retrieval: load this repo's cached LLM situating contexts.
    cl = cfg.get("contextual_llm", {})
    llm_cache = None
    apply_to: tuple[str, ...] = ("md", "code")
    if cl.get("enabled"):
        import wave4_context as W4
        llm_cache = W4.load_cache(cl["model"], repo_name)
        apply_to = tuple(cl.get("apply_to", ["md", "code"]))
    # Wave-4 Doc2Query: load this repo's cached predicted-query expansions (lexical field).
    dq = cfg.get("doc2query", {})
    d2q_cache = None
    d2q_apply_to: tuple[str, ...] = ("md", "code")
    d2q_field = dq.get("field", "sparse")
    if dq.get("enabled"):
        import wave4_doc2query as D2Q
        d2q_cache = D2Q.load_cache(dq["model"], repo_name)
        d2q_apply_to = tuple(dq.get("apply_to", ["md", "code"]))
    session_meta = cfg.get("session_meta")  # Wave-4 step 5: deterministic transcript capsule
    all_points: list[dict] = []
    for path, payload in corpus.items():
        all_points.extend(doc_points(repo_name, path, payload["kind"], payload["lang"],
                                     payload["text"], cfg, header, llm_cache, apply_to,
                                     d2q_cache, d2q_apply_to, d2q_field, session_meta))
    if not all_points:
        sys.exit(f"enriched_index: no chunks for {repo_name} (kinds={kinds})")
    if llm_cache is not None:
        keyset = {k for k in llm_cache if k != "__meta__" and llm_cache[k]}
        covered = sum(1 for p in all_points if p["kind"] in apply_to
                      and f"{p['path']}\t{p['start_byte']}\t{p['end_byte']}" in keyset)
        eligible = sum(1 for p in all_points if p["kind"] in apply_to)
        print(f"enriched_index: contextual_llm={cl['model']} apply_to={','.join(apply_to)} "
              f"coverage={covered}/{eligible} eligible chunks")

    client, where = R.get_client(force_local=force_local)
    emb = cfg["embedding"]
    # Wave-4 late chunking (LLM-free contextual embedding): dense vectors are
    # precomputed on GPU by wave4_latechunk (naive per-chunk vs late whole-doc pooling)
    # and loaded here; sparse/BM25 + the deterministic header path are unchanged, so the
    # ONLY variable vs the FastEmbed arms is the dense doc vector. See wave4_latechunk.py.
    ds = emb.get("dense_source")
    lc_doc = None
    if ds and ds.get("kind") == "latechunk":
        import wave4_latechunk as LC
        lc_doc = LC.load_doc_cache(ds.get("model", LC.MODEL_TAG), ds["mode"], repo_name)
    if client.collection_exists(collection):
        client.delete_collection(collection)
    client.create_collection(
        collection,
        vectors_config={"dense": models.VectorParams(
            size=int(emb["dense_dim"]),
            distance=getattr(models.Distance, emb.get("distance", "cosine").upper()))},
        sparse_vectors_config={"sparse": models.SparseVectorParams(
            modifier=models.Modifier.IDF if "bm25" in emb["sparse_model"].lower()
            or "bm42" in emb["sparse_model"].lower() else None)},
    )
    sf = Snowflake()
    n = len(all_points)
    print(f"enriched_index: {len(corpus)} docs -> {n} chunks -> '{collection}' ({where}) header={header}")
    for start in range(0, n, batch):
        chunk_payloads = all_points[start:start + batch]
        # dense embeds the (header[+llm-ctx]) field; sparse/BM25 embeds bm25_text when a
        # Doc2Query expansion exists for that chunk (else the same field). Splitting the two
        # texts is what lets Doc2Query expand the lexical arm without touching dense.
        dense_texts = [p["contextualized_text"] for p in chunk_payloads]
        sparse_texts = [p.get("bm25_text", p["contextualized_text"]) for p in chunk_payloads]
        if lc_doc is not None:  # late-chunk dense from cache
            import wave4_latechunk as LC
            dense = [lc_doc[LC.chunk_key(p["path"], p["start_byte"], p["end_byte"])].tolist()
                     for p in chunk_payloads]
        else:
            dense = [v.tolist() for v in R._dense(emb["dense_model"]).embed(dense_texts)]
        sparse = list(R._sparse(emb["sparse_model"]).embed(sparse_texts))
        pts = [models.PointStruct(
            id=sf.next_id(),
            vector={"dense": dense[j], "sparse": R.to_sparse_vector(sparse[j])},
            payload=chunk_payloads[j],
        ) for j in range(len(chunk_payloads))]
        client.upsert(collection, points=pts)
        print(f"  upserted {min(start + batch, n)}/{n}")
    return {"repo": repo_name, "collection": collection, "docs": len(corpus), "chunks": n}


# --- stdlib-only chunk report + chunker self-test ---------------------------
def cmd_chunk_report(args) -> int:
    """Chunk a repo (or one file), print stats, and ASSERT chunk integrity:
    raw_text is a verbatim source slice, and every gold sentinel for the repo is
    contained whole within some chunk's raw_text (a sentinel split across a chunk
    boundary would be unfindable — a chunking-granularity finding for Wave 2)."""
    cfg = _load_cfg(args.config)
    repo = M.REPOS[args.repo]
    base = Path(repo.root)
    corpus = M.load_repo_corpus(repo)
    total_chunks = 0
    verbatim_ok = True
    for path, payload in corpus.items():
        pts = doc_points(args.repo, path, payload["kind"], payload["lang"], payload["text"], cfg, args.contextual_header)
        total_chunks += len(pts)
        for p in pts:
            if payload["text"][p["start_byte"]:p["end_byte"]] != p["raw_text"]:
                verbatim_ok = False
                print(f"  [VERBATIM FAIL] {path}#{p['chunk_idx']}")
    # sentinel containment within a single chunk
    qs = [q for q in G.load_questions() if q.repo == args.repo]
    chunk_cache: dict[str, list[dict]] = {}
    split_sentinels = []
    for q in qs:
        for p in q.primary:
            if p not in corpus:
                continue
            if p not in chunk_cache:
                chunk_cache[p] = doc_points(args.repo, p, corpus[p]["kind"], corpus[p]["lang"],
                                            corpus[p]["text"], cfg, False)
            for s in q.sentinels:
                if s not in corpus[p]["text"]:
                    continue  # belongs to a different primary
                if not any(s in c["raw_text"] for c in chunk_cache[p]):
                    split_sentinels.append((q.id, p, s))
    print(f"repo={args.repo} docs={len(corpus)} chunks={total_chunks} "
          f"avg_chunks/doc={total_chunks/max(1,len(corpus)):.1f} verbatim_ok={verbatim_ok}")
    if split_sentinels:
        print(f"  WARNING: {len(split_sentinels)} sentinel(s) split across chunk boundaries "
              f"(unfindable at this chunk size — Wave-2 chunking finding):")
        for qid, p, s in split_sentinels[:15]:
            print(f"    {qid}  {p}  {s!r}")
    else:
        print("  sentinel containment: OK (every gold sentinel fits within one chunk)")
    return 0 if (verbatim_ok and not split_sentinels) else 1


def _load_cfg(path: str | None) -> dict:
    import json

    if path:
        return json.loads(Path(path).read_text())
    # default = shipped rag-config (the plain-current baseline)
    return json.loads((_skill_scripts_dir() / "rag-config.json").read_text())


def cmd_index(args) -> int:
    cfg = _load_cfg(args.config)
    kinds = tuple(args.kinds.split(",")) if args.kinds else ("md", "code")
    stats = index_repo(args.repo, args.collection, cfg, kinds, args.contextual_header, args.local)
    print(f"enriched_index: done {stats}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="rag-config.json (default: shipped plain-current)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("chunk-report", help="stdlib-only: chunk stats + verbatim/sentinel self-test")
    pr.add_argument("--repo", required=True, choices=list(M.REPOS))
    pr.add_argument("--contextual-header", action="store_true")
    pr.set_defaults(func=cmd_chunk_report)
    pi = sub.add_parser("index", help="embed + upsert into Qdrant (needs venv)")
    pi.add_argument("--repo", required=True, choices=list(M.REPOS))
    pi.add_argument("--collection", required=True)
    pi.add_argument("--kinds", help="comma list, e.g. code or md,code (default md,code)")
    pi.add_argument("--contextual-header", action="store_true")
    pi.add_argument("--local", action="store_true", help="force embedded Qdrant")
    pi.set_defaults(func=cmd_index)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
