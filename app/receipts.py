"""Receipt storage. Files are stored under generated names; client file names are ignored."""

from __future__ import annotations

import uuid
from pathlib import Path

MAX_RECEIPT_BYTES = 5 * 1024 * 1024

# Content type is decided from the file's leading bytes, never from the client.
_SIGNATURES: tuple[tuple[bytes, str, str], ...] = (
    (b"%PDF-", "application/pdf", ".pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
)


class ReceiptError(ValueError):
    """Raised when an upload is not an acceptable receipt."""


def detect_type(data: bytes) -> tuple[str, str]:
    """Return (content type, extension) for a PDF, PNG, or JPEG, else raise."""
    for magic, content_type, extension in _SIGNATURES:
        if data.startswith(magic):
            return content_type, extension
    raise ReceiptError("Receipts must be PDF, PNG, or JPEG files.")


def save_receipt(upload_dir: Path, data: bytes) -> tuple[str, str]:
    """Store receipt bytes and return (stored file name, content type)."""
    if not data:
        raise ReceiptError("The receipt file is empty.")
    if len(data) > MAX_RECEIPT_BYTES:
        raise ReceiptError("Receipts must be 5 MB or smaller.")
    content_type, extension = detect_type(data)
    upload_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{extension}"
    (upload_dir / name).write_bytes(data)
    return name, content_type


def receipt_path(upload_dir: Path, stored_name: str) -> Path:
    """Resolve a stored receipt name, refusing anything outside the upload directory."""
    root = upload_dir.resolve()
    path = (root / stored_name).resolve()
    if path.parent != root:
        raise ReceiptError("Invalid receipt reference.")
    return path
