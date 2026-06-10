#!/usr/bin/env python3
"""wave4_doc2query.py — Doc2Query / document expansion generator (Wave 4, step 4).

Wave 4, step 4 of ``0008-consolidated-rag-optimization-phase-2.md``: use the local LLM
to predict, per chunk, a few search queries the chunk answers (docTTTTTquery / Doc2Query),
and add them to a SEPARATE lexical field so code identifiers are not crowded out. The
expansion bridges vocabulary mismatch (a query phrasing the doc never uses) for the BM25
arm without touching the dense vector or the verbatim ``raw_text``.

Mirrors ``wave4_context.py``'s generate/cache split:
  * GENERATION (campaign venv / OpenAI SDK): one LLM call per chunk -> N predicted queries,
    cached on disk keyed by (path, byte-span) so a chunker change can't silently misalign.
  * INDEXING (FastEmbed/Qdrant venv): ``enriched_index`` reads the cache and appends the
    queries to a ``bm25_text`` field (sparse input only) OR to ``contextualized_text``
    (dense+sparse), per the arm's ``doc2query.field`` ("sparse" | "both").

The plan's hypothesis is PROSE-ONLY expansion (``apply_to=["md"]``); we generate for all
kinds so the all-chunks vs prose-only ablation (mirroring 0014's "code-dilution was wrong"
finding) can be scored without regenerating.

Cache: $DOC2QUERY_CACHE/<model_slug>/<repo>.json  (default ~/.cache/rag-skill/wave4-doc2query)
    { "<path>\\t<sb>\\t<eb>": "q1\\nq2\\nq3", ..., "__meta__": {...} }
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_HARNESS = Path(__file__).resolve().parent
sys.path.insert(0, str(_HARNESS))
import corpus_manifest as M  # noqa: E402
import enriched_index as E  # noqa: E402
import wave4_context as W4C  # noqa: E402  (reuse client/window/chunker-sig helpers)

PROMPT_VERSION = "d2q-v1"
DEFAULT_N = 4

_SYS = ("You expand a document passage for a search index by predicting the queries it "
        "answers. Output ONLY the queries, one per line: no numbering, no preamble, no "
        "markdown, no explanation. Use varied vocabulary and include both natural-language "
        "questions and short keyword phrases. Preserve exact identifiers/symbols verbatim.")
_USER = """<passage repo="{repo}" path="{path}">
{chunk}
</passage>

