# import sys
# import os

# # Add parent directory to path to allow imports
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# from flask import Flask, request, jsonify
# from flask_cors import CORS
# import chess
# import logging

# from utils.chess_helpers import analyze_fen_multipv, analyze_fen_multipv_persistent, cp_from_score, start_engine, to_root_cp
# from teacher.label_rules import label_move

# app = Flask(__name__)
# CORS(app)

# # Global persistent engine
# persistent_engine = None
# engine_lock = False

# # Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # Piece values for sacrifice detection
# # PIECE_VALUES = {
# #     chess.PAWN: 100,
# #     chess.KNIGHT: 300,
# #     chess.BISHOP: 300,
# #     chess.ROOK: 500,
# #     chess.QUEEN: 900,
# #     chess.KING: 0
# # }

# def material_value(piece_type):
#     return PIECE_VALUES.get(piece_type, 0)



# PIECE_VALUES = {
#     chess.PAWN: 100,
#     chess.KNIGHT: 300,
#     chess.BISHOP: 300,
#     chess.ROOK: 500,
#     chess.QUEEN: 900,
#     chess.KING: 0
# }

# MIN_SAC_CP = 100  # ≥ a pawn offered
# SEE_PENALTY_CP = 0  # mark as sac if SEE < 0 on target square

# def piece_cp(board: chess.Board, sq: chess.Square) -> int:
#     p = board.piece_at(sq)
#     return PIECE_VALUES.get(p.piece_type, 0) if p else 0

# def naive_see(board: chess.Board, square: chess.Square, side_to_move: bool) -> int:
#     """
#     Very small static-exchange eval on `square`.
#     Returns net cp for `side_to_move` assuming optimal local swaps starting on `square`.
#     NOTE: This is a simplified SEE; good enough to detect obvious losing exchanges.
#     """
#     # Collect attacker lists for both sides
#     # We iteratively simulate captures by the least valuable attacker each side.
#     def attackers(side):
#         return sorted(
#             (sq for sq in board.attackers(side, square)),
#             key=lambda s: PIECE_VALUES[board.piece_at(s).piece_type]
#         )

#     gain = []
#     occupied = set()  # squares whose pieces have been virtually removed
#     color = side_to_move
#     target_value = piece_cp(board, square)

#     if target_value == 0:
#         # Consider capturing empty square (quiet move): SEE starts at 0
#         target_value = 0

#     while True:
#         atk = [s for s in attackers(color) if s not in occupied]
#         if not atk:
#             break
#         # least valuable attacker captures
#         from_sq = atk[0]
#         gain.append(target_value)
#         # captured piece becomes the next target value
#         target_value = PIECE_VALUES[board.piece_at(from_sq).piece_type]
#         occupied.add(from_sq)
#         # switch side
#         color = not color

#     # Backward induction of gains/losses (classic SEE accumulation)
#     for i in range(len(gain)-2, -1, -1):
#         gain[i] = -max(-gain[i], gain[i+1])
#     return gain[0] if gain else 0


# def is_real_sacrifice(board_before: chess.Board, move: chess.Move,
#                       eval_before=None, eval_after=None, eval_types=None) -> bool:
#     board = board_before.copy()
#     mover = board.turn
#     from_sq, to_sq = move.from_square, move.to_square
#     moved_piece = board.piece_at(from_sq)
#     if moved_piece is None:
#         return False

#     moved_cp    = PIECE_VALUES[moved_piece.piece_type]
#     captured_cp = piece_cp(board, to_sq)

#     gives_check = board.gives_check(move)

#     # EP must be checked on the PRE-move board
#     if board_before.is_en_passant(move):
#         captured_cp = PIECE_VALUES[chess.PAWN]

#     # SEE from the PRE-move board on the destination square
#     see_net_for_mover = naive_see(board_before, to_sq, mover)

#     # Now push (after SEE calc)
#     board.push(move)

#     net_loss_cp = moved_cp - captured_cp
#     opp_can_capture_back = board.is_attacked_by(not mover, to_sq)

#     # Gate A: immediate debit + opponent can accept + losing swap for mover
#     if net_loss_cp >= MIN_SAC_CP and opp_can_capture_back and see_net_for_mover < 0:
#         return True

#     # Gate B: destination is a losing capture sequence for mover
#     if see_net_for_mover < 0:
#         return True

