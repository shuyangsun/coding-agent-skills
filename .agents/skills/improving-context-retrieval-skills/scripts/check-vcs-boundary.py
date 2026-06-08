#!/usr/bin/env python3
"""check-vcs-boundary.py — metric for nested workspace/worktree exclusion.

The harness and the setting-up-rag skill must not index files from a Jujutsu
workspace or Git worktree that appears under another corpus root. The selected
corpus root itself may be such a workspace/worktree, so this check exercises both
directions with marker-only fixtures: no jj/git command is required.

Outputs KEY=VALUE lines:
  vcs_boundary_ok=1 when every loader excludes nested VCS roots and accepts a
                    direct VCS root corpus.
  vcs_boundary_nested_docs_indexed=0 is the desired count.
  vcs_boundary_direct_root_ok=1 confirms direct VCS-root indexing still works.
"""
from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILLS_DIR = SCRIPT_DIR.parents[1]

sys.path.insert(0, str(SCRIPT_DIR))
import gold  # noqa: E402

NESTED_SENTINELS = (
    "JJ_NESTED_SENTINEL",
    "GIT_WORKTREE_NESTED_SENTINEL",
    "GIT_REPO_NESTED_SENTINEL",
)


def load_rag_lib():
    rag_lib_path = SKILLS_DIR / "setting-up-rag" / "scripts" / "rag_lib.py"
    if not rag_lib_path.is_file():
        sys.exit(
            f"check-vcs-boundary.py: missing sibling setting-up-rag at {rag_lib_path}"
        )
    spec = importlib.util.spec_from_file_location(
        "setting_up_rag_rag_lib", rag_lib_path
    )
    if spec is None or spec.loader is None:
        sys.exit(f"check-vcs-boundary.py: cannot load {rag_lib_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(root: Path) -> None:
    write(root / "root.md", "VISIBLE_ROOT_DOC\n")
    write(root / "src" / "app.ts", "export const visibleRootCode = true;\n")

    write(root / "jj-workspace" / ".jj" / "repo" / "store" / "placeholder", "")
    write(root / "jj-workspace" / "docs" / "hidden.md", "JJ_NESTED_SENTINEL\n")
    write(
        root / "jj-workspace" / "src" / "hidden.ts",
        "export const JJ_NESTED_SENTINEL = true;\n",
    )

    git_worktree = root / "git-worktree"
    git_worktree.mkdir(parents=True, exist_ok=True)
    write(git_worktree / ".git", "gitdir: /tmp/fake-git-worktree\n")
    write(git_worktree / "docs" / "hidden.md", "GIT_WORKTREE_NESTED_SENTINEL\n")
    write(
        git_worktree / "src" / "hidden.ts",
        "export const GIT_WORKTREE_NESTED_SENTINEL = true;\n",
    )

    write(root / "git-repo" / ".git" / "HEAD", "ref: refs/heads/main\n")
    write(root / "git-repo" / "docs" / "hidden.md", "GIT_REPO_NESTED_SENTINEL\n")
    write(
        root / "git-repo" / "src" / "hidden.ts",
        "export const GIT_REPO_NESTED_SENTINEL = true;\n",
    )


def nested_hits(docs: dict[str, str]) -> int:
    return sum(
        1
        for text in docs.values()
        for sentinel in NESTED_SENTINELS
        if sentinel in text
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--keep", action="store_true", help="keep the temporary fixture and print its path"
    )
    args = ap.parse_args(argv)

    rag_lib = load_rag_lib()
    tmp = Path(tempfile.mkdtemp(prefix="context-vcs-boundary-"))
    try:
        build_fixture(tmp)
        loaders = {
            "harness-md": gold.load_corpus(tmp, kind="md"),
            "harness-code": gold.load_corpus(tmp, kind="code"),
            "rag-md": rag_lib.load_corpus(str(tmp), kind="md"),
            "rag-code": rag_lib.load_corpus(str(tmp), kind="code"),
        }
        nested_indexed = sum(nested_hits(docs) for docs in loaders.values())

        direct_roots = [tmp / "jj-workspace", tmp / "git-worktree", tmp / "git-repo"]
        direct_root_ok = True
        for direct_root in direct_roots:
            direct_loaders = {
                "harness-md": gold.load_corpus(direct_root, kind="md"),
                "harness-code": gold.load_corpus(direct_root, kind="code"),
                "rag-md": rag_lib.load_corpus(str(direct_root), kind="md"),
                "rag-code": rag_lib.load_corpus(str(direct_root), kind="code"),
            }
            direct_root_ok = direct_root_ok and all(
                nested_hits(docs) > 0 for docs in direct_loaders.values()
            )
        visible_root_ok = (
            "root.md" in loaders["harness-md"]
            and "root.md" in loaders["rag-md"]
            and "src/app.ts" in loaders["harness-code"]
            and "src/app.ts" in loaders["rag-code"]
        )
        ok = int(nested_indexed == 0 and direct_root_ok and visible_root_ok)

        print(f"vcs_boundary_ok={ok}")
        print(f"vcs_boundary_nested_docs_indexed={nested_indexed}")
        print(f"vcs_boundary_direct_root_ok={int(direct_root_ok)}")
        print(f"vcs_boundary_direct_roots_checked={len(direct_roots)}")
        print(f"vcs_boundary_visible_root_ok={int(visible_root_ok)}")
        if args.keep:
            print(f"fixture={tmp}")
        return 0 if ok else 1
    finally:
        if not args.keep:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    raise SystemExit(main())
