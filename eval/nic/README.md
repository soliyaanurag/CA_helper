# NIC evaluation set

40 business descriptions labelled with the correct NIC activity code from the **official NIC list** we use
(`content/reference/nic_2008.csv`; every code in the file exists there).

File: `descriptions.csv` (UTF-8, comma-separated, header row):

| Column | Example | Notes |
|---|---|---|
| `id` | `nic-001` | unique |
| `description` | `Home bakery baking cakes and bread for neighbours` | how a user would describe the business; no personal data |
| `expected_code` | `10711` | the single best official NIC code |
| `acceptable_codes` | `10719` | optional, `;`-separated alternatives also counted as correct |
| `labelled_by` | `claude` | who labelled the row |
| `notes` | | optional |

Script: `evaluate.py` runs `onboarding.suggest_nic_codes()` for each description.
Metrics: top-1 accuracy (first suggestion = expected or acceptable), top-3 accuracy (among the first three) and how
often the code is in the keyword shortlist (the most Gemini can reach, since it only picks from the shortlist).
`--keywords-only` measures the fallback without Gemini.
