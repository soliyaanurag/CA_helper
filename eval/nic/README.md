# NIC evaluation set (CNT-08 → ONB-10)

~100 business descriptions labelled with the correct NIC activity code from the **official NIC list**.

File: `descriptions.csv` (UTF-8, comma-separated, header row):

| Column | Example | Notes |
|---|---|---|
| `id` | `nic-001` | unique |
| `description` | `Home bakery selling cakes to neighbours` | how a user would describe the business; no personal data |
| `expected_code` | `TODO` | the single best official NIC code |
| `acceptable_codes` | `TODO;TODO` | optional, `;`-separated alternatives also counted as correct |
| `labelled_by` | `Member A` | |
| `notes` | | optional |

Metrics (ONB-10): top-1 accuracy (first suggestion = expected) and top-3 accuracy (expected or acceptable code
among the first three suggestions).
