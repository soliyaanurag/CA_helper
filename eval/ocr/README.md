# OCR evaluation set (CNT-09 → DOC-05, MKT-11)

~30 sample documents with the fields OCR should extract. **No real personal data**: create samples with fake
details (correctly formatted but fake PAN/GSTIN/ARN numbers, fake names), or fully redact real layouts.

Layout:
```
eval/ocr/
  samples/<doc_id>.<pdf|png|jpg>
  labels.csv
```

`labels.csv` (one row per expected field):

| Column | Example | Notes |
|---|---|---|
| `doc_id` | `ack-gstr3b-01` | file name without extension |
| `doc_type` | `gstr3b_ack` | e.g. `gst_certificate`, `pan_card`, `gstr1_ack`, `gstr3b_ack`, `cmp08_ack`, `gstr4_ack`, `tds_ack`, `itr_ack`, `cop_certificate` |
| `field` | `ack_number` | e.g. `ack_number`, `filing_date`, `period`, `gstin`, `pan`, `name`, `membership_number` |
| `expected_value` | `TODO` | normalised value (dates as YYYY-MM-DD) |
| `created_by` | `Member C` | |

Metric (DOC-05): field-level accuracy (exact match after normalisation), per field and per document type.
Keep each sample under 1 MB (pre-commit blocks larger files).
