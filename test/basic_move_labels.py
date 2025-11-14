"""
basic_move_labels.py

Core engine-based move classification:
    Best / Good / Inaccuracy / Mistake / Blunder

This module assumes:
- eval_before_white and eval_after_white are Stockfish-style evaluations
  from WHITE's perspective, in centipawns, with mates mapped to big +/- values.
  (Exactly what you're already computing as eval_before_cp / eval_after_cp.)

- cpl = |best_eval_from_pre - played_eval_from_pre| from the PRE position,
  also in WHITE POV (same as your current CPL).

We convert these to the mover's POV and then classify the move.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import chess

# ---------------------------------------------------------------------------
# 1) Helpers: convert to player POV, bucket the situation
# ---------------------------------------------------------------------------



PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}






MIN_SAC_CP       = 300   # at least a minor piece effectively at risk
MIN_SEE_LOSS_CP  = 100   # SEE must say we lose ≥ 1 pawn locally
ATTACK_GAIN_CP   = 150   # if eval improves more than this, treat as attack, not "sac"
MATE_THRESHOLD   = 20000 # same idea as your existing mate cp mapping



def piece_cp(board: chess.Board, sq: chess.Square) -> int:
    p = board.piece_at(sq)
    return PIECE_VALUES.get(p.piece_type, 0) if p else 0


def naive_see(board: chess.Board, square: chess.Square, side_to_move: bool) -> int:
    """
    Very small static-exchange eval on `square`.
    Returns net cp for `side_to_move` assuming optimal local swaps.
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



def is_real_sacrifice(
    board_before: chess.Board,
    move: chess.Move,
    *,
    eval_before_white: float | None = None,
    eval_after_white: float | None = None,
    mover_color: str | None = None,
    eval_types: dict | None = None,
) -> bool:
    """
    Sacrifice detection tuned for your brilliancy system.

    True  -> move is a *material sacrifice* (non-trivial material put on a losing square)
    False -> no real material sacrifice

    Uses:
      - material debit (moved piece - captured piece)
      - naive_see() on the destination square
      - optional eval info to *exclude*:
          * forced mate clean-up sequences
          * huge eval-improving attack moves (attack brilliancy, not sac)
    """

    board = board_before.copy()
    mover = board.turn
    from_sq, to_sq = move.from_square, move.to_square

    moved_piece = board_before.piece_at(from_sq)
    if moved_piece is None:
        return False

    moved_cp = PIECE_VALUES[moved_piece.piece_type]
    if moved_cp == 0:
        # Kings / nonsense: not a sacrifice
        return False

    captured_cp = piece_cp(board_before, to_sq)

    # Handle en passant capture
    if board_before.is_en_passant(move):
        captured_cp = PIECE_VALUES[chess.PAWN]

    net_loss_cp = moved_cp - captured_cp
    if net_loss_cp < MIN_SAC_CP:
        # Not enough material at stake to count as a "sac" for brilliancy
        return False

    # Local static-exchange evaluation on destination square
    see_net_for_mover = naive_see(board_before, to_sq, mover)

    # If SEE says we are not really losing there, it's not a material sacrifice.
    if see_net_for_mover >= -MIN_SEE_LOSS_CP:
        return False

    # --- Forced mate sequences: don't call every mating move a 'sac' ---
    mate_before = (eval_types and eval_types.get("before") == "mate")
    mate_after  = (eval_types and eval_types.get("after")  == "mate")

    is_forced_mate_sequence = False
    if eval_before_white is not None and eval_after_white is not None:
        if abs(eval_before_white) >= MATE_THRESHOLD and abs(eval_after_white) >= MATE_THRESHOLD:
            if eval_before_white * eval_after_white > 0:  # same side mating
                is_forced_mate_sequence = True

    if is_forced_mate_sequence:
        # Mate-in-N clean-up (no real time to accept the material) -> not a 'sac'
        return False

    # --- Filter out pure attack-brilliancy where eval jumps UP a lot ---
    if (
        eval_before_white is not None and
        eval_after_white is not None and
        mover_color is not None
    ):
        before_pov = cp_for_player(eval_before_white, mover_color)
        after_pov  = cp_for_player(eval_after_white,  mover_color)
        eval_gain  = after_pov - before_pov

        # If the move *greatly* improves our eval, we treat it as an attack brilliancy
        # (your detect_brilliancy_level will already catch it),
        # but not as a "material sacrifice" for !!.
        if eval_gain >= ATTACK_GAIN_CP:
            return False

    # If we reach here:
    # - non-trivial material debit
    # - SEE says the square is locally losing
    # - not just forced-mate clean-up
    # - not a huge eval-improving attack move
    return True







# MIN_SAC_CP = 100






# def is_real_sacrifice(
#     board_before: chess.Board,
#     move: chess.Move,
#     eval_before=None,
#     eval_after=None,
#     eval_types=None
# ) -> bool:
#     """
#     Sacrifice detection using SEE + material debit.

