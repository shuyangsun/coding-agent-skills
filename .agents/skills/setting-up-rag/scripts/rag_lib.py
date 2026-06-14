#!/usr/bin/env python3
"""rag_lib.py — shared helpers for the `setting-up-rag` skill's local Qdrant pipeline.

Local-first by design: embeddings run on CPU via FastEmbed (ONNX, no torch, no
cloud); the vector store is Qdrant, reached over HTTP when a server is up
($QDRANT_URL, default http://localhost:6333) or falling back to qdrant-client's
embedded on-disk mode ($QDRANT_PATH) so the skill still works with no daemon.

Nothing here is repo-specific: callers pass a corpus directory and a config path.
`index.py` and `query.py` are thin CLIs over these helpers; the retrieval method
they implement is documented in RETRIEVAL.md and CHUNKING.md.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

# --- config -----------------------------------------------------------------
DEFAULT_CONFIG = Path(__file__).with_name("rag-config.json")

CONTEXT_PROMPT_VERSION = "v2"
DEFAULT_CONTEXT_SYSTEM_PROMPT = (
    "You situate a passage within its source document so search engines can find it. "
    "Reply with one or two plain sentences of context only: no preamble, no quotes, "
    "no markdown, no bullet points. Name the document's subject/component and where "
    "this passage fits (which section, function, class, command, or step)."
)
DEFAULT_CONTEXT_USER_PROMPT = """<document project="{project}" kind="{kind}" path="{doc_id}">
{document}
</document>

Here is a passage taken from that document:
<passage>
{chunk}
</passage>

