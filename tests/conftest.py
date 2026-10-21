from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.config import Config
from app.main import create_app
from app.models import Expense
from app.seed import email_for, seed

ORIGIN = "http://testserver"
DEMO_PASSWORD = "correct-horse-battery"
TODAY = date(2026, 10, 1)
CONTRACT_FIXTURE = Path(__file__).parent / "contract" / "expense_approved_v1.json"


@dataclass
class FakePayouts:
    """Stands in for payouts-service and enforces the same signature and contract."""

    secret: str
    token: str
    fail: bool = False
    webhooks: list[dict[str, Any]] = field(default_factory=list)
    payouts: dict[int, dict[str, Any]] = field(default_factory=dict)
    accounts: dict[str, dict[str, str]] = field(
        default_factory=lambda: {
            "emp-priya": {"bank_name": "Harbor Credit Union", "account_last4": "6789"}
        }
    )

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.fail:
            raise httpx.ConnectError("payouts-service down", request=request)
        if request.url.path == "/webhooks/expense-approved":
            return self._webhook(request)
        if request.headers.get("authorization") != f"Bearer {self.token}":
            return httpx.Response(401)
        if request.url.path == "/internal/payouts":
            payout = self.payouts.get(int(request.url.params["expense_id"]))
            return httpx.Response(200, json=payout) if payout else httpx.Response(404)
        prefix, _, rest = request.url.path.partition("/internal/employees/")
        if not prefix and rest.endswith("/bank-account"):
            employee_id = rest.removesuffix("/bank-account")
            account = self.accounts.get(employee_id)
            if account is None:
                return httpx.Response(404)
            return httpx.Response(200, json={"employee_id": employee_id, **account})
        return httpx.Response(404)

    def _webhook(self, request: httpx.Request) -> httpx.Response:
        header = request.headers.get("x-fernway-signature", "")
        parts = dict(item.split("=", 1) for item in header.split(","))
        expected = hmac.new(
            self.secret.encode(), parts["t"].encode() + b"." + request.content, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, parts["v1"]):
            return httpx.Response(401)
        event = json.loads(request.content)
        self.webhooks.append(event)
        data = event["data"]
        self.payouts[data["expense_id"]] = {
            "payout_id": len(self.webhooks),
            "status": "submitted",
            "amount_cents": round(data["amount"] * 100),
            "currency": data["currency"],
        }
        return httpx.Response(202, json={"payout_id": len(self.webhooks), "status": "submitted"})


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(
        database_url=f"sqlite:///{tmp_path / 'expenses.sqlite'}",
        public_origin=ORIGIN,
        payouts_base_url="http://payouts.test",
        payouts_webhook_secret="w" * 40,
        payouts_service_token="s" * 40,
        demo_password=DEMO_PASSWORD,
        upload_dir=tmp_path / "receipts",
        mail_dir=tmp_path / "mail",
    )


@pytest.fixture
def fake_payouts(config: Config) -> FakePayouts:
    return FakePayouts(config.payouts_webhook_secret, config.payouts_service_token)


@pytest.fixture
def client(config: Config, fake_payouts: FakePayouts) -> Iterator[TestClient]:
    app = create_app(config, httpx.MockTransport(fake_payouts.handler))
    with app.state.session_factory() as session:
        seed(session, DEMO_PASSWORD, today=TODAY)
    with TestClient(app, headers={"origin": ORIGIN}) as test_client:
        yield test_client


def app_of(client: TestClient) -> FastAPI:
    return cast(FastAPI, client.app)


def sessions(client: TestClient) -> sessionmaker[Session]:
    return cast(sessionmaker[Session], app_of(client).state.session_factory)


def login(client: TestClient, user_id: str) -> None:
    response = client.post(
        "/login",
        data={"email": email_for(user_id), "password": DEMO_PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def expense_id(client: TestClient, merchant: str) -> int:
    with sessions(client)() as session:
        expense = session.query(Expense).filter_by(merchant=merchant).one()
        return int(expense.id)


def expense_status(client: TestClient, merchant: str) -> str:
    with sessions(client)() as session:
        return str(session.query(Expense).filter_by(merchant=merchant).one().status.value)
