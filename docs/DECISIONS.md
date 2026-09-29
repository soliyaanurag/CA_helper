# Decision log

Newest first. One entry per decision: date, what, why. Anything decided in chat that affects others goes here
in the same PR.


## 2026-09-30: 2026 legal update: Form 138 / 140 names, ITR date by form, filings resynced

From the "findings that affect the app" in `docs/KB_VERIFICATION_NOTES.md`.

**What**
- **TDS returns keep their codes but show their new names** from tax year 2026-27: "Form 138 (earlier 24Q)" and
  "Form 140 (earlier 26Q)" (Income-tax Act, 2025; Form 138 / 140 user manuals). A display name is not a legal
  value (no threshold, rate or due date), so it is a small table in code, `RENAMED_FORMS` (backend
  `compliance_service` and frontend `lib/labels.js`, the same entries), keyed by the first financial year. The
  frontend reads the year from the filing's period label ("Q2 2026-27"). Codes, folders, rules and old periods
  stay 24Q / 26Q.
- **ITR due date by form:** without an audit, individuals and HUFs with business or professional income (ITR-3,
  ITR-4: every individual and proprietor in the app) stay on 31 August; **ITR-5 (firms, LLPs) is set to 31 July,
  `TODO_VERIFY`**: sources disagree (31 July or 31 August), and the earlier date is never late (the same choice as
  GSTR-3B's 22nd). Any audit: 31 October. 31 July for returns without business income (ITR-1 / ITR-2) is recorded
  in the source but no profile of the app has one. Stored as `by_itr_form` in the ITR template's `due_date_rule`
  (one template per form, frequency and start date is allowed).
- **GSTR-4** was already 30 June (V1); it keeps `TODO_VERIFY` until Notification 12/2024-CT is read.
- **Corrected rules reach existing filings:** `flask seed` (so `make seed` and `make sync`) ends with
  `resync_all_filings()`, which runs `sync_filings` for every business with its saved profile: not-started filings
  get the new dates; filed, "With CA" and requested filings keep theirs. `sync_filings` also moves a filing to the
  template now in force.
- **Guides and labels** name the new sections next to the old ones (44AB → 63, 44AD/44ADA → 58, TDS 192 → 392,
  193–194T → 393); the profile page says "Tax audit (s.44AB; s.63 from tax year 2026-27)".

**Why:** the smallest change that shows users the forms they will actually see on the portal, gives firms and LLPs
a date that is never late until the rule is confirmed, and makes a corrected rule reach every database with the
command teammates already run.

## 2026-09-29: Matching score and evaluations (B5: MA8, X3)

**What**
- **Matching score (MA8):** points per reason, added up, like the CA urgency score: open filings the CA prices
  (20 each) and specializes in (5 each), same city (15), fee at or below the typical fee (5 per filing), average
  rating ≥ 4 (10), at least half the client slots free (5), a point per year of experience up to 10. "Find a CA"
  lists the highest total first and shows every reason with its points. No language reason (businesses have no
  language field); capacity numbers stay hidden from businesses.
- **Evaluations (X3), agreed sizes:** 40 NIC descriptions, 15 made-up OCR documents, 25 assistant questions and
  10 real news items (instead of 100 / 30 / 50 / 20). Each `eval/<name>/evaluate.py` calls the app's own service
  functions and has a `--keywords-only` mode, so it runs without the Gemini quota.
- `assistant_service.answer_question(question, context)` was split out of `ask()` (no history saved), so the
  evaluation measures the exact chat code.
- **News items are our own short summaries** of real public items (URL, title and date kept), because news texts
  are not ours to copy and PIB refuses automated downloads.
- The datasets are labelled by Claude and should be checked by a teammate before the report.

**Why:** a weighted sum with written reasons is explainable in one sentence and to the user ("why this CA");
small, checked datasets and scripts that reuse the real code give honest numbers for the report now, and can be
rerun with Gemini when the quota allows.

## 2026-09-29: Legal values checked against official sources (V1, CO6)

**What**
- Every seeded threshold, due-date rule, penalty rule and GST state code was checked against official pages (GST
  portal FAQs, CBIC circulars and notifications, incometax.gov.in FAQs and form manuals, TRACES, the Udyam portal,
  the GST e-invoice portal). Each row's `source_reference` now names its source; `docs/TODO_VERIFY.md` lists the
  verified values with links, what is still open and the simplifications. A teammate re-reads the links once.
- **Corrected:** the ITR is due on **31 August** without a tax audit (31 July only applies to returns without
  business income) and GSTR-4 on **30 June** after the year (from FY 2024-25; that notification could not be opened,
  so it keeps `TODO_VERIFY`).
- **Values whose official text could not be opened** (the GSTR-1 / GSTR-4 daily fees, GST interest 18%, ITR interest)
  are filled in as proposals and keep `TODO_VERIFY`, so their estimates say "rules pending verification" (asked and
  approved).
- **GSTR-3B under QRMP stays on the 22nd for every state**, although some states have the 24th (asked and
  approved): the date shown is never late, and no state logic is needed.
- **Caps that depend on turnover or income store the small-business value** (turnover up to ₹1.5 crore; ITR ₹5,000);
  the TDS fee's cap (the TDS of the statement) is not stored (asked and approved).
- `seed_rule_thresholds`, `seed_obligation_templates` and `seed_penalty_rules` now **update** rows seeded earlier
  (`_upsert()` in `seed.py`), so a corrected value reaches every database with `make seed` / `make sync`.
- **The Income-tax Act, 2025** (from 1 April 2026) keeps these thresholds, due dates and fees; the guides mention
  its names (Form 138 / 140 for 24Q / 26Q, tax year). The app keeps the old form codes.
- **Content (CO6):** the 21 files in `content/forms/` were reviewed against the official pages and set to
  `status: DONE`. Fixed: CMP-08 has no late fee; unsupported claims removed; each page links its official FAQ.

**Why:** the rule "never invent a legal value" needs a named source per value; updating seeded rows keeps every
teammate's database in step with the reviewed values.

## 2026-09-29: Local OCR (B2: ON12, ON13, DO8, DO9, CO10 filed–verified)

**What**
- **Tools (asked and approved):** `PyMuPDF==1.28.2` (pip) reads PDF text and turns scanned pages into pictures;
  the **`tesseract` program** comes from conda-forge (`tesseract=5` in `environment.yml`; CI: `apt-get install
  tesseract-ocr`). `CLAUDE.md`'s conda rule now allows python, nodejs, pip **and tesseract** (a program, not a
  Python library). We call `tesseract stdin stdout` with `subprocess`, so no `pytesseract` and no Pillow.
- **OCR runs in the upload request**, in `documents_service.on_document_uploaded(document, data)` (the hook now gets
  the bytes), and never makes an upload fail. First 3 pages only, English.
- **Only non-personal facts are stored** in `documents.ocr_fields` (number, date, forms, periods, type guess), never
  the text, PAN, GSTIN or names (rule 4). Auto-fill (ON13) reads the file in memory and stores nothing.
- **Filed–verified rule (DO8):** the acknowledgement must name the form, show the period, carry a number (the same as
  a typed ARN) and a filing date on or after the period's end. Verified → `filed_verified` + `verified_at`; an empty
  ARN is filled from the file. Not verified → stays `filed` and the page lists what did not match. The same check
  runs when the CA marks a filing filed (CW5).
- **Document-type check (DO9)** compares a keyword guess with the type chosen at upload, not with the checklist
  entry (checklist keys have no document type); the vault shows "Looks like: ...".
- `storage.check_file()` split out of `save_file()` (shared code), so a file can be checked without being stored.

**Why:** proof of filing is one of the platform's three promises (track, guide, verify); doing it locally keeps
documents on our server (rule 2), and a rule anyone can read keeps "verified" explainable.

## 2026-09-29: Gemini: retry only 503, and log the model and Google's reason

**What**
- Every Gemini client is built by one helper, `_client()` in `app/utils/gemini_client.py` (used by `ask_gemini` and
  `embed_texts`). It retries **only 503** ("this model is currently experiencing high demand"), up to 3 attempts.
  A **429** (quota used up) is no longer retried.