Write a short context (1-2 sentences) that situates this passage within the overall \
document to improve search retrieval. Answer with only the context."""

_QWEN3_RR_PREFIX = (
    "<|im_start|>system\nJudge whether the Document meets the requirements "
    "based on the Query and the Instruct provided. Note that the answer can "
    'only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
)
_QWEN3_RR_SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
_QWEN3_RR_TASK = (
    "Given a search query over a software repository, retrieve code and "
    "documentation passages that answer the query"
)


def load_config(path: str | None = None) -> dict:
    p = Path(path) if path else DEFAULT_CONFIG
    return json.loads(p.read_text(encoding="utf-8"))


def chat_completions_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def rag_home() -> Path:
    return Path(
        os.environ.get("RAG_HOME")
        or str(Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "rag-skill")
    ).expanduser()


def project_manifest_path() -> Path:
    return rag_home() / "projects.json"


def context_cache_dir(cfg: dict[str, Any] | None = None) -> Path:
    block = (cfg or {}).get("contextual_llm", {})
    raw = (
        block.get("cache_dir")
        if isinstance(block, dict)
        else None
    )
    return Path(raw or (rag_home() / "context")).expanduser()


def slug_for_cache(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()) or "default"


def load_project_manifest() -> dict[str, Any]:
    path = project_manifest_path()
    if not path.exists():
        return {"version": 1, "projects": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"rag: invalid project manifest {path}: {exc}")
    if not isinstance(data, dict):
        sys.exit(f"rag: invalid project manifest {path}: expected object")
    data.setdefault("version", 1)
    data.setdefault("projects", {})
    if not isinstance(data["projects"], dict):
        sys.exit(f"rag: invalid project manifest {path}: projects must be an object")
    return data


def save_project_manifest(data: dict[str, Any]) -> Path:
    path = project_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug or "project"


def default_project_name(root: str | Path) -> str:
    return slugify(Path(root).expanduser().resolve().name)


def default_collection_name(root: str | Path, kind: str, project_name: str | None = None) -> str:
    name = slugify(project_name or default_project_name(root))
    return f"rag_{name}_{kind}"


def register_project_index(
    root: str | Path,
    *,
    project_name: str,
    kind: str,
    collection: str,
    source_count: int,
    chunk_count: int,
    config: dict[str, Any],
    config_path: str | None,
    qdrant_location: str,
) -> Path:
    manifest = load_project_manifest()
    projects = manifest["projects"]
    key = slugify(project_name)
    root_path = Path(root).expanduser().resolve()
    entry = projects.setdefault(key, {})
    existing_root = entry.get("root")
    if existing_root and Path(existing_root).expanduser().resolve() != root_path:
        digest = hashlib.sha1(str(root_path).encode("utf-8"), usedforsecurity=False).hexdigest()[:8]
        key = f"{key}-{digest}"
        entry = projects.setdefault(key, {})
    entry["name"] = project_name
    entry["root"] = str(root_path)
    collections = entry.setdefault("collections", {})
    collections[kind] = {
        "collection": collection,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "source_count": source_count,
        "chunk_count": chunk_count,
        "config_id": config.get("rag_config_id"),
        "config_path": str(Path(config_path).expanduser().resolve()) if config_path else str(DEFAULT_CONFIG),
        "qdrant_location": qdrant_location,
    }
    return save_project_manifest(manifest)


def resolve_project(selector: str) -> tuple[str, dict[str, Any]]:
    manifest = load_project_manifest()
    projects = manifest["projects"]
    key = slugify(selector)
    if key in projects:
        return key, projects[key]

    expanded = Path(selector).expanduser()
    if expanded.exists():
        selector_root = expanded.resolve()
        matches = []
        for name, project in projects.items():
            root = project.get("root")
            if root and Path(root).expanduser().resolve() == selector_root:
                matches.append((name, project))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            names = ", ".join(name for name, _ in matches)
            sys.exit(f"rag: project selector {selector!r} is ambiguous: {names}")

    available = ", ".join(sorted(projects)) or "(none registered)"
    sys.exit(f"rag: project {selector!r} is not registered. Available projects: {available}")


def _need_deps():
    """Import the optional heavy deps lazily with a friendly message so that
    `--help` and config errors do not require a provisioned environment."""
    try:
        import fastembed  # noqa: F401
        import qdrant_client  # noqa: F401
    except ImportError as exc:  # pragma: no cover - environment dependent
        sys.exit(
            f"rag: missing dependency ({exc.name}). Local RAG is not set up yet.\n"
            f"     Run:  bash {Path(__file__).resolve().parent}/setup-local-rag.sh\n"
            f"     (or:  pip install 'qdrant-client[fastembed]')"
        )


# --- corpus loading ---------------------------------------------------------
# Document/transcript formats for `--kind md`. The kind name is historical:
# this path is the prose/text corpus, not only Markdown. Fixed-name build files
# such as `CMakeLists.txt` are excluded below and stay in `--kind code`.
TEXT_EXTS = (".md", ".markdown", ".mdown", ".mkd", ".mkdn", ".mdx",
             ".txt", ".text", ".rst", ".adoc", ".asciidoc", ".org",
             ".tex", ".vtt", ".srt")
TEXT_FILENAMES = frozenset({
    "AUTHORS", "CHANGELOG", "CODE_OF_CONDUCT", "CONTRIBUTING", "COPYING",
    "INSTALL", "LICENSE", "NOTICE", "README", "SECURITY", "SUPPORT",
})

# Language-aware code set. The C/C++/CUDA/CMake/shell/config extensions (and the
# extensionless build files below) were added 2026-06-09: the original JS/TS/Python
# list silently skipped every `.cc`/`.h`/`.cuh`/`CMakeLists.txt`, so on a C++/CUDA
# repo the `code` corpus loaded almost nothing. (`.md` stays here so `--kind code`
# co-indexes a repo's docs with its code — they are one retrieval task.)
CODE_EXTS = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs",
             ".py", ".go", ".rs", ".java", ".rb",
             ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hh", ".hxx", ".cu", ".cuh",
             ".cmake", ".sh", ".bash", ".zsh", ".yml", ".yaml", ".toml",
             ".css", ".scss", ".less", ".html", ".json", ".jsonc", ".wgsl", ".glsl",
             ".md", ".mdx")
# Extensionless / fixed-name build files that are code by filename, not extension.
CODE_FILENAMES = frozenset({"CMakeLists.txt", "Makefile", "Dockerfile"})
SKIP_DIRS = {"node_modules", "dist", "build", ".output", ".vite", ".nitro",
             ".git", ".jj", ".turbo", "coverage", ".cache", "__pycache__", ".venv"}
SKIP_FILES = {"bun.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"}
VCS_BOUNDARY_MARKERS = (".git", ".jj")


def _has_ext(name: str, exts: tuple[str, ...]) -> bool:
    return name.lower().endswith(exts)


def _is_vcs_root(path: Path) -> bool:
    return any((path / marker).exists() for marker in VCS_BOUNDARY_MARKERS)


def _git_unignored_files(base: Path) -> set[str] | None:
    """Paths under `base` that git does NOT ignore (tracked + untracked-but-unignored),
    base-relative POSIX. None when `base` is not inside a git work tree or git is
    unavailable, so the caller falls back to a plain walk.

    This makes the corpus respect `.gitignore`: generated/build output (an ML repo's
    git-ignored `artifacts/` of multi-MB training traces, a `dist/`/`build/` tree, model
    checkpoints, logs) is never indexed — it is retrieval noise that also blows up index
    time. `-co --exclude-standard` keeps new untracked source you have not committed yet,
    dropping only what `.gitignore` (and global/info excludes) actually ignore.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(base), "ls-files", "-co", "--exclude-standard", "-z"],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return {p for p in out.stdout.split("\0") if p}


