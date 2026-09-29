"""Assistant evaluation over questions.md: answers, cited sources and a results table to score.

Every question in questions.md (the main table and the out-of-scope table) is sent to
assistant_service.answer_question(), the function the chat API uses (ask() adds only the
history). The user context is category-level only, the same text user_context() gives a
business owner who has not registered yet: no name, PAN, GSTIN or amount (CLAUDE.md rule 1).
Nothing is saved in the database.

Writes, next to this file:
    results.csv   one row per question: the answer, cited sources, "cited correctly", ...
    RESULTS.md    a table to score by hand (the "correctness" column is left empty) and
                  summary counts; the answers follow the table

"Cited correctly" is automatic: the expected source is among the cited sources. Out-of-scope
questions have no expected source ("n/a"); for them the table shows whether anything was cited.
"AI answer" is "no" when Gemini did not write the answer (no key, quota, error, or nothing
found): then the assistant shows the passages it found instead, so read those rows with care.

Needs the knowledge base (make assistant-ingest) and GEMINI_API_KEY. Two Gemini requests per
question (the search and the answer); --delay waits between questions (default 8 s) to stay
under the free tier's per-minute limit. Run from the repo root:
    make assistant-eval
    conda run -n ca-helper python eval/assistant/run_eval.py [--delay 8]
"""

import argparse
import csv
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import app_context  # noqa: E402

HERE = Path(__file__).parent
QUESTIONS = HERE / "questions.md"
RESULTS_CSV = HERE / "results.csv"
RESULTS_MD = HERE / "RESULTS.md"
CONTEXT = "The user is a business owner who has not registered their business in the app yet."
FAQ_DIR = "content/faqs/"


def _cells(line: str) -> list[str]:
    """The cells of one Markdown table row."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def read_questions() -> list[dict]:
    """The rows of both tables in questions.md: {number, question, expected, expected_source}.

    Main table: # | Question | Key points | Expected source (a file in content/faqs/).
    Out-of-scope table: # | Question | Expected behaviour (no expected source).
    """
    questions = []
    for line in QUESTIONS.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^\|\s*\d+\s*\|", line):
            continue  # not a question row (header, separator or text)
        cells = _cells(line)
        source = cells[3] if len(cells) >= 4 else ""
        questions.append(
            {
                "number": int(cells[0]),
                "question": cells[1],
                "expected": cells[2],
                "expected_source": FAQ_DIR + source if source else "",
            }
        )
    return questions


def evaluate(questions: list[dict], delay: float) -> list[dict]:
    """Ask every question; returns one result row per question."""
    rows = []
    with app_context():
        from app.services import assistant_service

        for index, item in enumerate(questions):
            if index > 0 and delay > 0:
                time.sleep(delay)
            result = assistant_service.answer_question(item["question"], CONTEXT)
            cited = []
            for citation in result["citations"]:
                if citation["source_path"] not in cited:
                    cited.append(citation["source_path"])
            if item["expected_source"]:
                cited_correctly = "yes" if item["expected_source"] in cited else "no"
            else:
                cited_correctly = "n/a"
            rows.append(
                {
                    "number": item["number"],
                    "question": item["question"],
                    "expected": item["expected"],
                    "expected_source": item["expected_source"],
                    "cited_sources": "; ".join(cited),
                    "cited_correctly": cited_correctly,
                    "ai_answer": "yes" if result["ai_used"] else "no",
                    "ask_a_ca": "yes" if result["ask_a_ca"] else "no",
                    "answer": result["answer"],
                    "correctness": "",
                }
            )
            print(
                f"{item['number']:>3}  cited correctly: {cited_correctly:<3}  "
                f"AI answer: {rows[-1]['ai_answer']:<3}  {item['question'][:60]}"
            )
    return rows


def write_csv(rows: list[dict]) -> None:
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _md(text: str) -> str:
    """Text safe inside a Markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ")


def _short(path: str) -> str:
    return path.removeprefix(FAQ_DIR)


def summary(rows: list[dict]) -> list[tuple[str, str]]:
    """(label, count) lines for the top of RESULTS.md."""
    in_scope = [row for row in rows if row["expected_source"]]
    out_of_scope = [row for row in rows if not row["expected_source"]]
    cited_ok = sum(1 for row in in_scope if row["cited_correctly"] == "yes")
    ai = sum(1 for row in rows if row["ai_answer"] == "yes")
    declined = sum(1 for row in out_of_scope if not row["cited_sources"])
    return [
        ("Questions", str(len(rows))),
        ("Answers written by Gemini (AI answer = yes)", f"{ai} of {len(rows)}"),
        ("In-scope questions citing the expected source", f"{cited_ok} of {len(in_scope)}"),
        ("Out-of-scope questions answered without a source", f"{declined} of {len(out_of_scope)}"),
        ("Scored by hand: correct / partial / wrong", "to fill in"),
    ]


def write_markdown(rows: list[dict]) -> None:
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    lines = [
        "# Assistant evaluation results",
        "",
        f"Run on {today:%d %b %Y} with `make assistant-eval` (`eval/assistant/run_eval.py`) "
        "over `questions.md`. Every answer and its cited sources are in `results.csv`.",
        "",
        "- **Cited correctly** (automatic): the expected source is among the cited sources. "
        "Out-of-scope questions have none (`n/a`).",
        "- **AI answer** `no`: Gemini did not write the answer (no key, quota or nothing found); "
        "the assistant showed matching passages instead.",
        "- **Correctness** (by hand): `correct` (every key point, no wrong fact), `partial` or "
        "`wrong`, against the key points in `questions.md`. Fill it in here and in `results.csv`.",
        "",
        "## Summary",
        "",
        "| | Count |",
        "|---|---|",
    ]
    for label, count in summary(rows):
        lines.append(f"| {label} | {count} |")
    lines += [
        "",
        "## Results",
        "",
        "| # | Question | Expected source | Cited sources | Cited correctly | AI answer "
        "| Correctness |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        cited = ", ".join(_short(path) for path in row["cited_sources"].split("; ") if path)
        lines.append(
            f"| {row['number']} | {_md(row['question'])} | {_short(row['expected_source']) or '—'} "
            f"| {cited or '—'} | {row['cited_correctly']} | {row['ai_answer']} | |"
        )
    lines += ["", "## Answers", ""]
    for row in rows:
        lines += [
            f"### {row['number']}. {row['question']}",
            "",
            f"**Expected:** {row['expected']}",
            "",
            "> " + row["answer"].strip().replace("\n", "\n> "),
            "",
        ]
    RESULTS_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--delay", type=float, default=8.0, help="seconds between questions")
    args = parser.parse_args()
    questions = read_questions()
    print(f"{len(questions)} questions from {QUESTIONS.name}")
    rows = evaluate(questions, args.delay)
    write_csv(rows)
    write_markdown(rows)
    for label, count in summary(rows):
        print(f"{label}: {count}")
    print(f"Wrote {RESULTS_CSV.name} and {RESULTS_MD.name}")


if __name__ == "__main__":
    main()
