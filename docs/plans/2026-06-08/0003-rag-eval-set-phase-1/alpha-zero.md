# RAG eval set — `alpha-zero`

- **Repo root:** `/Users/shuyang/developer/alpha-zero/alpha-zero`
- **Questions:** 32  ·  domain {'code': 20, 'nl': 12}  ·  difficulty {'easy': 3, 'hard': 12, 'medium': 17}  ·  source {'claude': 20, 'codex': 12}
- **Code corpus (`domain=code`):** src/ include/ (C++23 + CUDA engine: MCTS, inference, training), gui/ (TS/TSX), tests/, CMake
- **Prose corpus (`domain=nl`):** docs/ (transformer/inference/perf design docs, gui_design, logging, beyond_alphazero/)
- **Note:** C++23 + CUDA AlphaZero engine + web GUI; mix of engine-code and design-doc questions.

Each entry is a gold fact for retrieval eval: a paraphrased **Q** (never containing its own sentinel), the grounded **A**, the exact **sentinels** that occur verbatim in the **primary** file(s), and the `domain`/`difficulty` slice. Sources/paths are relative to the repo root above. Every sentinel below was re-verified against the primary file's raw bytes at build time.

## `domain = code` (20)

### az-mcts-virtual-loss-mean-q

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** In the MCTS search node, how does the mean action value account for in-flight parallel descents, so that multiple threads exploring the same edge are discouraged?
- **A:** In `Node::MeanActionValue()` the denominator is `edge_visit_count_ + virtual_loss_` and the numerator subtracts the pending virtual-loss count, computing `(edge_total_action_value_ - static_cast<float>(vl)) / denom`. This pessimistically biases an edge that other threads are currently descending, so PUCT steers concurrent workers toward different children.
- **sentinels:** `edge_total_action_value_ - static_cast<float>(vl)`, `MeanActionValue`
- **primary:** `include/az/mcts/node.h`
- **evidence:** include/az/mcts/node.h:224:    return (edge_total_action_value_ - static_cast<float>(vl)) /  ; include/az/mcts/node.h:220:  [[nodiscard]] float MeanActionValue() const {

### az-mcts-forced-playouts-floor

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** At the root of the tree search, before falling back to the usual selection rule, which under-explored children get priority and what formula sets their minimum visit floor?
- **A:** `Node::SelectForced(float forced_k)` returns the root child with the largest deficit below the KataGo forced-playout floor `std::sqrt(forced_k * std::max(0.0f, child->edge_prior_prob_) * total)`; it returns nullptr (deferring to PUCT) when forced_k <= 0 or every child has met its floor.
- **sentinels:** `Node* SelectForced(float forced_k)`, `std::sqrt(forced_k`
- **primary:** `include/az/mcts/node.h`
- **evidence:** include/az/mcts/node.h:379:  [[nodiscard]] Node* SelectForced(float forced_k) const {  ; include/az/mcts/node.h:389:          std::sqrt(forced_k * std::max(0.0f, child->edge_prior_prob_) *

### az-mcts-tree-reuse-delta1

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** When the same MCTS player is queried again after the opponent has made exactly one move, how does it decide whether it can keep part of the previous search tree, and what disqualifies a candidate subtree?
- **A:** `AdvanceOrBuildRoot_` handles the delta-1 case: when `cur_round == saved_round_ + 1` and a last action exists, it descends through the matching child, but treats an unexpanded leaf sibling (terminal or empty `Children()`) as a miss and falls through to building a fresh arena, since reusing it would leave `Select` with no children.
- **sentinels:** `AdvanceOrBuildRoot_`, `cur_round == saved_round_ + 1`
- **primary:** `include/az/mcts/player.h`
- **evidence:** include/az/mcts/player.h:211:  [[nodiscard]] std::pair<Node<G>*, bool> AdvanceOrBuildRoot_(  ; include/az/mcts/player.h:221:      if (cur_round == saved_round_ + 1 && game.LastAction().has_value()) {

### az-config-dirichlet-default-knobs

- **slice:** codebase · **difficulty:** easy · **source:** claude
- **Q:** What are the default values for the exploration noise mixing weight and the per-simulation search budget in the search configuration, and what happens if the noise concentration is left at zero?
- **A:** In `MctsConfig` the root-noise mixing weight `dirichlet_eps = 0.25f` and the search budget `num_iterations = 1600` by default; leaving `dirichlet_alpha` at its `0.0f` default opts into the engine-side fallback alpha = 10 / number of legal actions at the root.
- **sentinels:** `dirichlet_eps = 0.25f`, `num_iterations = 1600`, `dirichlet_alpha`
- **primary:** `include/az/config.h`
- **evidence:** include/az/config.h:36:  float dirichlet_eps = 0.25f;  ; include/az/config.h:25:  uint16_t num_iterations = 1600;  ; include/az/config.h:43:  float dirichlet_alpha = 0.0f;

### az-gumbel-sequential-halving-sigma

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** In the Gumbel-based root selection, how is the candidate set size constrained before sequential halving begins, and what scoring transform ranks survivors after each halving phase?
- **A:** `GumbelSchedule::Init` clamps the candidate count to `min(m_config, num_legal_actions)` and applies `RoundDownPow2_` so log2 phases divide evenly; survivors are ranked by `g + log(prior) + sigma(q)` where `sigma(q) = (c_visit + max_b N(b)) * c_scale * q`, and `BuildGumbelImprovedPolicy` reuses that sigma to build the completed-Q policy target.
- **sentinels:** `RoundDownPow2_`, `sigma(q) = (c_visit + max_b N(b)) * c_scale * q`, `BuildGumbelImprovedPolicy`
- **primary:** `include/az/mcts/gumbel.h`
- **evidence:** include/az/mcts/gumbel.h:91:    m_eff = RoundDownPow2_(m_eff);  ; include/az/mcts/gumbel.h:35://          sigma(q) = (c_visit + max_b N(b)) * c_scale * q  ; include/az/mcts/gumbel.h:277:std::vector<float> BuildGumbelImprovedPolicy(const Node<G>& root,

### az-replay-reanalyze-generation-guard

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** In the thread-safe training-sample ring buffer, how does the background re-analysis path avoid clobbering a slot whose original row was already evicted by fresh self-play between the read and the write-back?
- **A:** `WriteBackReanalyzed` compares each slot's current per-slot generation counter against the snapshot's expected id and skips the write when `slot_push_ids_[slot] != expected_push_ids[i]`, so only rows that haven't been overwritten since the reanalyze snapshot are updated.
- **sentinels:** `WriteBackReanalyzed`, `slot_push_ids_[slot] != expected_push_ids[i]`
- **primary:** `include/az/training/replay_buffer.h`
- **evidence:** include/az/training/replay_buffer.h:513:  WriteBackReanalyzed(std::span<const size_t> slot_indices,  ; include/az/training/replay_buffer.h:525:      if (slot_push_ids_[slot] != expected_push_ids[i]) continue;

### az-batch-inference-pipeline-slots

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** How does the batched inference server decide between a single-buffered synchronous path and a two-deep pipelined path, and what publishes a coherent set of mirrored weights to in-flight forward passes?
- **A:** The server keeps `kNumSlots = 2` pinned staging slots; sync-only models use slot 0 alone while a model exposing the async mixin (held via `async_model_`) pipelines submit/wait two-deep. Weight mirroring uses the seqlock-style `mirror_version_` counter, flipped only after `Mirror()` completes so any in-flight `ForwardBatch` sees fully-coherent parameters.
- **sentinels:** `kNumSlots = 2`, `async_model_`, `mirror_version_`
- **primary:** `include/az/model/batch_inference_server.h`
- **evidence:** include/az/model/batch_inference_server.h:169:  static constexpr size_t kNumSlots = 2;  ; include/az/model/batch_inference_server.h:144:  IAsyncForwardModel* async_model_ = nullptr;  ; include/az/model/batch_inference_server.h:164:  std::atomic<uint64_t> mirror_version_{0};

### az-cuda-adam-gradclip-kernel

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** In the hand-written CUDA training kernels, how is global-L2-norm gradient clipping arranged so that the L2 weight-decay term is never affected by the clip ratio, and how is the squared-gradient sum accumulated across all parameter buffers?
- **A:** The `adam_kernel` forms `g = grad_scale * grads[i] + weight_decay * params[i]`, applying the clip ratio `grad_scale` only to the data gradient before adding weight decay; the norm itself is gathered by `sum_sq_kernel`, a block-reduction that `atomicAdd`s each block's partial sum-of-squares (in double) into a single accumulator the host reads back.
- **sentinels:** `adam_kernel`, `grad_scale * grads[i] + weight_decay * params[i]`, `sum_sq_kernel`
- **primary:** `src/az/model/internal/cuda_mlp_kernels.cuh`
- **evidence:** src/az/model/internal/cuda_mlp_kernels.cuh:284:static __global__ void adam_kernel(float* __restrict__ params,  ; src/az/model/internal/cuda_mlp_kernels.cuh:292:  const float g = grad_scale * grads[i] + weight_decay * params[i];  ; src/az/model/internal/cuda_mlp_kernels.cuh:322:static __global__ void sum_sq_kernel(const float* __restrict__ g,

### az-flashattn-wmma-dh-gate

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** In the FP32 fused-attention implementation, for which head dimensions does the tensor-core (WMMA) forward kernel get used instead of the scalar one, and why is the larger head dimension excluded?
- **A:** `FlashAttnFp32UseWmma<kDh>()` returns true only for kDh of 16 or 32; kDh of 4, 8, and 64 fall back to the scalar one-thread-per-row kernel because TF32 m16n16k8 needs kDh % 8 == 0 and the ~96 KB SMEM footprint at kDh=64 exceeds the per-CTA opt-in cap.
- **sentinels:** `FlashAttnFp32UseWmma`, `kDh == 16 \|\| kDh == 32`
- **primary:** `src/az/model/internal/cuda_flash_attention.cuh`
- **evidence:** src/az/model/internal/cuda_flash_attention.cuh:44:constexpr bool FlashAttnFp32UseWmma() {  ; src/az/model/internal/cuda_flash_attention.cuh:45:  return kDh == 16 \|\| kDh == 32;

### az-cmake-game-swap-fetchcontent

- **slice:** codebase · **difficulty:** easy · **source:** claude
- **Q:** In the root build configuration, which cache variable and pinned tag select the concrete game that gets compiled into the engine binaries, and how is the unit-test build gated?
- **A:** The root `CMakeLists.txt` declares `AZ_GAME_XQ_GIT_TAG` pinned to `v0.2.7` for the FetchContent declaration of the wired Xiang Qi game, and unit tests are opt-in behind `option(AZ_BUILD_TESTS "Build engine unit tests" OFF)`.
- **sentinels:** `AZ_GAME_XQ_GIT_TAG`, `v0.2.7`, `AZ_BUILD_TESTS`
- **primary:** `CMakeLists.txt`
- **evidence:** CMakeLists.txt:49:set(AZ_GAME_XQ_GIT_TAG  ; CMakeLists.txt:50:    "v0.2.7"  ; CMakeLists.txt:264:option(AZ_BUILD_TESTS "Build engine unit tests" OFF)

### az-selfplay-value-mix-augment

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** In the self-play worker, how is each training sample's value target blended between the game outcome and the search estimate, and what multiplies the per-game sample count due to board symmetry?
- **A:** The worker computes `mixed_z = (1.0f - mix_alpha) * z_for_mover + mix_alpha * entry.root_q` for variance-reduced value mixing, then expands each full-search position through the Xiang Qi training augmenter; `kAugmentationFactor = 2` (identity plus horizontal mirror) sets the worst-case samples-per-game reservation.
- **sentinels:** `(1.0f - mix_alpha) * z_for_mover + mix_alpha * entry.root_q`, `kAugmentationFactor = 2`
- **primary:** `src/az/train/self_play.cc`
- **evidence:** src/az/train/self_play.cc:399:          (1.0f - mix_alpha) * z_for_mover + mix_alpha * entry.root_q;  ; src/az/train/self_play.cc:277:  constexpr size_t kAugmentationFactor = 2;

### az-cublaslt-tf32-fp8-entrypoints

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** In the tensor-core matmul wrapper, what compute type makes the FP32 trainer GEMMs run on tensor cores, and why does the FP8 entry point that produces FP32 output not fuse the bias in the epilogue?
- **A:** The FP32 trainer entry points set `CUBLAS_COMPUTE_32F_FAST_TF32` to run on TF32 tensor cores; `RunFp8To32` does not fuse bias because cuBLASLt requires the bias dtype to match the FP32 output while the replica only mirrors FP16 biases, so the caller adds the bias with a separate kernel.
- **sentinels:** `CUBLAS_COMPUTE_32F_FAST_TF32`, `RunFp8To32`
- **primary:** `src/az/model/internal/cublaslt_gemm.h`
- **evidence:** src/az/model/internal/cublaslt_gemm.h:21:// These set `CUBLAS_COMPUTE_32F_FAST_TF32` so Blackwell / Ada / Ampere  ; src/az/model/internal/cublaslt_gemm.h:12://   * `RunFp8To32`  — same, but Y is FP32 (policy head). Bias is added by

### az-cx-storage-root-dir-gui-layout

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** How does the GUI server reconstruct the same per-artifact directory layout that the C++ trainer uses, and which env vars decide whether the GUI pins to one run or auto-picks the newest one?
- **A:** The GUI's storage-layout helper reads the run config TOML from the config directory, takes the [storage] table, and resolves each per-artifact directory against the shared root prefix exactly as the C++ side does when joining relative paths. AZ_TRAINING_DIR pins the GUI to a single config directory; when it is unset, AZ_CONFIG_ROOT is the enumeration root under which the GUI picks the newest run config one level deep.
- **sentinels:** `readStorageLayout`, `AZ_TRAINING_DIR`, `AZ_CONFIG_ROOT`
- **primary:** `gui/src/server-fns/storage-layout.ts`, `gui/README.md`
- **evidence:** gui/src/server-fns/storage-layout.ts:42:export function readStorageLayout(configDir: string): StorageLayout {; gui/README.md:63:\| `AZ_TRAINING_DIR`    \| Pin the GUI (dashboard + daemon) to one **config directory**.; gui/README.md:64:\| `AZ_CONFIG_ROOT`     \| Enumeration root. When `AZ_TRAINING_DIR` is unset, the GUI picks the newest `run.toml` one level deep under this root.

### az-cx-replay-checkpoint-v5-doc-drift

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** What replay checkpoint schema does the checkpoint writer actually emit today, what extra targets does it append over the previous layout, and where is the markdown that describes this format out of date?
- **A:** The implementation defines and writes the compact V5 schema and rejects any compact checkpoint whose header schema isn't V5; V5 appends the own/opponent material-count float targets after the prior payload. The replay-buffer checkpoint markdown is stale because it still labels schema code 4 (compact V4) as the current format.
- **sentinels:** `kSchemaCompactV5`, `material_own`, `4=compact V4 (current)`
- **primary:** `src/az/training/replay_buffer_checkpoint.cc`, `docs/replay_buffer_checkpoint.md`, `docs/beyond_alphazero/material_head.md`
- **evidence:** src/az/training/replay_buffer_checkpoint.cc:41:constexpr uint32_t kSchemaCompactV5 = 5;; docs/beyond_alphazero/material_head.md:44:- `material_own` — own piece count / 16 in the side-to-move POV.; docs/replay_buffer_checkpoint.md:31:                           3=compact V3, 4=compact V4 (current)

### az-cx-batch-server-mirror-quiescence

- **slice:** codebase · **difficulty:** hard · **source:** codex
- **Q:** In the batched inference server, how is a weight-swap kept from racing an in-flight async forward pass, and what bookkeeping records that a swap actually published new weights?
- **A:** Mirror is queued on the same executor as forwards, and before it copies parameters in it drains any in-flight async slot by waiting on that slot's completion event so the read-side model is quiescent. A successful copy increments the mirror-publishes stat counter, giving an observable record that a weight swap landed.
- **sentinels:** `WaitForward`, `mirror_publishes`, `MirrorParametersFrom`
- **primary:** `src/az/model/batch_inference_server.cc`, `include/az/model/batch-inference-server.md`
- **evidence:** src/az/model/batch_inference_server.cc:240:    async_model_->WaitForward(slot.done_event);; src/az/model/batch_inference_server.cc:300:            stats_.mirror_publishes += 1;; src/az/model/batch_inference_server.cc:295:        ModelStatus mirror_status = model_->MirrorParametersFrom(*pm.src);

### az-cx-compact-head-output-widths

- **slice:** codebase · **difficulty:** hard · **source:** codex
- **Q:** Which output-vector widths does the compact policy adapter accept to cover the optional auxiliary heads (opponent-reply and material), and where do the value atoms sit relative to the policy logits when a distributional value head is present?
- **A:** The compact policy head uses the max-legal-action policy slots and maps them by a per-row legal-index array, skipping padding. With a distributional value head the leading value-bin atoms come first and policy logits follow. The compact adapter accepts the four output widths for baseline, opponent-policy, material, and both auxiliary heads enabled, with the largest being the value bins plus two policy blocks plus the two material scalars.
- **sentinels:** `n_value_bins + 2K + 2`, `kMaxLegalActions`, `legal_indices`
- **primary:** `include/az/model/policy.h`, `include/az/model/policy_head.md`
- **evidence:** include/az/model/policy.h:427:    //   n_value_bins + 2K + 2         (opp + material on); include/az/model/policy_head.md:8:  `kMaxLegalActions`.; include/az/model/policy_head.md:50:\| Per-row data \| full target distribution + optional `legal_mask`            \| `legal_indices` + `target_values`

### az-cx-gumbel-suppresses-root-noise

- **slice:** codebase · **difficulty:** hard · **source:** codex
- **Q:** When Gumbel root selection is turned on, why is the usual root exploration noise deliberately switched off, and how is that gating expressed in the player's branching logic?
- **A:** Gumbel root selection injects its own Gumbel(0,1) noise into the candidate ranking, so the player suppresses the usual Dirichlet root noise when Gumbel is active to keep the two from compounding. The code reads the gumbel-root-selection flag into a flag that then forces the exploration path off, so the temperature-schedule / cutoff-driven noise branch is skipped while Gumbel owns root descent.
- **sentinels:** `gumbel_root_selection`, `suppress Dirichlet`, `exploration_active`
- **primary:** `include/az/mcts/player.h`
- **evidence:** include/az/mcts/player.h:333:    const bool gumbel_active = conf_.gumbel_root_selection;; include/az/mcts/player.h:331:    // noise into the candidate-set ranking, so we suppress Dirichlet; include/az/mcts/player.h:334:    const bool exploration_active =

### az-cx-reanalyze-row-field-preservation

- **slice:** codebase · **difficulty:** hard · **source:** codex
- **Q:** When the reanalyze worker rewrites a replay row after re-running search, which sampling API gives it the slot generations it needs, and which fields of the row does it replace versus carry over unchanged from the original?
- **A:** The compact buffer's reanalyze snapshot API draws rows together with their physical slot indices and per-slot generations. After re-running MCTS, the worker's row builder overwrites only the legal-index and target-value arrays and preserves everything else (input, value, ply, opponent arrays, state bytes, material targets) from the original row.
- **sentinels:** `SnapshotForReanalyze`, `BuildReanalyzedRow`, `only `legal_indices` and `target_values``
- **primary:** `src/az/train/reanalyze.cc`, `include/az/training/replay_buffer.h`
- **evidence:** include/az/training/replay_buffer.h:481:  SnapshotForReanalyze(size_t n, size_t min_size_to_sample) {; src/az/train/reanalyze.cc:115:std::optional<CompactTrainingSample> BuildReanalyzedRow(; src/az/train/reanalyze.cc:114:// only `legal_indices` and `target_values`.

### az-cx-opp-reply-next-fullsearch-pairing

- **slice:** codebase · **difficulty:** hard · **source:** codex
- **Q:** How does self-play decide which later position supplies the opponent-reply target for a sample, given that some plies use reduced search budgets, and what flag marks samples whose target had to be zeroed out?
- **A:** Opponent-reply targets come from the next FULL-search ply, not merely the next ply; reduced-budget plies (fast PCR searches and resignation low-budget searches) are skipped because their visit count is too low to be a policy target. Rows that have such a successor pair augmented positions by transform index and set the opponent arrays with the present flag at 1, while tail full-search samples with no successor are emitted zero-filled with the present flag at 0.
- **sentinels:** `opp_present`, `opp_legal_indices`, `next full-search`
- **primary:** `src/az/train/self_play.cc`, `docs/beyond_alphazero/opp_reply_head.md`
- **evidence:** src/az/train/self_play.cc:443:            s.opp_present = 1;; src/az/train/self_play.cc:433:        s.opp_legal_indices.assign(XqGame::kMaxLegalActions, kCompactPadding);; docs/beyond_alphazero/opp_reply_head.md:15:  opponent's legal actions at the next full-search ply (same encoding

### az-cx-serve-model-cache-sha-keying

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** In the loopback inference daemon, how is its in-memory model cache keyed and concurrency-controlled, and what fields does its model-listing endpoint report for each checkpoint?
- **A:** The daemon's model cache holds models keyed by their sha256 and evicts on file mtime (LRU, default capacity 2), serializing inference for the same model through a per-entry mutex while letting different cached models interleave. Its model-listing endpoint reports each checkpoint with fields including its sha256, size, mtime, and schema version, and the inference endpoint accepts a wire-version field per request.
- **sentinels:** `keyed by sha256`, `schema_version`, `wire_version`
- **primary:** `src/serve.cc`
- **evidence:** src/serve.cc:113:// Model cache: shared_ptr<IModel> keyed by sha256, evicted on file mtime; src/serve.cc:483:                            {"schema_version", e.version}});; src/serve.cc:539:    const int wire = state.value("wire_version", 1);

## `domain = nl` (12)

### az-transformer-dyt-normalization

- **slice:** design-doc · **difficulty:** easy · **source:** claude
- **Q:** In the planned transformer policy-value network, what normalization scheme replaces LayerNorm, and what specifically about its math makes it a better fit for the custom CUDA kernels?
- **A:** The design uses DyT (Dynamic Tanh), computing `y = γ ⊙ tanh(α · x) + β` (citing arXiv:2503.10622) instead of LayerNorm. It fits because, unlike LayerNorm's per-token mean+variance reduction (a warp-shuffle plus sync inside each block), DyT is purely element-wise, so it removes a sync from the residual path and fuses cleanly into the pre-norm op of the attention/MLP kernels.
- **sentinels:** `y = γ ⊙ tanh(α · x) + β`, `arXiv:2503.10622`
- **primary:** `docs/az_transformer_design.md`
- **evidence:** docs/az_transformer_design.md:270:DyT replaces LayerNorm with `y = γ ⊙ tanh(α · x) + β` (Zhu/Chen/He/LeCun  ; docs/az_transformer_design.md:271:CVPR 2025, arXiv:2503.10622). Why this fits our project:

### az-transformer-model-parallel-split

- **slice:** design-doc · **difficulty:** hard · **source:** claude
- **Q:** For the opt-in two-GPU model-parallel mode of the transformer, how is the network partitioned across the two devices, and roughly how much data crosses the device boundary per forward pass at chess scale?
- **A:** The transformer is split between layers (the first n_layers/2 on device A, the rest on device B), not inside a single layer. Boundary traffic per forward pass is one `[B, T, d_model]` BF16 tensor in each direction, which at B=256, T=64, d_model=512 is 16 MB per direction (about 0.5 ms over a PCIe Gen5 x16 link), transferred via `cudaMemcpyPeer` since the box has no NVLink.
- **sentinels:** `between layers`, `cudaMemcpyPeer`, `16 MB per direction`
- **primary:** `docs/az_transformer_design.md`
- **evidence:** docs/az_transformer_design.md:800:  split the transformer **between layers**, not inside a single  ; docs/az_transformer_design.md:96:- **No NVLink**: cross-device transfers use `cudaMemcpyPeer` over PCIe  ; docs/az_transformer_design.md:804:  d*model=512 that is 16 MB per direction — about 0.5 ms over a

### az-inference-seq195-flash-recovery

- **slice:** design-doc · **difficulty:** hard · **source:** claude
- **Q:** After Xiang Qi switched to the token layout that encodes legal actions as distinct tokens, inference throughput collapsed; what was the measured slowdown relative to the old board-only shape, and which optimization recovered most of the loss and by how much?
- **A:** The board+actions shape measured at 0.27× the board-only dense baseline (about 3.7× slower), because attention is O(T²) and T more than doubled from 90 to 195. Adding FA2-style FlashAttention to the FP16 path jumped the new shape 2.14× (11,981 to 25,639 samples/s); FP8 did not help because the body was no longer GEMM-bound.
- **sentinels:** `0.27×`, `25,639`, `FlashAttention landed`
- **primary:** `docs/inference_optimization_plan.md`
- **evidence:** docs/inference_optimization_plan.md:280:\| `(seq=195, feat=2)` board + actions, compact 105 \| 105 \| **11,981** \| **0.27×** \|  ; docs/inference_optimization_plan.md:306:### Update (2026-05-14): FlashAttention landed  ; docs/inference_optimization_plan.md:317:\| `(seq=195, feat=2)` **+ FlashAttention** \| **25,639** \| **1.00×** \|

### az-fp8-gemm-16-alignment

- **slice:** design-doc · **difficulty:** medium · **source:** claude
- **Q:** What dimension-alignment constraints does cuBLASLt's FP8 algorithm catalog impose on the transformer's body matmuls, and how does the compact Xiang Qi configuration with its odd sequence length end up satisfying the per-call constraint?
- **A:** On sm_120 the FP8 body GEMM requires M, N, and K all to be multiples of 16, so d_model, d_model*mlp_ratio, and `B * seq_len` must each be 16-aligned. With seq_len=195 (odd), the per-call M constraint holds only for full batches: at max_batch=64 the product `B * seq_len = 12480 = 16 * 780`, so full steady-state batches are admissible while warm-up/tail batches return CUBLAS_STATUS_NOT_SUPPORTED.
- **sentinels:** `must be multiples`, `12480 = 16 * 780`, `CUBLAS_STATUS_NOT_SUPPORTED`
- **primary:** `docs/faster_inference.md`, `docs/inference_optimization_plan.md`
- **evidence:** docs/inference_optimization_plan.md:154:- `d_model`, `d_model * mlp_ratio`, and `B * seq_len` must be multiples  ; docs/faster_inference.md:243:  `B * seq_len = 12480 = 16 * 780` for full batches) satisfies this  ; docs/faster_inference.md:245:  `B * seq_len` returns `CUBLAS_STATUS_NOT_SUPPORTED` at heuristic

### az-replay-buffer-magic-schema

- **slice:** design-doc · **difficulty:** medium · **source:** claude
- **Q:** How does the persisted replay-buffer checkpoint file identify its format, and how does it handle attempts to load older compact-buffer layouts after the reanalyze data model landed?
- **A:** The file begins with an 8-byte magic `AZRB0001` followed by a 4-byte schema code (0=dense through 4=compact V4, the current writer layout). Pre-V4 compact buffers (V1, V2, V3) are refused with `kSchemaMismatch` because the reanalyze data model is a clean-slate migration; the schema codes share the same magic since the row-size delta is explicit in the schema field.
- **sentinels:** `AZRB0001`, `kSchemaMismatch`
- **primary:** `docs/replay_buffer_checkpoint.md`
- **evidence:** docs/replay_buffer_checkpoint.md:29: magic           : 8 bytes  "AZRB0001"  ; docs/replay_buffer_checkpoint.md:70:Pre-V4 compact buffers (V1, V2, V3) are refused with  ; docs/replay_buffer_checkpoint.md:71:`kSchemaMismatch` — the reanalyze data model is a clean-slate

### az-logging-training-perf-warmup-gate

- **slice:** design-doc · **difficulty:** medium · **source:** claude
- **Q:** Why does the training throughput CSV stay empty during the early part of a run even though its logging thread is active, and when does the first real row finally appear?
- **A:** The training-throughput CSV writer is gated on `warmup_done`: it polls but writes nothing while the buffer is still filling, deliberately so real throughput rows aren't buried under zeros. The first row lands one `kPerfLoggerDefaultPeriod` (5 min) after warmup ends, then once per period thereafter.
- **sentinels:** `warmup_done`, `kPerfLoggerDefaultPeriod`
- **primary:** `docs/logging.md`
- **evidence:** docs/logging.md:63:\| `training_perf.csv`  \| `TrainingPerfLogger` thread ... timer, **gated on `warmup_done`** ... first row lands `kPerfLoggerDefaultPeriod` (5 min) after warmup ends  ; docs/logging.md:70:silent during warmup — it polls but writes nothing until `warmup_done`

### az-perf-dyt-dalpha-single-thread-bug

- **slice:** design-doc · **difficulty:** hard · **source:** claude
- **Q:** An nsys profile once showed a single training kernel eating roughly three-quarters of GPU time; which kernel was it, what was the root cause, and what was the speedup after the fix?
- **A:** It was `tx_dyt_backward_dalpha_kernel`, which consumed about 72.9% of GPU time because it was launched `<<<1, 1>>>` with a triple-nested for-loop accumulating into a scalar (designed for T·B·D ≤ ~10^5 but run at production's 8.85 million). Rewriting it as a grid-stride parallel reduction with warp-shuffle/shared-memory block reduction gave a ~66× speedup on the bench (ms_per_step 8,984 → 135.8).
- **sentinels:** `tx_dyt_backward_dalpha_kernel`, `72.9`, `<<<1, 1>>>`
- **primary:** `docs/performance_optimization_tracker.md`
- **evidence:** docs/performance_optimization_tracker.md:453: \|   72.9 \| `tx_dyt_backward_dalpha_kernel`       \| 170,964,132,156 \|     355 \| 481,589,105 \|  ; docs/performance_optimization_tracker.md:466:kernel was launched `<<<1, 1>>>` with a triple-nested `for (b) for

### az-gui-serve-version-dispatch-cache

- **slice:** design-doc · **difficulty:** medium · **source:** claude
- **Q:** In the browser-GUI inference daemon, how does it decide which model loader to call for a given checkpoint, and what bounds how many loaded checkpoints it keeps resident on the GPU?
- **A:** The daemon dispatches by the `CMLP` version byte: v3 → `CudaMlp::Load`, v5 → `CudaTransformer::Load`, and any other version (including pre-opp-head v4 transformer files) returns 404 with a stderr line. Resident checkpoints are bounded by `--model-cache-size` (default 2), with synchronous LRU eviction since a transformer checkpoint can be hundreds of MB on the GPU.
- **sentinels:** `v3 → `CudaMlp::Load``, `--model-cache-size`
- **primary:** `docs/gui_design.md`
- **evidence:** docs/gui_design.md:294:transformer. `/infer` dispatches by version: v3 → `CudaMlp::Load`,  ; docs/gui_design.md:343:configurable (`--model-cache-size`, default 2) because a transformer

### az-cx-game-swap-checklist

- **slice:** design-doc · **difficulty:** medium · **source:** codex
- **Q:** If someone wants to retarget this engine onto a brand-new game instead of the one currently wired in, which entrypoint-level concerns does the README flag (model input/output widths, history handling) and which template layer is supposed to stay untouched?
- **A:** The README's game-swap walkthrough says the entrypoints (arena.cc, mcts.cc, train.cc) hardcode the concrete game type and that the model output width is currently the Xiang Qi compact-serializer width (z plus the max-legal-action slots). If the new game has history-dependent state, the empty history view the entrypoints pass to the serializer must be replaced with a real history window. The Node<G> / MCTSPlayer<G> / policy templates and everything under include/az/ are game-agnostic and don't change.
- **sentinels:** `1 + kMaxLegalActions`, `RingBufferView`, `MCTSPlayer<G>`
- **primary:** `README.md`
- **evidence:** README.md:97:     `kCompactStateFeatureSize` for input and `1 + kMaxLegalActions`; README.md:100:     `RingBufferView` the entrypoints currently pass to the serializer; README.md:106:The `Node<G>` / `MCTSPlayer<G>` / `CudaMlpPolicy<G>` templates and every

### az-cx-eval-server-isolation

- **slice:** design-doc · **difficulty:** medium · **source:** codex
- **Q:** While training runs, the trainer keeps pushing fresh weights into the self-play inference replicas, yet evaluator matches play with fixed candidate weights. What server separation and snapshot mechanism keeps the evaluator's candidate from drifting mid-match?
- **A:** The trainer only mirrors the self-play inference servers, and only every so many steps; the evaluator's live inference server is a deliberately separate replica that the trainer loop never touches. Each eval cycle loads a candidate snapshot from the eval anchor checkpoint directory and mirrors it once into the eval live inference server, so ongoing self-play mirroring cannot change the candidate during a match.
- **sentinels:** `eval_anchor_checkpoint_dir`, `eval_live_inference_server`, `mirror_every_steps`
- **primary:** `docs/training_pipeline.md`, `src/az/train/eval.cc`, `src/az/train/trainer.cc`
- **evidence:** docs/training_pipeline.md:195:   `<storage.eval_anchor_checkpoint_dir>/`, mirror it into; src/az/train/eval.cc:312:    std::shared_ptr<BatchInferenceServer> eval_live_inference_server,; src/az/train/trainer.cc:242:    if (!inference_servers.empty() && step % args.mirror_every_steps == 0) {

### az-cx-fp8-policy-head-stays-fp16

- **slice:** design-doc · **difficulty:** medium · **source:** codex
- **Q:** When the compact Xiang Qi transformer runs FP8 body matmuls, why is the policy head left in a higher precision rather than also being quantized?
- **A:** The head stays FP16 because the compact Xiang Qi policy output width (105) is not generally a multiple of 16, so it can't satisfy the FP8 GEMM's 16-alignment requirement; the FP8 path is restricted to the 16-aligned transformer body GEMMs. Config validation also limits the FP8 precision setting (rejecting it for distributional value heads and under model-parallel).
- **sentinels:** `output_size = 105`, `fp8_e4m3`
- **primary:** `docs/faster_inference.md`, `src/az/training/train_config.cc`
- **evidence:** docs/faster_inference.md:250:in general (`output_size = 105` for compact Xiang Qi), so the FP8; src/az/training/train_config.cc:1070:    case InferencePrecision::kFp8E4m3: return "fp8_e4m3";

### az-cx-mcts-value-perspective-convention

- **slice:** design-doc · **difficulty:** medium · **source:** codex
- **Q:** In what player's frame of reference are values stored and propagated through the search tree, and under what condition is a network value or an ancestor's contribution sign-flipped during backup?
- **A:** Every value reported up the tree is in the perspective of the leaf's just-moved player (the one who moved into the state), not the side about to move. A non-terminal leaf negates the network value when that player differs from the current side to move, and an ancestor flips sign when its just-moved player differs from the leaf's. Terminal leaves use the score from the leaf's last-mover perspective.
- **sentinels:** `last_player_`, `LastPlayer()`, `Backup_`
- **primary:** `include/az/mcts/conventions.md`
- **evidence:** include/az/mcts/conventions.md:24:`value` slot in PUCT scoring) is in the **leaf's `last_player_`'s; include/az/mcts/conventions.md:28:- Terminal leaves use `game.GetScore(*game.LastPlayer())`.; include/az/mcts/conventions.md:23:Every value reported up the tree (`Backup_`, `MeanActionValue`, the
