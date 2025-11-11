from flask import Flask, request, jsonify
from flask_cors import CORS
import chess

from utils.chess_helpers import analyze_fen_multipv, cp_from_score
from teacher.label_rules import label_move

app = Flask(__name__)
CORS(app)

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
    for d in pvs:
        pv = d.get("pv", [])
        if pv and pv[0].lower().startswith(uci_move[:4]):
            return d["multipv"]
    return 99

@app.route('/evaluate', methods=['POST'])
def evaluate_move():
    data = request.json
    fen = data.get("fen")
    move = data.get("move")
    depth = int(data.get("depth", 18))
    multipv = int(data.get("multipv", 5))

    try:
        board = chess.Board(fen)
        side = 'w' if board.turn else 'b'

        pre = analyze_fen_multipv(fen, depth=depth, multipv=multipv)
        eval_before = cp_from_score(pre[0]["score"], side)
        multipv_rank = played_rank_in_pvs(move, pre)

        # Push move and analyze post
        board.push_uci(move)
        post_fen = board.fen()
        post = analyze_fen_multipv(post_fen, depth=depth, multipv=multipv)
        eval_after = cp_from_score(post[0]["score"], 'w' if board.turn else 'b')

        # Check for real sacrifice
        original_board = chess.Board(fen)
        uci_move = chess.Move.from_uci(move)
        is_sacrifice = is_real_sacrifice(original_board, uci_move)

        is_book = False  # Replace with logic if needed
        label = label_move(fen, move, eval_before, eval_after, multipv_rank, is_sacrifice, is_book)

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