- A failed call is logged with the model and Google's reason, e.g. `Gemini call failed (model gemini-3.6-flash):
  429 RESOURCE_EXHAUSTED: You exceeded your current quota.` (Google's message never contains our prompt; errors
  without a code, like a timeout, are logged by name).

**Why:** retrying a 429 right away only used up more of the small free quota (one click could cost 3 requests), and
the old log line ("ClientError") hid the cause: a wrong model name, a retired model and a used-up quota all looked
the same.

## 2026-09-29: AI assistant (B3: AS1–AS5)

**What**
- **Retrieval-augmented answers:** our guides (`content/forms/`) and official FAQ pages (`content/faqs/`) are cut
  into chunks, embedded with Gemini (`gemini-embedding-001`, 768 numbers, `GEMINI_EMBED_MODEL`) and stored in
  `kb_chunks` (pgvector). A question finds the 5 closest chunks **within a cosine distance of 0.40**, and Gemini
  answers only from them, citing [n]. Nothing close enough → "not found" without calling Gemini.
- **Official FAQs are copied word for word** (only the layout becomes Markdown), with source URL, publisher and
  retrieval date, after checking robots.txt (asked and approved: "our content + a few FAQs"). Pages that were outdated
  (GSTR-4 "till FY 2018-19") or only built by JavaScript (income-tax "how to file", Protean TDS FAQs) were left out.
- **Fallbacks, no new tools:** without Gemini the search uses word matches and the answer is the passages
  themselves; ingestion needs Gemini (the vector column is NOT NULL) and changes nothing without it.
- **Only categories about the user go into the prompt** (entity type, MSME tier, GST scheme, ITR form, TDS returns,
  next filings), never names, PAN, GSTIN, addresses or amounts; embeddings go through `gemini_client` too, so
  questions are scrubbed (rule 1).
- **"Ask a CA"** = Gemini's own flag or words like notice / penalty / appeal in the question.
- The floating widget is for business owners and CAs (SCOPE.md "both roles"), not admins; history is kept (AS5,
  soft delete). `chat_messages.citations` holds `{sources, ask_a_ca, ai_used}` for an answer.
- `make assistant-ingest` (Makefile) runs `flask assistant ingest`; `content/faqs/` is listed in `CLAUDE.md`.

**Why:** the assistant must not invent legal facts; answering only from our own and official pages, with sources,
keeps every answer checkable, and the relevance cut-off keeps unrelated questions from getting unrelated passages.

## 2026-09-28: Regulatory monitor (RE1–RE6, X2 news job)

**What**
- **No new package:** the web is read with the standard library (`urllib.request`, `urllib.robotparser`,
  `xml.etree` for RSS, a regular expression for links on web pages). One polite request per source per day, our own
  user agent `CAHelperBot/1.0`; `robots.txt` is checked on every run and a site we cannot read it from is skipped.
- **Sources:** TaxGuru's GST and income-tax RSS feeds (their robots.txt allows it; checked 2026-09-28) and the
  CBIC GST home page (off by default). PIB refused our requests (403), so it is not used.
- **Keyword filter before Gemini:** only articles naming one of our 7 forms and a change word go to Gemini, at most
  10 per run (quota). Gemini's JSON is checked against our own codes; nothing it invents is kept.
- **Keyword fallback:** without Gemini a change is still saved from the title (marked `extracted_by: keywords` and
  shown as "Found by keywords (no AI)"), so the monitor works without a key; the admin reads the article.
- **Nothing is sent before an admin approves** (module contract). Approval tells businesses with a not-filed filing
  of the forms that fit the change's GST schemes / entity types / states (tray + email), their active CAs (tray),
  and adds 15 urgency points for 30 days. Due dates are never changed automatically.
- The Gemini client retries a 503 ("high demand") answer up to 3 times; since 29 Sept not a 429 (see that entry).

**Why:** the monitor must stay explainable and safe: public news only, the site's rules respected, an admin in the
loop before anyone is alarmed, and no legal value (a due date) changed by a scraper or a model (rule 3).


## 2026-09-28: Gemini client and NIC code suggestion (ON9, ON10, ON11)

**What**
- **`google-genai` (pinned 2.25.0)** is the Gemini library; the model, key and timeout come from `.env`
  (`GEMINI_MODEL`, default `gemini-flash-latest`, an alias Google keeps pointing at the current Flash model; `GEMINI_API_KEY`; `GEMINI_TIMEOUT_SECONDS`). Tests never have a key.
- **One wrapper, `app/utils/gemini_client.py`:** `ask_gemini()` always runs `scrub_pii()` first (GSTIN, PAN, email,
  Aadhaar-like numbers, phone → `[GSTIN]`, ...), logs only the kinds it removed, and raises 503
  `GEMINI_UNAVAILABLE` without a key or when the call fails. Every feature must work without Gemini (fallback).
- **The NIC list** is the Ministry of MSME's PMEGP file (NIC-2008), converted once to
  `content/reference/nic_2008.csv` and loaded by `make seed` (`seed_nic_codes`). Only the **5-digit sub-classes**
  (1,165 codes): that is what Udyam and GST registration ask for, and headings would make vague suggestions. The PDF
  had lost the leading zero of divisions 01–09; it is put back. Wording is kept as published.
- **Suggestion = keyword shortlist + Gemini pick:** the 15 codes whose description best matches the words of the
  business description (a word found in few codes counts more; common words ignored), then Gemini picks the best 3
  **from that shortlist only**, with a reason. Invented or repeated codes are dropped and keyword matches fill the
  gap. Only the scrubbed description and the shortlist are sent (never the name, PAN, GSTIN, ...). The user
  confirms one code; nothing is saved before that. No embeddings: word matching is explainable in one sentence.
- `POST /onboarding/nic-suggestions` is limited to 10 per minute (Gemini quota).

**Why:** rule 1 (no PII to Gemini) is only safe if there is exactly one place that calls it; rule "never invent"
applies to NIC codes too, so Gemini may only choose, not create. The form asks users to leave names and contact
details out of the description, because names cannot be found by a pattern.


## 2026-09-28: Suspension, audit log, admin filing numbers, peer insights, demo data (AD4, AD5, AD8, CO13, X1)

**What**
- **Suspension is `users.is_active = false`** (no new column): login answers 403 `ACCOUNT_INACTIVE` with "This
  account is suspended…", and a token still held stops working at once. A suspended CA disappears from the
  marketplace (only live accounts are listed); their `requested` / `quoted` engagements are cancelled and each
  business is told (tray + email). **Active engagements stay** (the business keeps its filings' history; deciding
  what happens next is an admin's call). An admin cannot suspend themselves. Reactivating does not restore
  cancelled requests. Both actions go to the audit log with the (optional) reason.
- **Overdue rate** (admin dashboard) = of the filings whose due date has passed, the share not filed on time
  (still unfiled, or `filed_at` after the due date in Indian time).
- **Peer insights** compare the **filed** filings of the same form: self vs through a CA (`filing_path`) and each
  path's on-time rate. Segment = same entity type + MSME tier, shown only with ≥ 10 businesses that filed the form
  (`MIN_PEER_BUSINESSES`, the rule in SCOPE.md), else the same figures over every business, else nothing.
- **Demo data is a separate command, `flask seed-demo` (`make seed-demo`)**, in `backend/app/demo_seed.py`, not
  part of `make seed` / `make sync`, so nobody's database fills with demo data unasked. It runs once (it checks
  for the first demo business's email), all fictional, 14 businesses of which 10 are micro proprietorships so the
  peer-insights segment shows. It gives `business@demo.local` a business only if it has none, and sets the demo
  CA's pro-bono pledge to 2 when it is 0 (so the pro-bono flow can be shown). README "Demo script" says which
  account shows which flow.

**Why:** the smallest changes that make the admin side and the demo complete, without new tables or columns.

## 2026-09-28: CA workspace (CW2–CW7) and CA capacity (MA7)

**What**
- **Built on the vault branch and sent as one PR with it** (asked by the team): the workspace needs the vault's
  links and downloads.
- **A CA's clients are the businesses with an active engagement;** every workspace route names the business and
  checks `require_ca_access` first, then keeps to the filings of the CA's active engagements (`active_work`).
- **Urgency is a weighted sum of named constants** (overdue 40 each, next deadline within 3 days 25 / within 7
  days 10, each missing required document 5, each unanswered request 3), each part shown as a "why flagged" line.
  `regulatory_points()` is the hook for regulatory changes (0 for now).
- **Document requests:** one checklist entry (or `general`) of an engaged, not-filed filing. The business answers
  with a vault file; the file is linked to the filing under that key (ticking it), which is also what lets the CA
  open it. No new access rule was needed. Emails use the `document_request` setting.
- **The CA marks one filing filed** (ARN and acknowledgement optional), reusing the business's mark-filed code
  (`_record_filed`). The acknowledgement belongs to the business owner. The engagement **completes by itself when
  its last filing is filed**; the manual "Mark as completed" stays. Open requests for that filing are cancelled.
- **Capacity = active clients** (distinct businesses with an active engagement, pro-bono included). A full CA is
  hidden from "Find a CA" and anything that would add a client answers 409 `CA_AT_CAPACITY`; an existing client
  can still add filings.
- CA reminders (alerts) now link to `/ca/clients/{business}` instead of `/ca/engagements`.

**Why:** the simplest workspace that lets a CA see exactly their active work, ask for what is missing, file, and
see which client needs attention first, with every score explainable line by line.

## 2026-09-28: Document vault and documents on the filing page (DO2–DO7)

**What**
- **One blueprint, `/api/v1/documents`**, for businesses: upload, list (filters FY, type, filing; paginated),
  download, soft delete, link and unlink. **No migration**: the `documents` and `compliance_item_documents` tables
  already had every column.
- **Download is the only route a CA may use**, and only for a document `ca_can_access_document()` allows (active
  engagement). Others get 404 (they do not learn it exists). Admins are not allowed on the vault routes at all (they
  never read contents; the certificate view stays their one exception).
- **Linking a file to a checklist entry ticks it** (asked and approved), through a new non-committing
  `compliance_service.tick_checklist_entry()`, so "docs pending → ready" moves by itself. Unlinking keeps the tick.
- **A filed filing's documents are fixed:** no link, unlink or delete of its files (409 `FILING_LOCKED` /
  `DOCUMENT_IN_USE`), and its acknowledgement can only go through "Undo mark as filed". A business can still add
  files while the filing is `with_ca`.
- **Upload-and-link is one request** (`compliance_item_id` + `checklist_key` on the upload); the link is checked
  before the file is stored, so a refused link leaves no orphan file.
- **OCR hook:** `on_document_uploaded(document)`, a no-op called by `add_document()` for every upload (vault,
  acknowledgement, certificate), is where local OCR (DO8, DO9) plugs in.
- documents ↔ compliance and documents ↔ marketplace import each other's service modules, as alerts ↔ marketplace.

**Why:** the simplest vault that gives the filing page real files per checklist entry, lets the CA of an active
engagement open exactly those files, and never lets proof of a filed return disappear.

## 2026-09-28: Alerts: tray, email settings, reminders, penalty estimator (AL1–AL5)

**What**
- **One `notify()` for every tray entry** (`alerts_service`). It never commits. Its email (if `email=True` and the
  user allows that type) is queued on the database session and sent by an `after_commit` listener, so it goes out
  only if the caller's single commit succeeds; a rollback drops it.
- **Engagement and account emails stay always on** (transactional) and unchanged: marketplace keeps sending them
  itself and only adds `notify(email=False)` for the tray. The settings page shows "CA request update: always
  emailed" instead of a switch. Switchable: deadline reminders, overdue, document requests, regulatory updates.
  Completing an engagement adds a tray entry only (it never emailed).
- **Reminder timing:** daily at 08:15 IST (after the hourly overdue job), plus `flask alerts send-reminders
  [--date]` for demos. Windows, not exact days: 4–7 days before → T-7, 2–3 → T-3, 0–1 → T-1, after the due date →
  overdue; only the current window's reminder is sent (a missed one is not sent late); each kind once per filing
  (`reminder_log`). **No reminder for a filing due before the business registered.** One summary email per person
  per run, with a tray entry per filing. The CA of an **active** engagement on the filing is reminded too.
- **Penalty rules are seeded with every amount NULL** (`TODO_VERIFY`): no value is confirmed from an official source
  yet; a later small PR fills verified values. The migration makes `late_fee_per_day` and `annual_interest_rate`
  nullable and adds **`flat_late_fee`** (the ITR's fee is fixed, not per day). NULL means "not confirmed", never 0.
- **Estimator:** the rule in force on the filing's due date; late fee = flat fee, or days late × daily fee (nil-return
  fee for nil returns) capped at the maximum; interest only when the business types the tax due (we do not store
  tax amounts). The dashboard "penalty exposure" adds late fees only. Every figure carries the label "Estimate
  (rules pending verification)".
- alerts ↔ marketplace import each other's service modules (reminders need the CA; engagement events need
  `notify`). It works because both use `from app.services import <module>` and neither calls the other at import time.

**Why:** the simplest design that keeps "one commit per service", never emails about something that was not saved,
does not spam a business that registers mid-year, and never shows an invented legal amount.

## 2026-09-28: The filing page (CO4–CO10, CO12) and the first form content

**What**
- **New packages (asked and approved):** `PyYAML==6.0.3` (backend, reads `checklist.yaml`) and
  `react-markdown` 10.1.0 (frontend, shows the Markdown explanation and instructions; `components/Markdown.jsx`).
- **Form content has a first draft** in `content/forms/<FORM>/` (`status: DRAFT`): explanation, self-filing steps and
  a document checklist for each of the 7 forms, with no amounts, rates or due dates. The API reports the status and
  the page says "draft" until it is `DONE`. Links are written `<https://...>` (clickable without extra plugins).