def _iter_corpus_files(base: Path, kind: str):
    """Yield indexable files without crossing into nested VCS workspaces.

    The corpus root itself may be a Git worktree or Jujutsu workspace. Only VCS
    roots strictly below it are pruned, so indexing a workspace directly still
    works while indexing its parent does not duplicate that workspace's files.
    """
    if kind == "md":
        def wanted(name: str) -> bool:
            return (
                name not in CODE_FILENAMES
                and (_has_ext(name, TEXT_EXTS) or name in TEXT_FILENAMES)
            )
    elif kind == "code":
        def wanted(name: str) -> bool:
            return _has_ext(name, CODE_EXTS) or name in CODE_FILENAMES
    else:
        sys.exit(f"rag: unknown corpus kind {kind!r} (use md|code)")

    for dirpath, dirnames, filenames in os.walk(base):
        current = Path(dirpath)
        if current != base and _is_vcs_root(current):
            dirnames[:] = []
            continue

        kept_dirs = []
        for dirname in sorted(dirnames):
            child = current / dirname
            if dirname in SKIP_DIRS or _is_vcs_root(child):
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            if wanted(filename):
                yield current / filename


def load_corpus(root: str, kind: str = "md") -> dict[str, str]:
    """Map corpus-root-relative POSIX path -> document text.

    kind="md"   : common prose/text docs under root (Markdown, .txt, .vtt, etc.).
    kind="code" : every CODE_EXTS file, skipping dependency/build dirs + lockfiles.
    """
    base = Path(root).expanduser().resolve()
    if not base.is_dir():
        sys.exit(f"rag: corpus dir not found: {base}")
    unignored = _git_unignored_files(base)  # respect .gitignore; None => not a git repo
    docs: dict[str, str] = {}
    for path in _iter_corpus_files(base, kind):
        rel = path.relative_to(base).as_posix()
        if path.name in SKIP_FILES:
            continue
        if unignored is not None and rel not in unignored:
            continue  # git-ignored generated/build output — never indexed
        try:
            docs[rel] = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:  # pragma: no cover - defensive
            print(f"rag: warning: cannot read {rel}: {exc}", file=sys.stderr)
    return docs


# --- chunking (see CHUNKING.md) ---------------------------------------------
_HEADING = re.compile(r"^[ \t]*#{1,6}[ \t]+", re.MULTILINE)


def _words(text: str) -> list[str]:
    return text.split()


def _fixed(text: str, size: int, overlap: int) -> list[str]:
    w = _words(text)
    if not w:
        return []
    if len(w) <= size:
        return [" ".join(w)]
    step = max(1, size - overlap)
    return [" ".join(w[i:i + size]) for i in range(0, len(w), step) if w[i:i + size]]