#     NOTE: In forced mate sequences, we don't count "undefended" pieces as sacrifices
#     because the opponent doesn't have time to capture them.
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

#     # --- Special case: Forced mate sequences ---
#     # If both before and after are mate scores and we're improving or maintaining mate,
#     # this is NOT a sacrifice - it's a forced sequence where opponent has no time to capture.
#     mate_before = (eval_types and eval_types.get("before") == "mate")
#     mate_after  = (eval_types and eval_types.get("after")  == "mate")

#     MATE_THRESHOLD = 20000  # Approximate threshold for mate scores (adjust based on your MATE_CP)

#     is_forced_mate_sequence = False
#     if eval_before is not None and eval_after is not None:
#         # Check if both evals are in mate territory (very high absolute values)
#         if abs(eval_before) >= MATE_THRESHOLD and abs(eval_after) >= MATE_THRESHOLD:
#             # Check if we're maintaining or improving our mate (same sign, similar or better eval)
#             same_side_advantage = (eval_before * eval_after > 0)  # same sign
#             if same_side_advantage:
#                 is_forced_mate_sequence = True

#     if is_forced_mate_sequence:
#         print(f"[SAC DEBUG] Forced mate sequence detected - NOT counting as sacrifice")
#         print(f"  eval_before: {eval_before}, eval_after: {eval_after}")
#         return False

#     # Gate A: debit + opponent can accept + SEE < 0
#     if net_loss_cp >= MIN_SAC_CP and opp_can_capture_back and see_net_for_mover < 0:
#         print(f"[SAC DEBUG] Gate A triggered: net_loss={net_loss_cp}, SEE={see_net_for_mover}")
#         return True

#     # Gate B: destination square is simply losing via SEE
#     if see_net_for_mover < 0:
#         print(f"[SAC DEBUG] Gate B triggered: SEE={see_net_for_mover} (losing exchange)")
#         return True

#     # Gate C: forcing sac (check/mate) with acceptability
#     if (gives_check or mate_after or mate_before) and (
#         see_net_for_mover < 0 or (opp_can_capture_back and net_loss_cp >= MIN_SAC_CP)
#     ):
#         print(f"[SAC DEBUG] Gate C triggered: forcing move with material commitment")
#         return True

#     return False

def cp_for_player(eval_white_cp: float, mover_color: str) -> float:
    """
    Convert White-centric eval to mover-centric eval.

    eval_white_cp: evaluation from White's perspective (Stockfish style)
    mover_color:   'w' if White just moved, 'b' if Black just moved

    Returns:
        cp where:
            +ve = good for the mover,
            -ve = bad for the mover.
    """
    return eval_white_cp if mover_color == 'w' else -eval_white_cp


def situation_from_cp(cp_player: float) -> str:
    """
    Bucket the mover's position into rough game states, using
    evaluation from the mover's perspective (cp_player).

    Tunable thresholds, but these are a good starting point.
    """
    if cp_player >= 800:
        return "Won"          # totally winning (e.g. +8.0 or more)
    if cp_player >= 300:
        return "Winning"      # clearly better
    if cp_player > -300:
        return "Equalish"     # roughly equal / unclear
    if cp_player > -800:
        return "Worse"        # clearly worse
    return "Lost"             # basically busted


# ---------------------------------------------------------------------------
# 2) Base label from CPL only
# ---------------------------------------------------------------------------

LABEL_ORDER = ["Best", "Good", "Inaccuracy", "Mistake", "Blunder"]
LABEL_RANK = {name: i for i, name in enumerate(LABEL_ORDER)}


def base_label_from_cpl(cpl: float | None, multipv_rank: int | None) -> str:
    """
    Raw engine severity → one of:
        Best / Good / Inaccuracy / Mistake / Blunder

    cpl:
        Centipawn loss vs engine best (>= 0, already absolute).
    multipv_rank:
        1 if played move is engine PV #1, else >1 or None.
    """
    if cpl is None:
        # Fail-safe: if something went wrong, treat as Inaccuracy
        return "Inaccuracy"

    # Near-perfect moves
    if cpl <= 20:
        # If it's literally PV#1, call it Best,
        # otherwise it's still very strong (Good).
        return "Best" if (multipv_rank == 1) else "Good"

    if cpl <= 60:
        return "Good"
    if cpl <= 200:
        return "Inaccuracy"
    if cpl <= 500:
        return "Mistake"
    return "Blunder"


def promote_label(current: str, minimum: str) -> str:
    """
    Ensure label is at least as severe as 'minimum' (towards Blunder).

    Example:
        promote_label("Inaccuracy", "Mistake") -> "Mistake"
        promote_label("Blunder", "Mistake")    -> "Blunder"
    """
    if LABEL_RANK[current] < LABEL_RANK[minimum]:
        return minimum
    return current