- **Status from the checklist (CO10):** for a filing the business works on itself: past due → `overdue`; nothing
  ticked → `upcoming`; a required document missing → `docs_pending`; all required ticked → `ready`. `with_ca`,
  `filed` and `filed_verified` are never changed by ticks. Optional checklist entries do not affect the status.
- **Mark as filed (CO9) is one multipart request** with an optional ARN and an optional acknowledgement file, from
  `upcoming`, `docs_pending`, `ready` or `overdue`. The file is a `documents` row (type `acknowledgement`) linked by
  `compliance_items.acknowledgement_document_id`. A `with_ca` filing is marked by the CA (CW5). A mistaken mark can
  be undone (`unmark-filed`) for self-filed filings only.
- **Choosing a path (CO8) only records the intention** (`filing_path`); `with_ca` still comes from an active
  engagement.
- **Dashboard numbers (CO12) come from the API.** `overdue` counts every not-filed filing whose due date passed,
  including late `with_ca` ones (the business should see them), unlike the `overdue` status (CO11).
- `current_business_or_none()` next to `current_business()` in `utils/decorators.py` (the dashboard works before
  registration).
- Built on one branch as one PR together with CO11 (asked and approved), because each feature builds on the last.

**Why:** these complete the business's side of a filing for the demo (calendar → filing page → file it myself or
find a CA → proof), using the tables that already existed; no migration was needed.

## 2026-09-28: Overdue job (CO11): hourly, and "With CA" stays "With CA"

**What**
- `compliance_service.mark_overdue_filings(today)` sets live filings in `upcoming`, `docs_pending` or `ready` whose
  due date is **before** today (Indian date) to `overdue`. A filing due today is not late yet.
- The worker runs it **every hour** (`compliance.mark_overdue`), not once at midnight: on a laptop the worker is
  often started during the day, and hourly means it catches up within an hour. Running it again changes nothing.
- **A late `with_ca` filing keeps `with_ca`.** `SCOPE.md` and `DATA_MODEL.md` said overdue is reachable from any
  pre-filed state; `DATA_MODEL.md` now says "from the states before `with_ca`". Reason: `with_ca` is how the code
  knows a CA is handling a filing (the dashboard's "with a CA" card, `sync_filings` keeping it on a profile change,
  and the CA workspace to come); overwriting it with `overdue` would lose that. The pages already show how late any
  filing is from its `due_date`.

**Why:** filings created by `sync_filings` only got `overdue` at registration or on a profile edit, so a filing
created as `upcoming` stayed `upcoming` after its due date.

## 2026-09-28: Pro-bono queue (MA16): micro businesses, the CA chooses, active at ₹0

**What**
- **Eligible:** a business whose computed MSME tier is `micro` (`PRO_BONO_TIERS` in `marketplace_service.py`). This
  is a platform policy, not a legal value; change the list to widen it.
- The business picks filings and joins the queue (one queued request at a time). The filings are stored on the
  request as a uuid array (`pro_bono_requests.compliance_item_ids`, one migration); they are not reserved while
  queued.
- **The CA chooses** from the queue (oldest first), only if verified and with free slots this calendar month
  (Indian time): `pro_bono_slots_per_month` minus pro-bono engagements activated this month.
- Taking a request creates an engagement that is **already `active`** (both sides agreed), `is_pro_bono`, prices 0,
  with the catalog service that fits each filing; filings become "With CA". Two CAs cannot take the same request
  (the row is locked).

**Why:** micro is the smallest tier, the natural "can't afford a CA" group, and it is already computed. Letting
the CA choose is simple and fair (nobody gets free work they did not accept); automatic matching can come later.
No quote step: the price is 0 and both sides chose each other.

## 2026-09-28: Ratings (MA17): once per completed engagement, anonymous, average computed live

