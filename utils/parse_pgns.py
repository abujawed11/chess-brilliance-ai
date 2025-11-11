"""
Read PGNs, yield (game_id, ply_index, fen_before, played_uci, side_to_move).
Writes a Parquet at data/samples/positions.parquet
"""
import os
import pandas as pd
import chess.pgn
from tqdm import tqdm

RAW_DIR = os.path.join("data", "raw_pgns")
OUT = os.path.join("data", "samples", "positions.parquet")

def iter_positions_from_pgn(pgn_path):
    with open(pgn_path, "r", encoding="utf-8", errors="ignore") as f:
        while True:
            game = chess.pgn.read_game(f)
            if game is None:
                break
            game_id = game.headers.get("Event", "Unknown") + "_" + game.headers.get("Site","")
            board = game.board()
            for i, move in enumerate(game.mainline_moves()):
                fen_before = board.fen()
                side = 'w' if board.turn else 'b'
                uci = move.uci()
                yield {"game_id": game_id, "ply_index": i, "fen_before": fen_before, "played_uci": uci, "side": side}
                board.push(move)

def main():
    rows = []
    for name in os.listdir(RAW_DIR):
        if not name.lower().endswith(".pgn"):
            continue
        for row in tqdm(iter_positions_from_pgn(os.path.join(RAW_DIR, name)), desc=f"PGN {name}"):
            rows.append(row)
    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if not rows:
        print("No positions found. Put .pgn files into data/raw_pgns/")
        return
    df.to_parquet(OUT, index=False)
    print(f"Wrote {len(df)} positions → {OUT}")

if __name__ == "__main__":
    main()
