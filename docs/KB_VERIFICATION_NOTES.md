# Knowledge-base research notes (checked 2026-09-30)

These FAQs were written in plain language from public sources. Official sources are cited in each file's front matter. Several facts were cross-checked against multiple secondary summaries (tax portals and CA firm blogs) where the official page could not be read directly. **Before the final demo, a team member should open each official source once and confirm the numbers** (lane V1).

## Findings that affect the APP, not just the assistant (please act on these)
1. **TDS forms were renamed from 1 April 2026.** Form 24Q is now **Form 138** and Form 26Q is now **Form 140**, for payments from tax year 2026-27. The app's calendar currently generates "24Q/26Q" items for 2026-27 quarters.
   Suggested fix: keep the internal codes, but change the display names to "TDS return, salary (Form 138, earlier 24Q)" and "TDS return, other payments (Form 140, earlier 26Q)". Update content/forms/24Q and 26Q to match.
2. **ITR due date for non-audit business/professional cases is now 31 August** (Finance Act, 2026), not 31 July. The seeded ITR due-date rule / obligation template must be updated (it showed 31 July for a non-audit LLP in the audit). For firms filing ITR-5 without audit, sources disagree (31 July vs 31 August); confirm on the e-filing portal.
3. **GSTR-4 is now due on 30 June** (Notification 12/2024-CT, from FY 2024-25), not 30 April. Check the seeded GSTR-4 template.
4. **Revised ITR deadline is now 31 March of the assessment year** (Finance Act, 2026), not 31 December.
5. **The new Income-tax Act, 2025 has been in force since 1 April 2026.** Section references in content/forms and UI text (44AD, 44AB, 194J...) should mention the new sections for tax year 2026-27 (58, 63, 393...).
6. **Late-fee values for the penalty_rules seed** (for lane V1) are in *gst-late-fee-and-interest.md*, *gst-cmp-08-and-gstr-4.md*, *itr-due-dates-late-fee-belated-revised.md* and *tds-returns-and-due-dates.md*. Verify them against the cited notifications before seeding.

## Points where sources disagreed or could not be fully confirmed (written cautiously)
- The ITR-5 non-audit due date for AY 2026-27 (31 July vs 31 August). The FAQ tells users to check the portal.
- Whether a CMP-08 late fee is currently levied. The FAQ mentions only interest and says to check the portal.
- Which states file quarterly GSTR-3B on the 22nd vs the 24th. The FAQ doesn't list the states and points to the portal.
- The special-category state list for GST thresholds. The FAQ says to check your state.
- The new form number for the non-salary TDS certificate (old Form 16A) under the 2025 rules. The FAQ says to check.
- Whether the late-fee section numbers under the new Act (e.g. the 234E equivalent) are carried over unchanged. This is reported by secondary sources; the FAQ says "equivalent provision".

## Not covered (deliberately)
- GST **rates** on specific goods and services. They were restructured in 2025, change often, and the app doesn't need them. The assistant should say it doesn't know.
- Personal tax computation, slabs and regimes. Out of scope for the product.
