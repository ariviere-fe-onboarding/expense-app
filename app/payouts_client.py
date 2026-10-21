"""Client for payouts-service: signed webhooks out, service-token internal API in."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Config

SIGNATURE_HEADER = "X-Fernway-Signature"


class PayoutsUnavailable(RuntimeError):
    """Raised when payouts-service cannot be reached or returns an unexpected response."""


class PayoutStatus(BaseModel):
    """Payout status as reported by payouts-service."""

    payout_id: int
    status: str
    amount_cents: int
    currency: str


class BankDestination(BaseModel):
    """Masked bank destination. payouts-service never returns full numbers."""

    bank_name: str
    account_last4: str


def sign(secret: str, body: bytes, timestamp: int) -> str:
    """Return the X-Fernway-Signature header value for body."""
    message = str(timestamp).encode("ascii") + b"." + body
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


@dataclass
class PayoutsClient:
    """Talks to payouts-service. Tests inject an httpx.MockTransport."""

    config: Config
    transport: httpx.BaseTransport | None = None

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.config.payouts_base_url,
            timeout=self.config.payouts_timeout_seconds,
            transport=self.transport,
            follow_redirects=False,
        )

    def _internal_get(self, path: str, params: dict[str, str] | None = None) -> httpx.Response:
        headers = {"authorization": f"Bearer {self.config.payouts_service_token}"}
        try:
            with self._client() as client:
                return client.get(path, params=params, headers=headers)
        except httpx.HTTPError as error:
            raise PayoutsUnavailable("payouts-service is unreachable") from error

    def deliver(self, payload: dict[str, object]) -> None:
        """POST a signed expense.approved event. Raises PayoutsUnavailable on failure."""
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {
            "content-type": "application/json",
            SIGNATURE_HEADER: sign(self.config.payouts_webhook_secret, body, int(time.time())),
        }
        try:
            with self._client() as client:
                response = client.post("/webhooks/expense-approved", content=body, headers=headers)
        except httpx.HTTPError as error:
            raise PayoutsUnavailable("payouts-service is unreachable") from error
        if response.status_code not in (200, 202):
            raise PayoutsUnavailable(f"payouts-service returned {response.status_code}")

    def payout_status(self, expense_id: int) -> PayoutStatus | None:
        """Return the payout for an expense, or None if none exists yet."""
        response = self._internal_get("/internal/payouts", {"expense_id": str(expense_id)})
        if response.status_code == 404:
            return None
        return self._parse(response, PayoutStatus)

    def bank_destination(self, employee_id: str) -> BankDestination | None:
        """Return the masked bank destination for an employee, or None if not on file."""
        response = self._internal_get(f"/internal/employees/{employee_id}/bank-account")
        if response.status_code == 404:
            return None
        return self._parse(response, BankDestination)

    @staticmethod
    def _parse[T: BaseModel](response: httpx.Response, model: type[T]) -> T:
        if response.status_code != 200:
            raise PayoutsUnavailable(f"payouts-service returned {response.status_code}")
        try:
            return model.model_validate_json(response.content)
        except ValidationError as error:
            raise PayoutsUnavailable("payouts-service returned an invalid response") from error