#     # Gate C: forcing sac (check/mate), but still require acceptability
#     mate_before = (eval_types and eval_types.get("before") == "mate")
#     mate_after  = (eval_types and eval_types.get("after")  == "mate")
#     if (gives_check or mate_after or mate_before) and (
#         see_net_for_mover < 0 or (opp_can_capture_back and net_loss_cp >= MIN_SAC_CP)
#     ):
#         return True

#     return False



# def played_rank_and_gap(uci_move, pvs, root_turn):
#     """
#     Find the rank of a UCI move in the multipv results and calculate top gap.

#     Args:
#         uci_move: UCI move string (e.g., "e2e4", "e7e8q")
#         pvs: List of PV dicts from engine with 'multipv', 'score', 'pv' keys
#         root_turn: bool - True if position is White's turn

#     Returns:
#         tuple: (rank, top_gap)
#             - rank: int - 1 to K if found, K+1 if not found (where K = len(pvs))
#             - top_gap: float or None - gap to best move in CP, None if move not found
#     """
#     if not pvs:
#         return (1, None)

#     # Normalize the input move to lowercase, remove '=' from promotions
#     uci_move_normalized = uci_move.lower().strip().replace('=', '')

#     K = len(pvs)  # MultiPV count
#     logger.debug(f"Searching for move: '{uci_move_normalized}' in {K} PVs")

#     # Get best move score for gap calculation (always PV#1)
#     best_score_cp = to_root_cp(pvs[0]["score"], root_turn, root_turn)

#     for pv_entry in pvs:
#         pv = pv_entry.get("pv", [])
#         if not pv:
#             continue

#         pv_move = pv[0].lower().strip().replace('=', '')

#         # Promotion-safe matching
#         # Match if:
#         # 1. Exact match (e7e8q == e7e8q)
#         # 2. Base matches and both are length 5 with same promotion piece (e7e8q == e7e8q)
#         # 3. Base matches and one is length 4, other is 5 (e7e8 matches e7e8q - assume queen)

#         is_match = False

#         if pv_move == uci_move_normalized:
#             # Exact match
#             is_match = True
#             logger.debug(f"  Exact match: '{uci_move_normalized}' = PV#{pv_entry['multipv']}")
#         elif len(pv_move) >= 4 and len(uci_move_normalized) >= 4:
#             # Check if base move matches (first 4 chars)
#             if pv_move[:4] == uci_move_normalized[:4]:
#                 # Both are same length
#                 if len(pv_move) == len(uci_move_normalized):
#                     if len(pv_move) == 4:
#                         # Both regular moves
#                         is_match = True
#                     elif len(pv_move) == 5 and pv_move[4] == uci_move_normalized[4]:
#                         # Both promotions with same piece
#                         is_match = True
#                 else:
#                     # Different lengths - one is promotion, one isn't
#                     # Accept as match (assume missing promotion = queen)
#                     is_match = True

#                 if is_match:
#                     logger.debug(f"  Base match: '{uci_move_normalized}' = PV#{pv_entry['multipv']}")

#         if is_match:
#             rank = pv_entry["multipv"]
#             # Calculate gap using consistent normalization
#             played_score_cp = to_root_cp(pv_entry["score"], root_turn, root_turn)
#             top_gap = abs(best_score_cp - played_score_cp)

#             logger.info(f"Move '{uci_move_normalized}' found at rank {rank}, gap={top_gap:.1f}cp")
#             return (rank, top_gap)

#     # Move not found in any PV
#     logger.warning(f"Move '{uci_move_normalized}' not found in any PV. Available moves: {[pv.get('pv', [[]])[0] if pv.get('pv') else 'none' for pv in pvs]}")
#     return (K + 1, None)

# @app.route('/start_engine', methods=['POST'])
# def start_engine_endpoint():
#     global persistent_engine, engine_lock
#     try:
#         if persistent_engine is not None:
#             return jsonify({"status": "already_running", "message": "Engine is already running"})

#         logger.info("Starting persistent Stockfish engine...")
#         # Recommended settings for calibration: 512MB hash, 2-4 threads
#         hash_mb = 512
#         threads = 2
#         # MultiPV will be set per-search in analyze_fen_multipv_persistent
#         persistent_engine = start_engine({"Hash": hash_mb, "Threads": threads})
#         logger.info(f"Stockfish engine started successfully (Hash={hash_mb}MB, Threads={threads})")
#         return jsonify({"status": "started", "message": "Engine started successfully"})
#     except Exception as e:
#         logger.error(f"Failed to start engine: {str(e)}")
#         return jsonify({"status": "error", "message": str(e)}), 500

