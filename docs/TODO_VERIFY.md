# Legal values awaiting human verification

**Rule:** never invent a legal threshold, rate or due date. Every legal value lives in a DB config table with
`source_reference`, `effective_from` and `effective_to`. A value that is not yet confirmed from an official source
gets `TODO_VERIFY` in its `source_reference` **and a row in this file**. When a value is verified, fill in the
value, the official source (URL + notification/circular number + date), who verified it and when, then remove
`TODO_VERIFY` from the config row.

Anyone may add rows for values their module needs.

**Current status (29 Sep 2026, V1):** every seeded value was checked against official sources (GST portal user
manuals, CBIC circulars and notifications on cbic-gst.gov.in, incometax.gov.in FAQs and form manuals, TRACES, the
Udyam portal, the GST e-invoice portal's master codes). The checked values are in "Verified values" below and carry
their source in `app/seed.py` (`make seed` / `make sync` updates databases seeded earlier). **A teammate should
re-read the linked pages once before the demo** ("Verified by" says so). What could not be read from an official
text is in "Still to verify": those values are filled in as proposals and keep `TODO_VERIFY`, so the penalty
estimates using them say "rules pending verification".

Seeded rows are effective from 1 April 2025. When the law changes, add a row with a new `effective_from` (and set
`effective_to` on the old one) instead of editing the old row.

## Still to verify

| Key / row | Proposed value (in use) | Where to confirm | Why it is open |
|---|---|---|---|
| `obligation_templates` ITR due date for ITR-5 (firms, LLPs) without an audit | 31 July after the FY (`by_itr_form`; ITR-3 / ITR-4 stay 31 August) | e-filing portal (the due date it shows for ITR-5, AY 2027-28), Finance Act 2026 amendment of s.139(1) / s.263 | Sources disagree (31 July vs 31 August; `docs/KB_VERIFICATION_NOTES.md`). The earlier date is used, so the date shown is never late. |
| `obligation_templates` GSTR-4 due date | 30 June after the FY (was 30 April) | CGST Rules rule 62 as amended by Notification 12/2024-CT (10.07.2024), 53rd GST Council | The notification could not be opened; the GST portal FAQ ([faq_GSTR4annual](https://tutorial.gst.gov.in/userguide/returns/faq_GSTR4annual.htm) Q5) still says "30th of the month succeeding the financial year" (= 30 April). Every other report says 30 June from FY 2024-25. |
| `penalty_rules` GSTR-1 daily fee | ₹50 a day, nil ₹20 | Notification 4/2018-CT | No longer hosted on cbic-gst.gov.in. The same amounts are confirmed for GSTR-3B (Circular 26/26/2017-GST). |
| `penalty_rules` GSTR-4 daily fee | ₹50 a day, nil ₹20 | Notification 73/2017-CT | No longer hosted. |
| `penalty_rules` GST interest (GSTR-3B, CMP-08, GSTR-4) | 18% a year | CGST Act s.50(1), Notification 13/2017-CT | Neither text could be opened from an official site (taxinformation.cbic.gov.in did not answer). |
| `penalty_rules` ITR interest | 12% a year (1% a month) | Income-tax Act 1961 s.234A; 2025 Act equivalent | Not found on an official page that could be read. Also, 234A is simple interest per month or part of a month; the estimator uses days / 365. |
| `tds.salary.taxable_limit` | none (not used by any code) | Income-tax slab / basic exemption | Meaning of "pays salaries above the taxable limit"; the user answers yes/no. |
| `itr.form_by_entity` (logic in `compute_profile()`) | company ITR-6; LLP ITR-5; presumptive ITR-4; other firm ITR-5; else ITR-3 | incometax.gov.in ITR help pages | ITR-3 and ITR-4 match the official page copied in `content/faqs/itr-business-profession.md` (ITR-4 for individuals, HUFs and firms other than LLPs, total income up to ₹50 lakh; ITR-3 for individuals who cannot use ITR-1, 2 or 4). ITR-5 and ITR-6 are not checked yet, nor the ₹50 lakh condition (not handled). |
| `content/reference/nic_2008.csv` descriptions | as published | MoSPI NIC-2008 | Some descriptions are cut off at about 200 characters in the PMEGP PDF (e.g. 07299, 32111). |

## Simplifications (decided 29 Sep 2026, `docs/DECISIONS.md`)

- **GSTR-3B under QRMP:** the official due date is the 22nd after the quarter in Chhattisgarh, MP, Gujarat,
  Maharashtra, Karnataka, Goa, Kerala, Tamil Nadu, Telangana, Andhra Pradesh, Daman and Diu, Dadra and Nagar Haveli,
  Puducherry, Andaman and Nicobar, Lakshadweep, and the **24th** everywhere else (GSTN QRMP advisory Q28). The app
  uses the 22nd for every state: in the 24th-group states the date shown is two days early, never late.
- **Late-fee caps that depend on turnover** store the value for a business with turnover up to ₹1.5 crore
  (GSTR-1, GSTR-3B, GSTR-4: ₹2,000). Nil returns (cap ₹500) and larger businesses (GSTR-1/3B: ₹5,000 up to ₹5 crore,
  ₹10,000 above) are not modelled.
- **ITR late fee:** ₹5,000 is stored; ₹1,000 applies when total income is at most ₹5 lakh (not modelled).
- **TDS late fee:** ₹200 a day with no cap stored; the law caps it at the TDS of the statement.
- **GST registration:** the lower, services limit (₹20 lakh) is used for every business; goods have ₹40 lakh, and
  special category states have lower limits (below). **Composition:** the goods limit (₹1.5 crore) is used; ₹75 lakh
  in special category states and services (s.10(2A)) are not handled. **44AD / 44AB:** the ₹2 crore and ₹1 crore
  limits are used; the higher limits for mostly non-cash businesses (₹3 crore / ₹10 crore) are not handled.
- **The Income-tax Act, 2025 applies from 1 April 2026** (tax year 2026-27, the filings the app creates now). Its
  thresholds, due dates and fees are the same as the 1961 Act's for everything above (incometax.gov.in FAQs); the
  TDS returns are called Form 138 (was 24Q) and Form 140 (was 26Q) and new ITR forms come under the Income-tax
  Rules, 2026. The app keeps the old codes and shows the new names for tax year 2026-27 onwards (`RENAMED_FORMS`).

## Verified values

Verified by: Claude (web research, 29 Sep 2026), from the official pages linked. **To confirm: a teammate re-reads
each link once** and writes their name next to "Claude".

| Key | Value | Official source |
|---|---|---|
| `msme.micro/small/medium.*` | Micro: investment ≤ ₹2.5 cr and turnover ≤ ₹10 cr; small ≤ ₹25 cr / ₹100 cr; medium ≤ ₹125 cr / ₹500 cr (from 1 April 2025) | [Udyam Registration portal](https://udyamregistration.gov.in/) (classification text); notification S.O. 1364(E), 21.03.2025 |
| `gst.registration.min_turnover` | ₹20 lakh (services; ₹10 lakh in Manipur, Mizoram, Nagaland, Tripura). Goods: ₹40 lakh (₹20 lakh in Arunachal Pradesh, Manipur, Meghalaya, Mizoram, Nagaland, Puducherry, Sikkim, Telangana, Tripura, Uttarakhand) | CBIC, [GST – An Update (1 May 2019)](https://cbic-gst.gov.in/pdf/01052019-GST-An-Update.pdf); CGST Act s.22, Notification 10/2019-CT |
| `gst.qrmp.max_turnover` | ₹5 crore | GST portal, [QRMP FAQ](https://tutorial.gst.gov.in/userguide/returns/FAQs_change_profile.htm) |
| `gst.composition.max_turnover` | ₹1.5 crore (goods; ₹75 lakh in special category states) | CBIC, GST – An Update (1 May 2019); Notification 14/2019-CT |
| `itr.presumptive_44ad.max_turnover` | ₹2 crore (₹3 crore when cash receipts ≤ 5%). 44ADA (professionals, not used by the app): ₹50 lakh (₹75 lakh) | incometax.gov.in, [ITR-4 (Sugam) FAQ](https://www.incometax.gov.in/iec/foportal/help/e-filing-itr4-form-sugam-faq) Q9 |
| `itr.audit_44ab.min_turnover` | ₹1 crore (₹10 crore when cash ≤ 5% of receipts and payments); profession ₹50 lakh. Same in the 2025 Act (s.63) | incometax.gov.in, [Income Tax Forms FAQ](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/%20income%20tax%20forms-faq) |
| ITR due date | **31 August** without a tax audit (was seeded 31 July; 31 July is for returns without business income), 31 October with an audit | incometax.gov.in, [Income Tax Returns FAQ](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/income-tax-returns) Q16 and Q24; s.263 of the 2025 Act as amended by Finance Act 2026 |
| GSTR-1 due dates | 11th of the next month; QRMP: 13th after the quarter | GST portal, [Form GSTR-1 FAQ](https://tutorial.gst.gov.in/userguide/returns/GSTR_1.htm) Q10; [QRMP advisory](https://tutorial.gst.gov.in/offlineutilities/returns/QRMP_Advisory.pdf) Q28 |
| GSTR-3B due dates | 20th of the next month; QRMP: 22nd or 24th after the quarter by state (see Simplifications) | GST portal, [Form GSTR-3B FAQ](https://tutorial.gst.gov.in/userguide/returns/GSTR3B.htm); QRMP advisory Q28 |
| CMP-08 due date | 18th after the quarter | GST portal, [CMP-08 FAQ](https://tutorial.gst.gov.in/userguide/returns/FAQs_CMP02.htm) Q3 |
| 24Q / 26Q due dates | 31 July, 31 October, 31 January, 31 May | incometax.gov.in, [Form 138](https://www.incometax.gov.in/iec/foportal/newformpage/forms/form138-um) and [Form 140](https://www.incometax.gov.in/iec/foportal/newformpage/forms/form140-um) user manuals |
| GSTR-3B late fee | ₹50 a day (₹25 CGST + ₹25 SGST), nil return ₹20 | CBIC [Circular 26/26/2017-GST](https://cbic-gst.gov.in/pdf/26of2017-Circular.pdf) para 2.2 |
| GST late-fee caps (CGST part; SGST the same) | GSTR-3B: ₹250 nil, ₹1,000 up to ₹1.5 cr, ₹2,500 up to ₹5 cr (N. 19/2021-CT). GSTR-1: ₹250 nil, ₹1,000, ₹2,500 (N. 20/2021-CT). GSTR-4: ₹250 nil, ₹1,000 (N. 21/2021-CT) | cbic-gst.gov.in, notifications 19, 20 and 21/2021-Central Tax (1 June 2021) |
| CMP-08 late fee | none | GST portal, CMP-08 FAQ Q9 |
| TDS statement late fee | ₹200 a day, at most the TDS of the statement (s.234E) | TRACES, [late filing fee FAQ](https://traces61contents.tdscpc.gov.in/en/faq-dedu-default-lf.html) |
| ITR late fee | ₹5,000; ₹1,000 when total income ≤ ₹5 lakh (s.234F; s.428 of the 2025 Act) | incometax.gov.in, Income Tax Returns FAQ Q25 |
| `content/reference/gst_states.json` | 36 states and UTs, codes 01–38 without 25 and 28 | GST e-invoice portal, [State Codes master](https://einvoice1.gst.gov.in/Others/MasterCodes) |
