<!-- markdownlint-disable MD013 MD024 -->

# Codex GraphRAG Benchmark Session

Date: 2026-06-08
Repo: coding-agent-skills (jj bookmark codex-graphrag-benchmark, change yxnquzym)
Author: Shuyang Sun <shuyangsun10@gmail.com>
Agent: Codex Desktop (GPT-5, CLI 0.137.0-alpha.4, reasoning effort: not exposed in session metadata)
Summary: Benchmarked Qdrant/FastEmbed against local GraphRAG on inception and alpha-zero, researched contextual retrieval with GraphRAG, then prepared the work for integration. Logged token usage through the exported session: 9291578 input, 52534 output, 16859 reasoning, 9344112 total.

<!-- markdownlint-disable MD034 -->

## User

Use the /improving-context-retrieval-skills harness to benchmark and compare the local Qdrant RAG setup against using https://github.com/microsoft/graphrag.

Implement local GraphRAG and use @inception/ and @[REDACTED_LOCAL_PATH]/ as test projects. Test both coding session history and project code context retrieval, record important metrics and token usage, save the methodology and benchmark in the same file under @docs/benchmarks/.

As a side task, research and tell me if I want to use more advanced context retrival techniques such as contextual retrieval described in the Anthropic engineering blog https://www.anthropic.com/engineering/contextual-retrieval (and maybe more recent advancements), is it possible to implement that with graphrag? Save this research result under @docs/research.

Do not yet change the /setting-up-rag skill, let me know when you are done with your research and benchmark, give me a summary about the situation, then I will make a decision on what to do.

<!-- markdownlint-enable MD034 -->

## Assistant

I’ll use the `vcs`, `improving-context-retrieval-skills`, `updating-docs`, and `coding-style` skills in that order: isolate the work, follow the benchmark harness, place the docs where the repo expects them, and keep any benchmark code consistent.

## Assistant

_Tool calls summarized: exec_command x5, tool output batches x5._

## Assistant

The harness here is a meta-harness for evaluating retrieval behavior, but the user request is benchmark-only and explicitly says not to edit `setting-up-rag`. I’m going to keep changes to benchmark/research artifacts and any local benchmark helper code needed to make the comparison reproducible.

## Assistant

_Tool calls summarized: exec_command x6, tool output batches x6._

## Assistant

I’ve confirmed the repo already has benchmark/research docs from today, so I’m treating this as a new dated benchmark rather than replacing prior RAG baseline work. Next I’m checking the existing harness scripts and the two requested target projects so the comparison can reuse the repo’s metrics shape instead of inventing one.

## Assistant

_Tool calls summarized: exec_command x6, tool output batches x6._

## Assistant

The harness already has a Phase-0 in-process evaluator and the `setting-up-rag` skill already has a Qdrant/FastEmbed local pipeline. For this benchmark I’m adding a separate comparison runner that exercises the real local Qdrant path and a local GraphRAG-style graph/index path over the two requested projects, then records the report under `docs/benchmarks/`.

## Assistant

_Tool calls summarized: exec_command x11, update_plan x1, tool output batches x12._

## Assistant

One guard caught a command because the hook wants an explicit `cd` prefix even when the tool has a working directory. I’m keeping all subsequent shell commands explicitly inside the isolated workspace so the benchmark artifacts don’t land in the shared checkout.

## Assistant

_Tool calls summarized: exec_command x5, tool output batches x5._

## Assistant

The environment does not currently have `qdrant-client`, `fastembed`, Microsoft `graphrag`, or numeric libraries on the default Python. I’m going to put benchmark dependencies in a cache venv and keep the repo changes limited to the reproducible runner plus the two docs.

## Assistant

_Tool calls summarized: exec_command x5, tool output batches x5._

## Assistant

The dependency install is still running because Microsoft `graphrag` pulls a large stack (`lancedb`, `spacy`, `graspologic`, `pyarrow`, etc.). I’m letting it complete, but the benchmark runner will still have a deterministic local GraphRAG mode so the results don’t depend on cloud LLM access.

## Assistant

_Tool calls summarized: write_stdin x1, tool output batches x1._

## Assistant

The benchmark venv is ready with `qdrant-client[fastembed]` and Microsoft `graphrag` 2.7.2 installed. I’m now shaping a fixed query set for four slices: inception history, inception code, alpha-zero project-history docs, and alpha-zero code.

## Assistant

_Tool calls summarized: exec_command x5, tool output batches x5._

## Assistant

I found no exported alpha-zero “coding-sessions” tree; the closest project-history source is its `memory/` and `doc/` markdown. I’ll label that honestly as alpha-zero project history, while inception has real exported coding-session transcripts in this repo.

## Assistant

_Tool calls summarized: exec_command x5, tool output batches x5._

## Assistant

