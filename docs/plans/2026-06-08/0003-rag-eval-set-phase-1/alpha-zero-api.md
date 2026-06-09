# RAG eval set — `alpha-zero-api`

- **Repo root:** `/Users/shuyang/developer/alpha-zero/alpha-zero-api`
- **Questions:** 30  ·  domain {'code': 23, 'nl': 7}  ·  difficulty {'easy': 5, 'hard': 5, 'medium': 20}  ·  source {'claude': 20, 'codex': 10}
- **Code corpus (`domain=code`):** src/ include/ (header-only C++ game-contract interfaces), test/
- **Prose corpus (`domain=nl`):** doc/report.md, doc/migration-guides/
- **Note:** Header-only C++ contract that games implement to plug into the engine.

Each entry is a gold fact for retrieval eval: a paraphrased **Q** (never containing its own sentinel), the grounded **A**, the exact **sentinels** that occur verbatim in the **primary** file(s), and the `domain`/`difficulty` slice. Sources/paths are relative to the repo root above. Every sentinel below was re-verified against the primary file's raw bytes at build time.

## `domain = code` (23)

### azapi-game-concept-required-statics

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** In the value-semantic game contract that replaced the old virtual interface, what compile-time static members must a conforming game type expose besides the policy-size and history-depth constants, specifically the one that bounds how many legal moves a single state can produce, and what numeric relationship must it satisfy?
- **A:** A conforming game must declare `kMaxLegalActions`, the per-state upper bound on the number of legal actions, and it must satisfy `kMaxLegalActions <= kPolicySize`. Dense games set them equal, while games with a much smaller legal-action ceiling can size a compact policy head against it.
- **sentinels:** `kMaxLegalActions`, `kMaxLegalActions <= kPolicySize`
- **primary:** `src/include/alpha-zero-api/game.h`
- **evidence:** src/include/alpha-zero-api/game.h:38: *     `kMaxLegalActions <= kPolicySize`. Dense games set

### azapi-game-self-play-cap-invariant

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** The game contract has an optional self-play hard cap so pathological loops in early-iteration networks still terminate. What type is that cap declared as, and what must the terminal-check observer guarantee once the round counter reaches it?
- **A:** The cap is declared as `static constexpr std::optional<uint32_t> kMaxRounds`. If it is set, `IsOver()` must return true once `CurrentRound() >= *kMaxRounds`.
- **sentinels:** `kMaxRounds`, `std::optional<uint32_t>`, `CurrentRound() >= *kMaxRounds`
- **primary:** `src/include/alpha-zero-api/game.h`
- **evidence:** src/include/alpha-zero-api/game.h:46: *     `CurrentRound() >= *kMaxRounds`. The cap exists so pathological; line 81: { G::kMaxRounds } -> std::convertible_to<std::optional<uint32_t>>;

