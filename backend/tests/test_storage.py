"""app/utils/storage.py: only real PDF, JPG and PNG files under the size limit are accepted."""

import pytest

from app.errors import ApiError
from app.utils import storage

PDF = b"%PDF-1.4 a tiny test file"
PNG = b"\x89PNG\r\n\x1a\n rest of a png"


@pytest.mark.parametrize(
    ("data", "mime_type", "code"),
    [
        (b"", "application/pdf", "FILE_EMPTY"),
        (b"MZ an exe", "application/pdf", "FILE_TYPE_NOT_ALLOWED"),  # the bytes decide
        (PNG, "image/gif", "FILE_TYPE_NOT_ALLOWED"),
    ],
)
def test_only_real_pdf_jpg_and_png_files_are_accepted(app, data, mime_type, code):
    with pytest.raises(ApiError) as error:
        storage.check_file(data, mime_type)
    assert error.value.code == code


def test_files_over_the_limit_are_refused(app, monkeypatch):
    monkeypatch.setitem(app.config, "MAX_UPLOAD_MB", 1)

    with pytest.raises(ApiError) as error:
        storage.check_file(PDF + b"x" * (1024 * 1024), "application/pdf")
    assert error.value.code == "FILE_TOO_LARGE"
