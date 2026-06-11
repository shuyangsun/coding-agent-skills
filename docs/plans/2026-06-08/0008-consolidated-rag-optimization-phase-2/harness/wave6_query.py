#!/usr/bin/env python3
"""wave6_query.py — Wave-6 query routing & adaptive retrieval (plan 0008 §"Wave 6").

Three deterministic pieces (stdlib only, used by run_benchmark at query time):

  * router FEATURES over the query text (step 1) — identifier density, path
    mentions, multipart markers. The 0020-TSV mining showed query-TEXT features do
    NOT separate rerank-helped from rerank-hurt queries (identical length/identifier
    stats), so text features only GATE transforms; rerank gating uses retrieval-state
    confidence below.
  * SELF-QUERY soft-filter extraction (step 2) — high-precision lang/kind/path
    triggers only. Applied as an extra *rank-fused list* (weighted RRF), never an
    additive score boost (the Wave-5 lesson: additive boosts on RRF's flat rank-score
    curve leapfrog dozens of ranks).
  * first-pass retrieval CONFIDENCE features (step 5, CRAG-style) — dense/sparse
    top-file agreement, fused-head concentration, dense score gap. Basis for the
    confidence-gated reranker: 0020 mining shows rerank helps weak first-pass queries
    (base pMRR 0.33) and hurts strong ones (0.69; 37/70 hurt cases had the primary at
    rank 1), so a query-time confidence signal is the missing piece.

One generative piece (OpenAI SDK, campaign venv): query TRANSFORMS (decomposition /
multi-query / HyDE — steps 3-4), generated once per gold query and cached on disk so
the benchmark runner NEVER calls the network. Deterministic decomposition
(sentence/conjunction split) is the LLM-free control arm.

Cache: $WAVE6_CACHE/<model_slug>/<kind>.json   (default ~/.cache/rag-skill/wave6-query)
    { "<query_id>": ["subquery", ...], ..., "__meta__": {...} }

CLI:
    wave6_query.py generate --kind decomp --model model --cache-model nemotron \
        --base-url http://127.0.0.1:8085/v1 --no-think [--workers 8] [--limit N]
    wave6_query.py stats  --cache-model nemotron
    wave6_query.py sample --cache-model nemotron --kind decomp [-n 6]
    wave6_query.py features          # per-query router-feature TSV to stdout
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

_HARNESS = Path(__file__).resolve().parent
sys.path.insert(0, str(_HARNESS))

PROMPT_VERSION = "w6-v1"

# --- router features (step 1) --------------------------------------------------
# identifier-shaped tokens: snake/dotted/scoped/camelCase, backticked spans, file exts
_IDENT = re.compile(
    r"`[^`]+`|[A-Za-z_][A-Za-z0-9_]*(?:[_.:]{1,2}[A-Za-z0-9_]+)+|\b[a-z]+[A-Z][A-Za-z0-9]*\b")
_PATHY = re.compile(
    r"[\w.-]+/[\w./-]+|\b[\w-]+\.(?:py|cc|cpp|h|hpp|cu|cuh|ts|tsx|js|md|sh|json|yml|yaml|toml|txt|cmake)\b")
_MULTI = re.compile(r"\band\b|\bvs\.?\b|difference between|\bboth\b|\beach of\b|\btwo\b"
                    r"|, and | as well as |\balso\b", re.I)
_QMARK = re.compile(r"\?")


def query_features(text: str) -> dict:
    toks = text.split()
    idents = _IDENT.findall(text)
    paths = _PATHY.findall(text)
    multi_hits = _MULTI.findall(text)
    n_q = len(_QMARK.findall(text))
    return {
        "len_w": len(toks),
        "n_ident": len(idents),
        "n_path": len(paths),
        "n_multi": len(multi_hits),
        "n_qmark": n_q,
        "has_exact_token": bool(idents or paths),
        # multipart: several conjunction markers on a long query, or 2+ questions
        "multipart": (len(multi_hits) >= 2 and len(toks) > 25) or n_q >= 2,
    }


def gate_triggers(gate: str, feats: dict) -> bool:
    """Whether a transform applies to this query. Gates are deterministic and
    query-text-only (the router never sees gold labels):
      all       — every query
      multipart — decomposition's target population (~26% of the gold set)
      no-ident  — queries WITHOUT exact identifier/path tokens (protects exact
                  lexical signals from dilution — the plan's HyDE/multi-query rule)
    """
    if gate == "all":
        return True
    if gate == "multipart":
        return bool(feats["multipart"])
    if gate == "no-ident":
        return not feats["has_exact_token"]
    raise ValueError(f"unknown transform gate: {gate}")


# --- self-query soft filters (step 2) -------------------------------------------
# High-precision triggers only (scan: lang 8% / kind 10% / path 9% of gold queries).
# Values match the enriched-index payload: kind in {md, code}; lang per
# corpus_manifest.LANG_BY_EXT.
_LANG_TRIGGERS: list[tuple[re.Pattern, tuple[str, ...]]] = [
    (re.compile(r"\bpython\b|\.py\b", re.I), ("python",)),
    (re.compile(r"c\+\+|\.cc\b|\.cpp\b|\.hpp\b", re.I), ("cpp", "c", "cuda")),
    (re.compile(r"\bcuda\b|\.cuh?\b", re.I), ("cuda", "cpp")),
    (re.compile(r"\btypescript\b|\.tsx?\b|\breact\b", re.I), ("typescript", "javascript")),
    (re.compile(r"\bshell script\b|\bbash\b|\.sh\b", re.I), ("shell",)),
    (re.compile(r"\bcmake\b|CMakeLists", re.I), ("cmake",)),
    (re.compile(r"\.ya?ml\b|\byaml\b", re.I), ("yaml",)),
]
_KIND_TRIGGERS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\btranscripts?\b|\bcoding[- ]sessions?\b|\bsession (?:history|transcript)", re.I), "md"),
    (re.compile(r"\breadme\b|\bdesign docs?\b|\bdocumentation\b", re.I), "md"),
]
_PATH_TOKEN = re.compile(r"[\w.-]+/[\w./-]+|\b[\w-]+\.(?:py|cc|cpp|h|hpp|cu|cuh|ts|tsx|js|md|sh|json|yml|yaml|cmake)\b")


def selfquery_filter(text: str) -> dict:
    """Extract a soft filter from the query. Returns {} when nothing fires.
    Keys: lang -> tuple of payload lang values; kind -> "md"; path_tokens -> list of
    lowercase substrings to match against payload path (client-side subsequence)."""
    out: dict = {}
    langs: list[str] = []
    for pat, vals in _LANG_TRIGGERS:
        if pat.search(text):
            for v in vals:
                if v not in langs:
                    langs.append(v)
    if langs:
        out["lang"] = tuple(langs)
    for pat, kind in _KIND_TRIGGERS:
        if pat.search(text):
            out["kind"] = kind
            break
    toks = [t.lower() for t in _PATH_TOKEN.findall(text)]
    if toks:
        out["path_tokens"] = toks[:4]
    return out


# --- first-pass confidence features (step 5, CRAG-style gate) -------------------
def confidence_features(dense_hits, sparse_hits, fused_hits) -> dict:
    """Query-time-computable retrieval-state confidence. dense/sparse hits come from
    the two single-arm searches (with scores); fused_hits is the candidate list the
    arm will actually use. All file-level (doc_id)."""
    def files(hits, k):
        out = []
        for h in hits:
            d = h.payload.get("doc_id")
            if d and d not in out:
                out.append(d)
            if len(out) >= k:
                break
        return out

    d10, s10 = files(dense_hits, 10), files(sparse_hits, 10)
    agree10 = len(set(d10) & set(s10))
    fused_docs = [h.payload.get("doc_id") for h in fused_hits[:10]]
    head_share = (fused_docs.count(fused_docs[0]) / len(fused_docs)) if fused_docs else 0.0
    nfiles10 = len(set(fused_docs)) if fused_docs else 0
    dscores = [float(h.score) for h in dense_hits[:5] if h.score is not None]
    return {
        "agree10": agree10,
        "head_share": round(head_share, 4),
        "nfiles10": nfiles10,
        "d_top": round(dscores[0], 4) if dscores else 0.0,
        "d_gap": round(dscores[0] - dscores[-1], 4) if len(dscores) >= 2 else 0.0,
        "s_top": round(float(sparse_hits[0].score), 4) if sparse_hits and sparse_hits[0].score is not None else 0.0,
    }


def gate_decision(gate_cfg: dict, conf: dict) -> bool:
    """True => RERANK this query. Generic OR-combination over `max_<feature>` /
    `min_<feature>` conditions on the confidence features; thresholds are fitted on
    dev rows (wave6_fit_gate.py over route.feat) and frozen in the arm config before
    any held-out run. NOTE the fitted directions are not all 'low confidence': dev
    shows rerank helps when dense+sparse AGREE (min_agree10) — a good candidate pool
    to arbitrate — and when the dense head is weak/flat (max_d_top / max_d_gap)."""
    hit = False
    for key, thr in gate_cfg.items():
        if key == "log_only":
            continue
        feat = key[4:]
        if feat not in conf:
            continue
        if key.startswith("max_"):
            hit = hit or conf[feat] <= float(thr)
        elif key.startswith("min_"):
            hit = hit or conf[feat] >= float(thr)
    return hit


# --- deterministic decomposition (LLM-free control, step 3) ---------------------
_SENT_SPLIT = re.compile(r"(?<=[.?])\s+(?=[A-Z])")
_AND_SPLIT = re.compile(r",?\s+\band\b\s+", re.I)


def decompose_det(text: str, max_sub: int = 3) -> list[str]:
    """Sentence-first, then one top-level 'and' split when both halves are
    substantial. Returns [] when the query doesn't decompose."""
    parts = [p.strip() for p in _SENT_SPLIT.split(text.strip()) if p.strip()]
    if len(parts) == 1:
        halves = _AND_SPLIT.split(parts[0])
        if len(halves) >= 2 and all(len(h.split()) >= 5 for h in halves):
            parts = [h.strip(" ,") for h in halves]
        else:
            return []
    subs = [p if p.endswith("?") else p for p in parts if len(p.split()) >= 4]
    return subs[:max_sub] if len(subs) >= 2 else []


# --- LLM transforms (steps 3-4): generation + cache ------------------------------
_SYS = ("You rewrite search queries for a code-and-docs retrieval system over a "
        "software repository. Follow the output format EXACTLY: plain lines, no "
        "numbering, no bullets, no commentary, no markdown.")

_PROMPTS = {
    "decomp": (
        "Decompose this question about the repository '{repo}' into 2-4 standalone "
        "search queries, each targeting ONE distinct fact, file, or step needed to "
        "answer it. Preserve every code identifier, file name, path, and quoted "
        "string VERBATIM. Each line must be a self-contained query (repeat the "
        "subject; no pronouns referring to other lines).\n\nQuestion: {q}\n\n"
        "Output: one query per line (2-4 lines)."),
    "multiquery": (
        "Rewrite this question about the repository '{repo}' in 3 alternative ways "
        "a developer might phrase it, varying vocabulary and angle. Preserve every "
        "code identifier, file name, path, and quoted string VERBATIM.\n\n"
        "Question: {q}\n\nOutput: one rewrite per line (exactly 3 lines)."),
    "hyde": (
        "Write a short hypothetical excerpt (3-5 sentences, ~80 words) that could "
        "appear in the repository '{repo}''s documentation, comments, or code and "
        "would directly answer this question. Use concrete, plausible technical "
        "detail and the question's own identifiers verbatim. No hedging, no "
        "markdown.\n\nQuestion: {q}\n\nOutput: the excerpt only."),
}
KINDS = tuple(_PROMPTS)


def model_slug(model: str) -> str:
    return "".join(c if (c.isalnum() or c in "-._") else "_" for c in model)


def cache_root() -> Path:
    return Path(os.environ.get(
        "WAVE6_CACHE",
        str(Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
            / "rag-skill" / "wave6-query"))).expanduser()


def cache_path(cache_model: str, kind: str) -> Path:
    return cache_root() / model_slug(cache_model) / f"{kind}.json"


def load_cache(cache_model: str, kind: str) -> dict:
    p = cache_path(cache_model, kind)
    if p.is_file():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _save_cache(cache_model: str, kind: str, data: dict) -> None:
    p = cache_path(cache_model, kind)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=0))
    tmp.replace(p)


