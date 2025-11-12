# Testing Guide: Validating Brilliant Move Detection

## Overview

This guide explains how to validate your brilliant move detection system to ensure accuracy and prevent false positives (like labeling blunders as brilliant).

## Quick Start

1. **Start your Flask API:**
   ```bash
   python app.py
   ```

2. **Run validation:**
   ```bash
   python validate_brilliance.py
   ```

## Files

- `test_data.json` - Test cases with ground truth labels
- `validate_brilliance.py` - Validation script with metrics
- `collect_test_data.py` - Helper to collect data from Chess.com

## Building Your Test Dataset

### 1. Manual Curation (Highest Quality)

Add known cases to `test_data.json`:

```json
{
  "name": "Descriptive name",
  "fen": "position before move",
  "move": "uci notation",
  "expected_label": "Brilliant|Blunder|Mistake|Best|Good|etc",
  "source": "where you got this",
  "description": "why this is interesting"
}
```

#### Critical Test Cases to Include:

**Brilliant Moves:**
- ✓ Non-obvious sacrifices (engine didn't see it)
- ✓ Forced tactical sacrifices (immediate eval drops)
- ✓ Defensive brilliancies (saving losing positions)
- ✓ Only moves (forced sequences)
- ✓ Queen sacrifices for mate
- ✓ Positional sacrifices

**Blunders (False Positive Check):**
- ✗ Hanging pieces without compensation
- ✗ Moving into checkmate
- ✗ Losing exchanges badly
- ✗ Random sacrifices in lost positions
- ✗ Missing obvious tactics

**Edge Cases:**
- Stalemate tricks
- Perpetual check draws from losing positions
- Quiet moves with huge eval swings
- Material sacrifices in already winning positions

### 2. Import from Chess.com

```bash
python collect_test_data.py <your_username>
```

This downloads your analyzed games and extracts annotated moves.

**Requirements:**
- Games must have Game Review run on Chess.com
- Looks at last 3 months of games

### 3. Import from Famous Games

Search for famous games with brilliant moves:
- Kasparov's Immortal Game
- Fischer's Game of the Century
- Tal's sacrifices
- Shirov's brilliancies

Resources:
- https://www.chessgames.com
- https://lichess.org/study (with annotations)

### 4. Generate Edge Cases Programmatically

Create specific tactical positions:
```python
# Example: Hanging queen (should NEVER be brilliant)
{
  "name": "Hanging queen",
  "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPPQPPP/RNB1KBNR w KQkq - 0 1",
  "move": "e2e5",  # Hangs queen
  "expected_label": "Blunder",
  "description": "Queen hangs to bishop - critical false positive test"
}
```

## Understanding the Metrics

### Accuracy
Overall percentage of correct predictions.
- **Target:** > 90%

### Precision (for Brilliant)
Of all moves labeled "Brilliant", how many actually are?
- **Formula:** True Brilliant / (True Brilliant + False Brilliant)
- **Target:** > 85% (avoid false positives!)

### Recall (for Brilliant)
Of all actual brilliant moves, how many did we catch?
- **Formula:** True Brilliant / (True Brilliant + Missed Brilliant)
- **Target:** > 70% (okay to miss some edge cases)

### F1 Score
Harmonic mean of precision and recall.
- **Target:** > 0.75

### Confusion Matrix
Shows which labels get confused with each other.

Example:
```
                Predicted
              Brilliant  Blunder  Best
Actual
Brilliant        15        0       2    <- 2 missed
Blunder           1       18       0    <- 1 FALSE POSITIVE! 🚨
Best              0        1      23
```

## Critical: False Positive Analysis

**False positives are the biggest concern!**

A blunder labeled as "Brilliant" is much worse than missing some brilliant moves.

The script highlights these:
```
⚠️  FALSE POSITIVE BRILLIANCIES (Critical Issues!)
❌ Hanging queen sacrifice
   Expected: Blunder, Got: Brilliant
   This should NOT be brilliant!
```

### When to Investigate:

1. **Brilliant → Blunder confusion:** Tighten thresholds
2. **Blunder → Brilliant confusion:** 🚨 CRITICAL - fix immediately!
3. **Best → Brilliant confusion:** Acceptable if close calls

## Iterating and Improving

1. **Run validation:**
   ```bash
   python validate_brilliance.py
   ```

2. **Identify issues:**
   - Check false positives first
   - Review confused labels
   - Look at edge cases

3. **Adjust thresholds in `label_rules.py`:**
   ```python
   # Example: Too many false brilliancies on small eval changes?
   # Increase threshold from 200 to 250
   if is_sacrifice and multipv_rank >= 5 and eval_change >= 250:
   ```

4. **Re-run validation and compare:**
   - Did accuracy improve?
   - Did false positives decrease?
   - Did we lose important cases?

5. **Add failed cases to test suite**

## Recommended Test Suite Size

- **Minimum:** 50 test cases
  - 15 Brilliant
  - 10 Blunders
  - 10 Best/Excellent
  - 10 Mistakes
  - 5 Edge cases

- **Good:** 200+ test cases
  - Diverse positions
  - Multiple brilliant types
  - Known false positive triggers

- **Production:** 1000+ test cases
  - Real game data
  - Continuous validation

## Continuous Testing

Add new test cases when you find:
- False positives in production
- Missed brilliant moves
- Weird edge cases
- User reports

## Advanced: A/B Testing

Test different threshold configurations:

```python
# configs.py
CONFIG_A = {
    "non_obvious_threshold": 200,
    "gap_threshold": 300
}

CONFIG_B = {
    "non_obvious_threshold": 250,
    "gap_threshold": 400
}
```

Run validation on both and compare metrics.

## Example Workflow

```bash
# 1. Collect data from your Chess.com games
python collect_test_data.py your_username

# 2. Merge with existing test data
# (Manually combine JSON files)

# 3. Add edge cases manually to test_data.json

# 4. Start API
python app.py

# 5. Run validation
python validate_brilliance.py

# 6. Review results and adjust thresholds

# 7. Re-validate until metrics are good
```

## Troubleshooting

**"No annotated moves found" from collect_test_data.py:**
- Chess.com only annotates games with Game Review enabled
- Analyze some games on Chess.com first

**API timeout errors:**
- Increase depth reduces speed
- Reduce depth temporarily for faster testing
- Or increase timeout in validate_brilliance.py

**Low accuracy:**
- Need more diverse test cases
- Check if thresholds match your use case
- Review false positives first

**High false positives:**
- Thresholds too loose
- Increase eval_change requirements
- Add more checks (e.g., not already winning)

## Next Steps

1. **Build initial test suite** (50+ cases)
2. **Run validation** and get baseline metrics
3. **Fix false positives** (priority #1)
4. **Iterate on thresholds**
5. **Continuously add cases** from production use
6. **Monitor metrics** over time

Good luck! 🎯