def chunk_markdown(text: str, size: int, overlap: int, min_words: int) -> list[str]:
    """Heading-aware: split on Markdown headings, then (a) fall back to fixed
    windows for over-long sections and (b) merge consecutive tiny sections up to
    `min_words` so a heading-dense doc does not explode into one-line chunks."""
    # split into heading-led sections
    sections: list[str] = []
    cur: list[str] = []
    for line in text.splitlines():
        if _HEADING.match(line) and cur:
            sections.append("\n".join(cur))
            cur = [line]
        else:
            cur.append(line)
    if cur:
        sections.append("\n".join(cur))
    # merge tiny adjacent sections up to the min-words floor
    merged: list[str] = []
    buf = ""
    for sec in sections:
        if not sec.strip():
            continue
        buf = f"{buf}\n\n{sec}".strip() if buf else sec
        if len(_words(buf)) >= min_words:
            merged.append(buf)
            buf = ""
    if buf:
        if merged:
            merged[-1] = f"{merged[-1]}\n\n{buf}"
        else:
            merged.append(buf)
    # split any still-too-long section into fixed windows
    out: list[str] = []
    for sec in merged:
        out.extend(_fixed(sec, size, overlap) if len(_words(sec)) > size else [sec])
    return out or _fixed(text, size, overlap)


