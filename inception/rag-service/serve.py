#!/usr/bin/env python3
"""serve.py — a warm, long-lived HTTP sidecar for the inception RAG GUI.

The GUI needs sub-second retrieval. Shelling out to ``query.py`` per request
pays a ~4 s cold model load every time (FastEmbed dense + sparse + the
cross-encoder reranker are re-imported and re-loaded for each process). This
sidecar imports the ``setting-up-rag`` skill's ``rag_lib`` + ``answer`` helpers
*once*, keeps those models hot, and answers over HTTP, so the second query
onward returns in well under a second.

It is stdlib-only (``http.server``) — no deps beyond what the rag-skill venv
already provides (``qdrant-client`` + ``fastembed``). Run it with that venv's
Python:

    ~/.cache/rag-skill/venv/bin/python rag-service/serve.py

Endpoints (all JSON, 127.0.0.1 only):
  GET  /health   -> {ok, warm, projects, where}
  GET  /projects -> {projects: [...]}
  POST /query    -> {results, where, target}
  POST /answer   -> {answer, sources, usage, model, base_url, where, target}

Configuration (env):
  RAG_SERVICE_HOST   bind host (default 127.0.0.1)
  RAG_SERVICE_PORT   bind port (default 8390)
  RAG_SCRIPTS_DIR    path to the setting-up-rag scripts dir (default: resolved
                     relative to this file at ../../.agents/skills/setting-up-rag/scripts)
"""

from __future__ import annotations

import json
import os
import sys
import threading
import urllib.error
import urllib.request
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def _scripts_dir() -> Path:
    env = os.environ.get("RAG_SCRIPTS_DIR")
    if env:
        return Path(env).expanduser().resolve()
    # serve.py lives at <repo>/inception/rag-service/serve.py
    here = Path(__file__).resolve()
    return (here.parents[2] / ".agents" / "skills" / "setting-up-rag" / "scripts").resolve()


SCRIPTS_DIR = _scripts_dir()
if not (SCRIPTS_DIR / "rag_lib.py").exists():
    sys.exit(
        f"serve: rag_lib.py not found under {SCRIPTS_DIR}. "
        "Set RAG_SCRIPTS_DIR to the setting-up-rag scripts directory."
    )
sys.path.insert(0, str(SCRIPTS_DIR))

import rag_lib as R  # noqa: E402
import answer as A  # noqa: E402


# --- shared warm state ------------------------------------------------------
# rag_lib caches the FastEmbed/reranker models in its own module globals once
# loaded; we hold the Qdrant client + config here and serialize retrieval (the
# embedding/rerank model calls are not guaranteed thread-safe, and a single
# desktop user never needs real retrieval concurrency).
_STATE_LOCK = threading.Lock()
_RETRIEVE_LOCK = threading.Lock()
_CLIENT: Any = None
_WHERE: str = "unknown"
_CFG: dict[str, Any] = {}
_WARM = False


def _config() -> dict[str, Any]:
    global _CFG
    if not _CFG:
        with _STATE_LOCK:
            if not _CFG:
                _CFG = R.load_config(os.environ.get("RAG_CONFIG") or None)
    return _CFG


def _client() -> tuple[Any, str]:
    global _CLIENT, _WHERE
    if _CLIENT is None:
        with _STATE_LOCK:
            if _CLIENT is None:
                _CLIENT, _WHERE = R.get_client(force_local=False)
    return _CLIENT, _WHERE


def _warm_models() -> None:
    """Load the dense, sparse, and reranker models so the first real query is fast."""
    global _WARM
    try:
        cfg = _config()
        _client()
        R.embed_query("warm up the retrieval models", cfg)
        try:
            R.rerank("warm up", ["a representative document chunk for warmup"], cfg)
        except Exception as exc:  # reranker is optional; queries still work without warm
            print(f"serve: reranker warmup skipped: {exc}", file=sys.stderr)
        _WARM = True
        print("serve: models warm", file=sys.stderr)
    except Exception as exc:
        print(f"serve: warmup failed (will warm on first query): {exc}", file=sys.stderr)


