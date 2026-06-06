#!/usr/bin/env bash
#
# Wire up automatic Markdown formatting for whichever VCS this clone uses.
#
#   • Git      → lefthook installs a pre-commit hook (see lefthook.yml) that runs
#                Prettier on staged *.md files and re-stages the result.
#   • Jujutsu  → jj has no commit hooks (commits are implicit and must stay
#                fast), so we configure `jj fix` to run Prettier on Markdown.
#                Format changed files at will with `jj fix` (or `jj fix -s @`).
#
# Safe to run repeatedly. Each VCS is configured only if it's present and this
# directory is actually a repo of that kind, so the script is a no-op for tools
# you don't use.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
cd "$repo_root"

configured=0

# --- Git -------------------------------------------------------------------
if git rev-parse --git-dir >/dev/null 2>&1; then
  if command -v bunx >/dev/null 2>&1; then
    bunx lefthook install >/dev/null
    echo "✔ Git: lefthook pre-commit hook installed (formats staged Markdown)."
    configured=1
  else
    echo "⚠ Git repo detected but 'bunx' not found — run 'bun install' first." >&2
  fi
fi

# --- Jujutsu ---------------------------------------------------------------
if command -v jj >/dev/null 2>&1 && jj root >/dev/null 2>&1; then
  jj config set --repo fix.tools.prettier-markdown.command \
    '["bunx", "prettier", "--stdin-filepath=$path"]'
  jj config set --repo fix.tools.prettier-markdown.patterns \
    '["glob:\"**/*.md\""]'
  echo "✔ Jujutsu: 'jj fix' configured to format Markdown with Prettier."
  echo "  jj has no commit hook — run 'jj fix' to format changed Markdown."
  configured=1
fi

if [ "$configured" -eq 0 ]; then
  echo "No supported VCS (Git or Jujutsu) detected in $repo_root." >&2
  exit 1
fi
