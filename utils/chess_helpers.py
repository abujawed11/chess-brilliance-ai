"""
Lightweight helpers: engine spawn, eval parsing, multipv query.
Assumes Stockfish binary at engine/stockfish(.exe). Adjust ENGINE_PATH if needed.
"""
import os
import subprocess
import shlex

ENGINE_PATH = os.getenv("STOCKFISH_PATH", os.path.join("engine", "stockfish.exe" if os.name=="nt" else "stockfish"))

# Constants for normalization
CP_MAX = 3000  # Maximum centipawn value before mate territory
MATE_BASE = CP_MAX + 100  # Mate scores start just above CP_MAX

def to_root_cp(score, root_turn, node_turn):
    """
    Normalize a typed score to centipawns from root player's perspective.

    Args:
        score: dict with {'type': 'cp'|'mate', 'value': int}
        root_turn: bool - True if root position is White's turn
        node_turn: bool - True if node position is White's turn

    Returns:
        float: normalized centipawns from root player's perspective
        - CP scores: direct UCI value, flipped if needed
        - Mate scores: mapped to MATE_BASE ± (sign * DTM), bounded
    """
    if score is None:
        return 0.0

    # UCI always returns from White's perspective
    raw_value = score.get("value", 0)
    score_type = score.get("type", "cp")

    if score_type == "mate":
        # Mate in N moves
        # Positive = white mates, negative = black mates
        # Map to CP scale: closer mate = higher score
        if raw_value > 0:
            # White mates in raw_value moves
            cp_value = MATE_BASE + (100 - min(raw_value, 100))
        else:
            # Black mates in abs(raw_value) moves
            cp_value = -(MATE_BASE + (100 - min(abs(raw_value), 100)))
    else:
        # Regular centipawn score
        cp_value = float(raw_value)

    # Flip perspective if needed
    # If root is White and node is White: no flip (same perspective)
    # If root is White and node is Black: flip (opponent's perspective)
    # If root is Black and node is White: flip
    # If root is Black and node is Black: no flip
    if root_turn != node_turn:
        cp_value = -cp_value

    # If root is Black, flip everything to get Black's perspective
    if not root_turn:
        cp_value = -cp_value

    return cp_value

def start_engine(extra_options=None):
    """
    Start Stockfish as a subprocess with pipes.
    Returns (proc, send, recv) where send(cmd) sends UCI lines, recv() yields raw lines.
    """
    if not os.path.exists(ENGINE_PATH):
        raise FileNotFoundError(f"Stockfish binary not found at: {ENGINE_PATH}")
    proc = subprocess.Popen(
        [ENGINE_PATH],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True, bufsize=1
    )
    def send(cmd: str):
        proc.stdin.write(cmd + "\n")
        proc.stdin.flush()
    def recv():
        for line in proc.stdout:
            yield line.strip()
    # Init UCI
    send("uci")
    # set options
    if extra_options:
        for k,v in extra_options.items():
            send(f"setoption name {k} value {v}")
    send("isready")
    # consume until readyok
    for line in recv():
        if line == "readyok":
            break
    return proc, send, recv

def analyze_fen_multipv_persistent(fen: str, engine_tuple, depth: int = 18, multipv: int = 3):
    """
    Analyze position using a persistent engine (proc, send, recv).
    Returns list of dicts: [{'multipv':1,'score':{'type':'cp'|'mate','value':int},'pv':[SAN/UCI? raw tokens]}, ...]
    """
    proc, send, recv = engine_tuple
    send("ucinewgame")
    # Set MultiPV for this search
    send(f"setoption name MultiPV value {multipv}")
    send("isready")
    # Wait for readyok
    for line in recv():
        if line == "readyok":
            break
    send(f"position fen {fen}")
    send(f"go depth {depth}")
    lines = []
    results = {}
    for line in recv():
        if line.startswith("info "):
            parts = line.split()
            if "multipv" in parts and "score" in parts and "pv" in parts:
                try:
                    mpv = int(parts[parts.index("multipv")+1])
                    sc_idx = parts.index("score")
                    sc_type = parts[sc_idx+1]
                    sc_val = int(parts[sc_idx+2])
                    pv_idx = parts.index("pv")
                    pv_moves = parts[pv_idx+1:]
                    results[mpv] = {"multipv": mpv, "score": {"type": sc_type, "value": sc_val}, "pv": pv_moves}
                except Exception:
                    pass
        elif line.startswith("bestmove"):
            break

    # Sort results by multipv rank
    sorted_results = [results[k] for k in sorted(results.keys())]

    # Calculate gap between PV#1 and PV#2 (legacy, not used in new code)
    if len(sorted_results) >= 2:
        best_score = sorted_results[0]["score"]
        second_score = sorted_results[1]["score"]
        best_cp = best_score["value"] if best_score["type"] == "cp" else (10000 if best_score["value"] > 0 else -10000)
        second_cp = second_score["value"] if second_score["type"] == "cp" else (10000 if second_score["value"] > 0 else -10000)
        gap = abs(best_cp - second_cp)
        sorted_results[0]["gap_to_second"] = gap
    else:
        if sorted_results:
            sorted_results[0]["gap_to_second"] = 0

    return sorted_results

