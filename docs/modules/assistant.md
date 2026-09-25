# assistant: AI assistant (Gemini RAG with citations)

## Purpose
The floating assistant for both roles: answers through the PII-scrubbing Gemini wrapper, RAG over our own content and official FAQs with citations, category-level profile awareness and Ask-a-CA handoff.

## Owner
Member B (Infrastructure, documents & AI)

Folders: `backend/app/modules/assistant/`, `frontend/src/features/assistant/` (the floating widget shell itself is FE-03)

## Tasks
Format: `- [ ] ID · P<phase> · <owner> · <description>`; states `[ ]` to do, `[~]` in progress, `[x]` done.

- [ ] AST-01 · P1 · B · Floating widget answers via plain Gemini through the PII wrapper
- [ ] AST-02 · P2 · B · Knowledge ingestion from content/ + official FAQs, embeddings in pgvector
- [ ] AST-03 · P2 · B · RAG answers with citations
- [ ] AST-04 · P3 · B · Category-level profile awareness + Ask-a-CA handoff
- [ ] AST-05 · P4 · B · Per-user chat history
- [ ] AST-06 · P5 · B · Assistant evaluation (~50 questions, correctness + citation accuracy)

## Tables owned
- `kb_chunks` (planned): source, title, url, text, `embedding vector(N)` (pgvector)
- `chat_messages` (planned, P4): per-user history

## Endpoints exposed
Planned: `/api/assistant/...` (ask).

## Service functions others may call
_None yet._

## Depends on
core-infra (Gemini wrapper), onboarding (category-level profile only, never PII), marketplace (Ask-a-CA).

## Contracts others rely on
- Only category-level profile facts (e.g. "proprietorship, QRMP") may go into prompts (rule 1)

## Known issues
_None yet._

## Session log
Newest first. Keep the last 10 entries.

- 2026-09-25 · Builder · Phase 0: created this doc and its task list.
