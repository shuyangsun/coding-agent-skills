#!/usr/bin/env python3
"""validate_prework.py — one-command readiness gate for Phase-3 Wave 0.

Runs every deterministic pre-work check and prints GO / NO-GO. This is what you run
to confirm the harness is wired before the first baseline. It does NOT run baselines
or touch Qdrant — it only proves the data + loaders + controls are sound.

Checks:
  1. deps          — skill venv has fastembed + qdrant_client; rapidfuzz present;
                     external IR libs advisory.
  2. sentinels     — verify.py: every sentinel a literal substring of a primary +
                     no query echoes its sentinel (the 207-set firewall).
  3. reachability  — gold_loader: every primary loader-reachable + sentinel-bearing
                     (the check that caught the C++/CUDA extension gap).
  4. chunk-integrity — enriched_index: raw_text byte-verbatim + every sentinel fits
                     within one chunk, per repo.
  5. exclusions    — eval set + consolidated plan absent from every corpus, AND in
                     gold.py EXCLUDE_GLOBS (Phase-0 harness protected too).
  6. configs       — the Wave-0 arm configs exist and load.

Stdlib-only (probes the venv via subprocess for check 1).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpus_manifest as M  # noqa: E402
import gold_loader as G  # noqa: E402
import enriched_index as E  # noqa: E402

HARNESS = Path(__file__).resolve().parent
PLAN_DIR = HARNESS.parent
DATE_DIR = PLAN_DIR.parent
VERIFY = DATE_DIR / "0003-rag-eval-set-phase-1" / "verify.py"
EVAL_SET = DATE_DIR / "0003-rag-eval-set-phase-1" / "eval-set.json"
VENV_PY = Path.home() / ".cache/rag-skill/venv/bin/python"

EXCLUDE_TOKENS = ("0003-rag-eval-set-phase-1", "0008-consolidated-rag-optimization-phase-2")


def _repo_root() -> Path:
    for anc in HARNESS.parents:
        if (anc / ".agents/skills/setting-up-rag/scripts/rag_lib.py").is_file():
            return anc
    raise RuntimeError("repo root not found")


def check_deps() -> tuple[bool, list[str]]:
    detail = []
    ok = True
    if VENV_PY.is_file():
        probe = ("import importlib.util;"
                 "print(','.join(m for m in ['fastembed','qdrant_client','rapidfuzz']"
                 " if importlib.util.find_spec(m)))")
        out = subprocess.run([str(VENV_PY), "-c", probe], capture_output=True, text=True)
        present = set(out.stdout.strip().split(",")) if out.stdout.strip() else set()
        for m in ("fastembed", "qdrant_client"):
            mark = "ok" if m in present else "MISSING"
            detail.append(f"venv {m}: {mark}")
            ok = ok and m in present
        detail.append(f"venv rapidfuzz: {'ok' if 'rapidfuzz' in present else 'missing (optional)'}")
    else:
        ok = False
        detail.append(f"skill venv ABSENT at {VENV_PY} — run setup-local-rag.sh")
    # advisory external IR libs (not required: gold.py is the deterministic IR core)
    for m in ("pytrec_eval", "ranx", "ir_measures"):
        spec = subprocess.run([sys.executable, "-c", f"import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('{m}') else 1)"])
        detail.append(f"{m}: {'present' if spec.returncode == 0 else 'absent (advisory; gold.py scorer is the core)'}")
    return ok, detail


def check_sentinels() -> tuple[bool, list[str]]:
    if not VERIFY.is_file():
        return False, [f"verify.py missing at {VERIFY}"]
    out = subprocess.run([sys.executable, str(VERIFY), str(EVAL_SET)], capture_output=True, text=True)
    last = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    return out.returncode == 0, [f"verify.py rc={out.returncode}: {last}"]


def check_reachability() -> tuple[bool, list[str]]:
    qs = G.load_questions()
    errors = G.validate_reachability(qs)
    return not errors, [f"{len(qs)} questions; {len(errors)} reachability errors"] + errors[:8]


def check_chunk_integrity() -> tuple[bool, list[str]]:
    cfg = E._load_cfg(None)
    detail = []
    ok = True
    qs_all = G.load_questions()
    for repo_name, repo in M.REPOS.items():
        corpus = M.load_repo_corpus(repo)
        verbatim = True
        for path, payload in corpus.items():
            for p in E.doc_points(repo_name, path, payload["kind"], payload["lang"], payload["text"], cfg, False):
                if payload["text"][p["start_byte"]:p["end_byte"]] != p["raw_text"]:
                    verbatim = False
                    break
            if not verbatim:
                break
        # sentinel containment within a single chunk
        split = 0
        for q in (x for x in qs_all if x.repo == repo_name):
            for p in q.primary:
                if p not in corpus:
                    continue
                chunks = E.doc_points(repo_name, p, corpus[p]["kind"], corpus[p]["lang"], corpus[p]["text"], cfg, False)
                for s in q.sentinels:
                    if s in corpus[p]["text"] and not any(s in c["raw_text"] for c in chunks):
                        split += 1
        good = verbatim and split == 0
        ok = ok and good
        detail.append(f"{repo_name:22s} verbatim={verbatim} split_sentinels={split}")
    return ok, detail


def check_exclusions() -> tuple[bool, list[str]]:
    detail = []
    ok = True
    # 5a: eval/plan files absent from every loaded corpus
    leaked = []
    for repo_name, repo in M.REPOS.items():
        for path in M.load_repo_corpus(repo):
            if any(tok in path for tok in EXCLUDE_TOKENS):
                leaked.append(f"{repo_name}:{path}")
    detail.append(f"corpus leak of eval/plan files: {len(leaked)}")
    if leaked:
        ok = False
        detail += leaked[:8]
    # 5b: gold.py EXCLUDE_GLOBS also protects the Phase-0 harness corpus
    goldpy = _repo_root() / ".agents/skills/improving-context-retrieval-skills/scripts/gold.py"
    text = goldpy.read_text()
    for tok in EXCLUDE_TOKENS:
        present = tok in text
        detail.append(f"gold.py EXCLUDE_GLOBS mentions {tok}: {'yes' if present else 'NO'}")
        ok = ok and present
    return ok, detail


def check_configs() -> tuple[bool, list[str]]:
    cfg_dir = PLAN_DIR / "configs"
    expect = ["plain-current", "plain-current-no-rerank", "bm25-only", "dense-only",
              "closed-book", "wrong-context", "manual-simple", "prefetch-topn-sweep"]
    detail = []
    ok = True
    for arm in expect:
        fp = cfg_dir / f"{arm}.json"
        if fp.is_file():
            try:
                json.loads(fp.read_text())
                detail.append(f"{arm}.json: ok")
            except json.JSONDecodeError as e:
                ok = False
                detail.append(f"{arm}.json: BAD JSON {e}")
        else:
            ok = False
            detail.append(f"{arm}.json: MISSING")
    return ok, detail


CHECKS = [
    ("1. deps", check_deps),
    ("2. sentinels (verify.py)", check_sentinels),
    ("3. primary reachability", check_reachability),
    ("4. chunk integrity", check_chunk_integrity),
    ("5. contamination exclusions", check_exclusions),
    ("6. wave-0 configs", check_configs),
]


def main() -> int:
    print("=== Phase-3 Wave-0 readiness ===\n")
    all_ok = True
    for name, fn in CHECKS:
        ok, detail = fn()
        all_ok = all_ok and ok
        print(f"[{'GO' if ok else 'NO-GO'}] {name}")
        for d in detail:
            print(f"        {d}")
        print()
    print("=" * 40)
    print("READY for Wave 0" if all_ok else "NOT READY — resolve NO-GO checks above")
    print("(this gate validates data + loaders + controls; it does not run baselines)")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
