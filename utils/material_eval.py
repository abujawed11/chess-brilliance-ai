"""
Material helpers usable by label rules or motif detection.
"""
import chess

PIECE_CP = {chess.PAWN:100, chess.KNIGHT:320, chess.BISHOP:330, chess.ROOK:500, chess.QUEEN:900, chess.KING:0}

def material_cp(board: chess.Board):
    w = b = 0
    for pt, cp in PIECE_CP.items():
        w += len(board.pieces(pt, chess.WHITE)) * cp
        b += len(board.pieces(pt, chess.BLACK)) * cp
    return w - b  # +cp means White is up
