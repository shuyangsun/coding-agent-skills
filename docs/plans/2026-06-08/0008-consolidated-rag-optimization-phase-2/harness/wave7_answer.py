#!/usr/bin/env python3
"""wave7_answer.py — answer generation, packing, and faithfulness metrics.

Wave 7 of ``0008-consolidated-rag-optimization-phase-2.md`` moves past retrieval
ranking: the promoted retriever already has near-ceiling R@20, so the remaining
questions are whether a source-preserving reader pack, citation-forced answers,
and a bounded retry/abstain policy improve grounded answers.

This script deliberately separates retrieval packing from generation:

  * ``pack`` runs under the RAG venv while the reranker service is up. It retrieves
    once per query, writes source-preserving context packs for several pack orders
    and budgets, and records retrieval/pack metrics in each JSONL row.
  * ``generate`` runs under the campaign/LLM venv. It reads those saved packs, calls
    an OpenAI-compatible local model endpoint, scores deterministic answer metrics
    (sentinel containment + mechanical citation coverage), and writes metrics TSV
    plus a summary JSON.

The gold answer and sentinels are NEVER sent to the generator; sentinels are used
only after the answer is produced.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_HARNESS = Path(__file__).resolve().parent
sys.path.insert(0, str(_HARNESS))

import contamination as C  # noqa: E402
import gold_loader as G  # noqa: E402
import metrics as MET  # noqa: E402
import run_benchmark as RB  # noqa: E402
import wave5_graph as W5  # noqa: E402


DEFAULT_PACKS = ("score:raw", "score:4000", "source:4000", "parent:4000")
ANSWER_PROMPT_VERSION = "w7-answer-v1"
_CITE = re.compile(r"\[S(\d+)\]")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
_ABSTAIN = re.compile(
    r"\b(i do not know|i don't know|not enough|insufficient|cannot determine|"
    r"provided sources do not|sources do not)\b",
    re.I,
)


def _load_cfg(path: str | None, arm: str | None) -> dict:
    cfg_dir = _HARNESS.parent / "configs"
    if arm:
        path = str(cfg_dir / f"{arm}.json")
    if not path:
        raise SystemExit("pass --config or --arm")
    return json.loads(Path(path).read_text())


def _select_questions(args) -> list[G.Question]:
    qs = G.load_questions()
    if args.split != "all":
        qs = [q for q in qs if q.split == args.split]
    if args.repos != "all":
        wanted = set(args.repos.split(","))
        qs = [q for q in qs if q.repo in wanted]
    if args.caveat_slice:
        qs = [
            q for q in qs
            if q.repo == "alpha-zero"
            or q.category == "session-prompting"
            or (q.difficulty == "hard" and q.domain == "nl")
        ]
    if args.query_id:
        wanted = set(args.query_id)
        qs = [q for q in qs if q.id in wanted]
    if args.limit:
        qs = qs[: args.limit]
    return qs


def _parse_budget(raw: str) -> int | None:
    val = raw.strip().lower()
    if val in {"raw", "all", "none", "top20"}:
        return None
    if val.endswith("k"):
        return int(float(val[:-1]) * 1000)
    return int(val)


def parse_pack_specs(specs: list[str] | None) -> list[dict]:
    out = []
    for spec in specs or list(DEFAULT_PACKS):
        if ":" not in spec:
            raise SystemExit(f"pack spec must be ORDER:BUDGET, got {spec!r}")
        order, budget = spec.split(":", 1)
        order = order.strip()
        if order not in {"score", "source", "parent"}:
            raise SystemExit(f"unknown pack order {order!r}; use score|source|parent")
        tok = _parse_budget(budget)
        label = "raw20" if tok is None else f"{tok // 1000}k"
        out.append({"order": order, "budget": tok, "label": f"{order}-{label}"})
    return out


def est_tokens(text: str) -> int:
    return (len(text) + 3) // 4


def _source_from_hit(hit, rank: int) -> dict:
    p = hit.payload
    raw = p.get("raw_text", p.get("text", ""))
    return {
        "rank": rank,
        "doc_id": p.get("doc_id", ""),
        "path": p.get("path", p.get("doc_id", "")),
        "kind": p.get("kind", ""),
        "lang": p.get("lang", ""),
        "heading_path": p.get("heading_path", ""),
        "symbol": p.get("symbol", ""),
        "parent_id": p.get("parent_id", ""),
        "parent_start": int(p.get("parent_start") or 0),
        "start_line": int(p.get("start_line") or 1),
        "end_line": int(p.get("end_line") or 1),
        "raw_text": raw,
    }


def _ordered_sources(sources: list[dict], order: str) -> list[dict]:
    if order == "score":
        return list(sources)
    if order == "source":
        return sorted(sources, key=lambda s: (s["doc_id"], s["start_line"], s["rank"]))
    groups: dict[tuple[str, int], list[dict]] = collections.defaultdict(list)
    for src in sources:
        groups[(src["doc_id"], src["parent_start"])].append(src)
    ordered = []
    for _key, group in sorted(groups.items(), key=lambda item: min(s["rank"] for s in item[1])):
        ordered.extend(sorted(group, key=lambda s: (s["start_line"], s["rank"])))
    return ordered


def _block(src: dict, sid: int) -> str:
    loc = f"{src['path']}:{src['start_line']}-{src['end_line']}"
    parts = [f"[S{sid}] {loc}", f"kind={src['kind']}"]
    if src.get("lang"):
        parts.append(f"lang={src['lang']}")
    if src.get("heading_path"):
        parts.append(f"heading={src['heading_path']}")
    if src.get("symbol"):
        parts.append(f"symbol={src['symbol']}")
    header = " | ".join(parts)
    return f"{header}\n{src['raw_text'].strip()}\n"


def build_pack(sources: list[dict], order: str, budget_tokens: int | None,
               sentinels: tuple[str, ...]) -> dict:
    ordered = _ordered_sources(sources, order)
    kept = []
    blocks = []
    used = 0
    for src in ordered:
        sid = len(kept) + 1
        block = _block(src, sid)
        cost = est_tokens(block)
        if budget_tokens is not None and kept and used + cost > budget_tokens:
            continue
        if budget_tokens is not None and not kept and cost > budget_tokens:
            raw_budget = max(200, budget_tokens * 4 - len(block) + len(src["raw_text"]))
            src = dict(src)
            src["raw_text"] = src["raw_text"][:raw_budget].rstrip() + "\n[truncated]"
            block = _block(src, sid)
            cost = est_tokens(block)
        if budget_tokens is not None and used + cost > budget_tokens and kept:
            continue
        src = {k: v for k, v in src.items() if k != "raw_text"}
        src["sid"] = f"S{sid}"
        kept.append(src)
        blocks.append(block)
        used += cost
        if budget_tokens is None and len(kept) >= 20:
            break
    context = "\n".join(blocks)
    first_evidence = ""
    first_tokens = ""
    before = 0
    for src, block in zip(kept, blocks, strict=False):
        if any(s in block for s in sentinels):
            first_evidence = src["sid"]
            first_tokens = before
            break
        before += est_tokens(block)
    return {
        "context": context,
        "sources": kept,
        "context_tokens": est_tokens(context),
        "n_packed": len(kept),
        "first_evidence_source": first_evidence,
        "first_evidence_tokens": first_tokens,
        "sentinel_in_pack": sum(1 for s in sentinels if s in context) / len(sentinels)
        if sentinels else 0.0,
    }


def pack_for_repo(cfg: dict, repo: str, qs: list[G.Question], specs: list[dict],
                  depth: int, reindex: bool, run_id: str) -> list[dict]:
    mode = cfg.get("retrieval_mode", "hybrid")
    top_k = int(cfg.get("top_k", 20))
    key = RB.index_key(cfg)
    corpus = G.combined_corpus(repo, qs)
    qrels = G.build_file_qrels(qs, corpus, sentinel_grade1=False)
    needs_index = mode in ("hybrid", "dense-only", "bm25-only", "wrong-context")
    client = None
    coll = None
    index_ms = 0.0
    if needs_index:
        client, _ = RB.R.get_client()
        coll, index_ms = RB.ensure_index(repo, cfg, key, reindex)
    graph = W5.build_graph(repo) if cfg.get("graph_overlay", {}).get("enabled") else None
    base_arm = cfg.get("arm", cfg.get("rag_config_id", "arm"))
    rows = []

    for q in qs:
        route: dict = {}
        t0 = time.time()
        if mode == "manual-rg":
            ranked_files = RB.manual_rg_rank(corpus, q.question, depth)
            hits = []
            sources = []
            for rank, doc_id in enumerate(ranked_files[:top_k], start=1):
                payload = corpus[doc_id]
                sources.append({
                    "rank": rank, "doc_id": doc_id, "path": doc_id,
                    "kind": payload["kind"], "lang": payload.get("lang", ""),
                    "heading_path": "", "symbol": "", "parent_id": doc_id,
                    "parent_start": 0, "start_line": 1,
                    "end_line": payload["text"].count("\n") + 1,
                    "raw_text": payload["text"],
                })
            file_kind = {p: corpus[p]["kind"] for p in ranked_files}
        else:
            hits = RB.retrieve_chunks(client, coll, q.question, cfg, mode, depth, graph,
                                      qid=q.id, route=route)
            ranked_files, file_kind, _ctx_texts, _ctx_kinds = RB.derive_ranking(hits, top_k)
            sources = [_source_from_hit(h, rank) for rank, h in enumerate(hits[:top_k], start=1)]
        retrieval_ms = (time.time() - t0) * 1000.0
        contam = C.check_query(ranked_files[:20], q.primary)

        for spec in specs:
            pack = build_pack(sources, spec["order"], spec["budget"], q.sentinels)
            packed_texts = []
            packed_kinds = []
            sid_to_source = {s["sid"]: s for s in pack["sources"]}
            for src in pack["sources"]:
                original = sources[int(src["sid"][1:]) - 1]
                packed_texts.append(original["raw_text"])
                packed_kinds.append(src["kind"])
            ret = MET.retrieval_metrics(
                ranked_files,
                qrels[q.id],
                ks=RB.KS,
                retrieved_texts=packed_texts,
                sentinels=q.sentinels,
                retrieved_kinds=packed_kinds,
            )
            metric_row = {}
            metric_row.update(MET.slice_columns(q))
            metric_row.update({
                "arm.run_id": run_id,
                "arm.config_id": f"{cfg.get('rag_config_id', base_arm)}+{spec['label']}",
                "arm.arm": f"{base_arm}+{spec['label']}",
                "arm.index_mode": cfg.get("index_mode", "combined"),
                "arm.header": bool(cfg.get("contextual_header", False)),
                "arm.reranked": bool(cfg.get("rerank", {}).get("enabled", False)),
            })
            metric_row.update({k: round(v, 6) if isinstance(v, float) else v
                               for k, v in ret.items()})
            metric_row.update({
                "pack.context_tokens": pack["context_tokens"],
                "pack.n_packed": pack["n_packed"],
                "ver.contamination_hits": len(contam),
                "eff.retrieval_ms": round(retrieval_ms, 2),
                "eff.index_ms": round(index_ms, 1),
                "route.action": route.get("action", ""),
                "route.triggered": route.get("triggered", ""),
                "route.n_sub": route.get("n_sub", ""),
                "route.feat": route.get("feat", ""),
            })
            rows.append({
                "pack_id": f"{q.id}:{base_arm}+{spec['label']}",
                "query": q.__dict__,
                "pack": {k: v for k, v in pack.items() if k != "context"},
                "pack_order": spec["order"],
                "pack_budget": spec["budget"],
                "context": pack["context"],
                "sid_to_source": sid_to_source,
                "metric_row": metric_row,
            })
    return rows


def cmd_pack(args) -> int:
    cfg = _load_cfg(args.config, args.arm)
    specs = parse_pack_specs(args.pack)
    qs = _select_questions(args)
    by_repo: dict[str, list[G.Question]] = collections.defaultdict(list)
    for q in qs:
        by_repo[q.repo].append(q)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", encoding="utf-8") as fh:
        for repo, rqs in sorted(by_repo.items()):
            rows = pack_for_repo(cfg, repo, rqs, specs, args.depth, args.reindex, args.tag)
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += len(rows)
            print(f"  {repo:24s} queries={len(rqs):3d} pack_rows={len(rows):4d}")
    print(f"wrote {n} packs -> {out}")
    return 0


def _client(base_url: str, api_key: str | None):
    from openai import OpenAI
    return OpenAI(base_url=base_url, api_key=api_key or os.environ.get("LITELLM_API_KEY", "x"))


def _messages(pack: dict, prompt_style: str) -> list[dict]:
    q = pack["query"]
    source_count = pack["pack"]["n_packed"]
    if prompt_style == "extractive":
        system = (
            "You answer software repository questions using only the provided source excerpts. "
            "Copy exact source wording for identifiers, constants, numbers, file names, quoted "
            "strings, command names, and error text instead of paraphrasing them. Every factual "
            "sentence must end with one or more citations like [S3]. Use only source IDs that "
            "appear in the context. If the context does not contain the answer, say \"I don't "
            "know from the provided sources.\" Keep the answer concise."
        )
    else:
        system = (
            "You answer software repository questions using only the provided source excerpts. "
            "Every factual sentence must end with one or more citations like [S3]. "
            "Use only source IDs that appear in the context. If the context does not contain "
            "the answer, say \"I don't know from the provided sources.\" Keep the answer concise."
        )
    user = (
        f"Question:\n{q['question']}\n\n"
        f"Source excerpts ({source_count}):\n{pack['context']}\n\n"
        "Answer with citations on every factual sentence."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _gen_one(client, pack: dict, model: str, max_tokens: int, extra_body: dict | None,
             retries: int, prompt_style: str) -> dict:
    last = ""
    t0 = time.time()
    for attempt in range(retries):
        try:
            kwargs = {"extra_body": extra_body} if extra_body else {}
            r = client.chat.completions.create(
                model=model,
                messages=_messages(pack, prompt_style),
                temperature=0.0,
                max_tokens=max_tokens,
                **kwargs,
            )
            answer = (r.choices[0].message.content or "").strip()
            return {"answer": answer, "gen_ms": round((time.time() - t0) * 1000, 1), "error": ""}
        except Exception as exc:  # noqa: BLE001 - endpoint errors are retried and recorded.
            last = str(exc)
            time.sleep(min(2 ** attempt, 8))
    return {"answer": "", "gen_ms": round((time.time() - t0) * 1000, 1), "error": last}


def _answer_sentences(answer: str) -> list[str]:
    out = []
    for part in _SENTENCE.split(answer):
        s = part.strip()
        if s and re.search(r"[A-Za-z0-9]", s):
            out.append(s)
    return out


def score_answer(pack: dict, answer: str) -> dict:
    q = pack["query"]
    valid = set(pack["sid_to_source"])
    citations = _CITE.findall(answer)
    invalid = [c for c in citations if f"S{c}" not in valid]
    sentences = _answer_sentences(answer)
    cited = 0
    for s in sentences:
        ids = [f"S{i}" for i in _CITE.findall(s)]
        if ids and all(i in valid for i in ids):
            cited += 1
    citation_support = cited / len(sentences) if sentences else 0.0
    sentinel = 0.0
    if q.get("sentinels"):
        sentinel = sum(1 for s in q["sentinels"] if s in answer) / len(q["sentinels"])
    return {
        "gen.abstained": 1 if _ABSTAIN.search(answer) else 0,
        "gen.answer_len": est_tokens(answer),
        "ver.sentinel_contained": round(sentinel, 6),
        "ver.citation_support": round(citation_support, 6),
        "ver.unsupported_rate": round(1.0 - citation_support, 6),
        "invalid_citations": invalid,
        "n_citations": len(citations),
        "n_sentences": len(sentences),
    }


def _load_existing_answers(path: Path) -> dict:
    if not path.is_file():
        return {}
    out = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            out[row["pack_id"]] = row
    return out


def _write_summary(rows: list[dict], path: Path, run_id: str, split: str) -> None:
    metrics = [
        "ret.recall@20", "ret.ndcg@10", "ret.primary_mrr", "ret.sentinel_cov",
        "ret.answer_hit@5", "pack.context_tokens", "pack.n_packed",
        "gen.abstained", "gen.answer_len", "ver.sentinel_contained",
        "ver.citation_support", "ver.unsupported_rate", "eff.retrieval_ms",
        "eff.generation_ms",
    ]
    axes = {
        "overall": lambda r: "all",
        "domain": lambda r: r["slice.domain"],
        "repo": lambda r: r["slice.repo"],
        "category": lambda r: r["slice.category"],
        "difficulty": lambda r: r["slice.difficulty"],
        "split": lambda r: r["slice.split"],
    }
    summary = {"run_id": run_id, "split": split, "arms": {}}
    for arm in sorted({r["arm.arm"] for r in rows}):
        arows = [r for r in rows if r["arm.arm"] == arm]
        summary["arms"][arm] = {"n_rows": len(arows), "agg": {}}
        for axis, keyfn in axes.items():
            groups: dict[str, list[dict]] = collections.defaultdict(list)
            for row in arows:
                groups[str(keyfn(row))].append(row)
            summary["arms"][arm]["agg"][axis] = {}
            for val, grp in sorted(groups.items()):
                cell = {"n": len(grp)}
                for met in metrics:
                    vals = [g.get(met) for g in grp if isinstance(g.get(met), (int, float))]
                    cell[met] = round(sum(vals) / len(vals), 4) if vals else 0.0
                summary["arms"][arm]["agg"][axis][val] = cell
    path.write_text(json.dumps(summary, indent=2))


def cmd_generate(args) -> int:
    packs = [json.loads(line) for line in Path(args.packs).read_text(encoding="utf-8").splitlines()
             if line.strip()]
    if args.limit:
        packs = packs[: args.limit]
    answers_path = Path(args.answers)
    answers_path.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_existing_answers(answers_path) if args.resume else {}
    pending = [p for p in packs if p["pack_id"] not in existing]
    extra_body = json.loads(args.extra_body) if args.extra_body else None
    if args.no_think:
        extra_body = {**(extra_body or {}), "chat_template_kwargs": {"enable_thinking": False}}
    client = _client(args.base_url, args.api_key)
    print(f"packs={len(packs)} pending={len(pending)} model={args.model} workers={args.workers}")
    arm_suffix = "" if args.prompt_style == "citation" else f"+ans-{args.prompt_style}"

    mode = "a" if args.resume else "w"
    with answers_path.open(mode, encoding="utf-8") as fh:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {
                ex.submit(_gen_one, client, p, args.model, args.max_tokens, extra_body,
                          args.retries, args.prompt_style): p
                for p in pending
            }
            done = 0
            t0 = time.time()
            for fut in as_completed(futs):
                pack = futs[fut]
                gen = fut.result()
                score = score_answer(pack, gen["answer"])
                row = {
                    "pack_id": pack["pack_id"],
                    "answer": gen["answer"],
                    "error": gen["error"],
                    "gen_ms": gen["gen_ms"],
                    "score": score,
                }
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                existing[pack["pack_id"]] = row
                done += 1
                if done % 20 == 0:
                    rate = done / max(time.time() - t0, 1e-9)
                    print(f"  {done}/{len(pending)} generated ({rate:.2f}/s)")

    metric_rows = []
    for pack in packs:
        ans = existing.get(pack["pack_id"])
        if not ans:
            continue
        row = dict(pack["metric_row"])
        if arm_suffix:
            row["arm.arm"] = f"{row['arm.arm']}{arm_suffix}"
            row["arm.config_id"] = f"{row['arm.config_id']}{arm_suffix}"
        score = ans["score"]
        row.update({
            "gen.abstained": score["gen.abstained"],
            "gen.answer_len": score["gen.answer_len"],
            "ver.sentinel_contained": score["ver.sentinel_contained"],
            "ver.citation_support": score["ver.citation_support"],
            "ver.unsupported_rate": score["ver.unsupported_rate"],
            "eff.generation_ms": ans["gen_ms"],
        })
        metric_rows.append(row)

    metrics_path = Path(args.metrics)
    if metrics_path.exists():
        metrics_path.unlink()
    writer = MET.TsvWriter(metrics_path)
    for row in metric_rows:
        writer.row(**row)
    writer.close()
    _write_summary(metric_rows, Path(args.summary), args.tag, args.split)
    print(f"wrote {answers_path}")
    print(f"wrote {metrics_path}")
    print(f"wrote {args.summary}")
    return 0


def cmd_table(args) -> int:
    data = json.loads(Path(args.summary).read_text())
    cols = [
        ("nDCG", "ret.ndcg@10"), ("pMRR", "ret.primary_mrr"),
        ("packSent", "ret.sentinel_cov"), ("ansSent", "ver.sentinel_contained"),
        ("cite", "ver.citation_support"), ("abst", "gen.abstained"),
        ("ctxTok", "pack.context_tokens"), ("genMs", "eff.generation_ms"),
    ]
    print("| arm | n | " + " | ".join(h for h, _k in cols) + " |")
    print("| --- | --- | " + " | ".join(["---"] * len(cols)) + " |")
    for arm, info in data["arms"].items():
        cell = info["agg"]["overall"]["all"]
        vals = [f"{cell[k]:.3f}" if "Tok" not in h and "Ms" not in h else f"{cell[k]:.0f}"
                for h, k in cols]
        print(f"| {arm} | {cell['n']} | " + " | ".join(vals) + " |")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--split", default="all", choices=["all", "dev", "held-out"])
    common.add_argument("--repos", default="all")
    common.add_argument("--caveat-slice", action="store_true")
    common.add_argument("--query-id", action="append")
    common.add_argument("--limit", type=int)

    p = sub.add_parser("pack", parents=[common], help="retrieve and save source packs")
    p.add_argument("--config")
    p.add_argument("--arm")
    p.add_argument("--pack", action="append", help="ORDER:BUDGET, e.g. score:4000")
    p.add_argument("--depth", type=int, default=RB.DEFAULT_DEPTH)
    p.add_argument("--reindex", action="store_true")
    p.add_argument("--tag", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_pack)

    g = sub.add_parser("generate", help="generate answers and write metrics")
    g.add_argument("--packs", required=True)
    g.add_argument("--answers", required=True)
    g.add_argument("--metrics", required=True)
    g.add_argument("--summary", required=True)
    g.add_argument("--tag", required=True)
    g.add_argument("--split", default="all")
    g.add_argument("--model", required=True)
    g.add_argument("--base-url", required=True)
    g.add_argument("--api-key")
    g.add_argument("--workers", type=int, default=8)
    g.add_argument("--max-tokens", type=int, default=512)
    g.add_argument("--retries", type=int, default=4)
    g.add_argument("--extra-body")
    g.add_argument("--no-think", action="store_true")
    g.add_argument("--prompt-style", default="citation", choices=["citation", "extractive"])
    g.add_argument("--resume", action="store_true")
    g.add_argument("--limit", type=int)
    g.set_defaults(func=cmd_generate)

    t = sub.add_parser("table", help="print a compact summary table")
    t.add_argument("summary")
    t.set_defaults(func=cmd_table)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
