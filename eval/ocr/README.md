# OCR evaluation set

15 made-up documents with the fields OCR should extract. **No real personal data**: every name, PAN, GSTIN and
number is fictional. `make_samples.py` creates them (and `labels.csv`) with PyMuPDF, each saved the way people
upload files: a PDF with real text, a PNG photo of the page, or a "scanned" PDF that holds only such a picture.

Layout:
```
eval/ocr/
  make_samples.py      writes samples/ and labels.csv (edit SAMPLES there, then run it again;
                       the PDFs get new internal dates each time, so only rerun it to change samples)
  samples/<doc_id>.<pdf|png>
  labels.csv
  evaluate.py
```

`labels.csv` (one row per expected field):

| Column | Example | Notes |
|---|---|---|
| `doc_id` | `ack-gstr3b-01` | file name without extension |
| `doc_type` | `gstr3b_ack` | `gst_certificate`, `pan_card`, `gstr1_ack`, `gstr3b_ack`, `cmp08_ack`, `gstr4_ack`, `tds_ack`, `itr_ack`, `invoice`, `bank_statement` |
| `field` | `ack_number` | `ack_number`, `filing_date`, `form`, `month`, `quarter`, `financial_year`, `type_guess`, `gstin`, `pan`, `legal_name`, `state`, `entity_type` |
| `expected_value` | `AA270826012345X` | normalised: dates YYYY-MM-DD, forms and types as our codes (`gstr_3b`, `acknowledgement`), month and quarter as numbers, the financial year as written (an ITR shows the assessment year) |
| `created_by` | `claude` | who created the sample |

Script: `evaluate.py` reads each file with `app/utils/ocr.py` and finds the fields with
`app/utils/document_text.py` (the same code as an upload). Metric: field-level accuracy (exact match; `form`,
`month`, `quarter` and `financial_year` count when they are among those found), per field, file format and
document type, plus the list of misses. Each sample is under 1 MB.
