# Phases (the phase is the priority)

| Phase | Content | Who |
|---|---|---|
| **0: Environment** | Environment, rules, context docs, tracker, empty skeleton | Builder |
| **1: Working prototype** | Thin end-to-end flow with one working example of every building block (see the Phase 1 prompt in `docs/prompts/`) | Builder |
| **2: Core features** | Real depth behind the prototype | Each owner |
| **3: Intelligent features** | NIC, OCR features, penalty, peer insights, regulatory monitor, matching, pro-bono, quotes, ratings, urgency, batch view, admin editors | Each owner |
| **4: Extras** | Cut first if time is short | Each owner |
| **5: Finish** | Evaluations, integration testing, deployment, report, demo, viva prep | Everyone |

Every task line in `docs/modules/*.md` carries its phase (`P0`–`P5`). `make progress` shows totals per phase and
member, and the **current phase** (the lowest phase with open tasks).

## Phase rule
Nobody starts a task from a later phase while any of their own tasks from an earlier phase are open, unless the
team agrees in the sync.

## Parallel track during Phases 0–1 (non-Builders)
While the Builder sets up Phases 0 and 1, the other members work on preparation tasks that need no code:

- verify legal values from official sources and fill `docs/TODO_VERIFY.md` (CNT-01)
- write form content in `content/forms/<form>/` (CNT-02 to CNT-07)
- label ~100 business descriptions with NIC codes (CNT-08) → `eval/nic/`
- collect or create ~30 sample documents for OCR evaluation, with no real personal data (CNT-09) → `eval/ocr/`

These are the `CNT-*` tasks in `docs/modules/content.md`. The `FIN-*` tasks in `docs/modules/finish.md` are Phase 5.