**What**
- The business rates an engagement only after the CA marked it `completed`, and only once (no editing). Stars 1–5
  (the table's CHECK), an optional review; an empty review is stored as null.
- A CA's average (one decimal) and count are computed from `ratings` on each request, like the typical price
  range; shown from the first rating together with the count ("4.5 (2 ratings)").
- The CA page shows the latest 5 reviews **without the business's name**.
- Not yet: editing a rating, CA replies, objective metrics (response time, completion rate).

**Why:** rating only completed work keeps ratings honest (you rate what you received). No editing and anonymous
reviews are the simplest safe choices (privacy of the business). The count next to the average tells readers how
much it is worth, so no minimum number of ratings is needed.

## 2026-09-28: Access checks (MA14): only an ACTIVE engagement opens a business to a CA

**What**
- `marketplace_service.ca_has_active_access(ca_profile_id, business_id)` is true only while an engagement between
  them is `active`; `active_engagement_item_ids` gives the filings of those engagements (so two CAs on one business
  each see only their own); `open_engagement_item_ids` adds requested and quoted ones (for a summary while
  deciding); `ca_can_access_document` allows only documents linked to active filings or their acknowledgement.
- CA routes call `require_ca_access(business_id)` (`app/utils/decorators.py`), which answers 404
  `BUSINESS_NOT_FOUND` (not 403) without access.
- Access ends with the engagement (completed, declined, expired, cancelled); no read-only period after completion.

**Why:** it follows the "Who may read what" table in `DATA_MODEL.md` and CLAUDE.md rule 5. A 404 does not reveal
that a business exists. Ending access at completion is the simplest safe rule; a read-only period can be added
later if CAs need to download acknowledgements after finishing.

## 2026-09-28: Request expiry (MA12): a 15-minute worker job, plus a check on every answer

**What**
- `marketplace_service.expire_old_requests()` runs in the worker every 15 minutes (`marketplace.expire_requests`).
  It sets `requested` engagements whose `expires_at` (request time + 48 h) has passed to `expired`, commits once,
  then emails each business which services to choose again in "Find a CA". Only `requested` expires: a `quoted`
  engagement is waiting for the business, not the CA.
- A CA answering after the deadline (accept, quote, decline) gets 409 `REQUEST_EXPIRED`, even before the job runs.
- No automatic re-matching: the business picks another CA itself (its filings are free as soon as the request
  expires, because `expired` is not an open status).

**Why:** a 15-minute interval is simple and precise enough for a 48-hour deadline; the check on every answer
closes the gap between two runs. Letting the business choose again keeps the CA choice with the business.

## 2026-09-27: Editable profile, CA verification and a clearer UI (PRs 2–4 as one)

**What**
- **Editing the profile** recomputes it in place and syncs this year's filings (`sync_filings`): new ones added,
  ones that no longer apply soft-deleted, ones that apply again reactivated (never inserted twice), periods and
  due dates updated. **A filing that no longer applies but is with a CA (`with_ca` or in an open engagement) is
  kept**, and "What changed" says so. Switching monthly ↔ quarterly turns "Q1" into "Apr" (same start date).
- **QRMP is the user's choice** within the QRMP limit ("Monthly / Quarterly (QRMP)"); above it returns are
  monthly. Existing QRMP businesses were recorded as having chosen it, so nothing changed for them.
- **The audit line is split:** tax audit (s.44AB, from turnover, every entity type) and accounts audited under
  another law (companies always; partnerships and LLPs answer; others never). The ITR due date uses either. The
  old "A company's accounts are always audited" under "Tax audit" is gone.
- **Filings start at 1 April** of the financial year; past due dates start `overdue` and appear in "Earlier this
  year". Businesses registered earlier get those past filings on their next save (no one-off command).
- **The Indian number format everywhere:** `format_inr()` on the backend (explanations), `formatRupees()` on the
  frontend (already en-IN).
- **The GST state list is a JSON reference file** (`content/reference/gst_states.json`, with a source note and
  a TODO_VERIFY row), served by `GET /onboarding/states`: one list for backend and frontend, no table or package.
  A state typed earlier that is not on the list is flagged for the user to choose again. GSTINs are checked for
  the mod-36 check character, the state code and the PAN (tests use synthetic GSTINs only).
- **Consent:** signup needs `terms_accepted: true` and sets `users.terms_accepted_at`; login says whether it was
  given; older accounts see a one-time consent step. `/terms` is short plain language.
- **Encrypted file storage** (`app/utils/storage.py`): PDF/JPG/PNG recognised by their first bytes, a size limit,
  Fernet with the same `FIELD_ENCRYPTION_KEY`, files in `UPLOAD_DIR` outside the tracked repo. First use: the
  Certificate of Practice, which is required before an admin can verify a CA.
- **Re-verification:** a new certificate (like a new membership or CoP number, the existing rule) sends a CA back
  to `pending`, out of the marketplace until checked; the profile page warns before saving a new number.
- **Admin verification** is in the admin module; it calls marketplace, documents and auth service functions and
  writes `admin_audit_log`. Verify/reject emails the CA; a rejection needs a reason the CA sees.
- **"Find a CA" is ranked for a registered business by default** (its own filings first, then same city, then the
  old order), with its prices per filing. No language badge: businesses have no language field. Unregistered
  users see the old list unchanged.
- **Presentation:** dashboard cards and to-dos, profile chips with collapsible explanations, the calendar by month
  with days left, coloured statuses and filters, request filings by quarter, engagement timelines with a
  countdown, CA preview and setup checklist, admin counts. All from existing endpoints except the new admin ones.
- **Tests whose expectations changed** because the behaviour they checked changed on purpose: the old GSTIN
  `27ABCDE1234F1Z5` (fails the check digit) became the synthetic `27ABCDE1234F1Z0`; tests that expected QRMP now
  choose it; the compliance tests expect every period from 1 April; the company audit test checks both lines;
  signup bodies send `terms_accepted`; the CA profile save body has `pro_bono_slots_per_month`; the calendar
  test counts one header row per month; the onboarding page selects the state from the list.

**Why:** the browser audit and the plan agreed for PRs 2–4, built as one pull request at the team's request.

## 2026-09-27: Audit bug fixes (PR 1)

**What**
- **ITR service follows the ITR form.** An ITR filing is priced and requested only with the catalog service of the
  business's profile ITR form: ITR-3 → `itr_business`, ITR-4 → `itr_presumptive`, ITR-5/ITR-6 →
  `itr_firm_company` (`ITR_SERVICE_CODES`). Before, every ITR service was offered and the page picked ITR-4, so an
  LLP could request the presumptive service. The old test that expected every ITR service was replaced.
- **A 20-second request timeout** in `apiFetch()`: a request without an answer fails with code `TIMEOUT` and a
  clear message instead of hanging. The reported 30–45 s freezes could not be reproduced (API calls took under
  12 ms through the Vite proxy, emails under 0.05 s, no render or redirect loops); the timeout makes the next one
  visible.
- **Logging out on purpose forgets the page.** The route guard remembers the page for the next login only after an
  expired session, not after the Log out button, so a later login goes to the role's home (this was the "admin
  lands on the last admin page" report).
- **Seed keeps sample CAs consistent:** every sample CA specializes in each service they price, and the seed adds
  missing specializations to sample profiles seeded earlier (never to the demo CA).
- **Forms say what is wrong where it is wrong:** the price errors get a summary next to Save and focus moves to the
  first wrong price; the duplicate membership number is a field error; checkboxes have ids, values and labels.
  "Send request" stays disabled until a filing is ticked (replacing the "Tick at least one filing" error).
- **The landing page's API badge** shows only in development or when the API or database is down; the audience
  cards link to signup (role preselected) or login.

**Why:** the browser audit; every fix is additive and keeps the existing endpoints, fields and codes.

## 2026-09-27: Engagements (MA9, MA10, MA11, MA13): quoted_price, filings "With CA", no expiry yet

**What**
- A request is one `engagements` row plus one `engagement_items` row per filing. Each item keeps three prices:
  `listed_price` (copied from the CA's menu when requested, so later menu changes do not alter it), the new
  column **`quoted_price`** (the CA's quote, until the business decides) and `agreed_price` (set when the
  engagement becomes `active`: the listed price if the CA accepted, the quoted price if the business accepted a
  quote). A quote needs a price for every filing and a reason.
- The business chooses the service per filing (the CA's services whose
  `service_catalog.form_code` matches the filing; several only for ITR). `form_code` is now seeded.
- **One open engagement per filing** (`requested`, `quoted`, `active`) is checked in
  `marketplace_service.create_request()`, with the filing rows locked (`SELECT ... FOR UPDATE`) during the check.
- When an engagement becomes `active`, its filings are set to status `with_ca`, path `ca`, through a new
  compliance service function (`mark_filings_with_ca`), not by marketplace touching the compliance table.
- The business can withdraw an unanswered request and reject a quote; both end as `cancelled` (no extra status).
  The CA can mark an `active` engagement `completed`; it does not yet check that the filings are filed.
- Notifications are emails only: the CA on a new request, the business when the CA accepts, quotes or declines.
- **MA12 (expiry) is not built**: `expires_at` is set to 48 hours after the request, but nothing expires it yet.

**Why:** a separate `quoted_price` keeps each price column meaning one thing (a quote is not agreed until the
business accepts). Locking the filings stops two quick requests from both reserving the same filing, which the
database alone cannot prevent (the status lives on `engagements`). Going through compliance's service keeps the
modules separate (CLAUDE.md rule 9).

## 2026-09-27: Business registration, profile engine and filings

**What**
- **`businesses.gst_composition`** (boolean, default false; migration `onboarding: add gst_composition to
  businesses`): the composition scheme is a choice the business makes, so the form asks for it. Without it CMP-08
  and GSTR-4 could never apply. Allowed only when GST registered; above the composition limit the profile falls
  back to a regular scheme and says why.
- **Legal values are seeded with proposed, unverified values**, each marked `TODO_VERIFY` and listed with its
  value in `docs/TODO_VERIFY.md` (11 rule thresholds, 9 obligation templates, effective from 1 April 2025). The
  engine reads them from the tables, never from code; a test changes a threshold and sees the result change.
- **Due-date rules are small JSON objects** read by `compliance_service.due_date()`: monthly `{"day": d}`,
  quarterly `{"quarters": [[m, d] x 4]}`, yearly `{"month": m, "day": d}` plus `audit_month`/`audit_day`.
  Template `applicability` maps profile column names to allowed values; `{}` = every business.
- **Registration does everything in one commit:** save the business, compute the profile, create the filings
  (onboarding calls `compliance_service.create_filings()`, which does not commit).
- **Only filings still due are created**, for the current financial year: we cannot know whether older periods
  were filed before the business joined.
- **`current_business()`** in `utils/decorators.py` (next to `current_user()`) finds the logged-in user's business
  (404 `BUSINESS_NOT_FOUND`). It lives in shared code so compliance does not import onboarding (onboarding already
  imports compliance) and other modules can use it too.
- **`today_in_india()`** in `models/base.py`: due dates and financial years use the Indian date.
- `rule_version` is `"v1"`, a version of the profile logic, bumped when `compute_profile()` changes.

**Why:** the marketplace's engagements need businesses and filings, and filings need the profile; this is the
shortest path there (ON1, ON4–ON6, CO1–CO3), kept to plain functions that can be explained step by step.

## 2026-09-27: The complete schema up front

**What**
- **Every v1 table exists now**, in one migration (`schema: complete data model`): 27 new tables and new columns
  on `users`, `ca_profiles` and `service_catalog`, one models file per module. No services, routes or pages; each
  module builds its logic on these tables and changes columns with its own migration.
- **Annual turnover is an amount** (`businesses.annual_turnover`, `Numeric(12,2)`), not a range. A CA sees only a
  turnover bracket computed from it before an engagement is active.
- **No blind index.** PAN, GSTIN, TAN and phone are Fernet-encrypted (`EncryptedString`, key
  `FIELD_ENCRYPTION_KEY`, no dev fallback). We never look a business up by them, so they are not searchable and not
  unique (two businesses can share a PAN).
- **Documents are owned by a user**, not a business (`owner_id`), so a CA's Certificate of Practice is a document
  too; `uploaded_by_id` can differ (a CA uploading a client's acknowledgement). A file can serve several filings
  through `compliance_item_documents`.
- **Engagement statuses without "accepted":** `requested → active` when the CA takes the listed price, or
  `requested → quoted → active` when the business accepts a quote; plus `declined`, `expired`, `cancelled`,
  `completed`. A business may have several CAs at once.
- **One open engagement per filing:** a compliance item is in at most one `requested`, `quoted` or `active`
  engagement. The database cannot enforce this (the status is on the engagement); the marketplace service will.
- **Content stays in files:** explanations, instructions and checklists live in `content/forms/<FORM>/`; rows store
  keys only (`checklist_key`). The admin edits rules, templates, penalty rules and the service catalog.
- **Soft delete vs UNIQUE:** a soft-deleted row still counts for a plain UNIQUE. Pure link or one-off rows
  (`checklist_ticks`, `compliance_item_documents`, `ratings`) are deleted normally; `businesses (user_id)` and
  `compliance_items (business_id, form_code, period_start)` use partial unique indexes on live rows
  (`WHERE deleted_at IS NULL`). CLAUDE.md rule 6 says so.
- **Aman's marketplace names stay:** `about` (the bio), `capacity` (max active clients), `cop_number`,
  `years_experience`, class `CatalogService` with `unit` and `sort_order`. Only columns were added.
  `CaProfile.user` now names its foreign key, because `verified_by_id` is a second link to `users`.
- **No seed data in this PR** (exception to "new table → seed data"): the reference tables hold legal values
  (thresholds, due-date rules, penalties) that must not be invented, and the NIC list must be imported from the
  official source. Each module seeds its own tables when it is built.
- `notifications` belongs to alerts (it was planned under core-infra). The array-code CHECK helper moved to
  `models/enums.py` as `only_codes()`. `terms_accepted_at` stays empty until signup sets it (a later task).
- New packages: `cryptography==50.0.1`, `pgvector==0.5.0` (no other dependencies). The migration and the test
  fixtures create the Postgres extension `vector`.

**Why:** the team builds modules in parallel; with every table, relationship and status agreed first, modules no
longer race to add migrations or disagree on names, and the access rules can be written down once.

## 2026-09-26: CA price menu and typical price range (computed, never stored)

**What**
- A fixed **service catalog** (`service_catalog`, 13 seeded services, each with a unit such as "per return" or
  "per month") that every CA prices against, so prices are comparable. The admin editor comes later.
- Each CA sets a price per service they offer (`ca_services`, `Numeric(12,2)` rupees, 1 to 10,00,000). The menu is
  saved as a whole (`PUT /api/v1/marketplace/ca-services`); unticked services are soft-deleted. Changing prices
  does not send the profile back for verification. Prices are independent of the specialization tags.
- The **typical range** (min / median / max) is **computed on each request** from the prices of verified CAs with
  live accounts. It replaces the planned stored `typical_min` / `typical_max` columns.
- A range is shown only once **3 CAs** offer the service (`MIN_CAS_FOR_RANGE`); below that, "Not enough data yet".
- **Median**, not average. Prices are shown as the CA's listed fee, with no claim about GST.

**Why:** typed-in "typical" prices would be invented numbers (the spirit of CLAUDE.md rule 3); computed ones always
match what CAs actually charge. With one or two CAs a range says little and could reveal a single CA's fee. The
median is not pulled up by one very expensive CA and is easy to explain ("the middle price").

## 2026-09-26: CA profiles: array columns for tags, CoP number instead of an upload (for now)

**What**
- `ca_profiles` (marketplace) holds a CA's practice profile and `verification_status` (`pending` / `verified` /
  `rejected`). Only `verified` CAs are listed for businesses (`GET /api/v1/marketplace/cas`).
- **Specializations and languages are Postgres arrays of codes** (`varchar[]`), not join tables. A CHECK
  (`<@` "is contained in") accepts only the listed codes; "CAs for ITR" is `specializations @> ARRAY['itr']`, with
  a GIN index. Specializations are the seven tracked forms plus six broader areas (`docs/DATA_MODEL.md`).
- **The CA types the Certificate of Practice number**; the certificate upload (encrypted storage, OCR) comes later.
- A new profile is `pending`. A verified or rejected CA who changes the membership or CoP number goes back to
  `pending`; a rejected CA who saves again goes back to `pending`; other edits keep `verified`.
- ICAI membership number: 6 digits, unique across CAs. The CoP number is free text (1–20 characters): we do not
  assume a format.
- The shared pagination shapes (`app/schemas/pagination.py`) arrived with the CA list.
- `make seed` gives the demo CA a verified profile and adds four sample verified CAs
  (`sample-ca-N@demo.local`, random passwords nobody knows, fictional membership numbers 900000–900004).

**Why:** tags are plain codes with no data of their own, so an array column is one table, one filter and easy to
explain; a join table is only worth it once a tag needs its own data. The upload was postponed to keep this task
small; the admin verification screen is a separate task, so until then a CA is verified by `make seed` or by
hand in the database.

## 2026-09-26: Workflow commands (make doctor / feature / sync / check / pr / merge)

**What**
- `scripts/workflow.sh` with one subcommand per step, called by five new Make targets; no existing target changed.
  `make feature` (latest main, sync, new branch), `make sync` (after a pull), `make check` (before pushing),
  `make pr` (check, push, open the PR), `make merge` (squash-merge when CI is green and a teammate approved).
- `make sync` reinstalls packages only when `environment.yml`, `backend/requirements*.txt` or
  `frontend/package-lock.json` changed since the last install. It remembers a fingerprint of those files
  (`git hash-object`) in `.git/`, so nothing new is committed or gitignored.
- `make check` adds two migration checks CI does not have: exactly one Alembic head, and `flask db check` (fails
  when a model changed without a migration).
- `make doctor` checks git, the conda env (Python 3.12, Node 22), packages, `.env`, Docker, the database's
  migration and the dev servers, changes nothing, and prints a fix for every problem.
- Every failure prints `ERROR in step "<step>"` with the fix. Known causes get specific advice: Docker not running,
  a database migration the branch does not know, Postgres unreachable, a port taken, uncommitted changes, main
  moved on, CI pending or failed, missing approval, requested changes, conflicts. Anything else names the step and
  points to `make doctor`.
- `make merge` merges only without conflicts, with green CI, at least one approval and no open "changes requested";
  always as a squash, deleting the branch.
- These commands are the team's workflow for every task; `CLAUDE.md` "Session checklist" and the README "Team
  workflow" describe it. The pull request template ticks `make check` instead of lint, test and build separately.
- The scripts never force-push, pull only fast-forward, refuse to switch branches with uncommitted changes, and only
  warn about variables missing from `.env` (they never edit it). They use `git`, `gh` and `make`, which we already use.

**Why:** the team asked for one set of commands that gets a feature from a branch to main and onto everyone's
machine without breaking anything. The usual failures were a missing migration, a missed package install, a stale
`.env` and Docker not running; each step now checks for those.

## 2026-09-26: Signup, email OTP and passwords

**What**
- **Signup** creates only `business` and `ca` accounts. A new account starts with `users.email_verified_at` empty
  and cannot log in (403 `EMAIL_NOT_VERIFIED`) until the user enters the 6-digit code we emailed. Verifying does
  not log the user in: they log in with their password afterwards. The migration marks existing users verified;
  seeded demo users are created verified.
- **One-time codes** live in `email_otps`: 6 random digits stored only as an argon2 hash (the same
  `hash_password()` as passwords), valid 10 minutes and 5 wrong guesses. Only the newest code per user and purpose
  counts. At most one new code a minute per account; extra requests are ignored silently. A wrong guess is
  committed before the 400 is raised, the one place a service commits before an error.
- **Password rule:** 8 to 128 characters with at least one letter and one number (signup, reset, change), checked
  in `backend/app/schemas/auth.py` and `frontend/src/lib/authRules.js`.
- **No account enumeration where it is cheap:** resend and forgot-password always answer 204; verify and reset give
  the same `OTP_INVALID` for an unknown email as for a wrong code. Signup still answers 409 `EMAIL_TAKEN`.
- **Password reset** also verifies an unverified email (the code proves ownership). Reset and change both send a
  "password was changed" email. A wrong current password is 400 `WRONG_PASSWORD`, not 401, because any 401 logs
  the frontend out.
- **Email:** `send_email()` in `app/utils/email.py` uses the standard library (`smtplib`, `EmailMessage`) and
  Flask's Jinja `render_template` on plain-text files in `app/templates/email/`. No new package. It runs inside
  the request (not the worker), logs a failure without the address and never raises. Tests set
  `MAIL_SUPPRESS_SEND` and read `app.utils.email.outbox`. New `.env` variables: `MAIL_SERVER`, `MAIL_PORT`,
  `MAIL_DEFAULT_SENDER`; no TLS or SMTP login yet (Mailpit needs neither).
- **Frontend:** plain async functions in `api/auth.js` (no TanStack mutations; the forms use React Hook Form's
  `isSubmitting`, like the login page). The email moves between pages in the router's location state, never in the
  URL. `FormCard` and `FormField` components keep the six account forms short. Change password lives at
  `<area>/change-password` in every role's area, linked from the sidebar.

**Why:** the smallest flow that is safe enough to explain in the viva: codes rather than emailed links (no frontend
URL setting, nothing to click in the wrong browser), no new dependencies, and every rule in one place in
`auth_service.py`.

## 2026-09-26: Simplified for explainability

**What**
- **New rule in `CLAUDE.md`, "Simplicity first":** build the simplest thing that works and is explainable in 1–2
  sentences; no infrastructure, tooling or abstraction layers without asking.
- **Logging:** `logging.basicConfig` with `LOG_LEVEL` in `create_app()`. Gone: the JSON format and `LOG_FORMAT`,
  request IDs (`X-Request-ID`, `request_id` in error bodies, `requestId` in the frontend), the custom access log
  (the dev server's own request lines are back) and the worker's `job` log field (APScheduler logs each job by name).
- **Removed:** ProxyFix and `TRUST_PROXY`; full-Docker mode (both Dockerfiles and `.dockerignore`s, `nginx.conf`,
  gunicorn and `gunicorn.conf.py`, the worker heartbeat and `--healthcheck`, the CI docker job, `make up/down/logs`;
  `docker-compose.yml` keeps `db` and `mailpit`); mypy; pre-commit; flask-cors and `CORS_ORIGINS` (Vite forwards
  `/api`, so the browser talks to one origin); `ProductionConfig`; `DEV_SERVER_DEBUG` (`make dev-backend` now runs
  `python main.py`, like the manual mode); `RATELIMIT_STORAGE_URI` (fixed to `memory://`); every `.env` variable
  nothing read yet; `make test-backend` / `test-frontend` (`make test` runs both).
- **Tests:** the tables are created once per session and the `database` fixture deletes every row after each test,
  in reverse foreign-key order. No outer transaction, savepoints or `db.session` swap.
- **Dependencies: only what the code imports.** Python: removed pgvector, cryptography, google-genai, pytesseract,
  PyMuPDF, pdfplumber, opencv-python-headless, requests, beautifulsoup4, feedparser, gunicorn, Faker, mypy and
  pre-commit. Each feature adds its own packages when it lands; for PDFs that is PyMuPDF only (never pdfplumber as
  well, no OpenCV). `tesseract` left `environment.yml`, together with the Tesseract smoke test, the
  `requires_tesseract` marker and the CI install. npm: removed FullCalendar, recharts, lucide-react, openapi-fetch
  and `cn` (shadcn's clsx + tailwind-merge replacement); `lib/utils.js` is the standard shadcn `cn()` built on
  clsx + tailwind-merge, and `shadcn` is a devDependency. A calendar or chart library is chosen (ask first) when
  its page is built.
- **Frontend API client:** one `apiFetch(path, {method, body})` in `api/client.js` (adds the token, parses JSON,
  throws `ApiRequestError` with `code` and `message`, logs out on a 401) replaces openapi-fetch, `unwrap()` and the
  AuthProvider middleware. `lib/labels.js` keeps only the role labels.
- **Tooling and docs:** `scripts/setup_dev.sh` is ~50 lines (no conda → print the Miniforge command and stop;
  otherwise env, `npm ci`, `.conda-env` link, `.env` with random secrets). `docs/WORKFLOW.md` is merged into
  `CLAUDE.md`. `docs/PATTERNS.md` covers only patterns with code behind them.
- **Unchanged:** every endpoint and response (except the dropped `request_id`), error code, table, migration and
  the login flow.

**Why:** every file must be explainable in the viva by a team of three. Most of what went served a deployment we
do not run (Docker images, nginx, gunicorn, proxy headers, JSON logs) or features that do not exist yet (their
packages and settings); the rest (mypy, pre-commit, the openapi-fetch middleware, the savepoint fixture) needed
long explanations for little benefit at this size.

**Supersedes:** "JSON logs and request IDs" and "mypy in lenient mode" (2026-09-25); the savepoint fixture in
"Service-level transactions"; openapi-fetch in "Frontend in plain JavaScript"; the `api.use()` middleware,
`unwrap()` and `DEV_SERVER_DEBUG` in "Basic login, role areas and manual run mode"; the pre-commit hooks and the
frontend Docker image in "Node.js comes from the conda env"; FullCalendar, nginx, `cn`, pre-commit, port 8080, the
Tesseract CI step and the CI docker job in "Initial bootstrap".

## 2026-09-26: Frontend in plain JavaScript, not TypeScript

> **Partly superseded (2026-09-26, "Simplified for explainability"):** openapi-fetch is gone; calls use `apiFetch()`.

**What**
- Every frontend file is `.js` / `.jsx` (types stripped mechanically, comments kept). `tsconfig*.json` is replaced
  by a small `jsconfig.json` (editor support for the `@/` alias only); shadcn `components.json` has `"tsx": false`.
- Removed: `typescript`, `typescript-eslint`, `@types/*`, `openapi-typescript`, the `typecheck` and `gen:api` npm
  scripts, `make gen-api`, `src/api/generated/`, and the CI/Docker steps that generated or checked types. The
  frontend CI job no longer waits for the backend job.
- Kept: **openapi-fetch** as the API client (same `api.GET("/api/v1/...")` calls, now untyped), `unwrap()`,
  Zod for form validation. Swagger at `/api/docs` is the reference for request/response fields. CI still checks
  that the OpenAPI spec builds.

**Why**
- All three team members know JavaScript/JSX but not TypeScript; the code has to be explainable in the viva.
  TypeScript was generated by mistake.
- Trade-off accepted: a renamed backend field is no longer caught at build time, only by tests or at runtime.
  Keep every API call in `api/<module>.js` so a schema change means checking one place.
- Supersedes "TypeScript 5.9", "openapi-fetch: typed client" and "Generated API types are not committed" in the
  2026-09-25 entry; `.ts`/`.tsx` paths in older entries now end in `.js`/`.jsx`.

## 2026-09-26: Folders by layer instead of by module; explicit registration

**What**
- **Backend `app/` is organised by layer:** `models/`, `schemas/`, `services/` (`<module>_service.py`),
  `routes/`, `utils/`, plus `config.py`, `extensions.py`, `errors.py`, `seed.py` at the top. All tests are in
  `backend/tests/` with `tests/conftest.py`. A module is the set of same-named files across the layers. Files are
  created only when they have code (the empty per-module stubs are gone).
- **Frontend `src/` is organised by layer:** `api/`, `pages/` (`business/`, `ca/`, `admin/`), `components/`,
  `context/`, `hooks/`, `lib/`, and one route table `src/routes.jsx`.
- **Registration is explicit, no auto-discovery:** `BLUEPRINTS` in `app/routes/__init__.py`, every model imported
  in `app/models/__init__.py`, `SEEDS` in `app/seed.py`, jobs in `build_scheduler()` (`worker.py`), pages and
  sidebar links (`NAV`) in `src/routes.jsx`. Supersedes "Module auto-discovery" and "Frontend route aggregation"
  (bootstrap entry) and `ROLE_LAYOUTS` / `AREA_PREFIX` (login entry).
- **Merged small files:** `cli.py` into `seed.py`; `request_id.py` into `utils/logging_setup.py`; `core/db/base.py`
  (`Base`, naming convention) into `extensions.py`; `core/api/errors.ts` into `api/client.js`; the three role
  layouts into `AppShell` (takes the role); `AreaIndexPage` removed (every area has a dashboard).
  `issue_access_token()` moved from `tokens.py` to `services/auth_service.py`; the heartbeat job id is now
  `worker.heartbeat`; `flask seed` prints `Seeded: demo users`.
- **Unchanged:** every URL, response, error code, table, migration, env variable, Make target, Docker and CI
  step, and all behaviour (request IDs, JSON logs, ProxyFix, heartbeat). `flask db check` reports no schema change.

Older entries below name files by their old paths. Old → new:

| Old | New |
|---|---|
| `app/core/auth/{models,routes,schemas,services}.py` | `app/models/user.py`, `app/routes/auth.py`, `app/schemas/auth.py`, `app/services/auth_service.py` |
| `app/core/auth/tokens.py`, `app/core/auth/seed.py`, `app/cli.py` | `app/utils/jwt_handlers.py`, `app/seed.py` |
| `app/core/permissions.py`, `app/core/security/passwords.py` | `app/utils/decorators.py`, `app/utils/passwords.py` |
| `app/core/db/{base,models,enums}.py` | `app/extensions.py` (`Base`), `app/models/base.py`, `app/models/enums.py` |
| `app/core/{errors,health}.py` | `app/errors.py`, `app/routes/health.py` |
| `app/core/{logging_config,request_id}.py` | `app/utils/logging_setup.py` |
| `app/modules/<m>/{routes,schemas,services}.py`, `.../tests/` | `app/routes/<m>.py`, `app/schemas/<m>.py`, `app/services/<m>_service.py`, `tests/test_<m>_*.py` |
| `app/core/{ai,ocr,storage,...}` (planned) | `app/utils/{gemini_client,ocr,storage,...}.py` (planned) |
| `backend/conftest.py` | `backend/tests/conftest.py` |
| `frontend/src/core/api/`, `core/auth/`, `core/layout/`, `core/components/` | `src/api/`, `src/context/` + `src/hooks/` + `src/lib/session.js`, `src/components/` |
| `frontend/src/core/{routes.tsx,labels.ts,query-client.ts}` | `src/routes.jsx`, `src/lib/labels.js`, `src/lib/queryClient.js` |
| `frontend/src/features/<m>/{pages,api.ts,routes.tsx}` | `src/pages/<role>/`, `src/api/<m>.js`, entries in `src/routes.jsx` |

**Why:** the per-module folders held mostly empty placeholder files, and auto-discovery hid which routes and pages
exist. The layer-first layout is the one most Flask and React tutorials use, so each file is easy to find and to
explain in the viva. One file per module per layer keeps the modules separate.

## 2026-09-25: Basic login, role areas and manual run mode

> **Partly superseded (2026-09-26, "Simplified for explainability"):** `apiFetch()` replaces `unwrap()` and the middleware; `make dev-backend` runs `python main.py`, so `DEV_SERVER_DEBUG` is gone.

**What**
- **Business area URL is `/business`** (was `/app`), so each role's area matches its name: `/business`, `/ca`,
  `/admin`. `AREA_PREFIX.business` in `frontend/src/core/routing.ts`; supersedes "`business` /app" in the
  bootstrap entry. Frontend contract change.
- **Area home endpoints stay module-owned**: `GET /api/v1/compliance/dashboard` (business),
  `/api/v1/ca-workspace/dashboard` (CA), `/api/v1/admin/dashboard` (admin), named for what they will become. No
  exception to `/api/v1/<module>/...`. Frontend pages: `BusinessDashboardPage`, `CaDashboardPage`,
  `AdminDashboardPage`, each registered as its area's `index` route by its module.
- **Access token only, in localStorage**, for this prototype (TODO in `frontend/src/core/auth/session.ts`: move to
  an httpOnly refresh-token cookie). Lifetime `JWT_ACCESS_TOKEN_MINUTES` (default 60).
- **Roles are checked against the database** in `roles_required`, not only the JWT claim; the JWT user loader
  rejects deactivated/deleted users on every request with **401 `ACCOUNT_INACTIVE`** (401, so the frontend logs
  out). Login itself returns 403 `ACCOUNT_INACTIVE`, and only after a correct password.
- **Unknown email and wrong password are indistinguishable**: same 401 `INVALID_CREDENTIALS`, and an unknown email
  still costs one argon2 verify (against a cached dummy hash). Outdated argon2 hashes are rehashed on login.
- **Bearer auth is the OpenAPI global default** (`API_SPEC_OPTIONS["security"]`); public endpoints opt out with
  `@blp.doc(security=[])` (health, login).
- **`users` and `UserRole` live in core** (`app/core/auth/`, `app/core/db/enums.py`); the demo-user seed is a core
  seed that `run_all_seeds()` runs before the module seeds.
- **Rate limiting stays on in tests**; `backend/conftest.py` resets the in-memory counters before each test.
  (With `RATELIMIT_ENABLED=False` Flask-Limiter registers no hooks, so the limit could not be tested.)
- **Login email is a plain string, not `fields.Email`**: the service trims and lowercases it, and a malformed
  email simply matches no user (401). The frontend validates the format with Zod.
- **Manual run mode:** `backend/main.py` (not `app.py`, which would shadow the `app` package) runs Flask's dev
  server on 127.0.0.1:8000 with debugger/reload from `DEV_SERVER_DEBUG` (on only in development), for people
  running `conda activate ca-helper && python main.py` by hand. Make targets, Docker and CI are unchanged, and
  scripts/Claude still use `conda run` or Make.
- **API client:** `baseUrl` is the page origin (no path) instead of `""`, and `fetch` is looked up per call, so
  frontend tests running in Node can build requests and stub `fetch`. Browser behaviour is the same.
- **shadcn `input` and `label`** added (no new npm packages).
- **One frontend error type:** every API call goes through `unwrap()` (`frontend/src/core/api/errors.ts`), which
  throws `ApiRequestError` (`status`, `code`, `message`, `requestId`); pages show `errorMessage(error)` and switch on
  `code` when needed. No per-feature error classes.
- **`login_required`** (any role) next to `roles_required`; the role areas in `frontend/src/core/routes.tsx` are
  built from one `ROLE_LAYOUTS` map, so a new role/area is one entry plus its layout.
- **Health:** a database outage logs one warning line (no traceback) and the landing badge says "API up,
  database unavailable" instead of "unreachable".
- **`GET /` on the API redirects to `/api/docs`** instead of a 404 JSON, since people open the API's root URL.

**Why:** a working login for all three roles is the base every later feature builds on; module-owned URLs keep
the "grep the module segment" rule without exceptions; the DB role check and 401-on-deactivation make an admin's
suspension take effect immediately; the manual mode is the simplest way to explain and demo the app.

## 2026-09-25: Node.js comes from the conda env

> **Partly superseded (2026-09-26, "Simplified for explainability"):** there are no pre-commit hooks or Docker images any more.

**What:** `environment.yml` installs `nodejs=22` (conda-forge) next to Python and Tesseract. Every node/npm command
runs through `conda run -n ca-helper` (Makefile `NPM` variable, pre-commit ESLint/Prettier hooks, `make setup`).
`.nvmrc` and all nvm instructions are removed. CI uses `actions/setup-node` with `node-version: "22"` (as it uses
pip, not conda, for Python) and the frontend Docker image stays on `node:22-alpine`. `package.json` `engines`
(`>=22.22`) with `engine-strict=true` remains the floor. Supersedes the `.nvmrc` point of the bootstrap entry.

**Why:** one tool (conda) now provides every runtime, so a fresh laptop needs only conda, Docker, git and make, and
everyone runs the same Node version without per-user nvm setups.

## 2026-09-25: JSON logs and request IDs

> **Superseded (2026-09-26, "Simplified for explainability"):** plain `logging.basicConfig`, no request IDs.

**What:** every request gets an ID: a valid incoming `X-Request-ID` (1–128 chars of `A-Za-z0-9._-`) is reused,
otherwise a UUID hex is generated (`app/core/request_id.py`). It is returned in the `X-Request-ID` header, added to
every log line and to every error body (`error.request_id`). The API logs one access line per request itself
(Werkzeug's and gunicorn's access lines are off). Logs are readable text by default and one JSON object per line
when `LOG_FORMAT=json` (set in docker-compose); the formatter is hand-written (`app/core/logging_config.py`), no
new dependency. gunicorn uses the same config (`backend/gunicorn.conf.py`). Worker log lines carry the job id in a
`job` field. `LOG_LEVEL` sets the level.

**Why:** a user or teammate can quote the request ID from an error and find every related log line; JSON lines
in Docker are searchable with `jq`, while text stays readable in a hybrid-mode terminal.

## 2026-09-25: Service-level transactions

> **Partly superseded (2026-09-26, "Simplified for explainability"):** services still commit once; tests now delete every row after each test instead of rolling back a savepoint transaction.

**What:** routes parse input, call one service function and serialize the result; they never touch `db.session`.
Each public service function is one unit of work and commits once at its end; helpers composed by other service
functions do not commit and say so. Models hold data only. Tests wrap each test in one outer transaction with
SQLAlchemy 2.0 `join_transaction_mode="create_savepoint"`, so service commits only release savepoints and are
rolled back after the test. Flask-SQLAlchemy 3.1's `Session.get_bind()` ignores a session-level bind, so the
`database` fixture in `backend/conftest.py` (and only it) temporarily replaces `db.session` with a plain scoped
session bound to the test connection. This replaces the old "delete all rows after each test" cleanup.

**Why:** one obvious place where data is committed makes behaviour easy to reason about and explain; tests can
call real services (which commit) and still stay isolated and fast.

## 2026-09-25: mypy in lenient mode

> **Superseded (2026-09-26, "Simplified for explainability"):** mypy is removed.

**What:** `mypy==2.3.1` (dev dependency) runs in `make lint` and CI over `app`, `tests`, `worker.py` and
`conftest.py`. Lenient: only annotated functions are checked (`check_untyped_defs = false`) and missing third-party
stubs are ignored (`ignore_missing_imports = true`); config in `backend/pyproject.toml`. Where mypy cannot see
Flask-SQLAlchemy's runtime `db.Model`, `app/core/db/models.py` uses a `TYPE_CHECKING` alias to our `Base`.
The frontend already has TypeScript `"strict": true` (both tsconfigs).

**Why:** catches wrong types in the code we annotate without forcing annotations everywhere at once; it can be
tightened per module later.

## 2026-09-25: API routes under /api/v1

**What:** every module route is under `/api/v1/...`, added centrally by `register_blueprints()` (module blueprints
set no `url_prefix`). `/api/health`, `/api/docs` and `/api/openapi.json` stay unversioned for healthchecks and
tooling. The Vite proxy and nginx already forward all of `/api/`. The frontend client keeps `baseUrl: ""` because
the generated paths already contain `/api/v1`. Supersedes "No `/v1` in URLs" in the bootstrap conventions.

**Why:** a later breaking change can live at `/api/v2` next to v1 without moving the infrastructure endpoints that
Docker, CI and the status badge depend on.

## 2026-09-25: Enums stored as text with a CHECK constraint

**What:** Python `StrEnum`s with lowercase snake_case values, mapped with `str_enum()` (`app/core/db/enums.py`):
SQLAlchemy `Enum(native_enum=False, create_constraint=True, values_callable=values, validate_strings=True,
length=50)`. The database stores the value, never the member name, and a named CHECK constraint
(`ck_<table>_<enum>`) rejects anything else. The API sends the same codes; display labels live only in
`frontend/src/core/labels.ts` and the code → label tables in `docs/DATA_MODEL.md` ("Status values", rewritten
from display strings to codes: e.g. `docs_pending` → "Docs pending").

**Why:** Postgres ENUM types are awkward to change in migrations; text + CHECK gives the same safety with a
simple constraint swap, and stable machine codes keep display wording out of the database and API.

## 2026-09-25: UUID primary keys

**What:** every model subclasses `BaseModel` (`app/core/db/models.py`): `id` is a UUID (uuid4 generated in
Python, stored as Postgres `uuid`), plus `created_at`/`updated_at` (timezone-aware UTC, DB default `now()`).
`SoftDeleteMixin` (`is_active`, `deleted_at`) is opt-in for user-facing rows. The existing MetaData naming
convention (ix, uq, ck, fk, pk) stays, so Alembic gets stable constraint names.

**Why:** IDs in URLs cannot be guessed or counted (e.g. how many businesses exist), rows can be created in seeds
and tests without a DB round-trip for the key, and one base class gives every table the same key and timestamps.

## 2026-09-25: No in-repo ownership or task tracking

**What**
- Tasks are assigned and split among the team outside the repo. The repo no longer records who owns which
  module, which phase we are in, or which tasks are open.
- Removed: the ownership and phases docs, `docs/prompts/`, the `content` and `finish` module trackers, the progress
  tracker script (`scripts/progress.py`) with its tests, its three Make targets and the two CI steps that ran it,
  the import of each member's personal identity file in `CLAUDE.md`, and member letters, task IDs and owner fields
  in docs, `content/` front matter, `eval/` READMEs and code comments. `git log` has the exact files.
- Module docs have eight sections: Purpose · What exists now · Tables · Endpoints · Service functions other modules
  call · Depends on · Contracts (don't change without telling the team) · Known issues.
- Compliance item and engagement status values now live in `docs/DATA_MODEL.md` ("Status values"), their one
  authoritative home.
- Branches are named `<name>/<module>-<short-task>`. Anyone may change any file; a PR that touches shared code, shared
  config or another module, or changes a contract, says so clearly.
- The frontend `ModulePlaceholder` no longer shows an owner or task IDs.
- Supersedes two points of the bootstrap entry below: CI no longer checks tracker lines, and ruff covers
  `backend/` only (no Python is left in `scripts/`).

**Why:** the team splits work in person, so an in-repo tracker and ownership rules were a second source of truth
to keep in sync. Everything technical (stack, rules, conventions, run modes) is unchanged.

## 2026-09-25: Initial bootstrap

> **Partly superseded (2026-09-26, "Simplified for explainability"):** no full-Docker mode (nginx, gunicorn, port 8080, CI docker job), pre-commit, `cn`, FullCalendar or Tesseract CI step.

**Stack and versions**
- **Stack as specified in the bootstrap prompt**; direct dependencies pinned exactly in
  `backend/requirements*.txt` and `frontend/package.json` (`.npmrc` has `save-exact=true`).
- **Node 22 LTS, not 20.** react-router 8, vitest 5 and jsdom 30 require Node ≥ 22.12 to 22.22. Enforced by `.nvmrc`
  (`22`), `package.json` `engines` (`>=22.22`) and `engine-strict=true`.
- **TypeScript 5.9, not 7.** typescript-eslint (peer `<6.1`) and openapi-typescript (peer `^5`) do not support TS 7 yet.
- **SQLAlchemy 2.0.x, not 2.1.** Flask-SQLAlchemy 3.1.1 predates SQLAlchemy 2.1.
- **FullCalendar 6.1, not 7.** v7 is a new headless rewrite whose plugin packages are not released for it; 6.1 is
  stable and well documented.
- **APScheduler 3.x** (`BlockingScheduler`, in-memory job store). Jobs are re-registered at worker start, so
  nothing needs to be persisted.
- **Gemini defaults:** `GEMINI_MODEL=gemini-3.8-flash`, `GEMINI_EMBED_MODEL=gemini-embedding-001` (current names
  on the Gemini models page on this date; change them in `.env` only).

**Approved small additions** (asked and approved)
- **python-dotenv**: `app/config.py` loads the root `.env`, so hybrid mode, the worker and pytest share it.
  Existing environment variables win (Docker/CI values are never overridden).
- **openapi-fetch**: typed client over the openapi-typescript types (`frontend/src/core/api/client.ts`).
- **nginx:alpine** serves the built frontend in full-Docker mode and proxies `/api` to the backend.
- shadcn/ui's own **`cn`** package (a clsx + tailwind-merge replacement), installed by `shadcn init`.

**Structure and conventions**
- **Shared pytest fixtures live in `backend/conftest.py`** (not `backend/tests/conftest.py`). pytest applies a
  conftest only to its own folder, and module tests live in `app/modules/<module>/tests/`.
- **Blueprints use `url_prefix="/api"`** and every route spells out its module segment (`/compliance/...`,
  `/admin/compliance/...`), so admin routes can live in the owning module's blueprint.
- **Module auto-discovery** (`app/modules/__init__.py`): each package exposes `blp`, optional `seed()`,
  `SEED_ORDER` (default 100) and `register_jobs(scheduler)`. `flask seed` commits once after all seeds.
- **Error format** `{"error": {"code", "message", "details?"}}` for every error, via a `flask_smorest.Api`
  subclass (`CaHelperApi`) plus an `ApiError` exception. Unhandled exceptions still show the debugger in dev and
  tracebacks in tests.
- **JSON is snake_case, money is a decimal string, timestamps are UTC ISO 8601** (docs/API_CONVENTIONS.md).
- **Worker cron times are Asia/Kolkata.** Every job is wrapped to run inside the Flask app context.
- **Alembic migration file names are date-prefixed** (`migrations/alembic.ini` `file_template`) so they sort in
  time order across members.
- **Frontend route aggregation** via `import.meta.glob("../features/*/routes.tsx")`. Each feature exports
  `routes: FeatureRoutes` keyed by area (`public`, `business` /app, `ca` /ca, `admin` /admin) with nav items.
- **shadcn/ui** initialised with the `radix-nova` preset; components live in `src/core/components/ui/`
  (`components.json` aliases point there).
- **Ruff config is one root `ruff.toml`** (backend and scripts share it); pytest config stays in `backend/pyproject.toml`.

**Environment and tooling**
- **Ports:** backend 8000 (macOS uses 5000 for AirPlay), Vite 5173, full-Docker frontend 8080, Postgres 5432
  (`DB_HOST_PORT`), Mailpit 1025/8025.
- **Generated API types are not committed**, so the frontend needs `make gen-api` before typecheck/build.
  The Makefile targets `dev-frontend`, `test-frontend`, `lint` and `up` run it first; `make setup` runs it once;
  CI passes the spec from the backend job to the frontend job.
- **VS Code interpreter:** `make setup` creates a gitignored `.conda-env` symlink to the env, and
  `.vscode/settings.json` points to `${workspaceFolder}/.conda-env/bin/python`. No user-specific paths.
- **Pre-commit Python hooks run ruff through `conda run -n ca-helper`** (local hooks), so they use the pinned
  version. Generic hooks come from `pre-commit/pre-commit-hooks`.
- **`make setup` also writes random dev secrets** (SECRET_KEY, JWT_SECRET_KEY, FIELD_ENCRYPTION_KEY,
  BLIND_INDEX_KEY) into a new `.env`, and generates API types at the end.
- **Any conda distribution works** (Miniforge recommended; Miniconda/Anaconda accepted). `environment.yml` uses
  `conda-forge` + `nodefaults`, so the `defaults` channel is never used.
- **CI** has three jobs: backend (ruff, tracker `--strict`, migrations, pytest with Postgres + Tesseract, OpenAPI
  export) → frontend (gen types, lint, format, typecheck, test, build) → docker (build all images, start
  full-Docker mode, smoke-test through nginx).
- **Git history** starts with one empty root commit on `main` (the GitHub repo was empty), so the bootstrap can be a
  normal PR from `chore/phase-0-bootstrap`.
