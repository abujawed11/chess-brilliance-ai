# 💎 Chess.com Diamond Member - Dataset Building Guide

## Why Diamond is Perfect for This

Your Diamond membership gives you:
- ✅ **Unlimited Game Review** - Analyze all your games instantly
- ✅ **Deeper Computer Analysis** - More accurate move classifications
- ✅ **Master Games Database** - Access to thousands of annotated games
- ✅ **Better Annotations** - Higher quality brilliant/blunder detection
- ✅ **Advanced Stats** - See patterns in your brilliant moves

---

## 🚀 Quick Start (15 minutes)

### Method 1: Use Your Own Games

**Step 1: Bulk Analyze Your Games**
```
1. Go to Chess.com → Archive
2. Select 20-30 recent games
3. Click "Game Review" on each (instant with Diamond!)
4. Wait for all to complete
```

**Step 2: Scrape the Data**
```bash
cd test
python scrape_chesscom_games.py YOUR_USERNAME 30   --Abubakar1995

python scrape_chesscom_games.py Abubakar1995 30
```

**Step 3: Validate**
```bash
python validate_brilliance.py
```

**Done!** You now have a real dataset based on Chess.com's analysis.

---

### Method 2: Use Master Games (Most Comprehensive)

**Step 1: Find Brilliant Games**
```
1. Go to: https://www.chess.com/games
2. Filter: Rating 2500+, Result: Decisive
3. Click games with lots of annotations
4. Look for green "!!" (brilliant moves)
```

**Step 2: Extract Positions Manually**

For each brilliant move:

1. **Open Analysis Board** (click game → Analysis)
2. **Navigate to move BEFORE the brilliant move**
3. **Copy FEN:**
   - Right-click board → "Copy FEN"
   - Or look in bottom left of analysis board
4. **Note the move in UCI:**
   - Click the brilliant move
   - Check move notation (e.g., Nxe5 = knight takes e5)
   - Convert to UCI: g1f3, e2e4, etc.
5. **Add to dataset:**
   ```json
   {
     "name": "Kasparov brilliant sacrifice",
     "fen": "paste_fen_here",
     "move": "f3g5",
     "expected_label": "Brilliant",
     "source": "game_url",
     "description": "Why it's brilliant"
   }
   ```

**Step 3: Run the master dataset builder**
```bash
python fetch_master_brilliancies.py
```

---

## 📊 Recommended Dataset Composition

For comprehensive testing, aim for:

| Label | Quantity | Source |
|-------|----------|--------|
| **Brilliant** | 20-30 | Master games + your games |
| **Great** | 10-15 | Your analyzed games |
| **Best** | 15-20 | Your games + master games |
| **Good** | 10-15 | Your games |
| **Inaccuracy** | 10-15 | Your games |
| **Mistake** | 10-15 | Your games |
| **Blunder** | 15-20 | Your games (important for false positive testing!) |

**Total: 100-150 positions** = Excellent dataset!

---

## 💡 Pro Tips for Diamond Members

### 1. **Use Game Review Filters**
```
Archive → Filters → Select:
- Games with brilliant moves
- Games with blunders
- Specific openings
```

### 2. **Find Your Best Brilliancies**
```
Stats → Insights → "Best Games"
Shows games with most brilliant moves!
```

### 3. **Learn from Masters**
```
Videos → Master Games
Watch annotated games, extract brilliant positions
```

### 4. **Use Tactics Trainer**
```
Puzzles → Tactics
Many puzzle solutions are brilliant moves!
Copy FEN from puzzle page
```

### 5. **Join Study Groups**
```
Studies → Browse
Find studies with annotated brilliant games
Example: "Tal's Greatest Sacrifices"
```

---

## 🎯 Fastest Way to Build Dataset (Diamond Workflow)

### Goal: 50 high-quality test cases in 30 minutes

**Minutes 0-10: Analyze Your Games**
1. Archive → Select 20 recent games
2. Click "Game Review" on all
3. Let them process (grab coffee ☕)

**Minutes 10-15: Run Scraper**
```bash
python scrape_chesscom_games.py YOUR_USERNAME 20
```
You now have: ~15-30 real positions from YOUR games!

