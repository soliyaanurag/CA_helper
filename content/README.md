# content/

Static, human-written content shown in the app, one folder per form.

```
content/forms/<FORM>/
  explanation.md   plain-language explanation (item page)
  instructions.md  self-filing steps (item page)
  checklist.yaml   documents to have ready (item page checklist, OCR document-type checks)
```

Each file starts with front matter (`form`, `status`). Set `status: DONE` when finished.

Rules:
- No legal thresholds, rates or due dates here. They live in DB rule tables and `docs/TODO_VERIFY.md`.
- Cite official sources at the bottom of each page.
- The assistant indexes this folder for RAG, so write clear, self-contained sections.
