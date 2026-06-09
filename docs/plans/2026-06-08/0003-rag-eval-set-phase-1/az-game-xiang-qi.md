# RAG eval set — `az-game-xiang-qi`

- **Repo root:** `/Users/shuyang/developer/alpha-zero/az-game-xiang-qi`
- **Questions:** 33  ·  domain {'code': 27, 'nl': 6}  ·  difficulty {'easy': 4, 'hard': 12, 'medium': 17}  ·  source {'claude': 21, 'codex': 12}
- **Code corpus (`domain=code`):** src/ include/ tests/ (9x10 board, piece rules, flying-general, move/tensor encoding), gui/ (TS/TSX)
- **Prose corpus (`domain=nl`):** memory/ (game_design(+details/), game_rules(+details/), gui_design, history_lookback, …)
- **Note:** C++ Xiang Qi (Chinese Chess) implementing the contract, plus a TS/TSX GUI; code + design-doc questions.

Each entry is a gold fact for retrieval eval: a paraphrased **Q** (never containing its own sentinel), the grounded **A**, the exact **sentinels** that occur verbatim in the **primary** file(s), and the `domain`/`difficulty` slice. Sources/paths are relative to the repo root above. Every sentinel below was re-verified against the primary file's raw bytes at build time.

## `domain = code` (27)

### xq-board-dims-and-cells

- **slice:** codebase · **difficulty:** easy · **source:** claude
- **Q:** In the C++ engine, what are the row and column counts of the Xiang Qi board, and how is the total intersection count derived from them?
- **A:** The header defines kBoardRows = 10 and kBoardCols = 9, and the total cell count is kBoardCells = kBoardRows * kBoardCols (90). Each cell is stored as one signed byte in a flat row-major array.
- **sentinels:** `kBoardRows = 10`, `kBoardCols = 9`, `kBoardCells = kBoardRows * kBoardCols`
- **primary:** `include/xq/game.h`
- **evidence:** include/xq/game.h:25: constexpr uint8_t kBoardRows = 10; \| include/xq/game.h:26: constexpr uint8_t kBoardCols = 9; \| include/xq/game.h:27: constexpr uint8_t kBoardCells = kBoardRows * kBoardCols;  // 90

### xq-action-space-size

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** How big is the fixed dense policy head, and why is it that size even though most slots are illegal moves?
- **A:** The full action space is kPolicySize = static_cast<size_t>(kBoardCells) * kBoardCells, i.e. 90*90 = 8100, because every (from, to) cell pair gets a slot via PolicyIndex(a) = a.from * kBoardCells + a.to. Physically impossible moves are still valid slots; they are masked out by ValidActionsInto() and stay zero.
- **sentinels:** `kPolicySize`, `static_cast<size_t>(kBoardCells) * kBoardCells`, `8100`
- **primary:** `include/xq/game.h`
- **evidence:** include/xq/game.h:135: static constexpr size_t kPolicySize = \| include/xq/game.h:136: static_cast<size_t>(kBoardCells) * kBoardCells; \| include/xq/game.h:131: `[0, kBoardCells^2) = [0, 8100)`.

### xq-cannon-screen-capture

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** In the attack-detection helper for the jumping artillery piece, what exact condition determines that it can capture a target along a rank or file?
- **A:** CannonAttacks counts the non-empty cells strictly between source and target and returns true only when screens == 1 — exactly one intervening piece (the screen). This differs from its non-capturing move semantics, which require zero pieces in between.
- **sentinels:** `CannonAttacks`, `screens == 1`, `the screen`
- **primary:** `src/xq/game/internal.cc`
- **evidence:** src/xq/game/internal.cc:158: bool CannonAttacks(const XqB& board, uint8_t from, uint8_t target) noexcept { \| src/xq/game/internal.cc:184:   return screens == 1; \| src/xq/game/internal.cc:161: one piece — the screen — between source and target).

