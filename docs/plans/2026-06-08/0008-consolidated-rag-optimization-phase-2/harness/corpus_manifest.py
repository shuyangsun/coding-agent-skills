#!/usr/bin/env python3
"""corpus_manifest.py — per-repo corpus definitions for the Phase-3 RAG benchmark.

Pre-work for ``0008-consolidated-rag-optimization-phase-2.md`` (§"Index per repo
and per corpus kind", §"Index Payload and Storage Changes"). For each of the six
eval repos it pins: the corpus root, a comprehensive language-aware file-type set,
the build/dependency dirs to skip, and the *hard* self-reference exclusions — so
every gold ``primary`` in ``eval-set.json`` is reachable and the eval files
themselves never enter the corpus they measure.

WHY a comprehensive extension set (the headline pre-work finding): the shipped
``setting-up-rag`` ``CODE_EXTS`` is JS/TS/Python-centric and omits C++/CUDA/CMake.
68 of the 207-set's distinct ``primary`` files — every Alpha-Zero engine file
(``.cc`` ×32, ``.h`` ×25, ``.cuh`` ×2, ``CMakeLists.txt`` ×5, ``.yml`` ×3, ``.sh``)
— would silently fail to load, leaving the code domain EMPTY for four of six
repos. This manifest fixes that for the harness without touching the shipped
skill (keep/revert discipline: a payload/extension change is promoted into
``setting-up-rag`` only if a benchmark proves it).

Stdlib-only so the readiness validator runs without the FastEmbed/Qdrant venv.

This file lives under the consolidated-plan subdir, which is itself hard-excluded
from the ``coding-agent-skills`` corpus — so the harness can never contaminate the
corpus it measures.
"""
from __future__ import annotations

import fnmatch
import functools
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# --- language-aware file typing --------------------------------------------
# Extension -> language tag (the `lang` payload field). Markdown is typed `md`
# but kept separate from `kind` (a code-domain question may cite a .md file).
LANG_BY_EXT: dict[str, str] = {
    ".ts": "typescript", ".tsx": "typescript", ".mts": "typescript", ".cts": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".py": "python",
    ".go": "go", ".rs": "rust", ".java": "java", ".rb": "ruby",
    ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".c": "c",
    ".h": "cpp", ".hpp": "cpp", ".hh": "cpp", ".hxx": "cpp",
    ".cu": "cuda", ".cuh": "cuda",
    ".css": "css", ".scss": "css", ".less": "css",
    ".html": "html",
    ".json": "json", ".jsonc": "json",
    ".yml": "yaml", ".yaml": "yaml", ".toml": "toml",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".cmake": "cmake",
    ".md": "markdown", ".mdx": "markdown",
    ".wgsl": "wgsl", ".glsl": "glsl",
}
# Extensionless / fixed-name build files that are code by filename, not extension.
CODE_FILENAMES: frozenset[str] = frozenset({"CMakeLists.txt", "Makefile", "Dockerfile"})

# `code` corpus membership = any LANG_BY_EXT ext except markdown, or a CODE_FILENAME.
_CODE_EXTS: frozenset[str] = frozenset(e for e, l in LANG_BY_EXT.items() if l != "markdown")
_MD_EXTS: frozenset[str] = frozenset(e for e, l in LANG_BY_EXT.items() if l == "markdown")

# Dirs never indexed: VCS, dependency, and build output. A nested .git/.jj marks a
# nested workspace/worktree and is pruned regardless of name (see iter_repo_files).
# This is a coarse fast-path; the AUTHORITATIVE generated-file filter is the
# .gitignore-respecting git-tracked allowlist below (tracked_files / iter_repo_files),
# which is why ad-hoc names like `artifacts/` are deliberately NOT enumerated here.
SKIP_DIRS: frozenset[str] = frozenset({
    ".git", ".jj", "node_modules", "dist", "build", ".output", ".vite", ".nitro",
    ".turbo", "coverage", ".cache", "__pycache__", ".venv", "venv", "out", "target",
    "cmake-build-debug", "cmake-build-release", ".next", "vendor", "third_party",
    "external", ".idea", ".vscode", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "wasm-build", "emsdk",
})
SKIP_FILES: frozenset[str] = frozenset({
    "bun.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "Cargo.lock",
})
VCS_MARKERS = (".git", ".jj")


def kind_of(relpath: str) -> str | None:
    """`md`, `code`, or None (not indexable)."""
    name = os.path.basename(relpath)
    ext = os.path.splitext(name)[1].lower()
    if ext in _MD_EXTS:
        return "md"
    if ext in _CODE_EXTS or name in CODE_FILENAMES:
        return "code"
    return None


