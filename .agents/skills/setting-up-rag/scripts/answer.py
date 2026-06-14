#!/usr/bin/env python3
"""answer.py - testing-only RAG answer generation with an OpenAI-compatible API.

This is a thin harness on top of the retrieval engine:
  1. retrieve chunks with the same hybrid + rerank path as query.py,
  2. pack citation-labeled context (parent-4k extractive by default),
  3. call a local or cloud /v1/chat/completions endpoint.

It is for manual tests and future UI/backend experiments, not the default RAG
consumer path.

Usage:
  answer.py "your question" --project NAME_OR_PATH --model MODEL
  answer.py "..." --collection docs --model MODEL --base-url http://127.0.0.1:8085/v1
  answer.py "..." --project repo --model MODEL --json
  answer.py "..." --project repo --model MODEL --dry-run --show-context
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rag_lib as R  # noqa: E402

DEFAULT_SYSTEM_PROMPT = (
    "You are a retrieval-grounded QA test harness. Answer only from the provided "
    "context. Cite every factual sentence with bracketed source ids like [1]. "
    "Copy exact source identifiers, constants, numbers, file names, quoted "
    "strings, commands, and error text instead of paraphrasing them. If the "
    "context is insufficient, say what is missing instead of guessing."
)


@dataclass(frozen=True)
class Source:
    source_id: int
    doc_id: str
    chunk_idx: int | None
    score: float
    text: str
    collection: str
    project: str | None
    kind: str | None


def answer_config(cfg: dict[str, Any]) -> dict[str, Any]:
    block = cfg.get("answering", {})
    return block if isinstance(block, dict) else {}


def chat_completions_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def parse_extra_body(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        sys.exit(f"answer: invalid --extra-body-json: {exc}")
    if not isinstance(parsed, dict):
        sys.exit("answer: --extra-body-json must decode to a JSON object")
    return parsed


def source_label(source: Source) -> str:
    scope = f"{source.project}/{source.kind}:" if source.project and source.kind else ""
    chunk = f"#{source.chunk_idx}" if source.chunk_idx is not None else ""
    return f"[{source.source_id}] {scope}{source.doc_id}{chunk}"


def ordered_for_pack(
    ranked: list[tuple[Any, float, str | None, str | None, str]],
    strategy: str,
) -> list[tuple[Any, float, str | None, str | None, str]]:
    if strategy == "score":
        return ranked
    if strategy == "source":
        return sorted(
            ranked,
            key=lambda item: (
                str((item[0].payload or {}).get("doc_id", "")),
                int((item[0].payload or {}).get("chunk_idx", 0) or 0),
            ),
        )
    if strategy != "parent":
        sys.exit("answer: --pack must be one of score, parent, source")

    groups: dict[str, list[tuple[Any, float, str | None, str | None, str]]] = {}
    order: list[str] = []
    for item in ranked:
        payload = item[0].payload or {}
        key = str(payload.get("parent_id") or payload.get("doc_id") or "")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)
    packed: list[tuple[Any, float, str | None, str | None, str]] = []
    for key in order:
        packed.extend(
            sorted(
                groups[key],
                key=lambda item: int((item[0].payload or {}).get("chunk_idx", 0) or 0),
            )
        )
    return packed


def pack_sources(
    ranked: list[tuple[Any, float, str | None, str | None, str]],
    max_context_chars: int,
    *,
    strategy: str = "score",
) -> list[Source]:
    if max_context_chars <= 0:
        sys.exit("answer: --max-context-chars must be greater than zero")

    sources: list[Source] = []
    used = 0
    for hit, score, project, kind, collection in ordered_for_pack(ranked, strategy):
        payload = hit.payload or {}
        raw_text = R.payload_display_text(payload).strip()
        if not raw_text:
            continue

        source_id = len(sources) + 1
        doc_id = str(payload.get("doc_id", ""))
        chunk_idx = payload.get("chunk_idx")
        header = source_label(
            Source(
                source_id=source_id,
                doc_id=doc_id,
                chunk_idx=chunk_idx if isinstance(chunk_idx, int) else None,
                score=float(score),
                text="",
                collection=collection,
                project=project,
                kind=kind,
            )
        )
        remaining = max_context_chars - used - len(header) - 2
        if remaining <= 80:
            break
        text = raw_text
        if len(text) > remaining:
            marker = "\n[truncated]"
            text = text[: max(0, remaining - len(marker))].rstrip() + marker

        sources.append(
            Source(
                source_id=source_id,
                doc_id=doc_id,
                chunk_idx=chunk_idx if isinstance(chunk_idx, int) else None,
                score=float(score),
                text=text,
                collection=collection,
                project=project,
                kind=kind,
            )
        )
        used += len(header) + len(text) + 2
    return sources


def build_context(sources: list[Source]) -> str:
    blocks = []
    for source in sources:
        header = f"{source_label(source)} score={source.score:+.4f} collection={source.collection}"
        blocks.append(f"{header}\n{source.text}")
    return "\n\n".join(blocks)


def build_messages(
    question: str, context: str, system_prompt: str
) -> list[dict[str, str]]:
    user_prompt = (
        f"Question:\n{question}\n\n"
        f"Retrieved context:\n{context}\n\n"
        "Answer the question from the retrieved context. Cite sources with the "
        "bracketed ids shown above. Preserve exact identifiers and literals from "
        "the context when they matter."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def collect_ranked(
    args: argparse.Namespace, cfg: dict[str, Any]
) -> tuple[
    list[tuple[Any, float, str | None, str | None, str]],
    str,
    str,
]:
    top_k = args.top_k if args.top_k is not None else int(cfg.get("top_k", 20))
    client, where = R.get_client(force_local=args.local)
    if args.project:
        ranked = []
        targets = R.project_targets(client, args.project, args.kind)
        for project_key, selected_kind, collection in targets:
            for hit, score in R.retrieve_chunks(
                client,
                collection,
                args.query,
                cfg,
                top_k,
                do_rerank=not args.no_rerank,
            ):
                ranked.append((hit, score, project_key, selected_kind, collection))
        ranked.sort(key=lambda item: item[1], reverse=True)
        target_label = (
            f"project '{args.project}' ({', '.join(coll for _, _, coll in targets)})"
        )
        return ranked[:top_k], where, target_label

    collection = args.collection or cfg.get("collection", "docs")
    if not client.collection_exists(collection):
        sys.exit(
            f"answer: collection '{collection}' not found ({where}). Run index.py first."
        )
    ranked = [
        (hit, score, None, None, collection)
        for hit, score in R.retrieve_chunks(
            client,
            collection,
            args.query,
            cfg,
            top_k,
            do_rerank=not args.no_rerank,
        )
    ]
    return ranked, where, f"collection '{collection}'"


def call_chat_completions(
    *,
    base_url: str,
    api_key: str | None,
    body: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        chat_completions_url(base_url),
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw_error = exc.read().decode("utf-8", errors="replace")
        sys.exit(f"answer: provider returned HTTP {exc.code}: {raw_error[:1200]}")
    except urllib.error.URLError as exc:
        sys.exit(f"answer: could not reach provider at {base_url}: {exc.reason}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"answer: provider returned invalid JSON: {exc}")
    if not isinstance(parsed, dict):
        sys.exit("answer: provider response was not a JSON object")
    return parsed


def response_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        sys.exit("answer: provider response did not include choices")
    first = choices[0]
    if not isinstance(first, dict):
        sys.exit("answer: provider response choice was not an object")
    message = first.get("message")
    if not isinstance(message, dict):
        sys.exit("answer: provider response choice did not include a message")
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(part, str):
                parts.append(part)
        return "".join(parts)
    return str(content)


def print_text_result(
    *,
    answer: str | None,
    sources: list[Source],
    context: str,
    show_context: bool,
    dry_run_body: dict[str, Any] | None,
    base_url: str,
    where: str,
    target_label: str,
    response: dict[str, Any] | None,
) -> None:
    print(f"# Retrieval\n{where}, {target_label}\n")
    if show_context:
        print(f"# Context\n{context}\n")
    if dry_run_body is not None:
        print("# Chat Completions Request")
        print(
            json.dumps(
                {
                    "url": chat_completions_url(base_url),
                    "body": dry_run_body,
                },
                indent=2,
            )
        )
        return

    print("# Answer")
    print((answer or "").strip())
    print("\n# Sources")
    for source in sources:
        print(
            f"{source_label(source)} score={source.score:+.4f} collection={source.collection}"
        )
    if response and response.get("usage"):
        print("\n# Usage")
        print(json.dumps(response["usage"], indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("query", nargs="?", help="the natural-language question")
    ap.add_argument("--project", help="registered project name or project root path")
    ap.add_argument(
        "--kind",
        choices=["md", "code", "all"],
        default="all",
        help="registered project collection kind",
    )
    ap.add_argument("--collection")
    ap.add_argument("--config")
    ap.add_argument(
        "--top-k", type=int, help="number of retrieved chunks (default: config top_k)"
    )
    ap.add_argument("--no-rerank", action="store_true")
    ap.add_argument(
        "--local",
        action="store_true",
        help="force embedded on-disk mode (skip the server probe)",
    )
    ap.add_argument("--model", help="OpenAI-compatible model name, or $RAG_LLM_MODEL")
    ap.add_argument(
        "--base-url", help="OpenAI-compatible API base URL, or $RAG_LLM_BASE_URL"
    )
    ap.add_argument(
        "--api-key-env", help="environment variable containing the provider API key"
    )
    ap.add_argument("--temperature", type=float)
    ap.add_argument("--max-tokens", type=int)
    ap.add_argument("--timeout", type=float)
    ap.add_argument(
        "--max-context-chars",
        type=int,
        help="context character budget before truncation",
    )
    ap.add_argument(
        "--max-context-tokens",
        type=int,
        help="approximate context token budget; converted using config chars_per_token",
    )
    ap.add_argument(
        "--pack",
        choices=["score", "parent", "source"],
        help="context order before truncation (default: config answering.pack_strategy)",
    )
    ap.add_argument(
        "--system-prompt", help="override the default grounded-answer system prompt"
    )
    ap.add_argument(
        "--extra-body-json",
        help="JSON object merged into the chat completions request body",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="retrieve and print the provider request without calling it",
    )
    ap.add_argument(
        "--show-context", action="store_true", help="print the packed retrieval context"
    )
    ap.add_argument("--json", action="store_true", help="emit one JSON object")
    args = ap.parse_args(argv)

    if not args.query:
        ap.error("query is required")
    if args.project and args.collection:
        ap.error("--project and --collection are mutually exclusive")

    cfg = R.load_config(args.config)
    ans_cfg = answer_config(cfg)
    model_env = str(ans_cfg.get("model_env", "RAG_LLM_MODEL"))
    base_url_env = str(ans_cfg.get("base_url_env", "RAG_LLM_BASE_URL"))
    api_key_env = args.api_key_env or str(ans_cfg.get("api_key_env", "RAG_LLM_API_KEY"))

    model = args.model or os.environ.get(model_env) or ans_cfg.get("default_model")
    if not model:
        ap.error(f"--model or ${model_env} is required")
    base_url = (
        args.base_url
        or os.environ.get(base_url_env)
        or str(ans_cfg.get("default_base_url", "http://127.0.0.1:8000/v1"))
    )
    api_key = os.environ.get(api_key_env) if api_key_env else None
    temperature = (
        args.temperature
        if args.temperature is not None
        else float(ans_cfg.get("temperature", 0.2))
    )
    max_tokens = (
        args.max_tokens
        if args.max_tokens is not None
        else int(ans_cfg.get("max_tokens", 800))
    )
    timeout = (
        args.timeout if args.timeout is not None else float(ans_cfg.get("timeout", 120))
    )
    if args.max_context_chars is not None:
        max_context_chars = args.max_context_chars
    else:
        token_budget = (
            args.max_context_tokens
            if args.max_context_tokens is not None
            else ans_cfg.get("max_context_tokens")
        )
        if token_budget is not None:
            max_context_chars = int(
                float(token_budget) * float(ans_cfg.get("chars_per_token", 4.0))
            )
        else:
            max_context_chars = int(ans_cfg.get("max_context_chars", 12000))
    pack_strategy = args.pack or str(ans_cfg.get("pack_strategy", "parent"))
    system_prompt = args.system_prompt or str(
        ans_cfg.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
    )

    ranked, where, target_label = collect_ranked(args, cfg)
    sources = pack_sources(ranked, max_context_chars, strategy=pack_strategy)
    if not sources:
        sys.exit("answer: retrieval returned no usable context chunks")
    context = build_context(sources)
    messages = build_messages(args.query, context, system_prompt)
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    body.update(parse_extra_body(args.extra_body_json))

    response = (
        None
        if args.dry_run
        else call_chat_completions(
            base_url=base_url,
            api_key=api_key,
            body=body,
            timeout=timeout,
        )
    )
    answer = None if response is None else response_content(response)

    if args.json:
        print(
            json.dumps(
                {
                    "question": args.query,
                    "answer": answer,
                    "model": model,
                    "base_url": base_url,
                    "qdrant": where,
                    "target": target_label,
                    "sources": [asdict(source) for source in sources],
                    "pack_strategy": pack_strategy,
                    "usage": response.get("usage") if response else None,
                    "request": body if args.dry_run else None,
                }
            )
        )
        return 0

    print_text_result(
        answer=answer,
        sources=sources,
        context=context,
        show_context=args.show_context,
        dry_run_body=body if args.dry_run else None,
        base_url=base_url,
        where=where,
        target_label=target_label,
        response=response,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