def soften_label(current: str, maximum: str) -> str:
    """
    Cap label so it is no more severe than 'maximum'.

    Example:
        soften_label("Blunder", "Mistake") -> "Mistake"
        soften_label("Good", "Mistake")    -> "Good"
    """
    if LABEL_RANK[current] > LABEL_RANK[maximum]:
        return maximum
    return current


# ---------------------------------------------------------------------------
# 3) Main classifier for the core 5 labels
# ---------------------------------------------------------------------------

def classify_basic_move(
    eval_before_white: float,
    eval_after_white: float,
    cpl: float | None,
    mover_color: str,           # 'w' or 'b'
    multipv_rank: int | None,   # 1..K or None if unknown
) -> str:
    """
    Core 5-type classifier:
        Best / Good / Inaccuracy / Mistake / Blunder

    Args:
        eval_before_white:
            Engine eval BEFORE the move, from WHITE's perspective (cp).
        eval_after_white:
            Engine eval AFTER the move, from WHITE's perspective (cp).
        cpl:
            Centipawn loss vs engine best from the PRE position (>= 0 or None).
        mover_color:
            Which side made the move: 'w' for White, 'b' for Black.
        multipv_rank:
            Rank of the played move in the PRE multiPV (1 = engine best).
    """

    # ---------- Convert to player POV ----------
    player_before = cp_for_player(eval_before_white, mover_color)
    player_after  = cp_for_player(eval_after_white,  mover_color)
    player_delta  = player_after - player_before   # >0 helped mover, <0 hurt mover

    before_state = situation_from_cp(player_before)
    after_state  = situation_from_cp(player_after)

    # Normalize CPL
    if cpl is None:
        # crude fallback: at least use how much eval changed for the mover
        cpl = abs(player_delta)

    # ---------- 1) Base label from CPL ----------
    label = base_label_from_cpl(cpl, multipv_rank)

    # ---------- 2) Throwing away a win (punish harder) ----------
    if before_state in ("Winning", "Won") and after_state in ("Equalish", "Worse", "Lost"):
        # You were clearly better, now not anymore
        if cpl >= 300:
            label = promote_label(label, "Blunder")
        elif cpl >= 200:
            label = promote_label(label, "Mistake")

    # ---------- 3) Already totally lost (soften a bit) ----------
    if before_state == "Lost" and after_state == "Lost":
        # Don’t spam blunders in a -10 vs -12 type position
        label = soften_label(label, "Mistake")   # cap at Mistake
        if label == "Mistake" and cpl <= 250:
            label = "Inaccuracy"

    # ---------- 4) Normal positions: tweak by player_delta ----------
    # Large improvement for mover → be kinder than pure CPL
    if player_delta >= 100:  # mover improved by ≥ 1 pawn
        if label == "Blunder":
            label = "Mistake"
        elif label == "Mistake":
            label = "Inaccuracy"
        elif label == "Inaccuracy":
            label = "Good"

    # Large worsening for mover → be harsher
    if player_delta <= -150:  # mover worsened by ≥ 1.5 pawns
        if label == "Good":
            label = "Inaccuracy"
        elif label == "Inaccuracy" and cpl >= 150:
            label = "Mistake"

    # ---------- 5) Huge rescue (optional but nice) ----------
    # From completely lost to at least "not dead" with big improvement
    if before_state == "Lost" and after_state in ("Equalish", "Winning", "Won"):
        if player_delta >= 300:  # improved by ≥ 3 pawns
            # Never call such a move worse than Good
            if LABEL_RANK[label] > LABEL_RANK["Good"]:
                label = "Good"

            
        # ---------- 6) Already totally winning (soften a bit, symmetric to Lost->Lost) ----------
    if before_state == "Won" and after_state == "Won":
        # Don't spam blunders when you're +10 and stay +10/+12
        label = soften_label(label, "Mistake")   # cap at Mistake
        if label == "Mistake" and cpl <= 250:
            label = "Inaccuracy"
    print("before",before_state,"after state",after_state)

    return label






# ---------------------------------------------------------------------------
# 4) "Miss" detection (tactical / concrete chance missed, but no self-harm)
# ---------------------------------------------------------------------------

@dataclass
class MissParams:
    # We only call something Miss if the move itself didn't really damage the eval
    max_self_drop_cp: int = 80          # if mover worsens more than this, it's not a Miss

    # How big the missed opportunity must be (in mover POV)
    min_opportunity_cp: int = 250       # generic "big chance" threshold
    tactical_min_gain_cp: int = 350     # clear tactical/material win (~pawn+)

    # Bands for interpretation
    still_winning_cp: int = 300         # ≥ this is clearly winning
    equal_band_cp: int = 150           # |cp| ≤ this is "equalish"
    still_ok_cp: int = 120             # ≥ -this counts as drawable / OK

    # How much improvement counts as save / conversion
    min_save_gain_cp: int = 300        # for "missed save" (lost → drawable)
    min_conversion_gain_cp: int = 250  # small edge → big edge


