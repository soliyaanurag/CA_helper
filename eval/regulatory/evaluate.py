"""Regulatory evaluation: does the news monitor keep the right items and read them correctly?

Each item in items.jsonl (title + a short factual summary of a real public news item or
official notice) goes through the same steps as the daily news job (regulatory_service):
step 2, the keyword filter (_looks_relevant), then step 3, the extraction
(_extract_change: Gemini, or keywords without Gemini). Nothing is saved.

    kept (precision / recall)  the items the monitor would save vs. the ones marked relevant
    forms, change type           for relevant items it kept, exact matches
    new due date, states         the same, only for items Gemini read

Needs the app (make infra); Gemini is used when GEMINI_API_KEY is set (one request per
kept item); --keywords-only never calls it (then no dates or states are extracted).
Run from the repo root:
    conda run -n ca-helper python eval/regulatory/evaluate.py [--keywords-only]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import app_context, percent, print_table  # noqa: E402

HERE = Path(__file__).parent


def main() -> None:
    keywords_only = "--keywords-only" in sys.argv
    with open(HERE / "items.jsonl", encoding="utf-8") as file:
        items = [json.loads(line) for line in file if line.strip()]

    kept_right = kept_total = relevant_total = 0
    fields = {"forms": [0, 0], "change type": [0, 0], "new due date": [0, 0], "states": [0, 0]}
    rows = []
    with app_context() as context:
        from app.models import NewsArticle
        from app.services import regulatory_service

        if keywords_only:
            context.app.config["GEMINI_API_KEY"] = ""
        for item in items:
            expected = item["expected"]
            relevant_total += int(expected["relevant"])
            # The same two steps as scan_news(); the article is never saved.
            article = NewsArticle(title=item["title"], content=item["text"])
            values = None
            if regulatory_service._looks_relevant(article.title + " " + article.content):
                values = regulatory_service._extract_change(article)
            kept = values is not None and bool(values["form_codes"])
            kept_total += int(kept)
            if kept and expected["relevant"]:
                kept_right += 1
                checks = {
                    "forms": sorted(values["form_codes"]) == sorted(expected["forms"]),
                    "change type": values["change_type"] == expected["change_type"],
                }
                # Dates and states are read only by Gemini; the keyword fallback leaves them out.
                by = values["affected_categories"]["extracted_by"]
                if by == "ai":
                    states = values["affected_categories"].get("states", [])
                    new_date = values["dates"].get("new_due_date")
                    checks["new due date"] = new_date == expected["new_due_date"]
                    checks["states"] = sorted(states) == sorted(expected["states"])
                for name, right in checks.items():
                    fields[name][0] += int(right)
                    fields[name][1] += 1
                wrong = [name for name, right in checks.items() if not right]
                note = f"kept ({by}); " + (
                    "fields right" if not wrong else "wrong: " + ", ".join(wrong)
                )
            elif kept:
                note = "kept, but not relevant"
            elif expected["relevant"]:
                note = "missed"
            else:
                note = "ignored (right)"
            rows.append([item["id"], "yes" if expected["relevant"] else "no", note])

    mode = "keywords only" if keywords_only else "Gemini when available"
    print(f"Regulatory monitor: {len(items)} items ({mode})\n")
    summary = [
        ["kept items that are relevant (precision)", percent(kept_right, kept_total)],
        ["relevant items kept (recall)", percent(kept_right, relevant_total)],
    ]
    for name, (hits, total) in fields.items():
        summary.append([name, percent(hits, total)])
    print_table(["Metric", "Score"], summary)
    print_table(["Id", "Relevant", "Result"], rows)


if __name__ == "__main__":
    main()
