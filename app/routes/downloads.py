"""File-based receipt downloads for the legacy receipt archive client."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.deps import AppConfig, CurrentUser

router = APIRouter()


@router.get("/receipts/download")
def download_receipt(
    config: AppConfig,
    user: CurrentUser,
    filename: Annotated[str, Query(min_length=1, max_length=1024)],
) -> FileResponse:
    """Download a named file from the receipt archive."""
    path = config.upload_dir / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Receipt not found.")
    return FileResponse(path, media_type="application/octet-stream", filename=path.name)
