

# import sys
# import os

# # ----------------------------
# # Path + env setup
# # ----------------------------
# current_dir = os.path.dirname(os.path.abspath(__file__))
# project_root = os.path.dirname(current_dir)

# sys.path.insert(0, project_root)

# from dotenv import load_dotenv
# env_path = os.path.join(project_root, '.env')
# load_dotenv(env_path, override=True)

# # Explicitly set STOCKFISH_PATH if not already set
# if not os.getenv('STOCKFISH_PATH'):
#     stockfish_path = os.path.join(project_root, 'engine', 'stockfish.exe')
#     os.environ['STOCKFISH_PATH'] = stockfish_path
#     print(f"[WARNING] STOCKFISH_PATH not in env, setting to: {stockfish_path}")
# else:
#     print(f"[OK] STOCKFISH_PATH loaded: {os.getenv('STOCKFISH_PATH')}")

# # ----------------------------
# # Imports
# # ----------------------------
# from flask import Flask, request, jsonify
# from flask_cors import CORS
# import chess
# import logging

# from utils.chess_helpers import (
#     analyze_fen_multipv,
#     analyze_fen_multipv_persistent,
#     cp_from_score,
#     start_engine,
#     to_root_cp,
#     ENGINE_PATH,
# )

# from teacher.label_rules import label_move

# from basic_move_labels import (
#     classify_basic_move,
#     detect_miss,
#     detect_book_move,
# )

# from basic_move_labels import (
#     classify_basic_move,
#     detect_miss,
#     detect_book_move,
#     classify_exclam_move,
# )



# from opening_book import is_book_move

# # ----------------------------
# # Flask app
# # ----------------------------
# app = Flask(__name__)
# CORS(app)

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # ----------------------------
# # Global persistent engine
# # ----------------------------
# persistent_engine = None
# engine_lock = False

# # ----------------------------
# # Material values / helpers
# # ----------------------------
# PIECE_VALUES = {
#     chess.PAWN: 100,
#     chess.KNIGHT: 300,
#     chess.BISHOP: 300,
#     chess.ROOK: 500,
#     chess.QUEEN: 900,
#     chess.KING: 0,
# }

# MATE_CP   = 32000
# MATE_STEP = 1000  # drop per ply


# def eval_for_white(score: dict, side_to_move: str) -> int:
#     """
#     Convert a Stockfish score dict + side_to_move into a centipawn eval
#     from White's perspective ONLY.

#     +ve => good for White
#     -ve => good for Black
#     """
#     if not score:
#         return 0

#     t = score.get("type")
#     v = score.get("value", 0)

#     # Normal cp case
#     if t == "cp":
#         try:
#             v = int(v)
#         except Exception:
#             v = 0
#         # Stockfish cp is from side-to-move POV
#         return v if side_to_move == "w" else -v

#     # Mate case
#     if t == "mate":
#         try:
#             v = int(v)
#         except Exception:
#             v = 0

#         # v is mate score from side-to-move POV
#         # side_to_move = 'w':
#         #   v > 0 -> White mates
#         #   v < 0 -> White gets mated
#         # side_to_move = 'b':
#         #   v > 0 -> Black mates (White gets mated)
#         #   v < 0 -> Black gets mated (White mates)
#         sign_for_white = 1 if side_to_move == "w" else -1
#         white_mate_val = v * sign_for_white   # >0: White mates, <0: White gets mated

#         if white_mate_val == 0:
#             return 0

#         n = abs(white_mate_val)
#         base = max(0, MATE_CP - MATE_STEP * n)
#         return base if white_mate_val > 0 else -base

#     # Fallback
#     try:
#         return int(v)
#     except Exception:
#         return 0


# def piece_cp(board: chess.Board, sq: chess.Square) -> int:
#     p = board.piece_at(sq)
#     return PIECE_VALUES.get(p.piece_type, 0) if p else 0


# def naive_see(board: chess.Board, square: chess.Square, side_to_move: bool) -> int:
#     """
#     Very small static-exchange eval on `square`.
#     Returns net cp for `side_to_move` assuming optimal local swaps.
#     """
#     def attackers(side):
#         return sorted(
#             (sq for sq in board.attackers(side, square)),
#             key=lambda s: PIECE_VALUES[board.piece_at(s).piece_type]
#         )

