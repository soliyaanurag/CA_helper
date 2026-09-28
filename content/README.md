# content/

Static, human-written content shown in the app, one folder per form.

```
content/forms/<FORM>/
  explanation.md   plain-language explanation (item page)
  instructions.md  self-filing steps (item page)
  checklist.yaml   documents to have ready (item page checklist, OCR document-type checks)
```

Each file starts with front matter (`form`, `status`): `TODO` (template), `DRAFT` (written, not checked against
the official sources; the app says so) or `DONE`. HTML comments (`<!-- -->`) are notes for writers and are never
shown. Write links as `<https://...>` so they are clickable. The filing page shows `explanation.md` and
`instructions.md` (Markdown) and the checklist (`GET /api/v1/compliance/forms/<form_code>`).

Rules:
- No legal thresholds, rates or due dates here. They live in DB rule tables and `docs/TODO_VERIFY.md`.
- Cite official sources at the bottom of each page.
- The assistant indexes this folder for RAG, so write clear, self-contained sections.
