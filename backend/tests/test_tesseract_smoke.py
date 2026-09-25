"""Smoke test: local OCR works (Tesseract via pytesseract, image drawn with OpenCV)."""

import pytest


@pytest.mark.requires_tesseract
def test_tesseract_reads_rendered_text():
    import cv2
    import numpy as np
    import pytesseract

    image = np.full((140, 700), 255, dtype=np.uint8)  # white canvas
    cv2.putText(image, "CA HELPER 2026", (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 2.2, 0, 5)

    text = pytesseract.image_to_string(image)

    assert "HELPER" in text.upper()