#     gain = []
#     occupied = set()
#     color = side_to_move
#     target_value = piece_cp(board, square)  # 0 if quiet

#     while True:
#         atk = [s for s in attackers(color) if s not in occupied]
#         if not atk:
#             break
#         from_sq = atk[0]  # least valuable attacker
#         gain.append(target_value)
#         target_value = PIECE_VALUES[board.piece_at(from_sq).piece_type]
#         occupied.add(from_sq)
#         color = not color

#     for i in range(len(gain) - 2, -1, -1):
#         gain[i] = -max(-gain[i], gain[i + 1])
#     return gain[0] if gain else 0


# MIN_SAC_CP = 100
# SEE_PENALTY_CP = 0   # not used directly but kept for tuning


# def is_real_sacrifice(board_before: chess.Board, move: chess.Move,
#                       eval_before=None, eval_after=None, eval_types=None) -> bool:
#     """
#     Sacrifice detection using SEE + material debit.
#     """
#     board = board_before.copy()
#     mover = board.turn
#     from_sq, to_sq = move.from_square, move.to_square
#     moved_piece = board.piece_at(from_sq)
#     if moved_piece is None:
#         return False

#     moved_cp    = PIECE_VALUES[moved_piece.piece_type]
#     captured_cp = piece_cp(board, to_sq)

#     # Handle en passant capture
#     if board_before.is_en_passant(move):
#         captured_cp = PIECE_VALUES[chess.PAWN]

#     see_net_for_mover = naive_see(board_before, to_sq, mover)
#     gives_check = board.gives_check(move)

#     board.push(move)

#     net_loss_cp = moved_cp - captured_cp
#     opp_can_capture_back = board.is_attacked_by(not mover, to_sq)

#     # Gate A: debit + opponent can accept + SEE < 0
#     if net_loss_cp >= MIN_SAC_CP and opp_can_capture_back and see_net_for_mover < 0:
#         return True

#     # Gate B: destination square is simply losing via SEE
#     if see_net_for_mover < 0:
#         return True

#     # Gate C: forcing sac (check/mate) with acceptability
#     mate_before = (eval_types and eval_types.get("before") == "mate")
#     mate_after  = (eval_types and eval_types.get("after")  == "mate")
#     if (gives_check or mate_after or mate_before) and (
#         see_net_for_mover < 0 or (opp_can_capture_back and net_loss_cp >= MIN_SAC_CP)
#     ):
#         return True

#     return False


# def played_rank_and_gap(uci_move, pvs, side_to_move: str):
#     """
#     Return (rank, top_gap_cp, played_eval_cp, best_eval_cp) using
#     White-perspective centipawns.

#     - best_eval_cp: eval_for_white(PV#1 score, side_to_move-before)
#     - played_eval_cp: eval_for_white(played move score, side_to_move-before)
#     - top_gap_cp: |best_eval_cp - played_eval_cp|
#     """
#     if not pvs:
#         return (1, None, None, None)

#     uci_move_normalized = uci_move.lower().strip().replace("=", "")
#     K = len(pvs)

#     best_eval_cp = eval_for_white(pvs[0]["score"], side_to_move)

#     for pv_entry in pvs:
#         pv = pv_entry.get("pv", [])
#         if not pv:
#             continue

#         pv_move = pv[0].lower().strip().replace("=", "")

#         is_match = False
#         if pv_move == uci_move_normalized:
#             is_match = True
#         elif len(pv_move) >= 4 and len(uci_move_normalized) >= 4 and pv_move[:4] == uci_move_normalized[:4]:
#             if len(pv_move) == len(uci_move_normalized):
#                 if len(pv_move) == 4:
#                     is_match = True
#                 elif len(pv_move) == 5 and pv_move[4] == uci_move_normalized[4]:
#                     is_match = True
#             else:
#                 # Accept base move equality for promotions (assume Q if missing)
#                 is_match = True

#         if is_match:
#             rank = pv_entry["multipv"]
#             played_eval_cp = eval_for_white(pv_entry["score"], side_to_move)
#             top_gap = abs(best_eval_cp - played_eval_cp)
#             logger.info(
#                 f"Move '{uci_move_normalized}' found at rank {rank}, gap={top_gap:.1f}cp"
#             )
#             return (rank, top_gap, played_eval_cp, best_eval_cp)