Write {n} diverse search queries that this passage directly answers \
(varied phrasing; mix questions and keyword phrases). One per line, nothing else."""


def cache_root() -> Path:
    return Path(os.environ.get(
        "DOC2QUERY_CACHE",
        str(Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
            / "rag-skill" / "wave4-doc2query"))).expanduser()


def cache_path(model: str, repo: str) -> Path:
    return cache_root() / W4C.model_slug(model) / f"{repo}.json"


def load_cache(model: str, repo: str) -> dict:
    p = cache_path(model, repo)
    if p.is_file():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _save_cache(model: str, repo: str, data: dict) -> None:
    p = cache_path(model, repo)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=0))
    tmp.replace(p)


def compose_bm25(base_text: str, queries: str | None) -> str:
    """Append predicted queries to the lexical field (BM25 input). raw_text/dense untouched."""
    q = (queries or "").strip()
    return f"{base_text}\n{q}" if q else base_text


def _clean(out: str, n: int) -> str:
    lines = []
    for ln in out.splitlines():
        s = ln.strip().lstrip("-*0123456789.)# ").strip()
        if s:
            lines.append(s)
    return "\n".join(lines[:n])


def gen_one(client, model, repo, path, chunk, n, max_tokens, retries=4, extra_body=None) -> str:
    msgs = [{"role": "system", "content": _SYS},
            {"role": "user", "content": _USER.format(repo=repo, path=path, n=n,
                                                      chunk=chunk[:W4C.DEFAULT_MAX_CHUNK_CHARS])}]
    kw = {"extra_body": extra_body} if extra_body else {}
    last = ""
    for attempt in range(retries):
        try:
            r = client.chat.completions.create(model=model, messages=msgs,
                                               max_tokens=max_tokens, temperature=0.0, **kw)
            return _clean((r.choices[0].message.content or "").strip(), n)
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
            time.sleep(min(2 ** attempt, 8))
    print(f"    [warn] d2q failed {path}: {last[:160]}", file=sys.stderr)
    return ""


def generate_for_repo(repo, cfg, model, base_url, api_key, apply_to, workers, n,
                      max_tokens, limit, extra_body=None, cache_model=None) -> dict:
    cache_model = cache_model or model
    corpus = M.load_repo_corpus(M.REPOS[repo], kinds=("md", "code"))
    cache = load_cache(cache_model, repo)
    meta = cache.get("__meta__", {})
    if meta and (meta.get("chunker") != W4C.chunker_sig(cfg) or meta.get("prompt_version") != PROMPT_VERSION):
        print(f"  [reset] {repo}: chunker/prompt changed -> regenerating", file=sys.stderr)
        cache = {}
    tasks = []
    for path in sorted(corpus):
        payload = corpus[path]
        if payload["kind"] not in apply_to:
            continue
        for c in E.span_chunks(payload["text"], payload["kind"], cfg):
            k = W4C.chunk_key(path, c.start_byte, c.end_byte)
            if k not in cache:
                tasks.append((k, path, c.raw_text))
    if limit:
        tasks = tasks[:limit]
    have = len([k for k in cache if k != "__meta__"])
    print(f"  {repo}: {len(corpus)} docs, {have} cached, {len(tasks)} to generate (apply_to={','.join(apply_to)})")
    if not tasks:
        return {"repo": repo, "generated": 0, "cached": have}
    client = W4C._client(base_url, api_key)
    done = 0
    t0 = time.time()

    def work(task):
        k, path, chunk = task
        return k, gen_one(client, model, repo, path, chunk, n, max_tokens, extra_body=extra_body)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for k, q in ex.map(work, tasks):
            if q:
                cache[k] = q
            done += 1
            if done % 100 == 0:
                cache["__meta__"] = {"chunker": W4C.chunker_sig(cfg), "prompt_version": PROMPT_VERSION,
                                     "cache_model": cache_model, "api_model": model, "n": n}
                _save_cache(cache_model, repo, cache)
                rate = done / (time.time() - t0)
                print(f"    {done}/{len(tasks)}  {rate:.1f} chunk/s  ETA {(len(tasks)-done)/max(rate,1e-9):.0f}s", flush=True)
    cache["__meta__"] = {"chunker": W4C.chunker_sig(cfg), "prompt_version": PROMPT_VERSION,
                         "cache_model": cache_model, "api_model": model, "n": n}
    _save_cache(cache_model, repo, cache)
    dt = time.time() - t0
    print(f"  {repo}: generated {done} in {dt:.0f}s ({done/max(dt,1e-9):.1f}/s) -> {cache_path(cache_model, repo)}")
    return {"repo": repo, "generated": done, "cached": have + done}


def cmd_generate(args) -> int:
    cfg = E._load_cfg(args.config)
    apply_to = tuple(args.apply_to.split(","))
    repos = list(M.REPOS) if args.repo == "all" else args.repo.split(",")
    extra_body = json.loads(args.extra_body) if args.extra_body else None
    if args.no_think:
        extra_body = {**(extra_body or {}), "chat_template_kwargs": {"enable_thinking": False}}
    results = []
    for repo in repos:
        results.append(generate_for_repo(repo, cfg, args.model, args.base_url, args.api_key,
                                         apply_to, args.workers, args.n, args.max_tokens,
                                         args.limit, extra_body, cache_model=args.cache_model))
    print("\n=== summary ===")
    for r in results:
        print(f"  {r['repo']:24s} generated={r.get('generated',0):5d} cached={r.get('cached',0):5d}")
    return 0


def cmd_stats(args) -> int:
    grand = 0
    for repo in (list(M.REPOS) if args.repo == "all" else args.repo.split(",")):
        cache = load_cache(args.model, repo)
        keys = [k for k in cache if k != "__meta__"]
        lens = [cache[k].count("\n") + 1 for k in keys if cache[k]]
        avg = sum(lens) / len(lens) if lens else 0
        grand += len(keys)
        print(f"  {repo:24s} chunks={len(keys):5d} avg_queries={avg:.1f}")
    print(f"  TOTAL {grand}")
    return 0


def cmd_sample(args) -> int:
    cache = load_cache(args.model, args.repo)
    keys = [k for k in cache if k != "__meta__" and cache[k]]
    for k in keys[:args.n]:
        path, sb, eb = k.split("\t")
        print(f"--- {path} [{sb}:{eb}]")
        print("    " + cache[k].replace("\n", "\n    "))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--repo", required=True)
    g.add_argument("--model", required=True)
    g.add_argument("--cache-model", default=None)
    g.add_argument("--base-url", default=os.environ.get("OPENAI_API_BASE", "https://llm.shuyangsun.com/v1"))
    g.add_argument("--api-key", default=None)
    g.add_argument("--config", default=None)
    g.add_argument("--apply-to", default="md,code")
    g.add_argument("--workers", type=int, default=24)
    g.add_argument("--n", type=int, default=DEFAULT_N)
    g.add_argument("--max-tokens", type=int, default=160)
    g.add_argument("--limit", type=int, default=None)
    g.add_argument("--no-think", action="store_true")
    g.add_argument("--extra-body", default=None)
    g.set_defaults(func=cmd_generate)
    s = sub.add_parser("stats")
    s.add_argument("--model", required=True)
    s.add_argument("--repo", default="all")
    s.set_defaults(func=cmd_stats)
    sp = sub.add_parser("sample")
    sp.add_argument("--model", required=True)
    sp.add_argument("--repo", required=True)
    sp.add_argument("-n", type=int, default=6)
    sp.set_defaults(func=cmd_sample)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
