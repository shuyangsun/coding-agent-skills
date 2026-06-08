#!/usr/bin/env python3
"""gold.py — deterministic single source of truth for the docs+rag harness.

This is the `scenario.py` analog for the docs/rag harness: it emits the gold
labels AND runs the IR scorers, so the two cannot drift. Doc/retrieval quality
has no computable oracle, so this module replaces the oracle with deterministic
surrogates (plan docs/plans/0002 §2):

  1. Gold-set IR metrics  — graded BEIR qrels -> precision/recall/MRR/nDCG.
  2. Sentinel factuality  — the answer must contain a known sentinel string.
  3. Build-time validation — every sentinel still occurs in its pinned doc.

The fact table below is grounded in this repository's own, machine-checkable
facts (verified at build time). It is a *seed*: the plan calls for 50-100+ queries
via cross-link enumeration and anchored paraphrases (a power calc); growing it is
ordinary round work. Everything here is stdlib-only so Phase-0 needs no services
and no eval-time LLM.

Non-circularity firewall (plan §6):
  - Queries are paraphrases, never echoes: a query may not contain its own
    sentinel, and its token-trigram Jaccard with the primary doc must stay under
    a pinned threshold (LEXICAL_OVERLAP_MAX).
  - Fixed dev/held-out split by stable hash(query_id) — tune on dev, clear the
    bar on held-out, never regenerated per round.
  - Self-reference / meta docs (this harness's own plan + transcript) are excluded
    from the corpus so the gold set never points at a doc that merely quotes a
    fact as an example.

Content-type axis (domains): facts carry a `domain` — "nl" (natural-language docs
under docs/, including exported coding-session transcripts) or "code" (the
inception/ app). Each domain is validated and scored against its OWN corpus, so
code vs natural-language retrieval can be compared with separate metrics.

CLI:
  gold.py build    [--corpus DIR] [--code-corpus DIR] [--out DIR]  # emit per-domain, validate
  gold.py validate [--corpus DIR] [--code-corpus DIR]              # validation + firewall only
  gold.py facts    [--split ...] [--domain nl|code|all]            # list the fact table
  gold.py score    --run FILE --domain nl|code [--corpus DIR] [--split ...] [--k 5,10,20]
                                                   # score a retrieval run vs qrels
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

GOLD_SET_VERSION = "docs-rag-gold-v1"

# Token-trigram Jaccard(query, primary doc) above this is rejected as too-echoic.
LEXICAL_OVERLAP_MAX = 0.30

# Stable dev/held-out partition: held-out iff hash(query_id) is odd.
HELD_OUT_FRACTION_NOTE = "hash(query_id) parity; even=dev, odd=held-out"

# Docs excluded from every corpus snapshot: this harness's own plan + the coding
# session that produced it + the benchmark reports it writes (all quote the gold
# facts/sentinels as worked examples), and any directory-overview index files.
# Globs are matched against the corpus-root relative POSIX path with fnmatch, so
# '*' spans '/'. The OVERVIEW.md globs enforce the firewall this comment has always
# claimed: index docs aggregate many facts' sentinels, so leaving them in-corpus
# would let a retriever score a hit by returning the directory listing instead of
# the actual answer (and would inflate sentinel-mode qrels). The benchmark-report
# globs are the same self-reference guard: a context-retrieval harness report names
# gold sentinels (e.g. "380s") to explain misses, so it must never enter the corpus
# it measures. Match both the historical report names (*docs-skill* / *rag-skill* /
# *docs-rag*) and the current per-skill names (*setting-up-rag* / *updating-docs* /
# *retrieving-context*); vcs (and other) benchmark reports stay legitimate corpus docs.
EXCLUDE_GLOBS = [
    # this harness's design plan + the sessions that produced it (historical + current names)
    "plans/0002-improving-docs-and-rag-skills.md",
    "plans/*improving-docs-and-rag*.md",
    "plans/*improving-context-retrieval*.md",
    "coding-sessions/*/*improving-docs-and-rag*.md",
    "coding-sessions/*/*improving-context-retrieval*.md",
    # benchmark reports that quote gold sentinels (historical + current per-skill names)
    "benchmarks/*docs-skill*.md",
    "benchmarks/*rag-skill*.md",
    "benchmarks/*docs-rag*.md",
    "benchmarks/*setting-up-rag*.md",
    "benchmarks/*updating-docs*.md",
    "benchmarks/*retrieving-context*.md",
    "OVERVIEW.md",
    "*/OVERVIEW.md",
]

# The code corpus (content-type axis, domain="code"). Phase-0 indexes the repo's
# own `inception/` TanStack Start app — a realistic target codebase built for this
# harness — so retrieval over CODE can be measured separately from natural-language
# docs ("inception only for now"). These select which files load and which trees
# to skip (build output, dependencies, lockfiles).
CODE_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json", ".css", ".html", ".md")
CODE_SKIP_DIRS = {"node_modules", "dist", "build", ".output", ".vite", ".nitro",
                  ".git", ".turbo", "coverage", ".cache"}
CODE_SKIP_FILES = {"bun.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"}


@dataclass(frozen=True)
class Fact:
    """One anchored, machine-checkable fact -> one gold query.

    sentinels:   answer strings that must appear in a relevant doc (factuality).
    primary:     corpus-root-relative paths hand-pinned as primary (grade 2).
                 Build-time validation asserts each sentinel occurs in each.
    qtype:       fact family (benchmark|issue|skill-behavior|cross-link|history|
                 code|coding-session).
    difficulty:  easy|medium|hard (hard => multi-sentinel across doc types).
    domain:      content type, which corpus the fact is scored against:
                 "nl"   = natural-language docs (markdown under docs/, incl. the
                          exported coding-session transcripts), or
                 "code" = the inception/ codebase (source + config files).
                 The harness scores each domain separately so code vs natural-
                 language retrieval can be compared (plan: content-type axis).
                 `primary` paths are relative to that domain's corpus root.
    answerable_closed_book: if True, the model may know the sentinel without the
                 corpus (parametric leakage); such queries are excluded from the
                 factuality headline (the closed-book control, plan §6).
    """

    id: str
    query: str
    sentinels: tuple[str, ...]
    primary: tuple[str, ...]
    qtype: str
    difficulty: str
    domain: str = "nl"
    answerable_closed_book: bool = False


# --- The seed fact table (verified against docs/ at build time) -------------
FACTS: list[Fact] = [
    Fact(
        id="bench-conflict-time",
        query="By how much did tuning the version-control skill speed up resolving "
        "a whole batch of merge conflicts?",
        sentinels=("380s", "85s"),
        primary=("benchmarks/2026-06-06/0000-vcs-skill-conflict-resolution.md",),
        qtype="benchmark",
        difficulty="medium",
    ),
    Fact(
        id="orphan-empty-head",
        query="What stray jj change was left behind after a workspace was cleaned "
        "up, and how was it removed?",
        sentinels=("urruyqxt",),
        primary=("issues/2026-06-07/0007-workspace-cleanup-left-unreferenced-empty-side-head.md",),
        qtype="issue",
        difficulty="hard",
    ),
    Fact(
        id="name-metric-transaction-hook",
        query="How is the workspace-naming convention scored durably even though "
        "branch names disappear when a branch is deleted?",
        sentinels=("reference-transaction",),
        primary=("coding-sessions/2026-06-06/0012-claude-vcs-skill-name-metric.md",),
        qtype="skill-behavior",
        difficulty="medium",
    ),
    Fact(
        id="composer-benchmark",
        query="Which coding model was benchmarked head-to-head on Jujutsu versus "
        "plain Git for the version-control skill?",
        sentinels=("Composer 2.5",),
        primary=("benchmarks/2026-06-07/0002-vcs-skill-composer-2.5-jj-vs-git.md",),
        qtype="benchmark",
        difficulty="medium",
    ),
    Fact(
        id="integrate-degenerate-merge",
        query="Why did landing finished work through the integrate helper sometimes "
        "create an empty merge that could not be pushed?",
        sentinels=("degenerate",),
        primary=("issues/2026-06-07/0003-jj-integrate-forms-degenerate-empty-merge-blocking-push.md",),
        qtype="issue",
        difficulty="medium",
    ),
    # --- Natural-language: exported coding-session transcript (domain="nl") ----
    # Retrieval over an exported session transcript (long, dialog-shaped prose) —
    # a distinct content type from the issue/benchmark docs above.
    Fact(
        id="session-inception-toolchain",
        query="Which exported coding session stood up the demo web app so it "
        "type-checks with the experimental native-Go build of the TypeScript "
        "compiler instead of plain tsc?",
        sentinels=("native-preview",),
        primary=("coding-sessions/2026-06-07/0028-claude-inception-tanstack-tooling.md",),
        qtype="coding-session",
        difficulty="medium",
        domain="nl",
    ),
    # --- Code: the inception/ TanStack Start app (domain="code") ---------------
    # "inception only for now": primaries are relative to the inception/ root, and
    # these are scored against the code corpus, never the docs corpus.
    Fact(
        id="code-router-preload",
        query="In the inception web app, how does the client-side router decide "
        "when to prefetch a route's code and data ahead of the user navigating?",
        sentinels=("defaultPreload",),
        primary=("src/router.tsx",),
        qtype="code",
        difficulty="medium",
        domain="code",
    ),
    Fact(
        id="code-react-compiler",
        query="How does the inception Vite build switch on React's automatic "
        "memoization — name the rolldown/babel plugin it loads and the preset it "
        "applies to it?",
        sentinels=("@rolldown/plugin-babel", "reactCompilerPreset"),
        primary=("vite.config.ts",),
        qtype="code",
        difficulty="hard",
        domain="code",
    ),
    Fact(
        id="code-typecheck-tsgo",
        query="What package script type-checks the inception sources, and which "
        "non-tsc compiler binary does it invoke under the hood?",
        sentinels=("tsgo --noEmit",),
        primary=("package.json",),
        qtype="code",
        difficulty="medium",
        domain="code",
    ),
]


# --- Corpus loading ----------------------------------------------------------
def find_corpus_root(explicit: str | None) -> Path:
    """Locate the corpus root (a directory of .md docs). Defaults to repo docs/."""
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.is_dir():
            sys.exit(f"gold.py: corpus dir not found: {p}")
        return p
    here = Path(__file__).resolve()
    for anc in here.parents:
        cand = anc / "docs"
        if (cand / "benchmarks").is_dir() or (cand / "issues").is_dir():
            return cand.resolve()
    sys.exit("gold.py: could not auto-locate docs/ corpus; pass --corpus DIR")


def find_code_corpus_root(explicit: str | None) -> Path | None:
    """Locate the code corpus root (the inception/ app). Returns None if absent,
    so a checkout without inception/ can still run the natural-language domain."""
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.is_dir():
            sys.exit(f"gold.py: code corpus dir not found: {p}")
        return p
    here = Path(__file__).resolve()
    for anc in here.parents:
        cand = anc / "inception"
        if (cand / "package.json").is_file():
            return cand.resolve()
    return None


def is_excluded(relpath: str) -> bool:
    return any(fnmatch.fnmatch(relpath, g) for g in EXCLUDE_GLOBS)


def load_corpus(corpus_root: Path, kind: str = "md") -> dict[str, str]:
    """Map corpus-root-relative POSIX path -> document text.

    kind="md"   : every *.md under the root, minus EXCLUDE_GLOBS (the docs/NL
                  domain: issues, benchmarks, transcripts, …).
    kind="code" : every CODE_EXTS file under the root, skipping dependency/build
                  dirs and lockfiles (the inception/ code domain).
    """
    if kind == "md":
        paths = list(corpus_root.rglob("*.md"))
    elif kind == "code":
        paths = [p for ext in CODE_EXTS for p in corpus_root.rglob(f"*{ext}")]
    else:
        raise ValueError(f"unknown corpus kind: {kind!r}")

    docs: dict[str, str] = {}
    for path in sorted(set(paths)):
        rel = path.relative_to(corpus_root).as_posix()
        if kind == "code":
            if set(Path(rel).parts) & CODE_SKIP_DIRS or path.name in CODE_SKIP_FILES:
                continue
        elif is_excluded(rel):
            continue
        try:
            docs[rel] = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:  # pragma: no cover - defensive
            print(f"gold.py: warning: cannot read {rel}: {exc}", file=sys.stderr)
    return docs


# --- Text utilities for the firewall ----------------------------------------
_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def trigrams(toks: list[str]) -> set[tuple[str, str, str]]:
    return {tuple(toks[i : i + 3]) for i in range(len(toks) - 2)} if len(toks) >= 3 else set()


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b) if (a | b) else 0.0


# --- qrels construction ------------------------------------------------------
def build_qrels(
    facts: list[Fact], docs: dict[str, str], mode: str = "pinned"
) -> dict[str, dict[str, int]]:
    """Graded relevance labels per query, in one of two modes:

    - ``pinned`` (GOLD/D plane): hand-pinned primary docs are grade 2; any other
      corpus doc that contains a sentinel is grade 1 (corroborating). Used where
      the structured doc paths are stable. Plan §6: never singletons when the
      corpus genuinely repeats a fact.
    - ``sentinel`` (per-corpus N/D plane): purely sentinel-derived, so it works
      for any corpus structure (naive dumps with opaque filenames included). A
      doc containing ALL of a fact's sentinels is grade 2; a doc containing some
      (but not all) is grade 1. Plan §3: labels are derived from the sentinels
      actually present in each corpus's files, never from GOLD's paths.
    """
    qrels: dict[str, dict[str, int]] = {}
    for fact in facts:
        rel: dict[str, int] = {}
        if mode == "pinned":
            for p in fact.primary:
                rel[p] = 2
            for doc_id, text in docs.items():
                if doc_id in rel:
                    continue
                if any(s in text for s in fact.sentinels):
                    rel[doc_id] = 1
        elif mode == "sentinel":
            n = len(fact.sentinels)
            for doc_id, text in docs.items():
                present = sum(1 for s in fact.sentinels if s in text)
                if present == 0:
                    continue
                rel[doc_id] = 2 if present == n else 1
        else:
            raise ValueError(f"unknown qrels mode: {mode}")
        qrels[fact.id] = rel
    return qrels


def split_of(query_id: str) -> str:
    h = int(hashlib.sha256(query_id.encode()).hexdigest(), 16)
    return "held-out" if h % 2 else "dev"


# --- Validation + firewall ---------------------------------------------------
def validate(facts: list[Fact], corpora: dict[str, dict[str, str]]) -> list[str]:
    """Return a list of error strings (empty => valid).

    `corpora` maps domain ("nl"|"code") -> that domain's {path: text}. Each fact
    is validated against the corpus for its own domain, so a code fact's primary
    is checked in inception/ and an nl fact's in docs/."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    for fact in facts:
        if fact.id in seen_ids:
            errors.append(f"[{fact.id}] duplicate fact id")
        seen_ids.add(fact.id)
        if fact.difficulty not in ("easy", "medium", "hard"):
            errors.append(f"[{fact.id}] bad difficulty {fact.difficulty!r}")
        docs = corpora.get(fact.domain)
        if docs is None:
            errors.append(f"[{fact.id}] no corpus loaded for domain {fact.domain!r} "
                          f"(have: {sorted(corpora)})")
            continue
        # primary docs exist and contain every sentinel
        for p in fact.primary:
            if p not in docs:
                errors.append(f"[{fact.id}] primary doc missing from corpus: {p}")
                continue
            for s in fact.sentinels:
                if s not in docs[p]:
                    errors.append(f"[{fact.id}] sentinel {s!r} not in primary {p}")
        # firewall 1a: query must not echo a sentinel verbatim
        q_low = fact.query.lower()
        for s in fact.sentinels:
            if s.lower() in q_low:
                errors.append(f"[{fact.id}] query echoes sentinel {s!r} (not a paraphrase)")
        # firewall 1b: token-trigram overlap with primary doc must stay low
        q_tri = trigrams(tokens(fact.query))
        for p in fact.primary:
            if p in docs:
                j = jaccard(q_tri, trigrams(tokens(docs[p])))
                if j > LEXICAL_OVERLAP_MAX:
                    errors.append(
                        f"[{fact.id}] query-vs-{p} trigram Jaccard {j:.3f} > "
                        f"{LEXICAL_OVERLAP_MAX} (too echoic)"
                    )
    return errors


