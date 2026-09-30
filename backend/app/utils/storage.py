"""The checks every uploaded file passes: a real PDF, JPG or PNG, and not too big.

The file is recognised by its first bytes (not by its name). Stored files live in the
database (documents.content), encrypted.
"""

from flask import current_app

from app.errors import ApiError

# Allowed file types and the bytes every such file starts with.
ALLOWED_TYPES = {
    "application/pdf": b"%PDF-",
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
}


def check_file(data: bytes, mime_type: str) -> None:
    """400 FILE_EMPTY, 400 FILE_TYPE_NOT_ALLOWED (not a real PDF/JPG/PNG),
    400 FILE_TOO_LARGE (over MAX_UPLOAD_MB)."""
    max_mb = current_app.config["MAX_UPLOAD_MB"]
    if not data:
        raise ApiError(400, "FILE_EMPTY", "The file is empty.")
    start = ALLOWED_TYPES.get(mime_type)
    if start is None or not data.startswith(start):
        raise ApiError(400, "FILE_TYPE_NOT_ALLOWED", "Upload a PDF, JPG or PNG file.")
    if len(data) > max_mb * 1024 * 1024:
        raise ApiError(400, "FILE_TOO_LARGE", f"The file is larger than {max_mb} MB.")
