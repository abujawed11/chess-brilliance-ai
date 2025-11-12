"""
Validation script to test brilliant move detection accuracy.
Tests against ground truth data and generates metrics.
"""

import json
import requests
from collections import defaultdict
from typing import Dict, List
import sys
import os

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

API_URL = "http://localhost:5000/evaluate"

def load_test_data(filepath: str) -> List[Dict]:
    """Load test cases from JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)

def evaluate_move(fen: str, move: str, depth: int = 18, multipv: int = 5) -> Dict:
    """Call the API to evaluate a move."""
    try:
        response = requests.post(API_URL, json={
            "fen": fen,
            "move": move,
            "depth": depth,
            "multipv": multipv
        }, timeout=60)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def calculate_metrics(results: List[Dict]) -> Dict:
    """Calculate precision, recall, F1 for each label."""
    # Initialize counters
    label_stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "tn": 0})

    all_labels = set()
    for r in results:
        all_labels.add(r["expected"])
        all_labels.add(r["predicted"])

    # Calculate confusion for each label
    for label in all_labels:
        for r in results:
            expected = r["expected"]
            predicted = r["predicted"]

            if expected == label and predicted == label:
                label_stats[label]["tp"] += 1  # True Positive
            elif expected != label and predicted == label:
                label_stats[label]["fp"] += 1  # False Positive
            elif expected == label and predicted != label:
                label_stats[label]["fn"] += 1  # False Negative
            else:
                label_stats[label]["tn"] += 1  # True Negative

    # Calculate metrics
    metrics = {}
    for label, stats in label_stats.items():
        tp = stats["tp"]
        fp = stats["fp"]
        fn = stats["fn"]

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        metrics[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": tp + fn  # Number of actual occurrences
        }

    # Overall accuracy
    total_correct = sum(1 for r in results if r["expected"] == r["predicted"])
    accuracy = total_correct / len(results) if results else 0

    return {
        "accuracy": accuracy,
        "per_label": metrics,
        "total_tests": len(results)
    }

def print_confusion_matrix(results: List[Dict]):
    """Print confusion matrix."""
    # Get all unique labels
    all_labels = sorted(set(r["expected"] for r in results) | set(r["predicted"] for r in results))

    # Build confusion matrix
    matrix = defaultdict(lambda: defaultdict(int))
    for r in results:
        matrix[r["expected"]][r["predicted"]] += 1

    print("\n" + "="*80)
    print("CONFUSION MATRIX")
    print("="*80)
    print(f"\n{'Actual \\ Predicted':<20}", end="")
    for label in all_labels:
        print(f"{label:<15}", end="")
    print()
    print("-" * 80)

    for actual in all_labels:
        print(f"{actual:<20}", end="")
        for predicted in all_labels:
            count = matrix[actual][predicted]
            print(f"{count:<15}", end="")
        print()

def print_detailed_results(results: List[Dict]):
    """Print detailed results for each test case."""
    print("\n" + "="*80)
    print("DETAILED TEST RESULTS")
    print("="*80)

    # Separate by result type
    correct = [r for r in results if r["expected"] == r["predicted"]]
    incorrect = [r for r in results if r["expected"] != r["predicted"]]
    errors = [r for r in results if r.get("error")]

    print(f"\n✅ CORRECT: {len(correct)}/{len(results)}")
    for r in correct:
        print(f"  • {r['name']}: {r['predicted']} ✓")

    if incorrect:
        print(f"\n❌ INCORRECT: {len(incorrect)}/{len(results)}")
        for r in incorrect:
            print(f"  • {r['name']}")
            print(f"    Expected: {r['expected']}, Got: {r['predicted']}")
            print(f"    Eval: {r.get('eval_before', '?')} → {r.get('eval_after', '?')}")
            print(f"    Rank: {r.get('multipv_rank', '?')}, Sacrifice: {r.get('is_sacrifice', '?')}")
            print(f"    Description: {r.get('description', '')}")

    if errors:
        print(f"\n⚠️  ERRORS: {len(errors)}/{len(results)}")
        for r in errors:
            print(f"  • {r['name']}: {r.get('error', 'Unknown error')}")

def print_metrics(metrics: Dict):
    """Print metrics in a formatted table."""
    print("\n" + "="*80)
    print("METRICS SUMMARY")
    print("="*80)
    print(f"\nOverall Accuracy: {metrics['accuracy']:.2%} ({metrics['total_tests']} tests)")

    print(f"\n{'Label':<15} {'Precision':<12} {'Recall':<12} {'F1-Score':<12} {'Support':<10}")
    print("-" * 80)

    for label, stats in sorted(metrics['per_label'].items()):
        print(f"{label:<15} {stats['precision']:.2%}       {stats['recall']:.2%}      {stats['f1']:.2%}      {stats['support']}")

def identify_false_positives(results: List[Dict]) -> List[Dict]:
    """Identify false positive brilliancies (biggest concern)."""
    return [r for r in results
            if r["predicted"] == "Brilliant" and r["expected"] != "Brilliant"]

def main():
    print("="*80)
    print("BRILLIANT MOVE VALIDATION SYSTEM")
    print("="*80)

    # Load test data - resolve path relative to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    test_file = os.path.join(script_dir, "test_data.json")

    try:
        test_cases = load_test_data(test_file)
        print(f"\n📋 Loaded {len(test_cases)} test cases from {test_file}")
    except Exception as e:
        print(f"❌ Error loading test data: {e}")
        print(f"   Looking for: {test_file}")
        sys.exit(1)

    # Run tests
    print("\n🔄 Running evaluations...")
    results = []

    for i, test in enumerate(test_cases, 1):
        print(f"  [{i}/{len(test_cases)}] Testing: {test['name']}...", end=" ")

        response = evaluate_move(test["fen"], test["move"])

        if "error" in response:
            print(f"❌ Error")
            results.append({
                "name": test["name"],
                "expected": test["expected_label"],
                "predicted": "ERROR",
                "error": response["error"],
                "description": test.get("description", "")
            })
        else:
            predicted_label = response.get("label", "UNKNOWN")
            is_correct = predicted_label == test["expected_label"]
            status = "✓" if is_correct else "✗"

            print(f"{status} (Expected: {test['expected_label']}, Got: {predicted_label})")

            results.append({
                "name": test["name"],
                "expected": test["expected_label"],
                "predicted": predicted_label,
                "eval_before": response.get("eval_before"),
                "eval_after": response.get("eval_after"),
                "multipv_rank": response.get("multipv_rank"),
                "is_sacrifice": response.get("is_sacrifice"),
                "description": test.get("description", "")
            })

    # Calculate and display metrics
    metrics = calculate_metrics(results)

    print_detailed_results(results)
    print_confusion_matrix(results)
    print_metrics(metrics)

    # Check for false positive brilliancies
    false_brilliants = identify_false_positives(results)
    if false_brilliants:
        print("\n" + "="*80)
        print("⚠️  FALSE POSITIVE BRILLIANCIES (Critical Issues!)")
        print("="*80)
        for r in false_brilliants:
            print(f"\n❌ {r['name']}")
            print(f"   Expected: {r['expected']}, Got: Brilliant")
            print(f"   Eval: {r.get('eval_before')} → {r.get('eval_after')}")
            print(f"   This should NOT be brilliant!")
    else:
        print("\n✅ No false positive brilliancies detected!")

    print("\n" + "="*80)
    print(f"✓ Validation complete! Accuracy: {metrics['accuracy']:.2%}")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
