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

# ---------------------------------------------------------------------------
# 1) Helpers: convert to player POV, bucket the situation
# ---------------------------------------------------------------------------

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