def lookup(cache_model: str, kind: str, qid: str) -> list[str]:
    """Runner-side cache read. Loud failure on a miss — the runner must never
    silently fall back (a half-cached arm would mix transformed and plain queries)."""
    cache = _CACHE_MEM.setdefault((cache_model, kind), load_cache(cache_model, kind))
    if qid not in cache:
        raise KeyError(
            f"wave6 transform cache miss: model={cache_model} kind={kind} qid={qid} "
            f"— run wave6_query.py generate first")
    return cache[qid]


_CACHE_MEM: dict = {}


def _parse_lines(out: str, kind: str, original: str) -> list[str]:
    if kind == "hyde":
        text = " ".join(out.split())
        return [text] if text else []
    lines = []
    for ln in out.splitlines():
        ln = ln.strip().lstrip("-*•").strip()
        ln = re.sub(r"^\d+[.)]\s*", "", ln)
        if not ln or ln.lower() == original.lower():
            continue
        if ln not in lines:
            lines.append(ln)
    cap = 4 if kind == "decomp" else 3
    return lines[:cap]


def _gen_one(client, model: str, kind: str, repo: str, q: str, max_tokens: int,
             extra_body: dict | None, retries: int = 4) -> list[str]:
    msgs = [{"role": "system", "content": _SYS},
            {"role": "user", "content": _PROMPTS[kind].format(repo=repo, q=q)}]
    kw = {"extra_body": extra_body} if extra_body else {}
    last = ""
    for attempt in range(retries):
        try:
            r = client.chat.completions.create(model=model, messages=msgs,
                                               max_tokens=max_tokens, temperature=0.0, **kw)
            return _parse_lines((r.choices[0].message.content or "").strip(), kind, q)
        except Exception as exc:  # noqa: BLE001 — network/serving hiccups: backoff
            last = str(exc)
            time.sleep(min(2 ** attempt, 8))
    print(f"    [warn] gen failed kind={kind} q={q[:60]!r}: {last[:160]}", file=sys.stderr)
    return []


