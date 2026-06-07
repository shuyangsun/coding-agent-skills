# LOOP — one round of the docs+rag harness

Mirrors `improving-vcs-skill/LOOP.md`, over the 2×2 factorial. Run rounds; keep
revisions that move the numbers; revert the rest. One small, attributable change
to **one** skill per round.

## Phase-0 quick start (no services, no LLM)

From this skill's directory (`SK=.agents/skills/improving-docs-and-rag-skills`),
with `H="${DOCS_RAG_HARNESS_DIR:-$TMPDIR/docs-rag-harness}"`:

```sh
# 1. Build + validate the gold set (the single source of truth).
python3 $SK/scripts/gold.py validate
python3 $SK/scripts/gold.py build --out "$H/gold-set"

# 2. Build the corpus axis: D (structured) and N (naive, de-structured).
python3 $SK/scripts/mk-corpus.py --out "$H/corpora"

# 3. Run all four factorial cells (corpus N|D × rag b|r), score each, log rows.
rm -f "$H/metrics.tsv"
for corpus in N D; do for tag in b r; do
  cfg=$SK/configs/$([ $tag = b ] && echo baseline-b || echo rag-r).json
  python3 $SK/scripts/docs-eval.py --corpus "$H/corpora/$corpus" --config "$cfg" \
      --out "$H/cell-$corpus$tag" --corpus-tag "$corpus"
  python3 $SK/scripts/check-retrieval.py --run "$H/cell-$corpus$tag/run.jsonl" \
      --corpus "$H/corpora/$corpus" --qrels-mode sentinel --tsv-out "$H/metrics.tsv" \
      --round "$ROUND" --corpus-tag "$corpus" --rag-tag "$tag" --rag-config-id "$(basename $cfg .json)"
done; done

# 4. Read the factorial: cell means, marginal effects, the interaction (coupling).
python3 $SK/scripts/scoreboard.py --tsv "$H/metrics.tsv" --metric recall@20
```

The retrieval half is **bit-reproducible** (deterministic chunking, stable-hash
embedding, stable sort); only the latency columns vary run-to-run.

## The round (general form, all three loops)

1. **Provision.** Build N/D corpora and baseline/skill rag configs; snapshot per
   (corpus × config); seed the WRITE convention trap (`new-corpus.sh`, future).
2. **Run the three loops** (blind sub-agents; see [SCENARIOS.md](SCENARIOS.md) and
   [MATRIX.md](MATRIX.md)):
   - **WRITE-docs** — agent with only `docs` authors into an empty `docs/` →
     `check-convention.sh` (`CONV_OK`, `WRITE_FINDABLE`).
   - **RAG-setup** — agent with only `rag`, blind to gold queries, emits
     `rag-config.json` → `check-rag-config.sh`.
   - **READ/eval** — blind consumer over each (corpus × rag) cell → the steps
     above feed the factorial.
3. **Score objectively** (`check-retrieval.py`, `check-convention.sh`,
   `check-rag-config.sh`); read tokens from transcripts via `_score.py` — never
   self-reported, never `budget.spent()`.
4. **Record + compare** (`record-metrics.sh`, `scoreboard.py`): recall@20, the two
   marginal effects, the interaction CI, factuality, latency, tokens — by round,
   tier×mode, difficulty×tier, and the factorial.
5. **Diagnose, then revise ONE skill.** Attribute via the factorial: if the `docs`
   marginal lags only under heading-aware chunking, the interaction tells you
   whether the lever is `docs` or `rag`.
6. **Re-run on fresh indexes.** Keep the change if its skill's marginal effect
   rises, quality holds across tiers/modes, **and** it does not degrade the other
   skill's marginal effect (coupling non-negative). Else revert. Noise → drop it
   and keep both skills smaller.
7. **Tear down** with `rm-corpus.sh` (guarded to `$DOCS_RAG_HARNESS_DIR`).

## Revise/revert discipline

- One attributable change to one skill per round; never both skills at once
  (the factorial only separates them if exactly one treatment definition moves).
- A `docs` change that raises `CONV_OK` but lowers recall is reverted.
- A `rag` change that raises recall but balloons latency/tokens at no factuality
  gain is reverted.
- A change that improves one skill's marginal effect but makes the **interaction**
  go negative is reverted.
- Clear the bar only on the **held-out** split (`--split held-out`); tune on
  `--split dev`. Report the dev↔held-out gap as an overfit signal.

See [METRICS.md](METRICS.md) for definitions and the exit bar.
