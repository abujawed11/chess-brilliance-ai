# 📝 Manual Test Data Collection Guide

## Why Manual Collection is Better

**Pros:**
- ✅ 100% accuracy - you verify each position
- ✅ Works even if API fails
- ✅ Select only the BEST examples
- ✅ Understand each test case deeply
- ✅ Takes only 20-30 minutes for 20 cases

**Cons:**
- Requires copy-pasting (but we make it easy!)

---

## 🚀 Quick Manual Collection (20 positions in 20 mins)

### Step 1: Find Analyzed Games on Chess.com

1. Go to: https://www.chess.com/home
2. Click **"Archive"** (left sidebar)
3. Look for games with **"Game Review"** button
4. If you don't see any, click **"Game Review"** on 10 recent games (instant with Diamond!)

### Step 2: Extract Brilliant Moves

For each game with brilliant moves:

1. **Click the game** to open it
2. **Look for green !!** (brilliant move indicators)
3. **Click on the move BEFORE the brilliant move**
4. **Open Analysis Board** (click "Analysis" button)
5. **Copy the position:**
   - Method A: Right-click board → "Copy FEN"
   - Method B: Look at bottom-left of analysis board for FEN

6. **Note the move:**
   - The brilliant move will be highlighted
   - Note the UCI notation (e.g., e2e4, g1f3, etc.)
   - Tip: Hover over the move to see notation

7. **Add to template below**

---

## 📋 Collection Template

Copy this template and fill it in:

```json
[
  {
    "name": "My brilliant queen sacrifice - Game 1",
    "fen": "PASTE_FEN_HERE",
    "move": "d1h5",
    "expected_label": "Brilliant",
    "source": "https://chess.com/game/live/YOUR_GAME_ID",
    "description": "Queen sac leading to forced mate"
  },
  {
    "name": "My brilliant rook sacrifice - Game 2",
    "fen": "PASTE_FEN_HERE",
    "move": "a1a8",
    "expected_label": "Brilliant",
    "source": "https://chess.com/game/live/YOUR_GAME_ID",
    "description": "Rook sac deflection"
  }
]
```

---

## 🎯 What to Collect (Priority Order)

### Priority 1: Brilliant Moves (10-15 cases)
- Your own brilliant moves from games
- One brilliant move from a master game
- Variety: Queen sacs, Knight sacs, Rook sacs, Quiet brilliancies

### Priority 2: Blunders (5-10 cases)
**CRITICAL for false positive testing!**
- Your own blunders (we all make them!)
- Hanging pieces
- Missing tactics
- Moving into checkmate

### Priority 3: Other Labels (5-10 cases)
- Best moves
- Good moves
- Inaccuracies
- Mistakes

---

## 📖 Step-by-Step Example

Let's collect ONE brilliant move together:

### Example: Finding Your Brilliant Move

1. **Go to your Chess.com Archive**
2. **Click a game with "Brilliant!" badge**
3. **Game opens - you see move list**
4. **Find the move with green !!** - let's say it's move 15...Qxf2+
5. **Click move 14** (the move BEFORE the brilliant)
6. **Click "Analysis"**
7. **You see the position before Qxf2+**
8. **Right-click board → Copy FEN**
   - Result: `r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP1QPPP/R1B1K2R b KQ - 0 14`
9. **Note the move:** Qxf2+ = Queen from d8 to f2 = `d8f2`
10. **Copy game URL** from address bar

### Your Entry:
```json
{
  "name": "My brilliant Queen sacrifice - vs Player123",
  "fen": "r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP1QPPP/R1B1K2R b KQ - 0 14",
  "move": "d8f2",
  "expected_label": "Brilliant",
  "source": "https://www.chess.com/game/live/123456789",
  "description": "Queen sacrifice forcing checkmate in 5"
}
```

**Done! One down, 19 to go!** 🎉

---

## 💡 Pro Tips

### Finding UCI Notation

Common moves:
- **e4** (pawn to e4) = `e2e4`
- **Nf3** (knight to f3) = `g1f3`
- **Qxf7+** (queen takes f7) = `d1f7` or `e2f7` (depends on queen position)
- **O-O** (kingside castle) = `e1g1`
- **Promotion** (e8=Q) = `e7e8q`

**Easy way:** Use Chess.com's analysis board - hover over moves to see notation!

### Finding Your Best Games

Chess.com → Stats → Insights → "Best Games"
Shows games where you played brilliant moves!

### Time-Saving Tip

**Collect in batches:**
- 10 mins: Find 5 brilliant moves
- 5 mins: Find 3 blunders
- 5 mins: Find 2 best moves
- Total: 20 mins for 10 quality test cases!

---

## 📁 Save Your Dataset

1. **Create file:** `test_data.json` in the `test` folder
2. **Paste your collected data**
3. **Validate format:**
   ```bash
   python -m json.tool test_data.json
   ```
4. **Run validation:**
   ```bash
   python validate_brilliance.py
   ```

---

## 🎯 Quality Checklist

Before running validation, check:
- [ ] At least 10 test cases total
- [ ] Mix of brilliant/blunder/other labels
- [ ] All FENs are valid (from Chess.com)
- [ ] All moves are in UCI notation
- [ ] Source URLs included
- [ ] Descriptions explain why the move is interesting

---

## 🚨 Common Mistakes

### ❌ Wrong FEN
**Problem:** Copying FEN AFTER the move instead of BEFORE
**Solution:** Always click the PREVIOUS move first!

### ❌ Wrong Move Notation
**Problem:** Using SAN (Qxf7) instead of UCI (d1f7)
**Solution:** Use analysis board or convert:
- Look at FROM square + TO square
- Example: Queen on d1 takes f7 = `d1f7`

### ❌ Missing Cases
**Problem:** Only collecting brilliant moves
**Solution:** Include blunders! They're crucial for testing!

---

## 📊 Example Complete Dataset

Here's a starter dataset you can use:

```json
[
  {
    "name": "Starter: Simple brilliant - Fork setup",
    "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1",
    "move": "f3g5",
    "expected_label": "Brilliant",
    "source": "Italian Game brilliant sacrifice",
    "description": "Knight sac opening attack lines"
  },
  {
    "name": "Starter: Classic blunder - Hanging queen",
    "fen": "rnbqkbnr/ppp2ppp/8/3pp3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 1",
    "move": "f3e5",
    "expected_label": "Blunder",
    "source": "Common opening mistake",
    "description": "Hangs queen to pawn - CRITICAL false positive test"
  }
]
```

Save this as `test_data.json` and add your own cases!

---

## ✅ Next Steps

1. **Collect 10 brilliant moves** (15 mins)
2. **Collect 5 blunders** (5 mins)
3. **Save as test_data.json**
4. **Run:** `python validate_brilliance.py`
5. **Check accuracy** - should be 100% on brilliants!
6. **Add more cases** based on results

---

**Ready to start collecting?** Open Chess.com and let's build your dataset! 🚀