def cmd_generate(args) -> int:
    import gold_loader as G
    from openai import OpenAI
    from concurrent.futures import ThreadPoolExecutor

    cache_model = args.cache_model or args.model
    kinds = list(KINDS) if args.kind == "all" else args.kind.split(",")
    extra_body = json.loads(args.extra_body) if args.extra_body else None
    if args.no_think:
        extra_body = {**(extra_body or {}), "chat_template_kwargs": {"enable_thinking": False}}
    client = OpenAI(base_url=args.base_url,
                    api_key=args.api_key or os.environ.get("LITELLM_API_KEY", "x"))
    questions = G.load_questions()
    for kind in kinds:
        cache = load_cache(cache_model, kind)
        meta = cache.get("__meta__", {})
        if meta and meta.get("prompt_version") != PROMPT_VERSION:
            print(f"  [reset] {kind}: prompt changed -> regenerating", file=sys.stderr)
            cache = {}
        todo = [q for q in questions if q.id not in cache]
        if args.limit:
            todo = todo[: args.limit]
        print(f"  {kind}: {len(questions)} queries, {len(cache) - bool(cache.get('__meta__'))} "
              f"cached, {len(todo)} to generate")
        t0 = time.time()
        done = 0

        def work(q):
            return q.id, _gen_one(client, args.model, kind, q.repo, q.question,
                                  args.max_tokens, extra_body)

        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            for qid, subs in ex.map(work, todo):
                # store [] too — the runner treats an empty entry as "transform does
                # not apply" (vs a MISSING entry, which is a loud config error)
                cache[qid] = subs
                done += 1
                if done % 25 == 0:
                    cache["__meta__"] = {"prompt_version": PROMPT_VERSION,
                                         "cache_model": cache_model, "api_model": args.model}
                    _save_cache(cache_model, kind, cache)
                    rate = done / (time.time() - t0)
                    print(f"    {done}/{len(todo)}  {rate:.1f} q/s", flush=True)
        cache["__meta__"] = {"prompt_version": PROMPT_VERSION,
                             "cache_model": cache_model, "api_model": args.model}
        _save_cache(cache_model, kind, cache)
        n_missing = sum(1 for q in questions if q.id not in cache)
        print(f"  {kind}: done in {time.time()-t0:.0f}s, {n_missing} missing, "
              f"cache -> {cache_path(cache_model, kind)}")
    return 0


