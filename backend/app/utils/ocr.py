"""Local OCR: the text of an uploaded PDF or photo (ON12). Nothing leaves the server (rule 2).

    text = extract_text(data, "application/pdf")   the document's text
    ocr_available() -> bool                         is the `tesseract` program installed?

PDFs downloaded from the government portals contain real text, which PyMuPDF reads
directly. A page with (almost) no text is a scan: PyMuPDF turns it into a PNG picture,
and the Tesseract program reads the picture. Photos (JPG, PNG) go to Tesseract directly.
The picture is handed to `tesseract` on its standard input, so no file is written.
Only the first MAX_PAGES pages are read, to keep uploads quick.

extract_text() raises OcrError when nothing could be read (a broken file, no text at
all, or Tesseract missing for a picture); the caller decides what that means.
"""

import logging
import shutil
import subprocess

import pymupdf

log = logging.getLogger(__name__)

MAX_PAGES = 3
MIN_PAGE_TEXT = 30  # a PDF page with fewer characters is treated as a scanned picture
RENDER_DPI = 200  # picture quality for scanned pages (higher = slower, more accurate)
TESSERACT_TIMEOUT_SECONDS = 30


class OcrError(Exception):
    """The file's text could not be read. The message says why (no personal data)."""


def ocr_available() -> bool:
    """True when the `tesseract` program is installed (environment.yml / CI)."""
    return shutil.which("tesseract") is not None


def _read_picture(picture: bytes) -> str:
    """The text in a PNG or JPG picture, read by the tesseract program (English)."""
    if not ocr_available():
        raise OcrError("Tesseract is not installed, so pictures cannot be read.")
    try:
        result = subprocess.run(
            ["tesseract", "stdin", "stdout", "-l", "eng"],
            input=picture,
            capture_output=True,
            timeout=TESSERACT_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise OcrError("Reading the picture took too long.") from error
    if result.returncode != 0:
        raise OcrError("Tesseract could not read the picture.")
    return result.stdout.decode("utf-8", errors="replace")


def _read_pdf(data: bytes) -> str:
    """The text of the first pages of a PDF; scanned pages are read as pictures."""
    try:
        pdf = pymupdf.open(stream=data, filetype="pdf")
    except Exception as error:  # PyMuPDF raises several error types for broken files
        raise OcrError("The PDF could not be opened.") from error
    texts = []
    with pdf:
        for number in range(min(MAX_PAGES, pdf.page_count)):
            page = pdf[number]
            text = page.get_text()
            if len(text.strip()) < MIN_PAGE_TEXT:
                picture = page.get_pixmap(dpi=RENDER_DPI).tobytes("png")
                text = _read_picture(picture)
            texts.append(text)
    return "\n".join(texts)


def extract_text(data: bytes, mime_type: str) -> str:
    """The text of a PDF, JPG or PNG file. Raises OcrError when no text could be read."""
    text = _read_pdf(data) if mime_type == "application/pdf" else _read_picture(data)
    if not text.strip():
        raise OcrError("No text was found in the file.")
    return text
