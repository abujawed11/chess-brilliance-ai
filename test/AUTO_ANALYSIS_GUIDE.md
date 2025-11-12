# 🚀 Auto-Analysis Feature Guide

## What's New?

**No more manual clicking!** The calibration tool now includes a fully automated PGN analysis feature that:

✅ Automatically plays through ALL moves in a PGN  
✅ Analyzes each move with Stockfish engine  
✅ Logs all evaluation data automatically  
✅ Shows real-time progress  
✅ Can be paused/stopped at any time  
✅ Allows you to edit labels afterwards  

## How to Use

### Step 1: Start the Server

```bash
cd test
python app.py
```

Server should start on `http://localhost:5000`

### Step 2: Open the Calibration Tool

Open `callibrator.html` in your browser (or navigate to the Flask route if you've configured one).

### Step 3: Configure Engine

1. Click **"Start Analysis Engine"** (green button)
2. Wait for confirmation: "Engine: Running" appears below the button
3. Optionally adjust settings:
   - **Depth**: 18-22 (lower = faster, higher = more accurate)
   - **MultiPV**: 3-5 (how many alternative moves to consider)

### Step 4: Load PGN

**Option A: Upload File**
- Click "Choose File" under "Upload PGN File"
- Select your `.pgn` file
- Click **"Load PGN"**

**Option B: Paste Text**
- Copy your PGN text
- Paste into the "Or Paste PGN" textarea
- Click **"Load PGN"**

You should see a message: "PGN loaded. X moves found."

### Step 5: Run Auto-Analysis

1. Click **"🚀 Start Auto-Analysis"** (blue button)
2. Confirm the dialog (it will tell you how many moves will be analyzed)
3. Watch the progress in real-time:
   - Progress bar shows: "Analyzing move X/Y... (Z logged, E errors)"
   - Board updates as moves are played
   - Live eval panel shows current move analysis

**To pause/stop**: Click the button again (it changes to "⏸️ Stop Auto-Analysis")

### Step 6: Review Results

After completion, you'll see:
- Summary alert with statistics
- All moves logged in the table below
- Each row shows: FEN, move, label, evaluations, mate info, etc.

### Step 7: Edit Labels (Optional)

1. Scroll to the "Logged Samples" table
2. Click any label dropdown in the "Chess.com Label" column
3. Select a new label (Brilliant, Great, Best, Good, Blunder, etc.)
4. Changes are saved automatically to browser storage

### Step 8: Export Data

1. Click **"Download JSON"** button
2. File downloads as `calibration_samples.json`
3. Use this data for model training or validation

## Performance Expectations

| Depth | MultiPV | Time per Move | 40-Move Game | 100-Move Game |
|-------|---------|---------------|--------------|---------------|
| 18    | 3       | ~0.5s         | ~20s         | ~50s          |
| 18    | 5       | ~0.7s         | ~28s         | ~70s          |
| 22    | 3       | ~1.2s         | ~48s         | ~120s         |
| 22    | 5       | ~1.8s         | ~72s         | ~180s         |

**Recommendation**: Depth 22, MultiPV 5 for best quality (1-2 min per game)

## Features

### Real-Time Feedback

- **Progress Counter**: "Analyzing move 15/40..."
- **Success/Error Count**: "(32 logged, 1 errors)"
- **Board Visualization**: Watch moves play out on the board
- **Live Eval Panel**: See engine analysis for current move

### Automatic Logging

Each move is automatically logged with:
- FEN position (before move)
- Move in UCI notation
- Engine's suggested label (Brilliant, Best, Mistake, etc.)
- Eval before/after
- CPL (centipawn loss)
- Top gap (gap to best move)
- MultiPV rank
- Sacrifice detection
- Mate information
- Game phase

### Editable Labels

- All logged samples appear in the table
- Click any label dropdown to change it
- Perfect for:
  - Confirming with Chess.com analysis
  - Manual corrections
  - Calibration experiments

### Pause/Resume

- Click "Stop Auto-Analysis" to pause
- Samples analyzed so far are kept
- Can restart from beginning if needed

## Troubleshooting

### "Please start the analysis engine first!"
- Click the green "Start Analysis Engine" button
- Wait for "Engine: Running" to appear

### "Please load a PGN first!"
- Upload a PGN file or paste PGN text
- Click "Load PGN"
- Verify the move count appears

### Analysis is too slow
- Reduce **Depth** to 18 (from 22)
- Reduce **MultiPV** to 3 (from 5)
- Check CPU usage (should be near 100%)
- Close other applications

### Some moves show errors
- Normal for positions with errors in PGN
- Check console (F12) for detailed error messages
- Most moves should succeed

### Labels don't match Chess.com
- This is expected! That's why you manually edit them
- Engine labels are just initial suggestions
- Use Chess.com Game Review to get official labels
- Update labels in the table dropdown

## Workflow: Chess.com Calibration

### Recommended Process

1. **Get analyzed games from Chess.com**:
   - Go to Chess.com Archive
   - Click "Game Review" on games
   - Download PGN files

2. **Auto-analyze with Stockfish**:
   - Use this tool's auto-analysis feature
   - Gets engine features for each move

3. **Compare labels**:
   - Open game on Chess.com
   - See their labels (Brilliant !!, Great !, Best, etc.)
   - Update labels in the tool's table

4. **Export calibration data**:
   - Download JSON with correct labels
   - Use for training your own move classifier

### Why This Works

- **Chess.com labels** = Human-calibrated "ground truth"
- **Stockfish features** = Objective evaluation metrics
- **Your model** = Learns to predict labels from features

## Tips & Best Practices

### For Speed
- Use Depth 18 for bulk analysis
- Use Depth 22 for important games
- Analyze multiple games in batches
- Let it run while you do other work

### For Accuracy
- Always use persistent engine
- Use MultiPV 5 to catch alternative moves
- Higher depth = better detection of tactics
- Check sacrifice detection is working

### For Data Quality
- Verify a few random moves manually
- Check that mate detection works
- Ensure labels make sense
- Remove obvious errors before training

### For Large Datasets
- Analyze 10-20 games at a time
- Save JSON after each session
- Merge JSON files later if needed
- Keep backups of your data

## Example Session

```
1. Start Flask server: python app.py
2. Open callibrator.html
3. Click "Start Analysis Engine" ✅
4. Upload: kasparov_1999.pgn
5. Click "Load PGN" → "PGN loaded. 82 moves found."
6. Click "🚀 Start Auto-Analysis"
7. Confirm dialog
8. Wait ~2 minutes (Depth 22, MultiPV 5)
9. Alert: "82 moves logged successfully"
10. Review table, edit 3 brilliant moves
11. Click "Download JSON"
12. Done! 🎉
```

## Next Steps

After collecting calibration data:

1. **Validate**: Use `validate_brilliance.py` to check accuracy
2. **Train**: Feed data to your XGBoost model
3. **Test**: Run predictions on new games
4. **Iterate**: Collect more edge cases, retrain

## FAQ

**Q: Can I stop and resume later?**  
A: Yes, click the stop button. Logged samples are saved in browser storage. You can continue with another game.

**Q: Does it work with FEN mode?**  
A: No, auto-analysis only works with PGN files. FEN mode is for manual play.

**Q: Can I analyze multiple PGNs at once?**  
A: No, analyze them one at a time. But it's very fast!

**Q: Where is my data stored?**  
A: In browser localStorage. Click "Download JSON" to export permanently.

**Q: Can I clear all samples?**  
A: Yes, click the red "Clear All" button in the logged samples section.

**Q: What if my computer goes to sleep?**  
A: Analysis will pause. Refresh and start over (data is lost unless you exported JSON).

## Support

If you encounter issues:
1. Check the browser console (F12 → Console tab)
2. Check the Flask server logs
3. Verify Stockfish engine is in `engine/stockfish.exe`
4. Try refreshing the page
5. Restart the Flask server

Happy analyzing! 🎯♟️

