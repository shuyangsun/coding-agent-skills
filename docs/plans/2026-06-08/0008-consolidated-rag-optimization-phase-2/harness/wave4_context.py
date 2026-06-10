#!/usr/bin/env python3
"""wave4_context.py — Anthropic-style *contextual retrieval* generator (Wave 4).

Wave 4, step 1 of ``0008-consolidated-rag-optimization-phase-2.md``: use a local
generative LLM to write a 1-2 sentence "situating context" for every chunk, prepend
it to the retrieval field (dense + sparse), and measure the retrieval lift over the
Wave-2 deterministic-header baseline. Source text (`raw_text`) stays verbatim for
citations/sentinels; only the embedded `contextualized_text` changes.

This module is the GENERATION half (LLM calls + on-disk cache). It is decoupled from
indexing on purpose:
  * generation needs only the OpenAI SDK (campaign venv) and reuses the harness
    chunker (`enriched_index.span_chunks`), so chunk identity is byte-identical to
    what the indexer will produce;
  * indexing (FastEmbed/Qdrant venv) reads the cache via ``compose_embedded`` /
    ``load_cache`` — see ``enriched_index.doc_points``.

Cache layout (kept OUT of the repo — derived, large, non-deterministic):
    $WAVE4_CACHE/<model_slug>/<repo>.json   (default $WAVE4_CACHE=~/.cache/rag-skill/wave4-context)
    { "<path>\t<start_byte>\t<end_byte>": "<context sentence(s)>", ... , "__meta__": {...} }
keyed by (path, byte-span) so a chunker change invalidates nothing silently — the
meta records the chunker signature + prompt version, and a mismatch is reported.

CLI:
    wave4_context.py generate --repo alpha-zero --model gemma-4 \
        --base-url https://llm.shuyangsun.com/v1 --apply-to md,code [--workers 24] [--limit N]
    wave4_context.py stats --model gemma-4 [--repo ...]
    wave4_context.py sample --model gemma-4 --repo website [-n 6]
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

PROMPT_VERSION = "v1"
DEFAULT_MAX_DOC_CHARS = 48_000  # ~12k tokens; full doc when shorter, head-truncated when longer
DEFAULT_MAX_CHUNK_CHARS = 6_000

# Anthropic "contextual retrieval" prompt, generalised to code+prose. One short
# situating context, no preamble — it is PREPENDED to the chunk before embedding.
_SYS = ("You situate a passage within its source document so search engines can find it. "
        "Reply with ONE or TWO plain sentences of context only: no preamble, no quotes, "
        "no markdown, no bullet points. Name the document's subject/component and where "
        "this passage fits (which section, function, or step).")
_USER = """<document repo="{repo}" path="{path}">
{doc}
</document>

Here is a passage taken from that document:
<passage>
{chunk}
</passage>