def detect_miss(
    eval_before_white: float,
    eval_after_white: float,
    eval_best_white: Optional[float],
    mover_color: str,
    *,
    best_mate_in_plies: Optional[int] = None,
    played_mate_in_plies: Optional[int] = None,   # reserved if we need later
    params: Optional[MissParams] = None,
) -> bool:
    """
    Pure 'Miss' detector. Does NOT depend on any of your old miss logic.

    All eval_* are from WHITE's perspective.
    It converts to mover POV internally.

    Returns:
        True  -> classify as 'Miss'
        False -> do NOT classify as 'Miss'
    """
    if params is None:
        params = MissParams()

    # Need best-line eval; otherwise we don't know the missed opportunity.
    if eval_best_white is None:
        return False

    # Convert everything to mover POV
    before_pov = cp_for_player(eval_before_white, mover_color)
    after_pov  = cp_for_player(eval_after_white,  mover_color)
    best_pov   = cp_for_player(eval_best_white,   mover_color)

    # Deltas
    self_drop   = before_pov - after_pov        # >0 means we worsened our own eval
    opportunity = best_pov   - before_pov       # how much better best-line is vs current
    miss_gap    = best_pov   - after_pov        # how much better best-line is vs what we got


    print("MISS DEBUG:", {
        "before_pov": before_pov,
        "after_pov": after_pov,
        "best_pov": best_pov,
        "self_drop": self_drop,
        "opportunity": opportunity,
        "miss_gap": miss_gap,
        "situation": situation_from_cp(before_pov),
    })

    # --- Global gates ---
    # If we clearly worsened the eval, this move belongs to Inaccuracy/Mistake/Blunder, not Miss.
    if self_drop > params.max_self_drop_cp:
        return False

    # If the missed improvement is small, not a Miss.
    if opportunity < params.min_opportunity_cp or miss_gap < params.min_opportunity_cp:
        return False

    situation = situation_from_cp(before_pov)  # uses the same Won/Winning/Equalish/Worse/Lost mapping you already have

    # --- 1) Missed mate / kill shot while still winning ---

    if best_mate_in_plies is not None:
        # best line contains a mate for the mover
        if (
            best_pov  >= params.still_winning_cp and
            after_pov >= params.still_winning_cp
        ):
            # you had a forced mate and still stayed winning, but didn’t take it
            return True

    # Even without mate, a huge boost while staying winning -> kill shot missed
    if (
        situation in ("Winning", "Won") and
        before_pov >= params.still_winning_cp and
        best_pov   >= before_pov + params.tactical_min_gain_cp and
        after_pov  >= params.still_winning_cp
    ):
        return True

    # --- 2) Missed defensive resource / save (lost -> drawable) ---

    if situation in ("Worse", "Lost"):
        if (
            opportunity >= params.min_save_gain_cp and
            best_pov   >= -params.still_ok_cp  # best line gives at least drawable chances
        ):
            return True

    # --- 3) Missed conversion (edge -> big edge) ---

    if situation in ("Winning", "Equalish"):
        if (
            opportunity >= params.min_conversion_gain_cp and
            best_pov   >= before_pov + params.min_conversion_gain_cp
        ):
            return True

    # --- 4) Generic tactical Miss: equalish, big tactical jump available ---

    is_equalish = abs(before_pov) <= params.equal_band_cp
    is_big_tactical = (
        best_pov >= before_pov + params.tactical_min_gain_cp and
        best_pov >= params.tactical_min_gain_cp
    )

    if is_equalish and is_big_tactical:
        return True

    # --- 5) Fallback: big opportunity, small self-harm -> generic Miss ---

    if opportunity >= params.min_opportunity_cp:
        return True

    return False






# ---------------------------------------------------------------------------
# BOOK MOVE DETECTION
# ---------------------------------------------------------------------------

# @dataclass
# class BookParams:
#     """
#     Tunables for detecting "Book" moves (theoretical opening moves).

#     This is a *heuristic* layer which can optionally be combined with a real
#     opening database in the future.
#     """
#     # Opening phase cutoff: if fullmove_number > this, we don't call it Book
#     max_opening_fullmove: int = 12

#     # Opening positions should be near-equal
#     max_abs_eval_opening: int = 80         # |eval| must be <= this (≈0.8 pawns)
#     max_eval_change_opening: int = 60      # |eval_before - eval_after| <= this

#     # Move must be close to engine best
#     max_cpl_book: int = 35                 # CPL vs best must be small (≈0.35 pawn)

#     # We only treat the top few engine candidates as "theoretical"
#     max_multipv_rank: int = 3              # if multipv_rank > this → not Book