### azapi-game-noexcept-free-apply

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** There is a non-mutating transition helper defined once for every conforming game (copy, apply in place, return) that concrete games are told never to implement themselves. On what trait is its noexcept specification conditioned?
- **A:** The free function `ApplyAction(const G& game, const action_t& action)` is marked `noexcept(std::is_nothrow_copy_constructible_v<G>)`, so it is noexcept exactly when copying the game type cannot throw. It copies the game, calls `ApplyActionInPlace`, and returns the snapshot.
- **sentinels:** `ApplyAction`, `std::is_nothrow_copy_constructible_v<G>`
- **primary:** `src/include/alpha-zero-api/game.h`
- **evidence:** src/include/alpha-zero-api/game.h:119: ApplyAction(const G& game, const typename G::action_t& action) noexcept( src/include/alpha-zero-api/game.h:120:    std::is_nothrow_copy_constructible_v<G>) {

### azapi-compact-target-padding-slot

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** When a compact policy-target blob is padded to a fixed width for uniform replay-buffer rows, what sentinel value marks the padding entries in the index list, and how is that value defined?
- **A:** Padding entries set their index to `CompactPolicyTargetBlob::kPaddingSlot`, which is defined as `std::numeric_limits<std::size_t>::max()`, with the padded values set to 0. Implementations that pad must still report the unpadded count via `count`.
- **sentinels:** `kPaddingSlot`, `std::numeric_limits<std::size_t>::max()`
- **primary:** `src/include/alpha-zero-api/policy_output.h`
- **evidence:** src/include/alpha-zero-api/policy_output.h:75:  static constexpr std::size_t kPaddingSlot = src/include/alpha-zero-api/policy_output.h:76:      std::numeric_limits<std::size_t>::max();

### azapi-evaluation-vs-trainingtarget-split

- **slice:** codebase · **difficulty:** easy · **source:** claude
- **Q:** The API splits 'what the network produced' from 'what the network is asked to learn' into two distinct structs. Name both structs and the scalar field each one uses for the value/outcome term.
- **A:** `Evaluation` is the decoded network prediction and holds a `value` field, while `TrainingTarget` is the supervised replay-buffer label and holds a `z` field for the actual game outcome. The split makes the prediction-versus-label distinction type-level explicit.
- **sentinels:** `struct Evaluation`, `struct TrainingTarget`
- **primary:** `src/include/alpha-zero-api/policy_output.h`
- **evidence:** src/include/alpha-zero-api/policy_output.h:30:struct Evaluation {  (float value; line 31) src/include/alpha-zero-api/policy_output.h:53:struct TrainingTarget {  (float z; line 54)

### azapi-ringbuffer-storage-concept

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** The history ring buffer is parameterized on a storage backend constrained by a concept so that misuse fails at compile time. What is that concept named, and which random-access iterator tag does the read-only window's iterator advertise to compose with std::ranges?
- **A:** The storage backend is constrained by the `RingBufferStorage` concept (requiring value_type, indexing, size(), and data()), and the view's iterator advertises `iterator_concept = std::random_access_iterator_tag` so it works with range-based for and std::ranges algorithms.
- **sentinels:** `concept RingBufferStorage`, `iterator_concept = std::random_access_iterator_tag`
- **primary:** `src/include/alpha-zero-api/ring_buffer.h`
- **evidence:** src/include/alpha-zero-api/ring_buffer.h:31:concept RingBufferStorage = requires(S s, std::size_t i) { src/include/alpha-zero-api/ring_buffer.h:193:    using iterator_concept = std::random_access_iterator_tag;

### azapi-ringbuffer-newest-index-arithmetic

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** When the history ring buffer builds its read-only window, how does it compute the storage index of the most-recently-pushed element given the write head and capacity, and which ordering does the resulting view present?
- **A:** View() computes the newest element's index as `(head_ + cap - 1) % cap` and constructs a window that iterates newest-first, where index 0 is the most recently pushed element and index Size()-1 is the oldest still retained.
- **sentinels:** `(head_ + cap - 1) % cap`, `newest-first`
- **primary:** `src/include/alpha-zero-api/ring_buffer.h`
- **evidence:** src/include/alpha-zero-api/ring_buffer.h:157:    const std::size_t newest = (head_ + cap - 1) % cap; src/include/alpha-zero-api/ring_buffer.h:145: *   The returned view iterates **newest-first**: index 0 is the most

### azapi-state-serializer-history-window

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** What is the abstract method signature a game's state serializer must override to turn a position into network input, and what engine-owned object does it receive alongside the game to reach back across past positions?
- **A:** The state serializer overrides `SerializeCurrentState(const G& game, RingBufferView<G> history)` returning a `std::vector<float>`; the `RingBufferView<G> history` is the engine-owned window of past states whose Size() equals G::kHistoryLookback.
- **sentinels:** `SerializeCurrentState`, `RingBufferView<G> history`
- **primary:** `src/include/alpha-zero-api/serializer.h`
- **evidence:** src/include/alpha-zero-api/serializer.h:31:  [[nodiscard]] virtual std::vector<float> SerializeCurrentState( src/include/alpha-zero-api/serializer.h:32:      const G& game, RingBufferView<G> history) const noexcept = 0;

### azapi-deserializer-precision-contract

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** The dense policy-output decoder takes a span of single-precision floats, and the docs explain why half-precision support is deliberately excluded from that signature. What must callers do with FP16/BF16 network outputs before invoking it, and what alternative signature would a dedicated half-precision overload use?
- **A:** Because the dense `Deserialize` takes `std::span<const float>`, callers must up-convert FP16/BF16 outputs to FP32 before invoking the deserializer; half-precision support, if needed, belongs in a dedicated overload taking `std::span<const std::byte>` plus a precision tag.
- **sentinels:** `up-convert FP16/BF16 outputs to FP32`, `std::span<const float> output`
- **primary:** `src/include/alpha-zero-api/deserializer.h`
- **evidence:** src/include/alpha-zero-api/deserializer.h:22: * up-convert FP16/BF16 outputs to FP32 before invoking the src/include/alpha-zero-api/deserializer.h:36:      const G& game, std::span<const float> output) const noexcept = 0;

### azapi-default-dense-serializer-layout

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** In the canonical dense policy-output serializer, how big is the produced output vector relative to the policy size, where does the value scalar go, and which expression chooses the slot for the i-th legal action's probability?
- **A:** The default dense serializer allocates a vector of size `G::kPolicySize + 1`, places `target.z` in slot 0, and scatters each probability into `result[1 + idx]` where `idx = game.PolicyIndex(actions[i])`. Slots not corresponding to a legal action stay 0.
- **sentinels:** `G::kPolicySize + 1`, `result[1 + idx]`
- **primary:** `src/include/alpha-zero-api/defaults/serializer.h`
- **evidence:** src/include/alpha-zero-api/defaults/serializer.h:34:    std::vector<float> result(G::kPolicySize + 1, 0.0f); src/include/alpha-zero-api/defaults/serializer.h:40:      result[1 + idx] = target.pi[i];

### azapi-compact-deserializer-missing-slot-error

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** When the default compact-policy decoder gathers priors back into per-legal-action order, how does it treat padded index entries during the scan, and what error string does it return if some legal action's slot is absent from the non-padding entries?
- **A:** The default compact deserializer skips entries whose index equals `CompactPolicyTargetBlob::kPaddingSlot`, and if a legal action's slot is not found among the remaining entries it returns the error 'compact output missing slot for a legal action'.
- **sentinels:** `CompactPolicyTargetBlob::kPaddingSlot`, `compact output missing slot for a legal action`
- **primary:** `src/include/alpha-zero-api/defaults/compact_deserializer.h`
- **evidence:** src/include/alpha-zero-api/defaults/compact_deserializer.h:61:        if (output.legal_indices[j] == CompactPolicyTargetBlob::kPaddingSlot) { src/include/alpha-zero-api/defaults/compact_deserializer.h:72:            "compact output missing slot for a legal action");

### azapi-defaults-board-action-player-aliases

- **slice:** codebase · **difficulty:** easy · **source:** claude
- **Q:** Among the standard type aliases the API ships for newcomers, what is the two-dimensional fixed-size board alias defined as, and what concrete boolean constants represent the two players in the binary-player convention?
- **A:** `Standard2DBoard<ROWS, COLS>` is defined as `std::array<std::array<int8_t, COLS>, ROWS>`, and the binary-player convention names the two players `Player1 = false` and `Player2 = true`.
- **sentinels:** `Standard2DBoard`, `constexpr BinaryPlayer Player1 = false`, `constexpr BinaryPlayer Player2 = true`
- **primary:** `src/include/alpha-zero-api/defaults/game.h`
- **evidence:** src/include/alpha-zero-api/defaults/game.h:15:using Standard2DBoard = std::array<std::array<int8_t, COLS>, ROWS>; src/include/alpha-zero-api/defaults/game.h:27:constexpr BinaryPlayer Player1 = false; src/include/alpha-zero-api/defaults/game.h:28:constexpr BinaryPlayer Player2 = true;

### azapi-ttt-error-enum-policy-size

- **slice:** codebase · **difficulty:** easy · **source:** claude
- **Q:** In the example tic-tac-toe game's error enumeration, which enumerator signals that a neural-network output vector had the wrong length, and which other enumerator flags an out-of-range column in a parsed action?
- **A:** The tic-tac-toe `TttError` enum includes `kInvalidPolicyOutputSize` for a malformed network output length and `kInvalidActionColumnRange` for a parsed action whose column is out of range.
- **sentinels:** `kInvalidPolicyOutputSize`, `kInvalidActionColumnRange`
- **primary:** `test/tic_tac_toe/game.h`
- **evidence:** test/tic_tac_toe/game.h:36:  kInvalidPolicyOutputSize, test/tic_tac_toe/game.h:33:  kInvalidActionColumnRange,

### azapi-ttt-policyindex-and-history-storage

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** How does the example tic-tac-toe game map a row/column action to its fixed policy slot, and since it is a Markov game, how is the engine-side history buffer instantiated so it occupies essentially no space?
- **A:** TttGame's PolicyIndex maps an action via `row * TTT_COLS + col`, and because it declares kHistoryLookback == 0 the history is a `RingBuffer<TttGame, std::array<TttGame, TttGame::kHistoryLookback>>`, i.e. a `std::array<TttGame, 0>` that takes essentially no space and always yields an empty view.
- **sentinels:** `row * TTT_COLS + col`, `TttGame::kHistoryLookback`
- **primary:** `test/tic_tac_toe/game.h`, `test/tic_tac_toe/main.cc`
- **evidence:** test/tic_tac_toe/game.h:119: *   The mapping is `row * TTT_COLS + col`, deterministic and stable test/tic_tac_toe/main.cc:44:    RingBuffer<TttGame, std::array<TttGame, TttGame::kHistoryLookback>>;

### azapi-ttt-augmentation-duplicate-symmetries

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** The tic-tac-toe example enumerates more board symmetries than the relevant symmetry group actually has. How many transformations does it enumerate, why is that a known over-count, and how does the inference combiner weight the outputs?
- **A:** The example enumerates `kNumAugmentations = 12` transformations even though the dihedral group D4 has order 8, so the last four `kMirrorVertical*` entries are duplicates of earlier ones; `Interpret` weights all 12 outputs equally, which double-weights certain symmetries.
- **sentinels:** `kNumAugmentations = 12`, `dihedral group D4 has order`, `kMirrorVerticalRotate270`
- **primary:** `test/tic_tac_toe/augmentation.h`
- **evidence:** test/tic_tac_toe/augmentation.h:38:constexpr std::size_t kNumAugmentations = 12; test/tic_tac_toe/augmentation.h:17: * by the Tic-Tac-Toe example. The dihedral group D4 has order 8, so test/tic_tac_toe/augmentation.h:35:  kMirrorVerticalRotate270,

### azapi-cx-default-deser-no-softmax-vs-migration

- **slice:** codebase · **difficulty:** hard · **source:** codex
- **Q:** There is a documented inconsistency about whether the library's canonical policy-output decoder normalizes its probabilities. What does the current default decoder header say it does to the gathered priors, and which older migration document describes the same default as doing the opposite?
- **A:** The current default dense (and compact) deserializer headers state they return the gathered probabilities verbatim with no implicit softmax or renormalization, telling callers whose networks emit logits to compose a softmax themselves. The older v0.0.5-to-v0.1.0 migration guide, however, describes the default deserializer as reading the masked subset and softmax-normalizing, which contradicts the current headers.
- **sentinels:** `those probabilities verbatim — no implicit softmax`, `softmax-normalizes`
- **primary:** `src/include/alpha-zero-api/defaults/deserializer.h`, `doc/migration-guides/v0.0.5-to-v0.1.0.md`
- **evidence:** src/include/alpha-zero-api/defaults/deserializer.h:26: * those probabilities verbatim — no implicit softmax or; doc/migration-guides/v0.0.5-to-v0.1.0.md:177:masked subset for `game.ValidActions()` and softmax-normalizes.

### azapi-cx-ttt-coordinate-parsing-display

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** When the example tic-tac-toe game parses a textual move like a column letter plus a row digit, how does it convert the human-facing row number into the internal storage row index, and which error does it raise when the letter falls outside the valid column letters?
- **A:** Parsing maps the 1-based human row number to the internal row index by computing the board height minus the row number (row_index = TTT_ROWS - row_number), which is why display labels rows from 3 down to 1. If the uppercased column letter is outside the valid range it returns the error kInvalidActionColumnRange, and a non-letter column yields kInvalidActionColumnType.
- **sentinels:** `TTT_ROWS - row_number`, `kInvalidActionColumnType`
- **primary:** `test/tic_tac_toe/game.cc`
- **evidence:** test/tic_tac_toe/game.cc:261:  const uint16_t row_index = static_cast<uint16_t>(TTT_ROWS - row_number); test/tic_tac_toe/game.cc:244:    return std::unexpected(TttError::kInvalidActionColumnType);

### azapi-cx-ttt-serializer-player-relative

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** The example tic-tac-toe state serializer ignores the history window because the game is Markov, but it does not emit raw board cells. What transformation does it apply to each cell so the encoding is from the side-to-move's perspective?
- **A:** For each flattened board cell it emits the value relative to the current player using the expression `player ? -cell : cell`, i.e. it negates every cell when it is the second player's turn so the network always sees the position from the perspective of the side to move.
- **sentinels:** `player ? -cell : cell`
- **primary:** `test/tic_tac_toe/serializer.cc`
- **evidence:** test/tic_tac_toe/serializer.cc:18:      result.emplace_back(static_cast<float>(player ? -cell : cell));

### azapi-cx-ttt-training-augmenter-remap

- **slice:** codebase · **difficulty:** hard · **source:** codex
- **Q:** When the example tic-tac-toe training augmenter produces symmetric copies of a labeled position, how does it line up each augmented board's policy probabilities with the original target, and what does it do with the value label?
- **A:** It builds a map keyed by the original game's PolicyIndex, then for each augmented game enumerates that game's legal actions and uses InverseTransformAction to map each augmented action back to the original coordinate frame, looking up the original probability through that map and writing it into the augmented legal-action order. The value label target.z is carried through unchanged.
- **sentinels:** `InverseTransformAction`, `TttTrainingAugmenter`
- **primary:** `test/tic_tac_toe/train.cc`
- **evidence:** test/tic_tac_toe/train.cc:24:std::vector<std::pair<TttGame, TrainingTarget>> TttTrainingAugmenter::Augment(; test/tic_tac_toe/train.cc:49:          InverseTransformAction(aug_actions[j], sym);

### azapi-cx-ttt-score-win-status-semantics

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** In the example tic-tac-toe game, what numeric value does the per-player score query return for an ongoing or drawn game versus a decisive one, and which internal status values represent the two possible winners?
- **A:** GetScore returns 0 for an ongoing or drawn game, +1 for the player whose symbol won, and -1 otherwise, deciding the winner by comparing the internal status WIN_PLAYER_X / WIN_PLAYER_O against the queried player. The terminal check treats the game as over when the round count reaches the round cap or the status is not ONGOING.
- **sentinels:** `WIN_PLAYER_O`, `WIN_PLAYER_X`
- **primary:** `test/tic_tac_toe/game.cc`
- **evidence:** test/tic_tac_toe/game.cc:177:  if ((status == WIN_PLAYER_O && !player) \|\|; test/tic_tac_toe/game.cc:178:      (status == WIN_PLAYER_X && player)) {

### azapi-cx-cmake-interface-library-defaults-gating

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** How is the header-only core of this API exposed as a CMake target, and how is the bundle of default serializer/deserializer implementations made optional?
- **A:** The core is declared as a header-only INTERFACE library named api with the namespaced alias AlphaZeroAPI::api. The default implementations are gated behind a DEFAULTS option (default off); only when DEFAULTS is enabled does CMake add the separate defaults INTERFACE library and its AlphaZeroAPI::defaults alias.
- **sentinels:** `add_library(AlphaZeroAPI::api ALIAS api)`, `add_library(AlphaZeroAPI::defaults ALIAS defaults)`
- **primary:** `src/CMakeLists.txt`
- **evidence:** src/CMakeLists.txt:17:add_library(AlphaZeroAPI::api ALIAS api); src/CMakeLists.txt:51:  add_library(AlphaZeroAPI::defaults ALIAS defaults)

### azapi-cx-project-version-cxx23

- **slice:** codebase · **difficulty:** easy · **source:** codex
- **Q:** What version number and C++ language standard does the top-level build configuration of this API declare for the project?
- **A:** The root CMake project is named AlphaZeroAPI at VERSION 0.2.1 and sets the C++ standard to 23 (CMAKE_CXX_STANDARD 23, required).
- **sentinels:** `VERSION 0.2.1`, `set(CMAKE_CXX_STANDARD 23)`
- **primary:** `CMakeLists.txt`
- **evidence:** CMakeLists.txt:5:  VERSION 0.2.1; CMakeLists.txt:9:set(CMAKE_CXX_STANDARD 23)

### azapi-cx-testsh-build-matrix-and-ci

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** What distinct library-linkage build configurations does the repository's test shell script exercise before running the example, and how is that script invoked from continuous integration?
- **A:** The test script configures and builds the project under STATIC_ONLY, SHARED_ONLY, and the combination of both (which is expected to fail configuration), plus a DEFAULTS build, then builds and runs the tic-tac-toe-main example. CI invokes it via `bash test.sh` on pushes to the main branch after installing cmake, ninja-build, and g++.
- **sentinels:** `DSTATIC_ONLY=True`, `tic-tac-toe-main`, `ninja-build`
- **primary:** `test.sh`, `.github/workflows/test.yml`
- **evidence:** test.sh:43:cmake -G Ninja -DSTATIC_ONLY=True ../.. &&  cmake --build .; test.sh:75:./build/build-tests/tic-tac-toe-main; .github/workflows/test.yml:14:        run: sudo apt-get update && sudo apt-get install -y cmake ninja-build g++

## `domain = nl` (7)

### azapi-report-b4-policyindex-resolution

- **slice:** design-doc · **difficulty:** medium · **source:** claude
- **Q:** The design review flagged that the old default decoder was unusable mid-game because the action-to-policy-slot mapping was an unwritten contract. How was that blocking issue resolved in the v0.1.0 API in terms of the new required static and member?
- **A:** It was resolved by making the Game concept require `static constexpr std::size_t kPolicySize` plus a `PolicyIndex(action)` member that maps each action_t to a slot in [0, kPolicySize); the default serializer scatters and the default deserializer gathers the legal-action subset through that mapping, so the defaults finally work mid-game.
- **sentinels:** `kPolicySize`, `PolicyIndex(action)`
- **primary:** `doc/report.md`
- **evidence:** doc/report.md:297: **Resolution (implemented in v0.1.0).** ... :298:`static constexpr std::size_t kPolicySize` and a `PolicyIndex(action)` doc/report.md:302:subset via `game.PolicyIndex(action)` into an `Evaluation`.

### azapi-report-s6-dihedral-bug

- **slice:** design-doc · **difficulty:** medium · **source:** claude
- **Q:** In the significant-issues section, the review identifies an averaging bias in the example augmenter caused by redundant square symmetries. Which algebraic identity does it cite as proof that one mirror-then-rotate composition collapses to another, and how does the combiner mishandle it?
- **A:** The review cites `MirrorH ∘ Rot180 == MirrorV` (among four such identities) to show four of the twelve transformations are duplicates, and notes that `Interpret()` averages all 12 outputs equally, giving certain symmetries double weight, which it calls a real bug in the example.
- **sentinels:** `MirrorH ∘ Rot180 == MirrorV`, `averages all 12 outputs equally`
- **primary:** `doc/report.md`
- **evidence:** doc/report.md:426:- `MirrorH ∘ Rot180 == MirrorV` doc/report.md:431:So four of the twelve are duplicates of others, and `Interpret()` doc/report.md:432:averages all 12 outputs equally — giving certain symmetries double

### azapi-report-s4-transposition-hash

- **slice:** design-doc · **difficulty:** medium · **source:** claude
- **Q:** The review suggests an opt-in primitive for engines that want a transposition table, an optimization the original AlphaZero paper does not require. What kind of canonical-state hash does it recommend, and what is the proposed opt-in signature returning an optional 64-bit value?
- **A:** It recommends a Zobrist-style hash of the canonical state, proposed as an opt-in `virtual std::optional<uint64_t> StateHash() const noexcept { return std::nullopt; }`, useful for MCTS transposition tables as in KataGo and LeelaChessZero.
- **sentinels:** `Zobrist-style hash`, `StateHash()`
- **primary:** `doc/report.md`
- **evidence:** doc/report.md:393:- A Zobrist-style hash of the canonical state doc/report.md:400:virtual std::optional<uint64_t> StateHash() const noexcept { return std::nullopt; }

### azapi-migration-compact-rule-of-thumb

- **slice:** design-doc · **difficulty:** medium · **source:** claude
- **Q:** In the v0.1.0-to-v0.2.0 migration guide, what is the quantitative rule of thumb given for deciding whether a game should switch from a dense policy head to a compact one, and what single line of code is the entire migration for a game that stays dense?
- **A:** The rule of thumb is to go compact when `kPolicySize > 10⁴` and `kMaxLegalActions / kPolicySize < 0.1`; for a game staying dense the whole migration is adding the line `static constexpr std::size_t kMaxLegalActions = kPolicySize;`.
- **sentinels:** `kMaxLegalActions / kPolicySize < 0.1`, `static constexpr std::size_t kMaxLegalActions = kPolicySize`
- **primary:** `doc/migration-guides/v0.1.0-to-v0.2.0.md`
- **evidence:** doc/migration-guides/v0.1.0-to-v0.2.0.md:41:before you decide; the rule of thumb is `kPolicySize > 10⁴` *and* doc/migration-guides/v0.1.0-to-v0.2.0.md:42:`kMaxLegalActions / kPolicySize < 0.1`. doc/migration-guides/v0.1.0-to-v0.2.0.md:15:static constexpr std::size_t kMaxLegalActions = kPolicySize;

### azapi-migration-validactionsinto-cookiecutter-marker

- **slice:** design-doc · **difficulty:** medium · **source:** claude
- **Q:** The v0.2.0-to-v0.2.1 guide replaces the heap-allocating legal-action enumerator with a caller-owned-buffer variant. What is the new method's name, and what leftover marker do compact games scaffolded from the template still carry on their legal-action ceiling that must be filled in first?
- **A:** The vector-returning enumerator is replaced by `ValidActionsInto(std::array<action_t, kMaxLegalActions>&)`, which writes into the caller's buffer and returns the count; compact games generated from the cookiecutter template still carry a `TODO(policy_head_layout=compact)` marker on the kMaxLegalActions declaration that must be filled in before implementing it.
- **sentinels:** `ValidActionsInto`, `TODO(policy_head_layout=compact)`
- **primary:** `doc/migration-guides/v0.2.0-to-v0.2.1.md`
- **evidence:** doc/migration-guides/v0.2.0-to-v0.2.1.md:27:std::size_t ValidActionsInto( doc/migration-guides/v0.2.0-to-v0.2.1.md:147:  template still carry a `TODO(policy_head_layout=compact)` marker on

### azapi-cx-v003-root-namespace-rename

- **slice:** design-doc · **difficulty:** easy · **source:** codex
- **Q:** One early migration in this project changed the library's top-level namespace. Which version's migration guide documents that rename, what were the old and new namespace names, and what command does it suggest for locating affected spots?
- **A:** The v0.0.2-to-v0.0.3 migration guide documents renaming the project root namespace from alphazero to az. It supplies a shell helper that runs `grep -rn 'alphazero'` over a directory to find every occurrence that needs changing, plus a dry-run/--apply replacement script.
- **sentinels:** `Changed project root namespace from `alphazero` to `az``, `grep -rn 'alphazero'`
- **primary:** `doc/migration-guides/v0.0.2-to-v0.0.3.md`
- **evidence:** doc/migration-guides/v0.0.2-to-v0.0.3.md:3:Changed project root namespace from `alphazero` to `az`. You may use the; doc/migration-guides/v0.0.2-to-v0.0.3.md:21:grep -rn 'alphazero' "$1"

### azapi-cx-v005-explicit-error-type-param

- **slice:** design-doc · **difficulty:** medium · **source:** codex
- **Q:** In the v0.0.4-to-v0.0.5 transition, what did the game interface start requiring for its string-to-action parsing, and what absl-style naming convention does the guide recommend adopting for the new typed errors and result wrappers?
- **A:** The interface IGame began taking an explicit error-type template parameter used by ActionFromString(), so parsing returns a typed result rather than a string error. The guide recommends absl-style aliases such as TttError, TttResult<T>, and TttStatus, e.g. instantiating IGame<TttBoard, TttAction, TttPlayer, TttError>.
- **sentinels:** `explicit error type parameter for `ActionFromString()``, `TttResult<T>`
- **primary:** `doc/migration-guides/v0.0.4-to-v0.0.5.md`
- **evidence:** doc/migration-guides/v0.0.4-to-v0.0.5.md:3:`IGame` now takes an explicit error type parameter for `ActionFromString()`.; doc/migration-guides/v0.0.4-to-v0.0.5.md:4:For example, prefer absl-style naming like `TttError`, `TttResult<T>`, and
