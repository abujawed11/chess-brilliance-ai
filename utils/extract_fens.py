"""
Utility: filter/sample positions for labeling (e.g., cap max per game).
Writes data/samples/positions_sample.parquet
"""
import os
import pandas as pd

SRC = os.path.join("data", "samples", "positions.parquet")
OUT = os.path.join("data", "samples", "positions_sample.parquet")

def main():
    df = pd.read_parquet(SRC)
    # simple sampling: take every Nth ply to start
    sample = df[df["ply_index"] % 2 == 0].copy()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    sample.to_parquet(OUT, index=False)
    print(f"Sampled {len(sample)} / {len(df)} → {OUT}")

if __name__ == "__main__":
    main()
