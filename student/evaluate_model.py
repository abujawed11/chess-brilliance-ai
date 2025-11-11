"""
Quick evaluation: train/test split accuracy with proper label encoding.
Prints classification report and confusion matrix.
"""
import os
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import LabelEncoder

SRC = os.path.join("data", "labeled_features", "teacher_labels.parquet")
FEATS = ["depth", "pre_top_gap", "played_rank", "cp_loss", "is_sac", "robust"]
LABEL = "label"

def main():
    print("📘 Loading labeled dataset…")
    df = pd.read_parquet(SRC)
    X = df[FEATS].astype(float)
    y = df[LABEL].astype(str)

    # Encode labels -> integers
    le = LabelEncoder()
    y_enc = le.fit_transform(y)
    class_names = list(le.classes_)
    print(f"Classes: {class_names}")

    # Split
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y_enc, test_size=0.2, random_state=42, stratify=y_enc
    )

    # Train a fresh model for evaluation
    print("🚀 Training model for evaluation…")
    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="mlogloss",
        random_state=42,
    )
    model.fit(X_tr, y_tr)

    # Predict
    y_pred = model.predict(X_te)

    # Reports
    print("\n📊 Classification report")
    print(classification_report(y_te, y_pred, target_names=class_names, digits=3))

    cm = confusion_matrix(y_te, y_pred, labels=np.arange(len(class_names)))
    cm_norm = cm.astype(float) / cm.sum(axis=1, keepdims=True)
    print("\n🧮 Confusion matrix (rows=true, cols=pred)")
    print(cm)
    print("\n🧮 Confusion matrix (normalized)")
    with np.printoptions(precision=3, suppress=True):
        print(cm_norm)

if __name__ == "__main__":
    main()
