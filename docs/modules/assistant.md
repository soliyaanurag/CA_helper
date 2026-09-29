# assistant: AI assistant (Gemini RAG with citations)

## Purpose
The floating assistant for business owners and CAs: answers through the PII-scrubbing Gemini wrapper, RAG over our
own content and official FAQs with citations, category-level profile awareness and an "Ask a CA" hand-off.

## What exists now
AS1–AS5 work (B3).
- **Knowledge base (AS1):** `assistant_service.ingest_knowledge()` (`flask assistant ingest` / `make assistant-ingest`)
  reads `content/forms/<FORM>/explanation.md` + `instructions.md` (our guides, reviewed against official pages) and `content/faqs/*.md`
  (official FAQ pages copied word for word, with their source URL: nil GSTR-3B, nil GSTR-1, IFF under QRMP and
  GSTR-2B from the GST portal user manual; returns for business / profession income from incometax.gov.in). Pages are
  cut into chunks of whole sections, at most `MAX_CHUNK` = 1500 characters (long sections at blank lines); writers'
  `<!-- -->` notes and front matter are removed. Each chunk is embedded as "title + text" with
  `gemini_client.embed_texts` (768 numbers). Only new or changed chunks are embedded; chunks whose text is gone are
  deleted (kb_chunks is reference data). Needs `GEMINI_API_KEY`; without it, 503 `GEMINI_UNAVAILABLE` and nothing
  changes. Today: 80 chunks (22 from the guide pages, 58 FAQ chunks).
- **Search (AS2):** the question is embedded (`RETRIEVAL_QUERY`) and pgvector finds the `TOP_K` = 5 closest chunks by
  cosine distance, **only those within `MAX_DISTANCE` = 0.40** (measured on our content: on-topic questions
  0.21–0.37, off-topic ones 0.44 and more). Without Gemini: the chunks sharing the most words with the question.
- **Answer (AS2):** `answer_question(question, context)` does the work and saves nothing (also used by
  `eval/assistant/evaluate.py`); `ask(user, question)` calls it with `user_context(user)` and saves both messages.
  In detail, Gemini gets `PROMPT` (answer only from the numbered sources, cite them as
  [n], plain English, no amount / rate / limit / date that is not in the sources, "ask_a_ca" when a professional is
  needed), the user context and the chunks, and replies with JSON `{answer, sources, ask_a_ca}`; cited numbers
  outside the sources are dropped (numbers written in the text are picked up too). Nothing relevant found → "I could
  not find this ..." without asking Gemini. Gemini failing (503 high demand, 429 quota) → the found passages are
  shown instead (`ai_used: false`; each citation has its `excerpt`).
- **User context (AS3):** `user_context(user)` = categories only: entity type, MSME tier, GST scheme, ITR form,
  presumptive / audit yes-no, TDS returns and the next three filings (form, period, due date). Never a name, email,
  PAN, GSTIN, address or amount; the question itself is scrubbed by `gemini_client` (rule 1). A CA gets "The user is
  a Chartered Accountant ...".
- **Ask a CA (AS4):** true when Gemini says so, or the question mentions notice, penalty, appeal, scrutiny, demand,
  refund, assessment, dispute, ... (`ASK_A_CA_WORDS`). The chat then links business owners to the marketplace.
- **History (AS5):** each question and answer is a `chat_messages` row; `list_history(user)` returns the last 50,
  oldest first; `clear_history(user)` soft-deletes them.
- **Backend files:** `services/assistant_service.py`, `routes/assistant.py`, `schemas/assistant.py`;
  `gemini_client.embed_texts`; `GEMINI_EMBED_MODEL` in `config.py` and `.env.example`; `make assistant-ingest`.
- **Frontend:** `components/AssistantWidget.jsx`: the round "AI" button at the bottom right of every page for
  business owners and CAs (added by `AppShell`; not for admins; hidden on the full page) that opens a panel;
  `components/AssistantChat.jsx`: the conversation (example questions when empty; answers as Markdown with numbered
  sources: a link for official pages, "(our guide)" for ours, "Show the passage" when the AI could not answer; "This
  may need a professional: ask a CA →" for business owners; Clear); `pages/business/AssistantPage.jsx`: the same
  chat on a full page (`/business/assistant`); `api/assistant.js`.
- **Tests:** `tests/test_assistant.py` (chunks, long pages, ingest only what changed, ingest without Gemini, the real
  content folder, cited sources only, prompt with categories and without PII, CA context, nothing relevant, Gemini
  down → passages, keyword search, Ask a CA from Gemini and from words, history per user + soft clear, routes and
  roles, embeddings scrubbed); frontend `AssistantPage.test.jsx` (ask, sources, passages, Ask a CA, clear, widget
  for business and CA, not for admins, not doubled on the full page).

## Tables
Created by migration `schema: complete data model`. Model file: `backend/app/models/assistant.py`.
- `kb_chunks`: public content only (no FKs, no user data), `embedding vector(768)`; unique (source_path, chunk_index)
- `chat_messages` (SD): per-user history; `citations` of an answer = `{sources, ask_a_ca, ai_used}`

## Endpoints
| Method | Path | Who | Returns |
|---|---|---|---|
| POST | `/api/v1/assistant/ask` | business, CA; 10 per minute | body `{question}` (3–500 characters) → `{answer, citations [{number, title, url, source_path, excerpt}], ask_a_ca, ai_used}` · 422 · 429 |
| GET | `/api/v1/assistant/history` | business, CA | `[{id, role, content, citations, ask_a_ca, ai_used, created_at}]`, oldest first |
| DELETE | `/api/v1/assistant/history` | business, CA | 204 (soft delete) |

CLI: `flask assistant ingest` (`make assistant-ingest`).

## Service functions other modules call
None. It calls `onboarding_service.business_of_user / get_my_business`, `compliance_service.list_filings` and
`gemini_client.embed_texts / ask_gemini`.

## Depends on
core-infra (Gemini wrapper, pgvector), onboarding (category-level profile only, never PII), compliance (the next
filings), marketplace (the "Ask a CA" link).

## Contracts (don't change without telling the team)
- Only category-level profile facts may go into prompts (rule 1); every Gemini call goes through `gemini_client`
- Answers cite only the chunks they were given; kb_chunks holds public text only
- `content/faqs/` files are copied word for word, with `source` and `retrieved` in the front matter

## Known issues
- Our own guides were reviewed on 2026-09-29 (V1) and must be re-checked when the rules change. The official FAQ
  copies are word for word but dated 2026-09-28 and must be refreshed when the official pages change. No official TDS, CMP-08 or current GSTR-4
  FAQs could be downloaded (those pages are built by JavaScript, or outdated), so those answers rest on our guides.
- The free Gemini tier can answer 503 ("high demand") or 429 (quota used up); the chat then shows the passages it
  found.
- Run `make assistant-ingest` after changing `content/` (not automatic; needs the key).
- The keyword fallback finds only words that appear literally (no synonyms).
- `MAX_DISTANCE` was measured on today's content; check it again after adding many pages.