# --- IR metrics (the shared scorer; check-retrieval.py imports these) --------
def _dcg(grades: list[int]) -> float:
    return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(grades))


def score_query(ranked: list[str], rel: dict[str, int], ks: list[int]) -> dict[str, float]:
    """Graded IR metrics for one query. `ranked` is the ordered doc-id list."""
    relevant = {d for d, g in rel.items() if g >= 1}
    out: dict[str, float] = {}
    for k in ks:
        topk = ranked[:k]
        hits = sum(1 for d in topk if d in relevant)
        out[f"recall@{k}"] = hits / len(relevant) if relevant else 0.0
        out[f"precision@{k}"] = hits / k if k else 0.0
        ideal = sorted(rel.values(), reverse=True)[:k]
        dcg = _dcg([rel.get(d, 0) for d in topk])
        idcg = _dcg(ideal)
        out[f"ndcg@{k}"] = dcg / idcg if idcg else 0.0
    mrr = 0.0
    for i, d in enumerate(ranked):
        if d in relevant:
            mrr = 1.0 / (i + 1)
            break
    out["mrr"] = mrr
    return out


def aggregate(per_query: dict[str, dict[str, float]]) -> dict[str, float]:
    if not per_query:
        return {}
    keys = next(iter(per_query.values())).keys()
    return {k: sum(q[k] for q in per_query.values()) / len(per_query) for k in keys}


