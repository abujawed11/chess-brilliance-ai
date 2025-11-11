# """
# Threshold-based labels; tune later.
# Input: dict with keys:
#  - cp_loss (float, positive = worse for player who moved)
#  - pre_top_gap (float, PV#1 - PV#2 cp gap before move)
#  - played_rank (int, 1 = best line before move)
#  - is_sac (bool)
#  - depth (int)
#  - robust (bool)  # post-move still OK at +4 depth
# Return: label string.
# """
# def label_move(x: dict) -> str:
#     cp_loss = x.get("cp_loss", 0.0)
#     pre_gap = x.get("pre_top_gap", 0.0)
#     rank = x.get("played_rank", 99)
#     is_sac = x.get("is_sac", False)
#     depth = x.get("depth", 0)
#     robust = x.get("robust", False)

#     # Easy buckets first
#     if cp_loss >= 300: return "blunder"
#     if cp_loss >= 120: return "mistake"
#     if cp_loss >= 50:  return "inaccuracy"

#     # Brilliant (strict): only-move or sound sacrifice discovered deep & robust
#     if rank == 1 and robust and depth >= 20 and (pre_gap >= 200 or is_sac):
#         return "brilliant"

#     # Best / Excellent / Good
#     if rank == 1: return "best"
#     if rank <= 2: return "excellent"
#     return "good"




# label_rules.py

import chess  # optional: can be used for move and board analysis if needed
import chess.pgn

# Piece values for reference (could be used to determine sacrifices if needed)
PIECE_VALUES = {
    'p': 1,  # pawn
    'n': 3,  # knight
    'b': 3,  # bishop
    'r': 5,  # rook
    'q': 9,  # queen
    'k': 0   # king (king's "value" is not usually counted in material balance)
}

def is_book_move(fen: str, move: str) -> bool:
    """
    Placeholder function to check if a given move is a known opening (book) move.
    In a real implementation, this could look up the move in an opening database.
    For now, it returns False for all inputs (no actual book knowledge).
    """
    # Example: this could use an openings library or a set of known book moves.
    return False

def label_move(
    fen: str,
    move: str,
    eval_before: float,
    eval_after: float,
    multipv_rank: int,
    is_sacrifice: bool,
    is_book: bool = False
) -> str:
    if is_book:
        return "Book"

    eval_change = eval_after - eval_before
    eval_loss = max(0, -eval_change)

    # 🟨 Category 1: Brilliance should be checked first
    if is_sacrifice and eval_loss >= 500 and eval_after < 0 and multipv_rank <= 2:
        return "Brilliant"

    # 🟦 Category 2: Great/Excellent
    if multipv_rank == 1:
        if eval_change >= 150:
            return "Great"
        elif eval_change >= 70:
            return "Excellent"
        else:
            return "Best"

    # 🟩 Category 3: Good
    if multipv_rank <= 3 and eval_loss <= 50:
        return "Good"

    # 🟥 Category 4: Inaccuracy → Mistake → Blunder
    if eval_loss > 300:
        return "Blunder"
    elif eval_loss > 150:
        return "Mistake"
    elif eval_loss > 50:
        return "Inaccuracy"

    # 🟫 Category 5: Miss
    return "Miss"



# def label_move(fen: str, move: str, eval_before: float, eval_after: float, 
#                multipv_rank: int, is_sacrifice: bool, is_book: bool) -> str:
#     """
#     Classify a chess move into categories similar to Chess.com's game review.
    
#     Parameters:
#         fen (str): The FEN of the position **before** the move is played.
#         move (str): The move in algebraic or UCI notation (e.g., "Nf3" or "g1f3").
#         eval_before (float): Engine evaluation *before* the move (in centipawns).
#                               Positive values favor White, negative favor Black.
#         eval_after (float): Engine evaluation *after* the move (in centipawns).
#         multipv_rank (int): The rank of this move in the engine's Multi-PV analysis 
#                              (1 = best move, 2 = second-best, etc.).
#         is_sacrifice (bool): True if the move involves a deliberate material sacrifice 
#                               (based on piece values given up vs. gained).
#         is_book (bool): True if the move is a known book (opening theory) move.
    
