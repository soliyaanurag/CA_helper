# assistant: AI assistant (Gemini RAG with citations)

## Purpose
The floating assistant for both roles: answers through the PII-scrubbing Gemini wrapper, RAG over our own content and official FAQs with citations, category-level profile awareness and Ask-a-CA handoff.

## What exists now
Skeleton only; no features yet.
- Backend: no code yet (no blueprint, models, schemas or services). Create `routes/assistant.py`, `schemas/assistant.py`, `services/assistant_service.py` (and `models/assistant.py`) when the first feature lands, and add the blueprint to `BLUEPRINTS` (docs/PATTERNS.md).
- Frontend: one placeholder page, "AI assistant" at `/business/assistant` (business nav), `frontend/src/pages/business/AssistantPage.jsx`, built from `Placeholder`; no API hooks yet. The floating widget shell (frontend core) does not exist yet.
- The Gemini wrapper it needs (`app/utils/gemini_client.py`) does not exist yet.

## Tables
None yet. Planned:
- `kb_chunks`: source, title, url, text, `embedding vector(N)` (pgvector)
- `chat_messages`: per-user history

## Endpoints
None yet. Planned: `/api/v1/assistant/...` (ask).

## Service functions other modules call
None yet.

## Depends on
core-infra (Gemini wrapper), onboarding (category-level profile only, never PII), marketplace (Ask-a-CA).

## Contracts (don't change without telling the team)
- Only category-level profile facts (e.g. "proprietorship, QRMP") may go into prompts (rule 1)

## Known issues
None yet.
