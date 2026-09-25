# Legal values awaiting human verification

**Rule:** never invent a legal threshold, rate or due date. Every legal value lives in a DB config table with
`source_reference`, `effective_from` and `effective_to`. A value that is not yet confirmed from an official source
gets `TODO_VERIFY` in its `source_reference` **and a row in this file**. When a value is verified, fill in the
value, the official source (URL + notification/circular number + date), who verified it and when, then remove
`TODO_VERIFY` from the config row.

Anyone may add rows for values their module needs.

**Current status:** no legal values exist in the code yet. The rows below list what needs to be verified before
the rule engine (onboarding), due-date rules (compliance) and penalty estimator (alerts) can use real values.
**Values are intentionally blank.** Section names and descriptions in the "What" columns are pointers for the
verifier and must be confirmed too.

## Profile thresholds (onboarding)

| Key | What it decides | Value | Official source | Verified by / date |
|---|---|---|---|---|
| `msme.micro/small/medium.*` | MSME tier limits (investment and turnover) | — TODO_VERIFY | | |
| `gst.qrmp.max_turnover` | QRMP scheme eligibility | — TODO_VERIFY | | |
| `gst.composition.max_turnover.*` | Composition scheme eligibility (goods / services / special categories) | — TODO_VERIFY | | |
| `itr.presumptive.44ad.*` | Presumptive taxation eligibility (business) | — TODO_VERIFY | | |
| `itr.presumptive.44ada.*` | Presumptive taxation eligibility (professionals) | — TODO_VERIFY | | |
| `itr.audit.44ab.*` | Tax audit applicability (incl. cash-transaction condition) | — TODO_VERIFY | | |
| `itr.form_by_entity` | Which ITR form (ITR-3/4/5/6) applies per entity type and scheme | — TODO_VERIFY | | |
| `tds.salary.taxable_limit` | Meaning of "pays salaries above the taxable limit" | — TODO_VERIFY | | |

## Due-date rules (compliance)

| Key | What | Value | Official source | Verified by / date |
|---|---|---|---|---|
| `due.gstr1.monthly` | GSTR-1 monthly due date | — TODO_VERIFY | | |
| `due.gstr1.qrmp` | GSTR-1 quarterly (QRMP) due date | — TODO_VERIFY | | |
| `due.gstr3b.monthly` | GSTR-3B monthly due date | — TODO_VERIFY | | |
| `due.gstr3b.qrmp.*` | GSTR-3B quarterly due dates (state-wise staggering) | — TODO_VERIFY | | |
| `due.cmp08` | CMP-08 quarterly due date | — TODO_VERIFY | | |
| `due.gstr4` | GSTR-4 annual due date | — TODO_VERIFY | | |
| `due.24q.q1-q4` | 24Q quarterly due dates | — TODO_VERIFY | | |
| `due.26q.q1-q4` | 26Q quarterly due dates | — TODO_VERIFY | | |
| `due.itr.non_audit` | ITR due date, non-audit cases | — TODO_VERIFY | | |
| `due.itr.audit` | ITR due date, audit cases | — TODO_VERIFY | | |

## Penalties (alerts)

| Key | What | Value | Official source | Verified by / date |
|---|---|---|---|---|
| `penalty.gst.late_fee.*` | Late fee per day and cap for GSTR-1 / GSTR-3B / CMP-08 / GSTR-4 (incl. nil returns) | — TODO_VERIFY | | |
| `penalty.gst.interest_rate` | Interest on late GST payment | — TODO_VERIFY | | |
| `penalty.tds.late_fee` | Late fee for late 24Q/26Q statements | — TODO_VERIFY | | |
| `penalty.itr.late_fee.*` | Late fee for a belated ITR (by income slab) | — TODO_VERIFY | | |

## Verified values
_None yet._ Move rows here (with value + source) once verified.
