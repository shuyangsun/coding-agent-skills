---
title: Export Session Assets in export-raw-transcript
date: 2026-06-28
repo: "coding-agent-skills (jj workspace `claude-export-assets`)"
author: "Shuyang Sun <shuyangsun10@gmail.com>"
agent: "Claude Code (Opus 4.8, 1M context, reasoning: max)"
summary: >-
  Added asset export to the export-raw-transcript skill: a new
  extract-claude-assets.py pulls images/files attached in a session into a
  colocated <prefix>-assets/ directory with provenance-preserving, hash-verified
  paths and a manifest, kept decoupled from the metadata sidecar and documented
  in a split-out ASSETS.md.
---

<!-- markdownlint-disable MD013 MD024 -->

# Export Session Assets in export-raw-transcript

## User

> _[Attached: a screenshot of a "Gem Share" web app — the "Bookmarks" page listing saved gems.]_

The metadata of the last transcript exported with the /export-raw-transcript is at ~/nas/database/llm_transcripts/raw/20260627/20260627T230654Z-bookmark-access-control-metadata.json. It contains a screenshot image `Screenshot 2026-06-27 at 4.09.07 PM.png`. The original is at path ~/Desktop/Screenshot 2026-06-27 at 4.09.07 PM.png.

The current /export-raw-transcript skill does not save assets from the input. Modify the skill so that if files or images are part of the session, they are exported a directory colocated with metadata and transcript files. The directory name should be `<timestamp>-<short-slug>-assets`. Since there could be multiple files with the same name, and we would like to be able to find the precise reference to the file, you may need to reconstruct the absolute path of the asset in the directory without modifying exported transcript. Use your best judgement on how to handle this.

I am giving you the image again, so you can test by exporting this session's transcript. Once you are done, export the screenshot to  ~/nas/database/llm_transcripts/raw/20260627/ for the previous transcript `20260627T230654Z-bookmark-access-control`.

Keep the main skill markdown small, split this asset export part into a separate markdown file. Reference it only when asset export is needed. You may want to write script to detect whether an asset was part of the input or output, and put it in the skill. Use your best judgement here.

Focus on Claude first, since you can test with this session. I will work on GPT Codex later.

Once the skill is working properly,

## Assistant

I started by reading the existing skill end-to-end — `SKILL.md`, `export-raw-transcript.sh`, `parse-claude-transcript.sh`, `metadata.schema.json`, and `validate-metadata.py` — and the previous session's metadata sidecar. Then I probed *how Claude stores assets*, being careful never to pull transcript bytes (the base64 image) into context. I ran `--detect` to locate the live transcript, then ran throwaway probe scripts that print only structure (record types, block types, sizes, key names — never base64 or full text).

Findings that shaped the whole design:

- **The image is an embedded base64 blob.** It lives at `message.content[0]` of a `type:user` record as `{ "type": "image", "source": { "data": …, "media_type": "image/png", "type": "base64" } }` — ~286 KB of base64, and the block carries **no filename and no path**, only `type` + `source`.
- **`attachment`-type records are NOT file attachments.** They're hook outputs and deferred-tool deltas. They must be ignored.
- **Path-grepping free text is unreliable.** The transcript is self-referential — it records my own tool calls — so naive path extraction picks up every path I ever grepped. Any "referenced file" detection has to be gated to genuine human turns and verified, not harvested.

Before editing, I renamed the session's auto-created jj workspace to `claude-export-assets` to keep the work isolated.

I then wrote **`extract-claude-assets.py`** — the core deliverable. It streams the transcript in a subprocess (bytes never reach the model), finds every base64 blob in `image`/`document` blocks, classifies each as **input vs output** by its structural position, de-dupes by sha256, and writes each blob out. Classification rule: a blob in a genuine human user turn (`type:user`, `role:user`, not a tool result, sub-agent, or injected meta record) is `input`; a blob inside a `tool_result`/`toolUseResult` or an `assistant` record is `output`.

For the "reconstruct the absolute path without modifying the transcript" requirement, I used a **content-hash-verified path mirror**:

