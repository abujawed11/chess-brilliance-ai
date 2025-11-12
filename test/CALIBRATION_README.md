# Chess.com Calibration Tool - Setup Guide

## Overview

This calibration tool helps validate chess move grading against Chess.com labels by analyzing moves with Stockfish and logging feature data for model training.

## 🚀 Quick Start (Auto-Analysis)

**Analyze an entire PGN automatically in 3 steps:**

1. **Start the Flask server**: 
   ```bash
   cd test
   python app.py
   ```

2. **Open the tool**: Navigate to `http://localhost:5000` and open `callibrator.html`

3. **Run Auto-Analysis**:
   - Click **"Start Analysis Engine"** (green button)
   - Upload your PGN file or paste PGN text
   - Click **"Load PGN"**
   - Click **"🚀 Start Auto-Analysis"** (blue button)
   - Wait for completion (progress shown in real-time)
   - Edit labels in the table if needed
   - Click **"Download JSON"** to save results

**That's it!** All moves are analyzed and logged automatically. ✨

## Recommended Settings

### Engine Configuration

**For optimal calibration quality:**

- **Depth**: 18-22
  - Depth 18: Fast, good for most positions (~0.5-1s per move)
  - Depth 22: More accurate, recommended for critical positions (~1-2s per move)

- **MultiPV (BEFORE position)**: 3-5
  - MultiPV 3: Minimum for rank detection
  - MultiPV 5: Recommended for better gap calculation and ranking
  - Higher values increase analysis time linearly

- **MultiPV (AFTER position)**: 1
  - Only need best move for evaluation after the played move
  - Reduces analysis time by ~50%

### Persistent Engine

**Always use the persistent engine for calibration:**

1. Click **"Start Analysis Engine"** before loading PGN
2. Engine stays running with 512MB hash and 2 threads
3. Significantly faster: <1s per move vs 3-4s with temporary engine
4. Click **"Stop Analysis Engine"** when done

### Hardware Considerations

- **Minimum**: 2 cores, 4GB RAM
- **Recommended**: 4+ cores, 8GB+ RAM
- **Hash Table**: 512MB (set automatically)
- **Threads**: 2 (default, increase for faster CPUs)

## Data Quality Guarantees

The system ensures:

1. **No rank=99**: Moves not in PVs get rank = K+1 (where K = MultiPV count)
2. **Consistent gaps**: If rank > 1, top_gap is strictly positive; if move not found, top_gap = null
3. **Single normalization**: All evals use `to_root_cp()` - consistent perspective, no manual sign flips
4. **Typed scores**: Mate scores stay structured (no ±100000 flattening)
5. **BEFORE FEN**: Logged samples store the FEN before the move, not after
6. **Null handling**: top_gap shows "—" when move not in PVs

## Usage Workflow

### Three Modes of Operation

#### **Mode 1: PGN Auto-Analysis (Recommended - Fully Automated)**

1. **Start Engine**: Click "Start Analysis Engine" (green button)
2. **Load PGN**: Upload file or paste PGN text
3. **Auto-Analyze**: Click "🚀 Start Auto-Analysis" (blue button)
   - System automatically plays through ALL moves
   - Engine analyzes each move with MultiPV settings
   - All moves are logged automatically with engine labels
   - Progress is shown in real-time
   - Can be stopped mid-analysis by clicking the button again
4. **Review & Edit Labels**: After completion, review the logged samples table
   - Click any label cell to change it (e.g., from "Best" to "Brilliant")
   - Labels can be updated based on Chess.com analysis
5. **Export**: Click "Download JSON" to save calibration dataset
6. **Stop Engine**: Click "Stop Analysis Engine" when done

**Performance**: At depth 22, MultiPV 5, expect ~1-2s per move. A 40-move game takes 1-2 minutes.

#### **Mode 2: PGN Manual Navigation (Replay Games Step-by-Step)**

1. **Start Engine**: Click "Start Analysis Engine" (green button)
2. **Load PGN**: Upload file or paste PGN text
3. **Navigate Moves**:
   - Click "Next ▶" to evaluate and advance
   - Engine analyzes BEFORE position with MultiPV=5
   - Engine analyzes AFTER position with MultiPV=1
4. **Log Samples**: Click "Log Current Move" to save feature data
5. **Export**: Click "Download JSON" to save calibration dataset
6. **Stop Engine**: Click "Stop Analysis Engine" (red button) when done

#### **Mode 3: FEN Manual Play (Analyze Specific Positions)**

1. **Start Engine**: Click "Start Analysis Engine" (green button)
2. **Load FEN**: Paste a FEN string (e.g., `rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1`)
3. **Click "Set Position"**: Board updates to that position
4. **Play Moves**: Click-based move selection
   - Click on a piece to select it (highlighted in **yellow**)
   - Legal moves are shown in **light green**
   - Click on a legal move square to make the move
   - Move is highlighted in **gold** (from and to squares)
   - Each move is automatically evaluated
   - Engine features appear in the live panel
5. **Log Samples**: Click "Log Current Move" after each move
6. **Reset**: Click "First ⏮" to return to the loaded FEN position
7. **Export**: Click "Download JSON" to save calibration dataset

**FEN Validation**: Invalid FEN strings will show an error message before loading.