#     logger.warning(
#         f"Move '{uci_move_normalized}' not found in any PV. "
#         f"Available first moves: {[pv.get('pv', [''])[0] if pv.get('pv') else '' for pv in pvs]}"
#     )
#     return (K + 1, None, None, best_eval_cp)


# # ----------------------------
# # Engine control endpoints
# # ----------------------------
# @app.route("/start_engine", methods=["POST"])
# def start_engine_endpoint():
#     global persistent_engine, engine_lock
#     try:
#         if persistent_engine is not None:
#             return jsonify({"status": "already_running", "message": "Engine is already running"})

#         logger.info(f"STOCKFISH_PATH from env: {os.getenv('STOCKFISH_PATH')}")
#         logger.info(f"ENGINE_PATH being used: {ENGINE_PATH}")
#         logger.info(f"Engine file exists: {os.path.exists(ENGINE_PATH)}")

#         logger.info("Starting persistent Stockfish engine...")
#         hash_mb = 512
#         threads = 2
#         persistent_engine = start_engine({"Hash": hash_mb, "Threads": threads})
#         logger.info(f"Stockfish engine started (Hash={hash_mb}MB, Threads={threads})")
#         return jsonify({"status": "started", "message": "Engine started successfully"})
#     except Exception as e:
#         logger.error(f"Failed to start engine: {str(e)}", exc_info=True)
#         return jsonify({"status": "error", "message": str(e)}), 500


# @app.route("/stop_engine", methods=["POST"])
# def stop_engine_endpoint():
#     global persistent_engine, engine_lock
#     try:
#         if persistent_engine is None:
#             return jsonify({"status": "not_running", "message": "Engine is not running"})
#         logger.info("Stopping persistent Stockfish engine...")
#         proc, send, recv = persistent_engine
#         try:
#             proc.kill()
#         except Exception:
#             pass
#         persistent_engine = None
#         logger.info("Engine stopped")
#         return jsonify({"status": "stopped", "message": "Engine stopped successfully"})
#     except Exception as e:
#         logger.error(f"Failed to stop engine: {str(e)}")
#         return jsonify({"status": "error", "message": str(e)}), 500


# # ----------------------------
# # Analysis helper
# # ----------------------------
# def analyze_or_fail(fen: str, depth: int, multipv: int, engine):
#     """Return PV list or raise with a clear message after retries."""
#     tries = [
#         (depth, multipv),
#         (max(8, depth - 4), multipv),
#         (max(6, depth - 6), 1),
#     ]
#     last_err = None
#     for d, k in tries:
#         try:
#             if engine is not None:
#                 pvs = analyze_fen_multipv_persistent(fen, engine, depth=d, multipv=k)
#             else:
#                 pvs = analyze_fen_multipv(fen, depth=d, multipv=k)
#             if pvs:
#                 return pvs
#         except Exception as e:
#             last_err = e
#     raise RuntimeError(
#         f"No PVs returned for fen='{fen[:60]}...' (depth tried: {tries}). "
#         f"Engine may have died or timed out. Last error: {last_err}"
#     )


# # ----------------------------
# # /evaluate endpoint
# # ----------------------------
# @app.route("/evaluate", methods=["POST"])
# def evaluate_move():
#     def mate_ply(score_dict):
#         if not score_dict:
#             return None
#         if score_dict.get("type") == "mate":
#             try:
#                 return abs(int(score_dict.get("value", 0)))
#             except Exception:
#                 return None
#         return None

#     global persistent_engine

#     data = request.json
#     fen = data.get("fen")
#     move = data.get("move")
#     depth = int(data.get("depth", 18))
#     multipv = int(data.get("multipv", 5))

#     logger.info(f"Evaluating move: {move} for FEN: {fen[:60]}...")

#     try:
#         board_before = chess.Board(fen)
#         fen_before = fen
#         side_before = "w" if board_before.turn == chess.WHITE else "b"
#         fullmove_number = board_before.fullmove_number

#         # --- PRE analysis (multi-PV) ---
#         pre = analyze_or_fail(fen_before, depth, multipv, persistent_engine)
#         pre_score = pre[0]["score"]
#         eval_before_cp = eval_for_white(pre_score, side_before)

