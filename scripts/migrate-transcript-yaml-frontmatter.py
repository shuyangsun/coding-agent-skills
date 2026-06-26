#!/usr/bin/env python3
"""Migrate transcript metadata blocks to YAML front matter.

This is a one-time repository maintenance script. It targets dated transcript
files under docs/transcripts/YYYY-MM-DD/*.md, leaves OVERVIEW.md alone, and is
idempotent for files that already start with YAML front matter.
"""

from __future__ import annotations

import argparse
import re
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path


REQUIRED_KEYS = ("date", "repo", "author", "agent", "summary")
DEFAULT_MARKDOWNLINT = "<!-- markdownlint-disable MD013 MD024 -->"
DATED_TRANSCRIPT_GLOB = "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]/*.md"

META_PATTERNS = (
    re.compile(
        r"^(?:-\s*)?\*\*(Date|Repo|Author|Agent|Summary):\*\*\s*(.*)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:-\s*)?\*\*(Date|Repo|Author|Agent|Summary)\*\*:\s*(.*)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:-\s*)?(Date|Repo|Author|Agent|Summary):\s*(.*)$",
        re.IGNORECASE,
    ),
)
TABLE_META_PATTERN = re.compile(
    r"^\|\s*\*\*(Date|Repo|Author|Agent|Summary)\*\*\s*\|\s*(.*?)\s*\|\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedTranscript:
    title: str
    metadata: dict[str, str]
    markdownlint_comments: tuple[str, ...]
    body_lines: list[str]


class ParseError(Exception):
    """Raised when a transcript header cannot be migrated safely."""


def discover_repo_root(start: Path) -> Path:
    current = start.resolve()
    for path in (current, *current.parents):
        if (path / "docs" / "transcripts").is_dir():
            return path
    raise ParseError("could not find docs/transcripts from current directory")


def transcript_paths(repo_root: Path) -> list[Path]:
    transcript_root = repo_root / "docs" / "transcripts"
    return sorted(transcript_root.glob(DATED_TRANSCRIPT_GLOB))


def has_yaml_frontmatter(lines: list[str]) -> bool:
    return bool(lines) and lines[0].strip() == "---"


def strip_outer_markdown(value: str) -> str:
    value = value.strip()
    value = re.sub(r"\s*\|\s*$", "", value).strip()
    return value


def parse_metadata_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    for pattern in META_PATTERNS:
        match = pattern.match(stripped)
        if match:
            return match.group(1).lower(), strip_outer_markdown(match.group(2))
    match = TABLE_META_PATTERN.match(stripped)
    if match:
        return match.group(1).lower(), strip_outer_markdown(match.group(2))
    return None


def skip_blank_lines(lines: list[str], index: int) -> int:
    while index < len(lines) and not lines[index].strip():
        index += 1
    return index


def split_preamble(lines: list[str]) -> tuple[tuple[str, ...], int]:
    comments: list[str] = []
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith("<!-- markdownlint-disable"):
            comments.append(stripped)
            index += 1
            continue
        break
    return tuple(comments), index


def parse_transcript(path: Path) -> ParsedTranscript:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if has_yaml_frontmatter(lines):
        raise ParseError("already has YAML front matter")

    markdownlint_comments, index = split_preamble(lines)
    index = skip_blank_lines(lines, index)
    if index >= len(lines) or not lines[index].startswith("# "):
        raise ParseError("missing top-level transcript title")
    title = lines[index][2:].strip()
    if not title:
        raise ParseError("empty top-level transcript title")

    index = skip_blank_lines(lines, index + 1)
    metadata, body_index = parse_metadata_block(lines, index)
    missing = [key for key in REQUIRED_KEYS if not metadata.get(key)]
    if missing:
        raise ParseError(f"missing metadata: {', '.join(missing)}")

    body_index = skip_metadata_separator(lines, body_index)
    body_lines = lines[body_index:]
    while body_lines and not body_lines[0].strip():
        body_lines = body_lines[1:]

    comments = markdownlint_comments or (DEFAULT_MARKDOWNLINT,)
    return ParsedTranscript(title, metadata, comments, body_lines)


def parse_metadata_block(
    lines: list[str],
    index: int,
) -> tuple[dict[str, str], int]:
    metadata: dict[str, str] = {}
    last_key: str | None = None
    saw_metadata = False

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            index += 1
            if saw_metadata:
                break
            continue

        if stripped in {"| | |", "|---|---|", "| --- | --- |"}:
            index += 1
            continue

        parsed = parse_metadata_line(line)
        if parsed:
            key, value = parsed
            metadata[key] = value
            last_key = key
            saw_metadata = True
            index += 1
            continue

        if last_key == "summary" and (line.startswith(" ") or line.startswith("\t")):
            metadata["summary"] = " ".join(
                part
                for part in (
                    metadata["summary"].strip(),
                    strip_outer_markdown(stripped),
                )
                if part
            )
            index += 1
            continue

        if saw_metadata:
            break
        raise ParseError("missing transcript metadata block")

    return metadata, index


def skip_metadata_separator(lines: list[str], index: int) -> int:
    index = skip_blank_lines(lines, index)
    if index < len(lines) and lines[index].strip() == "---":
        index += 1
    return skip_blank_lines(lines, index)


def yaml_double_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def folded_scalar(value: str) -> list[str]:
    normalized = " ".join(value.split())
    if not normalized:
        return ["summary: ''"]

    lines = ["summary: >-"]
    for wrapped in textwrap.wrap(
        normalized,
        width=88,
        break_long_words=False,
        break_on_hyphens=False,
    ):
        lines.append(f"  {wrapped}")
    return lines


def render_frontmatter(parsed: ParsedTranscript) -> list[str]:
    return [
        "---",
        f"title: {yaml_double_quote(parsed.title)}",
        f"date: {parsed.metadata['date']}",
        f"repo: {yaml_double_quote(parsed.metadata['repo'])}",
        f"author: {yaml_double_quote(parsed.metadata['author'])}",
        f"agent: {yaml_double_quote(parsed.metadata['agent'])}",
        *folded_scalar(parsed.metadata["summary"]),
        "---",
    ]


def migrate_text(path: Path) -> str | None:
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines()
    if has_yaml_frontmatter(lines):
        return None

    parsed = parse_transcript(path)
    output_lines = [
        *render_frontmatter(parsed),
        "",
        *parsed.markdownlint_comments,
        "",
        f"# {parsed.title}",
    ]
    if parsed.body_lines:
        output_lines.extend(("", *parsed.body_lines))
    return "\n".join(output_lines) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate docs/transcripts metadata to YAML front matter.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root. Defaults to searching upward for docs/transcripts.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Parse every transcript and report what would change without writing.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the files that would change without writing.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    repo_root = (
        args.repo_root.resolve() if args.repo_root else discover_repo_root(Path.cwd())
    )

    changed: list[Path] = []
    skipped: list[Path] = []
    failures: list[tuple[Path, str]] = []

    for path in transcript_paths(repo_root):
        try:
            migrated = migrate_text(path)
        except ParseError as error:
            if str(error) == "already has YAML front matter":
                skipped.append(path)
            else:
                failures.append((path, str(error)))
            continue

        if migrated is None:
            skipped.append(path)
            continue

        changed.append(path)
        if not args.check and not args.dry_run:
            path.write_text(migrated, encoding="utf-8")

    for path, reason in failures:
        print(f"FAIL {path.relative_to(repo_root)}: {reason}", file=sys.stderr)

    action = "would migrate" if args.check or args.dry_run else "migrated"
    print(f"{action}: {len(changed)}")
    print(f"already YAML: {len(skipped)}")
    print(f"failures: {len(failures)}")
    if args.dry_run or args.check:
        for path in changed:
            print(path.relative_to(repo_root))

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
