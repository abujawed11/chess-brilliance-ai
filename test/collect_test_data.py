"""
Helper script to collect test data from Chess.com games.
Downloads games and extracts moves with annotations (brilliant, blunder, etc.).

Usage:
    python collect_test_data.py <chess.com_username>
"""

import requests
import json
import chess
import chess.pgn
from io import StringIO
import sys
from typing import List, Dict

def get_user_games(username: str, year: int, month: int) -> List[str]:
    """Fetch user's games for a specific month from Chess.com API."""
    url = f"https://api.chess.com/pub/player/{username}/games/{year}/{month:02d}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get("games", [])
    return []

def extract_annotated_moves(pgn_text: str) -> List[Dict]:
    """Extract moves with special annotations (brilliant, blunder, etc.) from PGN."""
    pgn = StringIO(pgn_text)
    game = chess.pgn.read_game(pgn)

    if not game:
        return []

    annotated_moves = []
    board = game.board()

    for move_num, move in enumerate(game.mainline_moves()):
        node = game.mainline()
        for _ in range(move_num + 1):
            node = node.next()

        # Check for annotations in comments
        comment = node.comment if node else ""

        # Chess.com uses these annotations in PGN
        label = None
        if "[%csl" in comment or "brilliant" in comment.lower():
            label = "Brilliant"
        elif "blunder" in comment.lower() or "??" in comment:
            label = "Blunder"
        elif "mistake" in comment.lower() or "?" in comment:
            label = "Mistake"
        elif "good" in comment.lower() or "!" in comment:
            label = "Good"
        elif "best" in comment.lower():
            label = "Best"

        if label:
            annotated_moves.append({
                "fen": board.fen(),
                "move": move.uci(),
                "label": label,
                "move_number": (move_num // 2) + 1,
                "side": "White" if board.turn else "Black"
            })

        board.push(move)

    return annotated_moves

def collect_annotated_games(username: str, num_months: int = 3) -> List[Dict]:
    """Collect annotated moves from user's recent games."""
    import datetime
    now = datetime.datetime.now()

    all_moves = []

    print(f"Fetching games for user: {username}")

    for i in range(num_months):
        month = now.month - i
        year = now.year
        if month <= 0:
            month += 12
            year -= 1

        print(f"  Checking {year}-{month:02d}...", end=" ")
        games = get_user_games(username, year, month)
        print(f"{len(games)} games found")

        for game in games:
            pgn = game.get("pgn", "")
            if pgn:
                moves = extract_annotated_moves(pgn)
                for move in moves:
                    move["game_url"] = game.get("url", "")
                    move["source"] = "chess.com"
                all_moves.extend(moves)

    return all_moves

def main():
    if len(sys.argv) < 2:
        print("Usage: python collect_test_data.py <chess.com_username>")
        print("\nExample: python collect_test_data.py MagnusCarlsen")
        sys.exit(1)

    username = sys.argv[1]

    print("="*60)
    print("CHESS.COM TEST DATA COLLECTOR")
    print("="*60)

    # Collect annotated moves
    moves = collect_annotated_games(username, num_months=3)

    if not moves:
        print("\n❌ No annotated moves found!")
        print("Note: Chess.com only includes annotations in Game Review.")
        print("Try analyzing some games first on Chess.com.")
        sys.exit(1)

    # Group by label
    by_label = {}
    for move in moves:
        label = move["label"]
        if label not in by_label:
            by_label[label] = []
        by_label[label].append(move)

    print(f"\n✓ Found {len(moves)} annotated moves:")
    for label, items in sorted(by_label.items()):
        print(f"  {label}: {len(items)}")

    # Format for test_data.json
    test_cases = []
    for move in moves:
        test_cases.append({
            "name": f"{move['side']} move {move['move_number']} - {move['move']}",
            "fen": move["fen"],
            "move": move["move"],
            "expected_label": move["label"],
            "source": f"chess.com - {move.get('game_url', '')}",
            "description": f"From actual game analysis"
        })

    # Save to file
    output_file = f"test_data_collected_{username}.json"
    with open(output_file, 'w') as f:
        json.dump(test_cases, f, indent=2)

    print(f"\n✓ Saved {len(test_cases)} test cases to: {output_file}")
    print(f"\nYou can now merge this with test_data.json or test directly:")
    print(f"  python validate_brilliance.py")

if __name__ == "__main__":
    main()
