"""Browser previews for receipts attached to expenses."""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.models import Expense
from app.receipt_preview import load_receipt_preview
from app.receipts import save_receipt
from tests.conftest import expense_id, login, sessions

PDF = b"%PDF-1.7\n% Synthetic Fernway receipt\n"


def attach_receipt(client: TestClient, config: Config) -> int:
    """Attach a synthetic receipt to Priya's hotel expense."""
    identifier = expense_id(client, "Harborview Hotel")
    stored_name, content_type = save_receipt(config.upload_dir, PDF)
    with sessions(client)() as session:
        expense = session.get(Expense, identifier)
        assert expense is not None
        expense.receipt_file = stored_name
        expense.receipt_content_type = content_type
        session.commit()
    return identifier


@pytest.mark.parametrize("viewer", ["emp-priya", "emp-marcus", "emp-dana"])
def test_authorized_user_previews_receipt_inline(
    client: TestClient, config: Config, viewer: str
) -> None:
    """Authorized viewers receive the uploaded bytes with an inline disposition."""
    identifier = attach_receipt(client, config)
    login(client, viewer)
    response = client.get(f"/expenses/{identifier}/receipt/preview")
    assert response.status_code == 200
    assert response.content == PDF
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == "inline"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("viewer", ["emp-jonah", "emp-lena"])
def test_unrelated_user_cannot_preview_receipt(
    client: TestClient, config: Config, viewer: str
) -> None:
    """Unrelated employees and managers get 404 before receipt loading."""
    identifier = attach_receipt(client, config)
    login(client, viewer)
    with patch(
        "app.routes.previews.load_receipt_preview", wraps=load_receipt_preview
    ) as load_preview:
        response = client.get(f"/expenses/{identifier}/receipt/preview")
        load_preview.assert_not_called()
    assert response.status_code == 404
    assert "Expense not found." in response.text


def test_expense_page_offers_preview_and_download(client: TestClient, config: Config) -> None:
    """Employees can choose how to open a receipt from its expense page."""
    identifier = attach_receipt(client, config)
    login(client, "emp-priya")
    page = client.get(f"/expenses/{identifier}")
    assert f'href="/expenses/{identifier}/receipt/preview"' in page.text
    download = client.get(f"/expenses/{identifier}/receipt")
    assert download.content == PDF
    assert download.headers["content-disposition"] == "attachment"


def test_preview_requires_sign_in(client: TestClient, config: Config) -> None:
    """Anonymous requests redirect to the sign-in page."""
    identifier = attach_receipt(client, config)
    response = client.get(f"/expenses/{identifier}/receipt/preview", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_missing_receipt_is_not_found(client: TestClient) -> None:
    """A missing attachment returns a controlled 404."""
    login(client, "emp-priya")
    identifier = expense_id(client, "Harborview Hotel")
    assert client.get(f"/expenses/{identifier}/receipt/preview").status_code == 404
    assert client.get("/expenses/999999/receipt/preview").status_code == 404


def test_missing_stored_file_is_not_found(client: TestClient, config: Config) -> None:
    """A stale attachment reference does not become a server error."""
    identifier = expense_id(client, "Harborview Hotel")
    with sessions(client)() as session:
        expense = session.get(Expense, identifier)
        assert expense is not None
        expense.receipt_file = "missing.pdf"
        expense.receipt_content_type = "application/pdf"
        session.commit()
    login(client, "emp-priya")
    assert client.get(f"/expenses/{identifier}/receipt/preview").status_code == 404


def test_invalid_stored_path_is_not_found(client: TestClient, config: Config) -> None:
    """Preview still refuses paths outside receipt storage."""
    identifier = expense_id(client, "Harborview Hotel")
    with sessions(client)() as session:
        expense = session.get(Expense, identifier)
        assert expense is not None
        expense.receipt_file = str(Path("..") / "outside.pdf")
        expense.receipt_content_type = "application/pdf"
        session.commit()
    login(client, "emp-priya")
    assert client.get(f"/expenses/{identifier}/receipt/preview").status_code == 404
