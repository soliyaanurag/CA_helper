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

The AI assistant also reads the FAQ pages in `content/faqs/`, which come in two kinds:
- `status: OFFICIAL`: copied word for word from the official site (only the layout turned into Markdown).
- `status: DRAFT`: plain-language summaries written from the official sources listed in `sources`. Unlike the
  form guides, they state thresholds, rates and due dates, because users ask about them; every number must be
  checked against its source before the demo (`docs/KB_VERIFICATION_NOTES.md`). The app's own logic never reads
  these pages: legal values used by the app stay in the DB rule tables.

Every FAQ page has `title`, `source` (the main URL, or empty), `publisher`, `retrieved` and `status` in the front
matter; the assistant cites `title` and `source`. After changing anything here, run `make assistant-ingest`.

Rules:
- No legal thresholds, rates or due dates here. They live in DB rule tables and `docs/TODO_VERIFY.md`.
- Cite official sources at the bottom of each page.
- The assistant indexes this folder for RAG, so write clear, self-contained sections.