# --- retrieval --------------------------------------------------------------
class ApiError(Exception):
    """A handled error to surface to the client with an HTTP status."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def _retrieve(
    *,
    query: str,
    project: str | None,
    collection: str | None,
    kind: str,
    top_k: int,
    do_rerank: bool,
) -> tuple[list[tuple[Any, float, str | None, str | None, str]], str, str]:
    client, where = _client()
    cfg = _config()
    with _RETRIEVE_LOCK:
        if project:
            try:
                targets = R.project_targets(client, project, kind)
            except SystemExit as exc:
                raise ApiError(str(exc.code), 404) from exc
            ranked: list[tuple[Any, float, str | None, str | None, str]] = []
            for project_key, selected_kind, coll in targets:
                for hit, score in R.retrieve_chunks(
                    client, coll, query, cfg, top_k, do_rerank=do_rerank
                ):
                    ranked.append((hit, score, project_key, selected_kind, coll))
            ranked.sort(key=lambda item: item[1], reverse=True)
            target = f"project '{project}' ({', '.join(c for _, _, c in targets)})"
            return ranked[:top_k], where, target

        coll = collection or cfg.get("collection", "docs")
        if not client.collection_exists(coll):
            raise ApiError(f"collection '{coll}' not found ({where})", 404)
        ranked = [
            (hit, score, None, None, coll)
            for hit, score in R.retrieve_chunks(
                client, coll, query, cfg, top_k, do_rerank=do_rerank
            )
        ]
        return ranked, where, f"collection '{coll}'"


def _result_rows(
    ranked: list[tuple[Any, float, str | None, str | None, str]],
) -> list[dict[str, Any]]:
    rows = []
    for hit, score, project, kind, coll in ranked:
        payload = hit.payload or {}
        rows.append(
            {
                "project": project,
                "kind": kind,
                "collection": coll,
                "doc_id": payload.get("doc_id"),
                "chunk_idx": payload.get("chunk_idx"),
                "score": float(score),
                "text": payload.get("text", "") or "",
            }
        )
    return rows


# --- answering --------------------------------------------------------------
def _chat_completions_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    return base if base.endswith("/chat/completions") else f"{base}/chat/completions"


def _call_llm(
    *, base_url: str, api_key: str | None, body: dict[str, Any], timeout: float
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    url = _chat_completions_url(base_url)
    try:
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        # Newer OpenAI models reject 'max_tokens' and require
        # 'max_completion_tokens'. Retry once with the renamed field.
        if (
            exc.code == 400
            and "max_tokens" in body
            and "max_completion_tokens" in detail
        ):
            retry_body = {
                k: v for k, v in body.items() if k != "max_tokens"
            }
            retry_body["max_completion_tokens"] = body["max_tokens"]
            return _call_llm(
                base_url=base_url,
                api_key=api_key,
                body=retry_body,
                timeout=timeout,
            )
        raise ApiError(f"provider returned HTTP {exc.code}: {detail}", 502) from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"could not reach provider at {base_url}: {exc.reason}", 502) from exc
    except TimeoutError as exc:
        raise ApiError(f"provider timed out after {timeout:g}s", 504) from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ApiError(f"provider returned invalid JSON: {exc}", 502) from exc
    if not isinstance(parsed, dict):
        raise ApiError("provider response was not a JSON object", 502)
    return parsed


def _answer_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ApiError("provider response did not include choices", 502)
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise ApiError("provider response choice did not include a message", 502)
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
            elif isinstance(part, str):
                parts.append(part)
        return "".join(parts)
    return str(content)


# --- endpoint handlers ------------------------------------------------------
def handle_projects() -> dict[str, Any]:
    manifest = R.load_project_manifest()
    projects = []
    for key, project in sorted(manifest.get("projects", {}).items()):
        collections = []
        total_chunks = 0
        total_sources = 0
        for kind, info in sorted((project.get("collections") or {}).items()):
            chunks = int(info.get("chunk_count", 0) or 0)
            sources = int(info.get("source_count", 0) or 0)
            total_chunks += chunks
            total_sources += sources
            collections.append(
                {
                    "kind": kind,
                    "collection": info.get("collection"),
                    "chunk_count": chunks,
                    "source_count": sources,
                    "indexed_at": info.get("indexed_at"),
                }
            )
        projects.append(
            {
                "key": key,
                "name": project.get("name", key),
                "root": project.get("root", ""),
                "collections": collections,
                "total_chunks": total_chunks,
                "total_sources": total_sources,
            }
        )
    return {"projects": projects}


def _req_str(body: dict[str, Any], name: str) -> str:
    value = body.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(f"'{name}' is required", 400)
    return value.strip()


def _kind(body: dict[str, Any]) -> str:
    kind = body.get("kind", "all")
    if kind not in ("md", "code", "all"):
        raise ApiError("'kind' must be one of md, code, all", 400)
    return kind


def _top_k(body: dict[str, Any]) -> int:
    raw = body.get("top_k")
    if raw is None:
        return int(_config().get("top_k", 20))
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ApiError("'top_k' must be an integer", 400) from exc
    return max(1, min(value, 100))


def handle_query(body: dict[str, Any]) -> dict[str, Any]:
    query = _req_str(body, "query")
    project = body.get("project") or None
    collection = body.get("collection") or None
    if project and collection:
        raise ApiError("pass either 'project' or 'collection', not both", 400)
    if not project and not collection:
        raise ApiError("'project' is required", 400)
    ranked, where, target = _retrieve(
        query=query,
        project=project,
        collection=collection,
        kind=_kind(body),
        top_k=_top_k(body),
        do_rerank=bool(body.get("rerank", True)),
    )
    return {"results": _result_rows(ranked), "where": where, "target": target}


def handle_answer(body: dict[str, Any]) -> dict[str, Any]:
    query = _req_str(body, "query")
    model = _req_str(body, "model")
    project = body.get("project") or None
    collection = body.get("collection") or None
    if project and collection:
        raise ApiError("pass either 'project' or 'collection', not both", 400)
    if not project and not collection:
        raise ApiError("'project' is required", 400)

    ans_cfg = A.answer_config(_config())
    base_url = (
        body.get("base_url")
        or os.environ.get(str(ans_cfg.get("base_url_env", "RAG_LLM_BASE_URL")))
        or str(ans_cfg.get("default_base_url", "http://127.0.0.1:8000/v1"))
    )
    api_key = body.get("api_key") or os.environ.get(
        str(ans_cfg.get("api_key_env", "RAG_LLM_API_KEY"))
    )
    temperature = float(body.get("temperature", ans_cfg.get("temperature", 0.2)))
    max_tokens = int(body.get("max_tokens", ans_cfg.get("max_tokens", 800)))
    timeout = float(body.get("timeout", ans_cfg.get("timeout", 120)))
    max_context_chars = int(
        body.get("max_context_chars", ans_cfg.get("max_context_chars", 12000))
    )
    system_prompt = body.get("system_prompt") or str(
        ans_cfg.get("system_prompt", A.DEFAULT_SYSTEM_PROMPT)
    )
    if max_context_chars <= 0:
        raise ApiError("'max_context_chars' must be greater than zero", 400)

    ranked, where, target = _retrieve(
        query=query,
        project=project,
        collection=collection,
        kind=_kind(body),
        top_k=_top_k(body),
        do_rerank=bool(body.get("rerank", True)),
    )
    sources = A.pack_sources(ranked, max_context_chars)
    if not sources:
        raise ApiError("retrieval returned no usable context chunks", 422)
    context = A.build_context(sources)
    messages = A.build_messages(query, context, system_prompt)
    request_body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    response = _call_llm(
        base_url=base_url, api_key=api_key, body=request_body, timeout=timeout
    )
    return {
        "answer": _answer_content(response),
        "sources": [asdict(source) for source in sources],
        "usage": response.get("usage"),
        "model": model,
        "base_url": base_url,
        "where": where,
        "target": target,
    }


# --- HTTP plumbing ----------------------------------------------------------
ROUTES_GET = {
    "/health": lambda body: {
        "ok": True,
        "warm": _WARM,
        "where": _WHERE,
        "projects": len(R.load_project_manifest().get("projects", {})),
    },
    "/projects": lambda body: handle_projects(),
}
ROUTES_POST = {
    "/query": handle_query,
    "/answer": handle_answer,
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _dispatch(self, routes: dict[str, Any], body: dict[str, Any]) -> None:
        handler = routes.get(self.path.split("?", 1)[0])
        if handler is None:
            self._send(404, {"error": f"no route {self.path}"})
            return
        try:
            self._send(200, handler(body))
        except ApiError as exc:
            self._send(exc.status, {"error": str(exc)})
        except SystemExit as exc:  # rag_lib uses sys.exit for user errors
            self._send(400, {"error": str(exc.code)})
        except Exception as exc:  # noqa: BLE001 — never let the sidecar crash a request
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})

    def do_GET(self) -> None:  # noqa: N802 — http.server API
        self._dispatch(ROUTES_GET, {})

    def do_POST(self) -> None:  # noqa: N802 — http.server API
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw or b"{}")
            if not isinstance(body, dict):
                raise ValueError("body must be a JSON object")
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": f"invalid JSON body: {exc}"})
            return
        self._dispatch(ROUTES_POST, body)

    def log_message(self, fmt: str, *args: Any) -> None:  # quiet; prefix what we keep
        sys.stderr.write(f"serve: {self.address_string()} {fmt % args}\n")


def main() -> int:
    host = os.environ.get("RAG_SERVICE_HOST", "127.0.0.1")
    port = int(os.environ.get("RAG_SERVICE_PORT", "8390"))
    threading.Thread(target=_warm_models, name="warmup", daemon=True).start()
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    print(f"serve: RAG sidecar listening on http://{host}:{port} (scripts: {SCRIPTS_DIR})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("serve: shutting down", file=sys.stderr)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