Write a short context (1-2 sentences) that situates this passage within the overall \
document to improve search retrieval. Answer with only the context."""


def model_slug(model: str) -> str:
    return "".join(c if (c.isalnum() or c in "-._") else "_" for c in model)


def cache_root() -> Path:
    return Path(os.environ.get(
        "WAVE4_CACHE",
        str(Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
            / "rag-skill" / "wave4-context"))).expanduser()


def cache_path(model: str, repo: str) -> Path:
    return cache_root() / model_slug(model) / f"{repo}.json"


def chunk_key(path: str, start_byte: int, end_byte: int) -> str:
    return f"{path}\t{start_byte}\t{end_byte}"


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


def chunker_sig(cfg: dict) -> str:
    ch = cfg.get("chunker", {})
    return json.dumps({k: ch.get(k) for k in
                       ("size", "overlap", "min_words", "code_size", "code_overlap", "strategy")},
                      sort_keys=True)


# --- compose the embedded field (shared with the indexer) --------------------
def compose_embedded(header: str, llm_ctx: str | None, raw_text: str) -> str:
    """Build the retrieval/embedding text: optional deterministic header, then the
    LLM situating context, then the verbatim chunk. Mirrors Anthropic's recipe
    (context prepended to the chunk) while keeping the Wave-2 header win on top."""
    parts = []
    if header:
        parts.append(header)
    if llm_ctx:
        parts.append(llm_ctx.strip())
    body = "\n".join(parts)
    return f"{body}\n\n{raw_text}" if body else raw_text


# --- generation --------------------------------------------------------------
def _client(base_url: str, api_key: str | None):
    from openai import OpenAI
    return OpenAI(base_url=base_url, api_key=api_key or os.environ.get("LITELLM_API_KEY", "x"))


def _doc_window(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def gen_one(client, model: str, repo: str, path: str, doc: str, chunk: str,
            max_tokens: int, retries: int = 4, extra_body: dict | None = None) -> str:
    msgs = [{"role": "system", "content": _SYS},
            {"role": "user", "content": _USER.format(repo=repo, path=path, doc=doc,
                                                      chunk=chunk[:DEFAULT_MAX_CHUNK_CHARS])}]
    kw = {"extra_body": extra_body} if extra_body else {}
    last = ""
    for attempt in range(retries):
        try:
            r = client.chat.completions.create(model=model, messages=msgs,
                                               max_tokens=max_tokens, temperature=0.0, **kw)
            out = (r.choices[0].message.content or "").strip()
            # collapse to a single line; strip any stray fences/labels
            out = " ".join(out.split())
            for pre in ("Context:", "context:", "Here is", "This passage", "The passage"):
                if out.startswith(pre) and pre.endswith(":"):
                    out = out[len(pre):].strip()
            return out
        except Exception as exc:  # noqa: BLE001 — network/proxy hiccups: backoff + retry
            last = str(exc)
            time.sleep(min(2 ** attempt, 8))
    print(f"    [warn] gen failed {path}: {last[:160]}", file=sys.stderr)
    return ""


def generate_for_repo(repo: str, cfg: dict, model: str, base_url: str, api_key: str | None,
                      apply_to: tuple[str, ...], workers: int, max_doc_chars: int,
                      max_tokens: int, limit: int | None, extra_body: dict | None = None,
                      cache_model: str | None = None) -> dict:
    # cache_model is the on-disk cache NAMESPACE (and the value indexer configs reference);
    # model is the API model name actually sent to the endpoint. Decoupling them lets the
    # same served model produce distinct caches per doc-window (e.g. gemma-4 vs gemma-4-w8k)
    # without one regeneration clobbering the other.
    cache_model = cache_model or model
    repo_obj = M.REPOS[repo]
    corpus = M.load_repo_corpus(repo_obj, kinds=("md", "code"))
    cache = load_cache(cache_model, repo)
    meta = cache.get("__meta__", {})
    if meta and (meta.get("chunker") != chunker_sig(cfg) or meta.get("prompt_version") != PROMPT_VERSION):
        print(f"  [reset] {repo}: chunker/prompt changed -> regenerating", file=sys.stderr)
        cache = {}

    # build the full task list (doc-sorted so same-doc chunks are adjacent -> prefix-cache friendly)
    tasks = []
    n_trunc = 0
    for path in sorted(corpus):
        payload = corpus[path]
        if payload["kind"] not in apply_to:
            continue
        doc, trunc = _doc_window(payload["text"], max_doc_chars)
        n_trunc += int(trunc)
        for c in E.span_chunks(payload["text"], payload["kind"], cfg):
            k = chunk_key(path, c.start_byte, c.end_byte)
            if k in cache:
                continue
            tasks.append((k, path, doc, c.raw_text))
    if limit:
        tasks = tasks[:limit]

    total_missing = len(tasks)
    have = len([k for k in cache if k != "__meta__"])
    print(f"  {repo}: {len(corpus)} docs, {have} cached, {total_missing} to generate "
          f"(apply_to={','.join(apply_to)}, {n_trunc} docs head-truncated)")
    if not tasks:
        return {"repo": repo, "generated": 0, "cached": have, "truncated": n_trunc}

    client = _client(base_url, api_key)
    done = 0
    t0 = time.time()

    def work(task):
        k, path, doc, chunk = task
        return k, gen_one(client, model, repo, path, doc, chunk, max_tokens, extra_body=extra_body)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for k, ctx in ex.map(work, tasks):
            if ctx:
                cache[k] = ctx
            done += 1
            if done % 100 == 0:
                rate = done / (time.time() - t0)
                cache["__meta__"] = {"chunker": chunker_sig(cfg), "prompt_version": PROMPT_VERSION,
                                     "cache_model": cache_model, "api_model": model,
                                     "max_doc_chars": max_doc_chars}
                _save_cache(cache_model, repo, cache)
                print(f"    {done}/{total_missing}  {rate:.1f} chunk/s  "
                      f"ETA {(total_missing-done)/max(rate,1e-9):.0f}s", flush=True)
    cache["__meta__"] = {"chunker": chunker_sig(cfg), "prompt_version": PROMPT_VERSION,
                         "cache_model": cache_model, "api_model": model, "max_doc_chars": max_doc_chars}
    _save_cache(cache_model, repo, cache)
    dt = time.time() - t0
    n_empty = sum(1 for k, v in cache.items() if k != "__meta__" and not v)
    print(f"  {repo}: generated {done} in {dt:.0f}s ({done/max(dt,1e-9):.1f}/s), "
          f"{n_empty} empty, cache -> {cache_path(cache_model, repo)}")
    return {"repo": repo, "generated": done, "cached": have + done, "truncated": n_trunc,
            "empty": n_empty, "seconds": round(dt, 1)}


# --- CLI ---------------------------------------------------------------------
def _load_cfg(path: str | None) -> dict:
    return E._load_cfg(path)


def cmd_generate(args) -> int:
    cfg = _load_cfg(args.config)
    apply_to = tuple(args.apply_to.split(","))
    repos = list(M.REPOS) if args.repo == "all" else args.repo.split(",")
    extra_body = json.loads(args.extra_body) if args.extra_body else None
    if args.no_think:  # Qwen3 / reasoning models: disable <think> via the jinja template
        extra_body = {**(extra_body or {}), "chat_template_kwargs": {"enable_thinking": False}}
    if extra_body:
        print(f"  extra_body={extra_body}")
    results = []
    for repo in repos:
        results.append(generate_for_repo(
            repo, cfg, args.model, args.base_url, args.api_key, apply_to,
            args.workers, args.max_doc_chars, args.max_tokens, args.limit, extra_body,
            cache_model=args.cache_model))
    print("\n=== summary ===")
    for r in results:
        print(f"  {r['repo']:24s} generated={r.get('generated',0):5d} "
              f"cached={r.get('cached',0):5d} empty={r.get('empty',0):3d} trunc={r.get('truncated',0):3d}")
    return 0


def cmd_stats(args) -> int:
    repos = list(M.REPOS) if args.repo == "all" else args.repo.split(",")
    grand = 0
    for repo in repos:
        cache = load_cache(args.model, repo)
        keys = [k for k in cache if k != "__meta__"]
        empty = sum(1 for k in keys if not cache[k])
        lens = [len(cache[k]) for k in keys if cache[k]]
        avg = sum(lens) / len(lens) if lens else 0
        grand += len(keys)
        print(f"  {repo:24s} ctx={len(keys):5d} empty={empty:3d} avg_chars={avg:5.0f} "
              f"meta={cache.get('__meta__',{}).get('model','?')}")
    print(f"  TOTAL ctx={grand}")
    return 0


def cmd_sample(args) -> int:
    cache = load_cache(args.model, args.repo)
    keys = [k for k in cache if k != "__meta__" and cache[k]]
    for k in keys[:args.n]:
        path, sb, eb = k.split("\t")
        print(f"--- {path}  [{sb}:{eb}]")
        print(f"    {cache[k]}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate + cache situating contexts via an LLM")
    g.add_argument("--repo", required=True, help="repo name | comma list | all")
    g.add_argument("--model", required=True, help="API model name sent to the endpoint")
    g.add_argument("--cache-model", default=None,
                   help="cache namespace (+ value indexer configs reference); default = --model. "
                        "Use a window-suffixed name (e.g. qwen3.6-27b-w8k) to keep distinct doc-window caches apart")
    g.add_argument("--base-url", default=os.environ.get("OPENAI_API_BASE", "https://llm.shuyangsun.com/v1"))
    g.add_argument("--api-key", default=None)
    g.add_argument("--config", default=None, help="rag-config (chunker must match the index arm)")
    g.add_argument("--apply-to", default="md,code", help="chunk kinds to contextualize (default md,code)")
    g.add_argument("--workers", type=int, default=24)
    g.add_argument("--max-doc-chars", type=int, default=DEFAULT_MAX_DOC_CHARS)
    g.add_argument("--max-tokens", type=int, default=160)
    g.add_argument("--limit", type=int, default=None, help="cap tasks (pilot)")
    g.add_argument("--no-think", action="store_true",
                   help="disable reasoning <think> blocks (Qwen3 etc.) via chat_template_kwargs")
    g.add_argument("--extra-body", default=None, help="extra JSON body merged into each request")
    g.set_defaults(func=cmd_generate)

    s = sub.add_parser("stats", help="cache coverage per repo")
    s.add_argument("--model", required=True)
    s.add_argument("--repo", default="all")
    s.set_defaults(func=cmd_stats)

    sp = sub.add_parser("sample", help="print a few generated contexts")
    sp.add_argument("--model", required=True)
    sp.add_argument("--repo", required=True)
    sp.add_argument("-n", type=int, default=6)
    sp.set_defaults(func=cmd_sample)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
