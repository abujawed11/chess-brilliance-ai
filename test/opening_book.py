# opening_book.py

import chess

# ---------------------------------------------------------------------------
# Define a small set of popular openings as SAN move sequences.
# You can extend this list anytime.
# Each entry is: (name, "moves in SAN...")
# ---------------------------------------------------------------------------

OPENING_LINES = [
    # 1.e4 e5 openings
    ("Ruy Lopez (Morphy Defense)",
     "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7"),

    ("Italian Game (Giuoco Piano)",
     "e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6 d3"),

    ("Scotch Game",
     "e4 e5 Nf3 Nc6 d4 exd4 Nxd4"),

    ("Four Knights Game",
     "e4 e5 Nf3 Nc6 Nc3 Nf6 Bb5"),

    # 1.e4 c5 Sicilian
    ("Sicilian Defense (Open Sicilian)",
     "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6"),

    ("Sicilian Najdorf idea",
     "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6 Be3 e5"),

    # 1.e4 e6 French
    ("French Defense (Advance)",
     "e4 e6 d4 d5 e5 c5 c3 Nc6 Nf3"),

    ("French Defense (Tarrasch)",
     "e4 e6 d4 d5 Nd2 c5 exd5 exd5 Ngf3"),

    # 1.e4 c6 Caro-Kann
    ("Caro-Kann (Advance)",
     "e4 c6 d4 d5 e5 Bf5 Nf3 e6 Be2"),

    ("Caro-Kann (Classical)",
     "e4 c6 d4 d5 Nc3 dxe5 Nxe4 Bf5 Ng3 Bg6"),

    # 1.d4 d5 Queen's Gambit
    ("Queen's Gambit Declined",
     "d4 d5 c4 e6 Nc3 Nf6 Bg5 Be7 e3 O-O Nf3"),

    ("Queen's Gambit Accepted",
     "d4 d5 c4 dxc4 Nf3 Nf6 e3 e6 Bxc4 c5"),

    # 1.d4 Nf6 Indian systems
    ("King's Indian Defense",
     "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O"),

    ("Nimzo-Indian Defense",
     "d4 Nf6 c4 e6 Nc3 Bb4 e3 O-O Bd3 d5"),

    # 1.c4 English
    ("English Opening",
     "c4 e5 Nc3 Nf6 g3 d5 cxd5 Nxd5 Bg2 Nb6 Nf3"),

    # Slav / Semi-Slav
    ("Slav Defense",
     "d4 d5 c4 c6 Nf3 Nf6 Nc3 dxc4 a4 Bf5"),

    ("Semi-Slav",
     "d4 d5 c4 c6 Nf3 Nf6 Nc3 e6 e3 Nbd7 Bd3 dxc4"),
]


# ---------------------------------------------------------------------------
# Build a dict: (fen_before, move_uci) -> True
# ---------------------------------------------------------------------------

def build_opening_book():
    """
    Returns:
        dict[(fen_before, uci_move)] -> True
    """
    book = {}

    for name, san_line in OPENING_LINES:
        board = chess.Board()  # start from initial position
        moves = san_line.split()

        for san in moves:
            fen_before = board.fen()
            try:
                move = board.parse_san(san)
            except ValueError:
                # In case of a typo in SAN, skip the rest of this line
                print(f"[OPENING_BOOK] Failed to parse SAN '{san}' in line '{name}'")
                break

            uci_move = move.uci()
            # Store this as a book move from this position
            book[(fen_before, uci_move)] = True

            # Push the move and continue
            board.push(move)

    return book


# Build once at import time
BOOK_ENTRIES = build_opening_book()


def is_book_move(fen_before: str, move_uci: str) -> bool:
    """
    Check if (fen_before, move_uci) is in our small opening book.
    """
    return BOOK_ENTRIES.get((fen_before, move_uci), False)


def has_any_book_move(fen_before: str) -> bool:
    """
    Check if there is at least one book move from this position in our tiny DB.
    Useful if you ever want to show "book moves available" instead of
    just checking the user's move.
    """
    for (fen, uci), _ in BOOK_ENTRIES.items():
        if fen == fen_before:
            return True
    return False
