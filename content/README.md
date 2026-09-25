# content/

Static, human-written content shown in the app. It is owned per form (see `docs/OWNERSHIP.md`).

```
content/forms/<FORM>/
  explanation.md   plain-language explanation (item page)
  instructions.md  self-filing steps (item page, COM-07)
  checklist.yaml   documents to have ready (COM-06, DOC-04)
```

Each Markdown file starts with front matter (`form`, `owner`, `task`, `status`). Set `status: DONE` when finished.

Rules:
- Edit only the forms you own.
- No legal thresholds, rates or due dates here. They live in DB rule tables and `docs/TODO_VERIFY.md`.
- Cite official sources at the bottom of each page.
- The assistant (AST-02) indexes this folder for RAG, so write clear, self-contained sections.
