# LOOP — one round of the context-retrieval harness

Mirrors `improving-vcs-skill/LOOP.md`, over the 2×2 factorial. Run rounds; keep
revisions that move the numbers; revert the rest. One small, attributable change
to **one** skill per round (`updating-docs`, `setting-up-rag`, or
`retrieving-context`).

## Phase-0 quick start (no services, no LLM)

From the repo root (with `SK=.agents/skills/improving-context-retrieval-skills`,
`H="${CONTEXT_RETRIEVAL_HARNESS_DIR:-$TMPDIR/context-retrieval-harness}"`, and
optional `IMAGE_CORPUS` pointing at a project whose image assets should be
evaluated):

```sh
# 1. Build + validate the gold set (the single source of truth).
python3 $SK/scripts/check-vcs-boundary.py
if [ -n "${IMAGE_CORPUS:-}" ]; then
  python3 $SK/scripts/gold.py validate --image-corpus "$IMAGE_CORPUS"
  python3 $SK/scripts/gold.py build --out "$H/gold-set" --image-corpus "$IMAGE_CORPUS"
else
  python3 $SK/scripts/gold.py validate
  python3 $SK/scripts/gold.py build --out "$H/gold-set"
fi

# 2. Build the corpus axis: Z (empty baseline), N (naive), D (structured),
#    plus code/ and, when IMAGE_CORPUS is set, image/ snapshots.
if [ -n "${IMAGE_CORPUS:-}" ]; then
  python3 $SK/scripts/mk-corpus.py --out "$H/corpora" --image-corpus "$IMAGE_CORPUS"
else
  python3 $SK/scripts/mk-corpus.py --out "$H/corpora"
fi

# 3. FLOOR FIRST — the absolute "no doc, no RAG" baseline (empty corpus + no
#    retrieval). Every metric scores 0; the treatment cells are lifts above it.
rm -f "$H/metrics.tsv"
python3 $SK/scripts/docs-eval.py --corpus "$H/corpora/Z" --no-retrieval \
    --out "$H/cell-Z0" --corpus-tag Z
python3 $SK/scripts/check-retrieval.py --run "$H/cell-Z0/run.jsonl" \
    --corpus "$H/corpora/Z" --qrels-mode sentinel --tsv-out "$H/metrics.tsv" \
    --round "$ROUND" --corpus-tag Z --rag-tag 0 --rag-config-id none

# 4. Then the four NL treatment cells (corpus N|D × rag b|r): docs-only (Db),
#    RAG-only (Nr), docs+RAG (Dr), and the naive control (Nb). Score, log rows.
for corpus in N D; do for tag in b r; do
  cfg=$SK/configs/$([ $tag = b ] && echo baseline-b || echo rag-r).json
  python3 $SK/scripts/docs-eval.py --corpus "$H/corpora/$corpus" --config "$cfg" \
      --out "$H/cell-$corpus$tag" --corpus-tag "$corpus" --domain nl
  python3 $SK/scripts/check-retrieval.py --run "$H/cell-$corpus$tag/run.jsonl" \
      --corpus "$H/corpora/$corpus" --qrels-mode sentinel --tsv-out "$H/metrics.tsv" \
      --round "$ROUND" --corpus-tag "$corpus" --rag-tag "$tag" --rag-config-id "$(basename $cfg .json)" --domain nl
done; done

# 5. CODE content-type: index the inception/ snapshot under each rag config and
#    score the code gold queries — separate metrics, same eval path as NL.
for tag in b r; do
  cfg=$SK/configs/$([ $tag = b ] && echo baseline-b || echo rag-r).json
  python3 $SK/scripts/docs-eval.py --corpus "$H/corpora/code" --corpus-kind code \
      --config "$cfg" --out "$H/cell-code$tag" --corpus-tag code --domain code
  python3 $SK/scripts/check-retrieval.py --run "$H/cell-code$tag/run.jsonl" \
      --corpus "$H/corpora/code" --corpus-kind code --qrels-mode sentinel --tsv-out "$H/metrics.tsv" \
      --round "$ROUND" --corpus-tag code --rag-tag "$tag" --rag-config-id "$(basename $cfg .json)" --domain code
done

# 6. IMAGE content-type: index the image snapshot under each rag config and score
#    image gold queries. The docs-eval corpus contains summaries keyed to real
#    image paths; the snapshot keeps the actual image files available to inspect.
if [ -d "$H/corpora/image" ]; then
  for tag in b r; do
    cfg=$SK/configs/$([ $tag = b ] && echo baseline-b || echo rag-r).json
    python3 $SK/scripts/docs-eval.py --corpus "$H/corpora/image" --corpus-kind image \
        --config "$cfg" --out "$H/cell-image$tag" --corpus-tag image --domain image
    python3 $SK/scripts/check-retrieval.py --run "$H/cell-image$tag/run.jsonl" \
        --corpus "$H/corpora/image" --corpus-kind image --qrels-mode sentinel --tsv-out "$H/metrics.tsv" \
        --round "$ROUND" --corpus-tag image --rag-tag "$tag" --rag-config-id "$(basename $cfg .json)" --domain image
  done
fi

# 7. Read it: baseline-first lifts above the floor, the content-type comparison,
#    cell means, then the factorial (marginals + interaction/coupling).
python3 $SK/scripts/scoreboard.py --tsv "$H/metrics.tsv" --metric recall@20
```