- If a candidate on-disk path (from a `--asset-original` hint, or an absolute path mentioned in the same human turn's text) **exists and its sha256 equals the blob's**, the asset is stored at that absolute path mirrored under the assets dir (leading `/` dropped), e.g. `…-assets/Users/.../Desktop/Screenshot….png` → `origin: "disk"`. Different source dirs → different subtrees, so same-named files never collide and the original path reads straight off the layout.
- Otherwise the blob lives only inside the transcript, so it falls back to a precise transcript coordinate: `_embedded/<kind>/<record-uuid>-<block>.<ext>` → `origin: "transcript"`.

The hash gate is what makes mirroring safe: a wrong or stale path hint simply fails to match and falls back, so it can never produce a wrong mirror.

Testing the extractor in inventory mode revealed something subtle. The current session's asset resolved to `origin: disk` (mirrored to the Desktop path), but my shell check for that exact path reported it missing. Debugging the contradiction:

```text
python isfile: False
'/Users/.../Desktop/Screenshot 2025-07-24 at 10.37.01 PM.jpeg'
'/Users/.../Desktop/Screenshot 2026-06-27 at 4.09.07 PM.png'
```

**macOS screenshot filenames use U+202F (a NARROW NO-BREAK SPACE) before "PM", not an ASCII space.** It's visually identical and I genuinely could not tell which one I had typed (in one test I unknowingly typed both variants in the same command). The extractor was right — the live transcript's human text contained the real U+202F path, which exists and hash-matched (sha `7060eb9f…`), so it correctly mirrored. The previous session's transcript doesn't mention the path, so it correctly fell back to `_embedded/…`. Lesson baked into the skill: build such paths from disk via glob, never type them — and the hash gate turns a mistyped space into a harmless fallback.

## User

I asked two design questions before finalizing. Selections:

- **Asset record** → **Decoupled manifest**: keep `metadata.json` and its schema at v3, untouched; give the assets dir its own `_manifest.json`; discover it by the shared `<prefix>` naming convention.
- **Previous transcript metadata** → **Only add the assets dir**: create the `-assets/` directory for `20260627T230654Z-bookmark-access-control`, but leave its existing v3 `metadata.json` as the historical snapshot it is.

## Assistant

With those decisions, I finished the feature:

- Extended `extract-claude-assets.py` with `--manifest` (write `<dir>/_manifest.json`) and `--originals-file` (so the wrapper can forward paths containing spaces/U+202F safely). The manifest records `dir`, `count`, and per-asset `{ path, kind, media_type, bytes, sha256, origin, source_ref }`, where `source_ref` pins the exact transcript record + block.
- Wired extraction into `export-raw-transcript.sh`: it auto-runs after metadata (non-fatal — the transcript + sidecar are already written, but the extractor's warnings reach stderr), previews an asset count in `--detect`, and accepts a repeatable `--asset-original` flag.
- Split all the asset detail into a new **`ASSETS.md`** (detection, input/output, path layout, `--asset-original`, the U+202F note, and how to re-export from an archived transcript) and kept `SKILL.md` lean — just a short pointer to it.

I verified the whole thing:

- **Full export to a temp root** — produced the transcript, the sidecar (still schema-valid v3), and the assets dir with the screenshot mirrored to its Desktop path plus `_manifest.json`. The extracted PNG was byte-identical to the original (sha `7060eb9f…`).
- **Edge cases** — a text-only transcript creates no assets dir; a wrong (ASCII-space) `--original` correctly falls back to `transcript` origin while the real (U+202F) path mirrors as `disk`.

Then the two deliverables, both byte-identical to the original (sha `7060eb9f…`, 214665 bytes):

1. **This session** → `~/Downloads/transcripts/20260627/…-export-raw-asset-export-assets/` — auto-detected the Desktop path from the human turn, no flag needed.
2. **Previous transcript** → `~/nas/database/llm_transcripts/raw/20260627/20260627T230654Z-bookmark-access-control-assets/` — screenshot mirrored to its Desktop path via a glob-resolved `--original`; its `metadata.json` left untouched.

I also recorded the design and the U+202F gotcha in memory.

## User

_[Next step — selection]_ **Commit the changes.** (My final instruction had been truncated after "Once the skill is working properly,"; I confirmed the next step rather than guess.)

## Assistant

Committed the four files on the `claude-export-assets` workspace as `feat(export-raw-transcript): export attached assets to a colocated dir`, with `Author:` and `Co-Authored-By:` trailers. The two asset directories live outside the repo (in `~/Downloads` and the nas archive, like the transcripts they accompany), so only the skill changes are in the commit.

## User

Export session transcript (not raw), then commit and push again.

## Assistant

Exported this curated transcript to `docs/transcripts/2026-06-28/0082-claude-export-raw-transcript-assets.md` (reconstructed from context so the base64 image never entered the model; home paths abstracted to `~`), ran the redaction scan, committed it as its own `docs(transcripts): …` change stacked on the feature commit, and pushed the `claude-export-assets` branch to `origin`.