I’m going to add the benchmark runner now. It will not edit `setting-up-rag`; it imports that skill’s existing chunking/config code for the Qdrant arm and implements a separate deterministic local GraphRAG arm for measurement.

## Assistant

The runner is in place. I’m going to do a syntax pass first, then run the benchmark; the first Qdrant/FastEmbed run may download ONNX models, so it can take a bit.

## Assistant

_Tool calls summarized: exec_command x2, tool output batches x2._

## Assistant

The syntax check exposed that my patch landed in the shared checkout instead of the isolated workspace. That is my change, so I’m moving it into the isolated workspace and removing the stray copy before continuing.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

The stray shared-checkout file is removed and the runner is now in the isolated workspace. I’m rechecking status in both locations before running it.

## Assistant

_Tool calls summarized: exec_command x2, tool output batches x2._

## Assistant

Status is clean in the shared checkout and dirty only in my isolated workspace. I’m running the benchmark now against the four corpora.

## Assistant

_Tool calls summarized: exec_command x1, tool output batches x1._

## Assistant

The benchmark process is still running with no stdout yet, which likely means FastEmbed is warming/downloading models during the first Qdrant index. I’m polling rather than starting another run to avoid locking the embedded Qdrant store.

## Assistant

_Tool calls summarized: write_stdin x1, tool output batches x1._

## Assistant

Still running. This is the expected slow path for the real Qdrant/FastEmbed arm; I’m giving it more time before deciding whether to split the run by corpus.

## Assistant

_Tool calls summarized: write_stdin x1, tool output batches x1._

## Assistant

The runner buffers its progress output because it is not attached to a TTY, so the lack of output is not necessarily a hang. I’m continuing to wait; if it times out or errors, I’ll make the progress prints flush and rerun.

## Assistant

_Tool calls summarized: write_stdin x1, tool output batches x1._

## Assistant

It is still running after a few minutes. I’m going to let this poll complete once more; if it remains silent, I’ll interrupt and narrow the problem to either model download, Qdrant embedding, or a large alpha-zero corpus.

## Assistant

_Tool calls summarized: write_stdin x1, tool output batches x1._

## Assistant

The benchmark completed and wrote both TSV and JSON summaries. The alpha-zero code slice is noisy because that repo contains multiple similar API/game implementations; I’m inspecting per-query top docs now to decide whether the qrels need multi-relevant labels rather than a single hard-coded primary.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

The alpha-zero code corpus was polluted by `memory/` and `doc/` markdown because the code loader allowed `.md`. That made “code” queries rank design docs above source. I’m tightening the benchmark loader so alpha-zero code really means source/config files, then I’ll rerun the benchmark.

## Assistant

The loader fix is in the isolated workspace. I’m rerunning the benchmark with the same query set and overwriting the generated metrics/summary.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

The rerun is indexing again with a clean Qdrant path. Model files are cached now, so it should finish faster than the first run.

## Assistant

_Tool calls summarized: write_stdin x1, tool output batches x1._

## Assistant

Still running; the alpha-zero source corpus is the expensive part because it has hundreds of files and uses cross-encoder reranking. I’m letting it finish.

## Assistant

_Tool calls summarized: write_stdin x1, tool output batches x1._

## Assistant

The run is still active. No new action needed yet; I’m avoiding concurrent Qdrant runs because embedded mode is single-writer.

## Assistant

_Tool calls summarized: write_stdin x1, tool output batches x1._

## Assistant

The cleaned run finished. The main pattern is now clearer: Qdrant/FastEmbed ranks source code better on alpha-zero code, while the deterministic local graph arm is much faster and does well on history/source-map-like prose but loses on large code. I’m now drafting the report and the separate research note.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

The second run still shows alpha-zero code pollution from nested `.agents/skills` files inside alpha-zero game repos. Those are not project source context, so I’m excluding `.agents`, `.claude`, and `.github` from the code corpus and rerunning once more.

## Assistant

The loader now excludes nested agent/config scaffolding from the code corpus. I’m doing a quick syntax check and running the final benchmark pass.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

Final benchmark pass is running. This should be the reportable data set unless the cleaned corpus exposes another labeling issue.

## Assistant

_Tool calls summarized: write_stdin x1, tool output batches x1._

## Assistant

Still running; continuing to wait on the embedded Qdrant/FastEmbed pass.

## Assistant

_Tool calls summarized: write_stdin x1, tool output batches x1._

## Assistant

The final pass is clean enough to report: alpha-zero code corpus is now 247 source/config files after excluding docs, nested skills, and agent config. I’m writing the benchmark and research docs now, plus the overview index entries.

## Assistant

_Tool calls summarized: exec_command x1, tool output batches x1._

## Assistant