# @app.route('/stop_engine', methods=['POST'])
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
#         logger.info("Stockfish engine stopped successfully")
#         return jsonify({"status": "stopped", "message": "Engine stopped successfully"})
#     except Exception as e:
#         logger.error(f"Failed to stop engine: {str(e)}")
#         return jsonify({"status": "error", "message": str(e)}), 500

# @app.route('/evaluate', methods=['POST'])
# def evaluate_move():
#     global persistent_engine
#     data = request.json
#     fen = data.get("fen")
#     move = data.get("move")
#     depth = int(data.get("depth", 18))
#     multipv = int(data.get("multipv", 5))

#     logger.info(f"Evaluating move: {move} for FEN: {fen[:50]}...")

#     try:
#         board = chess.Board(fen)
#         root_turn = board.turn  # True if White's turn, False if Black's

#         # Store FEN before move for logging
#         fen_before = fen

#         # Use persistent engine if available, otherwise create temporary one
#         if persistent_engine is not None:
#             logger.info("Using persistent engine")
#             pre = analyze_fen_multipv_persistent(fen, persistent_engine, depth=depth, multipv=multipv)
#         else:
#             logger.info("Creating temporary engine (persistent engine not started)")
#             pre = analyze_fen_multipv(fen, depth=depth, multipv=multipv)

#         logger.debug(f"Engine returned {len(pre)} PV lines: {[d.get('pv', [[]])[0] if d.get('pv') else 'none' for d in pre]}")

#         # Get rank and top_gap using new function
#         multipv_rank, top_gap = played_rank_and_gap(move, pre, root_turn)

#         # Normalize eval_before using to_root_cp (BEFORE position, same side)
#         eval_before_cp = to_root_cp(pre[0]["score"], root_turn, root_turn)

#         # Push move and analyze post
#         board.push_uci(move)
#         post_fen = board.fen()
#         node_turn_after = board.turn  # Turn after the move

#         if persistent_engine is not None:
#             post = analyze_fen_multipv_persistent(post_fen, persistent_engine, depth=depth, multipv=1)
#         else:
#             post = analyze_fen_multipv(post_fen, depth=depth, multipv=1)

#         # Normalize eval_after using to_root_cp (AFTER position, opponent's perspective)
#         eval_after_cp = to_root_cp(post[0]["score"], root_turn, node_turn_after)

#         # Calculate eval_change (no manual sign flips)
#         eval_change = eval_after_cp - eval_before_cp

#         logger.info(f"Evaluation change: {eval_before_cp:+.1f} → {eval_after_cp:+.1f} (Δ {eval_change:+.1f}cp) from root's perspective")
#         logger.info(f"Rank: {multipv_rank}, Top gap: {top_gap if top_gap is not None else 'N/A'}")

#         # Check for real sacrifice
#         original_board = chess.Board(fen)
#         uci_move = chess.Move.from_uci(move)
#         is_sacrifice = is_real_sacrifice(original_board, uci_move)

#         is_book = False  # Replace with logic if needed

#         # For label_move, pass the new values (may need to update label_move signature if needed)
#         # Use top_gap if available, otherwise 0 for backward compatibility
#         gap_for_label = top_gap if top_gap is not None else 0
#         label = label_move(fen, move, eval_before_cp, eval_after_cp, multipv_rank, is_sacrifice, is_book, gap_for_label)

#         return jsonify({
#             "fen_before": fen_before,
#             "eval_before": eval_before_cp,
#             "eval_after": eval_after_cp,
#             "eval_change": eval_change,
#             "multipv_rank": multipv_rank,
#             "top_gap": top_gap,  # Can be None
#             "eval_before_struct": pre[0]["score"],
#             "eval_after_struct": post[0]["score"],
#             "is_sacrifice": is_sacrifice,
#             "label": label
#         })

#     except Exception as e:
#         logger.error(f"Error in /evaluate: {str(e)}", exc_info=True)
#         return jsonify({"error": str(e)}), 500

# if __name__ == "__main__":
#     app.run(debug=True)




import sys
import os

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
from flask_cors import CORS
import chess
import logging

from utils.chess_helpers import (
    analyze_fen_multipv,
    analyze_fen_multipv_persistent,
    cp_from_score,
    start_engine,
    to_root_cp,
)
from teacher.label_rules import label_move

app = Flask(__name__)
CORS(app)

# ----------------------------
# Logging
# ----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------
# Global persistent engine
# ----------------------------
persistent_engine = None
engine_lock = False

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

