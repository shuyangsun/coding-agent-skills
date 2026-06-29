#!/usr/bin/env python3
"""Extract binary assets (images, documents) from a Claude Code JSONL transcript.

Companion to parse-claude-transcript.sh. Claude Code embeds user-attached images
and documents directly in the transcript as base64 inside `image` / `document`
content blocks, so the bytes are *in the transcript* — no dependency on the
original file still existing on disk. This script streams the transcript in a
subprocess (json.loads per line; never the whole file in memory) and:

  * finds every base64-encoded `image`/`document` block,
  * classifies each as INPUT (a human attached it) or OUTPUT (a tool returned it
    or the model produced it) from its structural position in the record,
  * de-duplicates identical blobs by sha256,
  * writes each decoded blob into an assets directory, and
  * prints a JSON description of the assets for the metadata sidecar.

It NEVER writes transcript text/bytes to stdout (only sha256, sizes, media types,
paths, and transcript record ids), so the caller can fold the result into
metadata without surfacing transcript contents to the model.

## Reconstructing a precise, collision-free path per asset

Two attachments can share a basename (two different `screenshot.png`s), so a flat
directory would collide and lose provenance. Instead each asset is stored at a
path that *reconstructs its origin*, mirrored under the assets directory (the
exported transcript is never modified):

  * If the asset's true on-disk origin is known and verified — a `--original`
    path, or an absolute path mentioned in a human turn — that exists and whose
    bytes sha256-match the embedded blob, the asset is stored at that absolute
    path mirrored under the assets dir (leading "/" dropped), e.g.
    `<assets>/Users/alice/Desktop/Screenshot.png`. `origin` = "disk".
  * Otherwise the blob lives only inside the transcript, so it is stored under a
    reserved `_embedded/<kind>/` subtree keyed by the transcript record id and
    block index — a precise reference back into the transcript. `origin` =
    "transcript".

Usage:
  python3 extract-claude-assets.py [options] <transcript.jsonl>

Options:
  --out-dir <dir>     Write extracted assets here (created only if assets exist).
                      Omit for a dry inventory (nothing is written).
  --dir-name <name>   Basename recorded as the manifest "dir" (defaults to the
                      basename of --out-dir).
  --manifest          Also write `<out-dir>/_manifest.json` describing every
                      asset (the same object as `--emit metadata`). No-op without
                      --out-dir or when there are no assets.
  --original <path>   A known original absolute path for an attached asset
                      (repeatable). Used only if it exists and sha256-matches an
                      embedded blob, so a wrong hint is safely ignored.
  --originals-file <p>
                      Read newline-delimited original paths from a file (lets a
                      caller pass paths containing spaces safely). Combined with
                      any --original values.
  --emit metadata|inventory
                      stdout format. "metadata" (default) prints the JSON object
                      describing the assets. "inventory" prints a short human
                      summary.

Top-level entries beginning with "_" are skill-generated (`_manifest.json`,
`_embedded/`); every other entry mirrors an absolute source path.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys

# media_type -> file extension for the common attachment types. Anything else
# falls back to the subtype (after "/") sanitized, then "bin".
MEDIA_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/bmp": "bmp",
    "image/svg+xml": "svg",
    "image/tiff": "tiff",
    "image/heic": "heic",
    "image/heif": "heif",
    "application/pdf": "pdf",
    "text/plain": "txt",
    "text/csv": "csv",
    "text/markdown": "md",
    "application/json": "json",
}

# Extensions worth treating as an attachment when an absolute path is mentioned in
# a human turn (used only to *verify* a real on-disk origin, never to harvest).
PATH_EXT = (
    "png|jpe?g|gif|webp|bmp|svg|tiff?|heic|heif|pdf|txt|csv|tsv|md|json|"
    "xlsx?|docx?|pptx?|zip|tar|gz|mp4|mov|mp3|wav"
)
PATH_RE = re.compile(
    r"(/[^\n\"']*?\.(?:" + PATH_EXT + r"))(?=$|[\s\"'.,;:)\]}>])",
    re.IGNORECASE,
)


def warn(msg: str) -> None:
    sys.stderr.write("extract-claude-assets: %s\n" % msg)


def ext_for(media_type: str | None) -> str:
    if not media_type:
        return "bin"
    mt = media_type.lower().strip()
    if mt in MEDIA_EXT:
        return MEDIA_EXT[mt]
    sub = mt.split("/", 1)[1] if "/" in mt else mt
    sub = sub.split("+", 1)[0]
    sub = re.sub(r"[^a-z0-9]+", "", sub)
    return sub or "bin"


def decode_b64(data: str) -> bytes | None:
    if not isinstance(data, str) or not data:
        return None
    s = "".join(data.split())  # drop any embedded whitespace/newlines
    s += "=" * (-len(s) % 4)  # tolerate missing padding
    try:
        return base64.b64decode(s, validate=False)
    except Exception:
        return None


def sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


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
    """Map an absolute path to a safe relative path under the assets dir.

    Drops the leading separators and rejects any '..' / empty component so a
    crafted path can never escape the assets directory.
    """
    p = abs_path.replace("\\", "/").lstrip("/")
    parts = []
    for comp in p.split("/"):
        if comp in ("", ".", ".."):
            if comp == "..":
                return None
            continue
        parts.append(comp)
    if not parts:
        return None
    return "/".join(parts)


class Asset:
    __slots__ = ("sha256", "data", "media_type", "ext", "kind", "source_ref",
                 "record_uuid", "block_path", "relpath", "origin")

    def __init__(self, sha, data, media_type, ext, kind, record_uuid, block_path):
        self.sha256 = sha
        self.data = data
        self.media_type = media_type
        self.ext = ext
        self.kind = kind
        self.record_uuid = record_uuid
        self.block_path = block_path
        self.source_ref = "%s#%s" % (record_uuid or "rec", block_path)
        self.relpath = None
        self.origin = None


def collect(path: str):
    """Return (assets, human_paths) from the transcript.

    assets: list of unique Asset (first occurrence order, deduped by sha256).
    human_paths: list of absolute path strings mentioned in human user turns.
    """
    by_sha: dict[str, Asset] = {}
    order: list[Asset] = []
    human_paths: list[str] = []

    try:
        fh = open(path, "r", encoding="utf-8", errors="replace")
    except OSError as exc:
        warn("cannot open %s: %s" % (path, exc))
        return [], []

    rec_index = 0
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec_index += 1
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if not isinstance(rec, dict):
                continue

            rectype = rec.get("type")
            uuid = rec.get("uuid") or ("rec%d" % rec_index)
            msg = rec.get("message")
            role = msg.get("role") if isinstance(msg, dict) else None
            is_sidechain = rec.get("isSidechain") is True
            is_meta = rec.get("isMeta") is True or rec.get("isCompactSummary") is True
            human_turn = (
                rectype == "user" and role == "user"
                and not is_sidechain and not is_meta
            )
            base_output = rectype == "assistant"

            def visit(node, trail, output_ctx):
                if isinstance(node, dict):
                    bt = node.get("type")
                    if bt == "tool_result":
                        output_ctx = True
                    if bt in ("image", "document"):
                        handle_block(node, trail, output_ctx)
                        # don't descend into a blob's own source
                        return
                    for k, v in node.items():
                        oc = output_ctx or (k == "toolUseResult")
                        if isinstance(v, (dict, list)):
                            visit(v, trail + "." + k, oc)
                elif isinstance(node, list):
                    for i, item in enumerate(node):
                        visit(item, trail + "[%d]" % i, output_ctx)

            def handle_block(block, trail, output_ctx):
                src = block.get("source")
                if not isinstance(src, dict):
                    return
                if src.get("type") not in ("base64", None):
                    # url / file_id references carry no bytes in the transcript
                    return
                data = src.get("data")
                raw = decode_b64(data)
                if raw is None:
                    return
                media_type = src.get("media_type")
                if output_ctx:
                    kind = "output"
                elif human_turn:
                    kind = "input"
                else:
                    kind = "output"
                sha = sha256_bytes(raw)
                if sha in by_sha:
                    return
                a = Asset(sha, raw, media_type, ext_for(media_type), kind,
                          uuid, trail.lstrip("."))
                by_sha[sha] = a
                order.append(a)

            # Assets live in message content; tool output may also appear under a
            # top-level toolUseResult. Walk both with the right output context.
            if isinstance(msg, dict):
                visit(msg.get("content"), "content", base_output)
            if "toolUseResult" in rec:
                visit(rec.get("toolUseResult"), "toolUseResult", True)

            if human_turn and isinstance(msg, dict):
                content = msg.get("content")
                texts = []
                if isinstance(content, str):
                    texts.append(content)
                elif isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "text":
                            t = b.get("text")
                            if isinstance(t, str):
                                texts.append(t)
                for txt in texts:
                    for m in PATH_RE.findall(txt):
                        human_paths.append(m)

    return order, human_paths


def resolve_origins(assets, human_paths, originals):
    """Assign relpath + origin to each asset.

    Verifies candidate on-disk paths (--original first, then human-turn mentions)
    by existence and sha256 match, so a path mirror is only used when we are
    certain it is the same bytes. Everything else falls back to a precise
    transcript-coordinate path under _embedded/.
    """
    sha_to_path: dict[str, str] = {}
    seen_paths = []
    for p in list(originals) + list(human_paths):
        if not p or p in seen_paths:
            continue
        seen_paths.append(p)
        if not os.path.isfile(p):
            continue
        fsha = sha256_file(p)
        if fsha and fsha not in sha_to_path:
            sha_to_path[fsha] = os.path.abspath(p)

    used: dict[str, str] = {}  # relpath -> sha (collision guard)
    for a in assets:
        rel = None
        if a.sha256 in sha_to_path:
            rel = mirror_relpath(sha_to_path[a.sha256])
            if rel is not None:
                a.origin = "disk"
        if rel is None:
            stem = (a.record_uuid or "rec").replace("/", "-")
            block = a.block_path.replace("[", "-").replace("]", "").replace(".", "-")
            rel = "_embedded/%s/%s-%s.%s" % (a.kind, stem, block, a.ext)
            a.origin = "transcript"
        # Guard against two distinct blobs landing on one path.
        if used.get(rel, a.sha256) != a.sha256:
            root, dot, e = rel.rpartition(".")
            rel = "%s-%s%s%s" % (root or rel, a.sha256[:8], dot, e)
        used[rel] = a.sha256
        a.relpath = rel
    return assets


def write_assets(assets, out_dir):
    for a in assets:
        dest = os.path.join(out_dir, a.relpath)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(a.data)


def build_metadata(assets, dir_name):
    items = []
    for a in assets:
        items.append({
            "path": a.relpath,
            "kind": a.kind,
            "media_type": a.media_type,
            "bytes": len(a.data),
            "sha256": a.sha256,
            "origin": a.origin,
            "source_ref": a.source_ref,
        })
    return {
        "dir": dir_name if items else None,
        "count": len(items),
        "items": items,
    }


def write_manifest(obj, out_dir):
    dest = os.path.join(out_dir, "_manifest.json")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, indent=2))
        fh.write("\n")


def emit_inventory(assets):
    if not assets:
        sys.stdout.write("assets: none\n")
        return
    n_in = sum(1 for a in assets if a.kind == "input")
    n_out = len(assets) - n_in
    sys.stdout.write("assets: %d (%d input / %d output)\n" % (len(assets), n_in, n_out))
    for a in assets:
        sys.stdout.write("  - [%s] %s  %s  %d bytes  %s\n" % (
            a.kind, a.media_type or "?", a.origin, len(a.data), a.relpath))


def main() -> int:
    out_dir = None
    dir_name = None
    originals = []
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

    assets, human_paths = collect(transcript)
    resolve_origins(assets, human_paths, originals)

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
        sys.stdout.write(
            json.dumps(build_metadata(assets, dir_name), ensure_ascii=False, indent=2)
        )
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
