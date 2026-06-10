#!/usr/bin/env python3
"""rag-eval-verify.py — independent QA sweep for the Phase-1 RAG eval set.

Given the JSON the collection workflow returns (a {"repos":[{name,root,kept:[...]}]}
structure), this re-checks every question deterministically, with NO LLM:

  1. Each `primary` path exists under the repo root.
  2. Each `sentinel` is a literal substring of at least one of its `primary` files
     (the harness's build-time validation rule: a sentinel must occur in its doc).
  3. The `question` does NOT contain any sentinel verbatim (case-insensitive) —
     the non-circularity / non-echo firewall.
  4. (advisory) token-trigram Jaccard(question, primary) stays under 0.30, mirroring
     gold.py's LEXICAL_OVERLAP_MAX echo guard.

Usage:
  python3 rag-eval-verify.py eval.json [--strict]

Exit code is non-zero if any hard check (1-3) fails. Check 4 is advisory only.
"""
from __future__ import annotations
import argparse, json, os, re, sys
from pathlib import Path

LEXICAL_OVERLAP_MAX = 0.30
_word = re.compile(r"[A-Za-z0-9_]+")


def resolve_root(root: str) -> Path:
    """Portable repo root. The eval set pins the authoring machine's macOS paths
    (/Users/shuyang/developer/<tail>). Use the literal path when it exists (on that
    Mac), otherwise remap the post-`developer/` tail onto THIS machine's developer
    tree ($RAG_DEV_ROOT or $HOME/developer) — e.g. /home/ssun/developer/<tail> on the
    Ubuntu GPU box. This verifies the same pinned gold file on either host WITHOUT
    editing the gold data."""
    p = Path(root).expanduser()
    if p.is_dir():
        return p
    parts = Path(root).parts
    if "developer" in parts:
        tail = Path(*parts[parts.index("developer") + 1:])
        base = Path(os.environ.get("RAG_DEV_ROOT", str(Path.home() / "developer")))
        cand = base.joinpath(tail)
        if cand.is_dir():
            return cand
    return p


def trigram_jaccard(a: str, b: str) -> float:
    def grams(s: str):
        toks = _word.findall(s.lower())
        return {tuple(toks[i:i + 3]) for i in range(len(toks) - 2)} if len(toks) >= 3 else set(toks)
    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("json")
    ap.add_argument("--strict", action="store_true", help="treat advisory echo overlap as failure")
    args = ap.parse_args()

    data = json.loads(Path(args.json).read_text())
    repos = data["repos"] if isinstance(data, dict) else data
    cache: dict[str, str] = {}
    hard_fail = 0
    advisory = 0
    total = 0

    for repo in repos:
        root = resolve_root(repo["root"])
        rname = repo.get("name", str(root))
        kept = repo.get("kept") or repo.get("questions") or []
        print(f"\n=== {rname}  ({len(kept)} questions) ===")
        for q in kept:
            total += 1
            qid = q.get("id", "?")
            problems = []
            texts = []
            for rel in q.get("primary", []):
                fp = root / rel
                if not fp.is_file():
                    problems.append(f"MISSING primary file: {rel}")
                    continue
                if str(fp) not in cache:
                    try:
                        cache[str(fp)] = fp.read_text(encoding="utf-8", errors="replace")
                    except OSError as e:
                        problems.append(f"unreadable {rel}: {e}")
                        cache[str(fp)] = ""
                texts.append(cache[str(fp)])
            joined = "\n".join(texts)
            for s in q.get("sentinels", []):
                if s not in joined:
                    problems.append(f"SENTINEL not in any primary: {s!r}")
            ql = q.get("question", "").lower()
            for s in q.get("sentinels", []):
                if s.lower() in ql:
                    problems.append(f"ECHO: question contains sentinel {s!r}")
            jac = trigram_jaccard(q.get("question", ""), joined)
            echo_advisory = jac > LEXICAL_OVERLAP_MAX

            if problems:
                hard_fail += 1
                print(f"  [FAIL] {qid}")
                for p in problems:
                    print(f"         - {p}")
            elif echo_advisory and args.strict:
                hard_fail += 1
                print(f"  [FAIL] {qid}  (strict echo Jaccard={jac:.2f} > {LEXICAL_OVERLAP_MAX})")
            elif echo_advisory:
                advisory += 1
                print(f"  [warn] {qid}  high lexical overlap Jaccard={jac:.2f} (advisory)")
            else:
                print(f"  [ok]   {qid}  ({q.get('domain')}/{q.get('difficulty')})")

    print(f"\n---- summary ----")
    print(f"total={total}  hard_fail={hard_fail}  advisory_echo={advisory}")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