def lang_of(relpath: str) -> str:
    name = os.path.basename(relpath)
    ext = os.path.splitext(name)[1].lower()
    if name in CODE_FILENAMES:
        return "cmake" if name == "CMakeLists.txt" else name.lower()
    return LANG_BY_EXT.get(ext, "text")


@dataclass(frozen=True)
class Repo:
    """One eval repo as a corpus.

    code_corpus_desc/nl_corpus_desc are the prose scope from eval-set.json, kept
    for provenance. The loader indexes the whole root (minus skips/exclusions) and
    tags each chunk with `kind`/`lang`, because the gold `primary` files are
    scattered well beyond those described sub-trees (e.g. config files at the root,
    benchmark reports under docs/). Domain separation is applied at SCORE time as a
    soft `kind` slice with a primary backstop, not by dropping files at index time.
    """

    name: str
    root: str
    code_corpus_desc: str = ""
    nl_corpus_desc: str = ""
    # repo-root-relative fnmatch globs ('*' spans '/'); HARD-excluded from BOTH kinds.
    # Reserved for files that are never a legitimate primary for ANY query and would
    # leak gold answers (the eval set + the consolidated plan + this harness subdir).
    exclude_globs: tuple[str, ...] = ()


# Repo roots resolve under the developer tree of whatever machine runs the harness.
# The eval set was authored on macOS (/Users/shuyang/developer/…); this Ubuntu GPU
# box ("delos") has the same layout under /home/ssun/developer/…. Both are exactly
# `Path.home()/"developer"/<tail>`, so derive the base from $HOME (override with
# $RAG_DEV_ROOT) instead of pinning a macOS path that does not exist here. This is a
# pure portability fix — on the Mac it resolves to the identical original paths.
_DEV_ROOT = Path(os.environ.get("RAG_DEV_ROOT", str(Path.home() / "developer")))


def _root(*parts: str) -> str:
    return str(_DEV_ROOT.joinpath(*parts))


# Roots come from eval-set.json; descriptions are abridged from that file.
REPOS: dict[str, Repo] = {
    "coding-agent-skills": Repo(
        name="coding-agent-skills",
        root=_root("coding-agent-skills"),
        code_corpus_desc="inception/, .agents/skills/*/scripts/, scripts/, root config",
        nl_corpus_desc="docs/transcripts/, docs/{benchmarks,issues,plans,prompts,research}, .agents/skills/**/*.md",
        exclude_globs=(
            # the 207-query gold set quotes every answer/sentinel — never index it
            "docs/plans/2026-06-08/0003-rag-eval-set-phase-1.md",
            "docs/plans/2026-06-08/0003-rag-eval-set-phase-1*",
            # the consolidated plan restates benchmark decisions; the pre-work harness
            # (this dir) embeds the loader/configs — exclude the whole subtree
            "docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2.md",
            "docs/plans/2026-06-08/0008-consolidated-rag-optimization-phase-2*",
        ),
    ),
    "alpha-zero": Repo(
        name="alpha-zero",
        root=_root("alpha-zero", "alpha-zero"),
        code_corpus_desc="src/ include/ (MCTS/inference/training), gui/, tests/",
        nl_corpus_desc="docs/ (transformer/inference/perf design docs)",
    ),
    "alpha-zero-api": Repo(
        name="alpha-zero-api",
        root=_root("alpha-zero", "alpha-zero-api"),
        code_corpus_desc="src/ include/, test/",
        nl_corpus_desc="doc/report.md, doc/migration-guides/",
    ),
    "az-game-tic-tac-toe": Repo(
        name="az-game-tic-tac-toe",
        root=_root("alpha-zero", "az-game-tic-tac-toe"),
        code_corpus_desc="src/ include/ tests/",
        nl_corpus_desc="memory/ (constitution, rules, mcts/augmentation/history)",
    ),
    "az-game-xiang-qi": Repo(
        name="az-game-xiang-qi",
        root=_root("alpha-zero", "az-game-xiang-qi"),
        code_corpus_desc="src/ include/ tests/, gui/",
        nl_corpus_desc="memory/ (game_design/rules + details/, gui_design, …)",
    ),
    "website": Repo(
        name="website",
        root=_root("website"),
        code_corpus_desc="shuyang-website/src/ + config, tools/, scripts/",
        nl_corpus_desc="llm-sessions-history/, prompts/, docs/{design,plan,research}",
    ),
}


def is_excluded(repo: Repo, relpath: str) -> bool:
    return any(fnmatch.fnmatch(relpath, g) for g in repo.exclude_globs)