The retrieval half is **bit-reproducible** (deterministic chunking, stable-hash
embedding, stable sort); only the latency columns vary run-to-run. The floor cell
is identically 0 by construction (no index, no retrieval).

## The round (general form, all three loops)

1. **Provision.** Build N/D corpora and baseline/skill rag configs; snapshot per
   (corpus × config); seed the WRITE convention trap (`new-corpus.sh`, future).
2. **Run the three loops** (blind sub-agents; see [SCENARIOS.md](SCENARIOS.md) and
   [MATRIX.md](MATRIX.md)):
   - **WRITE-docs** — agent with only `updating-docs` authors into an empty `docs/`
     → `check-convention.sh` (`CONV_OK`, `WRITE_FINDABLE`).
   - **RAG-setup** — agent with only `setting-up-rag`, blind to gold queries, emits
     `rag-config.json` → `check-rag-config.sh`.
   - **READ/eval** — blind consumer with only `retrieving-context` over each
     (corpus × rag) cell, in each mode → the steps above feed the factorial and the
     consumer plane.
3. **Score objectively** (`check-vcs-boundary.py`, `check-retrieval.py`,
   `check-convention.sh`, `check-rag-config.sh`); read tokens from transcripts via
   `_score.py` — never self-reported, never `budget.spent()`.
4. **Record + compare** (`record-metrics.sh`, `scoreboard.py`): recall@20, the two
   marginal effects, the interaction CI, factuality, latency, tokens — by round,
   tier×mode, difficulty×tier, and the factorial.
5. **Diagnose, then revise ONE skill.** Attribute via the factorial: if the
   `updating-docs` marginal lags only under heading-aware chunking, the interaction
   tells you whether the lever is `updating-docs` or `setting-up-rag`; a gap between
   SIMPLE and RAG outcomes points at `retrieving-context`.
6. **Re-run on fresh indexes.** Keep the change if its skill's marginal effect
   rises, quality holds across tiers/modes, **and** it does not degrade another
   skill's marginal effect (coupling non-negative). Else revert. Noise → drop it
   and keep all three skills smaller.
7. **Tear down** with `rm-corpus.sh` (guarded to `$CONTEXT_RETRIEVAL_HARNESS_DIR`).

## Revise/revert discipline

- One attributable change to one skill per round; never two skills at once
  (the factorial only separates them if exactly one treatment definition moves).
- An `updating-docs` change that raises `CONV_OK` but lowers recall is reverted.
- A `setting-up-rag` change that raises recall but balloons latency/tokens at no
  factuality gain is reverted.
- A `retrieving-context` change that wins one consumer mode but regresses the other
  is reverted.
- A change that improves one skill's marginal effect but makes the **interaction**
  go negative is reverted.
- Clear the bar only on the **held-out** split (`--split held-out`); tune on
  `--split dev`. Report the dev↔held-out gap as an overfit signal.

See [METRICS.md](METRICS.md) for definitions and the exit bar.