#         multipv_rank, top_gap, played_eval_from_pre, best_eval_from_pre = played_rank_and_gap(
#             move, pre, side_before
#         )

#         # --- POST analysis (single PV) ---
#         board_after = board_before.copy()
#         board_after.push_uci(move)
#         post_fen = board_after.fen()
#         post = analyze_or_fail(post_fen, depth, 1, persistent_engine)
#         post_score = post[0]["score"]

#         side_after = "w" if board_after.turn == chess.WHITE else "b"
#         eval_after_cp = eval_for_white(post_score, side_after)

#         logger.info(
#             f"[EVAL] pre={eval_before_cp:+} post={eval_after_cp:+} "
#             f"(Δ {eval_after_cp - eval_before_cp:+})"
#         )

#         # --- CPL calculation ---
#         if played_eval_from_pre is None:
#             played_eval_from_pre = eval_after_cp

#         cpl = (
#             abs(best_eval_from_pre - played_eval_from_pre)
#             if best_eval_from_pre is not None
#             else None
#         )

#         if top_gap is None:
#             top_gap = cpl

#         eval_change = eval_after_cp - eval_before_cp

#         # --- Basic label (Best / Good / Inaccuracy / Mistake / Blunder) ---
#         basic_label = classify_basic_move(
#             eval_before_white=eval_before_cp,
#             eval_after_white=eval_after_cp,
#             cpl=cpl,
#             mover_color=side_before,
#             multipv_rank=multipv_rank,
#         )

#         print("Basic label:", basic_label)

#         # --- Sacrifice detection ---
#         uci_move_obj = chess.Move.from_uci(move)
#         is_sacrifice = is_real_sacrifice(board_before, uci_move_obj)

#         # --- Mate metadata ---
#         best_mate_in = mate_ply(pre_score)
#         played_mate_in = mate_ply(post_score)

#         pre_is_mate = pre_score.get("type") == "mate"
#         post_is_mate = post_score.get("type") == "mate"

#         mate_flip = bool(pre_is_mate and post_is_mate and (eval_before_cp * eval_after_cp < 0))
#         mate_flip_severity = 0
#         if mate_flip:
#             mate_flip_severity = 6400 + 100 * ((best_mate_in or 0) + (played_mate_in or 0))

#         # --- General Miss detection (new logic) ---
#         is_miss = detect_miss(
#             eval_before_white=eval_before_cp,
#             eval_after_white=eval_after_cp,
#             eval_best_white=best_eval_from_pre,
#             mover_color=side_before,
#             best_mate_in_plies=best_mate_in,
#             played_mate_in_plies=played_mate_in,
#         )

#         print("Miss detected:", is_miss)

#         # --- Book detection (tiny custom opening DB + heuristics) ---
#         in_opening_db = is_book_move(fen_before, move)  # move is UCI string
#         is_book = detect_book_move(
#             fullmove_number=fullmove_number,
#             eval_before_white=eval_before_cp,
#             eval_after_white=eval_after_cp,
#             cpl=cpl,
#             multipv_rank=multipv_rank,
#             in_opening_db=in_opening_db,
#         )

#         print("is_book: ", is_book)

#         gap_for_label = top_gap if top_gap is not None else 0


#         exclam_label, brill_info = classify_exclam_move(
#             eval_before_white=eval_before_cp,
#             eval_after_white=eval_after_cp,
#             eval_best_white=best_eval_from_pre,
#             mover_color=side_before,
#             is_sacrifice=is_sacrifice,
#             is_book=is_book,
#             multipv_rank=multipv_rank,
#             played_eval_from_pre_white=played_eval_from_pre,
#             best_mate_in_plies_pre=best_mate_in,
#             played_mate_in_plies_post=played_mate_in,
#             mate_flip=mate_flip,
#         )


#         # --- Final label priority: Book > Brilliant (mate flip) > Miss > basic ---
#         # if is_book:
#         #     label = "Book"

#         # elif mate_flip:
#         #     if eval_before_cp > 0 and eval_after_cp < 0:
#         #         label = "Blunder"   # threw away a winning mate
#         #     elif eval_before_cp < 0 and eval_after_cp > 0:
#         #         label = "Brilliant" # turned a lost mate into winning for your side
#         #     else:
#         #         label = label_move(
#         #             fen_before, move, eval_before_cp, eval_after_cp,
#         #             multipv_rank, is_sacrifice, is_book, gap_for_label
#         #         )