def analyze_fen_multipv(fen: str, depth: int = 18, multipv: int = 3, hash_mb: int = 256, threads: int = 2):
    """
    Returns list of dicts: [{'multipv':1,'score':{'type':'cp'|'mate','value':int},'pv':[SAN/UCI? raw tokens]}, ...]
    Note: We return PV as tokens (raw string split) for flexibility. You can later render SAN if needed.
    """
    proc, send, recv = start_engine({"Hash": hash_mb, "Threads": threads, "MultiPV": multipv})
    try:
        send("ucinewgame")  # Clear any previous game state
        send("isready")
        # Wait for readyok
        for line in recv():
            if line == "readyok":
                break
        send(f"position fen {fen}")
        send(f"go depth {depth}")
        lines = []
        results = {}
        for line in recv():
            if line.startswith("info "):
                # parse multipv, score, pv
                # examples:
                # info depth 18 seldepth 27 multipv 1 score cp 34 nodes ... pv e2e4 e7e5 ...
                # info depth 20 multipv 2 score mate 3 pv ...
                parts = line.split()
                if "multipv" in parts and "score" in parts and "pv" in parts:
                    try:
                        mpv = int(parts[parts.index("multipv")+1])
                        sc_idx = parts.index("score")
                        sc_type = parts[sc_idx+1]
                        sc_val = int(parts[sc_idx+2])
                        pv_idx = parts.index("pv")
                        pv_moves = parts[pv_idx+1:]
                        results[mpv] = {"multipv": mpv, "score": {"type": sc_type, "value": sc_val}, "pv": pv_moves}
                    except Exception:
                        pass
            elif line.startswith("bestmove"):
                break

        # Sort results by multipv rank
        sorted_results = [results[k] for k in sorted(results.keys())]

        # Calculate gap between PV#1 and PV#2 (if both exist)
        if len(sorted_results) >= 2:
            best_score = sorted_results[0]["score"]
            second_score = sorted_results[1]["score"]

            # Convert both to centipawns (using a simple conversion)
            best_cp = best_score["value"] if best_score["type"] == "cp" else (10000 if best_score["value"] > 0 else -10000)
            second_cp = second_score["value"] if second_score["type"] == "cp" else (10000 if second_score["value"] > 0 else -10000)

            gap = abs(best_cp - second_cp)
            sorted_results[0]["gap_to_second"] = gap
        else:
            # Only one line or no lines
            if sorted_results:
                sorted_results[0]["gap_to_second"] = 0

        return sorted_results
    finally:
        try:
            proc.kill()
        except Exception:
            pass

def cp_from_score(score: dict, side_to_move: str) -> float:
    """
    Normalize engine score to centipawns from the perspective of side_to_move.
    score like {'type':'cp'|'mate','value':int}
    Positive = good for side_to_move.

    IMPORTANT: UCI engines ALWAYS return scores from White's perspective.
    We need to flip the sign if side_to_move is Black.
    """
    if score is None:
        return 0.0

    if score["type"] == "mate":
        # Mate scores: use large sentinel cp scaled by sign.
        mate_value = 100000 if score["value"] > 0 else -100000
        # Flip sign for Black's perspective
        return mate_value if side_to_move == 'w' else -mate_value

    # UCI returns from White's perspective, flip for Black
    cp_value = float(score["value"])
    return cp_value if side_to_move == 'w' else -cp_value
