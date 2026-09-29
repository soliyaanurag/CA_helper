"""Helpers shared by the evaluation scripts (eval/<name>/evaluate.py).

BACKEND                 put on sys.path, so a script can `import app...` like the tests
app_context()           the Flask app (reads the root .env) for scripts that need the database
percent(hits, total)    "87.5% (7/8)"
print_table(headers, rows)   a plain text table for the report
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def app_context():
    """An app context of the development app (the database and GEMINI_API_KEY from .env)."""
    from app import create_app

    return create_app().app_context()


def percent(hits: int, total: int) -> str:
    if total == 0:
        return "-"
    return f"{100 * hits / total:.1f}% ({hits}/{total})"


def print_table(headers: list[str], rows: list[list]) -> None:
    """Print rows under headers, each column as wide as its longest cell."""
    widths = []
    for column, header in enumerate(headers):
        width = len(header)
        for row in rows:
            width = max(width, len(str(row[column])))
        widths.append(width)

    def line(cells) -> str:
        return "  ".join(str(cell).ljust(width) for cell, width in zip(cells, widths, strict=True))

    print(line(headers))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print(line(row))
    print()
