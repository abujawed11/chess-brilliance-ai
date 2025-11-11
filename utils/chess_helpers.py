"""
Lightweight helpers: engine spawn, eval parsing, multipv query.
Assumes Stockfish binary at engine/stockfish(.exe). Adjust ENGINE_PATH if needed.
"""
import os
import subprocess
import shlex

ENGINE_PATH = os.getenv("STOCKFISH_PATH", os.path.join("engine", "stockfish.exe" if os.name=="nt" else "stockfish"))

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

def analyze_fen_multipv(fen: str, depth: int = 18, multipv: int = 3, hash_mb: int = 256, threads: int = 2):
    """
    Returns list of dicts: [{'multipv':1,'score':{'type':'cp'|'mate','value':int},'pv':[SAN/UCI? raw tokens]}, ...]
    Note: We return PV as tokens (raw string split) for flexibility. You can later render SAN if needed.
    """
    proc, send, recv = start_engine({"Hash": hash_mb, "Threads": threads, "MultiPV": multipv})
    try:
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
        return [results[k] for k in sorted(results.keys())]
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
    """
    if score is None:
        return 0.0
    if score["type"] == "mate":
        # Mate scores: use large sentinel cp scaled by sign.
        # Positive value means mating for side_to_move.
        return 100000 if score["value"] > 0 else -100000
    # cp value already signed from side-to-move perspective in UCI lines
    return float(score["value"])
