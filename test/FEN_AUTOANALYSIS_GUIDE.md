# 🎯 Auto-Analysis from Custom FEN Positions

## Overview

You can now use auto-analysis to analyze games starting from any FEN position, not just the standard starting position!

---

## Workflow Options

### Option 1: Standard Game (Default)

**For regular games starting from the initial position:**

1. Load PGN
2. Start Auto-Analysis
3. Done!

---

### Option 2: Custom Starting Position

**For analyzing games from a specific position:**

1. **Load your custom FEN first**
   - Paste FEN in the "Load FEN Position" field
   - Click "Set Position"
   - Board shows your custom position ✓

2. **Then load your PGN**
   - The moves in the PGN will be played from your FEN position
   - Click "Load PGN"
   - You'll see: "PGN loaded. X moves found. Starting from custom FEN position."

3. **Start Auto-Analysis**
   - Click "🚀 Start Auto-Analysis"
   - System analyzes all moves starting from your FEN ✓

---

## Use Cases

### Use Case 1: Analyzing Middle/Endgame Positions

**Scenario:** You want to analyze a specific endgame or middle game position

```
Example FEN: 8/5k2/8/8/8/4K3/8/8 w - - 0 1 (King endgame)

1. Load this FEN
2. Have a PGN with the moves from this position
3. Auto-analyze to see if the play was optimal
```

### Use Case 2: Puzzle Solutions

**Scenario:** You have a chess puzzle position and the solution moves

```
Example: Mate in 3 puzzle

1. Load the puzzle FEN
2. Create a PGN with the solution moves
3. Auto-analyze to verify the solution
```

### Use Case 3: Game Fragments

**Scenario:** You only have moves from move 20 onwards

```
1. Get the FEN from move 19
2. Load that FEN
3. Load PGN with moves 20+
4. Auto-analyze from that point
```

### Use Case 4: Opening Variations

**Scenario:** Analyze a specific opening line from move 8

```
1. Get FEN after 7 moves of theory
2. Load that FEN  
3. Load PGN with the continuation
4. Auto-analyze the critical phase
```

---

## Important Notes

### ⚠️ FEN Mode vs Auto-Analysis

**FEN Mode (Manual Play):**
- Load FEN → Click pieces to play moves
- For exploring positions manually
- Each move must be evaluated individually
- Use "Log Current Move" after each move

**Auto-Analysis:**
- Requires a PGN with predetermined moves
- All moves analyzed automatically
- Much faster for complete games

### 📝 Creating PGN from FEN Position

If you have a FEN and want to create moves for auto-analysis:

**Option A: Use Chess.com Analysis**
1. Open Chess.com Analysis Board
2. Set your FEN position
3. Play the moves
4. Export as PGN
5. Use in auto-analysis

**Option B: Use Lichess**
1. Go to lichess.org/analysis
2. Paste your FEN
3. Play the moves
4. Export PGN
5. Use in auto-analysis

**Option C: Manual PGN Creation**
```
[FEN "YOUR_FEN_HERE"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 ...
```

---

## Step-by-Step Examples

### Example 1: Analyzing a Rook Endgame

**Starting Position:**
```
FEN: 8/5k2/8/3R4/8/5K2/8/8 w - - 0 1
```

**Steps:**
1. Copy FEN above
2. Open calibration tool
3. Paste FEN in "Load FEN Position" field
4. Click "Set Position" → Board shows rook endgame
5. Prepare PGN with endgame moves:
   ```
   [FEN "8/5k2/8/3R4/8/5K2/8/8 w - - 0 1"]
   
   1. Rd7+ Kg8 2. Kg4 Kf8 3. Kf5 Kg8 4. Ke6
   ```
6. Paste this PGN in "Or Paste PGN" field
7. Click "Load PGN"
8. Click "🚀 Start Auto-Analysis"
9. All endgame moves analyzed! ✓

---

### Example 2: Analyzing Opening Novelty

**Scenario:** You want to analyze a novelty on move 12 of the Sicilian

**Starting Position (after 11 moves):**
```
FEN: r1bq1rk1/pp2bppp/2nppn2/8/3NP3/2N1BP2/PPPQ2PP/R3KB1R w KQ - 0 12
```

**Steps:**
1. Get FEN from your database after move 11
2. Load this FEN
3. Create PGN with moves 12 onwards:
   ```
   [FEN "r1bq1rk1/pp2bppp/2nppn2/8/3NP3/2N1BP2/PPPQ2PP/R3KB1R w KQ - 0 12"]
   
   12. Ndb5 a6 13. Na3 Qc7 14. h3 ...
   ```
4. Load this PGN
5. Auto-analyze to evaluate the novelty ✓

---

## Troubleshooting

### "Please load a PGN first!"

**Problem:** You loaded a FEN but no PGN

**Solution:** 
- FEN sets the starting position only
- You still need a PGN with the moves to analyze
- Load both: FEN first, then PGN

### "Failed to parse PGN"

**Problem:** PGN doesn't include FEN tag or moves don't match position

**Solution:**
- Make sure PGN has `[FEN "..."]` tag if it starts from a non-standard position
- Or just load FEN separately first, then load PGN with just the moves

### Moves Don't Make Sense

**Problem:** Loaded FEN and PGN but pieces move illegally

**Solution:**
- The PGN moves might not be compatible with your FEN
- Verify the PGN moves are meant to start from that exact position
- Check move notation (algebraic vs descriptive)

### Auto-Analysis Starts from Wrong Position

**Problem:** Expected custom FEN but started from standard position

**Solution:**
1. Load FEN FIRST
2. THEN load PGN
3. Order matters!

---

## Advanced: Batch Analysis from FEN

If you have multiple games from the same FEN position:

**Workflow:**
1. Load FEN once
2. Load PGN #1 → Auto-analyze → Export JSON
3. Load PGN #2 → Auto-analyze → Export JSON  
4. Load PGN #3 → Auto-analyze → Export JSON
5. Combine JSON files

**Tip:** The FEN stays loaded, so you can keep loading different PGNs without reloading the FEN!

---

## FAQ

**Q: Can I auto-analyze without a PGN?**
A: No. Auto-analysis needs predetermined moves. Use manual mode for free exploration.

**Q: What if my PGN already has a FEN tag?**
A: You can load the PGN directly - it will use the FEN from the PGN.

**Q: Can I mix FEN loading and PGN loading?**
A: Yes! Load FEN first to set position, then load PGN with moves.

**Q: Does the PGN need the [FEN "..."] tag?**
A: No, if you load the FEN separately first.

**Q: Can I change the FEN mid-analysis?**
A: No. Reset and start over with new FEN + PGN.

**Q: What happens to the FEN when I load a new PGN?**
A: The FEN persists! Load FEN once, then load multiple PGNs if needed.

---

## Summary

✅ **Load FEN → Load PGN → Auto-Analyze**

This workflow lets you:
- Analyze games from any position
- Focus on specific phases (opening/middle/endgame)
- Verify puzzle solutions
- Study opening novelties
- Calibrate your model on specific position types

**The power of auto-analysis, now with custom starting positions!** 🎯

---

**Pro Tip:** When collecting calibration data, consider analyzing positions of different types:
- Early middlegames (moves 10-20)
- Complex middlegames (moves 20-35)
- Endgames (moves 35+)
- Tactical puzzles
- Positional struggles

This creates a more balanced training dataset! 📊

