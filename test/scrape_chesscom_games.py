"""
Scrape analyzed games from Chess.com to build test dataset.
Requires: You must have analyzed games on Chess.com with Game Review.

Usage:
    1. Go to Chess.com and analyze some of your games
    2. Run: python scrape_chesscom_games.py <username>
    3. Script will download games and extract annotations
"""

import requests
import json
import chess.pgn
from io import StringIO
from datetime import datetime
from typing import List, Dict
import sys
import time

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def get_monthly_archives(username: str) -> List[str]:
    """Get list of monthly archive URLs for a user."""
    url = f"https://api.chess.com/pub/player/{username}/games/archives"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            archives = response.json().get("archives", [])
            return archives
        elif response.status_code == 404:
            print(f"User '{username}' not found on Chess.com")
            print("Tip: Username is case-sensitive. Try checking your profile URL.")
            return []
        else:
            print(f"API Error: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error fetching archives: {e}")
        return []

def get_games_from_archive(archive_url: str) -> List[Dict]:
    """Get all games from a monthly archive."""
    response = requests.get(archive_url)
    if response.status_code == 200:
        return response.json().get("games", [])
    return []

def parse_pgn_with_annotations(pgn_text: str) -> Dict:
    """Parse PGN and extract positions with annotations."""
    try:
        pgn_io = StringIO(pgn_text)
        game = chess.pgn.read_game(pgn_io)

        if not game:
            return None

        result = {
            "white": game.headers.get("White", ""),
            "black": game.headers.get("Black", ""),
            "date": game.headers.get("Date", ""),
            "url": game.headers.get("Link", ""),
            "positions": []
        }

        board = game.board()
        node = game
        move_number = 1

        while node.variations:
            node = node.variation(0)
            move = node.move

            # Get FEN before the move
            fen_before = board.fen()

            # Get move in UCI
            uci_move = move.uci()

            # Check for NAGs (Numeric Annotation Glyphs)
            # Chess.com uses these for move quality
            nags = node.nags
            comment = node.comment

            label = None
            if nags:
                # $1 = Good move (!)
                # $2 = Mistake (?)
                # $3 = Brilliant (!!)
                # $4 = Blunder (??)
                # $5 = Interesting (!?)
                # $6 = Dubious (?!)
                if 3 in nags or "!!" in comment:
                    label = "Brilliant"
                elif 4 in nags or "??" in comment:
                    label = "Blunder"
                elif 2 in nags or "?" in comment and "??" not in comment:
                    label = "Mistake"
                elif 1 in nags or "!" in comment and "!!" not in comment:
                    label = "Good"
                elif 6 in nags or "?!" in comment:
                    label = "Inaccuracy"
                elif 5 in nags or "!?" in comment:
                    label = "Interesting"

            # Also check comment text for Chess.com annotations
            if not label:
                comment_lower = comment.lower()
                if "brilliant" in comment_lower:
                    label = "Brilliant"
                elif "great" in comment_lower:
                    label = "Great"
                elif "best" in comment_lower:
                    label = "Best"
                elif "excellent" in comment_lower:
                    label = "Excellent"
                elif "good" in comment_lower:
                    label = "Good"
                elif "blunder" in comment_lower:
                    label = "Blunder"
                elif "mistake" in comment_lower:
                    label = "Mistake"
                elif "inaccuracy" in comment_lower or "inaccurate" in comment_lower:
                    label = "Inaccuracy"

            if label:
                side = "White" if board.turn else "Black"
                result["positions"].append({
                    "fen": fen_before,
                    "move": uci_move,
                    "label": label,
                    "move_number": move_number,
                    "side": side,
                    "comment": comment[:100] if comment else ""  # First 100 chars
                })

            board.push(move)
            if not board.turn:  # After black's move
                move_number += 1

        return result if result["positions"] else None

    except Exception as e:
        print(f"Error parsing PGN: {e}")
        return None

def collect_annotated_games(username: str, max_games: int = 100) -> List[Dict]:
    """Collect annotated games from Chess.com."""
    print(f"Fetching game archives for {username}...")
    archives = get_monthly_archives(username)

    if not archives:
        print(f"No games found for user: {username}")
        return []

    print(f"Found {len(archives)} monthly archives")

    all_positions = []
    games_processed = 0

    # Process most recent archives first
    for archive_url in reversed(archives[-6:]):  # Last 6 months
        if games_processed >= max_games:
            break

        month = archive_url.split("/")[-2:]
        print(f"\nProcessing {'/'.join(month)}...")

        games = get_games_from_archive(archive_url)
        print(f"  Found {len(games)} games")

        for game_data in games:
            if games_processed >= max_games:
                break

            pgn = game_data.get("pgn", "")
            if not pgn:
                continue

            parsed = parse_pgn_with_annotations(pgn)
            if parsed and parsed["positions"]:
                print(f"  ✓ Game with {len(parsed['positions'])} annotated moves")
                for pos in parsed["positions"]:
                    pos["game_url"] = game_data.get("url", "")
                    pos["game_date"] = parsed["date"]
                    all_positions.append(pos)
                games_processed += 1

            time.sleep(0.1)  # Be nice to Chess.com API

    return all_positions

def format_as_test_data(positions: List[Dict]) -> List[Dict]:
    """Format collected positions as test_data.json format."""
    test_cases = []

    for i, pos in enumerate(positions):
        test_cases.append({
            "name": f"Game {i+1}: {pos['side']} move {pos['move_number']} ({pos['move']})",
            "fen": pos["fen"],
            "move": pos["move"],
            "expected_label": pos["label"],
            "source": f"chess.com - {pos.get('game_url', '')}",
            "description": f"{pos.get('comment', '')} - from real game on {pos.get('game_date', '')}"
        })

    return test_cases

def main():
    if len(sys.argv) < 2:
        print("Usage: python scrape_chesscom_games.py <chess.com_username> [max_games]")
        print("\nExample: python scrape_chesscom_games.py MagnusCarlsen 50")
        print("\nNote: Only games with annotations (from Game Review) will be collected.")
        sys.exit(1)

    username = sys.argv[1]
    max_games = int(sys.argv[2]) if len(sys.argv) > 2 else 100

    print("="*80)
    print("CHESS.COM GAME SCRAPER - Real Dataset Builder")
    print("="*80)

    # Collect positions
    positions = collect_annotated_games(username, max_games)

    if not positions:
        print("\n❌ No annotated positions found!")
        print("\nTips:")
        print("  1. Make sure you have games on Chess.com")
        print("  2. Run 'Game Review' on some games to get annotations")
        print("  3. Try a different username or check spelling")
        sys.exit(1)

    # Group by label
    by_label = {}
    for pos in positions:
        label = pos["label"]
        by_label[label] = by_label.get(label, 0) + 1

    print(f"\n✓ Collected {len(positions)} annotated positions:")
    for label, count in sorted(by_label.items(), key=lambda x: -x[1]):
        print(f"  {label}: {count}")

    # Format and save
    test_data = format_as_test_data(positions)

    output_file = f"test_data_real_{username}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved {len(test_data)} test cases to: {output_file}")
    print(f"\nNext steps:")
    print(f"  1. Review the file: {output_file}")
    print(f"  2. Rename to test_data.json (or merge with existing)")
    print(f"  3. Run validation: python validate_brilliance.py")

    # Show sample
    if test_data:
        print(f"\nSample test case:")
        print(json.dumps(test_data[0], indent=2))

if __name__ == "__main__":
    main()