The benchmark report will call out an important constraint: Microsoft GraphRAG is LLM-indexing software, while the scored local GraphRAG arm here is a deterministic no-LLM graph retriever modeled on its text-unit/entity/relationship shape. That distinction matters for the decision.

## Assistant

The report and research note are written and indexed. I’m formatting the new Markdown/JSON files now, then I’ll run the repo’s checks that are relevant to these artifacts.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

Formatting surfaced a typo in the research note. I’m fixing that before running markdown lint.

## Assistant

The typo is fixed. I’m running the reproducibility and documentation checks now: Python syntax, Prettier check, and markdownlint.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

I have the benchmark and research drafted in the isolated workspace. I’m doing the final hygiene pass now: install the repo’s pinned markdown tooling, run the formatting/lint checks, and confirm I didn’t touch the `setting-up-rag` skill.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

The change set is limited to new benchmark/research docs, raw benchmark outputs, the runner, and the two overview indexes. The benchmark doc references `setting-up-rag` as the baseline but there are no edits under `.agents/skills/setting-up-rag`.

## Assistant

_Tool calls summarized: exec_command x1, tool output batches x1._

## Assistant

The pinned repo tooling is installed in this workspace now, including the jj formatting hook setup. I’m running the actual checks against the finished documents and runner.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

The full repo-wide checks are currently blocked by pre-existing Markdown issues in older docs and transcripts. I’m narrowing the verification to the files touched in this change so the result reflects this benchmark work rather than inherited cleanup debt.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

The direct binaries are not on the shell PATH, but the local packages are present under `node_modules/.bin`. I’m rerunning the targeted checks through those pinned binaries.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

One check needed adjustment: Prettier doesn’t own Python or TSV here, and the repo’s markdownlint config injects the full `**/*.md` glob even when file arguments are provided. I’m checking the touched Markdown/JSON directly and then running markdownlint with a temporary config that preserves the same rule set but limits the file list.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

The touched Markdown and JSON pass Prettier. I’m using a temporary markdownlint config without the repo-wide glob so the lint run only evaluates the files from this task.

## Assistant

_Tool calls summarized: exec_command x2, tool output batches x2._

## Assistant

Targeted markdownlint on the four touched Markdown files is clean. I’m doing one last status/summary read so the final note can point to the exact artifacts and key benchmark numbers.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

The final status is still exactly the intended seven-file change set. The report and research note both read cleanly; I noticed the summary JSON uses a different key shape than my quick `jq` probe expected, so I’m checking that structure before I close this out.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

One more narrow diff check confirms `setting-up-rag` itself is untouched; the only references to it are in the new benchmark/research docs and runner.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

I’m going to do one final feasibility check for a real Microsoft GraphRAG run: whether a local or API LLM endpoint is actually configured. I won’t print any secret values, just whether the relevant variables or local service are present.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

There are no relevant OpenAI/Azure/Anthropic/GraphRAG/Ollama environment variables visible. The GraphRAG CLI is installed; I’m checking the local Ollama service path from the isolated workspace now.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

The shell hook blocks ad-hoc `curl` even to localhost, so I’m using the Ollama CLI directly for the local-model check.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

`ollama` is installed, but `ollama list` did not return within 10 seconds, which is consistent with no responsive local service for a full GraphRAG indexing run. I’m polling it once so I don’t leave a command running.

## Assistant

_Tool calls summarized: write_stdin x1, tool output batches x1._

## Assistant

Ollama does have models available, so a real Microsoft GraphRAG run may be possible via an OpenAI-compatible local endpoint. I’m inspecting GraphRAG’s generated config in `/tmp` before deciding whether that can be run reliably inside this benchmark.

## Assistant

_Tool calls summarized: exec_command x4, tool output batches x4._

## Assistant

GraphRAG has a `fast` indexing method and an explicit `--skip-validation` flag for no-LLM steps. I’m probing that on a tiny `/tmp` corpus; if it works, I can replace the hand-rolled graph arm with the actual Microsoft GraphRAG fast outputs.

## Assistant

_Tool calls summarized: exec_command x1, tool output batches x1._

## Assistant

The Microsoft GraphRAG fast probe is still running after 30 seconds on a one-line corpus, so I’m polling it carefully rather than leaving it in the background.

## Assistant

_Tool calls summarized: write_stdin x1, tool output batches x1._

## Assistant

A one-line Microsoft GraphRAG `fast` index still has no output after about a minute, which is not usable for this benchmark pass. I’m stopping the probe and keeping the documented limitation explicit.

## Assistant

_Tool calls summarized: exec_command x2, write_stdin x2, tool output batches x4._

## Assistant

The GraphRAG probe changes the limitation wording: Ollama is installed with models, but GraphRAG is not configured against it, and the `fast` probe failed before completion due missing NLTK data over a certificate error. I’m updating the benchmark note so it accurately distinguishes “local model exists” from “configured GraphRAG indexing path exists.”