**Minutes 15-25: Add Famous Brilliancies**
1. Edit `fetch_master_brilliancies.py`
2. Add 5-10 famous brilliant moves (provided in script)
3. Run: `python fetch_master_brilliancies.py`

**Minutes 25-30: Combine & Test**
```bash
# Merge the files
cat test_data_real_*.json test_data_masters.json > test_data.json

# Validate
python validate_brilliance.py
```

**Result:** Professional-grade test dataset with mix of:
- Your own games (real-world data at your level)
- Master games (extreme test cases)
- Famous blunders (false positive protection)

---

## 🔍 Finding Specific Test Cases

### Need more Brilliant moves?
```
Chess.com → Games → Advanced Search
Filter: "Moves with !!" annotation
Result: Games with brilliant moves only
```

### Need edge cases?
- **Stalemate tricks:** Search "stalemate brilliancy"
- **Quiet moves:** Search "positional brilliancies"
- **Defensive brilliancies:** Search "defensive sacrifice"
- **Only moves:** Search "forced win" or "forced draw"

### Need blunders? (For false positive testing)
```
Your Archive → Games you lost
Run Game Review → Find your blunders
These are CRITICAL for testing!
```

---

## 📈 Advanced: Continuous Dataset Improvement

### Monthly Workflow:
1. **Analyze all new games** (automatic with Diamond!)
2. **Run scraper** to add new positions
3. **Re-validate** to check accuracy
4. **Adjust thresholds** based on new data
5. **Rinse and repeat**

### Track Progress:
```bash
# Save validation results
python validate_brilliance.py > results_2025_01.txt

# Compare month-to-month
diff results_2025_01.txt results_2025_02.txt
```

---

## 🎮 Gamification: Make It Fun!

### Challenge 1: "The Brilliant Collector"
- **Goal:** Collect 10 brilliant moves in your games this month
- **Reward:** Better test dataset + improve your play!

### Challenge 2: "False Positive Hunter"
- **Goal:** Find blunders your system labels as brilliant
- **Reward:** Improve system accuracy!

### Challenge 3: "Master Study"
- **Goal:** Analyze 5 master games with brilliant moves
- **Reward:** Learn from the best + build dataset!

---

## 🚨 Important: Quality Over Quantity

**Bad dataset example:**
- 1000 positions, all from one player
- All brilliant moves, no blunders
- All similar positions (same opening)
- Not verified against Chess.com labels

**Good dataset example:**
- 100 positions from diverse games
- Mix of all label types
- Various positions (tactical, positional, endgame)
- Verified against Chess.com Game Review

**Your Diamond membership makes building a GOOD dataset easy!**

---

## 📞 Troubleshooting

**Q: Scraper finds no annotated moves**
- A: Make sure you've run "Game Review" on games first
- Check: Games must be analyzed, not just played

**Q: How do I convert move notation to UCI?**
- A: Use Chess.com analysis board
  - Regular notation: Nf3, e4, Qxd5
  - UCI notation: g1f3, e2e4, d1d5

**Q: What if Chess.com labels differ from my system?**
- A: This is EXPECTED! You're calibrating to match Chess.com
- Adjust thresholds in `label_rules.py` based on differences

**Q: How many test cases do I need?**
- Minimum: 30-50 for basic validation
- Good: 100-150 for reliable testing
- Great: 200+ for production use

---

## 🎯 Next Steps

1. ✅ Choose your method (own games vs master games)
2. ✅ Follow the "Fastest Way" workflow
3. ✅ Run validation: `python validate_brilliance.py`
4. ✅ Check accuracy - aim for >85% on brilliants
5. ✅ Iterate and improve!

**Your Diamond membership is a huge advantage - use it!** 💎

---

## Resources

- **Chess.com API Docs:** https://www.chess.com/news/view/published-data-api
- **Famous Brilliant Games:** https://www.chess.com/article/view/the-most-brilliant-moves
- **Your Stats:** https://www.chess.com/stats/overview/YOUR_USERNAME

Good luck building the ultimate chess move classifier! 🚀
