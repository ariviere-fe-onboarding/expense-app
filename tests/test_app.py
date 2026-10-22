from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import ConfigError, load_config
from app.money import AmountError, format_cents, parse_amount
from app.receipts import ReceiptError, receipt_path
from app.seed import seed
from tests.conftest import FakePayouts, login, sessions


def test_security_headers(client: TestClient) -> None:
    headers = client.get("/login").headers
    assert "frame-ancestors 'none'" in headers["content-security-policy"]
    assert "unsafe-inline" not in headers["content-security-policy"]
    assert headers["x-content-type-options"] == "nosniff"


def test_cross_origin_post_is_blocked(client: TestClient) -> None:
    login(client, "emp-marcus")
    for origin in ("https://evil.example", ""):
        response = client.post(
            "/expenses/1/decision", data={"decision": "approve"}, headers={"origin": origin}
        )
        assert response.status_code == 403


def test_profile_shows_masked_bank(client: TestClient) -> None:
    login(client, "emp-priya")
    page = client.get("/profile").text
    assert "Harbor Credit Union ····6789" in page
    assert "Marcus Bell" in page


def test_profile_without_bank_account(client: TestClient) -> None:
    login(client, "emp-jonah")
    assert "No bank account on file" in client.get("/profile").text


def test_profile_when_payouts_down(client: TestClient, fake_payouts: FakePayouts) -> None:
    fake_payouts.fail = True
    login(client, "emp-priya")
    assert "Unavailable right now" in client.get("/profile").text


def test_payouts_rejecting_token_is_unavailable(
    client: TestClient, fake_payouts: FakePayouts
) -> None:
    fake_payouts.token = "rotated"
    login(client, "emp-priya")
    assert "Unavailable right now" in client.get("/profile").text


@pytest.mark.parametrize(
    ("text", "cents"), [("42", 4200), ("42.5", 4250), ("$1,000.01", 100_001), (" 0.01 ", 1)]
)
def test_parse_amount(text: str, cents: int) -> None:
    assert parse_amount(text) == cents


@pytest.mark.parametrize("text", ["", "abc", "1.001", "0", "-1", "Infinity", "10000.01"])
def test_parse_amount_rejects(text: str) -> None:
    with pytest.raises(AmountError):
        parse_amount(text)


def test_format_cents() -> None:
    assert format_cents(123_456) == "$1,234.56"
    assert format_cents(5) == "$0.05"
    assert format_cents(-250) == "-$2.50"
    assert format_cents(100, "EUR") == "€1.00"
    assert format_cents(100, "JPY") == "JPY 1.00"


def test_receipt_path_refuses_traversal(tmp_path: Path) -> None:
    with pytest.raises(ReceiptError):
        receipt_path(tmp_path, "../secrets.txt")


def test_seed_is_idempotent(client: TestClient) -> None:
    with sessions(client)() as session:
        assert seed(session, "irrelevant-pass", today=date(2026, 1, 1)) == 0


def test_config_requires_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("PAYOUTS_WEBHOOK_SECRET", "PAYOUTS_SERVICE_TOKEN", "FERNWAY_DEMO_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ConfigError):
        load_config(tmp_path / "none.env")


def test_config_reads_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("PAYOUTS_WEBHOOK_SECRET", "PAYOUTS_SERVICE_TOKEN", "FERNWAY_DEMO_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    env = tmp_path / ".env"
    env.write_text(
        f"# local\nPAYOUTS_WEBHOOK_SECRET={'a' * 40}\nPAYOUTS_SERVICE_TOKEN={'b' * 40}\n"
        "FERNWAY_DEMO_PASSWORD=a-demo-passphrase\n",
        encoding="utf-8",
    )
    assert load_config(env).demo_password == "a-demo-passphrase"
