# eval/

Evaluation datasets and scripts for the report. **Never real personal data**: synthetic or fully
anonymised data only (fake names, fake but correctly formatted PAN/GSTIN, no real addresses or phone numbers).

| Folder | Measures | Evaluates module |
|---|---|---|
| `nic/` | NIC code suggestion top-1 / top-3 accuracy | onboarding |
| `ocr/` | OCR field accuracy on sample documents | documents (filing proof), marketplace (Certificate of Practice) |
| `assistant/` | Assistant answer correctness + citation accuracy | assistant |
| `regulatory/` | Regulatory-change extraction precision | regulatory |

Each folder's README describes the exact file format. Evaluation scripts go next to their data
(e.g. `eval/nic/evaluate.py`), use the same conda env, and print a small results table for the report.
