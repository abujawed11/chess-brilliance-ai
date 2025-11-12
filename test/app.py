import sys
import os

# Get the absolute path to the project root FIRST
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

# Add parent directory to path BEFORE any imports
sys.path.insert(0, project_root)

# Load .env file and set environment variable explicitly
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


# --- RAW White-centric mapping (no normalization) ---
MATE_CP = 32000
MATE_STEP = 1000  # drop per ply

def cp_white_raw(score: dict) -> int:
    """
    Map a Stockfish score dict to centipawns from White's POV ONLY.
    - cp: return value as-is
    - mate: + for White mates, - for Black mates
      cp = (MATE_CP - MATE_STEP * |plies|)
    """
    if not score:
        return 0
    t = score.get("type")
    v = score.get("value", 0)
    if t == "mate":
        try:
            n = max(0, int(abs(v)))  # plies to mate
        except Exception:
            n = 0
        # Handle edge cases: if v==0 (terminal), treat as full MATE_CP
        base = MATE_CP - MATE_STEP * n
        if base < 0:
            base = 0
        return base if v > 0 else -base
    # cp case
    try:
        return int(v)
    except Exception:
        return 0


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
# def played_rank_and_gap(uci_move, pvs, root_turn):
#     """
#     Return (rank, top_gap_cp, played_eval_cp, best_eval_cp)

#     - rank: 1..K if found, K+1 if not found
#     - top_gap_cp: |best_eval - played_eval| (None if not found)
#     - played_eval_cp: eval of played move from PRE position (None if not found)
#     - best_eval_cp: eval of PV#1 from PRE position
#     """
#     if not pvs:
#         return (1, None, None, None)

#     uci_move_normalized = uci_move.lower().strip().replace('=', '')
#     K = len(pvs)

#     # Best eval (PV#1) normalized to root side
#     best_eval_cp = to_root_cp(pvs[0]["score"], root_turn, root_turn)

#     for pv_entry in pvs:
#         pv = pv_entry.get("pv", [])
#         if not pv:
#             continue

#         pv_move = pv[0].lower().strip().replace('=', '')

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
#             played_eval_cp = to_root_cp(pv_entry["score"], root_turn, root_turn)
#             top_gap = abs(best_eval_cp - played_eval_cp)
#             logger.info(f"Move '{uci_move_normalized}' found at rank {rank}, gap={top_gap:.1f}cp")
#             return (rank, top_gap, played_eval_cp, best_eval_cp)

#     logger.warning(
#         f"Move '{uci_move_normalized}' not found in any PV. "
#         f"Available first moves: {[pv.get('pv', [''])[0] if pv.get('pv') else '' for pv in pvs]}"
#     )
#     return (K + 1, None, None, best_eval_cp)


# ----------------------------
# MultiPV helper  (RAW / White-centric)
# ----------------------------
def played_rank_and_gap(uci_move, pvs, _root_turn_ignored):
    """
    Return (rank, top_gap_cp, played_eval_cp, best_eval_cp) using RAW White-centric CP.

    - best_eval_cp: RAW CP of PV#1 from PRE (cp_from_score)
    - played_eval_cp: RAW CP of the played move from PRE (cp_from_score)
    - top_gap_cp: |best_eval_cp - played_eval_cp|
    """
    if not pvs:
        return (1, None, None, None)

    uci_move_normalized = uci_move.lower().strip().replace('=', '')
    K = len(pvs)

    # RAW White-centric best eval
    # best_eval_cp = cp_from_score(pvs[0]["score"])
    # best_eval_cp = cp_from_score(pvs[0]["score"], side_to_move='w')
    best_eval_cp = cp_white_raw(pvs[0]["score"])

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
            # played_eval_cp = cp_from_score(pv_entry["score"])       # RAW (White POV)
            # played_eval_cp = cp_from_score(pv_entry["score"], side_to_move='w')
            played_eval_cp = cp_white_raw(pv_entry["score"])

            top_gap = abs(best_eval_cp - played_eval_cp)            # RAW gap
            logger.info(f"Move '{uci_move_normalized}' found at rank {rank}, RAW gap={top_gap:.1f}cp")
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

        # Debug: log the engine path
        from utils.chess_helpers import ENGINE_PATH
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


