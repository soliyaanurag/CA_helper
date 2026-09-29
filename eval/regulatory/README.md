# Regulatory extraction evaluation set

10 real, public news items or official updates: 7 about a deadline change of one of our forms (ITR, GSTR-3B) and
3 that the monitor should ignore (a tax-audit-report deadline, a GST rate change, tax collections). Public news
only; no personal data.

The `text` is **our own short, factual summary** of the item (a sentence or two), not a copy of the article: the
news sites' texts are not ours to copy, and PIB and some news sites refuse automated downloads. Each date and number
in a summary was checked against the official release or at least two reports of it.

File: `items.jsonl` (one JSON object per line):

```json
{"id": "reg-005", "url": "https://...", "published_at": "2025-08-20", "title": "...", "text": "...", "expected": {"relevant": true, "change_type": "due_date_extension", "forms": ["gstr_3b"], "states": ["Maharashtra"], "old_due_date": "2025-08-20", "new_due_date": "2025-08-27"}, "notes": ""}
```

`expected` uses the values of `regulatory_changes`: `change_type` is `due_date_extension`, `rate_change`, `new_rule`
or `other`; `forms` are our form codes; `states` are state names (empty = every state). An item the monitor should
ignore has only `{"relevant": false}`.

Script: `evaluate.py` runs the daily job's steps 2 and 3 on each item (`regulatory_service._looks_relevant()` and
`_extract_change()`, nothing saved). Metrics: precision and recall of the items kept, then for the relevant items
kept: forms and change type, and (only when Gemini read the item) the new due date and states.
