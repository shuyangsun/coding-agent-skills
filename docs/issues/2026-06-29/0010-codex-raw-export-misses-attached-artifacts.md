# Codex raw transcript export misses attached artifacts from Codex Desktop

- **Status:** Fixed (implemented 2026-06-29) — Codex and Claude raw exports now
  write sibling asset directories when the transcript exposes attached or
  referenced local files.
- **Area:** `export-raw-transcript` skill and Codex raw-session archival; artifact
  export parity with Claude Code.
- **Severity:** Medium — the raw transcript backup succeeds, but the archive is
  incomplete when a user attaches a file in the IDE. Replaying or auditing the
  session later loses the exact artifact bytes that influenced the work.
- **Environment:** Codex Desktop IDE on macOS, active agent detected by
  `export-raw-transcript.sh --detect` as `codex-cli` version `0.142.3`, entrypoint
  `Codex Desktop`, model `gpt-5.5`, effort `xhigh`.
- **Observed:** 2026-06-29 during a Codex Desktop session in
  `/Users/shuyang/developer/utility`.
- **Example artifact:** `/Users/shuyang/Desktop/secure_fill.sh`, shown to the
  agent as a user-attached or referenced file while building the Swift/Metal
  `secure_fill` utility.
- **Related code:** `.agents/skills/export-raw-transcript/export-raw-transcript.sh`,
  `.agents/skills/export-raw-transcript/parse-codex-transcript.sh`, and the
  Claude raw asset export behavior represented by
  `/Users/shuyang/nas/database/llm_transcripts/raw/20260627/20260627T234900Z-export-raw-asset-export-assets/`.

## Summary

`export-raw-transcript` currently backs up the Codex Desktop raw JSONL session and
metadata sidecar, but it does not export file artifacts attached through the
Codex Desktop IDE. In the observed session, the user supplied
`/Users/shuyang/Desktop/secure_fill.sh`; the raw transcript export produced the
`.jsonl` and `-metadata.json` files, but there was no companion asset directory
containing a copy or manifest entry for `secure_fill.sh`.

This is specifically a Codex Desktop + `codex-cli` artifact export gap. Claude
raw transcript archives already have an asset-export pattern that creates a
separate `*-assets/` directory beside the raw transcript and metadata; Codex raw
exports should preserve user-attached files with the same kind of sidecar asset
directory.

## Expected

When a Codex Desktop session contains an attached or referenced local file, raw
export should create a sibling assets directory alongside the raw transcript and
metadata, for example:

```text
<utc-ts>-<short-name>.jsonl
<utc-ts>-<short-name>-metadata.json
<utc-ts>-<short-name>-assets/
```

The assets directory should preserve each attached file byte-for-byte, with a
manifest that records at least the original path, copied filename, byte count,
SHA-256 digest, transcript reference if available, and whether the source was a
true IDE attachment or a path merely mentioned by the user.

## Actual

The Codex export created only the raw transcript and metadata sidecar. The
`secure_fill.sh` file attached or referenced from Codex Desktop was not copied
into the export destination, so the raw backup is not self-contained.

## Reproduction

1. Start a Codex Desktop session using the Codex agent.
2. Attach or reference a local file in the IDE, such as
   `/Users/shuyang/Desktop/secure_fill.sh`.
3. Run the raw exporter from `.agents/skills/export-raw-transcript`:

   ```sh
   bash export-raw-transcript.sh --tool codex --title "..." --summary "..." codex-artifact-test
   ```

4. Inspect the export destination by filename only; do not read the raw
   transcript into agent context.
5. Observe that the export contains `<prefix>.jsonl` and
   `<prefix>-metadata.json`, but no `<prefix>-assets/` directory containing the
   attached `.sh` artifact.

## Why this matters

The raw export is meant to be a faithful backup of the session. For sessions that
depend on attached files, the transcript alone is insufficient: it may name the
artifact or show that an attachment existed, but it does not preserve the file
bytes needed to reproduce the agent's input context. This is especially important
for scripts, screenshots, documents, and generated assets that live outside the
repository and may be edited or deleted after the session.

## Candidate fix

Add Codex artifact discovery and copy support to `export-raw-transcript.sh`,
mirroring the Claude asset export layout:

1. Detect file attachments or local artifact references in Codex raw transcript
   records without loading the full transcript into model context.
2. Copy each source file byte-for-byte into `<prefix>-assets/`, using collision
   safe filenames.
3. Write an asset manifest inside the asset directory with source path, copied
   path, size, SHA-256, mtime, and transcript record identifiers when available.
4. Include the asset directory path and manifest path in metadata, or add a
   clearly versioned metadata extension for raw transcript assets.
5. Keep the existing no-redaction caveat: raw assets are unredacted and should
   remain outside the repo unless explicitly scrubbed.

## Resolution

Implemented in `export-raw-transcript`:

- Restored the Claude Code asset-export path with `extract-claude-assets.py` and
  `ASSETS.md`, preserving embedded image/document blobs into
  `<prefix>-assets/_manifest.json`.
- Added `extract-codex-assets.py` for Codex Desktop sessions. It copies existing
  local files from structured Codex attachment fields, explicit
  `--asset-original` hints, and absolute file paths mentioned in human input,
  while skipping ordinary path mentions under the session cwd/workspace roots.
- Wired `export-raw-transcript.sh --detect` and export mode to preview and write
  assets for both `--tool claude` and `--tool codex`.
- Documented Codex provenance via `source_kind` (`attachment`, `path_mention`, or
  `original_hint`) plus `original_path`, `source_refs`, byte count, mtime, and
  SHA-256 in the asset manifest.

## Notes

The observed session also used `export-raw-transcript.sh --detect`, which
identified the tool as `codex-cli` and the IDE entrypoint as `Codex Desktop`.
That distinction matters: this is not a Claude Code issue, and it is not a
generic shell transcript issue. It is a gap in preserving Codex Desktop session
attachments during Codex raw transcript export.