# def detect_book_move(
#     *,
#     fullmove_number: int,
#     eval_before_white: float,
#     eval_after_white: float,
#     cpl: Optional[float],
#     multipv_rank: Optional[int],
#     in_opening_db: Optional[bool] = None,
#     params: Optional[BookParams] = None,
# ) -> bool:
#     """
#     Decide whether a move should be labeled as 'Book'.

#     Arguments:
#         fullmove_number: 1-based fullmove number from the FEN
#                          (chess.Board(...).fullmove_number)
#         eval_before_white: eval BEFORE the move, White POV (cp)
#         eval_after_white:  eval AFTER the move, White POV (cp)
#         cpl: centipawn loss vs engine best from PRE (White POV)
#         multipv_rank: engine rank of the played move (1..K), or None if unknown
#         in_opening_db: if you have a real/small opening DB, pass True/False here.
#                        If True, this function returns True immediately.

#     Returns:
#         True  -> treat this move as 'Book'
#         False -> not Book
#     """
#     if params is None:
#         params = BookParams()

#     # If a real opening DB says "yes", trust it.
#     if in_opening_db is True:
#         return True

#     # Clearly out of the opening by move number
#     if fullmove_number > params.max_opening_fullmove:
#         return False

#     # Need CPL to know how far from best we are.
#     if cpl is None:
#         return False

#     # Move must be close to engine best
#     if cpl > params.max_cpl_book:
#         return False

#     # Opening positions should be roughly equal and stable
#     if abs(eval_before_white) > params.max_abs_eval_opening:
#         return False
#     if abs(eval_after_white) > params.max_abs_eval_opening:
#         return False
#     if abs(eval_before_white - eval_after_white) > params.max_eval_change_opening:
#         return False

#     # If we know multipv rank, restrict to top few candidates
#     if multipv_rank is not None and multipv_rank > params.max_multipv_rank:
#         return False

#     # Heuristically, this looks like a theoretical opening move.
#     return True


# def detect_book_move(
#     *,
#     fullmove_number: int,
#     eval_before_white: float,
#     eval_after_white: float,
#     cpl: Optional[float],
#     multipv_rank: Optional[int],
#     in_opening_db: Optional[bool] = None,
#     is_standard_start: bool = True,          # <-- add this param if you can
#     params: Optional[BookParams] = None,
# ) -> bool:
#     if params is None:
#         params = BookParams()

#     # 1) If a real opening DB says "yes", trust it.
#     if in_opening_db is True:
#         return True

#     # 2) If the game did NOT start from initial position,
#     #    do NOT use any heuristic Book logic.
#     if not is_standard_start:
#         return False

#     # 3) Heuristic Book only for early moves from start position
#     if fullmove_number > params.max_opening_fullmove:
#         return False

#     if cpl is None:
#         return False
#     if cpl > params.max_cpl_book:
#         return False
#     if abs(eval_before_white) > params.max_abs_eval_opening:
#         return False
#     if abs(eval_after_white) > params.max_abs_eval_opening:
#         return False
#     if abs(eval_before_white - eval_after_white) > params.max_eval_change_opening:
#         return False
#     if multipv_rank is not None and multipv_rank > params.max_multipv_rank:
#         return False

#     return True


@dataclass
class BookParams:
    """
    Book parameters placeholder.
    We now rely ONLY on a real opening database (Polyglot),
    so no heuristic thresholds are used here anymore.
    """
    pass


def detect_book_move(
    *,
    fullmove_number: int,
    eval_before_white: float,
    eval_after_white: float,
    cpl: Optional[float],
    multipv_rank: Optional[int],
    in_opening_db: Optional[bool] = None,
    params: Optional[BookParams] = None,
) -> bool:
    """
    Decide whether a move should be labeled 'Book'.

    NEW SIMPLE RULE:
    - Only return True if the move is found in the real opening DB
      (Polyglot `book.bin` via opening_book.is_book_move).
    - Ignore all heuristic logic based on eval, CPL, move number, etc.

    This guarantees:
    - No 'Book' labels in random middle-game/end-game FENs.
    - No 'Book' labels if the book file is missing.
    """
    # Only trust the real DB signal
    return bool(in_opening_db)




# ---------------------------------------------------------------------------
# 5) Brilliancy-level detection (for Brilliant !! and Great !)
# ---------------------------------------------------------------------------

