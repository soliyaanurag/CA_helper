# assistant: AI assistant (Gemini RAG with citations)

## Purpose
The floating assistant for both roles: answers through the PII-scrubbing Gemini wrapper, RAG over our own content and official FAQs with citations, category-level profile awareness and Ask-a-CA handoff.

## What exists now
Skeleton only; no features yet.
- Backend (`backend/app/modules/assistant/`): the `assistant` blueprint is registered under `/api` with no routes; `models.py`, `schemas.py` and `services.py` are empty; `seed()` does nothing; `tests/` is empty.
- Frontend (`frontend/src/features/assistant/`): one placeholder page, "AI assistant" at `/app/assistant` (business nav), built from `ModulePlaceholder`; `api.ts` is empty. The floating widget shell (frontend core) does not exist yet.
- The Gemini wrapper it needs (`core/ai/gemini_client.py`) does not exist yet.

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
