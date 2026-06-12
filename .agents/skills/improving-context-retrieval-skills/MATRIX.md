# MATRIX — what varies each round, and how it is sampled

The factorial has mandatory axes (always run) and sampled axes (rotated to bound
combinatorial blowup, plan §13). Phase-0 exercises the mandatory axes with no
services; the tier axes arrive with Phase-1's real providers.

## Mandatory axes (every round)

- **Floor first** — `Z` (empty corpus + `--no-retrieval`), the absolute "no doc,
  no RAG" baseline, run **before** the treatment cells every round. Scores 0 by
  construction; the four cells are reported as lifts above it.
- **Factorial cell** — `Nb`, `Nr`, `Db`, `Dr` (corpus N|D × rag b|r). All four,
  always — the interaction needs all four. Mapped to the named conditions:
  `Db` = docs-only, `Nr` = RAG-only, `Dr` = docs+RAG (`Nb` = neither-skill control).
- **Content type (domain)** — `nl` (natural-language docs incl. coding-session
  transcripts), `code` (the `inception/` app), and optional `image` (image-backed
  project context from the project passed with `--image-corpus`: code/docs/session
  history plus image summaries keyed to real image paths). Each runs against its
  own corpus and is reported with **separate metrics**, so image-backed/code/
  natural-language retrieval is compared (not averaged together).
- **Consumer mode** — `simple` (`retrieving-context`'s manual-structure navigation —
  ripgrep/file over `docs/`; a joint `updating-docs` × `retrieving-context` outcome)
  and `rag` (the consumer routed to the `setting-up-rag` pipeline; a joint outcome).
  A change that wins RAG but loses SIMPLE fails.
- **Difficulty** — `easy | medium | hard`; hard = multi-sentinel spanning distinct
  doc types. Reported as a difficulty×tier matrix.
- **Retrieval arm** — `plain` (no per-chunk contextualization; the noise-free
  cross-round comparison) and `full` (with contextualization; corroborating).

## Sampled axes (rotate per round; record what ran)

- **Embedding tier** — `large | mid | small` local embedders (Phase 1; e.g.
  `bge-large` / `nomic-embed-text` / a small `bge-small`). Phase-0 uses the
  deterministic hashed-embedding placeholder.
- **Generation tier** — `large | mid | small` local chat models (Phase 1, for the
  factuality/answer path). Phase-0 has no generation; `retrieval_hit` stands in.
- **Chunker** — at least `fixed` and `heading` exercised across rounds, since some
  structural gates only pay off under heading-aware chunking (the coupling).

Sampling discipline: never leave a mandatory axis out; rotate tier/chunker so
every combination is hit over a window of rounds, not every round. Name N (seeds)
and the paired test in the round notes.

## Seeds and distributions

Corpus `D` is LLM-authored and config `r` may use LLM contextualization, so each
(corpus × rag) cell is a **distribution**: author **N ≥ 5 seeds** per cell, report
median + IQR, gate on a paired sign/permutation test whose CI excludes zero across
consecutive rounds. Snapshot per-chunk contexts per (corpus-hash × rag-config-hash)
so identical re-runs reuse them.

## Reproducibility pins (Phase 1)

Pin model tags + quant + provider version + `temp 0` + seed + `num_ctx`; warm the
model; fix the host. Embeddings and reranker are deterministic forward passes, so
over a fixed (corpus, config) the retrieval half is bit-reproducible; only the
answer step carries residual variance (scored by containment, not a judge). Stamp
every TSV row with a `host_fingerprint`; `scoreboard.py` refuses cross-fingerprint
comparison. Local-first: the bar is met with Ollama + Qdrant; cloud parity is a
separately-gated later milestone.