def cmd_stats(args) -> int:
    import gold_loader as G
    questions = G.load_questions()
    for kind in KINDS:
        cache = load_cache(args.cache_model, kind)
        keys = [k for k in cache if k != "__meta__"]
        missing = sum(1 for q in questions if q.id not in cache)
        n_sub = [len(cache[k]) for k in keys]
        avg = sum(n_sub) / len(n_sub) if n_sub else 0
        print(f"  {kind:10s} cached={len(keys):3d} missing={missing:3d} avg_n={avg:.1f} "
              f"meta={cache.get('__meta__', {}).get('api_model', '?')}")
    return 0


def cmd_sample(args) -> int:
    import gold_loader as G
    questions = {q.id: q for q in G.load_questions()}
    cache = load_cache(args.cache_model, args.kind)
    shown = 0
    for qid, subs in cache.items():
        if qid == "__meta__":
            continue
        q = questions.get(qid)
        print(f"--- {qid}  [{q.repo if q else '?'}]")
        print(f"  Q: {q.question if q else '?'}")
        for s in subs:
            print(f"   > {s}")
        shown += 1
        if shown >= args.n:
            break
    return 0


def cmd_features(args) -> int:
    import gold_loader as G
    cols = ["qid", "repo", "domain", "split", "len_w", "n_ident", "n_path", "n_multi",
            "n_qmark", "has_exact_token", "multipart", "sq_lang", "sq_kind", "sq_path"]
    print("\t".join(cols))
    n_multi = n_sq = 0
    for q in G.load_questions():
        f = query_features(q.question)
        sq = selfquery_filter(q.question)
        n_multi += f["multipart"]
        n_sq += bool(sq)
        print("\t".join(str(x) for x in [
            q.id, q.repo, q.domain, q.split, f["len_w"], f["n_ident"], f["n_path"],
            f["n_multi"], f["n_qmark"], int(f["has_exact_token"]), int(f["multipart"]),
            ",".join(sq.get("lang", ())), sq.get("kind", ""),
            ",".join(sq.get("path_tokens", []))]))
    print(f"# multipart={n_multi}  selfquery_triggered={n_sq}", file=sys.stderr)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate + cache query transforms via an LLM")
    g.add_argument("--kind", default="all", help="decomp|multiquery|hyde|all|comma list")
    g.add_argument("--model", required=True, help="API model name sent to the endpoint")
    g.add_argument("--cache-model", default=None, help="cache namespace; default = --model")
    g.add_argument("--base-url", default=os.environ.get("OPENAI_API_BASE",
                                                        "https://llm.shuyangsun.com/v1"))
    g.add_argument("--api-key", default=None)
    g.add_argument("--workers", type=int, default=8)
    g.add_argument("--max-tokens", type=int, default=300)
    g.add_argument("--limit", type=int, default=None)
    g.add_argument("--no-think", action="store_true")
    g.add_argument("--extra-body", default=None)
    g.set_defaults(func=cmd_generate)

    s = sub.add_parser("stats", help="cache coverage per kind")
    s.add_argument("--cache-model", required=True)
    s.set_defaults(func=cmd_stats)

    sp = sub.add_parser("sample", help="print a few cached transforms")
    sp.add_argument("--cache-model", required=True)
    sp.add_argument("--kind", default="decomp")
    sp.add_argument("-n", type=int, default=6)
    sp.set_defaults(func=cmd_sample)

    f = sub.add_parser("features", help="per-query router-feature TSV")
    f.set_defaults(func=cmd_features)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