# --- small helper: analyze with retries and ensure PVs exist ---
def analyze_or_fail(fen: str, depth: int, multipv: int, engine):
    """Return PV list or raise with a clear message after retries."""
    tries = [
        (depth, multipv),
        (max(8, depth - 4), multipv),  # retry slightly shallower
        (max(6, depth - 6), 1),        # final minimal PV to get *something*
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
    # If we reach here, no PVs
    raise RuntimeError(f"No PVs returned for fen='{fen[:60]}...' (depth tried: {tries}). "
                       f"Engine may have died or timed out. Last error: {last_err}")


@app.route('/evaluate', methods=['POST'])
def evaluate_move():
    def mate_ply(score_dict):
        if not score_dict: return None
        if score_dict.get("type") == "mate":
            try: return abs(int(score_dict.get("value", 0)))
            except Exception: return None
        return None

    MISS_STILL_WINNING_CP = 300
    MISS_TOLERANCE_PLIES  = 1
    MISS_MIN_GAP_CP       = 300

    global persistent_engine
    data = request.json
    fen   = data.get("fen")
    move  = data.get("move")
    depth = int(data.get("depth", 18))
    multipv = int(data.get("multipv", 5))

    logger.info(f"Evaluating move: {move} for FEN: {fen[:60]}...")

    try:
        board = chess.Board(fen)
        fen_before = fen

        # --- PRE (RAW White-centric) with retries ---
        pre = analyze_or_fail(fen_before, depth, multipv, persistent_engine)
        pre_score = pre[0]["score"]
        # eval_before_cp = cp_from_score(pre_score, side_to_move='w')
        eval_before_cp = cp_white_raw(pre_score)

        # rank/gap vs best (RAW)
        multipv_rank, top_gap, played_eval_from_pre, best_eval_from_pre = played_rank_and_gap(
            move, pre, None  # root ignored in RAW path
        )

        # --- POST (after the move) with retries ---
        board.push_uci(move)
        post_fen = board.fen()
        post = analyze_or_fail(post_fen, depth, 1, persistent_engine)
        post_score = post[0]["score"]
        # eval_after_cp = cp_from_score(post_score, side_to_move='w')
        eval_after_cp  = cp_white_raw(post_score)

        print(f"RAW pre={pre_score} post={post_score}  raw_cp pre={eval_before_cp:+} post={eval_after_cp:+}")

        # --- deltas (RAW) ---
        eval_change = eval_after_cp - eval_before_cp

        # CPL = |best_pre_raw - played_pre_raw| ; fallback to POST raw if not found in PRE PVs
        if played_eval_from_pre is None:
            played_eval_from_pre = eval_after_cp
        cpl = abs(best_eval_from_pre - played_eval_from_pre) if best_eval_from_pre is not None else None

        if top_gap is None:
            top_gap = cpl

        logger.info(
            f"[RAW] Eval change {eval_before_cp:+.1f} → {eval_after_cp:+.1f} (Δ {eval_change:+.1f}); "
            f"rank={multipv_rank}, top_gap={top_gap if top_gap is not None else 'N/A'} cp, CPL={cpl}"
        )

        # --- sacrifice check (unchanged) ---
        original_board = chess.Board(fen_before)
        uci_move = chess.Move.from_uci(move)
        is_sacrifice = is_real_sacrifice(original_board, uci_move)

        # --- mate metadata (RAW) ---
        best_mate_in   = mate_ply(pre_score)
        played_mate_in = mate_ply(post_score)

        pre_is_mate  = (pre_score.get("type")  == "mate")
        post_is_mate = (post_score.get("type") == "mate")

        # flip of winner (RAW: sign change means "who mates" flipped)
        mate_flip = bool(pre_is_mate and post_is_mate and (eval_before_cp * eval_after_cp < 0))
        mate_flip_severity = 0
        if mate_flip:
            mate_flip_severity = 6400 + 100 * ((best_mate_in or 0) + (played_mate_in or 0))

        # missed-mate (RAW: still winning for White)
        still_winning = eval_after_cp is not None and eval_after_cp >= MISS_STILL_WINNING_CP
        forgone = False
        if best_mate_in is not None:
            forgone = (played_mate_in is None) or (played_mate_in > best_mate_in + MISS_TOLERANCE_PLIES)
        big_gap = (top_gap is not None and (top_gap >= MISS_MIN_GAP_CP))
        miss_mate = bool(best_mate_in is not None and forgone and still_winning and big_gap)

        mate_miss_severity = 0.0
        if miss_mate:
            mate_miss_severity = float(top_gap or 0) + 200.0 * float((played_mate_in or 99) - best_mate_in)

        # --- label ---
        is_book = False
        gap_for_label = top_gap if top_gap is not None else 0

        if mate_flip:
            if eval_before_cp > 0 and eval_after_cp < 0:
                label = "Blunder"
            elif eval_before_cp < 0 and eval_after_cp > 0:
                label = "Brilliant"
            else:
                label = label_move(fen_before, move, eval_before_cp, eval_after_cp,
                                   multipv_rank, is_sacrifice, is_book, gap_for_label)
        elif miss_mate:
            label = "Miss"
        else:
            label = label_move(fen_before, move, eval_before_cp, eval_after_cp,
                               multipv_rank, is_sacrifice, is_book, gap_for_label)

        return jsonify({
            "fen_before": fen_before,

            # RAW White-centric CP (mates mapped)
            "eval_before": eval_before_cp,
            "eval_after":  eval_after_cp,
            "eval_change": eval_change,

            "multipv_rank": multipv_rank,
            "top_gap": top_gap,
            "cpl": cpl,

            "eval_before_struct": pre_score,
            "eval_after_struct":  post_score,

            "is_sacrifice": is_sacrifice,

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
        # return a structured 500 so the UI can show a clear message
        return jsonify({
            "error": "ENGINE_ANALYSIS_FAILED",
            "message": str(e)
        }), 500

# @app.route('/evaluate', methods=['POST'])
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

#     MISS_STILL_WINNING_CP = 300
#     MISS_TOLERANCE_PLIES  = 1
#     MISS_MIN_GAP_CP       = 300

#     global persistent_engine
#     data = request.json
#     fen = data.get("fen")
#     move = data.get("move")
#     depth = int(data.get("depth", 18))
#     multipv = int(data.get("multipv", 5))

#     logger.info(f"Evaluating move: {move} for FEN: {fen[:60]}...")

#     try:
#         board = chess.Board(fen)
#         fen_before = fen

#         # --- analyze PRE (RAW White POV) ---
#         if persistent_engine is not None:
#             pre = analyze_fen_multipv_persistent(fen, persistent_engine, depth=depth, multipv=multipv)
#         else:
#             pre = analyze_fen_multipv(fen, depth=depth, multipv=multipv)

#         # Rank/gap vs best (RAW)
#         multipv_rank, top_gap, played_eval_from_pre, best_eval_from_pre = played_rank_and_gap(
#             move, pre, None  # root_turn ignored (RAW mode)
#         )

#         # Eval BEFORE (best line) in RAW CP (White POV)
#         pre_score = pre[0]["score"]
#         # eval_before_cp = cp_from_score(pre_score)
#         eval_after_cp = cp_from_score(post_score, side_to_move='w')

#         # --- analyze POST (after the move) ---
#         board.push_uci(move)
#         post_fen = board.fen()

#         if persistent_engine is not None:
#             post = analyze_fen_multipv_persistent(post_fen, persistent_engine, depth=depth, multipv=1)
#         else:
#             post = analyze_fen_multipv(post_fen, depth=depth, multipv=1)

#         # Eval AFTER in RAW CP (White POV)
#         post_score = post[0]["score"]
#         eval_after_cp = cp_from_score(post_score)

#         print(f"RAW pre={pre_score} post={post_score}  raw_cp pre={eval_before_cp:+} post={eval_after_cp:+}")

#         # Delta in RAW (positive = better for White, negative = better for Black)
#         eval_change = eval_after_cp - eval_before_cp

#         # CPL = |best_pre_raw - played_pre_raw| ; fallback to POST raw if not in PV
#         if played_eval_from_pre is None:
#             played_eval_from_pre = eval_after_cp
#         cpl = abs(best_eval_from_pre - played_eval_from_pre) if best_eval_from_pre is not None else None

#         # If top_gap missing (move not in PV), set it to CPL for UI
#         if top_gap is None:
#             top_gap = cpl

#         logger.info(
#             f"[RAW] Eval change {eval_before_cp:+.1f} → {eval_after_cp:+.1f} (Δ {eval_change:+.1f}); "
#             f"rank={multipv_rank}, top_gap={top_gap if top_gap is not None else 'N/A'} cp, CPL={cpl}"
#         )

#         # --- sacrifice check (unchanged logic; uses board features) ---
#         original_board = chess.Board(fen)
#         uci_move = chess.Move.from_uci(move)
#         is_sacrifice = is_real_sacrifice(original_board, uci_move)

#         # --- mate metadata (RAW) ---
#         best_mate_in   = mate_ply(pre_score)   # mate-in-N BEFORE (best line)
#         played_mate_in = mate_ply(post_score)  # mate-in-N AFTER (played line)

#         pre_is_mate  = (pre_score.get("type")  == "mate")
#         post_is_mate = (post_score.get("type") == "mate")

#         # Mate ownership flip in RAW White POV:
#         # sign(pre_raw) * sign(post_raw) < 0  → switched winner (White mates vs Black mates)
#         mate_flip = bool(pre_is_mate and post_is_mate and (eval_before_cp * eval_after_cp < 0))
#         mate_flip_severity = 0
#         if mate_flip:
#             mate_flip_severity = 6400 + 100 * ((best_mate_in or 0) + (played_mate_in or 0))

#         # --- missed mate (RAW POV: "still winning for White") ---
#         still_winning = (eval_after_cp is not None and eval_after_cp >= MISS_STILL_WINNING_CP)
#         forgone = False
#         if best_mate_in is not None:
#             forgone = (played_mate_in is None) or (played_mate_in > best_mate_in + MISS_TOLERANCE_PLIES)

#         big_gap = (top_gap is not None and (top_gap >= MISS_MIN_GAP_CP))
#         miss_mate = bool(best_mate_in is not None and forgone and still_winning and big_gap)

#         mate_miss_severity = 0.0
#         if miss_mate:
#             mate_miss_severity = float(top_gap or 0) + 200.0 * float((played_mate_in or 99) - best_mate_in)

#         # --- labels (reuse your rule-set; pass RAW gap) ---
#         is_book = False
#         gap_for_label = top_gap if top_gap is not None else 0

#         if mate_flip:
#             # direction of flip in RAW White POV
#             if eval_before_cp > 0 and eval_after_cp < 0:
#                 label = "Blunder"    # White was mating → now Black is mating
#             elif eval_before_cp < 0 and eval_after_cp > 0:
#                 label = "Brilliant"  # Black was mating → now White is mating
#             else:
#                 label = label_move(fen, move, eval_before_cp, eval_after_cp, multipv_rank,
#                                    is_sacrifice, is_book, gap_for_label)
#         elif miss_mate:
#             label = "Miss"
#         else:
#             label = label_move(fen, move, eval_before_cp, eval_after_cp, multipv_rank,
#                                is_sacrifice, is_book, gap_for_label)

#         return jsonify({
#             "fen_before": fen_before,

#             # These are now RAW White-centric CP (mates mapped via cp_from_score)
#             "eval_before": eval_before_cp,
#             "eval_after":  eval_after_cp,
#             "eval_change": eval_change,

#             "multipv_rank": multipv_rank,
#             "top_gap": top_gap,   # RAW gap vs best (PRE)
#             "cpl": cpl,           # RAW CPL

#             "eval_before_struct": pre_score,   # original dicts for UI (cp/mate, value)
#             "eval_after_struct":  post_score,

#             "is_sacrifice": is_sacrifice,

#             # mate-related
#             "best_mate_in": best_mate_in,
#             "played_mate_in": played_mate_in,
#             "miss_mate": miss_mate,
#             "mate_miss_severity": mate_miss_severity,
#             "mate_flip": mate_flip,
#             "mate_flip_severity": mate_flip_severity,

#             "label": label
#         })

    except Exception as e:
        logger.error(f"Error in /evaluate: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


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

#         print(f"RAW pre={pre[0]['score']} post={post[0]['score']}  norm pre={eval_before_cp:+} post={eval_after_cp:+} root_turn={root_turn} node_after={node_turn_after}")


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

#         # --- mate metadata (pre/post) ---
#         pre_score   = pre[0]["score"]
#         post_score  = post[0]["score"]
#         best_mate_in   = mate_ply(pre_score)      # mate-in-N in best line BEFORE
#         played_mate_in = mate_ply(post_score)     # mate-in-N AFTER played move

#         pre_is_mate  = (pre_score.get("type")  == "mate")
#         post_is_mate = (post_score.get("type") == "mate")

#         # Mate ownership flip (winning mate → losing mate or vice versa)
#         mate_flip = bool(pre_is_mate and post_is_mate and (eval_before_cp * eval_after_cp < 0))
#         mate_flip_severity = 0
#         if mate_flip:
#             # heavy severity so it always overrides CPL-based labels
#             mate_flip_severity = 6400 + 100 * ((best_mate_in or 0) + (played_mate_in or 0))

#         # --- missed mate detection (pre-best vs post) ---
#         still_winning = eval_after_cp is not None and (eval_after_cp >= MISS_STILL_WINNING_CP)
#         forgone = False
#         if best_mate_in is not None:
#             # missed if mate disappears OR gets slower by more than tolerance
#             forgone = (played_mate_in is None) or (played_mate_in > best_mate_in + MISS_TOLERANCE_PLIES)

#         big_gap = (top_gap is not None and (top_gap >= MISS_MIN_GAP_CP))
#         miss_mate = bool(best_mate_in is not None and forgone and still_winning and big_gap)

#         # a simple severity score for miss (handy for calibration/UX)
#         mate_miss_severity = 0.0
#         if miss_mate:
#             mate_miss_severity = float(top_gap or 0) + 200.0 * float((played_mate_in or 99) - best_mate_in)

#         is_book = False
#         gap_for_label = top_gap if top_gap is not None else 0

#         if mate_flip:
#             # Check direction of flip
#             if eval_before_cp > 0 and eval_after_cp < 0:
#                 label = "Blunder"   # lost winning mate
#             elif eval_before_cp < 0 and eval_after_cp > 0:
#                 label = "Brilliant" # saved from mate or turned it around
#             else:
#                 label = label_move(
#                     fen, move, eval_before_cp, eval_after_cp, multipv_rank,
#                     is_sacrifice, is_book, gap_for_label
#                 )
#         elif miss_mate:
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
#             "eval_before_struct": pre_score,
#             "eval_after_struct":  post_score,
#             "is_sacrifice": is_sacrifice,

#             # mate-related outputs
#             "best_mate_in": best_mate_in,
#             "played_mate_in": played_mate_in,
#             "miss_mate": miss_mate,
#             "mate_miss_severity": mate_miss_severity,
#             "mate_flip": mate_flip,
#             "mate_flip_severity": mate_flip_severity,

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
