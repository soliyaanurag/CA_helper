# Legal values awaiting human verification

**Rule:** never invent a legal threshold, rate or due date. Every legal value lives in a DB config table with
`source_reference`, `effective_from` and `effective_to`. A value that is not yet confirmed from an official source
gets `TODO_VERIFY` in its `source_reference` **and a row in this file**. When a value is verified, fill in the
value, the official source (URL + notification/circular number + date), who verified it and when, then remove
`TODO_VERIFY` from the config row.

Anyone may add rows for values their module needs.

**Current status:** the onboarding thresholds (`rule_thresholds`) and the compliance due-date rules
(`obligation_templates`) are **seeded with proposed values** in `backend/app/seed.py`, every row with `TODO_VERIFY`
in its `source_reference`. The proposed values below are what the code uses today; **none has been checked against
an official source yet.** Rows without a value (penalties, the salary limit) are not used by any code yet. Section
names and descriptions in the "What" columns are pointers for the verifier and must be confirmed too.
Seeded rows are effective from 1 April 2025.

## GST registration (onboarding)

| Key | What it decides | Value | Official source | Verified by / date |
|---|---|---|---|---|
| `gst.registration.min_turnover` | "You may need GST registration" (the lower, services limit is used for every business) | Seeded: ₹20 lakh — TODO_VERIFY | | |

## Profile thresholds (onboarding)

| Key | What it decides | Value | Official source | Verified by / date |
|---|---|---|---|---|
| `msme.micro/small/medium.*` | MSME tier limits (investment and turnover) | Seeded: micro ₹2.5 cr / ₹10 cr, small ₹25 cr / ₹100 cr, medium ₹125 cr / ₹500 cr — TODO_VERIFY | | |
| `gst.qrmp.max_turnover` | QRMP scheme eligibility | Seeded: ₹5 cr — TODO_VERIFY | | |
| `gst.composition.max_turnover` | Composition scheme eligibility (seeded: goods only; services and special categories not handled) | Seeded: ₹1.5 cr — TODO_VERIFY | | |
| `itr.presumptive_44ad.max_turnover` | Presumptive taxation eligibility (business; the higher limit for mostly digital receipts is not handled) | Seeded: ₹2 cr — TODO_VERIFY | | |
| `itr.presumptive.44ada.*` | Presumptive taxation eligibility (professionals) | — TODO_VERIFY | | |
| `itr.audit_44ab.min_turnover` | Tax audit applicability (the higher limit for mostly digital receipts is not handled) | Seeded: ₹1 cr — TODO_VERIFY | | |
| `itr.form_by_entity` | Which ITR form (ITR-3/4/5/6) applies per entity type and scheme, and "companies always have an audit" (logic in `compute_profile()`, steps 4–5, not a table value) | In code: company ITR-6; LLP ITR-5; presumptive ITR-4; other firm ITR-5; else ITR-3 — TODO_VERIFY | | |
| `tds.salary.taxable_limit` | Meaning of "pays salaries above the taxable limit" | — TODO_VERIFY | | |

## Due-date rules (compliance)

| Key | What | Value | Official source | Verified by / date |
|---|---|---|---|---|
| `due.gstr1.monthly` | GSTR-1 monthly due date | Seeded: 11th of next month — TODO_VERIFY | | |
| `due.gstr1.qrmp` | GSTR-1 quarterly (QRMP) due date | Seeded: 13th after the quarter — TODO_VERIFY | | |
| `due.gstr3b.monthly` | GSTR-3B monthly due date | Seeded: 20th of next month — TODO_VERIFY | | |
| `due.gstr3b.qrmp.*` | GSTR-3B quarterly due dates (state-wise staggering) | Seeded: 22nd after the quarter for every state (some states: 24th) — TODO_VERIFY | | |
| `due.cmp08` | CMP-08 quarterly due date | Seeded: 18th after the quarter — TODO_VERIFY | | |
| `due.gstr4` | GSTR-4 annual due date | Seeded: 30 April after the FY — TODO_VERIFY | | |
| `due.24q.q1-q4` | 24Q quarterly due dates | Seeded: 31 Jul, 31 Oct, 31 Jan, 31 May — TODO_VERIFY | | |
| `due.26q.q1-q4` | 26Q quarterly due dates | Seeded: 31 Jul, 31 Oct, 31 Jan, 31 May — TODO_VERIFY | | |
| `due.itr.non_audit` | ITR due date, non-audit cases | Seeded: 31 July after the FY — TODO_VERIFY | | |
| `due.itr.audit` | ITR due date, audit cases | Seeded: 31 October after the FY — TODO_VERIFY | | |

## Penalties (alerts)

| Key | What | Value | Official source | Verified by / date |
|---|---|---|---|---|
| `penalty.gst.late_fee.*` | Late fee per day and cap for GSTR-1 / GSTR-3B / CMP-08 / GSTR-4 (incl. nil returns) | — TODO_VERIFY | | |
| `penalty.gst.interest_rate` | Interest on late GST payment | — TODO_VERIFY | | |
| `penalty.tds.late_fee` | Late fee for late 24Q/26Q statements | — TODO_VERIFY | | |
| `penalty.itr.late_fee.*` | Late fee for a belated ITR (by income slab) | — TODO_VERIFY | | |

## Verified values
_None yet._ Move rows here (with value + source) once verified.