def _is_vcs_root(path: Path) -> bool:
    return any((path / m).exists() for m in VCS_MARKERS)


@functools.lru_cache(maxsize=None)
def tracked_files(root: str) -> frozenset[str] | None:
    """The repo's git-tracked files (repo-root-relative POSIX paths), or None when
    `root` is not a git work tree.

    This is how the corpus RESPECTS .gitignore: generated / ignored output is never
    tracked, so an allowlist of tracked files excludes it without enumerating dir
    names. The audit that motivated this: alpha-zero's `artifacts/` (git-ignored)
    held 1.47 M words — 84% of that repo's text, ~15 k of ~17.6 k chunks — of
    machine-generated self-play traces (`selfplay_traces/trace_*.json`, 50-84 k words
    each). They are never a gold primary (0 of 207) and are pure retrieval noise that
    also made CPU indexing intractable. `git ls-files` drops them for free, and all
    207 gold primaries are tracked (verified), so nothing pinned is lost. The shipped
    `setting-up-rag` loader has the same gap and should gain the same filter — a
    promotion candidate (CPU-clean, license-neutral); see the Wave-0 report.

    Best-effort: returns None on any git failure so callers fall back to a plain walk."""
    try:
        out = subprocess.run(
            ["git", "-C", root, "ls-files", "-z", "--cached"],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return frozenset(p for p in out.stdout.split("\0") if p)


def iter_repo_files(repo: Repo, kinds: tuple[str, ...] = ("md", "code")):
    """Yield (relpath, kind, lang) for indexable files under repo.root.

    Prunes SKIP_DIRS, lockfiles, hard exclusions, and nested VCS workspaces/
    worktrees strictly below the root (the root itself may be a workspace). Mirrors
    the shipped loader's VCS-boundary rule so per-agent workspaces are never indexed.
    """
    base = Path(repo.root).expanduser().resolve()
    if not base.is_dir():
        return
    tracked = tracked_files(str(base))  # .gitignore-respecting allowlist (None => walk-only)
    for dirpath, dirnames, filenames in os.walk(base):
        current = Path(dirpath)
        if current != base and _is_vcs_root(current):
            dirnames[:] = []
            continue
        kept = []
        for d in sorted(dirnames):
            child = current / d
            if d in SKIP_DIRS or _is_vcs_root(child):
                continue
            kept.append(d)
        dirnames[:] = kept
        for fn in sorted(filenames):
            if fn in SKIP_FILES:
                continue
            rel = (current / fn).relative_to(base).as_posix()
            if tracked is not None and rel not in tracked:
                continue  # git-ignored / untracked generated output — never indexed
            k = kind_of(rel)
            if k is None or k not in kinds:
                continue
            if is_excluded(repo, rel):
                continue
            yield rel, k, lang_of(rel)


def load_repo_corpus(
    repo: Repo,
    kinds: tuple[str, ...] = ("md", "code"),
    guarantee: tuple[str, ...] = (),
) -> dict[str, dict]:
    """Map relpath -> {text, kind, lang} for the requested kinds.

    `guarantee` is the primary-backstop: relpaths (a question's `primary` files)
    that MUST be present even if their kind is not in `kinds` (e.g. an nl-domain
    question whose evidence lives in a .cc file). Backstopped files keep their TRUE
    kind/lang tag; they are merely force-included. They are never the hard-excluded
    eval files (verified: no primary points at an exclusion target).
    """
    base = Path(repo.root).expanduser().resolve()
    out: dict[str, dict] = {}
    for rel, k, lang in iter_repo_files(repo, kinds):
        out[rel] = _read(base, rel, k, lang)
    for rel in guarantee:
        if rel in out:
            continue
        if is_excluded(repo, rel):  # defensive: should never happen
            continue
        fp = base / rel
        if fp.is_file():
            out[rel] = _read(base, rel, kind_of(rel) or "code", lang_of(rel))
    return {k: v for k, v in out.items() if v is not None}


def _read(base: Path, rel: str, kind: str, lang: str) -> dict | None:
    try:
        text = (base / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return {"text": text, "kind": kind, "lang": lang}


if __name__ == "__main__":  # quick manifest self-report
    import sys

    only = sys.argv[1] if len(sys.argv) > 1 else None
    for name, repo in REPOS.items():
        if only and name != only:
            continue
        counts = {"md": 0, "code": 0}
        for _rel, k, _lang in iter_repo_files(repo):
            counts[k] += 1
        present = "ok" if Path(repo.root).is_dir() else "MISSING-ROOT"
        print(f"{name:22s} root={present:12s} md={counts['md']:5d} code={counts['code']:5d}")
