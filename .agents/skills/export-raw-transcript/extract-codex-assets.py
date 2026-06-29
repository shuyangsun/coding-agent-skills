#!/usr/bin/env python3
"""Extract local file assets referenced by a Codex JSONL transcript.

Codex Desktop transcripts usually do not embed attached file bytes the way
Claude Code does. They preserve user-visible text plus structured attachment
containers such as `images`, `local_images`, and `text_elements`. This script
streams the copied transcript, finds local file paths that came from human input
or those attachment containers, and copies still-existing files into a sibling
assets directory.

The transcript text is never written to stdout. Output is only an inventory or a
manifest containing paths, sizes, hashes, and transcript coordinates.

Usage:
  python3 extract-codex-assets.py [options] <codex-rollout.jsonl>

Options:
  --out-dir <dir>     Write copied assets here (created only if assets exist).
  --dir-name <name>   Basename recorded as the manifest "dir" (defaults to the
                      basename of --out-dir).
  --manifest          Also write `<out-dir>/_manifest.json`.
  --original <path>   A known original absolute path for an attached asset
                      (repeatable). Codex has no embedded blob hash to verify, so
                      this explicit hint is copied when the file exists.
  --originals-file <p>
                      Read newline-delimited original paths from a file.
  --emit metadata|inventory
                      stdout format. "metadata" (default) prints the JSON object;
                      "inventory" prints a short human summary.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import mimetypes
import os
import re
import shutil
import sys
import urllib.parse
from dataclasses import dataclass, field


PATH_EXT = (
    "png|jpe?g|gif|webp|bmp|svg|tiff?|heic|heif|pdf|txt|csv|tsv|md|json|"
    "ya?ml|toml|xml|html?|css|js|jsx|ts|tsx|py|rb|go|rs|swift|c|cc|cpp|cxx|"
    "h|hh|hpp|m|mm|sh|bash|zsh|fish|sql|sqlite|db|xlsx?|docx?|pptx?|zip|"
    "tar|gz|tgz|mp4|mov|mp3|wav"
)
PATH_RE = re.compile(
    r"(/[^\n\"'`<>]*?\.(?:" + PATH_EXT + r"))(?=$|[\s\"'`,;:)\]}>])",
    re.IGNORECASE,
)
STRUCTURED_CONTAINERS = ("images", "local_images", "text_elements")
PATH_KEY_HINTS = ("path", "file", "image", "uri", "url")
SOURCE_PRIORITY = {"path_mention": 1, "original_hint": 2, "attachment": 3}


def warn(msg: str) -> None:
    sys.stderr.write("extract-codex-assets: %s\n" % msg)


def as_dict(value):
    return value if isinstance(value, dict) else {}


def as_str(value):
    return value if isinstance(value, str) and value else None


def sha256_file(path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def mirror_relpath(abs_path: str) -> str | None:
    """Map an absolute path to a safe relative path under the assets dir."""
    p = abs_path.replace("\\", "/").lstrip("/")
    parts = []
    for comp in p.split("/"):
        if comp in ("", "."):
            continue
        if comp == "..":
            return None
        parts.append(comp)
    if not parts:
        return None
    return "/".join(parts)


def normalize_path(raw: str) -> str | None:
    s = raw.strip().strip("\"'`")
    s = s.rstrip(".,;:)]}>")
    if s.startswith("file://"):
        parsed = urllib.parse.urlparse(s)
        s = urllib.parse.unquote(parsed.path)
    # Drop common editor-style line/column suffixes after trying the literal.
    candidates = [s]
    without_line = re.sub(r":\d+(?::\d+)?$", "", s)
    if without_line != s:
        candidates.append(without_line)
    for cand in candidates:
        if os.path.isabs(cand):
            return os.path.abspath(cand)
    return None


def media_type_for(path: str) -> str | None:
    media_type, _encoding = mimetypes.guess_type(path)
    return media_type


def mtime_utc(path: str) -> str | None:
    try:
        ts = os.path.getmtime(path)
    except OSError:
        return None
    value = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_under(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) == os.path.abspath(root)
    except ValueError:
        return False


def is_under_any(path: str, roots: list[str]) -> bool:
    return any(is_under(path, root) for root in roots)


@dataclass
class Candidate:
    abs_path: str
    source_kind: str
    source_refs: list[str] = field(default_factory=list)
    first_seen: int = 0

    def add_ref(self, source_kind: str, source_ref: str) -> None:
        if SOURCE_PRIORITY.get(source_kind, 0) > SOURCE_PRIORITY.get(self.source_kind, 0):
            self.source_kind = source_kind
        if source_ref and source_ref not in self.source_refs:
            self.source_refs.append(source_ref)


@dataclass
class Asset:
    abs_path: str
    relpath: str
    kind: str
    media_type: str | None
    bytes: int
    sha256: str
    mtime_utc: str | None
    source_kind: str
    source_refs: list[str]


def add_candidate(
    candidates: dict[str, Candidate],
    raw_path: str,
    source_kind: str,
    source_ref: str,
    counter: list[int],
) -> None:
    path = normalize_path(raw_path)
    if path is None:
        return
    existing = candidates.get(path)
    if existing is None:
        counter[0] += 1
        candidates[path] = Candidate(
            abs_path=path,
            source_kind=source_kind,
            source_refs=[source_ref] if source_ref else [],
            first_seen=counter[0],
        )
    else:
        existing.add_ref(source_kind, source_ref)


def record_ref(rec: dict, line_no: int) -> str:
    payload = as_dict(rec.get("payload"))
    meta = as_dict(payload.get("internal_chat_message_metadata_passthrough"))
    for value in (
        payload.get("client_id"),
        payload.get("id"),
        payload.get("call_id"),
        meta.get("turn_id"),
        rec.get("id"),
    ):
        text = as_str(value)
        if text:
            return text
    return "line%d" % line_no


def add_text_paths(
    candidates: dict[str, Candidate],
    text: str,
    source_ref: str,
    counter: list[int],
) -> None:
    for match in PATH_RE.findall(text):
        add_candidate(candidates, match, "path_mention", source_ref, counter)


def iter_structured_paths(node, trail: str = ""):
    if isinstance(node, dict):
        for key, value in node.items():
            child = ("%s.%s" % (trail, key)) if trail else str(key)
            key_l = str(key).lower()
            if isinstance(value, str):
                if value.startswith("/") or value.startswith("file://") or any(h in key_l for h in PATH_KEY_HINTS):
                    yield value, child
            elif isinstance(value, (dict, list)):
                yield from iter_structured_paths(value, child)
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            child = "%s[%d]" % (trail, idx)
            if isinstance(value, str):
                if value.startswith("/") or value.startswith("file://"):
                    yield value, child
            elif isinstance(value, (dict, list)):
                yield from iter_structured_paths(value, child)


def add_structured_paths(
    candidates: dict[str, Candidate],
    node,
    source_ref: str,
    counter: list[int],
) -> None:
    for raw_path, trail in iter_structured_paths(node):
        add_candidate(candidates, raw_path, "attachment", "%s#%s" % (source_ref, trail), counter)


def add_repo_root(roots: list[str], value) -> None:
    text = as_str(value)
    if not text:
        return
    path = os.path.abspath(text)
    if os.path.isdir(path) and path not in roots:
        roots.append(path)


def collect(path: str, originals: list[str]) -> tuple[list[Asset], list[str]]:
    candidates: dict[str, Candidate] = {}
    counter = [0]
    repo_roots: list[str] = []

    for original in originals:
        add_candidate(candidates, original, "original_hint", "flag:--asset-original", counter)

    try:
        handle = open(path, "r", encoding="utf-8", errors="replace")
    except OSError as exc:
        warn("cannot open %s: %s" % (path, exc))
        return [], []

    with handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if not isinstance(rec, dict):
                continue

            payload = as_dict(rec.get("payload"))
            payload_type = as_str(payload.get("type"))
            source_base = record_ref(rec, line_no)

            if rec.get("type") == "session_meta":
                add_repo_root(repo_roots, payload.get("cwd") or rec.get("cwd"))
            elif rec.get("type") == "turn_context":
                add_repo_root(repo_roots, payload.get("cwd"))
                roots = payload.get("workspace_roots")
                if isinstance(roots, list):
                    for root in roots:
                        add_repo_root(repo_roots, root)

            if payload_type == "user_message":
                text = as_str(payload.get("message"))
                if text:
                    add_text_paths(candidates, text, "%s#message" % source_base, counter)
                for key in STRUCTURED_CONTAINERS:
                    value = payload.get(key)
                    if value:
                        add_structured_paths(candidates, value, "%s#%s" % (source_base, key), counter)
            elif payload_type == "message" and payload.get("role") == "user":
                content = payload.get("content")
                if isinstance(content, str):
                    add_text_paths(candidates, content, "%s#content" % source_base, counter)
                elif isinstance(content, list):
                    for idx, block in enumerate(content):
                        block_ref = "%s#content[%d]" % (source_base, idx)
                        if isinstance(block, dict):
                            text = as_str(block.get("text"))
                            if text:
                                add_text_paths(candidates, text, "%s.text" % block_ref, counter)
                            block_type = as_str(block.get("type"))
                            if block_type not in ("input_text", "text"):
                                add_structured_paths(candidates, block, block_ref, counter)
                        elif isinstance(block, str):
                            add_text_paths(candidates, block, block_ref, counter)
                for key in STRUCTURED_CONTAINERS:
                    value = payload.get(key)
                    if value:
                        add_structured_paths(candidates, value, "%s#%s" % (source_base, key), counter)

    assets: list[Asset] = []
    used_relpaths: dict[str, str] = {}
    for cand in sorted(candidates.values(), key=lambda item: item.first_seen):
        if not os.path.isfile(cand.abs_path):
            continue
        if cand.source_kind == "path_mention" and is_under_any(cand.abs_path, repo_roots):
            continue
        rel = mirror_relpath(cand.abs_path)
        if rel is None:
            continue
        sha = sha256_file(cand.abs_path)
        if sha is None:
            continue
        if used_relpaths.get(rel, sha) != sha:
            root, dot, ext = rel.rpartition(".")
            rel = "%s-%s%s%s" % (root or rel, sha[:8], dot, ext)
        used_relpaths[rel] = sha
        try:
            size = os.path.getsize(cand.abs_path)
        except OSError:
            continue
        assets.append(
            Asset(
                abs_path=cand.abs_path,
                relpath=rel,
                kind="input",
                media_type=media_type_for(cand.abs_path),
                bytes=size,
                sha256=sha,
                mtime_utc=mtime_utc(cand.abs_path),
                source_kind=cand.source_kind,
                source_refs=cand.source_refs,
            )
        )
    return assets, repo_roots


def write_assets(assets: list[Asset], out_dir: str) -> None:
    for asset in assets:
        dest = os.path.join(out_dir, asset.relpath)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(asset.abs_path, dest)


def build_metadata(assets: list[Asset], dir_name: str | None) -> dict:
    items = []
    for asset in assets:
        items.append({
            "path": asset.relpath,
            "kind": asset.kind,
            "media_type": asset.media_type,
            "bytes": asset.bytes,
            "sha256": asset.sha256,
            "origin": "disk",
            "source_ref": asset.source_refs[0] if asset.source_refs else None,
            "source_refs": asset.source_refs,
            "source_kind": asset.source_kind,
            "original_path": asset.abs_path,
            "mtime_utc": asset.mtime_utc,
        })
    return {
        "dir": dir_name if items else None,
        "count": len(items),
        "items": items,
    }


def write_manifest(obj: dict, out_dir: str) -> None:
    dest = os.path.join(out_dir, "_manifest.json")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, indent=2))
        fh.write("\n")


def emit_inventory(assets: list[Asset]) -> None:
    if not assets:
        sys.stdout.write("assets: none\n")
        return
    sys.stdout.write("assets: %d (%d input / 0 output)\n" % (len(assets), len(assets)))
    for asset in assets:
        sys.stdout.write("  - [%s] %s  %s  %d bytes  %s\n" % (
            asset.kind,
            asset.media_type or "?",
            asset.source_kind,
            asset.bytes,
            asset.relpath,
        ))


def main() -> int:
    out_dir = None
    dir_name = None
    originals: list[str] = []
    originals_file = None
    want_manifest = False
    emit = "metadata"
    transcript = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--out-dir":
            i += 1
            out_dir = args[i] if i < len(args) else None
        elif arg.startswith("--out-dir="):
            out_dir = arg.split("=", 1)[1]
        elif arg == "--dir-name":
            i += 1
            dir_name = args[i] if i < len(args) else None
        elif arg.startswith("--dir-name="):
            dir_name = arg.split("=", 1)[1]
        elif arg == "--manifest":
            want_manifest = True
        elif arg == "--original":
            i += 1
            if i < len(args):
                originals.append(args[i])
        elif arg.startswith("--original="):
            originals.append(arg.split("=", 1)[1])
        elif arg == "--originals-file":
            i += 1
            originals_file = args[i] if i < len(args) else None
        elif arg.startswith("--originals-file="):
            originals_file = arg.split("=", 1)[1]
        elif arg == "--emit":
            i += 1
            emit = args[i] if i < len(args) else emit
        elif arg.startswith("--emit="):
            emit = arg.split("=", 1)[1]
        elif arg in ("-h", "--help"):
            sys.stdout.write(__doc__ or "")
            return 0
        elif arg.startswith("--"):
            warn("unknown option: %s" % arg)
            return 2
        else:
            if transcript is not None:
                warn("unexpected extra argument: %s" % arg)
                return 2
            transcript = arg
        i += 1

    if not transcript:
        warn("missing transcript path")
        return 2
    if dir_name is None and out_dir:
        dir_name = os.path.basename(out_dir.rstrip("/"))
    if originals_file:
        try:
            with open(originals_file, encoding="utf-8") as fh:
                for line in fh:
                    line = line.rstrip("\n")
                    if line:
                        originals.append(line)
        except OSError as exc:
            warn("cannot read originals file %s: %s" % (originals_file, exc))

    assets, _repo_roots = collect(transcript, originals)

    if out_dir and assets:
        try:
            write_assets(assets, out_dir)
            if want_manifest:
                write_manifest(build_metadata(assets, dir_name), out_dir)
        except OSError as exc:
            warn("failed writing assets to %s: %s" % (out_dir, exc))
            return 1

    if emit == "inventory":
        emit_inventory(assets)
    else:
        sys.stdout.write(json.dumps(build_metadata(assets, dir_name), ensure_ascii=False, indent=2))
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