# --- Output ------------------------------------------------------------------
def emit(out_dir: Path, facts: list[Fact], docs: dict[str, str], qrels) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    # BEIR-style qrels TSV: query-id <tab> corpus-id <tab> score
    with (out_dir / "qrels.tsv").open("w", encoding="utf-8") as fh:
        fh.write("query-id\tcorpus-id\tscore\n")
        for qid in sorted(qrels):
            for doc_id in sorted(qrels[qid]):
                fh.write(f"{qid}\t{doc_id}\t{qrels[qid][doc_id]}\n")
    # query records
    with (out_dir / "records.jsonl").open("w", encoding="utf-8") as fh:
        for fact in facts:
            fh.write(
                json.dumps(
                    {
                        "query_id": fact.id,
                        "query": fact.query,
                        "sentinels": list(fact.sentinels),
                        "gold_doc_paths": list(fact.primary),
                        "qrels": qrels[fact.id],
                        "difficulty": fact.difficulty,
                        "qtype": fact.qtype,
                        "domain": fact.domain,
                        "split": split_of(fact.id),
                        "answerable_closed_book": fact.answerable_closed_book,
                        "gold_set_version": GOLD_SET_VERSION,
                    }
                )
                + "\n"
            )
    # corpus manifest (doc-id -> length), so docs-eval indexes exactly this set
    with (out_dir / "corpus.jsonl").open("w", encoding="utf-8") as fh:
        for doc_id in sorted(docs):
            fh.write(json.dumps({"doc_id": doc_id, "chars": len(docs[doc_id])}) + "\n")
    summary = {
        "gold_set_version": GOLD_SET_VERSION,
        "n_queries": len(facts),
        "n_docs": len(docs),
        "split": {
            "dev": sum(1 for f in facts if split_of(f.id) == "dev"),
            "held-out": sum(1 for f in facts if split_of(f.id) == "held-out"),
        },
        "by_difficulty": {
            d: sum(1 for f in facts if f.difficulty == d) for d in ("easy", "medium", "hard")
        },
        "multi_relevant_queries": sum(1 for q in qrels.values() if len(q) > 1),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"gold.py: wrote qrels/records/corpus/summary to {out_dir}")
    print(json.dumps(summary, indent=2))


