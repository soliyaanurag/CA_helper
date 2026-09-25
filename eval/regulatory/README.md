# Regulatory extraction evaluation set (REG-06)

~20 real, public news items or official updates about deadline or filing-rule changes, with the structured change
we expect Gemini to extract. Public news only; no personal data.

File: `items.jsonl` (one JSON object per line):

```json
{"id": "reg-001", "url": "TODO", "published_at": "YYYY-MM-DD", "title": "TODO", "expected": {"change_type": "deadline_extension", "forms": ["GSTR-3B"], "categories": ["regular_gst"], "dates": {"new_due_date": "YYYY-MM-DD"}}, "notes": ""}
```

`change_type` values are fixed in REG-02 (e.g. `deadline_extension`, `new_requirement`, `threshold_change`,
`not_relevant`). Metric: precision of extracted fields (form, category, dates) against `expected`.
