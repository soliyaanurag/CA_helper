# Scope: CA Helper ("ComplianceConnect" in the report)

A two-sided web platform connecting Indian MSMEs, gig workers and small businesses with Chartered Accountants (CAs).

**Problem.** Small businesses lack tax and regulatory knowledge. They miss filings, pay avoidable penalties and get
overcharged. Early-career CAs struggle to find clients.

**What the platform does:** tells each business exactly which filings apply and when; guides them to file themselves
or connects them to a fairly priced (or pro-bono) CA; keeps verifiable proof of what was filed.
It does **not** file returns (no government API access). It tracks, guides, connects and verifies.

**Roles:** Business, CA, Admin.

## Forms tracked in v1

| Form | Applies to | Frequency |
|---|---|---|
| ITR (profile selects ITR-3, ITR-4, ITR-5 or ITR-6) | Every registered business/individual | Yearly |
| GSTR-1 | Regular GST taxpayers | Monthly or quarterly (QRMP) |
| GSTR-3B | Regular GST taxpayers | Monthly or quarterly (QRMP) |
| CMP-08 | Composition-scheme taxpayers | Quarterly |
| GSTR-4 | Composition-scheme taxpayers | Yearly |
| 24Q | Businesses deducting TDS on salaries | Quarterly |
| 26Q | Businesses deducting TDS on non-salary payments | Quarterly |

**Entity types:** individual (freelancer/gig worker), proprietorship, partnership firm, LLP, Pvt Ltd company.
LLPs and companies get GST, ITR and TDS tracked, plus a notice that ROC/MCA filings are not tracked.
Tax audit applicability is computed in the profile (it changes the ITR due date); there is no audit form page.

## Business side
1. **Registration.** Mandatory: name, email, phone, entity type, state, business description, annual turnover range,
   investment in plant/machinery/equipment, PAN, "GST registered?". Conditional: GSTIN (if GST registered),
   TAN / "deducts TDS?", "pays salaries above the taxable limit?", CIN/LLPIN (company/LLP). Optional: Udyam number.
   Email OTP verification. Optional OCR auto-fill from an uploaded GST certificate or PAN.
2. **Profile review.** NIC activity code: keyword-shortlist real codes from the official NIC list, Gemini picks from
   the shortlist (never invents a code), user confirms. Regulatory profile with a "why" for every line: MSME tier,
   GST scheme (regular/QRMP/composition), ITR form, presumptive-scheme eligibility, tax audit applicability, TDS
   returns. Edit and re-check.
3. **Home dashboard:** next deadline, due/overdue counts, dynamic penalty estimator, notification tray.
4. **Compliance calendar:** month and list views.
5. **Compliance item page.** Plain-language explanation. Peer insights: % self-filed vs % via CA and the on-time rate
   of each path, segmented by similar businesses (same MSME tier and entity type); a segment is shown only with
   ≥10 users, otherwise overall figures. The user chooses a path:
   - **Self-file:** static instruction pages → link to the government portal → upload the acknowledgement → OCR
     extracts ARN/ack number, date and period → status "Filed–verified".
   - **Consult a CA:** document checklist (tick what you have; upload optional) → CA marketplace with filters
     auto-applied for this form.

   Status lifecycle: `Upcoming → Docs pending → Ready → With CA → Filed → Filed–verified`; `Overdue` is reachable
   from any pre-filed state.
6. **Document vault:** by financial year, period and type; OCR document-type verification.
7. **CA marketplace:** match results with reasons; standard service catalog with listed prices and the platform's
   typical price range; pro-bono queue for eligible businesses; requests and ratings.
8. **Working with a CA:** CA document requests appear as to-dos; the client sees filing status and the verified acknowledgement.
9. **Notifications:** email only, plus the in-app tray. Reminders at T-7, T-3, T-1 days and on overdue.
10. **Profile lifecycle check:** at the start of each financial year and whenever a threshold is crossed.

## CA side
1. **Onboarding:** ICAI membership number, Certificate of Practice upload (OCR extracts number and name), admin
   verification. Unverified CAs are hidden from the marketplace.
2. **Practice profile:** specializations, languages, city, service menu priced against the standard catalog,
   capacity, monthly pro-bono pledge.
3. **Incoming requests:** accept, send a revised quote (reason required), or decline. Requests auto-expire after 48
   hours and the business is re-matched.
4. **Invite existing clients:** the client joins and must approve the CA's access.
5. **Multi-client dashboard:** urgency score per client with a "why flagged" breakdown.
6. **Deadline batch view:** all clients with the same filing due, their document readiness, bulk document requests.
7. **Client workspace:** client's profile, calendar and vault; document requests; mark filed + upload
   acknowledgement; private notes.
8. **Notification settings.**
9. **Ratings:** reviews plus objective metrics.

## Admin
- Verify, suspend or remove users and CAs.
- Edit configuration data: rule thresholds, obligation templates, checklists, instruction pages, service catalog.
- Approve flagged regulatory news before alerts are sent.
- **No** database-structure changes from the UI.

## Platform-wide
- **AI assistant:** floating circle at the bottom right of every page, for both roles. RAG over our own content and
  official FAQs via Gemini, with citations. Category-level profile awareness. "Ask a CA" handoff.
- **Regulatory monitor:** scrape a news website (and official update pages) for deadline or filing-rule changes →
  Gemini extracts the change → one-click admin approval → affected users are flagged, emailed and shown in their
  tray; their CAs' urgency scores rise.

## Out of scope in v1
Advance tax, GSTR-9, ROC/MCA forms, monthly TDS deposit, Telegram/SMS/WhatsApp, in-platform payments, mobile app,
admin schema changes, CA earnings summary.
