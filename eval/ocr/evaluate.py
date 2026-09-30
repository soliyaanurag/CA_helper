"""OCR evaluation: how many labelled fields our local OCR reads correctly.

For each file in samples/, the same code as an upload runs: app/utils/ocr.py reads the
text, then app/utils/document_text.py finds the fields. A field counts as correct when it
equals labels.csv (form, month, quarter and financial_year: when it is among those found).
Needs no database and no Gemini. Run from the repo root:
    conda run -n ca-helper python eval/ocr/evaluate.py
"""

import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import percent, print_table  # noqa: E402

from app import ocr
from app.ocr import read_proof_fields, read_registration

HERE = Path(__file__).parent
# The samples' dates are in 2026; a later "today" keeps every one of them valid.
TODAY = date(2026, 12, 31)
FORMATS = {"pdf": "text PDF", "png": "photo (PNG)"}


def _format_of(path: Path, data: bytes) -> str:
    """What kind of file it is: text PDF, scanned PDF or photo (PNG)."""
    if path.suffix == ".pdf" and b"/Image" in data:
        return "scanned PDF"
    return FORMATS[path.suffix[1:]]


def _found(text: str) -> dict:
    """Every field we evaluate, as strings or lists of strings."""
    proof = read_proof_fields(text, TODAY)
    registration = read_registration(text)
    found = {
        "ack_number": proof["acknowledgement_no"],
        "filing_date": proof["filing_date"],
        "form": proof["form_codes"],
        "month": [str(month) for month in proof["months"]],
        "quarter": [str(quarter) for quarter in proof["quarters"]],
        "financial_year": proof["financial_years"],
        "type_guess": proof["type_guess"],
    }
    for field in ("gstin", "pan", "legal_name", "state", "entity_type"):
        found[field] = registration.get(field)
    return found


def _correct(found, expected: str) -> bool:
    if isinstance(found, list):
        return expected in found
    return found == expected


def main() -> None:
    if not ocr.ocr_available():
        sys.exit("Tesseract is not installed: run make sync first.")

    labels = {}
    with open(HERE / "labels.csv", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            labels.setdefault(row["doc_id"], []).append(row)

    by_field, by_format, by_type = {}, {}, {}  # name -> [hits, total]
    misses = []
    for path in sorted((HERE / "samples").iterdir()):
        data = path.read_bytes()
        mime_type = "image/png" if path.suffix == ".png" else "application/pdf"
        try:
            found = _found(ocr.extract_text(data, mime_type))
        except ocr.OcrError as error:
            found = {}
            misses.append([path.stem, "(whole file)", "", str(error)])
        file_format = _format_of(path, data)
        for label in labels.get(path.stem, []):
            value = found.get(label["field"])
            hit = _correct(value, label["expected_value"])
            for table, key in (
                (by_field, label["field"]),
                (by_format, file_format),
                (by_type, label["doc_type"]),
            ):
                counts = table.setdefault(key, [0, 0])
                counts[0] += int(hit)
                counts[1] += 1
            if not hit:
                misses.append([path.stem, label["field"], label["expected_value"], value])

    total_hits = sum(hits for hits, _ in by_field.values())
    total = sum(count for _, count in by_field.values())
    print(f"OCR field accuracy: {percent(total_hits, total)} over {len(labels)} documents\n")
    for title, table in (("Field", by_field), ("File format", by_format), ("Document", by_type)):
        rows = [[key, percent(hits, count)] for key, (hits, count) in sorted(table.items())]
        print_table([title, "Correct"], rows)
    if misses:
        print("Misses:")
        print_table(["Document", "Field", "Expected", "Found"], misses)


if __name__ == "__main__":
    main()
