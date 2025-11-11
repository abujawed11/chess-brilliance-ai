"""
Core teacher: read positions, run MultiPV before+after the played move,
compute cp_loss, motif flags, and assign label via rules.
Writes Parquet at data/labeled_features/teacher_labels.parquet
"""
import os
import pandas as pd
import chess
from tqdm import tqdm
from utils.chess_helpers import analyze_fen_multipv, cp_from_score
from teacher.label_rules import label_move
from teacher.detect_motifs import detect_motifs

SRC = os.path.join("data", "samples", "positions_sample.parquet")
OUT = os.path.join("data", "labeled_features", "teacher_labels.parquet")

DEPTH = int(os.getenv("TEACHER_DEPTH", "20"))
MULTIPV = int(os.getenv("TEACHER_MULTIPV", "5"))

def played_rank_in_pvs(uci_move: str, pvs: list) -> int:
    for d in pvs:
        pv = d.get("pv", [])
        if pv and pv[0].lower().startswith(uci_move[:4]):
            return d["multipv"]
    return 99

def main():
    df = pd.read_parquet(SRC)
    rows = []
    for row in tqdm(df.itertuples(index=False), total=len(df), desc="Analyzing"):
        fen = row.fen_before
        played = row.played_uci
        side = row.side

        pre = analyze_fen_multipv(fen, depth=DEPTH, multipv=MULTIPV)
        if not pre:
            continue
        pre_best = pre[0]
        pre_best_cp = cp_from_score(pre_best["score"], side)
        pre_gap = 0.0
        if len(pre) >= 2:
            pv2_cp = cp_from_score(pre[1]["score"], side)
            pre_gap = pre_best_cp - pv2_cp

        board = chess.Board(fen)
        try:
            board.push_uci(played)
        except Exception:
            continue
        post_fen = board.fen()
        post = analyze_fen_multipv(post_fen, depth=DEPTH, multipv=MULTIPV)
        if not post:
            continue
        post_best_cp = cp_from_score(post[0]["score"], 'w' if board.turn else 'b')

        cp_loss = pre_best_cp - (-post_best_cp)
        played_rank = played_rank_in_pvs(played, pre)
        material_delta_cp = 0

        motifs = detect_motifs(material_delta_cp=material_delta_cp, pre_top_gap=pre_gap)
        robust = True

        features = {
            "fen_before": fen,
            "played_uci": played,
            "side": side,
            "depth": DEPTH,
            "pre_top_gap": pre_gap,
            "played_rank": played_rank,
            "cp_loss": float(cp_loss),
            "is_sac": motifs["is_sac"],
            "is_book": motifs.get("is_book", False),
            "robust": robust
        }

        label = label_move(
            fen=fen,
            move=played,
            eval_before=pre_best_cp,
            eval_after=post_best_cp,
            multipv_rank=played_rank,
            is_sacrifice=motifs["is_sac"],
            is_book=motifs.get("is_book", False)
        )
        features["label"] = label
        rows.append(features)

    if not rows:
        print("No rows produced. Check engine path and input positions.")
        return

    out_df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out_df.to_parquet(OUT, index=False)
    print(f"Wrote {len(out_df)} labeled rows → {OUT}")

if __name__ == "__main__":
    main()
