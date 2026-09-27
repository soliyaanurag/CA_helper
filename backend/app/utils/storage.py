"""Encrypted file storage for uploads (CLAUDE.md rule 4: files are encrypted at rest).

    key = save_file(data, "application/pdf")   checks type and size, encrypts, writes
    data = open_file(key)                      reads and decrypts
    delete_file(key)                           removes the file (only when its save failed:
                                               documents are soft-deleted, files are kept)

Files are written to UPLOAD_DIR (default backend/instance/uploads, gitignored), each
under a random name, encrypted with Fernet (FIELD_ENCRYPTION_KEY). Only PDF, JPG and
PNG are accepted, recognised by their first bytes (not by the file name), and at most
MAX_UPLOAD_MB megabytes. The database keeps the metadata (the `documents` table).
"""

import uuid
from pathlib import Path

from flask import current_app

from app.errors import ApiError
from app.utils.encryption import decrypt_bytes, encrypt_bytes

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

# Allowed file types and the bytes every such file starts with.
ALLOWED_TYPES = {
    "application/pdf": b"%PDF-",
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
}


def _folder() -> Path:
    folder = Path(current_app.config["UPLOAD_DIR"])
    return folder if folder.is_absolute() else BACKEND_DIR / folder


def _path(key: str) -> Path:
    if not key.isalnum():  # our keys are hex; never a path someone typed
        raise ApiError(404, "FILE_NOT_FOUND", "This file was not found.")
    return _folder() / key


def save_file(data: bytes, mime_type: str) -> str:
    """Encrypt and store an uploaded file; returns its storage key.

    400 FILE_EMPTY, 400 FILE_TYPE_NOT_ALLOWED (not a real PDF/JPG/PNG),
    400 FILE_TOO_LARGE (over MAX_UPLOAD_MB).
    """
    max_mb = current_app.config["MAX_UPLOAD_MB"]
    if not data:
        raise ApiError(400, "FILE_EMPTY", "The file is empty.")
    start = ALLOWED_TYPES.get(mime_type)
    if start is None or not data.startswith(start):
        raise ApiError(400, "FILE_TYPE_NOT_ALLOWED", "Upload a PDF, JPG or PNG file.")
    if len(data) > max_mb * 1024 * 1024:
        raise ApiError(400, "FILE_TOO_LARGE", f"The file is larger than {max_mb} MB.")
    key = uuid.uuid4().hex
    folder = _folder()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / key).write_bytes(encrypt_bytes(data))
    return key


def open_file(key: str) -> bytes:
    """The decrypted contents of a stored file. 404 FILE_NOT_FOUND if it is missing."""
    path = _path(key)
    if not path.exists():
        raise ApiError(404, "FILE_NOT_FOUND", "This file was not found.")
    return decrypt_bytes(path.read_bytes())


def delete_file(key: str) -> None:
    _path(key).unlink(missing_ok=True)
