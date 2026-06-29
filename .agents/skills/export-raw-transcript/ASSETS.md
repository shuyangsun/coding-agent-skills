# Exporting Session Assets

Companion to `SKILL.md`. Read this only when a session has **attached files or
images** and you need to understand or drive how they are exported. For a plain
text-only session there is nothing here to do: the main export skips assets
automatically.

## What An Asset Is

The exporter supports two agent-specific asset sources today:

- **Claude Code embedded assets.** Claude embeds attached images and documents
  directly in the transcript as base64 inside `image` / `document` content
  blocks. `extract-claude-assets.py` decodes those blobs from the copied JSONL,
  so the original disk file does not need to exist anymore. A Claude record whose
  `type` is `attachment` is not a file attachment; those are hook outputs and
  tool deltas, and are ignored.
- **Codex Desktop local assets.** Codex usually records local-file evidence
  rather than embedding bytes. `extract-codex-assets.py` copies files that still
  exist on disk when they came from `--asset-original`, from structured Codex
  attachment containers (`images`, `local_images`, `text_elements`), or from an
  absolute file path mentioned in human input. It does not copy paths from tool
  output or assistant text. Plain path mentions under the session cwd or
  workspace roots are skipped by default so ordinary repo references do not turn
  into asset archives; explicit `--asset-original` paths are still copied.

Both extractors run in a subprocess and stream the transcript. As with the raw
transcript copy itself, **the bytes never enter the model's context**; only
counts, sizes, media types, sha256s, and paths are surfaced.

## Where Assets Go

Next to the transcript and metadata, sharing the same `<utc-ts>-<short-name>`
prefix:

```text
<dest>/<utc-ts>-<short-name>.jsonl              # raw transcript
<dest>/<utc-ts>-<short-name>-metadata.json      # sidecar
<dest>/<utc-ts>-<short-name>-assets/            # assets (only if any exist)
```

The assets directory is **decoupled** from the metadata sidecar: the sidecar is
not modified and its schema is unchanged. The directory is found by the shared
prefix, and it describes itself with `_manifest.json`. The directory is created
only when the session actually has assets.

## Input Vs Output

Each asset has a `kind`:

- `input` - the person attached or referenced it in a human turn.
- `output` - a Claude blob inside `tool_result` / `toolUseResult` or an
  assistant record. Codex output assets are not copied today because Codex output
  records have not been observed to carry durable local-file bytes or attachment
  paths.

Codex manifests also include `source_kind`:

- `attachment` - a path found in a structured Codex attachment container.
- `path_mention` - an existing absolute file path found in human input text.
- `original_hint` - an explicit `--asset-original <path>` value supplied to the
  exporter.

## Layout Inside The Assets Directory

Two attachments can share a basename, so a flat directory would collide and lose
provenance. Instead every asset is stored at a path that reconstructs its origin.
The exported transcript is never rewritten to point at the new files.

- **`origin: "disk"` - mirror of an absolute path.** Disk-backed assets are stored
  at their absolute path with the leading `/` dropped, e.g.

  ```text
  <assets>/Users/alice/Desktop/Screenshot 2026-06-27 at 4.09.07 PM.png
  ```

  Different source directories give different subtrees, so same-named files do
  not collide and the original absolute path is readable from the layout. Claude
  uses this only when the on-disk path exists and sha256-matches the embedded
  blob. Codex uses it for copied local files because those transcripts generally
  point at disk instead of embedding bytes.

- **`origin: "transcript"` - Claude embedded-only fallback.** When a Claude blob
  has no verified on-disk source, it is stored under a reserved subtree keyed by
  the transcript record id and block index:

  ```text
  <assets>/_embedded/<kind>/<record-uuid>-<block>.<ext>
  ```

Top-level names beginning with `_` (`_manifest.json`, `_embedded/`) are
skill-generated; every other top-level entry mirrors a real absolute path.

## `_manifest.json`

The machine-readable index of the directory. The common fields are stable across
extractors; Codex adds source-path provenance fields when available.

```json
{
  "dir": "<utc-ts>-<short-name>-assets",
  "count": 1,
  "items": [
    {
      "path": "Users/alice/Desktop/diagram.png",
      "kind": "input",
      "media_type": "image/png",
      "bytes": 214665,
      "sha256": "7060eb9f...",
      "origin": "disk",
      "source_ref": "<record-id>#content[0]",
      "source_kind": "path_mention",
      "original_path": "/Users/alice/Desktop/diagram.png",
      "mtime_utc": "2026-06-29T14:05:11Z"
    }
  ]
}
```

`path` is relative to the assets directory; `source_ref` pins the transcript
record and field that led to the copy; `sha256` verifies the copied bytes later.
Codex entries also include `source_refs` when multiple transcript coordinates
pointed at the same file.

## Driving It

Normally there is nothing extra to do: `export-raw-transcript.sh` extracts assets
automatically and prints the assets directory in its report.

Use `--asset-original` when you know a real path that the transcript may not make
machine-readable:

```sh
bash <skill-dir>/export-raw-transcript.sh \
  --asset-original "/Users/alice/Desktop/diagram.png" \
  <short-name>
```

Repeat `--asset-original` per file. Claude verifies each hint by hash before it
uses the path. Codex has no embedded hash to compare, so it copies the explicit
hint when the file exists.

For macOS screenshots, copy paths verbatim. Screenshot filenames may contain a
NARROW NO-BREAK SPACE (U+202F, not an ASCII space) before `AM`/`PM`; retyping the
space can make Claude hash verification fail and can make Codex fail to find the
file.

## Re-Exporting Assets From An Archived Transcript

To add an assets directory next to a transcript that was exported earlier, run
the matching extractor directly against the **archived copy**. The metadata
sidecar is left untouched.

```sh
python3 <skill-dir>/extract-claude-assets.py \
  --manifest \
  --out-dir "<dest>/<prefix>-assets" \
  --dir-name "<prefix>-assets" \
  --original "/Users/alice/Desktop/diagram.png" \
  "<dest>/<prefix>.jsonl"
```

For Codex, use `extract-codex-assets.py` with the same flags. Use
`--emit inventory` and omit `--out-dir` first for a dry preview that writes
nothing.

## Scope

Claude Code and Codex Desktop have dedicated extractors. Other agents skip asset
extraction until each gets its own `extract-<tool>-assets` companion. The
exporter's main flow degrades cleanly: no extractor for the detected tool means
no assets directory.
