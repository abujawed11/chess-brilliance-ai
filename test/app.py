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


from basic_move_labels import classify_basic_move, detect_miss


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
# MATE_CP = 32000
# MATE_STEP = 1000  # drop per ply

# def cp_white_raw(score: dict) -> int:
#     """
#     Map a Stockfish score dict to centipawns from White's POV ONLY.
#     - cp: return value as-is
#     - mate: + for White mates, - for Black mates
#       cp = (MATE_CP - MATE_STEP * |plies|)
#     """
#     if not score:
#         return 0
#     t = score.get("type")
#     v = score.get("value", 0)
#     if t == "mate":
#         try:
#             n = max(0, int(abs(v)))  # plies to mate
#         except Exception:
#             n = 0
#         # Handle edge cases: if v==0 (terminal), treat as full MATE_CP
#         base = MATE_CP - MATE_STEP * n
#         if base < 0:
#             base = 0
#         return base if v > 0 else -base
#     # cp case
#     try:
#         return int(v)
#     except Exception:
#         return 0


# --- Position-based eval from White's perspective ---
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

    # 1) Normal centipawn case
    if t == "cp":
        try:
            v = int(v)
        except Exception:
            v = 0
        # Stockfish: cp is from side-to-move POV
        # If White to move: v = advantage for White
        # If Black to move: v = advantage for Black => flip sign
        return v if side_to_move == "w" else -v

    # 2) Mate case
    if t == "mate":
        try:
            v = int(v)
        except Exception:
            v = 0

        # raw v is from side-to-move POV
        # turn = 'w':
        #   v > 0 -> White mates in v
        #   v < 0 -> White gets mated in |v|
        # turn = 'b':
        #   v > 0 -> Black mates in v (White gets mated)
        #   v < 0 -> Black gets mated in |v| (White mates)
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
# MultiPV helper  (RAW / White-centric)
# ----------------------------
# def played_rank_and_gap(uci_move, pvs, _root_turn_ignored):
#     """
#     Return (rank, top_gap_cp, played_eval_cp, best_eval_cp) using RAW White-centric CP.

#     - best_eval_cp: RAW CP of PV#1 from PRE (cp_from_score)
#     - played_eval_cp: RAW CP of the played move from PRE (cp_from_score)
#     - top_gap_cp: |best_eval_cp - played_eval_cp|
#     """
#     if not pvs:
#         return (1, None, None, None)

#     uci_move_normalized = uci_move.lower().strip().replace('=', '')
#     K = len(pvs)

#     # RAW White-centric best eval
#     # best_eval_cp = cp_from_score(pvs[0]["score"])
#     # best_eval_cp = cp_from_score(pvs[0]["score"], side_to_move='w')
#     best_eval_cp = cp_white_raw(pvs[0]["score"])

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
#             # played_eval_cp = cp_from_score(pv_entry["score"])       # RAW (White POV)
#             # played_eval_cp = cp_from_score(pv_entry["score"], side_to_move='w')
#             played_eval_cp = cp_white_raw(pv_entry["score"])

#             top_gap = abs(best_eval_cp - played_eval_cp)            # RAW gap
#             logger.info(f"Move '{uci_move_normalized}' found at rank {rank}, RAW gap={top_gap:.1f}cp")
#             return (rank, top_gap, played_eval_cp, best_eval_cp)

#     logger.warning(
#         f"Move '{uci_move_normalized}' not found in any PV. "
#         f"Available first moves: {[pv.get('pv', [''])[0] if pv.get('pv') else '' for pv in pvs]}"
#     )
#     return (K + 1, None, None, best_eval_cp)


