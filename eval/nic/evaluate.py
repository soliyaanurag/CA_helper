"""NIC evaluation: top-1 and top-3 accuracy of the NIC code suggestions (ON10).

Each description in descriptions.csv goes through onboarding_service.suggest_nic_codes(),
the same function the registration page uses: a keyword shortlist of real codes, then
Gemini picks 3 from it (or the best keyword matches without Gemini).

    top-1      the first suggestion is the expected code (or an acceptable one)
    top-3      the expected (or an acceptable) code is among the 3 suggestions
    shortlist  it is in the keyword shortlist Gemini chooses from (Gemini can do no better)

Needs the database with the NIC codes (make infra, make seed). Gemini is used when
GEMINI_API_KEY is set (one request per description); --keywords-only never calls it.
Run from the repo root:
    conda run -n ca-helper python eval/nic/evaluate.py [--keywords-only]
"""

import csv
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import app_context, percent, print_table  # noqa: E402

HERE = Path(__file__).parent


def main() -> None:
    keywords_only = "--keywords-only" in sys.argv
    with open(HERE / "descriptions.csv", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    with app_context() as context:
        from app import onboarding as onboarding_service

        if keywords_only:
            context.app.config["GEMINI_API_KEY"] = ""
        top1 = top3 = shortlisted = ai_used = 0
        misses = []
        for row in rows:
            good = {row["expected_code"]}
            good.update(code for code in row["acceptable_codes"].split(";") if code)
            # suggest_nic_codes() only reads the description of the business.
            result = onboarding_service.suggest_nic_codes(
                SimpleNamespace(description=row["description"])
            )
            picks = [pick["code"] for pick in result["picks"]]
            shortlist = [nic.code for nic in result["shortlist"]]
            ai_used += int(result["ai_used"])
            top1 += int(bool(picks) and picks[0] in good)
            top3 += int(bool(good.intersection(picks[:3])))
            shortlisted += int(bool(good.intersection(shortlist)))
            if not good.intersection(picks[:3]):
                misses.append(
                    [row["id"], row["description"][:45], row["expected_code"], " ".join(picks)]
                )

    total = len(rows)
    mode = "keywords only" if keywords_only else f"Gemini used for {ai_used} of {total}"
    print(f"NIC suggestions: {total} descriptions ({mode})\n")
    print_table(
        ["Metric", "Accuracy"],
        [
            ["top-1", percent(top1, total)],
            ["top-3", percent(top3, total)],
            ["in the keyword shortlist", percent(shortlisted, total)],
        ],
    )
    if misses:
        print("Not in the top 3:")
        print_table(["Id", "Description", "Expected", "Suggested"], misses)


if __name__ == "__main__":
    main()