#         # elif is_miss:
#         #     label = "Miss"

#         # else:
#         #     label = label_move(
#         #         fen_before, move, eval_before_cp, eval_after_cp,
#         #         multipv_rank, is_sacrifice, is_book, gap_for_label
#         #     )

#         if is_book:
#             label = "Book"
#         elif exclam_label == "Blunder":
#             label = "Blunder"   # mate-flip catastrophe
#         elif exclam_label in ("Brilliant", "Great"):
#             label = exclam_label
#         elif is_miss:
#             label = "Miss"
#         else:
#             label = basic_label


#         return jsonify({
#             "fen_before": fen_before,
#             "eval_before": eval_before_cp,
#             "eval_after": eval_after_cp,
#             "eval_change": eval_change,
#             "multipv_rank": multipv_rank,
#             "top_gap": top_gap,
#             "cpl": cpl,
#             "eval_before_struct": pre_score,
#             "eval_after_struct": post_score,
#             "is_sacrifice": is_sacrifice,
#             "best_mate_in": best_mate_in,
#             "played_mate_in": played_mate_in,
#             "mate_flip": mate_flip,
#             "mate_flip_severity": mate_flip_severity,
#             "basic_label": basic_label,
#             "miss_detected": is_miss,
#             "is_book": is_book,
#             "label": label,
#         })

#     except Exception as e:
#         logger.error(f"Error in /evaluate: {str(e)}", exc_info=True)
#         return jsonify({
#             "error": "ENGINE_ANALYSIS_FAILED",
#             "message": str(e),
#         }), 500


# # ----------------------------
# # Entrypoint
# # ----------------------------
# if __name__ == "__main__":
#     app.run(debug=True)










import sys
import os

# ----------------------------
# Path + env setup
# ----------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

sys.path.insert(0, project_root)

from dotenv import load_dotenv
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path, override=True)

# Explicitly set STOCKFISH_PATH if not already set
if not os.getenv('STOCKFISH_PATH'):
    stockfish_path = os.path.join(project_root, 'engine', 'stockfish.exe')
    os.environ['STOCKFISH_PATH'] = stockfish_path
    print(f"[WARNING] STOCKFISH_PATH not in env, setting to: {stockfish_path}")
else:
    print(f"[OK] STOCKFISH_PATH loaded: {os.getenv('STOCKFISH_PATH')}")

# ----------------------------
# Imports
# ----------------------------
from flask import Flask, request, jsonify
from flask_cors import CORS
import chess
import logging

from utils.chess_helpers import (
    analyze_fen_multipv,
    analyze_fen_multipv_persistent,
    start_engine,
    ENGINE_PATH,
)

from basic_move_labels import (
    classify_basic_move,
    detect_miss,
    detect_book_move,
    classify_exclam_move,
)

from opening_book import is_book_move

from basic_move_labels import is_real_sacrifice


# ----------------------------
# Flask app
# ----------------------------
app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------
# Global persistent engine
# ----------------------------
persistent_engine = None

# ----------------------------
# Material values / helpers
# ----------------------------
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

MATE_CP   = 32000
MATE_STEP = 1000  # drop per ply


def eval_for_white(score: dict, side_to_move: str) -> int:
    """
    Convert a Stockfish score dict + side_to_move into a centipawn eval
    from White's perspective ONLY.

    +ve => good for White
    -ve => good for Black
    """
    if not score:
        return 0

    t = score.get("type")
    v = score.get("value", 0)

    # Normal cp case
    if t == "cp":
        try:
            v = int(v)
        except Exception:
            v = 0
        # Stockfish cp is from side-to-move POV
        return v if side_to_move == "w" else -v

    # Mate case
    if t == "mate":
        try:
            v = int(v)
        except Exception:
            v = 0

        # v is mate score from side-to-move POV
        # side_to_move = 'w':
        #   v > 0 -> White mates
        #   v < 0 -> White gets mated
        # side_to_move = 'b':
        #   v > 0 -> Black mates (White gets mated)
        #   v < 0 -> Black gets mated (White mates)
        sign_for_white = 1 if side_to_move == "w" else -1
        white_mate_val = v * sign_for_white   # >0: White mates, <0: White gets mated

        if white_mate_val == 0:
            return 0

        n = abs(white_mate_val)
        base = max(0, MATE_CP - MATE_STEP * n)
        return base if white_mate_val > 0 else -base

    # Fallback
    try:
        return int(v)
    except Exception:
        return 0



