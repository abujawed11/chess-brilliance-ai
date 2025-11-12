# 🔧 Troubleshooting Auto-Analysis

## Error: "Please start the analysis engine first!"

This error means the system cannot detect a running engine. Here's how to fix it:

---

## ✅ Solution (Step-by-Step)

### Step 1: Check Flask Server is Running

**Open Command Prompt/PowerShell:**
```bash
cd D:\react\chess_brilliance_ai\test
python app.py
```

**You should see:**
```
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```

**If you see errors:**
- Check Python is installed: `python --version`
- Install requirements: `pip install -r requirements.txt`
- Check port 5000 is not in use

**Keep this window open!** Don't close it while using the tool.

---

### Step 2: Open the Calibration Tool

**Open in browser:**
```
File → Open File → D:\react\chess_brilliance_ai\test\callibrator.html
```

OR drag and drop the file into your browser.

---

### Step 3: Start the Engine (GREEN BUTTON)

**CRITICAL: You must do this BEFORE auto-analysis!**

1. Look for the **green button**: **"Start Analysis Engine"**
2. Click it
3. Wait 2-3 seconds
4. Check the status below the button

**✅ Success looks like:**
```
Button: "Stop Analysis Engine" (now RED)
Status: "Engine: Running" (GREEN text)
```

**❌ Failure looks like:**
```
Alert: "Failed to start engine: [error message]"
Button: Still says "Start Analysis Engine"
Status: "Engine: Stopped"
```

---

### Step 4: Load PGN

1. Click "Choose File" or paste PGN text
2. Click **"Load PGN"**
3. You should see: **"PGN loaded. 40 moves found."**

---

### Step 5: Start Auto-Analysis

Now you can click: **"🚀 Start Auto-Analysis"**

It should work! 🎉

---

## 🔍 Common Issues & Fixes

### Issue 1: Flask Server Not Running

**Symptom:** Engine start button does nothing, or shows network error

**Fix:**
```bash
# Terminal 1: Start Flask
cd D:\react\chess_brilliance_ai\test
python app.py

# Keep this running!
```

---

### Issue 2: Engine Start Fails

**Symptom:** Alert says "Failed to start engine"

**Possible Causes:**

**A) Stockfish Not Found**
```
Check file exists: D:\react\chess_brilliance_ai\engine\stockfish.exe

If missing:
1. Download from: https://stockfishchess.org/download/
2. Extract stockfish.exe
3. Place in: D:\react\chess_brilliance_ai\engine\
```

**B) Path Issue in Code**

Open `D:\react\chess_brilliance_ai\utils\chess_helpers.py`

Check the `ENGINE_PATH` is correct:
```python
ENGINE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
    "engine", 
    "stockfish.exe"
)
```

**C) Permission Issue**

Stockfish might be blocked by Windows:
1. Right-click `stockfish.exe`
2. Properties → General
3. Check if there's an "Unblock" checkbox
4. If yes, check it and click OK

---

### Issue 3: Browser Console Shows Errors

**Check browser console (F12 → Console):**

**Error: "Failed to fetch"**
- Flask server is not running
- Wrong API endpoint URL
- CORS issue (should be enabled in app.py)

**Error: "NetworkError"**
- Firewall blocking connection
- Antivirus blocking Flask
- Port 5000 already in use

**Error: "404 Not Found"**
- Check API endpoint: `http://localhost:5000/evaluate`
- Make sure Flask is running
- Check app.py has the `/evaluate` route

---

### Issue 4: "engineRunning" is False

**Debug Steps:**

1. **Open Browser Console (F12 → Console)**

2. **Check engine status:**
   ```javascript
   console.log("Engine running:", engineRunning);
   ```

3. **Should show:** `Engine running: true`

4. **If it shows false:**
   - Engine didn't start successfully
   - Check Flask server logs for errors
   - Try clicking "Start Analysis Engine" again

---

### Issue 5: Wrong API Endpoint

**Check the endpoint field:**

Should be: `http://localhost:5000/evaluate`

NOT:
- ~~http://localhost:5000~~ (missing /evaluate)
- ~~http://localhost:5000/~~ (missing evaluate)
- ~~https://localhost:5000/evaluate~~ (https instead of http)

---

## 🧪 Quick Test Checklist

Go through this checklist in order:

