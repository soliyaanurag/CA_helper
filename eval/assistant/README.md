# Assistant evaluation set

25 questions a business owner might ask, with the points a correct answer must contain and the pages it should be
based on. The points come from our guides (`content/forms/`) and the official FAQ copies (`content/faqs/`).

File: `questions.jsonl` (one JSON object per line):

```json
{"id": "ast-006", "category": "gst", "question": "When can I file a nil GSTR-3B for a month?", "must_mention": ["1st of the subsequent month"], "expected_sources": ["content/faqs/gst-nil-gstr-3b.md"], "notes": ""}
```

| Field | Meaning |
|---|---|
| `id` | unique |
| `category` | `gst`, `itr`, `tds`, `platform`, `out_of_scope` |
| `question` | as a user would type it (no personal data) |
| `must_mention` | key points a correct answer contains (checked as lowercase text) |
| `expected_sources` | `source_path`s of `kb_chunks` (content files) that should be found and cited |
| `expect_ask_a_ca` | optional, `true` when the "Ask a CA" hint must be on |

Script: `evaluate.py` calls `assistant_service.search()` and `assistant_service.answer_question()` (the chat's own
code; nothing is saved). Metrics: retrieval (an expected source is among the passages found), out of scope (nothing
found, so the assistant declines), must mention (every point is in the answer) and citations (cited sources ⊆
expected sources), both only for answers Gemini wrote, and "Ask a CA".
