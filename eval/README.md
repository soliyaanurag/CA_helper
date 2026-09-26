# eval/

Evaluation datasets and scripts for the report. **Never real personal data**: synthetic or fully
anonymised data only (fake names, fake but correctly formatted PAN/GSTIN, no real addresses or phone numbers).
Create a subfolder (e.g. `eval/nic/`) when its data arrives. Evaluation scripts go next to their data
(e.g. `eval/nic/evaluate.py`), use the same conda env, and print a small results table for the report.

| Folder | Measures | Evaluates module |
|---|---|---|
| `nic/` | NIC code suggestion top-1 / top-3 accuracy | onboarding |
| `ocr/` | OCR field accuracy on sample documents | documents (filing proof), marketplace (Certificate of Practice) |
| `assistant/` | Assistant answer correctness + citation accuracy | assistant |
| `regulatory/` | Regulatory-change extraction precision | regulatory |

## nic/: NIC code suggestions
~100 business descriptions labelled with the correct NIC activity code from the **official NIC list**.
File `descriptions.csv` (UTF-8, header row):

| Column | Example | Notes |
|---|---|---|
| `id` | `nic-001` | unique |
| `description` | `Home bakery selling cakes to neighbours` | how a user would describe the business; no personal data |
| `expected_code` | `TODO` | the single best official NIC code |
| `acceptable_codes` | `TODO;TODO` | optional, `;`-separated alternatives also counted as correct |
| `labelled_by` | `<initials>` | who labelled the row |
| `notes` | | optional |

Metrics: top-1 accuracy (first suggestion = expected) and top-3 accuracy (expected or acceptable code among the
first three suggestions).

## ocr/: OCR field extraction
~30 sample documents with the fields OCR should extract, as `samples/<doc_id>.<pdf|png|jpg>` plus `labels.csv`.
Create samples with fake details (correctly formatted but fake PAN/GSTIN/ARN numbers, fake names), or fully redact
real layouts. Keep each sample under 1 MB so the repo stays small.

| Column | Example | Notes |
|---|---|---|
| `doc_id` | `ack-gstr3b-01` | file name without extension |
| `doc_type` | `gstr3b_ack` | e.g. `gst_certificate`, `pan_card`, `gstr1_ack`, `gstr3b_ack`, `cmp08_ack`, `gstr4_ack`, `tds_ack`, `itr_ack`, `cop_certificate` |
| `field` | `ack_number` | e.g. `ack_number`, `filing_date`, `period`, `gstin`, `pan`, `name`, `membership_number` |
| `expected_value` | `TODO` | normalised value (dates as YYYY-MM-DD) |
| `created_by` | `<initials>` | who created the sample |

Metric: field-level accuracy (exact match after normalisation), per field and per document type.

## assistant/: assistant answers
~50 questions a business owner or CA might ask. File `questions.jsonl` (one JSON object per line):

```json
{"id": "ast-001", "category": "gst", "question": "TODO", "must_mention": ["TODO"], "expected_sources": ["content/forms/GSTR-3B/explanation.md"], "notes": ""}
```

`category` is `gst`, `itr`, `tds`, `platform` or `out_of_scope`; `question` is typed as a user would (no personal
data); `must_mention` lists the key points a correct answer contains; `expected_sources` lists content paths or
official FAQ URLs that should be cited. Metrics: correctness (all `must_mention` points present, judged manually
or with a rubric) and citation accuracy (cited sources ⊆ expected sources). Out-of-scope questions should be
declined politely.

## regulatory/: regulatory-change extraction
~20 real, public news items or official updates about deadline or filing-rule changes, with the structured change
we expect Gemini to extract. Public news only; no personal data. File `items.jsonl`:

```json
{"id": "reg-001", "url": "TODO", "published_at": "YYYY-MM-DD", "title": "TODO", "expected": {"change_type": "deadline_extension", "forms": ["GSTR-3B"], "categories": ["regular_gst"], "dates": {"new_due_date": "YYYY-MM-DD"}}, "notes": ""}
```

`change_type` values are fixed when the extraction step is built (e.g. `deadline_extension`, `new_requirement`,
`threshold_change`, `not_relevant`). Metric: precision of extracted fields (form, category, dates) against `expected`.