@dataclass
class BrilliancyParams:
    """
    Tunables for detecting brilliancy-level moves.
    All values are in centipawns from the mover's POV.
    """

    # How close to engine best the move must be (general)
    max_gap_to_best_cp: int = 60          # ≈ 0.6 pawn

    # For very sharp mate / stalemate rescues we allow a bit more slack
    max_gap_mate_patterns_cp: int = 120   # ≈ 1.2 pawns

    # --- Attack/conversion brilliancy (equal/small edge -> big win) ---
    attack_min_gain_cp: int = 200         # how much the eval must improve
    attack_min_final_cp: int = 300        # final eval must be at least clearly winning

    # --- Defensive brilliancy (lost -> drawable/ok) ---
    defense_lost_threshold_cp: int = -250 # before <= this => clearly worse/lost
    defense_draw_band_cp: int = 80        # after in [-80, +80] => drawable/ok
    defense_min_rescue_gain_cp: int = 350 # gain from before to after

    # --- Stalemate/draw-rescue brilliancy (very lost -> draw) ---
    stalemate_lost_threshold_cp: int = -500   # really lost before
    stalemate_draw_band_cp: int = 60         # after very close to 0.00
    stalemate_min_rescue_gain_cp: int = 600  # huge swing to draw

    # --- Mate-flip brilliancy ---
    min_mate_flip_eval_swing_cp: int = 800    # swing in eval to treat as brilliancy
    min_mate_depth_plies: int = 1             # mate depth must be at least this


@dataclass
class BrilliancyResult:
    """
    Result of the brilliancy-level detector.

    kind can be:
      "attack"
      "defense"
      "stalemate_rescue"
      "mate_flip"
      None
    """
    is_brilliancy: bool
    kind: Optional[str] = None
    # debug info for tuning:
    before_pov: float = 0.0
    after_pov: float = 0.0
    best_pov: Optional[float] = None
    delta_cp: float = 0.0
    gap_to_best_cp: Optional[float] = None
    rescue_gain_cp: Optional[float] = None