- [ ] Flask server is running (check terminal)
- [ ] Browser is open with callibrator.html
- [ ] Green "Start Analysis Engine" button is visible
- [ ] Clicked "Start Analysis Engine"
- [ ] Status shows "Engine: Running" (green text)
- [ ] Button now says "Stop Analysis Engine" (red)
- [ ] Loaded a PGN file
- [ ] Saw "PGN loaded. X moves found."
- [ ] Blue "🚀 Start Auto-Analysis" button is visible
- [ ] Clicked "🚀 Start Auto-Analysis"
- [ ] Saw confirmation dialog
- [ ] Clicked OK/Yes in dialog
- [ ] Analysis starts (progress counter updates)

**If all checked ✅:** It should work!

**If any fail ❌:** That's where the problem is.

---

## 🐛 Still Not Working?

### Debug Mode

**1. Enable debug output:**

Open browser console (F12 → Console)

**2. Check for errors:**
- Red text = errors
- Look for stack traces
- Copy error messages

**3. Check Flask logs:**
- Look at the terminal where Flask is running
- Any error messages?
- Any 500 Internal Server Error?

**4. Try manual mode:**
- Don't use auto-analysis
- Click "Next ▶" once
- Does it analyze that move?
- If yes → auto-analysis code issue
- If no → engine issue

---

## 📊 Verification Tests

### Test 1: Manual Engine Start

**In browser console:**
```javascript
fetch('http://localhost:5000/start_engine', {
    method: 'POST'
}).then(r => r.json()).then(console.log);
```

**Should return:**
```json
{
  "status": "started",
  "message": "Engine started successfully"
}
```

### Test 2: Manual Evaluation

**In browser console:**
```javascript
fetch('http://localhost:5000/evaluate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        fen: 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1',
        move: 'e7e5',
        depth: 18,
        multipv: 5
    })
}).then(r => r.json()).then(console.log);
```

**Should return evaluation data** (not an error)

---

## 💡 Pro Tips

### Tip 1: Start Fresh
If things are broken:
1. Close browser tab
2. Stop Flask server (Ctrl+C)
3. Restart Flask: `python app.py`
4. Open callibrator.html again
5. Click "Start Analysis Engine"
6. Try auto-analysis again

### Tip 2: Clear Browser Cache
Sometimes old JavaScript is cached:
1. Press Ctrl+Shift+R (hard refresh)
2. Or: Clear browser cache
3. Reload page

### Tip 3: Check Port Conflicts
If Flask won't start on port 5000:
```bash
# Check what's using port 5000
netstat -ano | findstr :5000

# Change port in app.py:
if __name__ == "__main__":
    app.run(debug=True, port=5001)  # Use 5001 instead

# Update API endpoint in browser:
http://localhost:5001/evaluate
```

---

## 📞 Getting Help

**Still stuck? Collect this info:**

1. **Flask server output** (copy/paste terminal)
2. **Browser console errors** (F12 → Console, screenshot)
3. **Steps you followed** (what did you click?)
4. **What happened vs what you expected**
5. **Your system:** Windows version, Python version

**Then:**
- Open a GitHub issue
- Include all the info above
- We'll help you debug!

---

## ✅ Success Indicators

**You know it's working when:**

1. ✅ Flask shows: "Running on http://127.0.0.1:5000"
2. ✅ Engine button is RED and says "Stop Analysis Engine"
3. ✅ Status shows "Engine: Running" in GREEN
4. ✅ Auto-analysis button shows progress
5. ✅ Board animates through moves
6. ✅ Samples appear in the table
7. ✅ Completion alert appears

**Congratulations!** 🎉 You're analyzing chess games automatically!

---

## 🎓 Understanding the Flow

```
User clicks "Start Auto-Analysis"
         ↓
    Check: engineRunning == true?
         ↓
    NO → Show error: "Please start the analysis engine first!"
    YES → Continue
         ↓
    Loop through all PGN moves
         ↓
    For each move:
        - Call Flask API: /evaluate
        - Get engine analysis
        - Log to samples array
        - Update UI
         ↓
    Show completion message
```

**The error occurs at the first check!**

So the fix is simple: **Make sure engine is started** before clicking auto-analysis.

---

**Remember:** The workflow is:
1. **Start Engine** (GREEN button) ← DON'T SKIP THIS!
2. Load PGN
3. Auto-Analyze

Not:
1. ~~Load PGN~~
2. ~~Auto-Analyze~~ ← Will fail!
3. ~~Start Engine~~

**Order matters!** 🎯

