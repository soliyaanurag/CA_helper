# Assistant evaluation set

~50 questions a business owner or CA might ask, with the points a correct answer must contain and the sources it
should cite.

File: `questions.jsonl` (one JSON object per line):

```json
{"id": "ast-001", "category": "gst", "question": "TODO", "must_mention": ["TODO"], "expected_sources": ["content/forms/GSTR-3B/explanation.md"], "notes": ""}
```

| Field | Meaning |
|---|---|
| `id` | unique |
| `category` | `gst`, `itr`, `tds`, `platform`, `out_of_scope` |
| `question` | as a user would type it (no personal data) |
| `must_mention` | key points a correct answer contains |
| `expected_sources` | content paths or official FAQ URLs that should be cited |

Metrics: correctness (all `must_mention` points present, judged manually or with a rubric) and citation accuracy
(cited sources ⊆ expected sources). Out-of-scope questions should be declined politely.