def detect_brilliancy_level(
    *,
    eval_before_white: float,
    eval_after_white: float,
    eval_best_white: Optional[float],
    mover_color: str,
    is_sacrifice: bool,
    is_book: bool,
    multipv_rank: Optional[int],
    played_eval_from_pre_white: Optional[float],
    best_mate_in_plies_pre: Optional[int],
    played_mate_in_plies_post: Optional[int],
    mate_flip: bool,
    params: Optional[BrilliancyParams] = None,
) -> BrilliancyResult:
    """
    Detect whether a move is 'brilliancy-level' (regardless of sacrifice).

    This ONLY says: is this conceptually (!! / !) worthy?

    It **does not** decide between Brilliant (!!) vs Great (!).
    That mapping is done separately using is_sacrifice.

    Arguments:
        eval_before_white:
            White POV eval BEFORE move (cp).
        eval_after_white:
            White POV eval AFTER move (cp).
        eval_best_white:
            White POV eval of engine best from PRE, or None.
        mover_color:
            'w' or 'b'
        is_sacrifice:
            True if the move is a real sacrifice.
        is_book:
            True if already detected as Book (we never call Book moves brilliant).
        multipv_rank:
            Engine rank of played move from PRE, or None.
            (Used only as soft info; logic does not depend on it strictly.)
        played_eval_from_pre_white:
            If you have eval of the played move from PRE (White POV), pass it.
            Else None; we fall back to AFTER eval.
        best_mate_in_plies_pre:
            Mate distance (plies) for engine best in PRE, or None.
        played_mate_in_plies_post:
            Mate distance (plies) for the played move in POST, or None.
        mate_flip:
            True if, from White POV, both PRE and POST were mates and the sign flipped
            (i.e., who is mating changed).

    Returns:
        BrilliancyResult
    """
    if params is None:
        params = BrilliancyParams()

    # 0) Never call Book moves brilliant
    if is_book:
        return BrilliancyResult(is_brilliancy=False)

    # Convert evals to mover POV
    before_pov = cp_for_player(eval_before_white, mover_color)
    after_pov  = cp_for_player(eval_after_white,  mover_color)
    best_pov   = cp_for_player(eval_best_white,   mover_color) if eval_best_white is not None else None

    # If we know eval of played move from PRE, use that for gap_to_best; else use AFTER.
    if played_eval_from_pre_white is not None and eval_best_white is not None:
        played_pov_pre = cp_for_player(played_eval_from_pre_white, mover_color)
        gap_to_best = best_pov - played_pov_pre
    elif best_pov is not None:
        gap_to_best = best_pov - after_pov
    else:
        gap_to_best = None

    # Rescue gain if best_pov is known
    rescue_gain = (best_pov - before_pov) if best_pov is not None else None

    delta = after_pov - before_pov
    situation = situation_from_cp(before_pov)

    def make_result(kind: Optional[str]) -> BrilliancyResult:
        return BrilliancyResult(
            is_brilliancy=(kind is not None),
            kind=kind,
            before_pov=before_pov,
            after_pov=after_pov,
            best_pov=best_pov,
            delta_cp=delta,
            gap_to_best_cp=gap_to_best,
            rescue_gain_cp=rescue_gain,
        )

    print("BRILL DEBUG:", {
        "before_pov": before_pov,
        "after_pov": after_pov,
        "best_pov": best_pov,
        "delta_cp": delta,
        "gap_to_best_cp": gap_to_best,
        "situation": situation_from_cp(before_pov),
        "is_sacrifice": is_sacrifice,
        "multipv_rank": multipv_rank,
    })


    # Small helpers
    def near_best_general() -> bool:
        """Near-best constraint for non-mate patterns."""
        if best_pov is None or gap_to_best is None:
            return False
        return abs(gap_to_best) <= params.max_gap_to_best_cp

    def near_best_mate_pattern() -> bool:
        """Looser near-best for mate / stalemate patterns."""
        if best_pov is None or gap_to_best is None:
            return False
        return abs(gap_to_best) <= params.max_gap_mate_patterns_cp

    # -----------------------------------------------------------------------
    # Pattern A: Attack / conversion brilliancy
    # (equal/small edge -> clearly winning)
    # -----------------------------------------------------------------------
    is_attack_candidate = (
        delta >= params.attack_min_gain_cp and
        after_pov >= params.attack_min_final_cp
    )
    if is_attack_candidate and near_best_general():
        return make_result("attack")

    # -----------------------------------------------------------------------
    # Pattern A2: Sacrifice-based brilliancy (already winning -> stay winning)
    # (custom pattern for sacrifice moves that maintain winning advantage)
    # -----------------------------------------------------------------------
    # if is_sacrifice:
    #     # Must be at least clearly better before and after
    #     if before_pov >= 300 and after_pov >= 300:
    #         # Engine should not hate the move (looser gap tolerance for sacrifices)
    #         if best_pov is None or (gap_to_best is not None and abs(gap_to_best) <= 120):
    #             return make_result("attack")

    # -----------------------------------------------------------------------
    # Pattern B: Defensive brilliancy (lost -> drawable/ok)
    # -----------------------------------------------------------------------
    is_lost_or_worse = before_pov <= params.defense_lost_threshold_cp
    is_drawish_after = abs(after_pov) <= params.defense_draw_band_cp
    defense_rescue_gain = after_pov - before_pov

    is_defense_candidate = (
        is_lost_or_worse and
        is_drawish_after and
        defense_rescue_gain >= params.defense_min_rescue_gain_cp
    )

    if is_defense_candidate:
        # Prefer near-best if we know best_pov, otherwise trust the rescue shape.
        if best_pov is None or near_best_general():
            return make_result("defense")

    # -----------------------------------------------------------------------
    # Pattern C: Stalemate / draw-rescue brilliancy
    # (very lost -> near-0 draw; typical "sacrifice for stalemate" scenario)
    # -----------------------------------------------------------------------
    is_very_lost = before_pov <= params.stalemate_lost_threshold_cp
    is_drawish_after_strict = abs(after_pov) <= params.stalemate_draw_band_cp
    stalemate_rescue_gain = after_pov - before_pov

    is_stalemate_candidate = (
        is_very_lost and
        is_drawish_after_strict and
        stalemate_rescue_gain >= params.stalemate_min_rescue_gain_cp
    )

    if is_stalemate_candidate:
        if best_pov is None or near_best_mate_pattern():
            return make_result("stalemate_rescue")

    # -----------------------------------------------------------------------
    # Pattern D: Mate-flip / mate-rescue brilliancy
    #
    # IMPORTANT:
    # - We ONLY treat mate_flip as brilliancy if it is GOOD for the mover.
    # - If it's bad for the mover (you had mate and now opponent has mate),
    #   that should be a Blunder, NOT brilliancy.
    # -----------------------------------------------------------------------
    if mate_flip:
        eval_swing = after_pov - before_pov

        # Good mate flip for mover: big positive swing and final eval > 0
        if eval_swing >= params.min_mate_flip_eval_swing_cp and after_pov > 0:
            return make_result("mate_flip")

        # Bad mate flip for mover (we'll let higher-level logic call this Blunder)
        # Just fall through and return 'no brilliancy' here.
        # (Top-level logic should separately check mate_flip + eval_swing < 0 to force Blunder.)

    # Also treat "killing a short mate against us" as a mate-rescue brilliancy.
    if best_mate_in_plies_pre is not None and best_mate_in_plies_pre <= params.min_mate_depth_plies:
        # There was a very short mate in the best line (against the mover).
        # If after our move the mate disappears or becomes much longer and eval improves a lot,
        # this is a brilliancy-level save.
        if played_mate_in_plies_post is None or played_mate_in_plies_post > best_mate_in_plies_pre + 2:
            if after_pov - before_pov >= params.defense_min_rescue_gain_cp:
                if best_pov is None or near_best_mate_pattern():
                    return make_result("mate_flip")
                
    # -----------------------------------------------------------------------
    # Pattern E: Pure sacrifice brilliancy in a winning position
    #
    # For cases like your Rd8!!:
    # - already clearly better
    # - make a genuine sacrifice
    # - stay clearly better
    # - engine still likes the move (small gap to best)
    # - eval doesn't need to improve much (or at all)
    # -----------------------------------------------------------------------
    if is_sacrifice:
        # Must be at least clearly better before and after
        if before_pov >= 300 and after_pov >= 300:
            # Engine should not hate the move
            if best_pov is None or (gap_to_best is not None and abs(gap_to_best) <= 120):
                return make_result("attack")

    

    # -----------------------------------------------------------------------
    # No brilliancy pattern matched
    # -----------------------------------------------------------------------
    return make_result(None)





