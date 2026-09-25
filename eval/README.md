# eval/

Evaluation datasets and scripts for the report (Phase 5). **Never real personal data**: synthetic or fully
anonymised data only (fake names, fake but correctly formatted PAN/GSTIN, no real addresses or phone numbers).

| Folder | Measures | Dataset task | Evaluation task |
|---|---|---|---|
| `nic/` | NIC code suggestion top-1 / top-3 accuracy | CNT-08 (A) | ONB-10 (A) |
| `ocr/` | OCR field accuracy on sample documents | CNT-09 (C) | DOC-05 (B), MKT-11 (C) |
| `assistant/` | Assistant answer correctness + citation accuracy | AST-06 (B) | AST-06 (B) |
| `regulatory/` | Regulatory-change extraction precision | REG-06 (B) | REG-06 (B) |

Each folder's README describes the exact file format. Evaluation scripts go next to their data
(e.g. `eval/nic/evaluate.py`), use the same conda env, and print a small results table for the report.
