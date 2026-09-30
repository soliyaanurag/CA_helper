"""Assistant evaluation: does the assistant find the right pages and answer correctly?

Each question in questions.jsonl goes through the same code as the chat:
assistant.search() (retrieval) and assistant.answer_question() (the
answer; nothing is saved). The user context is a business owner who has not
registered, so no profile is involved.

    retrieval        a chunk of an expected source is among the passages found
    out of scope     nothing is found (the assistant declines without calling Gemini)
    must mention     every must_mention point is in the answer (only answers Gemini wrote)
    citations        every cited source is an expected one (only answers Gemini wrote)
    ask a CA         the hint is on for questions marked expect_ask_a_ca

Needs the database with the knowledge base (`docker compose exec backend flask --app app assistant ingest`). With GEMINI_API_KEY
the search uses embeddings and Gemini writes the answers (2 requests per question);
--keywords-only never calls Gemini (word-match search, passages instead of answers).
Run in the backend container:
    docker compose exec backend python ../eval/assistant/evaluate.py [--keywords-only]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import app_context, percent, print_table  # noqa: E402

HERE = Path(__file__).parent
CONTEXT = "The user is a business owner who has not registered their business in the app yet."


def main() -> None:
    keywords_only = "--keywords-only" in sys.argv
    with open(HERE / "questions.jsonl", encoding="utf-8") as file:
        questions = [json.loads(line) for line in file if line.strip()]

    # name -> [hits, total]
    scores = {
        "retrieval": [0, 0],
        "out of scope": [0, 0],
        "must mention": [0, 0],
        "citations": [0, 0],
        "ask a CA": [0, 0],
    }
    rows = []
    with app_context() as context:
        from app import assistant

        if keywords_only:
            context.app.config["GEMINI_API_KEY"] = ""
        for item in questions:
            chunks, vector_search = assistant.search(item["question"])
            found = [chunk.source_path for chunk in chunks]
            result = assistant.answer_question(item["question"], CONTEXT)
            cited = [citation["source_path"] for citation in result["citations"]]
            expected = set(item["expected_sources"])
            notes = []

            if item["category"] == "out_of_scope":
                declined = len(found) == 0
                scores["out of scope"][0] += int(declined)
                scores["out of scope"][1] += 1
                notes.append("declined" if declined else f"found {len(found)} passages")
            elif expected:
                hit = bool(expected.intersection(found))
                scores["retrieval"][0] += int(hit)
                scores["retrieval"][1] += 1
                notes.append("found" if hit else "expected page not found")

            if result["ai_used"] and item["must_mention"]:
                answer = result["answer"].lower()
                all_there = all(point.lower() in answer for point in item["must_mention"])
                scores["must mention"][0] += int(all_there)
                scores["must mention"][1] += 1
                if not all_there:
                    notes.append("missing a must_mention point")
            if result["ai_used"] and expected and cited:
                only_expected = set(cited) <= expected
                scores["citations"][0] += int(only_expected)
                scores["citations"][1] += 1
                if not only_expected:
                    notes.append("cited an unexpected source")
            if item.get("expect_ask_a_ca"):
                scores["ask a CA"][0] += int(result["ask_a_ca"])
                scores["ask a CA"][1] += 1
                notes.append("ask a CA on" if result["ask_a_ca"] else "ask a CA off")

            mode = ("AI answer" if result["ai_used"] else "passages") + (
                ", vector search" if vector_search else ", word search"
            )
            rows.append([item["id"], item["category"], mode, "; ".join(notes)])

    print(f"Assistant: {len(questions)} questions\n")
    print_table(
        ["Metric", "Score"],
        [[name, percent(hits, total)] for name, (hits, total) in scores.items()],
    )
    print_table(["Id", "Category", "How it answered", "Notes"], rows)


if __name__ == "__main__":
    main()