# ---------------------------------------------------------------------------
# 6) Final exclamation label helper (Brilliant !! / Great ! / mate-flip Blunder)
# ---------------------------------------------------------------------------

@dataclass
class ExclamParams:
    """
    Parameters for mapping brilliancy + mate-flip into:
        - Brilliant (!!)
        - Great (!)
        - Blunder (for catastrophic mate-flip against mover)
    """
    min_mate_flip_eval_swing_cp: int = 800  # same idea as in BrilliancyParams


def classify_exclam_move(
          
    *,
    eval_before_white: float,
    eval_after_white: float,
    eval_best_white: Optional[float],
    mover_color: str,
    is_sacrifice: bool,
    is_book: bool,
    multipv_rank: Optional[int],
    played_eval_from_pre_white: Optional[float],
    best_mate_in_plies_pre: Optional[int],
    played_mate_in_plies_post: Optional[int],
    mate_flip: bool,
    br_params: Optional[BrilliancyParams] = None,
    ex_params: Optional[ExclamParams] = None,
) -> tuple[Optional[str], BrilliancyResult]:
    """
    Decide if a move deserves a special exclamation label, using all info:

        - Brilliant (!!)  -> brilliancy-level AND is_sacrifice
        - Great (!)       -> brilliancy-level AND NOT is_sacrifice
        - Blunder         -> catastrophic mate-flip against the mover
        - None            -> no special exclam label (fall back to Best/Good/etc.)

    Returns:
        (label, brilliancy_result)

        label can be:
          - "Brilliant"
          - "Great"
          - "Blunder"
          - None
    """
    if ex_params is None:
        ex_params = ExclamParams()

    # First: compute mover POV evals
    before_pov = cp_for_player(eval_before_white, mover_color)
    after_pov  = cp_for_player(eval_after_white,  mover_color)
    eval_swing = after_pov - before_pov

    # 1) Mate-flip catastrophe (Blunder) check:
    #
    # "if suppose the engine says mate in 4 for white and white plays a move
    #  that flips mate in favor of black, then its a blunder"
    #
    # That is exactly: mate_flip == True AND the swing is *bad* for mover.
    if mate_flip and eval_swing <= -ex_params.min_mate_flip_eval_swing_cp:
        # Force 'Blunder' label here; brilliancy-level will be considered False.
        dummy_result = BrilliancyResult(
            is_brilliancy=False,
            kind=None,
            before_pov=before_pov,
            after_pov=after_pov,
            best_pov=None,
            delta_cp=eval_swing,
            gap_to_best_cp=None,
            rescue_gain_cp=None,
        )
        return "Blunder", dummy_result

    # 2) General brilliancy-level detection (attack / defense / stalemate / good mate-flip)
    brill = detect_brilliancy_level(
        eval_before_white=eval_before_white,
        eval_after_white=eval_after_white,
        eval_best_white=eval_best_white,
        mover_color=mover_color,
        is_sacrifice=is_sacrifice,
        is_book=is_book,
        multipv_rank=multipv_rank,
        played_eval_from_pre_white=played_eval_from_pre_white,
        best_mate_in_plies_pre=best_mate_in_plies_pre,
        played_mate_in_plies_post=played_mate_in_plies_post,
        mate_flip=mate_flip,
        params=br_params,
    )

    print("EXCLAM DEBUG:", {
        "is_brilliancy": brill.is_brilliancy,
        "brilliancy_kind": brill.kind,
        "is_sacrifice": is_sacrifice,
        "before_pov": brill.before_pov,
        "after_pov": brill.after_pov,
        "best_pov": brill.best_pov,
        "gap_to_best_cp": brill.gap_to_best_cp,
    })

    if not brill.is_brilliancy:
        return None, brill

    # 3) Map brilliancy-level + sacrifice into Brilliant (!!) vs Great (!)

    # "for Brilliancy (!!), Sacrifice is must,
    #  if the move is Brilliancy level but without sacrifice, then its Great (!)"

    if is_sacrifice:
        print("  → Final label: Brilliant (!! - brilliancy + sacrifice)")
        return "Brilliant", brill
    else:
        print("  → Final label: Great (! - brilliancy without sacrifice)")
        return "Great", brill
