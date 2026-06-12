# RAG eval set — `coding-agent-skills`

- **Repo root:** `/Users/shuyang/developer/coding-agent-skills`
- **Questions:** 45 · domain {'code': 25, 'nl': 20} · difficulty {'easy': 5, 'hard': 12, 'medium': 28} · source {'claude': 31, 'codex': 14}
- **Code corpus (`domain=code`):** inception/ (TanStack Start app), .agents/skills/\*/scripts/ (Python+shell harness), scripts/
- **Prose corpus (`domain=nl`):** docs/transcripts/ (exported transcripts), docs/{benchmarks,issues,plans,prompts,research}
- **Note:** Has both source/harness code and exported session transcripts, so the set splits codebase vs prompting/session-history.

Each entry is a gold fact for retrieval eval: a paraphrased **Q** (never containing its own sentinel), the grounded **A**, the exact **sentinels** that occur verbatim in the **primary** file(s), and the `domain`/`difficulty` slice. Sources/paths are relative to the repo root above. Every sentinel below was re-verified against the primary file's raw bytes at build time.

## `domain = code` (25)

### cas-inception-react-compiler-babel-preset

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** In the inception web app's Vite config, how is React's automatic memoization (the React Compiler) turned on at build time — which Babel-style plugin is loaded and what preset is fed to it?
- **A:** vite.config.ts loads the `babel` plugin from `@rolldown/plugin-babel` and passes it `{ presets: [reactCompilerPreset()] }`, where `reactCompilerPreset` is imported from `@vitejs/plugin-react`, so the React Compiler runs over the sources during the build.
- **sentinels:** `@rolldown/plugin-babel`, `reactCompilerPreset`
- **primary:** `inception/vite.config.ts`
- **evidence:** inception/vite.config.ts:7: import babel from "@rolldown/plugin-babel"; \| :6: import viteReact, { reactCompilerPreset } from "@vitejs/plugin-react"; \| :17: babel({ presets: [reactCompilerPreset()] }),

### cas-inception-router-preload-intent

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** How does the inception app's TanStack router decide when to prefetch a route's code/data ahead of navigation, and how long does it consider that preloaded data fresh?
- **A:** getRouter() in src/router.tsx sets `defaultPreload: "intent"` so routes are prefetched on hover/touch intent, and `defaultPreloadStaleTime: 0` so the preloaded data is treated as immediately stale (re-fetched on actual navigation).
- **sentinels:** `defaultPreload: "intent"`, `defaultPreloadStaleTime`
- **primary:** `inception/src/router.tsx`
- **evidence:** inception/src/router.tsx:8: defaultPreload: "intent", \| :9: defaultPreloadStaleTime: 0,

### cas-inception-typecheck-tsgo

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** What command does the inception package run for type-checking, and which non-tsc TypeScript compiler binary does that rely on as a dev dependency?
- **A:** The `typecheck` script runs `tsgo --noEmit`, and that binary comes from the `@typescript/native-preview` dev dependency (the experimental native-Go TypeScript compiler), not plain tsc.
- **sentinels:** `tsgo --noEmit`, `@typescript/native-preview`
- **primary:** `inception/package.json`
- **evidence:** inception/package.json:14: "typecheck": "tsgo --noEmit" \| :42: "@typescript/native-preview": "latest",

### cas-snowflake-bit-layout-epoch

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** In the RAG point-id generator, how many bits are reserved for the node id versus the per-millisecond sequence, and what calendar date is the timestamp epoch pinned to?
- **A:** snowflake.py lays out the id with NODE_BITS = 10 and SEQ_BITS = 12, and pins the epoch via EPOCH_MS to datetime(2026, 6, 8, tzinfo=timezone.utc), so 10 bits identify the node and 12 bits disambiguate ids minted in the same millisecond.
- **sentinels:** `NODE_BITS = 10`, `SEQ_BITS = 12`, `datetime(2026, 6, 8, tzinfo=timezone.utc)`
- **primary:** `.agents/skills/setting-up-rag/scripts/snowflake.py`
- **evidence:** .agents/skills/setting-up-rag/scripts/snowflake.py:28: NODE_BITS = 10 \| :29: SEQ_BITS = 12 \| :26: EPOCH_MS = int(datetime(2026, 6, 8, tzinfo=timezone.utc).timestamp() \* 1000)

