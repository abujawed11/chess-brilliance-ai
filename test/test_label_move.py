import chess
from teacher.label_rules import label_move
from utils.chess_helpers import analyze_fen_multipv, cp_from_score

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

def is_real_sacrifice(board_before: chess.Board, move: chess.Move) -> bool:
    board = board_before.copy()
    mover_color = board.turn
    from_sq, to_sq = move.from_square, move.to_square
    moved_piece_type = board.piece_type_at(from_sq)
    captured_piece_type = board.piece_type_at(to_sq)

    board.push(move)

    # Is the destination square attacked by opponent?
    if not board.is_attacked_by(not mover_color, to_sq):
        return False

    moved_value = material_value(moved_piece_type)
    captured_value = material_value(captured_piece_type)

    attackers = board.attackers(not mover_color, to_sq)
    defenders = board.attackers(mover_color, to_sq)
    net_loss = moved_value - captured_value

    return net_loss > 0 and len(defenders) < len(attackers)

def played_rank_in_pvs(uci_move: str, pvs: list) -> int:
    for d in pvs:
        pv = d.get("pv", [])
        if pv and pv[0].lower().startswith(uci_move[:4]):
            return d["multipv"]
    return 99

# Test FEN and move
fen = "3q4/2p5/p3r3/4npkp/1Q6/3P4/5PKP/4B3 w - - 0 1"
move = "b4h4"
depth = 18
multipv = 5

# Analyze pre-move
pre = analyze_fen_multipv(fen, depth=depth, multipv=multipv)
side = 'w' if chess.Board(fen).turn else 'b'
eval_before = cp_from_score(pre[0]["score"], side)

# Compute multipv rank
multipv_rank = played_rank_in_pvs(move, pre)

# Push move and get post-eval
board = chess.Board(fen)
board.push_uci(move)
post_fen = board.fen()
post = analyze_fen_multipv(post_fen, depth=depth, multipv=multipv)
eval_after = cp_from_score(post[0]["score"], 'w' if board.turn else 'b')

# Compute is_sacrifice realistically
original_board = chess.Board(fen)
uci_move = chess.Move.from_uci(move)
is_sacrifice = is_real_sacrifice(original_board, uci_move)

# Final label
is_book = False
print("Move:", move)
print("Eval before:", eval_before)
print("Eval after:", eval_after)
print("Multipv rank:", multipv_rank)
print("Is sacrifice:", is_sacrifice)
print("Eval loss:", eval_before - eval_after)

label = label_move(fen, move, eval_before, eval_after, multipv_rank, is_sacrifice, is_book)
print(f"Labeled as: {label}")