def played_rank_and_gap(uci_move, pvs, side_to_move: str):
    """
    Return (rank, top_gap_cp, played_eval_cp, best_eval_cp) using
    White-perspective centipawns.

    - best_eval_cp: eval_for_white(PV#1 score, side_to_move-before)
    - played_eval_cp: eval_for_white(played move score, side_to_move-before)
    - top_gap_cp: |best_eval_cp - played_eval_cp|
    """
    if not pvs:
        return (1, None, None, None)

    uci_move_normalized = uci_move.lower().strip().replace("=", "")
    K = len(pvs)

    best_eval_cp = eval_for_white(pvs[0]["score"], side_to_move)

    for pv_entry in pvs:
        pv = pv_entry.get("pv", [])
        if not pv:
            continue

        pv_move = pv[0].lower().strip().replace("=", "")

        is_match = False
        if pv_move == uci_move_normalized:
            is_match = True
        elif len(pv_move) >= 4 and len(uci_move_normalized) >= 4 and pv_move[:4] == uci_move_normalized[:4]:
            if len(pv_move) == len(uci_move_normalized):
                if len(pv_move) == 4:
                    is_match = True
                elif len(pv_move) == 5 and pv_move[4] == uci_move_normalized[4]:
                    is_match = True
            else:
                # Accept base move equality for promotions (assume Q if missing)
                is_match = True

        if is_match:
            rank = pv_entry["multipv"]
            played_eval_cp = eval_for_white(pv_entry["score"], side_to_move)
            top_gap = abs(best_eval_cp - played_eval_cp)
            logger.info(
                f"Move '{uci_move_normalized}' found at rank {rank}, gap={top_gap:.1f}cp"
            )
            return (rank, top_gap, played_eval_cp, best_eval_cp)

    logger.warning(
        f"Move '{uci_move_normalized}' not found in any PV. "
        f"Available first moves: {[pv.get('pv', [''])[0] if pv.get('pv') else '' for pv in pvs]}"
    )
    return (K + 1, None, None, best_eval_cp)


# ----------------------------
# Engine control endpoints
# ----------------------------
@app.route("/start_engine", methods=["POST"])
def start_engine_endpoint():
    global persistent_engine
    try:
        if persistent_engine is not None:
            return jsonify({"status": "already_running", "message": "Engine is already running"})

        logger.info(f"STOCKFISH_PATH from env: {os.getenv('STOCKFISH_PATH')}")
        logger.info(f"ENGINE_PATH being used: {ENGINE_PATH}")
        logger.info(f"Engine file exists: {os.path.exists(ENGINE_PATH)}")

        logger.info("Starting persistent Stockfish engine...")
        hash_mb = 512
        threads = 2
        persistent_engine = start_engine({"Hash": hash_mb, "Threads": threads})
        logger.info(f"Stockfish engine started (Hash={hash_mb}MB, Threads={threads})")
        return jsonify({"status": "started", "message": "Engine started successfully"})
    except Exception as e:
        logger.error(f"Failed to start engine: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/stop_engine", methods=["POST"])