### cas-index-reindex-delete-by-docid

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** Because the RAG indexer mints fresh time-based point ids on every run, what does it do when re-indexing into an already-existing collection to avoid piling up duplicate chunks of the same document?
- **A:** When the collection already exists, index.py first deletes each doc's prior points with a `models.FilterSelector` whose filter matches `doc_id` via `models.MatchAny(any=doc_ids)`, so re-indexing a changed/added doc replaces rather than appends duplicate Snowflake-id'd chunks.
- **sentinels:** `FilterSelector`, `MatchAny`
- **primary:** `.agents/skills/setting-up-rag/scripts/index.py`
- **evidence:** .agents/skills/setting-up-rag/scripts/index.py:86: client.delete(coll, points_selector=models.FilterSelector(filter=models.Filter( \| :87: must=[models.FieldCondition(key="doc_id", match=models.MatchAny(any=doc_ids))]

### cas-index-bm25-idf-modifier

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** When building the sparse vector configuration for the Qdrant collection, how does the indexer decide whether to ask the server to apply inverse-document-frequency weighting, and for which sparse models does it do so?
- **A:** sparse_modifier() in index.py returns `models.Modifier.IDF` when the sparse model name contains "bm25" or "bm42" (raw term-frequency emitters whose IDF Qdrant applies server-side) and returns None for learned sparse models like SPLADE that already encode weighting.
- **sentinels:** `models.Modifier.IDF`, `sparse_modifier`
- **primary:** `.agents/skills/setting-up-rag/scripts/index.py`
- **evidence:** .agents/skills/setting-up-rag/scripts/index.py:31: return models.Modifier.IDF \| :26: def sparse_modifier(model: str):

### cas-query-hybrid-fusion-default

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** In the RAG query pipeline, what two fusion strategies can combine the dense and sparse prefetch rank lists, and which one is used unless the config explicitly requests the score-based alternative?
- **A:** retrieve() in query.py builds a `models.FusionQuery` that uses `models.Fusion.DBSF` only when the hybrid config's fusion is "dbsf", otherwise defaulting to `models.Fusion.RRF` (reciprocal rank fusion) over the dense and sparse prefetches.
- **sentinels:** `models.Fusion.DBSF`, `FusionQuery`
- **primary:** `.agents/skills/setting-up-rag/scripts/query.py`
- **evidence:** .agents/skills/setting-up-rag/scripts/query.py:33: fusion = models.Fusion.DBSF if cfg.get("hybrid", {}).get("fusion") == "dbsf" else models.Fusion.RRF \| :41: query=models.FusionQuery(fusion=fusion),

### cas-ragconfig-default-models

- **slice:** codebase · **difficulty:** easy · **source:** claude
- **Q:** What are the default dense embedding model and the cross-encoder reranking model named in the setting-up-rag skill's shipped retrieval config file?
- **A:** rag-config.json sets the default dense model to `BAAI/bge-small-en-v1.5` (384-dim, cosine) and the rerank cross-encoder to `Xenova/ms-marco-MiniLM-L-6-v2`, with bm25 as the sparse arm.
- **sentinels:** `BAAI/bge-small-en-v1.5`, `Xenova/ms-marco-MiniLM-L-6-v2`
- **primary:** `.agents/skills/setting-up-rag/scripts/rag-config.json`
- **evidence:** .agents/skills/setting-up-rag/scripts/rag-config.json:6: "dense_model": "BAAI/bge-small-en-v1.5", \| :29: "model": "Xenova/ms-marco-MiniLM-L-6-v2",

### cas-ragclient-embedded-singlewriter

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** When the RAG helper falls back to Qdrant's embedded on-disk mode and the store directory is already locked by another process, what does it do, and why can only one process use that store at a time?
- **A:** get_client() in rag_lib.py catches the RuntimeError, and if the message contains "already accessed" or "lock" it exits with an error explaining that embedded mode is single-writer (it takes an exclusive lock on the dir), suggesting the caller wait or run a Qdrant server via QDRANT_URL for concurrent access.
- **sentinels:** `single-writer`, `already accessed`
- **primary:** `.agents/skills/setting-up-rag/scripts/rag_lib.py`
- **evidence:** .agents/skills/setting-up-rag/scripts/rag_lib.py:293: # Embedded mode is single-writer: it takes an exclusive lock on the dir. \| :295: if "already accessed" in msg or "lock" in msg:

### cas-ragserver-healthz-probe

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** How does the RAG library probe whether a Qdrant server is reachable before deciding to use it instead of embedded mode, and why does it check more than one HTTP endpoint?
- **A:** server_up() in rag_lib.py probes both `/healthz` (current builds) and `/` (returns version JSON on every build, since older Qdrant lacks /healthz), returning True on the first endpoint that responds 200, so it never declares the server down just because /healthz is missing.
- **sentinels:** `/healthz`
- **primary:** `.agents/skills/setting-up-rag/scripts/rag_lib.py`
- **evidence:** .agents/skills/setting-up-rag/scripts/rag_lib.py:268-270: /healthz on current builds; / returns version JSON on every build (older Qdrant lacks /healthz) ... for ep in ("/healthz", "/"):

### cas-docseval-hashed-embedding-bm25

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** In the Phase-0 in-process retrieval eval, what fixed BM25 parameters does it use, and how does it produce its deterministic placeholder dense vectors instead of using a learned embedding model?
- **A:** docs-eval.py pins BM25_K1 = 1.5 and BM25_B = 0.75 for its sparse scorer, and builds dense vectors by hashing each token into a fixed-dimension bucket with `zlib.crc32(t.encode()) % self.dim` (a stable per-process hash), giving a deterministic hashed-lexical embedding rather than a semantic model.
- **sentinels:** `BM25_K1 = 1.5`, `BM25_B = 0.75`, `zlib.crc32`
- **primary:** `.agents/skills/improving-context-retrieval-skills/scripts/docs-eval.py`
- **evidence:** .agents/skills/improving-context-retrieval-skills/scripts/docs-eval.py:63: BM25_K1 = 1.5 \| :64: BM25_B = 0.75 \| :172: vec[zlib.crc32(t.encode()) % self.dim] += w

### cas-gold-noncircularity-firewall

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** In the gold-set harness, what numeric threshold caps how lexically similar a generated query may be to its primary document, and how is each query deterministically assigned to the dev versus held-out split?
- **A:** gold.py enforces a non-circularity firewall with LEXICAL_OVERLAP_MAX = 0.30 (max token-trigram Jaccard of query vs primary doc) and partitions via split_of(), which sha256-hashes the query id and returns "held-out" if h % 2 else "dev" (even=dev, odd=held-out).
- **sentinels:** `LEXICAL_OVERLAP_MAX = 0.30`, `split_of`
- **primary:** `.agents/skills/improving-context-retrieval-skills/scripts/gold.py`
- **evidence:** .agents/skills/improving-context-retrieval-skills/scripts/gold.py:57: LEXICAL_OVERLAP_MAX = 0.30 \| :396-398: def split_of(query_id): h = int(hashlib.sha256(query_id.encode()).hexdigest(),16); return "held-out" if h % 2 else "dev"

### cas-gold-qrels-pinned-vs-sentinel

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** The gold-set qrels builder supports two grading modes; in the per-corpus sentinel mode, what determines whether a document gets the highest relevance grade versus a lower corroborating grade?
- **A:** In build_qrels with the "sentinel" mode, a doc containing all of a fact's sentinels gets grade 2 while one containing some but not all gets grade 1 (`rel[doc_id] = 2 if present == n else 1`); the default "pinned" mode instead grades the hand-pinned primary paths as 2 and any other sentinel-bearing doc as 1.
- **sentinels:** `present == n else 1`, `mode: str = "pinned"`
- **primary:** `.agents/skills/improving-context-retrieval-skills/scripts/gold.py`
- **evidence:** .agents/skills/improving-context-retrieval-skills/scripts/gold.py:389: rel[doc_id] = 2 if present == n else 1 \| :358: facts: list[Fact], docs: dict[str, str], mode: str = "pinned" \| :375-382: pinned mode sets primary p -> 2, other sentinel-bearing -> 1

### cas-scoreboard-bootstrap-coupling

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** How does the harness scoreboard estimate uncertainty on its 2x2 factorial effects reproducibly, and which term captures whether co-designing the docs and RAG skills beats simply adding their separate effects?
- **A:** scoreboard.py uses a seeded bootstrap (BOOTSTRAP_SEED = 12345, B=2000) for its 90% CIs, and reports the coupling/interaction term computed per query as (Dr−Db) − (Nr−Nb), which is positive when co-design beats the additive expectation.
- **sentinels:** `BOOTSTRAP_SEED = 12345`, `coupling/interaction`
- **primary:** `.agents/skills/improving-context-retrieval-skills/scripts/scoreboard.py`
- **evidence:** .agents/skills/improving-context-retrieval-skills/scripts/scoreboard.py:53: BOOTSTRAP_SEED = 12345 \| :222: print(fmt_effect("coupling/interaction (×)", inter))

### cas-mkcorpus-naive-destructure

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** When the corpus builder generates the 'naive' variant of the docs to isolate the structure signal, what two structural elements does it strip from each document, and how does it name the resulting per-doc files?
- **A:** naive_text() in mk-corpus.py drops YAML front-matter and demotes Markdown heading markers to plain lines (preserving content/sentinels byte-for-byte otherwise), and in perdoc mode writes each result under an opaque filename `n-{i + 1:04d}.md`.
- **sentinels:** `naive_text`, `n-{i + 1:04d}.md`
- **primary:** `.agents/skills/improving-context-retrieval-skills/scripts/mk-corpus.py`
- **evidence:** .agents/skills/improving-context-retrieval-skills/scripts/mk-corpus.py:51: def naive_text(text: str) -> str: \| :85: (n_root / f"n-{i + 1:04d}.md").write_text(naive_text(text), encoding="utf-8")

### cas-jsonmerge-keyed-by-id-arrays

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** The conflicted-JSON merge helper treats certain arrays specially rather than as opaque sets; what condition makes it merge an array element-by-element using a key, and where does it read the three sides of the conflict from?
- **A:** json-union-merge.py reads base/ours/theirs blobs from the Git index via git_stage() (running `git show :<stage>:<path>`), and merges an array as a keyed collection when keyed_by_id() reports every element is a dict containing an "id" field, merging items by that id instead of unioning whole values.
- **sentinels:** `keyed_by_id`, `git_stage`
- **primary:** `.agents/skills/vcs/scripts/json-union-merge.py`
- **evidence:** .agents/skills/vcs/scripts/json-union-merge.py:99-101: def keyed_by_id(items): ... all(isinstance(item, dict) and "id" in item ...) \| :26-28: def git_stage(stage, path): subprocess.run(["git","show",f":{stage}:{path}"]...)

### cas-scalarmerge-version-winner

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** The single-purpose version-conflict resolver only handles one narrow conflict shape; what must both sides of a conflict block look like for it to resolve, and which value does it keep?
- **A:** scalar-version-merge.py only resolves a block where each side is exactly one line assigning the same key, same indentation, to a dotted-numeric value (matched by its ASSIGNMENT regex); it keeps the higher version, choosing `winner = left_value if version_tuple(left_value) >= version_tuple(right_value) else right_value`.
- **sentinels:** `winner = left_value`, `version_tuple`
- **primary:** `.agents/skills/vcs/scripts/scalar-version-merge.py`
- **evidence:** .agents/skills/vcs/scripts/scalar-version-merge.py:50: winner = left_value if version_tuple(left_value) >= version_tuple(right_value) else right_value \| :32: def version_tuple(value): \| :37-46: one line per side, same key, same indentation, ASSIGNMENT regex requires dotted-numeric value

### cas-conflict-preview-jj-bullet-rule

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** The conflict-preview tool strips merge markers to show a clean version; how does it avoid mistakenly deleting Markdown bullet lines when handling jj-style diff conflicts that mark removed base lines with a leading dash?
- **A:** preview_line() in conflict-preview.py drops a line starting with "-" only when it is NOT followed by a space (`line.startswith("-") and not line.startswith("- ")`), so Markdown bullets like "- item" are kept while compact removals like "-version: 1.4.0" are dropped; explicit marker lines are dropped via MARKER_PREFIXES.
- **sentinels:** `not line.startswith("- ")`, `MARKER_PREFIXES`
- **primary:** `.agents/skills/vcs/scripts/conflict-preview.py`
- **evidence:** .agents/skills/vcs/scripts/conflict-preview.py:32: if line.startswith("-") and not line.startswith("- "): \| :14: MARKER_PREFIXES = ( \| :26: if line.startswith(MARKER_PREFIXES):

### cas-lefthook-sequential-stagefixed

- **slice:** codebase · **difficulty:** easy · **source:** claude
- **Q:** In the repo's pre-commit hook config, why are the formatting/lint jobs run one at a time rather than concurrently, and how do Prettier/oxlint fixes make it back into the commit?
- **A:** lefthook.yml sets `parallel: false` so two tools never write the same staged file at once, and each job sets `stage_fixed: true` so any auto-fixes Prettier or oxlint apply are re-staged into the commit.
- **sentinels:** `parallel: false`, `stage_fixed: true`
- **primary:** `lefthook.yml`
- **evidence:** lefthook.yml:22: parallel: false \| :27: stage_fixed: true (also 31/35/39)

### cas-oxlint-ignore-generated-routetree

- **slice:** codebase · **difficulty:** easy · **source:** claude
- **Q:** Which generated file(s) does the repo's oxlint configuration exclude from linting, and what rule category is escalated to error?
- **A:** The .oxlintrc.json escalates the `correctness` category to "error" and sets ignorePatterns to skip `**/routeTree.gen.ts` and `**/*.gen.ts`, so the TanStack-generated route tree is never linted.
- **sentinels:** `routeTree.gen.ts`, `"correctness": "error"`
- **primary:** `.oxlintrc.json`
- **evidence:** .oxlintrc.json:16: "ignorePatterns": ["**/routeTree.gen.ts", "**/*.gen.ts"] \| :9: "correctness": "error"

### cas-cx-reindex-removed-doc-recreate-caveat

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** The RAG indexer deletes a document's prior points before re-inserting so that an edited or added doc replaces rather than duplicates its chunks. What case does that per-doc delete NOT handle, and what flag must the operator pass instead?
- **A:** The delete-before-insert only covers docs that still exist in the new run; a document that has been fully removed from the corpus leaves orphaned points behind, so the operator must drop and rebuild the collection by passing the recreate flag.
- **sentinels:** `--recreate`, `Fully *removed* docs still need a`
- **primary:** `.agents/skills/setting-up-rag/scripts/index.py`
- **evidence:** setting-up-rag/scripts/index.py:84: replaces rather than duplicates. (Fully _removed_ docs still need a \| :10: [--config rag-config.json] [--recreate] \| :41: --recreate ... drop the collection first

### cas-cx-rag-corpus-loader-vcs-boundary-pruning

- **slice:** codebase · **difficulty:** hard · **source:** codex
- **Q:** When the RAG corpus loader walks a directory tree, how does it avoid pulling a nested Git worktree or Jujutsu workspace into the parent repo's index, while still allowing such a workspace to be indexed when it is itself the chosen corpus root?
- **A:** The loader treats .git and .jj as version-control boundary markers (a helper checks each directory for them) and, during the os.walk, prunes any directory strictly below the corpus root that is such a root; the corpus root itself is exempt, so directly indexing a worktree/workspace still works. It also skips dependency/build directories.
- **sentinels:** `VCS_BOUNDARY_MARKERS`, `_is_vcs_root`, `SKIP_DIRS`
- **primary:** `.agents/skills/setting-up-rag/scripts/rag_lib.py`
- **evidence:** setting-up-rag/scripts/rag_lib.py:51: VCS_BOUNDARY_MARKERS = (".git", ".jj") \| :54: def \_is_vcs_root(path: Path) -> bool: \| :48: SKIP_DIRS = {"node_modules", ...} \| :76: if current != base and \_is_vcs_root(current): dirnames[:] = []

### cas-cx-markdown-chunk-minwords-floor-25x

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** The setting-up-rag chunker merges consecutive tiny Markdown sections up to a word-count floor instead of emitting a chunk per heading. What is the default value of that floor, and what reduction in chunk count did this repo's docs see at equal recall once it was applied?
- **A:** The Markdown chunker merges tiny adjacent heading sections up to the floor (default 80 words) so a heading-dense doc does not explode into one-line chunks; on this repo's docs the floor cut the chunk count roughly 2.5x (from 2729 down to 1092) while holding recall, giving fewer, denser, better-separated vectors.
- **sentinels:** `min_words`, `2729 → 1092`, `chunk_markdown`
- **primary:** `.agents/skills/setting-up-rag/CHUNKING.md`, `.agents/skills/setting-up-rag/scripts/rag_lib.py`
- **evidence:** setting-up-rag/CHUNKING.md:15: Merge tiny adjacent sections up to `min_words` (default 80). \| :19: the floor cut chunk count ≈2.5× (2729 → 1092) at equal recall \| rag_lib.py:132: def chunk_markdown(text, size, overlap, min_words)

### cas-cx-gold-corpus-exclude-globs-overview

- **slice:** codebase · **difficulty:** hard · **source:** codex
- **Q:** Beyond rejecting self-echoing queries, the gold-set builder drops certain documents from every corpus snapshot so they cannot be scored. Which kinds of documents are excluded, and notably which per-directory index files are removed everywhere?
- **A:** The gold builder removes leakage-prone docs from each corpus snapshot via a glob list: the harness's own design plan and the sessions that produced it, the benchmark reports that quote gold sentinels, and crucially every per-directory and top-level OVERVIEW.md (matched by both a bare and a nested glob), since those summaries restate answers and would inflate sentinel-mode qrels.
- **sentinels:** `EXCLUDE_GLOBS`, `*/OVERVIEW.md`
- **primary:** `.agents/skills/improving-context-retrieval-skills/scripts/gold.py`
- **evidence:** gold.py:75: EXCLUDE_GLOBS = [ \| :89: "OVERVIEW.md", \| :90: "\*/OVERVIEW.md", \| :62-69: excluded: this harness's own plan + the session + the benchmark reports ... OVERVIEW.md globs enforce the firewall

### cas-cx-checkretrieval-domain-corpuskind-guard

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** The Phase-0 retrieval scorer separates code from natural-language runs. What does it require about the relationship between the run's domain selector and its corpus-kind selector, and why does it refuse a mismatched pair?
- **A:** check-retrieval.py guards that the domain and corpus-kind selectors agree (domain code goes with corpus-kind code, domain nl with corpus-kind md); a mismatched pair is rejected because scoring against the wrong corpus mis-grades the run through cross-domain sentinel overlap.
- **sentinels:** `must agree`, `cross-domain sentinel overlap`, `--corpus-kind`
- **primary:** `.agents/skills/improving-context-retrieval-skills/scripts/check-retrieval.py`
- **evidence:** check-retrieval.py:67: Guard: domain and corpus-kind must agree \| :68: mis-grades via cross-domain sentinel overlap \| :69: if (args.domain == "code") != (args.corpus_kind == "code"): ap.error(...) \| :19: Pass `--corpus-kind code --domain code`

## `domain = nl` (20)

### cas-graphify-transcript-provenance-failure

- **slice:** session-prompting · **difficulty:** medium · **source:** claude
- **Q:** In the benchmark comparing graphify against the local Qdrant and GraphRAG paths, what was the blocking provenance defect that made graphify unable to attribute an extracted fact back to the transcript that actually recorded it, and which graph node field exhibited that defect?
- **A:** Graphify's session-transcript provenance was the blocking issue: in the final inception history graph, the nodes' `source_file` values pointed at files merely mentioned inside the transcripts (such as `.agents/skills/...`) rather than the transcript file that actually contained the evidence, so all three inception history queries missed their primary session file.
- **sentinels:** `source_file`, `which session recorded this?`
- **primary:** `docs/benchmarks/2026-06-08/0009-graphify-graphrag-rag.md`
- **evidence:** docs/benchmarks/2026-06-08/0009-graphify-graphrag-rag.md:105: Graphify's session-transcript provenance is the blocking issue. The final inception history graph had nodes whose `source_file` values were files mentioned by transcripts, such as `.agents/skills/...`, instead of the transcript file that contained the evidence. That makes graphify poor at answering "which session recorded this?"

### cas-graphify-version-and-commit-pin

- **slice:** session-prompting · **difficulty:** easy · **source:** claude
- **Q:** Which exact graphify release version, branch, and commit hash were pinned for the three-way retrieval benchmark, and which backend was used for the markdown/history extraction?
- **A:** The benchmark used graphify `0.8.35` from branch `v8` at commit `29e57cd295219773b8d300f1c134e41cc7133f05`, running `graphify extract ... --no-cluster` from a local checkout; markdown/history extraction used the Gemini backend, while code-only extraction used graphify's local tree-sitter path with no LLM tokens.
- **sentinels:** `0.8.35`, `29e57cd295219773b8d300f1c134e41cc7133f05`
- **primary:** `docs/benchmarks/2026-06-08/0009-graphify-graphrag-rag.md`
- **evidence:** docs/benchmarks/2026-06-08/0009-graphify-graphrag-rag.md:44: - `graphify`: graphify `0.8.35` from branch `v8` at commit `29e57cd295219773b8d300f1c134e41cc7133f05`. ... Markdown/history extraction used the Gemini backend

### cas-orphan-empty-head-abandon-revset

- **slice:** session-prompting · **difficulty:** medium · **source:** claude
- **Q:** When an agent's jj workspace cleanup left a stray anonymous empty change with no bookmark, what manual command was first used to remove it, and what revset did the eventual automated sweep use to find such residue?
- **A:** The stray empty side-head was first removed manually with `jj abandon urruyqxt`, and the eventual automated `jj_abandon_orphan_empty_heads` sweep finds the candidates with the revset `heads(all()) ~ ::main ~ bookmarks()` filtered by an empty/description template, minus each registered workspace's working-copy commit.
- **sentinels:** `jj abandon urruyqxt`, `heads(all()) ~ ::main ~ bookmarks()`
- **primary:** `docs/issues/2026-06-07/0007-workspace-cleanup-left-unreferenced-empty-side-head.md`
- **evidence:** docs/issues/2026-06-07/0007-...md:43: jj abandon urruyqxt ; :133: `heads(all()) ~ ::main ~ bookmarks()` filtered by an `empty`/`description` ; :129: jj_finish now calls jj_abandon_orphan_empty_heads

### cas-vcs-conflict-slowest-haiku-and-jj-proof

- **slice:** session-prompting · **difficulty:** hard · **source:** claude
- **Q:** In the first multi-agent conflict-resolution benchmark of the version-control skill, what was the worst serialized small-model conflict time before the revision, and what op-log evidence did the hardened quality check require to prove a round genuinely advanced the shared branch through Jujutsu rather than plain Git?
- **A:** The worst serialized small-model conflict time was 380s on the stub skill (a Haiku agent), falling to about 85s after the revision. To stop a colocated jj-mode round from passing while integrated with pure Git, `check-quality.sh` was hardened to require op-log proof of a `point/move bookmark main` operation, which is version-stable evidence since the seed never moves `main`.
- **sentinels:** `380s`, `point/move bookmark main`
- **primary:** `docs/benchmarks/2026-06-06/0000-vcs-skill-conflict-resolution.md`
- **evidence:** docs/benchmarks/2026-06-06/0000-...md:22: \| Worst small-model conflict time (serialized) \| 380s \| ~85s \| ; :43: require op-log proof that `main` was advanced through jj (a `point/move bookmark main` operation ...) ; :8: small = Haiku

### cas-inception-naming-rationale-and-typescript

- **slice:** session-prompting · **difficulty:** medium · **source:** claude
- **Q:** When the scaffold app for the docs/RAG harness was created, what reason did the user give for its name, and how did the agent get a TypeScript 7 native compiler binary into the project?
- **A:** The user asked for the project to be named 'inception' to represent the recursive abstraction and self-improving philosophy of the skill repository, and the agent obtained the TypeScript 7 native `tsgo` binary by swapping the generated `typescript` dependency for `@typescript/native-preview`.
- **sentinels:** `recursive abstraction and self-improving philosophy`, `@typescript/native-preview`
- **primary:** `docs/transcripts/2026-06-07/0028-claude-inception-tanstack-tooling.md`
- **evidence:** docs/transcripts/2026-06-07/0028-...md:15: called "inception", representing the recursive abstraction and self-improving philosophy of this skill repository. ; :35: The generated `typescript ^6.0.2` ... I swapped it for `@typescript/native-preview` ... added a `typecheck` script running `tsgo --noEmit`.

### cas-coding-style-memo-ban-and-oxlint-extends

- **slice:** session-prompting · **difficulty:** hard · **source:** claude
- **Q:** During the coding-style skill session, what did the adversarial research conclude about a literal blanket prohibition on memoization, and why couldn't the reusable lint fragment be applied only to the inception directory via a scoped block?
- **A:** The research's key verified result was that a literal blanket ban on memoization contradicts react.dev's own escape-hatch guidance, so `useMemo`/`useCallback`/`memo` stay legitimate in three documented cases. The fragment couldn't be scoped because oxlint's `extends` is top-level only — the `OxlintOverride` schema has no `extends` key — so it was consumed via a top-level `extends` instead of inside an overrides entry.
- **sentinels:** `literal blanket ban on memoization contradicts react.dev`, `OxlintOverride`
- **primary:** `docs/transcripts/2026-06-08/0037-claude-coding-style-skill.md`
- **evidence:** docs/transcripts/2026-06-08/0037-...md:33: a literal blanket ban on memoization contradicts react.dev's own escape-hatch guidance ; :58: the `OxlintOverride` schema has no `extends` key

### cas-cursor-composer-published-foreign-work

- **slice:** session-prompting · **difficulty:** medium · **source:** claude
- **Q:** In the documented incident where a concurrent agent swept up and published another agent's uncommitted edits, which commit hash bundled the two unrelated changes, and which agent identity was credited as co-author on it?
- **A:** The Cursor / Composer 2.5 session created commit `b30c66a2`, which bundled the Claude session's three uncommitted vcs edits with Cursor's own transcript reorder and was pushed to `origin/main` with a `Co-Authored-By: Composer 2.5 (Cursor) <cursoragent@cursor.com>` trailer describing work it did not author.
- **sentinels:** `b30c66a2`, `cursoragent@cursor.com`
- **primary:** `docs/issues/2026-06-07/0005-concurrent-cursor-agent-committed-and-pushed-another-agents-work.md`
- **evidence:** docs/issues/2026-06-07/0005-...md:47: `b30c66a2` that bundled two unrelated things ; :48-50: the Claude session's three uncommitted `vcs` edits, plus the Cursor session's own change ; :58: Co-Authored-By: Composer 2.5 (Cursor) <cursoragent@cursor.com> ; :61: pushed `b30c66a2` to `origin/main`

### cas-docs-migration-found-writing-docs-skill

- **slice:** session-prompting · **difficulty:** medium · **source:** claude
- **Q:** When the agent was asked to kick-start the docs skill but had to find a reference docs skill the user recalled from another repo, where did it ultimately locate that reference skill, and what was the skill called?
- **A:** After grepping across `~/.claude/projects/` for the user-referenced docs skill, the agent located a `writing-docs` skill on disk at `website/.agents/skills/writing-docs/SKILL.md` in the sibling website repo and used its method to author the OVERVIEW.md files.
- **sentinels:** `writing-docs`, `website/.agents/skills/writing-docs/SKILL.md`
- **primary:** `docs/transcripts/2026-06-07/0029-claude-docs-convention-migration.md`
- **evidence:** docs/transcripts/2026-06-07/0029-...md:32: `grep` across `~/.claude/projects/` surfaced a `writing-docs` skill; extracted full paths and located it on disk at `website/.agents/skills/writing-docs/SKILL.md`.

### cas-anthropic-contextual-retrieval-failure-stats

- **slice:** session-prompting · **difficulty:** medium · **source:** claude
- **Q:** In the GraphRAG research note, what top-20 retrieval failure-rate reductions does it cite from Anthropic's contextual retrieval, and which 2026 graph-retrieval system does it name as pushing hierarchical retrieval further?
- **A:** The note reports Anthropic's top-20 retrieval failure reductions of 35% for contextual embeddings, 49% for contextual embeddings plus BM25, and 67% when reranking is added, and it names Deep GraphRAG, published in 2026, as pushing hierarchical graph retrieval further with global-to-local filtering and dynamic reranking.
- **sentinels:** `for contextual embeddings, 49% for contextual embeddings plus BM25`, `Deep GraphRAG`
- **primary:** `docs/research/2026-06-08/0001-contextual-retrieval-with-graphrag.md`
- **evidence:** docs/research/2026-06-08/0001-...md:46-47: top-20 retrieval failure reductions of 35% for contextual embeddings, 49% for contextual embeddings plus BM25, and 67% when ... ; :91-92: Deep GraphRAG, published in 2026, pushes hierarchical graph retrieval further with global-to-local filtering

### cas-docs-rag-plan-coupling-and-closed-book

- **slice:** session-prompting · **difficulty:** hard · **source:** claude
- **Q:** The design plan for the docs/RAG harness argues one harness should optimize two skills together; what term names that core hypothesis and which statistic in the 2x2 factorial captures it, and what control does the plan add because the corpus is this very repo?
- **A:** The plan frames it as the coupling thesis, where the factorial's interaction term is the coupling signal that proves co-design beats additive. Because the corpus is this repo, it adds a Closed-book parametric-leakage control: generation is run with empty context and any query whose sentinel the model emits from prior knowledge is excluded from factuality.
- **sentinels:** `the coupling thesis`, `interaction term is the coupling signal`, `Closed-book parametric-leakage control`
- **primary:** `docs/plans/2026-06-07/0002-improving-docs-and-rag-skills.md`
- **evidence:** docs/plans/2026-06-07/0002-...md:33: Why one harness for both — the coupling thesis. ; :62: The interaction term is the coupling signal ; :308: Closed-book parametric-leakage control (critical — the corpus is this repo).

### cas-token-benchmark-gpt-outlier

- **slice:** session-prompting · **difficulty:** hard · **source:** claude
- **Q:** In the jj-vs-Git token and speed benchmark by model tier, what model was mapped to the small tier for the GPT family, and what single anomalous run drove GPT's headline token edge for Git over jj?
- **A:** For the GPT/Codex family the small tier mapped to `gpt-5.4-mini`, and GPT's headline came from a single small-tier jj outlier of 337 s and 29,095 tokens (a YAML scalar conflict plus a guard retry) versus 39 s and 3,158 tokens on Git — a 'huge Git edge'.
- **sentinels:** `gpt-5.4-mini`, `huge Git edge`, `single small-tier jj outlier`
- **primary:** `docs/benchmarks/2026-06-07/0004-vcs-jj-vs-git-token-speed.md`
- **evidence:** docs/benchmarks/2026-06-07/0004-...md:8: small=gpt-5.4-mini (Run A). ; :108: GPT's headline came from a single small-tier jj outlier (337 s / 29,095 ; :443/446/469: jj 337s/29,095 vs git 39s/3,158 \| huge Git edge

### cas-cx-retrieval-routing-ladder-tiers

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** The retrieving-context skill defines a best-first ladder for getting repo context. In order, what three retrieval approaches does it tell an agent to prefer, and which one is the always-available fallback?
- **A:** The ladder is, best-first: a hosted/managed retrieval service (cloud RAG) if the repo wires one, then a local hybrid RAG index via setting-up-rag for a medium-to-large local corpus, then hand-navigating the doc structure (the always-available floor). Hits at any tier are treated as candidates to verify against the cited primary source.
- **sentinels:** `Tier 1 — Cloud / managed RAG`, `Navigate the doc structure by hand`, `check-local-rag.sh`
- **primary:** `.agents/skills/retrieving-context/SKILL.md`
- **evidence:** retrieving-context/SKILL.md:32: ### Tier 1 — Cloud / managed RAG, if the repo wires one \| :69: ### Tier 3 — Navigate the doc structure by hand (always available) \| :54: Run `setting-up-rag`'s `check-local-rag.sh` (prints `READY` / `NOT_READY`)

### cas-cx-harness-floor-cell-and-mode-veto

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** In the context-retrieval harness's factorial, what does the floor cell represent and how is it run, and what rule governs a change that helps the RAG consumer mode but hurts the manual-structure consumer mode?
- **A:** The floor cell is the empty-corpus, no-retrieval baseline run before the four treatment cells each round; it scores 0 by construction and the cells are reported as lifts above it. The harness runs both consumer modes (manual structure navigation and RAG-routed), and a change that wins the RAG mode while losing the manual mode is treated as a failure.
- **sentinels:** `--no-retrieval`, `wins RAG but loses SIMPLE fails`
- **primary:** `.agents/skills/improving-context-retrieval-skills/MATRIX.md`
- **evidence:** improving-context-retrieval-skills/MATRIX.md:9: **Floor first** — `Z` (empty corpus + `--no-retrieval`) ... Scores 0 by construction; the four cells are reported as lifts above it. \| :22: A change that wins RAG but loses SIMPLE fails.

### cas-cx-optimizing-rag-prompt-scope-and-qa-count

- **slice:** session-prompting · **difficulty:** easy · **source:** codex
- **Q:** The June 8 prompt that kicked off this RAG-optimization effort scoped which skills to touch and how many Q&A pairs to collect per repo. How many detailed Q&A pairs did it ask for per repo, and which docs-authoring skill did it explicitly tell agents to leave unchanged?
- **A:** The prompt asked agents to use the improving-context-retrieval-skills harness to improve setting-up-rag and retrieving-context, collecting 10 to 20 very detailed question-and-answer pairs per repo, and it explicitly said to use the existing docs as-is and not modify the updating-docs skill.
- **sentinels:** `10 to 20 very detailed question-and-answer pairs`, `do not modify`, `Focus on RAG.`
- **primary:** `docs/prompts/2026-06-08/0005-optimizing-rag-setup.md`
- **evidence:** docs/prompts/2026-06-08/0005-optimizing-rag-setup.md:22: come up with 10 to 20 very detailed question-and-answer pairs \| :16: do not modify the [$updating-docs](...) skill. Focus on RAG.

### cas-cx-docs-convention-dated-typed-path

- **slice:** session-prompting · **difficulty:** medium · **source:** codex
- **Q:** The June 7 docs/RAG plan surveyed the repo and found that only one doc type used dated subdirectories. What canonical directory-and-filename layout did it propose to standardize all doc types on, and which new doc type did it add?
- **A:** The plan generalized the transcripts convention to `docs/<type>/YYYY-MM-DD/NNNN-slug.md` for every type, with a globally-unique zero-padded index from a generalized next-index.sh, required front-matter, and an OVERVIEW.md per subdir plus a top-level one. It kept the existing types and added a research type.
- **sentinels:** `docs/<type>/YYYY-MM-DD/NNNN-slug.md`, `next-index.sh`
- **primary:** `docs/plans/2026-06-07/0002-improving-docs-and-rag-skills.md`
- **evidence:** plans/0002-improving-docs-and-rag-skills.md:457: Canonical convention: `docs/<type>/YYYY-MM-DD/NNNN-slug.md`, globally-unique zero-padded index from a generalized `next-index.sh`, required front-matter, an OVERVIEW.md per subdir \| :460: add `research`

### cas-cx-floor-benchmark-cleanest-signal-256

- **slice:** session-prompting · **difficulty:** medium · **source:** codex
- **Q:** In the docs-skill floor-vs-doc benchmark, what was the cleanest headline result going from the no-doc floor to the with-docs condition, and why did the structured corpus fail to beat the naive corpus at the baseline RAG config?
- **A:** The cleanest signal was the floor-to-with-docs jump: retrieval_hit@20 rose from 0.000 to 0.833 and recall@20 from 0.000 to 0.642. The structured docs marginal was zero at baseline because the baseline used fixed 256-word chunking, which ignores headings and so erased the structural advantage that makes the structured corpus better.
- **sentinels:** `0.833`, `0.642`, `fixed-256-word chunking`
- **primary:** `docs/benchmarks/2026-06-08/0005-docs-skill-floor-vs-doc.md`
- **evidence:** 0005-docs-skill-floor-vs-doc.md:68: retrieval_hit@20 0.000 -> 0.833 (+0.833) \| :69: recall@20 0.000 -> 0.642 \| :96: fixed-256-word chunking ignores headings, so the structural advantage of ...

### cas-cx-rag-benchmark-0006-code-ranking-deltas

- **slice:** session-prompting · **difficulty:** medium · **source:** codex
- **Q:** In the baseline-vs-RAG benchmark for the new RAG skill, what natural-language recall lift did the skill's config give over naive RAG, and by how much did it sharpen code-file ranking on the nDCG and MRR metrics?
- **A:** The skill's RAG config lifted natural-language recall@20 by +0.100 (0.642 to 0.742) and pushed retrieval_hit@20 to 1.000 so every NL query surfaced a grade-2 doc; on code, where recall was already at ceiling, it sharpened ranking by +0.141 nDCG@10 (0.452 to 0.593) and +0.153 MRR (0.333 to 0.486).
- **sentinels:** `recall@20 +0.100`, `+0.141`, `+0.153`
- **primary:** `docs/benchmarks/2026-06-08/0006-rag-skill-baseline-vs-rag.md`
- **evidence:** 0006-rag-skill-baseline-vs-rag.md:48: lifts recall@20 +0.100 (0.642 -> 0.742) and closes retrieval_hit@20 to 1.000 \| :50: nDCG@10 +0.141 (0.452 -> 0.593) \| :51: MRR +0.153 (0.333 -> 0.486)

### cas-cx-source-map-token-reduction-inception-alphazero

- **slice:** session-prompting · **difficulty:** medium · **source:** codex
- **Q:** In the contextual-retrieval benchmark behind the updating-docs changes, adding explicit source maps cut how many tokens an agent needed to reach an answer for code corpora under the RAG config. What were the before/after token counts for the alpha-zero code and inception code cases?
- **A:** With the RAG config enabled, source maps cut chunk tokens-to-answer on alpha-zero code from 199 down to 99 while keeping primary_hit@20 at 1.000, and on inception code from 396 down to 75. For history/prose, source maps lifted answer_hit@5 to 1.000 on both projects.
- **sentinels:** `tokens-to-answer`, `from 199 to 99`, `from 396 to 75`
- **primary:** `docs/benchmarks/2026-06-08/0007-updating-docs-contextual-retrieval.md`
- **evidence:** 0007-updating-docs-contextual-retrieval.md:19: source map cut chunk tokens-to-answer from `199` to `99` while keeping primary_hit@20 = 1.000 \| :21: tokens-to-answer from `396` to `75`

### cas-cx-graphify-benchmark-recommendation-keep-qdrant

- **slice:** session-prompting · **difficulty:** medium · **source:** codex
- **Q:** In the three-way retrieval benchmark, which contender achieved the strongest recall across both domains and projects with no LLM indexing tokens, and what was the benchmark's practical decision about adopting graphify as the backend?
- **A:** The local GraphRAG prototype had the strongest recall, reaching 1.000 recall@20 on both domains across both projects with no LLM indexing tokens, but it was not yet a drop-in replacement. The practical decision was not to replace setting-up-rag with graphify; the suggested path was code-aware retrieval for Qdrant plus an optional graph/source-map overlay.
- **sentinels:** `best recall profile`, `not to replace setting-up-rag with graphify`
- **primary:** `docs/benchmarks/2026-06-08/0009-graphify-graphrag-rag.md`
- **evidence:** 0009-graphify-graphrag-rag.md:15: The local GraphRAG prototype had the best recall profile. It reached `1.000` recall@20 on both domains across both projects with no LLM indexing tokens \| :19: The practical decision is not to replace `setting-up-rag` with graphify.

### cas-cx-vcs-boundary-session-metric-verification

- **slice:** session-prompting · **difficulty:** medium · **source:** codex
- **Q:** In the session that added VCS-boundary pruning to the RAG loaders, what new verification script was introduced, and what hygiene-metric values did it report to prove nested VCS roots were excluded while gold validation still passed?
- **A:** The session added check-vcs-boundary.py, which fixtures nested jj workspaces, Git worktree .git files, and nested Git repos and verifies they are excluded while directly selected VCS roots still index. It reported vcs_boundary_ok=1 and vcs_boundary_nested_docs_indexed=0, and gold.py validate passed with 9 facts across 2 domains.
- **sentinels:** `check-vcs-boundary.py`, `vcs_boundary_nested_docs_indexed=0`, `9 facts across 2 domains`
- **primary:** `docs/transcripts/2026-06-08/0039-codex-exclude-vcs-workspaces-rag.md`
- **evidence:** 0039-codex-exclude-vcs-workspaces-rag.md:69: Added `check-vcs-boundary.py` to fixture nested jj workspaces, Git worktree `.git` files, and nested Git repos \| :82: it reported `vcs_boundary_ok=1`, `vcs_boundary_nested_docs_indexed=0` \| :84: gold set validated with 9 facts across 2 domains
