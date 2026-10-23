"""Inline receipt previews for signed-in employees."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.deps import AppConfig, CurrentUser, DbSession
from app.receipt_preview import load_receipt_preview
from app.receipts import ReceiptError
from app.routes.expenses import visible_expense

router = APIRouter()


@router.get("/expenses/{expense_id}/receipt/preview")
def preview_receipt(
    session: DbSession, config: AppConfig, user: CurrentUser, expense_id: int
) -> FileResponse:
    """Open a stored receipt in the browser rather than downloading it."""
    visible_expense(session, user, expense_id)
    try:
        document = load_receipt_preview(session, config.upload_dir, expense_id)
    except ReceiptError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Receipt not found.") from error
    return FileResponse(
        document.path,
        media_type=document.content_type,
        headers={"content-disposition": "inline"},
    )
