"""Resolve stored receipts for browser previews."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Expense
from app.receipts import ReceiptError, receipt_path


@dataclass(frozen=True)
class ReceiptPreview:
    """The stored document and content type to send to the browser."""

    path: Path
    content_type: str


def load_receipt_preview(session: Session, upload_dir: Path, expense_id: int) -> ReceiptPreview:
    """Resolve an expense's receipt and check that the stored file is available."""
    expense = session.get(Expense, expense_id)
    if expense is None or not expense.receipt_file or not expense.receipt_content_type:
        raise ReceiptError("No receipt attached.")
    path = receipt_path(upload_dir, expense.receipt_file)
    if not path.is_file():
        raise ReceiptError("Receipt file is unavailable.")
    return ReceiptPreview(path=path, content_type=expense.receipt_content_type)
