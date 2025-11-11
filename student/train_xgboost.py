"""
Train an XGBoost baseline on teacher labels.
Writes student/brilliance_model.json
"""
import os
import pandas as pd
from xgboost import XGBClassifier

SRC = os.path.join("data", "labeled_features", "teacher_labels.parquet")
OUT = os.path.join("student", "brilliance_model.json")

FEATS = ["depth","pre_top_gap","played_rank","cp_loss","is_sac","robust"]
LABEL = "label"

def main():
    df = pd.read_parquet(SRC)
    # simple subset: drop rare labels if too few
    X = df[FEATS].astype(float)
    y = df[LABEL].astype("category")

    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="mlogloss"
    )
    model.fit(X, y)
    model.save_model(OUT)
    print(f"Model saved → {OUT}")

if __name__ == "__main__":
    main()
