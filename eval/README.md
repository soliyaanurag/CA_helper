# eval/

Evaluation datasets and scripts for the report (X3). **Never real personal data**: synthetic or fully
anonymised data only (fake names, fake but correctly formatted PAN/GSTIN, no real addresses or phone numbers).

| Folder | Measures | Evaluates module | Data |
|---|---|---|---|
| `nic/` | NIC code suggestion top-1 / top-3 accuracy | onboarding (ON10) | 40 descriptions |
| `ocr/` | OCR field accuracy on sample documents | documents (DO8, DO9), onboarding (ON13) | 15 made-up documents, 74 fields |
| `assistant/` | Retrieval, answer points, citations, "Ask a CA" | assistant (AS1–AS4) | 25 questions |
| `regulatory/` | Which news items are kept, and the fields read from them | regulatory (RE3) | 10 real public items |

Each folder's README describes its file format. Each script (`eval/<folder>/evaluate.py`) calls the **same service
functions as the app** and prints a small results table; `eval/common.py` holds the shared helpers (the import
path, the app context, the table). Run them from the repo root:

```bash
conda run -n ca-helper python eval/ocr/evaluate.py                       # no database, no Gemini
conda run -n ca-helper python eval/nic/evaluate.py [--keywords-only]      # database (make infra, make seed)
conda run -n ca-helper python eval/assistant/evaluate.py [--keywords-only]  # + make assistant-ingest
conda run -n ca-helper python eval/regulatory/evaluate.py [--keywords-only]
```

Without `--keywords-only` the scripts use Gemini when `GEMINI_API_KEY` is set; when Gemini fails (quota), the app's
own fallbacks run and the script says so. The datasets were labelled by Claude (`labelled_by` / `created_by`
`claude`) and should be checked by a teammate before the numbers go into the report.

## Results (29 Sep 2026, main + MA8)

The Gemini free tier answered 429 (quota used up) all day, so every result below is **without Gemini text
generation**; embeddings worked. Rerun without `--keywords-only` when the quota is back to measure the AI paths.

| Evaluation | Result |
|---|---|
| OCR (all local) | 95.9% of fields (71/74): text PDF 96.0%, photo 100%, scanned PDF 91.7%. Misses: a TDS "Provisional Receipt" is not recognised as an acknowledgement (2 documents), and Tesseract cut one scanned token number short. |
| NIC, keyword shortlist only | top-1 35.0% (14/40), top-3 72.5% (29/40); the right code is in the shortlist Gemini chooses from for 85.0% (34/40), so that is the most Gemini can reach. |
| Assistant, vector search (embeddings) | right page found for 21/21 questions; 2 of 3 out-of-scope questions found nothing ("register a company with MCA" found GST pages); "Ask a CA" on for the notice question. Answer points and citations not measured (no Gemini answers). |
| Assistant, word search only | right page found for 19/21; out-of-scope declined 1/3. |
| Regulatory, keywords only | kept 7/7 relevant items and ignored 3/3 others (precision and recall 100%); forms and change type right 7/7. Dates and states are only read by Gemini (not measured). The items are short summaries that name the form clearly, so this is an easy set for the keyword filter. |
