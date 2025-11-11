"""
Threshold-based labels; tune later.
Input: dict with keys:
 - cp_loss (float, positive = worse for player who moved)
 - pre_top_gap (float, PV#1 - PV#2 cp gap before move)
 - played_rank (int, 1 = best line before move)
 - is_sac (bool)
 - depth (int)
 - robust (bool)  # post-move still OK at +4 depth
Return: label string.
"""
def label_move(x: dict) -> str:
    cp_loss = x.get("cp_loss", 0.0)
    pre_gap = x.get("pre_top_gap", 0.0)
    rank = x.get("played_rank", 99)
    is_sac = x.get("is_sac", False)
    depth = x.get("depth", 0)
    robust = x.get("robust", False)

    # Easy buckets first
    if cp_loss >= 300: return "blunder"
    if cp_loss >= 120: return "mistake"
    if cp_loss >= 50:  return "inaccuracy"

    # Brilliant (strict): only-move or sound sacrifice discovered deep & robust
    if rank == 1 and robust and depth >= 20 and (pre_gap >= 200 or is_sac):
        return "brilliant"

    # Best / Excellent / Good
    if rank == 1: return "best"
    if rank <= 2: return "excellent"
    return "good"
