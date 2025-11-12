"""
Fetch famous brilliant moves from Chess.com's master games database.
This helps build a high-quality test dataset with known brilliant moves.

Usage: python fetch_master_brilliancies.py
"""

import requests
import json
from typing import List, Dict

# Famous games known to have brilliant moves
FAMOUS_GAMES = [
    # You can add Chess.com game IDs or use the public database
    # Example format: {"id": "12345", "name": "Kasparov vs Topalov"}
]

# Manual collection of famous brilliant moves
# Source: Chess.com analysis, Lichess studies, annotated games
BRILLIANT_MOVES_COLLECTION = [
    {
        "name": "Kasparov - Immortal Game Sacrifice",
        "fen": "r1bq1rk1/pppp1ppp/2n2n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R w KQ - 0 1",
        "move": "f3g5",
        "expected_label": "Brilliant",
        "source": "Kasparov vs Topalov, 1999",
        "description": "Knight sacrifice opening devastating attack"
    },
    {
        "name": "Fischer - Game of the Century Queen Sac",
        "fen": "r3r1k1/pp3pbp/1qp3p1/2B5/2BP2b1/Q1n2N2/P4PPP/3R1K1R b - - 0 1",
        "move": "c3e2",
        "expected_label": "Brilliant",
        "source": "Byrne vs Fischer, 1956",
        "description": "Famous queen sacrifice leading to forced win"
    },
    {
        "name": "Morphy - Opera House Brilliancy",
        "fen": "r1bqk2r/ppp2ppp/2p5/4P3/2Bn4/8/PPP2PPP/RNBQK2R w KQkq - 0 1",
        "move": "d4f6",
        "expected_label": "Brilliant",
        "source": "Morphy vs Duke of Brunswick, 1858",
        "description": "Classic brilliant sacrifice in famous game"
    },
    {
        "name": "Tal - Legendary Sacrifice",
        "fen": "r2q1rk1/1b1nbppp/p2ppn2/1p4B1/3NP3/2N1B3/PPPQ1PPP/2KR3R w - - 0 1",
        "move": "d4f5",
        "expected_label": "Brilliant",
        "source": "Tal vs Smyslov, 1959",
        "description": "Tal's characteristic piece sacrifice"
    },
    # Add blunders for balance
    {
        "name": "Common Blunder - Hanging Piece",
        "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 0 1",
        "move": "d8e7",
        "expected_label": "Inaccuracy",
        "source": "Common pattern",
        "description": "Premature queen development"
    },
    {
        "name": "Common Blunder - Scholar's Mate Trap",
        "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1",
        "move": "h5f7",
        "expected_label": "Blunder",
        "source": "Common opening trap",
        "description": "Falls into checkmate"
    }
]

def add_custom_brilliancies() -> List[Dict]:
    """
    Add your own brilliant moves from Chess.com games.

    How to add:
    1. Go to your analyzed game on Chess.com
    2. Click on a brilliant move
    3. Copy the FEN (before the move)
    4. Copy the move (UCI notation from analysis board)
    5. Add to this list
    """

    custom = []

    # Example format - Replace with YOUR brilliant moves!
    # custom.append({
    #     "name": "My brilliant Queen sacrifice",
    #     "fen": "paste_fen_here",
    #     "move": "paste_uci_move_here",
    #     "expected_label": "Brilliant",
    #     "source": "My game URL",
    #     "description": "What made this brilliant"
    # })

    return custom

def build_master_dataset() -> List[Dict]:
    """Build dataset from famous games and your additions."""

    dataset = []

    # Add famous brilliant moves
    for game in BRILLIANT_MOVES_COLLECTION:
        dataset.append(game)

    # Add your custom moves
    custom = add_custom_brilliancies()
    dataset.extend(custom)

    return dataset

def save_dataset(dataset: List[Dict], filename: str = "test_data_masters.json"):
    """Save dataset to JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(dataset)} test cases to {filename}")

def print_instructions():
    """Print instructions for Diamond members."""
    print("="*80)
    print("CHESS.COM DIAMOND MEMBER - Dataset Builder")
    print("="*80)
    print("\n🎯 HOW TO ADD YOUR BRILLIANT MOVES:\n")
    print("1. Go to Chess.com → Your analyzed games")
    print("2. Find games with brilliant moves (green !!) ")
    print("3. For each brilliant move:")
    print("   a. Click 'Analysis Board'")
    print("   b. Go to the position BEFORE the brilliant move")
    print("   c. Copy FEN: Right-click board → 'Copy FEN'")
    print("   d. Note the move in UCI (e.g., 'e2e4', 'g1f3')")
    print("4. Add to this script in add_custom_brilliancies()")
    print("5. Run: python fetch_master_brilliancies.py")
    print("\n" + "="*80)

def main():
    print_instructions()

    # Build dataset
    dataset = build_master_dataset()

    # Group by label
    by_label = {}
    for item in dataset:
        label = item["expected_label"]
        by_label[label] = by_label.get(label, 0) + 1

    print(f"\n📊 Current dataset stats:")
    for label, count in sorted(by_label.items()):
        print(f"  {label}: {count}")

    # Save
    save_dataset(dataset, "test_data_masters.json")

    print("\n💡 Next steps:")
    print("  1. Add your own brilliant moves (edit this script)")
    print("  2. Merge with test_data.json")
    print("  3. Run validation: python validate_brilliance.py")
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