def piece_cp(board: chess.Board, sq: chess.Square) -> int:
    p = board.piece_at(sq)
    return PIECE_VALUES.get(p.piece_type, 0) if p else 0

# Minimal SEE for “can they accept profitably?”
def naive_see(board: chess.Board, square: chess.Square, side_to_move: bool) -> int:
    """
    Very small static-exchange eval on `square`.
    Returns net cp for `side_to_move` assuming optimal local swaps starting on `square`.
    """
    def attackers(side):
        return sorted(
            (sq for sq in board.attackers(side, square)),
            key=lambda s: PIECE_VALUES[board.piece_at(s).piece_type]
        )

    gain = []
    occupied = set()
    color = side_to_move
    target_value = piece_cp(board, square)  # 0 if quiet

    while True:
        atk = [s for s in attackers(color) if s not in occupied]
        if not atk:
            break
        from_sq = atk[0]  # least valuable attacker
        gain.append(target_value)
        target_value = PIECE_VALUES[board.piece_at(from_sq).piece_type]
        occupied.add(from_sq)
        color = not color

    for i in range(len(gain) - 2, -1, -1):
        gain[i] = -max(-gain[i], gain[i + 1])
    return gain[0] if gain else 0

# ----------------------------
# Sacrifice detection (tightened)
# ----------------------------
MIN_SAC_CP = 100     # at least a pawn offered
SEE_PENALTY_CP = 0   # treat SEE < 0 as losing for mover

def is_real_sacrifice(board_before: chess.Board, move: chess.Move,
                      eval_before=None, eval_after=None, eval_types=None) -> bool:
    """
    A move is a sacrifice if the opponent can accept with a profitable sequence
    (SEE < 0 for the mover), or if the move offers a real material debit that
    can be accepted, or a forcing (check/mate) sac with a debit AND acceptability.
    """
    board = board_before.copy()
    mover = board.turn
    from_sq, to_sq = move.from_square, move.to_square
    moved_piece = board.piece_at(from_sq)
    if moved_piece is None:
        return False

    moved_cp    = PIECE_VALUES[moved_piece.piece_type]
    captured_cp = piece_cp(board, to_sq)

    # Check en passant on PRE-move board
    if board_before.is_en_passant(move):
        captured_cp = PIECE_VALUES[chess.PAWN]

    # SEE computed on PRE-move board – destination square
    see_net_for_mover = naive_see(board_before, to_sq, mover)

    gives_check = board.gives_check(move)

    # Push AFTER SEE calc
    board.push(move)

    net_loss_cp = moved_cp - captured_cp
    opp_can_capture_back = board.is_attacked_by(not mover, to_sq)

    # Gate A: debit + opponent can accept + losing sequence for mover
    if net_loss_cp >= MIN_SAC_CP and opp_can_capture_back and see_net_for_mover < 0:
        return True

    # Gate B: destination is losing via SEE alone (under-defended offer)
    if see_net_for_mover < 0:
        return True

    # Gate C: forcing sac (check/mate) still requires acceptability
    mate_before = (eval_types and eval_types.get("before") == "mate")
    mate_after  = (eval_types and eval_types.get("after")  == "mate")
    if (gives_check or mate_after or mate_before) and (
        see_net_for_mover < 0 or (opp_can_capture_back and net_loss_cp >= MIN_SAC_CP)
    ):
        return True

    return False

# ----------------------------
# MultiPV helper
# ----------------------------
def played_rank_and_gap(uci_move, pvs, root_turn):
    """
    Return (rank, top_gap_cp, played_eval_cp, best_eval_cp)

    - rank: 1..K if found, K+1 if not found
    - top_gap_cp: |best_eval - played_eval| (None if not found)
    - played_eval_cp: eval of played move from PRE position (None if not found)
    - best_eval_cp: eval of PV#1 from PRE position
    """
    if not pvs:
        return (1, None, None, None)

    uci_move_normalized = uci_move.lower().strip().replace('=', '')
    K = len(pvs)

    # Best eval (PV#1) normalized to root side
    best_eval_cp = to_root_cp(pvs[0]["score"], root_turn, root_turn)

    for pv_entry in pvs:
        pv = pv_entry.get("pv", [])
        if not pv:
            continue

        pv_move = pv[0].lower().strip().replace('=', '')

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
            played_eval_cp = to_root_cp(pv_entry["score"], root_turn, root_turn)
            top_gap = abs(best_eval_cp - played_eval_cp)
            logger.info(f"Move '{uci_move_normalized}' found at rank {rank}, gap={top_gap:.1f}cp")
            return (rank, top_gap, played_eval_cp, best_eval_cp)

    logger.warning(
        f"Move '{uci_move_normalized}' not found in any PV. "
        f"Available first moves: {[pv.get('pv', [''])[0] if pv.get('pv') else '' for pv in pvs]}"
    )
    return (K + 1, None, None, best_eval_cp)