def stop_engine_endpoint():
    global persistent_engine
    try:
        if persistent_engine is None:
            return jsonify({"status": "not_running", "message": "Engine is not running"})
        logger.info("Stopping persistent Stockfish engine...")
        proc, send, recv = persistent_engine
        try:
            proc.kill()
        except Exception:
            pass
        persistent_engine = None
        logger.info("Engine stopped")
        return jsonify({"status": "stopped", "message": "Engine stopped successfully"})
    except Exception as e:
        logger.error(f"Failed to stop engine: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ----------------------------
# Analysis helper
# ----------------------------
def analyze_or_fail(fen: str, depth: int, multipv: int, engine):
    """Return PV list or raise with a clear message after retries."""
    tries = [
        (depth, multipv),
        (max(8, depth - 4), multipv),
        (max(6, depth - 6), 1),
    ]
    last_err = None
    for d, k in tries:
        try:
            if engine is not None:
                pvs = analyze_fen_multipv_persistent(fen, engine, depth=d, multipv=k)
            else:
                pvs = analyze_fen_multipv(fen, depth=d, multipv=k)
            if pvs:
                return pvs
        except Exception as e:
            last_err = e
    raise RuntimeError(
        f"No PVs returned for fen='{fen[:60]}...' (depth tried: {tries}). "
        f"Engine may have died or timed out. Last error: {last_err}"
    )


# ----------------------------
# /evaluate endpoint
# ----------------------------
@app.route("/evaluate", methods=["POST"])
def evaluate_move():
    def mate_ply(score_dict):
        if not score_dict:
            return None
        if score_dict.get("type") == "mate":
            try:
                return abs(int(score_dict.get("value", 0)))
            except Exception:
                return None
        return None

    global persistent_engine

    data = request.json
    fen = data.get("fen")
    move = data.get("move")
    depth = int(data.get("depth", 18))
    multipv = int(data.get("multipv", 5))

    logger.info(f"Evaluating move: {move} for FEN: {fen[:60]}...")

    try:
        board_before = chess.Board(fen)
        fen_before = fen
        side_before = "w" if board_before.turn == chess.WHITE else "b"
        fullmove_number = board_before.fullmove_number

        # --- PRE analysis (multi-PV) ---
        pre = analyze_or_fail(fen_before, depth, multipv, persistent_engine)
        pre_score = pre[0]["score"]
        eval_before_cp = eval_for_white(pre_score, side_before)

        multipv_rank, top_gap, played_eval_from_pre, best_eval_from_pre = played_rank_and_gap(
            move, pre, side_before
        )

        # --- POST analysis (single PV) ---
        board_after = board_before.copy()
        board_after.push_uci(move)
        post_fen = board_after.fen()

        # Check if the position is game over (checkmate, stalemate, etc.)
        if board_after.is_checkmate():
            # Checkmate: the side to move is mated
            # Use mate value of -1 to indicate the side to move has been checkmated
            # (mate in 1 against them = already mated)
            post_score = {"type": "mate", "value": -1}
            logger.info(f"Position after move is CHECKMATE")
        elif board_after.is_stalemate():
            # Stalemate: position is drawn, eval = 0
            post_score = {"type": "cp", "value": 0}
            logger.info(f"Position after move is STALEMATE")
        elif board_after.is_game_over():
            # Other game over (insufficient material, repetition, 50-move rule, etc.)
            post_score = {"type": "cp", "value": 0}
            logger.info(f"Position after move is GAME OVER (draw)")
        else:
            # Normal position: analyze with engine
            post = analyze_or_fail(post_fen, depth, 1, persistent_engine)
            post_score = post[0]["score"]

        side_after = "w" if board_after.turn == chess.WHITE else "b"
        eval_after_cp = eval_for_white(post_score, side_after)

        logger.info(
            f"[EVAL] pre={eval_before_cp:+} post={eval_after_cp:+} "
            f"(Δ {eval_after_cp - eval_before_cp:+})"
        )

        # --- CPL calculation ---
        if played_eval_from_pre is None:
            played_eval_from_pre = eval_after_cp

        cpl = (
            abs(best_eval_from_pre - played_eval_from_pre)
            if best_eval_from_pre is not None
            else None
        )

        if top_gap is None:
            top_gap = cpl

        eval_change = eval_after_cp - eval_before_cp

        # --- Basic label (Best / Good / Inaccuracy / Mistake / Blunder) ---
        basic_label = classify_basic_move(
            eval_before_white=eval_before_cp,
            eval_after_white=eval_after_cp,
            cpl=cpl,
            mover_color=side_before,
            multipv_rank=multipv_rank,
        )

        print("Basic label:", basic_label)

        # --- Sacrifice detection ---
        uci_move_obj = chess.Move.from_uci(move)

        # Prepare eval_types dict for sacrifice detection
        eval_types_dict = {
            "before": pre_score.get("type") if pre_score else None,
            "after": post_score.get("type") if post_score else None,
        }

        # is_sacrifice = is_real_sacrifice(
        #     board_before=board_before,
        #     move=uci_move_obj,
        #     # eval_before=eval_before_cp,
        #     # eval_after=eval_after_cp,
        #     # eval_types=eval_types_dict
        # )
        is_sacrifice = is_real_sacrifice(
            board_before=board_before,
            move=uci_move_obj,
            eval_before_white=eval_before_cp,
            eval_after_white=eval_after_cp,
            mover_color=side_before,
            eval_types=eval_types_dict,
        )


        print("SAC DEBUG:", {
            "is_sacrifice": is_sacrifice,
            "eval_before": eval_before_cp,
            "eval_after": eval_after_cp,
        })


        # --- Mate metadata ---
        best_mate_in = mate_ply(pre_score)
        played_mate_in = mate_ply(post_score)

        pre_is_mate = pre_score.get("type") == "mate"
        post_is_mate = post_score.get("type") == "mate"

        mate_flip = bool(pre_is_mate and post_is_mate and (eval_before_cp * eval_after_cp < 0))
        mate_flip_severity = 0
        if mate_flip:
            mate_flip_severity = 6400 + 100 * ((best_mate_in or 0) + (played_mate_in or 0))

        # --- General Miss detection ---
        is_miss = detect_miss(
            eval_before_white=eval_before_cp,
            eval_after_white=eval_after_cp,
            eval_best_white=best_eval_from_pre,
            mover_color=side_before,
            best_mate_in_plies=best_mate_in,
            played_mate_in_plies=played_mate_in,
        )

        print("Miss detected:", is_miss)

        # --- Book detection (custom opening DB + heuristics) ---
        in_opening_db = is_book_move(fen_before, move)  # move is UCI string
        is_book = detect_book_move(
            fullmove_number=fullmove_number,
            eval_before_white=eval_before_cp,
            eval_after_white=eval_after_cp,
            cpl=cpl,
            multipv_rank=multipv_rank,
            in_opening_db=in_opening_db,
        )

        print("is_book: ", is_book)
        print("in_opening_db:", in_opening_db)

        # --- Brilliant (!!) / Great (!) / mate-flip Blunder ---
        exclam_label, brill_info = classify_exclam_move(
            eval_before_white=eval_before_cp,
            eval_after_white=eval_after_cp,
            eval_best_white=best_eval_from_pre,
            mover_color=side_before,
            is_sacrifice=is_sacrifice,
            is_book=is_book,
            multipv_rank=multipv_rank,
            played_eval_from_pre_white=played_eval_from_pre,
            best_mate_in_plies_pre=best_mate_in,
            played_mate_in_plies_post=played_mate_in,
            mate_flip=mate_flip,
        )

        # --- Final label priority: Book > exclam (Brilliant/Great/mate-flip Blunder) > Miss > basic ---
        if in_opening_db:
            label = "Book"
        elif exclam_label == "Blunder":
            label = "Blunder"   # mate-flip catastrophe
        elif exclam_label in ("Brilliant", "Great"):
            label = exclam_label
        elif is_miss:
            label = "Miss"
        else:
            label = basic_label

        print("Label: ",label)
        return jsonify({
            "fen_before": fen_before,
            "eval_before": eval_before_cp,
            "eval_after": eval_after_cp,
            "eval_change": eval_change,
            "multipv_rank": multipv_rank,
            "top_gap": top_gap,
            "cpl": cpl,
            "eval_before_struct": pre_score,
            "eval_after_struct": post_score,
            "is_sacrifice": is_sacrifice,
            "best_mate_in": best_mate_in,
            "played_mate_in": played_mate_in,
            "mate_flip": mate_flip,
            "mate_flip_severity": mate_flip_severity,
            "basic_label": basic_label,
            "miss_detected": is_miss,
            "is_book": is_book,
            "exclam_label": exclam_label,
            "brilliancy_info": brill_info.__dict__ if brill_info else None,
            "label": label,
        })
    
    except Exception as e:
        logger.error(f"Error in /evaluate: {str(e)}", exc_info=True)
        return jsonify({
            "error": "ENGINE_ANALYSIS_FAILED",
            "message": str(e),
        }), 500


# ----------------------------
# Entrypoint
# ----------------------------
if __name__ == "__main__":
    app.run(debug=True)