# --- Run scoring -------------------------------------------------------------
def load_run(run_file: Path) -> dict[str, list[str]]:
    """A run file is JSONL of {query_id, ranked:[doc_id,...]} or a single JSON
    object {query_id: [doc_id,...]}."""
    text = run_file.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    if text[0] == "{" and "\n" not in text.strip().splitlines()[0][:1] and text.count("\n") == 0:
        return {k: list(v) for k, v in json.loads(text).items()}
    runs: dict[str, list[str]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        runs[obj["query_id"]] = list(obj["ranked"])
    return runs


def load_corpora(args) -> tuple[dict[str, dict[str, str]], Path]:
    """Load every domain corpus the fact table needs. The nl (docs) corpus is
    always loaded; the code (inception/) corpus is loaded when any code fact
    exists and inception/ is found. A checkout without inception/ degrades to
    nl-only (a warning is printed and code facts are skipped, see active_facts).
    Returns (corpora_by_domain, nl_root)."""
    nl_root = find_corpus_root(args.corpus)
    corpora: dict[str, dict[str, str]] = {"nl": load_corpus(nl_root, kind="md")}
    if any(f.domain == "code" for f in FACTS):
        code_root = find_code_corpus_root(getattr(args, "code_corpus", None))
        if code_root is not None:
            corpora["code"] = load_corpus(code_root, kind="code")
        else:
            print("gold.py: warning: inception/ code corpus not found; skipping the "
                  "code domain (running natural-language facts only).", file=sys.stderr)
    return corpora, nl_root


def active_facts(corpora: dict[str, dict[str, str]]) -> list[Fact]:
    """Facts whose domain corpus is loaded. Facts in an absent domain are skipped
    (their corpus could not be located), keeping validate/build nl-only-safe."""
    return [f for f in FACTS if f.domain in corpora]


def cmd_score(args) -> int:
    kind = "code" if args.domain == "code" else "md"
    if kind == "code":
        root = find_code_corpus_root(args.corpus)
        if root is None:
            sys.exit("gold.py: code corpus (inception/) not found; pass --corpus DIR")
    else:
        root = find_corpus_root(args.corpus)
    docs = load_corpus(root, kind=kind)
    facts = [f for f in FACTS if args.split in ("all", split_of(f.id)) and f.domain == args.domain]
    qrels = build_qrels(facts, docs)
    ks = [int(x) for x in args.k.split(",")]
    runs = load_run(Path(args.run))
    per_query: dict[str, dict[str, float]] = {}
    missing = []
    for fact in facts:
        if fact.id not in runs:
            missing.append(fact.id)
            continue
        per_query[fact.id] = score_query(runs[fact.id], qrels[fact.id], ks)
    agg = aggregate(per_query)
    for key in sorted(agg):
        print(f"{key}={agg[key]:.4f}")
    print(f"domain={args.domain}")
    print(f"n_scored={len(per_query)}")
    print(f"n_missing={len(missing)}")
    print(f"split={args.split}")
    print(f"gold_set_version={GOLD_SET_VERSION}")
    return 0


def cmd_build(args) -> int:
    corpora, nl_root = load_corpora(args)
    facts = active_facts(corpora)
    errors = validate(facts, corpora)
    if errors:
        print("gold.py: VALIDATION FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    out_dir = Path(args.out).expanduser().resolve() if args.out else nl_root.parent / "gold-set"
    for domain in sorted(corpora):
        dfacts = [f for f in facts if f.domain == domain]
        qrels = build_qrels(dfacts, corpora[domain])
        emit(out_dir / domain, dfacts, corpora[domain], qrels)
    print(f"gold.py: built {len(corpora)} domain(s) under {out_dir}: {sorted(corpora)}")
    return 0


def cmd_validate(args) -> int:
    corpora, _ = load_corpora(args)
    facts = active_facts(corpora)
    errors = validate(facts, corpora)
    if errors:
        print("gold.py: VALIDATION FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    for domain in sorted(corpora):
        dfacts = [f for f in facts if f.domain == domain]
        qrels = build_qrels(dfacts, corpora[domain])
        multi = sum(1 for q in qrels.values() if len(q) > 1)
        print(f"  {domain:<5} {len(dfacts):>2} facts  {len(corpora[domain]):>3} docs  "
              f"{multi} multi-relevant")
    print(f"gold.py: OK — {len(facts)} facts across {len(corpora)} domain(s)")
    return 0


def cmd_facts(args) -> int:
    for fact in FACTS:
        if args.split not in ("all", split_of(fact.id)):
            continue
        if args.domain not in ("all", fact.domain):
            continue
        print(f"{fact.id}\t{fact.domain}\t{split_of(fact.id)}\t{fact.difficulty}\t"
              f"{fact.qtype}\t{fact.query}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("build", help="emit qrels/records/corpus and validate")
    pb.add_argument("--corpus", help="docs/ (nl) corpus root")
    pb.add_argument("--code-corpus", help="inception/ (code) corpus root")
    pb.add_argument("--out")
    pb.set_defaults(func=cmd_build)

    pv = sub.add_parser("validate", help="validation + firewall only")
    pv.add_argument("--corpus", help="docs/ (nl) corpus root")
    pv.add_argument("--code-corpus", help="inception/ (code) corpus root")
    pv.set_defaults(func=cmd_validate)

    pf = sub.add_parser("facts", help="list the fact table")
    pf.add_argument("--split", choices=["dev", "held-out", "all"], default="all")
    pf.add_argument("--domain", choices=["nl", "code", "all"], default="all")
    pf.set_defaults(func=cmd_facts)

    ps = sub.add_parser("score", help="score a retrieval run vs qrels")
    ps.add_argument("--run", required=True)
    ps.add_argument("--corpus", help="corpus root for the chosen --domain")
    ps.add_argument("--domain", choices=["nl", "code"], default="nl")
    ps.add_argument("--split", choices=["dev", "held-out", "all"], default="all")
    ps.add_argument("--k", default="5,10,20")
    ps.set_defaults(func=cmd_score)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
