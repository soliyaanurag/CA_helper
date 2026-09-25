"""Local OCR and PDF text extraction (owner: Member B). Empty in Phase 0.

Planned (INF-08): helpers around Tesseract (pytesseract), PyMuPDF, pdfplumber
and OpenCV. OCR is local only; documents never leave our server. Tests that
need Tesseract use the `requires_tesseract` pytest marker. Use `import pymupdf`
(the old `fitz` import name is deprecated).
"""
