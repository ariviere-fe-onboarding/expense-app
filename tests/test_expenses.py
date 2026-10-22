from __future__ import annotations

from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.config import Config
from app.models import Expense
from tests.conftest import FakePayouts, expense_id, login, sessions

PDF = b"%PDF-1.7\n% synthetic receipt\n"


def submit(client: TestClient, **overrides: str) -> httpx.Response:
    data = {
        "merchant": "Lakeside Diner",
        "amount": "42.50",
        "spent_on": "2026-09-30",
        "category": "meals",
        "description": "Team lunch",
        **overrides,
    }
    return client.post("/expenses", data=data, follow_redirects=False)


def test_submit_expense(client: TestClient) -> None:
    login(client, "emp-priya")
    response = submit(client)
    assert response.status_code == 303
    detail = client.get(response.headers["location"])
    assert "Lakeside Diner" in detail.text
    assert "$42.50" in detail.text
    assert "Awaiting manager" in detail.text


def test_amount_is_stored_in_cents(client: TestClient) -> None:
    login(client, "emp-priya")
    submit(client, amount="$1,234.56")
    with sessions(client)() as session:
        assert (
            session.query(Expense).filter_by(merchant="Lakeside Diner").one().amount_cents
            == 123_456
        )


def test_invalid_amount_is_rejected(client: TestClient) -> None:
    login(client, "emp-priya")
    for amount in ("abc", "0", "-5", "12.345", "20000", "NaN"):
        assert submit(client, amount=amount).status_code == 400, amount


def test_future_date_is_rejected(client: TestClient) -> None:
    login(client, "emp-priya")
    assert submit(client, spent_on="2999-01-01").status_code == 400


def test_manager_expense_goes_to_finance(client: TestClient) -> None:
    login(client, "emp-marcus")
    response = submit(client)
    detail = client.get(response.headers["location"])
    assert "Awaiting finance" in detail.text


def test_receipt_upload_and_download(client: TestClient, config: Config) -> None:
    login(client, "emp-priya")
    response = client.post(
        "/expenses",
        data={
            "merchant": "Copy Shop",
            "amount": "9.99",
            "spent_on": "2026-09-30",
            "category": "other",
        },
        files={"receipt": ("../../etc/passwd", PDF, "text/html")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    stored = list(config.upload_dir.iterdir())
    assert len(stored) == 1
    assert stored[0].suffix == ".pdf"
    assert "passwd" not in stored[0].name
    download = client.get(response.headers["location"].split("?")[0] + "/receipt")
    assert download.content == PDF
    assert download.headers["content-type"] == "application/pdf"
    assert download.headers["content-disposition"] == "attachment"


def test_non_receipt_upload_is_rejected(client: TestClient, config: Config) -> None:
    login(client, "emp-priya")
    response = client.post(
        "/expenses",
        data={
            "merchant": "Copy Shop",
            "amount": "9.99",
            "spent_on": "2026-09-30",
            "category": "other",
        },
        files={"receipt": ("receipt.pdf", b"<script>alert(1)</script>", "application/pdf")},
    )
    assert response.status_code == 400
    assert "PDF, PNG, or JPEG" in response.text
    assert not config.upload_dir.exists() or not list(config.upload_dir.iterdir())


def test_oversized_receipt_is_rejected(client: TestClient) -> None:
    login(client, "emp-priya")
    big = PDF + b"0" * (5 * 1024 * 1024)
    response = client.post(
        "/expenses",
        data={
            "merchant": "Copy Shop",
            "amount": "9.99",
            "spent_on": "2026-09-30",
            "category": "other",
        },
        files={"receipt": ("big.pdf", big, "application/pdf")},
    )
    assert response.status_code == 400
    assert "5 MB" in response.text


def test_other_employee_cannot_view_expense(client: TestClient) -> None:
    hotel = expense_id(client, "Harborview Hotel")
    login(client, "emp-jonah")
    assert client.get(f"/expenses/{hotel}").status_code == 404
    assert client.get(f"/expenses/{hotel}/receipt").status_code == 404


def test_other_teams_manager_cannot_view_expense(client: TestClient) -> None:
    hotel = expense_id(client, "Harborview Hotel")
    login(client, "emp-lena")
    assert client.get(f"/expenses/{hotel}").status_code == 404


def test_manager_and_finance_can_view_expense(client: TestClient) -> None:
    hotel = expense_id(client, "Harborview Hotel")
    for viewer in ("emp-marcus", "emp-dana"):
        login(client, viewer)
        assert client.get(f"/expenses/{hotel}").status_code == 200


def test_list_shows_only_own_expenses(client: TestClient) -> None:
    login(client, "emp-jonah")
    page = client.get("/").text
    assert "Cedar &amp; Salt" in page
    assert "Harborview Hotel" not in page


def test_user_content_is_escaped(client: TestClient) -> None:
    login(client, "emp-priya")
    response = submit(
        client, merchant="<script>alert(1)</script>", description="<img src=x onerror=1>"
    )
    page = client.get(response.headers["location"]).text
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page
    assert "<img src=x" not in page


def test_missing_receipt_is_404(client: TestClient, tmp_path: Path) -> None:
    login(client, "emp-priya")
    hotel = expense_id(client, "Harborview Hotel")
    assert client.get(f"/expenses/{hotel}/receipt").status_code == 404


def test_submit_foreign_currency_expense(client: TestClient) -> None:
    login(client, "emp-priya")
    response = submit(client, amount="85.00", currency="EUR")
    page = client.get(response.headers["location"]).text
    assert "€85.00" in page
    assert "≈ $91.80" in page


def test_foreign_expense_pays_usd(client: TestClient, fake_payouts: FakePayouts) -> None:
    login(client, "emp-priya")
    submit(client, merchant="Café Lumière", amount="40.00", currency="EUR")
    login(client, "emp-marcus")
    client.post(
        f"/expenses/{expense_id(client, 'Café Lumière')}/decision", data={"decision": "approve"}
    )
    assert fake_payouts.webhooks[0]["data"]["amount"] == 43.2
    assert fake_payouts.webhooks[0]["data"]["currency"] == "USD"


def test_unsupported_currency_is_rejected(client: TestClient) -> None:
    login(client, "emp-priya")
    assert submit(client, currency="JPY").status_code == 422
