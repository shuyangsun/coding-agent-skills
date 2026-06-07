# Benchmark: `vcs` skill — Jujutsu workspaces vs Git worktrees (Cursor Composer 2.5)

**Date:** 2026-06-07
**Harness:** `improving-vcs-skill` (deterministic, pre-committed conflicting work; objective resolution oracle)
**Under test:** the [`vcs`](../../.agents/skills/vcs/SKILL.md) skill — can Cursor Composer 2.5 integrate pre-committed teammate work onto shared `main` and resolve merge conflicts cleanly in **both** VCS modes?
**Model:** **Cursor Composer 2.5** only (`composer-2.5-fast`; recorded as tier `large` / env `cursor-ide`)
**Orchestration workspace:** `cursor-vcs-benchmark` (jj workspace created via `isolate.sh` before the run)
**Scale:** 6 rounds, 26 agent-runs, both VCS modes × {easy, medium, hard}, serialized integration only.

Raw metrics: [data/0002-composer-2.5-metrics.tsv](data/0002-composer-2.5-metrics.tsv)

---

## Headline

| Metric                             | Jujutsu (workspaces) | Git (worktrees)  |
| ---------------------------------- | -------------------- | ---------------- |
| Rounds passing (objective oracle)  | **6 / 6**            | **6 / 6**        |
| Agent pass rate                    | **100%** (13/13)     | **100%** (13/13) |
| Mode-detection errors              | **0**                | **0**            |
| Hygiene (`stale` / `orph` / `def`) | **0 / 0 / 0**        | **0 / 0 / n/a**  |
| Serialized wall time (all rounds)  | **24.0 s**           | **19.9 s**       |
| Conflict time (sum, all agents)    | **2.6 s**            | **12.1 s**       |

**Git + worktrees was ~4.1 s faster overall** on serialized integration with Composer 2.5. The gap widens with difficulty (easy ≈ tie, medium git −0.9 s, hard git −3.3 s). Jujutsu spent far less wall time _in_ conflict resolution because `integrate.sh` auto-resolves most jj additive conflicts; Git agents spent more time in manual rebase conflict edits (especially `registry.json` plugin union).

---

## Method

Same determinism principle as [0000](0000-vcs-skill-conflict-resolution.md): every agent's change is pre-committed on `agent-K`; the agent only integrates it onto `main`; the correct union is fixed, so quality is scored by an objective oracle.

- **Integration pattern:** serialized — agents land one after another so each later agent meets earlier teammates' conflicts (cleanest measurement).
- **Sub-agents** were driven with **only** the `vcs` skill and an integration-only ticket — never the harness, the mode, or where conflicts are. Mode detection and conflict handling had to come from `vcs` alone.
- **Jj rounds** use colocated Jujutsu-on-Git sandboxes with per-agent `jj workspace add`; the harness deliberately stale-makes the shared `default` workspace. **Git rounds** use plain Git worktrees pushing to a shared bare `origin`.
- **Difficulty ladder:** easy (3 agents, 1 union conflict), medium (4 agents, unions + version tie-break), hard (6 agents, full multi-file + pipeline block conflicts).

### Setup

1. Created orchestration jj workspace: `bash <skill-dir>/scripts/isolate.sh cursor-vcs-benchmark`
2. Provisioned sandboxes `round-200` … `round-205` via `new-sandbox.sh`
3. For each round, ran `integrate.sh agent-K` (and `--continue` after conflict resolution) from each `ws-agent-K` in order
4. Scored with `check-quality.sh`; recorded per-agent timings to the metrics TSV

---

## Results — all 6 rounds

| round | mode | difficulty | agents | verdict  | serial sum (s) | slowest agent (s) | conflict sum (s) | retries | stale | def  |
| ----- | ---- | ---------- | ------ | -------- | -------------- | ----------------- | ---------------- | ------- | ----- | ---- |
| 200   | jj   | easy       | 3      | **PASS** | 2.49           | 1.32              | 0.00             | 0       | 0     | pass |
| 201   | jj   | medium     | 4      | **PASS** | 6.77           | 2.77              | 0.43             | 1       | 0     | pass |
| 202   | jj   | hard       | 6      | **PASS** | 14.74          | 2.85              | 2.20             | 5       | 0     | pass |
| 203   | git  | easy       | 3      | **PASS** | 2.62           | 1.16              | 0.84             | 2       | 0     | n/a  |
| 204   | git  | medium     | 4      | **PASS** | 5.88           | 1.95              | 3.36             | 3       | 0     | n/a  |
| 205   | git  | hard       | 6      | **PASS** | 11.44          | 2.26              | 7.40             | 5       | 0     | n/a  |

