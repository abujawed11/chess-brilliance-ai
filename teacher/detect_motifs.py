"""
Very light motif flags; expand later.
Given pre/post multipv and material delta, return booleans like is_sac, only_move, missed_win.
"""
def detect_motifs(*, material_delta_cp: int, pre_top_gap: float) -> dict:
    return {
        "is_sac": material_delta_cp <= -300,  # gave ≥ minor piece
        "only_move": pre_top_gap >= 200,
        "missed_win": False,  # set later if you implement deeper checks
    }