### xq-cannon-move-two-phase

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** Walk through how the cannon's pseudo-legal move generator emits both its quiet slides and its capture; what is the two-phase loop doing?
- **A:** EmitCannonMoves runs a phase 1 that emits every empty cell along a direction (identical to a chariot slide), then after hitting the first blocker it skips exactly one screen and, in phase 2, scans onward for the first non-empty cell and emits a capture if that piece is an enemy. The comment marks this as 'Phase 2: skip exactly one screen, then look for an enemy capture.'
- **sentinels:** `EmitCannonMoves`, `Phase 2: skip exactly one screen`, `Phase 1: empty cells`
- **primary:** `src/xq/game/internal.cc`
- **evidence:** src/xq/game/internal.cc:329: void EmitCannonMoves(const XqB& board, uint8_t from, XqP player, \| src/xq/game/internal.cc:347:     // Phase 2: skip exactly one screen, then look for an enemy capture. \| src/xq/game/internal.cc:335:     // Phase 1: empty cells.

### xq-flying-general-rule

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** How does the engine detect the illegal face-to-face kings position, and how is that check integrated into move legality filtering?
- **A:** IsFlyingGenerals finds both generals, returns false unless they share a column, then scans the cells between them and returns true only if every intervening cell is empty. ValidActionsInto applies each pseudo-legal move on a scratch board and keeps it only if !IsInCheck(...) && !IsFlyingGenerals(scratch).
- **sentinels:** `IsFlyingGenerals`, `!IsFlyingGenerals(scratch)`
- **primary:** `src/xq/game/internal.cc`, `src/xq/game/action.cc`
- **evidence:** src/xq/game/internal.cc:469: bool IsFlyingGenerals(const XqB& board) noexcept { \| src/xq/game/action.cc:60:     !internal::IsInCheck(scratch, current_player_) && !IsFlyingGenerals(scratch);

### xq-horse-hobbling-leg

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** For the L-shaped piece, how does the move generator implement the rule that an adjacent blocker prevents the move, and how is the blocking cell computed for each of the eight targets?
- **A:** EmitHorseMoves stores eight Move structs each carrying the L-target offsets (dr, dc) and the orthogonal leg offsets (leg_dr, leg_dc); for each target it computes the leg cell and skips the move if that cell is not kEmpty (the 'hobbling' block). The attack helper HorseAttacks does the same by deriving leg_r/leg_c from whether the move is (±2,±1) or (±1,±2).
- **sentinels:** `EmitHorseMoves`, `leg_dr`, `HorseAttacks`
- **primary:** `src/xq/game/internal.cc`
- **evidence:** src/xq/game/internal.cc:271: void EmitHorseMoves(const XqB& board, uint8_t from, XqP player, \| src/xq/game/internal.cc:276:     int dr, dc, leg_dr, leg_dc; \| src/xq/game/internal.cc:114: bool HorseAttacks(const XqB& board, uint8_t from, uint8_t target) noexcept {

### xq-elephant-river-and-eye

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** What two constraints does the diagonal two-step piece's move generator enforce beyond basic bounds, and which helper decides the river constraint?
- **A:** EmitElephantMoves skips a target if !OnOwnSide(tr, player) ('Cannot cross river') and also skips it if the intermediate eye cell at (r + dr/2, c + dc/2) is not kEmpty ('Eye blocked'). OnOwnSide returns true when the row is on the player's own half (Red rows 0..4, Black rows 5..9).
- **sentinels:** `OnOwnSide`, `Cannot cross river`, `Eye blocked`
- **primary:** `src/xq/game/internal.cc`
- **evidence:** src/xq/game/internal.cc:254:     if (!OnOwnSide(tr, player)) continue;  // Cannot cross river \| src/xq/game/internal.cc:259:       continue;  // Eye blocked

### xq-soldier-river-crossing

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** How does the pawn move generator decide whether sideways steps are allowed, and how does the forward direction depend on color?
- **A:** EmitSoldierMoves sets forward = player ? -1 : 1 (Black moves to lower rows, Red higher) and always tries the forward step; it only adds the left/right steps once the soldier has crossed the river, computed as crossed = player ? (r <= 4) : (r >= 5).
- **sentinels:** `EmitSoldierMoves`, `const bool crossed = player ? (r <= 4) : (r >= 5);`
- **primary:** `src/xq/game/internal.cc`
- **evidence:** src/xq/game/internal.cc:367: void EmitSoldierMoves(const XqB& board, uint8_t from, XqP player, \| src/xq/game/internal.cc:374:   const bool crossed = player ? (r <= 4) : (r >= 5);

### xq-canonical-board-rotate-negate

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** When it is Black's turn, how is the perspective-normalized board produced so the side to move always sees its own pieces as positive and advancing upward?
- **A:** CanonicalBoard returns board_ unchanged for Red, but for Black it negates every non-zero cell and rotates 180 degrees by reading from board_[(kBoardRows - 1 - r) * kBoardCols + (kBoardCols - 1 - c)]. The matching action remap RotateCellForBlack applies the same 180-degree cell rotation so policy slots line up.
- **sentinels:** `CanonicalBoard`, `(kBoardRows - 1 - r) * kBoardCols + (kBoardCols - 1 - c)`, `RotateCellForBlack`
- **primary:** `src/xq/game/state.cc`
- **evidence:** src/xq/game/state.cc:50: XqB XqGame::CanonicalBoard() const noexcept { \| src/xq/game/state.cc:56:           board_[(kBoardRows - 1 - r) * kBoardCols + (kBoardCols - 1 - c)]; \| src/xq/game/state.cc:17: uint8_t RotateCellForBlack(uint8_t cell) noexcept {

### xq-dense-serializer-planes

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** How many feature planes does the dense state serializer emit, how are own vs opponent pieces split across them, and how is the side-to-move signaled?
- **A:** The dense layout uses kStateFeaturePlanes = 15 planes of 90 cells: planes 0..6 are own pieces, 7..13 are opponent pieces (computed on CanonicalBoard so the split is automatic), and plane 14 is the side-to-move plane filled with 1.0 only when Red is to move via PlaneOffset(14).
- **sentinels:** `kStateFeaturePlanes = 15`, `PlaneOffset(14)`, `SerializeBoardState`
- **primary:** `include/xq/serializer.h`, `src/xq/serializer/serializer.cc`
- **evidence:** include/xq/serializer.h:14: inline constexpr size_t kStateFeaturePlanes = 15; \| src/xq/serializer/serializer.cc:64:     const size_t base = PlaneOffset(14); \| src/xq/serializer/serializer.cc:44: std::vector<float> SerializeBoardState(const XqGame& game) noexcept {

### xq-compact-token-layout

- **slice:** codebase · **difficulty:** hard · **source:** claude
- **Q:** In the transformer-oriented compact state encoding, how many tokens are there, what width is each, and how are padded legal-action slots distinguished from real moves?
- **A:** The compact state is kCompactStateTokenCount = 195 tokens (90 board + 1 repeat counter + 104 action slots), each kCompactTokenFeatureWidth = 2 floats wide, total 390. Padded action slots reuse the no-action sentinel via kCompactActionPadValue = static_cast<float>(kBoardCells), i.e. 90, so they never collide with a real (from, to) pair.
- **sentinels:** `kCompactStateTokenCount`, `kCompactTokenFeatureWidth`, `kCompactActionPadValue`
- **primary:** `include/xq/serializer.h`, `src/xq/serializer/serializer.cc`
- **evidence:** include/xq/serializer.h:37: inline constexpr size_t kCompactStateTokenCount = \| include/xq/serializer.h:36: inline constexpr size_t kCompactTokenFeatureWidth = 2; \| src/xq/serializer/serializer.cc:34: constexpr float kCompactActionPadValue = static_cast<float>(kBoardCells);

### xq-max-legal-and-max-rounds

- **slice:** codebase · **difficulty:** easy · **source:** claude
- **Q:** What is the engine's hard cap on legal moves per state and its hard cap on plies before a forced draw?
- **A:** kMaxLegalActions = 104 is the per-state legal-action ceiling used to size compact policy heads, and kMaxRounds is set to static_cast<uint32_t>(300) (150 moves per side); once CurrentRound() reaches that, IsOver() reports a technical draw.
- **sentinels:** `kMaxLegalActions = 104`, `static_cast<uint32_t>(300)`
- **primary:** `include/xq/game.h`
- **evidence:** include/xq/game.h:147:   static constexpr size_t kMaxLegalActions = 104; \| include/xq/game.h:159:       static_cast<uint32_t>(300);

### xq-zobrist-seed-and-black-key

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** How is the repetition-detection hash key table generated deterministically at compile time, and what extra key encodes whose turn it is?
- **A:** A constexpr xorshift64 PRNG (Xorshift64) seeded with 0x9E3779B97F4A7C15ULL fills the per-(cell, piece-code) key table in MakeZobristPieceKeys, and a separate fixed-seed key kZobristBlackToMove is XOR'd into the running hash when it is Black's turn to move. Same keys every run, no platform variance.
- **sentinels:** `0x9E3779B97F4A7C15ULL`, `kZobristBlackToMove`, `MakeZobristPieceKeys`
- **primary:** `src/xq/game/internal.cc`
- **evidence:** src/xq/game/internal.cc:30:   Xorshift64 prng{0x9E3779B97F4A7C15ULL}; \| src/xq/game/internal.cc:206: const uint64_t kZobristBlackToMove = MakeZobristBlackKey(); \| src/xq/game/internal.cc:28: constexpr auto MakeZobristPieceKeys() noexcept {

### xq-undo-capture-packing

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** When a move is applied, how is the captured piece recorded so it can be restored on undo without an external table, and how does the bit layout encode the captured piece's color?
- **A:** ApplyActionInPlace stores PackCaptured(captured) into apply_undo_log_, which packs the captured piece into one byte: bit 7 set if the captured piece was Black and bits 0..6 hold the piece-type magnitude (0 if no capture). UnpackCaptured reverses this so UndoLastAction can put the piece back.
- **sentinels:** `PackCaptured`, `apply_undo_log_`, `UnpackCaptured`
- **primary:** `src/xq/game/action.cc`
- **evidence:** src/xq/game/action.cc:25: constexpr uint8_t PackCaptured(int8_t code) noexcept { \| src/xq/game/action.cc:95:     apply_undo_log_[round_] = PackCaptured(captured); \| src/xq/game/action.cc:31: constexpr int8_t UnpackCaptured(uint8_t packed) noexcept {

### xq-history-lookback-zero

- **slice:** codebase · **difficulty:** easy · **source:** claude
- **Q:** How many past states does the serializer require from the engine's history buffer, and what is the stated reason it can stay at that value?
- **A:** kHistoryLookback = 0 because Xiang Qi is treated as Markov from the network's point of view; threefold repetition is tracked inside XqGame via a Zobrist hash log, so the serializer never needs past states, and keeping it at 0 avoids inflating the per-node RingBuffer history.
- **sentinels:** `kHistoryLookback = 0`, `Zobrist hash log`
- **primary:** `include/xq/game.h`
- **evidence:** include/xq/game.h:123: static constexpr size_t kHistoryLookback = 0; \| include/xq/game.h:424: // Per-round Zobrist hash log. `position_history_[i]` is the hash

### xq-gui-piece-glyphs-and-markers

- **slice:** codebase · **difficulty:** medium · **source:** claude
- **Q:** In the browser board renderer, how are piece characters chosen per color, and which intersections get the decorative corner-bracket marks?
- **A:** The board uses two indexed arrays, RED_CHARS and BLACK_CHARS, mapping the piece-type magnitude (1..7) to its Chinese glyph, and draws corner brackets at the cannon/pawn launch points listed in POSITION_MARKERS (e.g. red cannons at [2,1] and [2,7], pawns on row 3, mirrored for black).
- **sentinels:** `RED_CHARS`, `BLACK_CHARS`, `POSITION_MARKERS`
- **primary:** `gui/src/components/xiangqi/XiangQiBoard.tsx`
- **evidence:** gui/src/components/xiangqi/XiangQiBoard.tsx:17: const RED_CHARS = ['', '帥', '仕', '相', '馬', '車', '砲', '兵'] \| gui/src/components/xiangqi/XiangQiBoard.tsx:18: const BLACK_CHARS = ['', '將', '士', '象', '傌', '俥', '炮', '卒'] \| gui/src/components/xiangqi/XiangQiBoard.tsx:27: const POSITION_MARKERS: ReadonlyArray<readonly [row: number, col: number]> = [

### xq-cx-policy-slot-canonical-sharing

- **slice:** codebase · **difficulty:** hard · **source:** codex
- **Q:** When the serializer scatters move probabilities into the dense policy head, how does it guarantee that equivalent moves for the two players land in the same output slot regardless of whose turn it is?
- **A:** The serializer maps every legal move through the canonical action transform before computing its policy index, writing each probability to out[1 + PolicyIndex(CanonicalAction(a))]. Because the canonical transform rotates Black's frame to match Red's, an 'own piece advances' move resolves to the same slot for either side.
- **sentinels:** `out[1 + PolicyIndex(CanonicalAction(a_i))]   = target.pi[i]`, `game.PolicyIndex(game.CanonicalAction(actions[i]))`, `const XqA canonical_action = game.CanonicalAction(actions[i]);`
- **primary:** `src/xq/serializer/serializer.cc`, `include/xq/game.h`
- **evidence:** src/xq/serializer/serializer.cc:134:   //   out[1 + PolicyIndex(CanonicalAction(a_i))]   = target.pi[i] \| src/xq/serializer/serializer.cc:148:     const size_t slot = 1 + game.PolicyIndex(game.CanonicalAction(actions[i])); \| src/xq/serializer/serializer.cc:78:     const XqA canonical_action = game.CanonicalAction(actions[i]);

### xq-cx-dense-deserializer-length-contract

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** What exact length must a dense policy/value output span have for the deserializer to accept it, and what happens when the length is wrong?
- **A:** The dense deserializer requires the float span to be exactly kPolicySize + 1 long (the value scalar plus one slot per policy index). If output.size() does not equal that, it returns an error rather than parsing the buffer.
- **sentinels:** `constexpr size_t kExpected = XqGame::kPolicySize + 1;`, `kInvalidPolicyOutputSize`, `output.size() != kExpected`
- **primary:** `src/xq/deserializer/deserializer.cc`
- **evidence:** src/xq/deserializer/deserializer.cc:29:   constexpr size_t kExpected = XqGame::kPolicySize + 1; \| src/xq/deserializer/deserializer.cc:30:   if (output.size() != kExpected) { \| src/xq/deserializer/deserializer.cc:31:     return std::unexpected(XqError::kInvalidPolicyOutputSize);

### xq-cx-compact-policy-target-ordering

- **slice:** codebase · **difficulty:** hard · **source:** codex
- **Q:** In the transformer-oriented training target, how is each policy-target row kept aligned with the corresponding legal-action input token, and what comparator establishes that order?
- **A:** The compact policy target blob serializes the legal-action features in the same sorted order used for the input action tokens, applying the LegalActionFeatureLess comparator so row i of the target corresponds to input token i; unused rows use the blob's padding slot constant. Changing this sort or padding is a breaking ABI change.
- **sentinels:** `CompactPolicyTargetBlob`, `LegalActionFeatureLess`, `CompactPolicyTargetBlob::kPaddingSlot`
- **primary:** `src/xq/serializer/serializer.cc`, `include/xq/serializer.h`
- **evidence:** src/xq/serializer/serializer.cc:174: ::az::game::api::CompactPolicyTargetBlob \| src/xq/serializer/serializer.cc:82:   std::sort(features.begin(), features.end(), LegalActionFeatureLess); \| src/xq/serializer/serializer.cc:196:         ::az::game::api::CompactPolicyTargetBlob::kPaddingSlot);

### xq-cx-termination-priority-order

- **slice:** codebase · **difficulty:** hard · **source:** codex
- **Q:** In what order does the engine evaluate end-of-game conditions, and why does that ordering matter when a forced-loss position coincides with the move limit?
- **A:** IsOver and GetScore both resolve conditions in a fixed priority: a missing general first, then no-legal-move (checkmate/stalemate), then threefold repetition, then the max-rounds cap. No-legal-move is checked before the round cap, so a position that is checkmate at or past the limit is still scored as a win/loss for the relevant side rather than collapsing to a draw.
- **sentinels:** `Termination priority`, `HasAnyLegalMove(board_, current_player_)`, `if (kMaxRounds.has_value() && round_ >= *kMaxRounds) return true;`
- **primary:** `src/xq/game/state.cc`, `memory/game_rules_details/termination.md`
- **evidence:** src/xq/game/state.cc:100:   // Termination priority — see \| src/xq/game/state.cc:113:   if (!HasAnyLegalMove(board_, current_player_)) return true; \| src/xq/game/state.cc:117:   if (kMaxRounds.has_value() && round_ >= *kMaxRounds) return true;

### xq-cx-snapshot-undo-unavailable

- **slice:** codebase · **difficulty:** hard · **source:** codex
- **Q:** How can a snapshot-constructed game report its most recent move yet still silently refuse to take it back?
- **A:** The snapshot constructor can seed the previous action-history slot from the supplied last move so observers can read it, but it records the undo-metadata sentinel meaning capture info and older history are unknown. The take-back routine returns without mutating when the stored action is a no-action or the undo metadata equals that unavailable sentinel.
- **sentinels:** `kUndoUnavailable`, `apply_undo_log_[current_round - 1] = kUndoUnavailable;`, `apply_undo_log_[previous_round] == kUndoUnavailable`
- **primary:** `src/xq/game/constructors.cc`, `src/xq/game/action.cc`
- **evidence:** src/xq/game/constructors.cc:113:       apply_undo_log_[current_round - 1] = kUndoUnavailable; \| src/xq/game/action.cc:110:       apply_undo_log_[previous_round] == kUndoUnavailable) { \| src/xq/game/action.cc:28: using ::az::game::xq::internal::kUndoUnavailable;

### xq-cx-mirror-transform-mechanics

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** How does the augmentation code actually reflect a board across the central file, and how are the resulting variants enumerated?
- **A:** A single-cell helper reflects a cell as (r, c) -> (r, kBoardCols - 1 - c), and the board mirror applies it to every cell while leaving piece codes (colors) unchanged. The augmentation enumerator returns two variants in enum order: the identity kOriginal and the column mirror kMirrorHorizontal.
- **sentinels:** `MirrorCell`, `kBoardCols - 1 - c`, `kMirrorHorizontal`
- **primary:** `src/xq/augmentation/augmentation.cc`, `include/xq/augmentation.h`
- **evidence:** src/xq/augmentation/augmentation.cc:16: constexpr uint8_t MirrorCell(uint8_t cell) noexcept { \| src/xq/augmentation/augmentation.cc:19:   return Idx(r, static_cast<uint8_t>(kBoardCols - 1 - c)); \| include/xq/augmentation.h:32:   kMirrorHorizontal = 1,

### xq-cx-inference-vs-train-inverse-mapping

- **slice:** codebase · **difficulty:** hard · **source:** codex
- **Q:** How do the inference and training augmentation paths each use inverse action transforms, and how do their goals differ?
- **A:** Inference builds a lookup from each original-frame action's policy index to its slot, then for each augmented variant inverse-maps the variant's actions back to the original action and averages values and probabilities across variants. Training instead emits augmented (game, target) pairs: for each variant action it inverse-maps to the original action, gathers the original target probability by policy index, and keeps the original value target.
- **sentinels:** `slot_for_policy_index`, `internal::AugmentAll(game)`, `variant_count`
- **primary:** `src/xq/inference/inference.cc`, `src/xq/train/train.cc`
- **evidence:** src/xq/inference/inference.cc:30:     slot_for_policy_index[original.PolicyIndex(orig_actions[i])] = i; \| src/xq/inference/inference.cc:56:     ++variant_count; \| src/xq/train/train.cc:23:   std::vector<XqGame> variants = internal::AugmentAll(game);

### xq-cx-action-string-notation-and-errors

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** What human-readable move notation does the engine parse, what preprocessing and error reporting does the parser apply, and where is this codec mirrored in the GUI?
- **A:** Moves use a column-letter/row-digit form for source and destination separated by a dash, where columns are letters and row 0 is Red's back rank. The C++ parser trims whitespace, lowercases the column letters, and returns distinct typed errors for a bad source cell versus a bad destination cell. The GUI's kit.ts reimplements the same pure codec using the row * 9 + col mapping.
- **sentinels:** `ActionFromString`, `kInvalidActionFromCell`, `<from_col><from_row>-<to_col><to_row>`
- **primary:** `src/xq/game/string_conv.cc`, `memory/game_design_details/action_encoding.md`, `gui/src/kit.ts`
- **evidence:** src/xq/game/string_conv.cc:91: XqResult<XqA> XqGame::ActionFromString( \| src/xq/game/string_conv.cc:100:     return std::unexpected(XqError::kInvalidActionFromCell); \| memory/game_design_details/action_encoding.md:50: <from_col><from_row>-<to_col><to_row>

### xq-cx-wasm-apply-by-index-safety

- **slice:** codebase · **difficulty:** hard · **source:** codex
- **Q:** How does the browser front end apply a user's move through the compiled engine without letting fabricated illegal moves reach the C++ core?
- **A:** The WASM binding does not accept arbitrary (from, to) pairs; it exposes a method that applies a move by its index into the engine's own legal-action list, which it regenerates and bounds-checks. The TypeScript wrapper first locates the chosen action inside the current snapshot's valid actions and only then calls that indexed method, so the engine only ever applies a move it generated itself.
- **sentinels:** `applyValidActionByIndex`, `EMSCRIPTEN_BINDINGS`, `this.gameJs.applyValidActionByIndex(index)`
- **primary:** `src/wasm/bindings.cc`, `gui/src/engine/xq-game.ts`
- **evidence:** src/wasm/bindings.cc:82:   void applyValidActionByIndex(uint32_t idx) { \| src/wasm/bindings.cc:296: EMSCRIPTEN_BINDINGS(xq_module) { \| gui/src/engine/xq-game.ts:53:     this.gameJs.applyValidActionByIndex(index)

### xq-cx-gamekit-server-payload-no-history

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** What fields does the GUI's reusable kit send upstream to represent a position, why does it copy the board out of its raw typed array, and why is there no past-states field?
- **A:** The kit encodes a JSON-serializable payload of the board, the current player, and the current round; it copies the board out of the Int8Array into a plain number[] because JSON.stringify on a typed array produces an object-keyed mess. There is no history field because the configured history lookback is 0 and the repetition state the game needs lives inside the engine.
- **sentinels:** `encodeSnapshotForServer`, `current_round: s.currentRound,`, `historyLookback: 0,`
- **primary:** `gui/src/kit.ts`
- **evidence:** gui/src/kit.ts:165: export function encodeSnapshotForServer(s: Snapshot): ServerStatePayload { \| gui/src/kit.ts:173:     current_round: s.currentRound, \| gui/src/kit.ts:189:     historyLookback: 0,

### xq-cx-build-ci-presets-and-pinned-api

- **slice:** codebase · **difficulty:** medium · **source:** codex
- **Q:** What C++ standard and pinned upstream API version does the build use, how are unit tests gated, and how does CI smoke-test the built binary?
- **A:** The project builds against C++23 and pins the upstream API dependency to a fixed git tag; unit tests are gated behind a BUILD_TESTING option that defaults off and is turned on by the dedicated test presets. CI configures and builds both the debug-test and release-test presets, runs the interactive xq binary with stdin redirected from /dev/null so it exits on EOF, then runs ctest.
- **sentinels:** `ALPHA_ZERO_API_GIT_TAG`, `BUILD_TESTING`, `./build/${{ matrix.build_dir }}/xq </dev/null`
- **primary:** `CMakeLists.txt`, `.github/workflows/ci.yml`
- **evidence:** CMakeLists.txt:14: set(ALPHA_ZERO_API_GIT_TAG \| CMakeLists.txt:29: option(BUILD_TESTING "Build unit tests" OFF) \| .github/workflows/ci.yml:28:         run: ./build/${{ matrix.build_dir }}/xq </dev/null

## `domain = nl` (6)

### xq-doc-piece-codes-table

- **slice:** design-doc · **difficulty:** easy · **source:** claude
- **Q:** In the board-encoding design doc, what does the sign versus magnitude of a cell's signed byte represent, and what magnitude code identifies the red side's screen-capturing artillery piece?
- **A:** Per board_encoding.md the sign distinguishes color (positive = Red, negative = Black) and the magnitude indexes the piece type; the Red Cannon is code +6, with the Red Soldier at +7 and the General at +1.
- **sentinels:** `Sign distinguishes color`, `+6`
- **primary:** `memory/game_design_details/board_encoding.md`
- **evidence:** memory/game_design_details/board_encoding.md:28: Sign distinguishes color; magnitude indexes piece type. The \| memory/game_design_details/board_encoding.md:18: \| +6   \| Red Cannon        \|

### xq-doc-stalemate-asian-rule

- **slice:** design-doc · **difficulty:** medium · **source:** claude
- **Q:** How does the rules doc say a side with zero legal moves but not in check is scored, and how does that differ from Western chess?
- **A:** special_rules.md states that by Asian Xiang Qi rules the side to move still loses even when not in check (a stalemate is a loss), whereas Western chess scores this as a draw; this implementation follows the Asian convention.
- **sentinels:** `Asian convention`, `still loses`, `Western chess scores this as a draw`
- **primary:** `memory/game_rules_details/special_rules.md`
- **evidence:** memory/game_rules_details/special_rules.md:37: move still loses. (Western chess scores this as a draw; this \| memory/game_rules_details/special_rules.md:38: implementation follows the Asian convention.)

### xq-doc-repetition-zobrist-array

- **slice:** design-doc · **difficulty:** medium · **source:** claude
- **Q:** In the repetition-tracking design note, how many random hash keys make up the per-cell piece table, and how is the per-ply hash log array sized?
- **A:** repetition.md specifies one key per (cell, piece-code) pair giving 90 cells × 14 piece codes = 1260 random keys plus a 'Black to move' key, and position_history_ is std::array<uint64_t, 301>, sized to kMaxRounds + 1 so it covers both the initial position and the position after the final allowed ply.
- **sentinels:** `90 cells × 14 piece`, `std::array<uint64_t, 301>`
- **primary:** `memory/game_design_details/repetition.md`
- **evidence:** memory/game_design_details/repetition.md:12: One key per (cell, piece-code) pair: 90 cells × 14 piece \| memory/game_design_details/repetition.md:26: `position_history_` is `std::array<uint64_t, 301>` — sized to

### xq-doc-symmetry-only-mirror

- **slice:** design-doc · **difficulty:** hard · **source:** claude
- **Q:** According to the augmentation design, which single board symmetry is exploited for training, and why are rotations and vertical flips excluded?
- **A:** augmentation.h's doc and game_rules_details/board.md explain Xiang Qi has a single useful symmetry, a left/right mirror across the central file (column 4); the river divides the two sides asymmetrically and the palaces are tied to specific files, so rotations and the vertical flip are not symmetries, giving kNumAugmentations = 2.
- **sentinels:** `central file (column 4)`, `kNumAugmentations = 2`, `left-right symmetric`
- **primary:** `include/xq/augmentation.h`, `memory/game_rules_details/board.md`
- **evidence:** include/xq/augmentation.h:16:  * across the central file (column 4). The river divides the two \| include/xq/augmentation.h:40: inline constexpr size_t kNumAugmentations = 2; \| memory/game_rules_details/board.md:57: - The board is **left-right symmetric** along the central file

### xq-doc-cannon-screen-rule

- **slice:** design-doc · **difficulty:** medium · **source:** claude
- **Q:** How does the pieces rules doc describe the artillery piece's capture requirement versus its non-capturing movement?
- **A:** pieces.md says the Cannon moves without capturing exactly like a Chariot (any number of empty intersections), but to capture it must jump exactly one piece called the 'screen' between itself and the target; the screen may be friendly or enemy, the target must be enemy, and it never captures without a screen or with more than one.
- **sentinels:** `screen`, `The screen may be`, `jump exactly one piece`
- **primary:** `memory/game_rules_details/pieces.md`
- **evidence:** memory/game_rules_details/pieces.md:63: "screen") between itself and the target. The screen may be \| memory/game_rules_details/pieces.md:62: Capture move: must jump exactly one piece (called the

### xq-cx-apply-undo-allocation-free-constraint

- **slice:** design-doc · **difficulty:** medium · **source:** codex
- **Q:** Per the MCTS performance notes, why must the in-place move and its reversal avoid heap allocation entirely, and what validation does the move-apply path deliberately skip?
- **A:** The constraints doc explains that these calls run once per expanded MCTS edge, so a single allocation per call would balloon into hundreds of millions of allocations across a training cycle; computation must stay in stack-local fixed-size buffers. To stay on the hot path, the apply routine does not validate its input action.
- **sentinels:** `hundreds of millions of allocations across a training cycle`, `keep computation in stack-local`, `does not validate`
- **primary:** `memory/mcts_constraints.md`
- **evidence:** memory/mcts_constraints.md:29: hundreds of millions of allocations across a training cycle. \| memory/mcts_constraints.md:36: - Do not allocate scratch space — keep computation in stack-local \| memory/mcts_constraints.md:88: called on the MCTS hot path — `ApplyActionInPlace` does not validate
