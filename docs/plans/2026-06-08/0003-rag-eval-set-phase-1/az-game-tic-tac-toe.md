# RAG eval set — `az-game-tic-tac-toe`

- **Repo root:** `/Users/shuyang/developer/alpha-zero/az-game-tic-tac-toe`
- **Questions:** 24  ·  domain {'code': 19, 'nl': 5}  ·  difficulty {'easy': 2, 'hard': 5, 'medium': 17}  ·  source {'claude': 14, 'codex': 10}
- **Code corpus (`domain=code`):** src/ include/ tests/ (board encoding, win detection, D4 symmetry, tensor encoding)
- **Prose corpus (`domain=nl`):** memory/ (constitution, game_rules, mcts_constraints, augmentation_strategy, history_lookback, …)
- **Note:** C++ Tic-Tac-Toe implementing the alpha-zero-api contract; code + design-doc questions.

Each entry is a gold fact for retrieval eval: a paraphrased **Q** (never containing its own sentinel), the grounded **A**, the exact **sentinels** that occur verbatim in the **primary** file(s), and the `domain`/`difficulty` slice. Sources/paths are relative to the repo root above. Every sentinel below was re-verified against the primary file's raw bytes at build time.

## `domain = code` (19)

### ttt-board-packing-bits

- **slice:** codebase · **difficulty:** easy · **source:** claude
- **Q:** How is the 3x3 board state physically stored in a single integer, and how many bits per cell does it use including which bits are left unused?
- **A:** The board is a `TttBoard` struct holding one `uint32_t cells` field, using 2 bits per cell (cell c lives in bits 2c and 2c+1, encodings 00 empty / 01 X / 10 O). Bits 18..31 are reserved zero, keeping `sizeof = 4`.
- **sentinels:** `TttBoard`, `Bits 18..31 are reserved zero`, `uint32_t cells`
- **primary:** `include/ttt/game.h`
- **evidence:** include/ttt/game.h:29:struct TttBoard { \| include/ttt/game.h:30:  uint32_t cells = 0; \| include/ttt/game.h:26: * Bits 18..31 are reserved zero. Total `sizeof = 4` keeps the per-node

### ttt-win-line-masks

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** How does win detection avoid looping over cells, and what precomputed values does it compare against the player's marks?
- **A:** Win detection precomputes a table of 8 bitmasks (one per winning line: 3 rows, 3 cols, 2 diagonals) in `kWinLines`, and `MaskHasAnyLine` checks whether a player's low-bit mask AND'ed with each line equals that line. For example the anti-diagonal is `0x01110` (cells 2,4,6).
- **sentinels:** `kWinLines`, `MaskHasAnyLine`, `0x01110`
- **primary:** `src/ttt/game/state.cc`
- **evidence:** src/ttt/game/state.cc:15:constexpr std::array<uint32_t, 8> kWinLines = { \| src/ttt/game/state.cc:28:    if ((player_low_bits & line) == line) { \| src/ttt/game/state.cc:23:    0x01110,  // anti diagonal: 2,4,6 -> bits 4,8,12 \| src/ttt/game/state.cc:26:bool MaskHasAnyLine(uint32_t player_low_bits) noexcept {

### ttt-isolate-x-o-bits

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** What single mask constant is used to pull out one player's marks from the packed board, and how does the code separate X's bits from O's bits?
- **A:** The code uses the mask `0x15555` (named `kLowBitsMask`, the low bit of every cell) to isolate X-encoded positions via `board_.cells & kLowBitsMask`, and gets O's bits by shifting right one and masking the same way: `(board_.cells >> 1) & kLowBitsMask`.
- **sentinels:** `0x15555`, `kLowBitsMask`
- **primary:** `src/ttt/game/state.cc`
- **evidence:** src/ttt/game/state.cc:11:constexpr uint32_t kLowBitsMask = 0x15555; \| src/ttt/game/state.cc:43:  const uint32_t low = board_.cells & kLowBitsMask; \| src/ttt/game/state.cc:44:  const uint32_t high = (board_.cells >> 1) & kLowBitsMask;

### ttt-canonical-perspective-swap

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** When it is the second player's turn, how does the perspective-normalized board recode the marks so both players' positions look the same to the network?
- **A:** `CanonicalBoard()` swaps the X (low) and O (high) bit of every cell so the current player's marks always read as 01 and the opponent's as 10, returning `TttB{(low << 1) | high}`. When Player1 is to move it returns the raw board unchanged.
- **sentinels:** `CanonicalBoard`, `(low << 1) \| high`
- **primary:** `src/ttt/game/state.cc`
- **evidence:** src/ttt/game/state.cc:37:TttB TttGame::CanonicalBoard() const noexcept { \| src/ttt/game/state.cc:38:  if (cur_player_ == ::az::game::api::Player1) { \| src/ttt/game/state.cc:45:  return TttB{(low << 1) \| high};

### ttt-apply-mark-code

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** When a move is applied in place, how does the code decide which two-bit pattern to OR into the board for the current player, and how does it record the move for undo?
- **A:** A helper `MarkCode` returns `0b01u` for Player1 and `0b10u` otherwise, and `ApplyActionInPlace` shifts that code left by `action * 2` and ORs it into `board_.cells`. It pushes the action into the fixed `action_history_` array and bumps `history_size_` so `UndoLastAction` can roll it back.
- **sentinels:** `MarkCode`, `0b01u : 0b10u`, `action_history_`
- **primary:** `src/ttt/game/action.cc`
- **evidence:** src/ttt/game/action.cc:14:  return (player == ::az::game::api::Player1) ? 0b01u : 0b10u; \| src/ttt/game/action.cc:41:  board_.cells \|= MarkCode(cur_player_) << shift; \| src/ttt/game/action.cc:43:    action_history_[history_size_] = action;

### ttt-valid-actions-empty-test

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** How does the legal-move enumerator determine that a given cell is empty before listing it as a valid action?
- **A:** `ValidActionsInto` loops cells 0..8 and tests whether the two bits for that cell are zero via `((board_.cells >> shift) & 0b11u) == 0u`, writing each empty cell index into the output array in increasing order and returning the count (0 if `IsOver()`).
- **sentinels:** `ValidActionsInto`, `0b11u) == 0u`
- **primary:** `src/ttt/game/action.cc`
- **evidence:** src/ttt/game/action.cc:19:std::size_t TttGame::ValidActionsInto( \| src/ttt/game/action.cc:25:  for (uint8_t c = 0; c < 9; ++c) { \| src/ttt/game/action.cc:27:    if (((board_.cells >> shift) & 0b11u) == 0u) {

### ttt-d4-forward-perm-table

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** How are the 8 symmetry transforms of the board represented, and how is the inverse of each transform obtained rather than hand-written?
- **A:** Each of the 8 D4 elements is a 9-entry cell permutation in the `kForwardPerm` table (e.g. 90-degree clockwise rotation is `{2, 5, 8, 1, 4, 7, 0, 3, 6}`), and the inverses are derived at compile time by `ComputeInversePerm`, which inverts each forward permutation into `kInversePerm`.
- **sentinels:** `kForwardPerm`, `{2, 5, 8, 1, 4, 7, 0, 3, 6}`, `ComputeInversePerm`
- **primary:** `src/ttt/augmentation/augmentation.cc`
- **evidence:** src/ttt/augmentation/augmentation.cc:16:constexpr std::array<std::array<uint8_t, 9>, 8> kForwardPerm = {{ \| src/ttt/augmentation/augmentation.cc:18:    {2, 5, 8, 1, 4, 7, 0, 3, 6},  // kRotate90CW \| src/ttt/augmentation/augmentation.cc:27:constexpr std::array<std::array<uint8_t, 9>, 8> ComputeInversePerm() {

### ttt-state-builder-friend

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** How do augmented game variants inherit the original's round counter and current player without replaying any moves, and what mechanism gives the augmenter direct access to private fields?
- **A:** A `TttStateBuilder` class (declared a friend of `TttGame`) constructs a variant by directly setting the private `board_`, `cur_player_`, and `round_` fields, so `AugmentAll` builds each transformed board while inheriting the original's current player and round count without action replay.
- **sentinels:** `TttStateBuilder`, `AugmentAll`
- **primary:** `src/ttt/augmentation/augmentation.cc`, `include/ttt/game.h`
- **evidence:** src/ttt/augmentation/augmentation.cc:58:class TttStateBuilder { \| src/ttt/augmentation/augmentation.cc:70:std::vector<TttGame> AugmentAll(const TttGame& game) noexcept { \| include/ttt/game.h:265:  friend class internal::TttStateBuilder;

### ttt-state-input-tensor-shape

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** What is the exact length and layout of the float vector produced for the network input, and how does it encode the two players' marks?
- **A:** The state serializer fills a vector of `2u * kCellCount` (18 floats): channel 0 (slots 0..8) one-hots the current player's marks and channel 1 (`kCellCount + c`, slots 9..17) one-hots the opponent's, read from the canonical board. The test pins this as `kStateVectorSize = 18`.
- **sentinels:** `2u * kCellCount`, `kCellCount + c`, `kStateVectorSize = 18`
- **primary:** `src/ttt/serializer/serializer.cc`, `tests/unit/serializer.cc`
- **evidence:** src/ttt/serializer/serializer.cc:35:  out->assign(2u * kCellCount, 0.0F); \| src/ttt/serializer/serializer.cc:43:      (*out)[kCellCount + c] = 1.0F; \| tests/unit/serializer.cc:23:constexpr std::size_t kStateVectorSize = 18;  // 2 channels x 9 cells

### ttt-deserializer-wrong-size

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** What length does the network-output decoder require, and what error does it return when the input vector is the wrong length?
- **A:** The decoder computes `kExpectedSize = TttGame::kPolicySize + 1u` (10) and, if `output.size()` differs, returns `std::unexpected(TttError::kDeserializeWrongSize)`; otherwise it gathers per-action priors over `ValidActionsInto`.
- **sentinels:** `kExpectedSize`, `kDeserializeWrongSize`
- **primary:** `src/ttt/deserializer/deserializer.cc`
- **evidence:** src/ttt/deserializer/deserializer.cc:16:  constexpr std::size_t kExpectedSize = TttGame::kPolicySize + 1u; \| src/ttt/deserializer/deserializer.cc:18:    return std::unexpected(TttError::kDeserializeWrongSize);

### ttt-inference-mean-aggregation

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** When combining the per-symmetry network evaluations back into one for the original position, how are the value and probabilities aggregated and how is each augmented action mapped back?
- **A:** `Interpret` maps each augmented action back with `InverseTransformAction`, accumulates probabilities into the original action-order slots, and averages: the value is `value_sum / static_cast<float>(variant_count)` and each probability is divided by the variant count (mean aggregation).
- **sentinels:** `InverseTransformAction`, `value_sum / static_cast<float>(variant_count)`
- **primary:** `src/ttt/inference/inference.cc`
- **evidence:** src/ttt/inference/inference.cc:40:          internal::InverseTransformAction(aug_actions[j], augmentation); \| src/ttt/inference/inference.cc:52:  result.value = value_sum / static_cast<float>(variant_count); \| src/ttt/inference/inference.cc:54:    p /= static_cast<float>(variant_count);

### ttt-last-player-toggle

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** How does the game report who moved last and the most recent move when no move has been applied yet versus after a move?
- **A:** Both observers guard on `history_size_ == 0` and return `std::nullopt` before any move; otherwise LastPlayer returns the toggle of the current player as `static_cast<TttP>(!cur_player_)` and LastAction returns `action_history_[history_size_ - 1]`.
- **sentinels:** `history_size_ == 0`, `static_cast<TttP>(!cur_player_)`, `action_history_[history_size_ - 1]`
- **primary:** `src/ttt/game/basic.cc`
- **evidence:** src/ttt/game/basic.cc:12:  if (history_size_ == 0) { \| src/ttt/game/basic.cc:17:  return static_cast<TttP>(!cur_player_); \| src/ttt/game/basic.cc:24:  return action_history_[history_size_ - 1];

### ttt-cx-game-contract-static-assert

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** What compile-time mechanism guarantees that the concrete tic-tac-toe game type satisfies the AlphaZero game interface, and what are the fixed sizes it declares for the policy head and maximum legal moves per turn?
- **A:** A compile-time check verifies the type conforms to the `::az::game::api::Game` concept (the engine stores games by value, so there is no virtual base). The type declares `kPolicySize = 9` and sets `kMaxLegalActions = kPolicySize`, so both equal 9.
- **sentinels:** `static_assert(::az::game::api::Game<TttGame>`, `kPolicySize = 9`, `kMaxLegalActions = kPolicySize`
- **primary:** `include/ttt/game.h`
- **evidence:** include/ttt/game.h:268:static_assert(::az::game::api::Game<TttGame>, \| include/ttt/game.h:95:  static constexpr std::size_t kPolicySize = 9; \| include/ttt/game.h:101:  static constexpr std::size_t kMaxLegalActions = kPolicySize;

### ttt-cx-isover-terminal-conditions

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** Besides a completed line, what two other conditions make the terminal-state check report that the game has ended, and how does it detect a completely filled board?
- **A:** The terminal check returns true if the round counter has reached the round cap (`round_ >= *kMaxRounds`) or if there is any winning line for either player. It also treats a full board as terminal: the board is full when the union of X and O low bits equals `kLowBitsMask`, i.e. `(x_bits | o_bits) == kLowBitsMask`.
- **sentinels:** `round_ >= *kMaxRounds`, `(x_bits \| o_bits) == kLowBitsMask`
- **primary:** `src/ttt/game/state.cc`
- **evidence:** src/ttt/game/state.cc:49:  if (kMaxRounds.has_value() && round_ >= *kMaxRounds) { \| src/ttt/game/state.cc:60:  return (x_bits \| o_bits) == kLowBitsMask;

### ttt-cx-undo-last-action-restore

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** When the most recent move is rolled back during a tree search, what does the undo routine do when the history is empty, and how does it erase the marked cell from the packed board?
- **A:** The rollback no-ops when there is no recorded history; otherwise it decrements the history size, looks up the popped action, and clears that cell's two bits with `board_.cells &= ~(0b11u << shift)`. It also decrements the round counter when positive and toggles the current player back.
- **sentinels:** `UndoLastAction`, `board_.cells &= ~(0b11u << shift)`
- **primary:** `src/ttt/game/action.cc`
- **evidence:** src/ttt/game/action.cc:50:void TttGame::UndoLastAction() noexcept { \| src/ttt/game/action.cc:57:  board_.cells &= ~(0b11u << shift);

### ttt-cx-policy-output-layout-z-slot

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** In the serialized policy-output vector, what occupies the very first slot, and how are the per-move priors scattered into the remaining slots?
- **A:** Slot 0 holds the scalar game outcome (`(*out)[0] = target.z`), and each legal move's prior is scattered to slot `1 + PolicyIndex(action)`; all other slots stay zero. The vector length is `kPolicySize + 1`.
- **sentinels:** `(*out)[0] = target.z`, `1u + idx`
- **primary:** `src/ttt/serializer/serializer.cc`
- **evidence:** src/ttt/serializer/serializer.cc:62:  (*out)[0] = target.z; \| src/ttt/serializer/serializer.cc:67:    (*out)[1u + idx] = target.pi[i];

### ttt-cx-d4-augmentation-enum-order

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** How are the eight board symmetry variants named and ordered in the augmentation enumeration, with the identity first and rotations before reflections?
- **A:** The symmetry enum lists the identity first (`kOriginal = 0`), then the rotations, then the reflections, ending with the two diagonal mirrors (`kMirrorDiagonalMain`, `kMirrorDiagonalAnti`). The augmenter emits one variant per enum member in this order.
- **sentinels:** `kOriginal = 0`, `kMirrorDiagonalAnti`, `kMirrorHorizontal`
- **primary:** `include/ttt/augmentation.h`
- **evidence:** include/ttt/augmentation.h:22:  kOriginal = 0, \| include/ttt/augmentation.h:26:  kMirrorHorizontal, \| include/ttt/augmentation.h:29:  kMirrorDiagonalAnti,

### ttt-cx-repl-ringbuffer-history-noop

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** In the interactive driver, what data structure holds prior game states before each move is applied, and why is pushing into it a no-op for this game?
- **A:** The driver keeps a fixed-capacity history buffer typed `RingBuffer<TttGame, std::array<TttGame, TttGame::kHistoryLookback>>`. Before applying the chosen move it calls `history.Push(game)`, but since the lookback is 0 for this Markov game the backing array is empty and the push is effectively a no-op.
- **sentinels:** `RingBuffer<TttGame, std::array<TttGame, TttGame::kHistoryLookback>>`, `history.Push(game)`
- **primary:** `src/main.cc`
- **evidence:** src/main.cc:45:    RingBuffer<TttGame, std::array<TttGame, TttGame::kHistoryLookback>>; \| src/main.cc:306:      history.Push(game);

### ttt-cx-build-cmake-standard-and-api-dep

- **slice:** codebase · **difficulty:** easy · **source:** codex
- **Q:** What minimum build-system version and C++ language standard does the project require, and how does it bring in its external AlphaZero API dependency?
- **A:** The build requires CMake 3.26 and C++23 with extensions disabled. The external AlphaZero API is fetched via FetchContent from the alpha-zero-api git repository, pinned by a configurable tag variable defaulting to v0.2.1.
- **sentinels:** `cmake_minimum_required(VERSION 3.26)`, `set(CMAKE_CXX_STANDARD 23)`, `ALPHA_ZERO_API_GIT_TAG`
- **primary:** `CMakeLists.txt`
- **evidence:** CMakeLists.txt:1:cmake_minimum_required(VERSION 3.26) \| CMakeLists.txt:9:set(CMAKE_CXX_STANDARD 23) \| CMakeLists.txt:14:set(ALPHA_ZERO_API_GIT_TAG

## `domain = nl` (5)

### ttt-augmentation-d4-order-eight

- **slice:** design-doc · **difficulty:** medium · **source:** claude
- **Q:** Why does the symmetry design use exactly eight transforms for the square board, and what is warned against padding the enum with?
- **A:** Because the 3x3 grid has full dihedral symmetry and the design notes that the dihedral group has order 8 (4 rotations + 4 reflections); it warns against padding with duplicate mirror-rotations since `D4 has order 8` and duplicates inflate per-position network calls without adding information. The network is trained to be `equivariant` under these symmetries.
- **sentinels:** `D4 has order 8`, `equivariant`
- **primary:** `memory/augmentation_strategy.md`
- **evidence:** memory/augmentation_strategy.md:56:with duplicate mirror-rotations: D4 has order 8, and duplicates inflate \| memory/augmentation_strategy.md:10:The neural network is trained to be **equivariant** under board

### ttt-mcts-allocation-free-rationale

- **slice:** design-doc · **difficulty:** medium · **source:** claude
- **Q:** Why must the in-place apply and undo move primitives avoid any heap allocation, and what is the quantified consequence of allocating in them?
- **A:** The design doc explains these two methods sit on the inner MCTS rollout loop and run once per expanded edge, so a single allocation per call multiplies into `hundreds of millions of allocations` across a training cycle; it mandates a pre-sized `std::array` history and `PolicyIndex` being a `bijection` to avoid corruption.
- **sentinels:** `hundreds of millions of allocations`, `bijection`
- **primary:** `memory/mcts_constraints.md`
- **evidence:** memory/mcts_constraints.md:29:hundreds of millions of allocations across a training cycle. \| memory/mcts_constraints.md:80:`PolicyIndex(action)` must be a **bijection** over the entire action

### ttt-cx-valid-action-ordering-determinism

- **slice:** design-doc · **difficulty:** medium · **source:** codex
- **Q:** Why must the order in which legal moves are enumerated be a pure function of the board state with no dependence on time, randomness, or call history?
- **A:** Because a training tuple records its policy targets under one enumeration order and is replayed against a network trained under another; if the orderings disagree the policy labels are scrambled. The design therefore requires the ordering to depend only on the current game state.
- **sentinels:** `labels are scrambled`
- **primary:** `memory/mcts_constraints.md`
- **evidence:** memory/mcts_constraints.md:77:labels are scrambled. The ordering must depend only on the current

### ttt-cx-unittest-coverage-gaps

- **slice:** design-doc · **difficulty:** medium · **source:** codex
- **Q:** Which two test obligations in the project's unit-test checklist are still marked as not yet implemented even though the code exists, relating to the allocation-reusing serializer methods and the symmetry round-trip?
- **A:** Two items remain unchecked: that the allocation-reusing serialize-into methods produce output identical to their allocating forms (noted as not yet covered in the serializer test file), and that applying a forward then inverse action transform returns the original action for every supported symmetry and representative action.
- **sentinels:** `not yet covered in`, `every supported `sym``
- **primary:** `memory/unittest_checklists.md`
- **evidence:** memory/unittest_checklists.md:158:  not yet covered in `tests/unit/serializer.cc`. \| memory/unittest_checklists.md:174:  every supported `sym` and every representative action `a`.

### ttt-cx-training-augmenter-pi-permute-z-preserve

- **slice:** design-doc · **difficulty:** hard · **source:** codex
- **Q:** What is the documented bug a training-time symmetry augmenter must avoid regarding the policy target, and what must happen to the scalar value target under symmetry?
- **A:** The augmenter must permute the policy target alongside the augmented board; returning the target unchanged would wrongly train the network to be augmentation-invariant rather than equivariant. The scalar value target is preserved unchanged because board symmetries are score-preserving.
- **sentinels:** `augmentation-invariant rather than equivariant`, `TASK-TRAIN-IMPL`
- **primary:** `memory/augmentation_strategy.md`
- **evidence:** memory/augmentation_strategy.md:96:the network to be augmentation-invariant rather than equivariant — \| memory/augmentation_strategy.md:98:template compiles before TASK-TRAIN-IMPL is done.
