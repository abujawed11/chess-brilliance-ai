"""
Quick evaluation: train/test split accuracy.
"""
import os
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from xgboost import XGBClassifier

SRC = os.path.join("data", "labeled_features", "teacher_labels.parquet")
FEATS = ["depth","pre_top_gap","played_rank","cp_loss","is_sac","robust"]
LABEL = "label"

def main():
    df = pd.read_parquet(SRC)
    X = df[FEATS].astype(float)
    y = df[LABEL].astype("category")
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    model = XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.05, eval_metric="mlogloss")
    model.fit(X_tr, y_tr)
    y_pred = model.predict(X_te)
    print(classification_report(y_te, y_pred))

if __name__ == "__main__":
    main()