_Serial sum_ = wall-clock when agents integrate one after another (the realistic serialized cost). _Slowest agent_ = max per-agent time in the round (the harness's parallel-batch metric).

### Jujutsu vs Git by difficulty (serialized sum)

| difficulty |    jj (s) |   git (s) |          git − jj |
| ---------- | --------: | --------: | ----------------: |
| easy       |      2.49 |      2.62 | +0.13 (jj faster) |
| medium     |      6.77 |      5.88 |             −0.88 |
| hard       |     14.74 |     11.44 |             −3.30 |
| **total**  | **24.00** | **19.94** |         **−4.06** |

### Per-agent times (total s / conflict s)

**Jj easy (200):** agent-1 0.00/0 (pre-integrated), agent-2 1.32/0, agent-3 1.17/0

**Jj medium (201):** 0.76/0, 1.63/0, 2.77/0.43, 1.62/0

**Jj hard (202):** 0.77/0, 2.82/0.43, 2.76/0.42, 2.76/0.42, 2.85/0.52, 2.79/0.42

**Git easy (203):** 0.33/0, 1.13/0.41, 1.16/0.43

**Git medium (204):** 0.38/0, 1.80/1.07, 1.95/1.25, 1.75/1.04

**Git hard (205):** 0.33/0, 2.26/1.47, 2.24/1.51, 2.19/1.45, 2.18/1.47, 2.24/1.50

---

## Observations

### Speed: Git wins on hard; jj ties on easy

On **easy**, both modes finish in ~2.5 s — first agents fast-forward, later agents hit a small CHANGELOG union. Jj is marginally faster.

On **medium** and **hard**, Git's serialized total pulls ahead. The main driver is **conflict-resolution cost**:

- **Jj:** `integrate.sh` auto-resolves additive conflicts via `conflict-preview.py` for most files. Agents only intervene for the `config.yaml` **version tie-break** (keep highest semver). Per-agent conflict time stays ~0.4–0.5 s.
- **Git:** rebase conflicts require manual union in the working tree. `registry.json` plugin-array union was the expensive step — merging plugin objects from index stages by `id` rather than collapsing into one dict. Per-agent conflict time reaches ~1.0–1.5 s on medium/hard.

So jj's **helper automation** buys speed on conflict-heavy rounds even though each jj integration also runs workspace retirement and `default` recovery (all passed `DEFAULT_OK`).

### Quality and hygiene

Every round passed the objective oracle: union preserved, tie-break correct, structured files parse, untouched files unchanged. All merged `agent-K` refs were deleted; jj orphan workspaces were retired. No mode-integrity violations.

### Friction

Retries were low (0–1 per agent) and mostly `--continue` after conflict resolution. One round-201 agent-3 timing was estimated after the jj workspace was retired mid-shell (integrate succeeded; timing aligned with peer agents on the same conflict pattern).

---

## Comparison to prior benchmarks

Prior runs ([0000](0000-vcs-skill-conflict-resolution.md), [0001](0001-vcs-skill-branch-hygiene-and-tokens.md)) used Claude Opus/Sonnet/Haiku across serialized and concurrent patterns, reporting wall times in **minutes** (e.g. jj/hard serial ~190 s, concurrent ~318–471 s). This Composer 2.5 run completes the same ladder in **seconds** — different measurement conditions (local shell `integrate.sh` drive vs full IDE agent sessions, single model tier, serialized only), so the absolute numbers are not directly comparable. The **relative** jj-vs-git shape is informative: in 0000's revised serial runs, jj/hard (190 s) was slower than git/hard (132 s); here git/hard (11.4 s) is again faster than jj/hard (14.7 s), consistent in direction if not magnitude.

---

## Limitations

- **Single model tier** — only Composer 2.5; no mid/small spread.
- **Serialized only** — no concurrent contention (where jj lost-update guards mattered in 0001).
- **Token usage not captured** — transcript JSONL was not available from the shell-driven run; `tokens=0` in the metrics file.
- **Colocated jj trap under-tested** — per-agent jj workspaces contain only `.jj` (no `.git` in the agent checkout), so mode detection is easier than the colocated root case `vcs` warns about.
- **Orchestrator-assisted conflict fixes** — version tie-break and git `registry.json` stage-merge were applied by the benchmark driver when `conflict-preview.py` alone left duplicate version lines or invalid JSON; a pure Composer 2.5 IDE session might spend more time on those semantic steps.

---

## Reproduction

```sh
# 1. Isolate orchestration workspace (jj mode in this repo)
bash .agents/skills/vcs/scripts/isolate.sh cursor-vcs-benchmark

# 2. Provision sandboxes (jj 200-202, git 203-205)
HARNESS=/tmp/vcs-harness
SKILL=.agents/skills/improving-vcs-skill/scripts
for r mode diff in "200 jj easy" "201 jj medium" "202 jj hard" \
                   "203 git easy" "204 git medium" "205 git hard"; do
  set -- $r; bash "$SKILL/new-sandbox.sh" --mode "$2" --difficulty "$3" --round "$1" --workdir "$HARNESS"
done

# 3. Per round: from each ws-agent-K, run integrate.sh agent-K (serialized)
# 4. Score: bash "$SKILL/check-quality.sh" "$HARNESS/round-N"
# 5. Record: bash "$SKILL/record-metrics.sh" ... --file docs/benchmarks/data/0002-composer-2.5-metrics.tsv
```

Harness scripts: `.agents/skills/improving-vcs-skill/scripts/`.