def chunk_code(text: str, size: int, overlap: int) -> list[str]:
    """Code: pack blank-line-separated blocks up to `size` words (keeps small
    functions/configs whole), splitting any over-long block into fixed windows."""
    blocks = [b for b in re.split(r"\n\s*\n", text) if b.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    n = 0
    for b in blocks:
        bw = len(_words(b))
        if n + bw > size and buf:
            chunks.append("\n\n".join(buf))
            buf, n = [], 0
        buf.append(b)
        n += bw
    if buf:
        chunks.append("\n\n".join(buf))
    out: list[str] = []
    for c in chunks:
        out.extend(_fixed(c, size, overlap) if len(_words(c)) > size else [c])
    return out or _fixed(text, size, overlap)


def chunk(text: str, cfg: dict, kind: str) -> list[str]:
    ch = cfg.get("chunker", {})
    if kind == "code":
        return chunk_code(text, int(ch.get("code_size", 120)), int(ch.get("code_overlap", 20)))
    return chunk_markdown(
        text,
        int(ch.get("size", 350)),
        int(ch.get("overlap", 40)),
        int(ch.get("min_words", 80)),
    )


# --- contextual retrieval (OpenAI-compatible local LLM, index-time) ---------
def contextual_llm_config(cfg: dict[str, Any]) -> dict[str, Any]:
    block = cfg.get("contextual_llm", {})
    return block if isinstance(block, dict) else {}


def contextual_cache_path(project_name: str, kind: str, cfg: dict[str, Any]) -> Path:
    block = contextual_llm_config(cfg)
    cache_model = str(block.get("cache_model") or block.get("model") or "model")
    return context_cache_dir(cfg) / slug_for_cache(cache_model) / slugify(project_name) / f"{kind}.json"


def load_context_cache(project_name: str, kind: str, cfg: dict[str, Any]) -> dict[str, Any]:
    path = contextual_cache_path(project_name, kind, cfg)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_context_cache(project_name: str, kind: str, cfg: dict[str, Any], cache: dict[str, Any]) -> None:
    path = contextual_cache_path(project_name, kind, cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    tmp.replace(path)


def context_cache_key(doc_id: str, chunk_idx: int, raw_text: str) -> str:
    digest = hashlib.sha1(raw_text.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
    return f"{doc_id}\t{chunk_idx}\t{digest}"


def context_header(project_name: str, doc_id: str, kind: str) -> str:
    return f"[{slugify(project_name)}] {doc_id} ({kind})"


def compose_contextual_text(header: str, llm_context: str | None, raw_text: str) -> str:
    parts = [part.strip() for part in (header, llm_context or "") if part and part.strip()]
    return f"{'\n'.join(parts)}\n\n{raw_text}" if parts else raw_text


def doc_window(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars]


def post_chat_completion(
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
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"provider returned HTTP {exc.code}: {detail[:1200]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"could not reach provider at {base_url}: {exc.reason}") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"provider returned invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("provider response was not a JSON object")
    return parsed


def chat_response_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("provider response did not include choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise RuntimeError("provider response choice was not an object")
    message = first.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("provider response choice did not include a message")
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


def render_context_user_prompt(
    template: str,
    *,
    project_name: str,
    kind: str,
    doc_id: str,
    document: str,
    chunk_text: str,
) -> str:
    return template.format(
        project=project_name,
        kind=kind,
        doc_id=doc_id,
        document=document,
        chunk=chunk_text,
    )


def fitted_context_prompt(
    *,
    system_prompt: str,
    user_template: str,
    project_name: str,
    kind: str,
    doc_id: str,
    document: str,
    chunk_text: str,
    max_prompt_chars: int,
) -> str:
    doc = document
    chunk = chunk_text
    floor = 1000
    while True:
        prompt = render_context_user_prompt(
            user_template,
            project_name=project_name,
            kind=kind,
            doc_id=doc_id,
            document=doc,
            chunk_text=chunk,
        )
        if max_prompt_chars <= 0 or len(system_prompt) + len(prompt) <= max_prompt_chars:
            return prompt
        overage = len(system_prompt) + len(prompt) - max_prompt_chars
        trim_by = max(500, overage)
        if len(doc) >= len(chunk) and len(doc) > floor:
            doc = doc[: max(floor, len(doc) - trim_by)]
        elif len(chunk) > floor:
            chunk = chunk[: max(floor, len(chunk) - trim_by)]
        else:
            return prompt[: max(0, max_prompt_chars - len(system_prompt))]


def generate_context_one(
    *,
    project_name: str,
    kind: str,
    doc_id: str,
    document: str,
    chunk_text: str,
    cfg: dict[str, Any],
) -> str:
    block = contextual_llm_config(cfg)
    model = str(block.get("model") or "model")
    base_url = str(
        block.get("base_url")
        or os.environ.get(str(block.get("base_url_env", "RAG_CONTEXT_LLM_BASE_URL")))
        or "http://127.0.0.1:8085/v1"
    )
    api_key_env = str(block.get("api_key_env", "RAG_CONTEXT_LLM_API_KEY"))
    api_key = os.environ.get(api_key_env) if api_key_env else None
    max_tokens = int(block.get("max_tokens", 96))
    timeout = float(block.get("timeout", 180))
    max_chunk_chars = int(block.get("max_chunk_chars", 6000))
    max_prompt_chars = int(block.get("max_prompt_chars", 12000))
    extra_body = block.get("extra_body") if isinstance(block.get("extra_body"), dict) else {}
    if block.get("no_think", True):
        extra_body = {
            **extra_body,
            "chat_template_kwargs": {
                **extra_body.get("chat_template_kwargs", {}),
                "enable_thinking": False,
            },
        }

    system_prompt = str(block.get("system_prompt", DEFAULT_CONTEXT_SYSTEM_PROMPT))
    user_template = str(block.get("user_prompt", DEFAULT_CONTEXT_USER_PROMPT))
    user_prompt = fitted_context_prompt(
        system_prompt=system_prompt,
        user_template=user_template,
        project_name=project_name,
        kind=kind,
        doc_id=doc_id,
        document=document,
        chunk_text=chunk_text[:max_chunk_chars],
        max_prompt_chars=max_prompt_chars,
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": float(block.get("temperature", 0.0)),
        "max_tokens": max_tokens,
        "stream": False,
    }
    body.update(extra_body)
    last = ""
    retries = int(block.get("retries", 4))
    for attempt in range(retries):
        try:
            content = chat_response_content(
                post_chat_completion(
                    base_url=base_url,
                    api_key=api_key,
                    body=body,
                    timeout=timeout,
                )
            )
            out = " ".join(content.split()).strip()
            for prefix in ("Context:", "context:"):
                if out.startswith(prefix):
                    out = out[len(prefix):].strip()
            return out
        except RuntimeError as exc:
            last = str(exc)
            time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"context generation failed for {doc_id}: {last[:300]}")


def contextualize_chunks(
    *,
    chunks: list[str],
    meta: list[dict[str, Any]],
    docs: dict[str, str],
    cfg: dict[str, Any],
    project_name: str,
    kind: str,
) -> list[str]:
    block = contextual_llm_config(cfg)
    if not block.get("enabled"):
        return chunks
    apply_to = tuple(block.get("apply_to", ["md", "code"]))
    headers_enabled = bool(cfg.get("contextual_header", True))
    if kind not in apply_to:
        return [
            compose_contextual_text(context_header(project_name, m["doc_id"], kind), None, chunk)
            if headers_enabled
            else chunk
            for chunk, m in zip(chunks, meta, strict=True)
        ]

    cache = load_context_cache(project_name, kind, cfg)
    meta_block = cache.get("__meta__")
    current_meta = {
        "prompt_version": CONTEXT_PROMPT_VERSION,
        "config_id": cfg.get("rag_config_id"),
        "project": project_name,
        "kind": kind,
        "cache_model": block.get("cache_model") or block.get("model"),
        "max_doc_chars": int(block.get("max_doc_chars", 12000)),
    }
    if isinstance(meta_block, dict) and any(meta_block.get(k) != v for k, v in current_meta.items()):
        cache = {}

    max_doc_chars = int(block.get("max_doc_chars", 12000))
    tasks: list[tuple[int, str, str, str, str]] = []
    contexts: list[str | None] = [None] * len(chunks)
    for i, (raw_text, m) in enumerate(zip(chunks, meta, strict=True)):
        doc_id = str(m["doc_id"])
        key = context_cache_key(doc_id, int(m["chunk_idx"]), raw_text)
        cached = cache.get(key)
        if isinstance(cached, str) and cached.strip():
            contexts[i] = cached
            continue
        tasks.append((i, key, doc_id, doc_window(docs.get(doc_id, ""), max_doc_chars), raw_text))

    if tasks:
        print(
            f"context: {project_name}/{kind}: {len(chunks) - len(tasks)} cached, "
            f"{len(tasks)} to generate -> {contextual_cache_path(project_name, kind, cfg)}"
        )
    workers = max(1, int(block.get("workers", 8)))
    required = bool(block.get("required", True))
    done = 0
    started = time.time()

    def work(task: tuple[int, str, str, str, str]) -> tuple[int, str, str]:
        i, key, doc_id, document, raw_text = task
        return i, key, generate_context_one(
            project_name=project_name,
            kind=kind,
            doc_id=doc_id,
            document=document,
            chunk_text=raw_text,
            cfg=cfg,
        )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        for i, key, context in executor.map(work, tasks):
            contexts[i] = context
            cache[key] = context
            done += 1
            if done % 50 == 0:
                cache["__meta__"] = current_meta
                save_context_cache(project_name, kind, cfg, cache)
                rate = done / max(time.time() - started, 1e-9)
                remaining = (len(tasks) - done) / max(rate, 1e-9)
                print(f"  context {done}/{len(tasks)}  {rate:.1f}/s  ETA {remaining:.0f}s", flush=True)

    cache["__meta__"] = current_meta
    save_context_cache(project_name, kind, cfg, cache)
    if tasks:
        elapsed = time.time() - started
        print(f"context: {project_name}/{kind}: generated {done} in {elapsed:.0f}s")

    embedded: list[str] = []
    missing = 0
    for raw_text, m, context in zip(chunks, meta, contexts, strict=True):
        if not context:
            missing += 1
            if required:
                sys.exit(f"index: missing generated context for {m['doc_id']}#{m['chunk_idx']}")
        header = context_header(project_name, str(m["doc_id"]), kind) if headers_enabled else ""
        embedded.append(compose_contextual_text(header, context, raw_text))
    if missing:
        print(f"context: warning: {missing} chunks missing context; indexed with header/raw only", file=sys.stderr)
    return embedded


# --- embedding (FastEmbed, CPU) ---------------------------------------------
@lru_cache(maxsize=4)
def _dense(model: str):
    from fastembed import TextEmbedding
    return TextEmbedding(model)


@lru_cache(maxsize=4)
def _sparse(model: str):
    from fastembed import SparseTextEmbedding
    return SparseTextEmbedding(model)


@lru_cache(maxsize=4)
def _reranker(model: str):
    from fastembed.rerank.cross_encoder import TextCrossEncoder
    return TextCrossEncoder(model)


def embed_documents(texts: list[str], cfg: dict):
    """Return (dense_vectors[list[list[float]]], sparse_embeddings[list])."""
    emb = cfg["embedding"]
    dense = [v.tolist() for v in _dense(emb["dense_model"]).embed(texts)]
    sparse = list(_sparse(emb["sparse_model"]).embed(texts))
    return dense, sparse


def embed_query(text: str, cfg: dict):
    """Return (dense_vector[list[float]], sparse_embedding) for a query.
    FastEmbed exposes query_embed for asymmetric models (e.g. bm25)."""
    emb = cfg["embedding"]
    dv = list(_dense(emb["dense_model"]).query_embed(text))[0].tolist()
    sv = list(_sparse(emb["sparse_model"]).query_embed(text))[0]
    return dv, sv


def to_sparse_vector(sparse_embedding):
    """FastEmbed SparseEmbedding -> qdrant SparseVector."""
    from qdrant_client import models
    return models.SparseVector(
        indices=sparse_embedding.indices.tolist(),
        values=sparse_embedding.values.tolist(),
    )


def qwen3_rerank_inputs(query: str, texts: list[str]) -> tuple[str, list[str]]:
    wrapped_query = f"{_QWEN3_RR_PREFIX}<Instruct>: {_QWEN3_RR_TASK}\n<Query>: {query}\n"
    wrapped_texts = [f"<Document>: {text}{_QWEN3_RR_SUFFIX}" for text in texts]
    return wrapped_query, wrapped_texts


def http_rerank(query: str, texts: list[str], rr: dict[str, Any]) -> list[float]:
    endpoint = str(rr.get("endpoint") or os.environ.get("RAG_RERANK_ENDPOINT") or "").rstrip("/")
    if not endpoint:
        sys.exit("rag: rerank.backend=http requires rerank.endpoint or $RAG_RERANK_ENDPOINT")
    model = str(rr.get("model") or os.environ.get("RAG_RERANK_MODEL") or "")
    if not model:
        sys.exit("rag: rerank.backend=http requires rerank.model or $RAG_RERANK_MODEL")
    if rr.get("template") == "qwen3":
        query, texts = qwen3_rerank_inputs(query, texts)
    body = json.dumps({
        "model": model,
        "query": query,
        "documents": texts,
        "return_documents": False,
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{endpoint}/rerank",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=float(rr.get("timeout", 180))) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        sys.exit(f"rag: reranker returned HTTP {exc.code}: {detail[:1200]}")
    except urllib.error.URLError as exc:
        sys.exit(f"rag: could not reach reranker at {endpoint}: {exc.reason}")
    if not isinstance(parsed, dict):
        sys.exit("rag: reranker response was not a JSON object")
    scores = [0.0] * len(texts)
    for item in parsed.get("results", []):
        if not isinstance(item, dict):
            continue
        idx = item.get("index")
        if isinstance(idx, int) and 0 <= idx < len(scores):
            scores[idx] = float(item.get("relevance_score", item.get("score", 0.0)))
    return scores


def rerank(query: str, texts: list[str], cfg: dict) -> list[float]:
    rr = cfg.get("rerank", {})
    backend = str(rr.get("backend", "fastembed")).lower()
    if backend in {"http", "infinity", "vllm", "jina"}:
        return http_rerank(query, texts, rr)
    return list(_reranker(rr["model"]).rerank(query, texts))


def payload_display_text(payload: dict[str, Any]) -> str:
    return str(payload.get("raw_text") or payload.get("text") or "")


def payload_rerank_text(payload: dict[str, Any], cfg: dict[str, Any]) -> str:
    rr = cfg.get("rerank", {})
    if rr.get("use_contextualized_text", True):
        text = payload.get("contextualized_text")
        if isinstance(text, str) and text.strip():
            return text
    return payload_display_text(payload)


# --- retrieval ---------------------------------------------------------------
def retrieve_chunks(
    client: Any,
    collection: str,
    query: str,
    cfg: dict[str, Any],
    top_k: int,
    *,
    do_rerank: bool,
) -> list[tuple[Any, float]]:
    """Return top chunks from one Qdrant collection using the standard RAG path."""
    from qdrant_client import models

    dv, sv = embed_query(query, cfg)
    prefetch = int(cfg.get("hybrid", {}).get("prefetch", 60))
    rr = cfg.get("rerank", {})
    # Fetch enough to feed the reranker when it is on, else just top_k.
    fuse_limit = max(top_k, int(rr.get("top_n", 50))) if (do_rerank and rr.get("enabled")) else top_k
    fusion = models.Fusion.DBSF if cfg.get("hybrid", {}).get("fusion") == "dbsf" else models.Fusion.RRF

    hits = client.query_points(
        collection,
        prefetch=[
            models.Prefetch(query=dv, using="dense", limit=prefetch),
            models.Prefetch(query=to_sparse_vector(sv), using="sparse", limit=prefetch),
        ],
        query=models.FusionQuery(fusion=fusion),
        limit=fuse_limit,
        with_payload=True,
    ).points

    if do_rerank and rr.get("enabled") and hits:
        texts = [payload_rerank_text(h.payload or {}, cfg) for h in hits]
        scores = rerank(query, texts, cfg)  # aligned to `hits`
        order = sorted(range(len(hits)), key=lambda i: scores[i], reverse=True)
        ranked = [(hits[i], scores[i]) for i in order]
    else:
        ranked = [(h, h.score) for h in hits]
    return ranked[:top_k]


def project_targets(client: Any, selector: str, kind: str) -> list[tuple[str, str, str]]:
    """Resolve a registered project selector to existing collection targets."""
    project_key, project = resolve_project(selector)
    collections = project.get("collections", {})
    selected_kinds = sorted(collections) if kind == "all" else [kind]
    targets = []
    for selected_kind in selected_kinds:
        info = collections.get(selected_kind)
        if not info:
            continue
        coll = info.get("collection")
        if not coll:
            continue
        if client.collection_exists(coll):
            targets.append((project_key, selected_kind, coll))
        else:
            print(
                f"rag: warning: registered collection '{coll}' for "
                f"{project_key}/{selected_kind} does not exist",
                file=sys.stderr,
            )
    if not targets:
        available = ", ".join(sorted(collections)) or "(none)"
        sys.exit(
            f"rag: project '{project_key}' has no available collection for "
            f"kind={kind}; registered kinds: {available}"
        )
    return targets


# --- Qdrant client ----------------------------------------------------------
def qdrant_url() -> str:
    return os.environ.get("QDRANT_URL", "http://localhost:6333")


def qdrant_path() -> str:
    home = os.environ.get("RAG_HOME") or str(
        Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "rag-skill"
    )
    return os.environ.get("QDRANT_PATH", str(Path(home) / "qdrant"))


def server_up(url: str | None = None, timeout: float = 1.5) -> bool:
    import urllib.request
    base = (url or qdrant_url()).rstrip("/")
    # /healthz on current builds; / returns version JSON on every build (older
    # Qdrant lacks /healthz) — so probe both before declaring the server down.
    for ep in ("/healthz", "/"):
        try:
            with urllib.request.urlopen(f"{base}{ep}", timeout=timeout) as r:
                if r.status == 200:
                    return True
        except Exception:
            continue
    return False


def get_client(force_local: bool = False):
    """A live Qdrant server ($QDRANT_URL) if reachable (unless force_local), else
    embedded on-disk mode ($QDRANT_PATH). The on-disk fallback needs no daemon —
    local-first."""
    _need_deps()
    from qdrant_client import QdrantClient
    if not force_local and server_up():
        return QdrantClient(url=qdrant_url()), f"server:{qdrant_url()}"
    path = qdrant_path()
    Path(path).mkdir(parents=True, exist_ok=True)
    try:
        return QdrantClient(path=path), f"local:{path}"
    except RuntimeError as exc:
        # Embedded mode is single-writer: it takes an exclusive lock on the dir.
        msg = str(exc).lower()
        if "already accessed" in msg or "lock" in msg:
            sys.exit(
                f"rag: embedded Qdrant store at {path} is in use by another rag "
                f"process (embedded mode is single-writer). Wait for indexing to "
                f"finish, or run a Qdrant server (set QDRANT_URL) for concurrent access."
            )
        raise
