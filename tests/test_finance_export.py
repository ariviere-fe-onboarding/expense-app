from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient

from tests.conftest import expense_id, login


def export(client: TestClient, start: str, end: str) -> list[list[str]]:
    response = client.get("/finance/export", params={"start": start, "end": end})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    return list(csv.reader(io.StringIO(response.text)))


def test_finance_exports_approved_expenses(client: TestClient) -> None:
    login(client, "emp-dana")
    rows = export(client, "2026-09-01", "2026-09-30")
    assert rows[0][0] == "expense_id"
    assert rows[1][1:] == [
        "2026-09-19",
        "Priya Nair",
        "Design",
        "Brightline Rail",
        "travel",
        "86.40",
    ]
    assert rows[-1] == ["total", "", "", "", "", "", "86.40"]


def test_unapproved_expenses_are_excluded(client: TestClient) -> None:
    login(client, "emp-dana")
    merchants = [row[4] for row in export(client, "2026-09-01", "2026-09-30")[1:-1]]
    assert "Figment Fonts" not in merchants


def test_formula_text_is_neutralized(client: TestClient) -> None:
    login(client, "emp-priya")
    client.post(
        "/expenses",
        data={
            "merchant": "=HYPERLINK(1)",
            "amount": "12.00",
            "spent_on": "2026-09-15",
            "category": "other",
        },
    )
    login(client, "emp-marcus")
    client.post(
        f"/expenses/{expense_id(client, '=HYPERLINK(1)')}/decision", data={"decision": "approve"}
    )
    login(client, "emp-dana")
    merchants = [row[4] for row in export(client, "2026-09-01", "2026-09-30")[1:-1]]
    assert "'=HYPERLINK(1)" in merchants


def test_only_finance_can_export(client: TestClient) -> None:
    for user in ("emp-priya", "emp-marcus"):
        login(client, user)
        response = client.get(
            "/finance/export", params={"start": "2026-09-01", "end": "2026-09-30"}
        )
        assert response.status_code == 403


def test_reversed_range_is_rejected(client: TestClient) -> None:
    login(client, "emp-dana")
    response = client.get("/finance/export", params={"start": "2026-09-30", "end": "2026-09-01"})
    assert response.status_code == 400
