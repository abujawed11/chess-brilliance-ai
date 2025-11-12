# test/self_test_eval.py
import os
import sys

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.chess_helpers import (
    analyze_fen_multipv_persistent,
    cp_from_score,
    start_engine,
    to_root_cp,
)

TESTS = [
    ("7k/8/8/8/8/8/7Q/K7 w - - 0 1", True,  "KQ vs K  (White to move)"),
    ("7k/8/8/8/8/8/7Q/K7 b - - 0 1", True,  "KQ vs K  (Black to move)"),
    ("k7/8/8/8/8/8/8/K6q w - - 0 1", True,  "K vs KQ  (White to move)"),
    ("k7/8/8/8/8/8/8/K6q b - - 0 1", True,  "K vs KQ  (Black to move)"),
    ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", True, "Start (White to move)"),
    ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1", True, "Start (Black to move)"),
]

def pretty_score(s):
    t, v = s.get("type"), s.get("value")
    if t == "cp":
        return f"cp {v:+d}"
    if t == "mate":
        sign = "+" if v > 0 else ""
        return f"mate {sign}{v}"
    return str(s)

def main():
    # Start persistent engine like your server does
    cfg = {"Hash": 256, "Threads": 2}
    engine = start_engine(cfg)  # (proc, send, recv)
    print(f"Engine started. STOCKFISH_PATH={os.getenv('STOCKFISH_PATH','<>')}")
    print(f"Engine started. STOCKFISH_PATH={os.getenv('STOCKFISH_PATH', r'D:\react\chess_brilliance_ai\engine\stockfish.exe')}")


    try:
        for fen, root_is_white, label in TESTS:
            pre = analyze_fen_multipv_persistent(fen, engine, depth=12, multipv=5)  # depth 12 to avoid timeouts
            print(f"\n[{label}] FEN: {fen}")
            if not pre:
                print("  [X] No PVs returned (pre == []).")
                print("    Hints: check STOCKFISH_PATH, AV permissions, helper timeouts, or reduce depth.")
                continue

            raw_best = pre[0]["score"]                    # {"type":"cp"|"mate","value":int}
            raw_best_cp = cp_from_score(raw_best)         # White-centric cp (mates mapped)
            root_best_cp = to_root_cp(raw_best, root_is_white, root_is_white)

            print(f"  RAW best:  {pretty_score(raw_best)}  -> raw_cp={raw_best_cp:+}")
            print(f"  ROOT best: root_is_white={root_is_white} -> {root_best_cp:+}")

    finally:
        # Stop engine
        try:
            p, send, recv = engine
            p.kill()
        except Exception:
            pass

if __name__ == "__main__":
    main()