# ----------------------------
# Engine control endpoints
# ----------------------------
@app.route('/start_engine', methods=['POST'])
def start_engine_endpoint():
    global persistent_engine, engine_lock
    try:
        if persistent_engine is not None:
            return jsonify({"status": "already_running", "message": "Engine is already running"})
        logger.info("Starting persistent Stockfish engine...")
        hash_mb = 512
        threads = 2
        persistent_engine = start_engine({"Hash": hash_mb, "Threads": threads})
        logger.info(f"Stockfish engine started (Hash={hash_mb}MB, Threads={threads})")
        return jsonify({"status": "started", "message": "Engine started successfully"})
    except Exception as e:
        logger.error(f"Failed to start engine: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stop_engine', methods=['POST'])
def stop_engine_endpoint():
    global persistent_engine, engine_lock
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
# Evaluation endpoint
# ----------------------------
# @app.route('/evaluate', methods=['POST'])
# def evaluate_move():
#     global persistent_engine
#     data = request.json
#     fen = data.get("fen")
#     move = data.get("move")
#     depth = int(data.get("depth", 18))
#     multipv = int(data.get("multipv", 5))

#     logger.info(f"Evaluating move: {move} for FEN: {fen[:60]}...")

#     try:
#         board = chess.Board(fen)
#         root_turn = board.turn  # True if White to move

#         fen_before = fen

#         # Analyze PRE position
#         if persistent_engine is not None:
#             pre = analyze_fen_multipv_persistent(fen, persistent_engine, depth=depth, multipv=multipv)
#         else:
#             pre = analyze_fen_multipv(fen, depth=depth, multipv=multipv)

#         # Rank/gap + evals from PRE
#         multipv_rank, top_gap, played_eval_from_pre, best_eval_from_pre = played_rank_and_gap(
#             move, pre, root_turn
#         )

#         # Eval before (best line from PRE), normalized
#         eval_before_cp = to_root_cp(pre[0]["score"], root_turn, root_turn)

#         # Analyze POST position (after the move)
#         board.push_uci(move)
#         post_fen = board.fen()
#         node_turn_after = board.turn

#         if persistent_engine is not None:
#             post = analyze_fen_multipv_persistent(post_fen, persistent_engine, depth=depth, multipv=1)
#         else:
#             post = analyze_fen_multipv(post_fen, depth=depth, multipv=1)

#         # Eval after, normalized to root perspective (account for turn switch)
#         eval_after_cp = to_root_cp(post[0]["score"], root_turn, node_turn_after)

#         # Delta from root perspective
#         eval_change = eval_after_cp - eval_before_cp

#         # CPL = |best_eval(pre) - played_eval(pre)|
#         # If move not present in MultiPV, fall back to eval_after_cp as proxy
#         if played_eval_from_pre is None:
#             played_eval_from_pre = eval_after_cp
#         cpl = abs(best_eval_from_pre - played_eval_from_pre) if best_eval_from_pre is not None else None

#         # If top_gap missing (move not in PV), set it to CPL so UI always has a value
#         if top_gap is None:
#             top_gap = cpl

#         logger.info(
#             f"Eval change {eval_before_cp:+.1f} → {eval_after_cp:+.1f} (Δ {eval_change:+.1f}); "
#             f"rank={multipv_rank}, top_gap={top_gap if top_gap is not None else 'N/A'} cp, CPL={cpl}"
#         )

#         # Sacrifice check (tight gates)
#         original_board = chess.Board(fen)
#         uci_move = chess.Move.from_uci(move)
#         is_sacrifice = is_real_sacrifice(original_board, uci_move)

#         is_book = False  # replace with real book lookup if you add it

#         # Label using your rule-set; pass top_gap (gap vs best) to labeler
#         gap_for_label = top_gap if top_gap is not None else 0
#         label = label_move(
#             fen, move, eval_before_cp, eval_after_cp, multipv_rank,
#             is_sacrifice, is_book, gap_for_label
#         )

#         return jsonify({
#             "fen_before": fen_before,
#             "eval_before": eval_before_cp,
#             "eval_after": eval_after_cp,
#             "eval_change": eval_change,
#             "multipv_rank": multipv_rank,
#             "top_gap": top_gap,           # gap vs best (pre), equals CPL when found
#             "cpl": cpl,                   # chess.com-style centipawn loss
#             "eval_before_struct": pre[0]["score"],
#             "eval_after_struct": post[0]["score"],
#             "is_sacrifice": is_sacrifice,
#             "label": label
#         })

#     except Exception as e:
#         logger.error(f"Error in /evaluate: {str(e)}", exc_info=True)
#         return jsonify({"error": str(e)}), 500



@app.route('/evaluate', methods=['POST'])
def evaluate_move():
    # --- helper for mate distance (plies) ---
    def mate_ply(score_dict):
        """Return mate-in-N (plies) as nonnegative int, or None if not mate."""
        if not score_dict:
            return None
        if score_dict.get("type") == "mate":
            try:
                return abs(int(score_dict.get("value", 0)))
            except Exception:
                return None
        return None

    # --- tunables for "Miss" ---
    MISS_STILL_WINNING_CP = 300   # after the move you're still clearly winning
    MISS_TOLERANCE_PLIES  = 1     # allow equal / +1 ply; larger = missed
    MISS_MIN_GAP_CP       = 300   # require a meaningful gap to best

    global persistent_engine
    data = request.json
    fen = data.get("fen")
    move = data.get("move")
    depth = int(data.get("depth", 18))
    multipv = int(data.get("multipv", 5))

    logger.info(f"Evaluating move: {move} for FEN: {fen[:60]}...")

    try:
        board = chess.Board(fen)
        root_turn = board.turn  # True if White to move
        fen_before = fen

        # --- analyze PRE position ---
        if persistent_engine is not None:
            pre = analyze_fen_multipv_persistent(fen, persistent_engine, depth=depth, multipv=multipv)
        else:
            pre = analyze_fen_multipv(fen, depth=depth, multipv=multipv)

        # rank/gap + evals from PRE
        multipv_rank, top_gap, played_eval_from_pre, best_eval_from_pre = played_rank_and_gap(
            move, pre, root_turn
        )

        # eval before (best line from PRE), normalized
        eval_before_cp = to_root_cp(pre[0]["score"], root_turn, root_turn)

        # --- analyze POST position (after the move) ---
        board.push_uci(move)
        post_fen = board.fen()
        node_turn_after = board.turn

        if persistent_engine is not None:
            post = analyze_fen_multipv_persistent(post_fen, persistent_engine, depth=depth, multipv=1)
        else:
            post = analyze_fen_multipv(post_fen, depth=depth, multipv=1)

        # eval after, normalized to root perspective (account for turn switch)
        eval_after_cp = to_root_cp(post[0]["score"], root_turn, node_turn_after)

        # delta from root perspective
        eval_change = eval_after_cp - eval_before_cp

        # CPL = |best_eval(pre) - played_eval(pre)|  (fallback to eval_after if move not in PV)
        if played_eval_from_pre is None:
            played_eval_from_pre = eval_after_cp
        cpl = abs(best_eval_from_pre - played_eval_from_pre) if best_eval_from_pre is not None else None

        # if top_gap missing (move not in PV), use CPL so UI always has a value
        if top_gap is None:
            top_gap = cpl

        logger.info(
            f"Eval change {eval_before_cp:+.1f} → {eval_after_cp:+.1f} (Δ {eval_change:+.1f}); "
            f"rank={multipv_rank}, top_gap={top_gap if top_gap is not None else 'N/A'} cp, CPL={cpl}"
        )

        # --- sacrifice check ---
        original_board = chess.Board(fen)
        uci_move = chess.Move.from_uci(move)
        is_sacrifice = is_real_sacrifice(original_board, uci_move)

        # --- mate metadata (pre/post) ---
        pre_score   = pre[0]["score"]
        post_score  = post[0]["score"]
        best_mate_in   = mate_ply(pre_score)      # mate-in-N in best line BEFORE
        played_mate_in = mate_ply(post_score)     # mate-in-N AFTER played move

        pre_is_mate  = (pre_score.get("type")  == "mate")
        post_is_mate = (post_score.get("type") == "mate")

        # Mate ownership flip (winning mate → losing mate or vice versa)
        mate_flip = bool(pre_is_mate and post_is_mate and (eval_before_cp * eval_after_cp < 0))
        mate_flip_severity = 0
        if mate_flip:
            # heavy severity so it always overrides CPL-based labels
            mate_flip_severity = 6400 + 100 * ((best_mate_in or 0) + (played_mate_in or 0))

        # --- missed mate detection (pre-best vs post) ---
        still_winning = eval_after_cp is not None and (eval_after_cp >= MISS_STILL_WINNING_CP)
        forgone = False
        if best_mate_in is not None:
            # missed if mate disappears OR gets slower by more than tolerance
            forgone = (played_mate_in is None) or (played_mate_in > best_mate_in + MISS_TOLERANCE_PLIES)

        big_gap = (top_gap is not None and (top_gap >= MISS_MIN_GAP_CP))
        miss_mate = bool(best_mate_in is not None and forgone and still_winning and big_gap)

        # a simple severity score for miss (handy for calibration/UX)
        mate_miss_severity = 0.0
        if miss_mate:
            mate_miss_severity = float(top_gap or 0) + 200.0 * float((played_mate_in or 99) - best_mate_in)

        # --- label (apply mate-flip > miss > normal rules) ---
        # is_book = False
        # gap_for_label = top_gap if top_gap is not None else 0

        # if mate_flip:
        #     label = "Blunder"
        # elif miss_mate:
        #     label = "Miss"
        # else:
        #     label = label_move(
        #         fen, move, eval_before_cp, eval_after_cp, multipv_rank,
        #         is_sacrifice, is_book, gap_for_label
        #     )
        # --- label (apply mate-flip > miss > normal rules) ---
        is_book = False
        gap_for_label = top_gap if top_gap is not None else 0

        if mate_flip:
            # Check direction of flip
            if eval_before_cp > 0 and eval_after_cp < 0:
                label = "Blunder"   # lost winning mate
            elif eval_before_cp < 0 and eval_after_cp > 0:
                label = "Brilliant" # saved from mate or turned it around
            else:
                label = label_move(
                    fen, move, eval_before_cp, eval_after_cp, multipv_rank,
                    is_sacrifice, is_book, gap_for_label
                )
        elif miss_mate:
            label = "Miss"
        else:
            label = label_move(
                fen, move, eval_before_cp, eval_after_cp, multipv_rank,
                is_sacrifice, is_book, gap_for_label
            )


        return jsonify({
            "fen_before": fen_before,
            "eval_before": eval_before_cp,
            "eval_after":  eval_after_cp,
            "eval_change": eval_change,
            "multipv_rank": multipv_rank,
            "top_gap": top_gap,             # gap vs best (pre); equals CPL when move found
            "cpl": cpl,                     # chess.com-style centipawn loss
            "eval_before_struct": pre_score,
            "eval_after_struct":  post_score,
            "is_sacrifice": is_sacrifice,

            # mate-related outputs
            "best_mate_in": best_mate_in,
            "played_mate_in": played_mate_in,
            "miss_mate": miss_mate,
            "mate_miss_severity": mate_miss_severity,
            "mate_flip": mate_flip,
            "mate_flip_severity": mate_flip_severity,

            "label": label
        })

    except Exception as e:
        logger.error(f"Error in /evaluate: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500



#---------working

# @app.route('/evaluate', methods=['POST'])
# def evaluate_move():
#     # --- helper for mate distance (plies) ---
#     def mate_ply(score_dict):
#         """Return mate-in-N (plies) as nonnegative int, or None if not mate."""
#         if not score_dict:
#             return None
#         if score_dict.get("type") == "mate":
#             try:
#                 return abs(int(score_dict.get("value", 0)))
#             except Exception:
#                 return None
#         return None

#     # --- tunables for "Miss" ---
#     MISS_STILL_WINNING_CP = 300   # after the move you're still clearly winning
#     MISS_TOLERANCE_PLIES  = 1     # allow equal / +1 ply; larger = missed
#     MISS_MIN_GAP_CP       = 300   # require a meaningful gap to best

#     global persistent_engine
#     data = request.json
#     fen = data.get("fen")
#     move = data.get("move")
#     depth = int(data.get("depth", 18))
#     multipv = int(data.get("multipv", 5))

#     logger.info(f"Evaluating move: {move} for FEN: {fen[:60]}...")

#     try:
#         board = chess.Board(fen)
#         root_turn = board.turn  # True if White to move
#         fen_before = fen

#         # --- analyze PRE position ---
#         if persistent_engine is not None:
#             pre = analyze_fen_multipv_persistent(fen, persistent_engine, depth=depth, multipv=multipv)
#         else:
#             pre = analyze_fen_multipv(fen, depth=depth, multipv=multipv)

#         # rank/gap + evals from PRE
#         multipv_rank, top_gap, played_eval_from_pre, best_eval_from_pre = played_rank_and_gap(
#             move, pre, root_turn
#         )

#         # eval before (best line from PRE), normalized
#         eval_before_cp = to_root_cp(pre[0]["score"], root_turn, root_turn)

#         # --- analyze POST position (after the move) ---
#         board.push_uci(move)
#         post_fen = board.fen()
#         node_turn_after = board.turn

#         if persistent_engine is not None:
#             post = analyze_fen_multipv_persistent(post_fen, persistent_engine, depth=depth, multipv=1)
#         else:
#             post = analyze_fen_multipv(post_fen, depth=depth, multipv=1)

#         # eval after, normalized to root perspective (account for turn switch)
#         eval_after_cp = to_root_cp(post[0]["score"], root_turn, node_turn_after)

#         # delta from root perspective
#         eval_change = eval_after_cp - eval_before_cp

#         # CPL = |best_eval(pre) - played_eval(pre)|  (fallback to eval_after if move not in PV)
#         if played_eval_from_pre is None:
#             played_eval_from_pre = eval_after_cp
#         cpl = abs(best_eval_from_pre - played_eval_from_pre) if best_eval_from_pre is not None else None

#         # if top_gap missing (move not in PV), use CPL so UI always has a value
#         if top_gap is None:
#             top_gap = cpl

#         logger.info(
#             f"Eval change {eval_before_cp:+.1f} → {eval_after_cp:+.1f} (Δ {eval_change:+.1f}); "
#             f"rank={multipv_rank}, top_gap={top_gap if top_gap is not None else 'N/A'} cp, CPL={cpl}"
#         )

#         # --- sacrifice check ---
#         original_board = chess.Board(fen)
#         uci_move = chess.Move.from_uci(move)
#         is_sacrifice = is_real_sacrifice(original_board, uci_move)

#         # --- missed mate detection (pre-best vs post) ---
#         best_mate_in   = mate_ply(pre[0]["score"])     # mate-in-N in best line before move
#         played_mate_in = mate_ply(post[0]["score"])    # mate-in-N after the played move

#         still_winning = eval_after_cp is not None and (eval_after_cp >= MISS_STILL_WINNING_CP)
#         forgone = False
#         if best_mate_in is not None:
#             # missed if mate disappears OR gets slower by more than tolerance
#             forgone = (played_mate_in is None) or (played_mate_in > best_mate_in + MISS_TOLERANCE_PLIES)

#         big_gap = (top_gap is not None and (top_gap >= MISS_MIN_GAP_CP))
#         miss_mate = bool(best_mate_in is not None and forgone and still_winning and big_gap)

#         # a simple severity score (handy for later calibration/UX)
#         mate_miss_severity = 0.0
#         if miss_mate:
#             mate_miss_severity = float(top_gap or 0) + 200.0 * float((played_mate_in or 99) - best_mate_in)

#         # --- label ---
#         is_book = False  # (hook for opening-book logic if you add it)
#         gap_for_label = top_gap if top_gap is not None else 0

#         # If we missed a forced mate and are still easily winning, force "Miss"
#         if miss_mate:
#             label = "Miss"
#         else:
#             label = label_move(
#                 fen, move, eval_before_cp, eval_after_cp, multipv_rank,
#                 is_sacrifice, is_book, gap_for_label
#             )

#         return jsonify({
#             "fen_before": fen_before,
#             "eval_before": eval_before_cp,
#             "eval_after":  eval_after_cp,
#             "eval_change": eval_change,
#             "multipv_rank": multipv_rank,
#             "top_gap": top_gap,             # gap vs best (pre); equals CPL when move found
#             "cpl": cpl,                     # chess.com-style centipawn loss
#             "eval_before_struct": pre[0]["score"],
#             "eval_after_struct":  post[0]["score"],
#             "is_sacrifice": is_sacrifice,
#             # missed-mate fields
#             "miss_mate": miss_mate,
#             "best_mate_in": best_mate_in,
#             "played_mate_in": played_mate_in,
#             "mate_miss_severity": mate_miss_severity,
#             "label": label
#         })

#     except Exception as e:
#         logger.error(f"Error in /evaluate: {str(e)}", exc_info=True)
#         return jsonify({"error": str(e)}), 500


# ----------------------------
# Entrypoint
# ----------------------------
if __name__ == "__main__":
    app.run(debug=True)