#     Returns:
#         str: The label for the move, one of:
#              "Brilliant", "Great", "Best", "Excellent", "Good", "Book",
#              "Inaccuracy", "Mistake", "Miss", or "Blunder".
#     """
#     # 1. Book moves (opening theory) take precedence over other labels.
#     if is_book:
#         return "Book"
    
#     # 2. Calculate the change in evaluation (centipawn loss or gain) caused by the move.
#     # We interpret eval_before and eval_after from the perspective of the player who made the move.
#     # A positive eval_before means the side to move (White if eval positive, Black if negative) was ahead before the move.
#     # We define eval_loss as how much evaluation advantage was lost due to the move.
#     eval_change = eval_after - eval_before  # positive if the evaluation increased after the move (good for the mover), negative if it decreased.
#     if eval_change < 0:
#         eval_loss = -eval_change  # convert negative drop to a positive loss value
#     else:
#         eval_loss = 0  # if eval_change is positive or zero, the move did not lose any advantage (it improved or kept the eval).
    
#     # 3. Brilliant move: sacrifice + top engine choice + not trivially winning beforehand.
#     # Check if the move is a known sacrifice and is the best move.
#     if is_sacrifice and multipv_rank == 1:
#         # Additional conditions for brilliance:
#         # - The side should not end up in a losing position after the move.
#         # - The game wasn't already completely won without this move.
#         # We'll use eval_after and eval_before to approximate these:
#         if eval_after > -300 and eval_before < 300:
#             # eval_after > -300cp: not a "bad" position after the move (not significantly losing).
#             # eval_before < 300cp: not already completely winning before the move.
#             return "Brilliant"
    
#     # 4. Great move: top engine move (multipv=1) that has a significant positive impact.
#     if multipv_rank == 1 and not is_sacrifice:
#         # If the move dramatically improves the evaluation or was the only move to maintain the best outcome.
#         # For example, turning a losing or equal position into a winning one.
#         if eval_after - eval_before > 100:
#             # Gained more than a pawn in value (100 cp) – a big swing in evaluation.
#             return "Great"
#         elif eval_before < 0 and eval_after >= 0:
#             # Alternatively, if it turned a losing position (negative eval) into equal or better.
#             return "Great"
#         # If it doesn't meet the "Great" criteria but is still the top move, label it as Best.
#         return "Best"
    
#     # 5. Best move: If none of the above triggered and this is the top move, label as Best.
#     if multipv_rank == 1:
#         return "Best"
    
#     # 6. Excellent move: near-optimal (within top 2 choices, small eval loss).
#     if multipv_rank <= 2 and eval_loss <= 20:
#         return "Excellent"
    
#     # 7. Good move: a reasonably good move (within top 3, small eval loss).
#     if multipv_rank <= 3 and eval_loss <= 50:
#         return "Good"
    
#     # 8. Miss: If the move is not the best, check if a significantly better move was available.
#     # We consider it a "Miss" (missed opportunity) if the best move would have improved the eval by over 100 cp.
#     if multipv_rank != 1 and eval_loss > 100:
#         # (eval_loss > 100 cp implies the move lost more than a pawn worth relative to the best move.)
#         return "Miss"
    
#     # 9. Inaccuracy/Mistake/Blunder: classify based on the magnitude of eval loss.
#     if eval_loss > 300:
#         return "Blunder"
#     elif eval_loss > 150:
#         return "Mistake"
#     elif eval_loss > 50:
#         return "Inaccuracy"
    
#     # 10. If none of the above conditions matched, the move is very close to the best (<=50 cp loss)
#     # but didn't fall in top3 criteria. We can classify it as "Good" by elimination, since it's not a serious error.
#     return "Good"
