from flask import Flask, request, jsonify
from flask_cors import CORS
import chess
import logging

from utils.chess_helpers import analyze_fen_multipv, cp_from_score
from teacher.label_rules import label_move

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Piece values for sacrifice detection
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0
}

def material_value(piece_type):
    return PIECE_VALUES.get(piece_type, 0)

# def is_real_sacrifice(board_before: chess.Board, move: chess.Move) -> bool:
#     board = board_before.copy()
#     mover_color = board.turn
#     from_sq, to_sq = move.from_square, move.to_square
#     moved_piece_type = board.piece_type_at(from_sq)
#     captured_piece_type = board.piece_type_at(to_sq)

#     board.push(move)

#     if not board.is_attacked_by(not mover_color, to_sq):
#         return False

#     moved_value = material_value(moved_piece_type)
#     captured_value = material_value(captured_piece_type)
#     attackers = board.attackers(not mover_color, to_sq)
#     defenders = board.attackers(mover_color, to_sq)
#     net_loss = moved_value - captured_value

#     return net_loss > 0 and len(defenders) < len(attackers)


def is_real_sacrifice(board_before: chess.Board, move: chess.Move) -> bool:
    board = board_before.copy()
    mover_color = board.turn
    from_sq = move.from_square
    to_sq = move.to_square
    moved_piece = board.piece_at(from_sq)

    if moved_piece is None:
        return False

    moved_value = PIECE_VALUES.get(moved_piece.piece_type, 0)
    captured_piece = board.piece_at(to_sq)
    captured_value = PIECE_VALUES.get(captured_piece.piece_type, 0) if captured_piece else 0

    # Apply move
    board.push(move)

    # Now check: is the destination square attacked?
    attacked = board.is_attacked_by(not mover_color, to_sq)
    defended = board.is_attacked_by(mover_color, to_sq)

    net_material_loss = moved_value - captured_value

    # Define sacrifice more broadly now:
    if attacked and (not defended or net_material_loss > 0):
        return True

    return False


def played_rank_in_pvs(uci_move, pvs):
    """
    Find the rank of a UCI move in the multipv results.
    Handles promotion moves correctly (e.g., e7e8q, e7e8=Q, e7e8).
    """
    # Normalize the input move to lowercase
    uci_move_lower = uci_move.lower().strip()

    # Remove '=' from promotions if present (e7e8=q -> e7e8q)
    uci_move_normalized = uci_move_lower.replace('=', '')

    logger.debug(f"Searching for move: '{uci_move_normalized}' in {len(pvs)} PVs")

    for d in pvs:
        pv = d.get("pv", [])
        if not pv:
            continue

        pv_move = pv[0].lower().strip()
        logger.debug(f"  Comparing with PV#{d['multipv']}: '{pv_move}'")

        # Exact match (best case)
        if pv_move == uci_move_normalized:
            logger.info(f"Exact match found: '{uci_move_normalized}' = PV#{d['multipv']}")
            return d["multipv"]

        # Handle promotion variants: compare base move (first 4 chars) and promotion piece
        # e.g., "e7e8q" should match "e7e8q" or "e7e8"
        if len(uci_move_normalized) >= 4 and len(pv_move) >= 4:
            # If one is a promotion (5 chars) and other isn't, check base matches
            if len(uci_move_normalized) == 5 or len(pv_move) == 5:
                # Both have same source/dest squares
                if pv_move[:4] == uci_move_normalized[:4]:
                    # If lengths match or one is missing promotion suffix, it's a match
                    if len(pv_move) == len(uci_move_normalized):
                        if pv_move[4] == uci_move_normalized[4]:
                            logger.info(f"Promotion match found: '{uci_move_normalized}' = PV#{d['multipv']}")
                            return d["multipv"]
                    elif len(pv_move) == 4 or len(uci_move_normalized) == 4:
                        # One doesn't specify promotion, assume match
                        logger.info(f"Partial promotion match found: '{uci_move_normalized}' ≈ '{pv_move}' = PV#{d['multipv']}")
                        return d["multipv"]
            else:
                # Regular move (non-promotion) exact 4-char match
                if pv_move[:4] == uci_move_normalized[:4] and len(pv_move) == 4 and len(uci_move_normalized) == 4:
                    logger.info(f"Regular move match found: '{uci_move_normalized}' = PV#{d['multipv']}")
                    return d["multipv"]

    logger.warning(f"Move '{uci_move_normalized}' not found in any PV. Available moves: {[d.get('pv', [[]])[0] if d.get('pv') else 'none' for d in pvs]}")
    return 99

@app.route('/evaluate', methods=['POST'])
def evaluate_move():
    data = request.json
    fen = data.get("fen")
    move = data.get("move")
    depth = int(data.get("depth", 18))
    multipv = int(data.get("multipv", 5))

    logger.info(f"Evaluating move: {move} for FEN: {fen[:50]}...")

    try:
        board = chess.Board(fen)
        side = 'w' if board.turn else 'b'  # Side making the move

        pre = analyze_fen_multipv(fen, depth=depth, multipv=multipv)
        logger.debug(f"Engine returned {len(pre)} PV lines: {[d.get('pv', [[]])[0] if d.get('pv') else 'none' for d in pre]}")

        eval_before = cp_from_score(pre[0]["score"], side)
        multipv_rank = played_rank_in_pvs(move, pre)
        gap_to_second = pre[0].get("gap_to_second", 0)  # Extract gap between best and 2nd best move

        if multipv_rank == 99:
            logger.warning(f"multipv_rank is 99 for move '{move}'. This indicates the move was not found in engine PVs.")

        logger.debug(f"Gap to 2nd best move: {gap_to_second}cp")

        # Push move and analyze post
        board.push_uci(move)
        post_fen = board.fen()
        post = analyze_fen_multipv(post_fen, depth=depth, multipv=multipv)
        # IMPORTANT: Use the SAME side (who made the move) for consistent perspective
        eval_after = cp_from_score(post[0]["score"], side)

        eval_change = eval_after - eval_before
        logger.info(f"Evaluation change: {eval_before:+.1f} → {eval_after:+.1f} (Δ {eval_change:+.1f}cp) from {side.upper()}'s perspective")

        # Check for real sacrifice
        original_board = chess.Board(fen)
        uci_move = chess.Move.from_uci(move)
        is_sacrifice = is_real_sacrifice(original_board, uci_move)

        is_book = False  # Replace with logic if needed
        label = label_move(fen, move, eval_before, eval_after, multipv_rank, is_sacrifice, is_book, gap_to_second)

        return jsonify({
            "eval_before": eval_before,
            "eval_after": eval_after,
            "multipv_rank": multipv_rank,
            "is_sacrifice": is_sacrifice,
            "label": label
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)