# ----------------------------
# MultiPV helper  (White POV)
# ----------------------------
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

    uci_move_normalized = uci_move.lower().strip().replace('=', '')
    K = len(pvs)

    # Best eval from PRE, White POV
    best_eval_cp = eval_for_white(pvs[0]["score"], side_to_move)

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
            played_eval_cp = eval_for_white(pv_entry["score"], side_to_move)
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

        side_before = 'w' if board.turn == chess.WHITE else 'b'

        # --- PRE (RAW White-centric) with retries ---
        pre = analyze_or_fail(fen_before, depth, multipv, persistent_engine)
        pre_score = pre[0]["score"]
        eval_before_cp = eval_for_white(pre_score, side_before)



        
        # pre = analyze_or_fail(fen_before, depth, multipv, persistent_engine)
        # pre_score = pre[0]["score"]
        # # eval_before_cp = cp_from_score(pre_score, side_to_move='w')
        # eval_before_cp = cp_white_raw(pre_score)

        # rank/gap vs best (RAW)
        # multipv_rank, top_gap, played_eval_from_pre, best_eval_from_pre = played_rank_and_gap(
        #     move, pre, None  # root ignored in RAW path
        # )
        multipv_rank, top_gap, played_eval_from_pre, best_eval_from_pre = played_rank_and_gap(
        move, pre, side_before
        )

       

        # --- POST (after the move) with retries ---
        board.push_uci(move)
        post_fen = board.fen()
        post = analyze_or_fail(post_fen, depth, 1, persistent_engine)
        post_score = post[0]["score"]

        side_after = 'w' if board.turn == chess.WHITE else 'b'
        eval_after_cp = eval_for_white(post_score, side_after)

        # eval_after_cp = cp_from_score(post_score, side_to_move='w')
        # eval_after_cp  = cp_white_raw(post_score)

        print(f"RAW pre={pre_score} post={post_score}  raw_cp pre={eval_before_cp:+} post={eval_after_cp:+}")
        print(f"best_eval_from_pre ={best_eval_from_pre} multipv_rank = {multipv_rank}  top_gap = {top_gap} played_eval_from_pre={played_eval_from_pre} ")

        print( "NEW :"
            f"RAW pre={pre_score} post={post_score}  "
            f"white_eval pre={eval_before_cp:+} post={eval_after_cp:+}  "
            f"side_before={side_before} side_after={side_after}"
        )


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

        basic_label = classify_basic_move(
            eval_before_white=eval_before_cp,
            eval_after_white=eval_after_cp,
            cpl=cpl,
            mover_color=side_before,      # 'w' or 'b'
            multipv_rank=multipv_rank,
        )

        print("Basic label: ", basic_label)



        # --- Miss detection (general tactical / conversion / save) ---
        # We use best_eval_from_pre (White POV) as the eval of the engine's PV#1
        # miss_detected = detect_miss(
        #     eval_before_white=eval_before_cp,
        #     eval_after_white=eval_after_cp,
        #     eval_best_white=best_eval_from_pre,
        #     mover_color=side_before,
        #     best_mate_in_plies=None,       # we keep your old miss_mate logic separate for now
        #     played_mate_in_plies=None,
        # )
                # General Miss detection (tactical / save / conversion)


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


        is_miss = detect_miss(
            eval_before_white=eval_before_cp,
            eval_after_white=eval_after_cp,
            eval_best_white=best_eval_from_pre,
            mover_color=side_before,
            best_mate_in_plies=best_mate_in,      # you already compute this later
            played_mate_in_plies=played_mate_in,  # optional, not used yet
        )

        print("miss_detected", is_miss)

        # --- label ---
        # is_book = False
        # gap_for_label = top_gap if top_gap is not None else 0

        # if mate_flip:
        #     if eval_before_cp > 0 and eval_after_cp < 0:
        #         label = "Blunder"
        #     elif eval_before_cp < 0 and eval_after_cp > 0:
        #         label = "Brilliant"
        #     else:
        #         label = label_move(fen_before, move, eval_before_cp, eval_after_cp,
        #                            multipv_rank, is_sacrifice, is_book, gap_for_label)
        # elif miss_mate:
        #     label = "Miss"
        # else:
        #     label = label_move(fen_before, move, eval_before_cp, eval_after_cp,
        #                        multipv_rank, is_sacrifice, is_book, gap_for_label)
        is_book = False
        gap_for_label = top_gap if top_gap is not None else 0

        # --- Final label selection ---
        # 1) Mate flip overrides everything (Brilliant / Blunder swing)
        if mate_flip:
            if eval_before_cp > 0 and eval_after_cp < 0:
                label = "Blunder"   # threw away a winning mate
            elif eval_before_cp < 0 and eval_after_cp > 0:
                label = "Brilliant" # turned a lost mate into winning for your side
            else:
                label = label_move(
                    fen_before, move, eval_before_cp, eval_after_cp,
                    multipv_rank, is_sacrifice, is_book, gap_for_label
                )

        # 2) General Miss detection (tactical / conversion / save) or your existing missed-mate
        elif is_miss:
            label = "Miss"

        # 3) Fallback to your existing label_rules logic
        else:
            label = label_move(
                fen_before, move, eval_before_cp, eval_after_cp,
                multipv_rank, is_sacrifice, is_book, gap_for_label
            )

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

            "basic_label": basic_label,      # <-- NEW (optional)
            "miss_detected": is_miss,  # <-- NEW (optional)
            "label": label
        })

    except Exception as e:
        logger.error(f"Error in /evaluate: {str(e)}", exc_info=True)
        # return a structured 500 so the UI can show a clear message
        return jsonify({
            "error": "ENGINE_ANALYSIS_FAILED",
            "message": str(e)
        }), 500

    except Exception as e:
        logger.error(f"Error in /evaluate: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# ----------------------------
# Entrypoint
# ----------------------------
if __name__ == "__main__":
    app.run(debug=True)
