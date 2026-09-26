"""Local OCR and PDF text extraction. Not built yet.

Planned: helpers around Tesseract (pytesseract) for images and PyMuPDF for PDFs
(PyMuPDF only; no second PDF library). OCR is local only; documents never leave
our server. Tests that need Tesseract use the `requires_tesseract` pytest marker.
Use `import pymupdf` (the old `fitz` import name is deprecated).
"""