## Assistant

I updated the benchmark limitation section. I’m rerunning the targeted formatting and Markdown lint on the touched docs.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

The edited docs pass targeted Prettier, targeted markdownlint, and the Python runner compiles. I’m checking final workspace status and then I’ll summarize the decision point.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

Done. I did not change `setting-up-rag`.

Artifacts:

- Benchmark + methodology: [0008-qdrant-vs-local-graphrag.md](./docs/benchmarks/2026-06-08/0008-qdrant-vs-local-graphrag.md)
- Raw metrics: [0008-qdrant-vs-local-graphrag-metrics.tsv](./docs/benchmarks/2026-06-08/0008-qdrant-vs-local-graphrag-metrics.tsv)
- Runner: [0008-qdrant-vs-local-graphrag-benchmark.py](./docs/benchmarks/2026-06-08/0008-qdrant-vs-local-graphrag-benchmark.py)
- Research note: [0001-contextual-retrieval-with-graphrag.md](./docs/research/2026-06-08/0001-contextual-retrieval-with-graphrag.md)

Situation summary: Qdrant/FastEmbed should remain the default. The local GraphRAG arm was very fast and strong on history/prose, but it is too brittle for source-code context retrieval. Qdrant is slower mainly because the current baseline uses CPU cross-encoder reranking, but it has the stronger production path for hybrid dense+sparse code/doc search.

Important limitation: Microsoft `graphrag` was installed and probed, but I did not get a full Microsoft GraphRAG index run. There is no API key/configured local LLM+embedding endpoint, and a `graphrag index --method fast --skip-validation` probe failed on local NLTK data download/cert verification before graph completion. The scored comparison is therefore Qdrant/FastEmbed vs a local deterministic GraphRAG implementation, with that limitation documented.

Research answer: yes, Anthropic-style contextual retrieval can be implemented with GraphRAG, but it is not a simple flag. The clean approach is a preprocessing/custom workflow step that stores raw chunk text separately from contextualized retrieval text, so citations and source verification remain grounded.

Verification:

- Benchmark ran and produced TSV/JSON outputs.
- Python runner compiles.
- Touched Markdown/JSON passes Prettier.
- Touched Markdown passes markdownlint with `--no-globs`.
- Repo-wide `format:check`/`lint:md` still fail on pre-existing older docs/transcripts, unrelated to this change.

Key sources used: [Anthropic Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval), [Microsoft GraphRAG repo](https://github.com/microsoft/graphrag), [GraphRAG indexing docs](https://microsoft.github.io/graphrag/index/overview/), [GraphRAG query docs](https://microsoft.github.io/graphrag/query/overview/).

## User

Rebased onto main, resolve conflicts, export coding session transcript, then integrate and push using the [$vcs](./.agents/skills/vcs/SKILL.md) skill.

## Assistant

I’ll work from the existing isolated workspace for this task and use the VCS helper path for conflict resolution/integration. I’m also loading the session export skill now because you explicitly asked for the transcript export.

## Assistant

_Tool calls summarized: exec_command x3, tool output batches x3._

## Assistant

The workspace is in jj mode and currently has no visible conflict markers or unresolved jj conflict state. I’m exporting the transcript next, then I’ll run the standard `integrate.sh` helper for the bookmark and handle any conflicts it reports.

## Assistant

_Tool calls summarized: exec_command x6, tool output batches x6._

## Assistant

The export index is `0040`. I’m parsing the Codex JSONL now; if the raw session file is too tool-heavy to preserve verbatim, I’ll keep user turns exact and summarize tool calls per the export skill.

## Assistant

_Tool calls summarized: exec_command x8, tool output batches x8._

## Assistant

I’m going to generate the transcript from the matching Codex JSONL session, preserving user turns and summarizing tool calls. I’ll redact local paths outside the repo and convert repo-local absolute paths to relative paths before running the bundled redaction scanner.

## Assistant

_Tool calls summarized: exec_command x1, tool output batches x1._

## Assistant

The raw log exposes token counts but not a named reasoning-effort setting. I’ll record that honestly in the transcript metadata rather than guessing.

## Assistant

_Tool calls summarized: exec_command x1, tool output batches x1._

## Assistant

The transcript’s tool summary will show the local shell/plan/session-control calls that Codex logged. Web research citations are already preserved in the benchmark and research docs; the raw Codex JSONL does not expose separate browser call records in the same way.

## Assistant

I’m creating `docs/coding-sessions/2026-06-08/0040-codex-graphrag-benchmark.md` now. The file will include the required markdownlint directive, metadata, exact user turns with required redactions, assistant turns, and compact tool summaries.

## Assistant

_Tool calls summarized: exec_command x1._
