"""
Train an XGBoost baseline on teacher labels.
Writes:
 - student/brilliance_model.json
 - student/label_encoder.pkl
"""
import os
import pandas as pd
from xgboost import XGBClassifier
from sklearn.preprocessing import LabelEncoder
import joblib

SRC = os.path.join("data", "labeled_features", "teacher_labels.parquet")
OUT_MODEL = os.path.join("student", "brilliance_model.json")
OUT_ENCODER = os.path.join("student", "label_encoder.pkl")

FEATS = ["depth", "pre_top_gap", "played_rank", "cp_loss", "is_sac", "robust"]
LABEL = "label"


def main():
    print("📘 Loading teacher labels...")
    df = pd.read_parquet(SRC)
    print(f"Loaded {len(df)} samples")

    # Filter + prepare data
    X = df[FEATS].astype(float)
    y = df[LABEL].astype(str)

    # Encode string labels -> numeric
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    # Save encoder for later decoding
    joblib.dump(le, OUT_ENCODER)
    print(f"🧩 Saved label encoder → {OUT_ENCODER}")
    print(f"Classes: {list(le.classes_)}")

    # Train model
    print("🚀 Training XGBoost model...")
    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="mlogloss",
        random_state=42
    )

    model.fit(X, y_encoded)
    model.save_model(OUT_MODEL)
    print(f"✅ Model saved → {OUT_MODEL}")


if __name__ == "__main__":
    main()
