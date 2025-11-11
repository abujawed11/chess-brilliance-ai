"""
Load trained model and predict label for a single feature row (placeholder).
In your app you'll generate these features at runtime from quick engine probes.
"""
import json
import sys
from xgboost import XGBClassifier

def main():
    if len(sys.argv) < 3:
        print("Usage: python student/predict_move_type.py model.json '{\"depth\":18,\"pre_top_gap\":220,\"played_rank\":1,\"cp_loss\":-10,\"is_sac\":1,\"robust\":1}'")
        return
    model_path = sys.argv[1]
    payload = json.loads(sys.argv[2])
    model = XGBClassifier()
    model.load_model(model_path)
    X = [[payload["depth"], payload["pre_top_gap"], payload["played_rank"], payload["cp_loss"], payload["is_sac"], payload["robust"]]]
    pred = model.predict(X)[0]
    print(pred)

if __name__ == "__main__":
    main()