**Visual Indicators**:
- **Yellow**: Selected piece
- **Light Green**: Legal move destinations
- **Gold**: Last played move (from → to)

## Output Format

Each logged sample contains:

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "move": "e2e4",
  "chesscom_label": "Best",
  "eval_before_cp": 25.0,
  "eval_after_cp": -28.0,
  "cpl": 53.0,
  "top_gap": 0.0,
  "multipv_rank": 1,
  "is_sacrifice": false,
  "is_mate_before": false,
  "is_mate_after": false,
  "phase": "opening"
}
```

**Field Notes:**
- `fen`: Position BEFORE the move (root position)
- `top_gap`: Gap to best move in CP, null if move not in PVs (shows as "—")
- `multipv_rank`: 1 to K if found, K+1 if not found
- `is_sacrifice`: True if move is a real material sacrifice (piece hangs after move)
- All `_cp` values use consistent root-player perspective

**Sacrifice Detection:**
The `is_sacrifice` field identifies moves where:
- Material is given up (moved piece value > captured piece value)
- The moved piece is attacked on the destination square
- The piece is not adequately defended
This helps identify brilliant sacrificial moves (Brilliant moves often combine sacrifice with high eval improvement).

## Troubleshooting

### Auto-Analysis Not Starting
- Make sure you've loaded a PGN first (click "Load PGN")
- Ensure the persistent engine is running (green button should show "Stop Analysis Engine")
- Check that the Flask server is running on port 5000
- If it gets stuck, refresh the page and try again

### Auto-Analysis Too Slow
- Reduce depth from 22 to 18 (Settings: Depth field)
- Reduce MultiPV from 5 to 3 (Settings: MultiPV field)
- At depth 18, MultiPV 3: expect ~0.5s per move (75 moves/min)
- At depth 22, MultiPV 5: expect ~1.5s per move (40 moves/min)

### Slow Analysis (General)
- Ensure persistent engine is started (green button shows "Stop Analysis Engine")
- Reduce depth to 18 or MultiPV to 3
- Check CPU usage (should be near 100% per thread)

### rank=99 Issues
- **Fixed**: System now returns K+1 instead of 99
- If still seeing 99, restart the Flask server

### top_gap=0 for rank>1
- **Fixed**: System now calculates gap using `to_root_cp()` consistently
- If gap is truly 0, moves have identical evaluations (rare but valid)

### Missing Moves in PVs
- Increase MultiPV from 3 to 5 or higher
- Some moves may be bad enough to not appear in top K
- These get rank = K+1 and top_gap = null (correct behavior)

### Can't Click Pieces in PGN Mode
- **Expected Behavior**: In PGN Navigation mode, clicking pieces is disabled
- Use "Next ▶" / "Prev ◀" buttons to navigate moves
- If you want to manually play moves, use FEN mode instead

### Can't Use Next Button in FEN Mode
- **Expected Behavior**: In FEN Manual Play mode, Next/Prev buttons are disabled
- Click pieces to select and play moves manually
- If you want to replay a game, use PGN mode instead

### Mode Indicator
- Check the "Mode:" indicator below the board
- **Blue** = PGN Navigation (use Next/Prev buttons)
- **Green** = FEN Manual Play (click pieces to move)
- **Gray** = Ready (load PGN or FEN to start)

### Piece Not Highlighting
- Make sure you're clicking on your own pieces (white pieces when it's white's turn)
- Clicking opponent's pieces will clear selection
- If no legal moves exist, piece won't highlight (check if position is checkmate/stalemate)

## Technical Details

### Normalization (`to_root_cp`)

All evaluations use a single normalization function:

```python
eval_before_cp = to_root_cp(score_before, root_turn=True, node_turn=True)
eval_after_cp = to_root_cp(score_after, root_turn=True, node_turn=False)
```

- Root perspective: Always from the side that played the move
- Mate scores: Mapped to CP_MAX + (100 - DTM) for bounded values
- No ±100000 ever appear in output

### Rank Calculation

```python
rank, top_gap = played_rank_and_gap(uci_move, pvs, root_turn)
```

- Promotion-safe matching (e7e8q matches e7e8)
- If found: rank = PV index (1 to K), top_gap = |best_cp - played_cp|
- If not found: rank = K+1, top_gap = null

## Performance Benchmarks

**Auto-Analysis Mode (with Persistent Engine - recommended):**
- Depth 18, MultiPV 5: ~0.5-0.8s per move → **4500-7200 moves/hour**
- Depth 22, MultiPV 5: ~1-2s per move → **1800-3600 moves/hour**
- **Example**: 40-move game at depth 22 = ~60-80 seconds total
- **Example**: 100-move game at depth 18 = ~50-80 seconds total
- Can analyze multiple full games while you grab coffee! ☕

**Manual Navigation (with Persistent Engine):**
- Same engine speed as above, but requires manual clicking
- Best for learning and spot-checking specific positions

**Without Persistent Engine (not recommended):**
- Depth 18, MultiPV 5: ~3-4s per move
- Engine spawn overhead: ~2-3s per evaluation
- ~900-1200 moves/hour
- **4x slower than persistent engine**

**Recommendation**: Always use persistent engine + auto-analysis for bulk calibration work.
