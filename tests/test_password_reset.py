from __future__ import annotations

import re
from datetime import timedelta
from email import message_from_bytes
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Config
from app.models import PasswordResetToken, utcnow
from tests.conftest import DEMO_PASSWORD, sessions

NEW_PASSWORD = "a-brand-new-passphrase"


def request_reset(client: TestClient, email: str = "priya@fernway.example") -> None:
    response = client.post("/password-reset", data={"email": email})
    assert response.status_code == 200
    assert "If an account exists" in response.text


def mailed_token(mail_dir: Path) -> str:
    messages = sorted(mail_dir.glob("*.eml"))
    assert messages, "no reset email was written"
    body = message_from_bytes(messages[-1].read_bytes()).get_payload(decode=True)
    assert isinstance(body, bytes)
    match = re.search(r"token=([\w-]+)", body.decode())
    assert match
    return match.group(1)


def sign_in(client: TestClient, password: str) -> int:
    response = client.post(
        "/login",
        data={"email": "priya@fernway.example", "password": password},
        follow_redirects=False,
    )
    return response.status_code


def test_full_reset_flow(client: TestClient, config: Config) -> None:
    request_reset(client)
    token = mailed_token(config.mail_dir)
    assert client.get("/password-reset/confirm", params={"token": token}).status_code == 200
    response = client.post(
        "/password-reset/confirm", data={"token": token, "password": NEW_PASSWORD}
    )
    assert "Password updated" in response.text
    assert sign_in(client, NEW_PASSWORD) == 303
    assert sign_in(client, DEMO_PASSWORD) == 401


def test_token_is_single_use(client: TestClient, config: Config) -> None:
    request_reset(client)
    token = mailed_token(config.mail_dir)
    client.post("/password-reset/confirm", data={"token": token, "password": NEW_PASSWORD})
    again = client.post(
        "/password-reset/confirm", data={"token": token, "password": "yet-another-passphrase"}
    )
    assert again.status_code == 400


def test_expired_token_is_rejected(client: TestClient, config: Config) -> None:
    request_reset(client)
    token = mailed_token(config.mail_dir)
    with sessions(client)() as session:
        for record in session.query(PasswordResetToken).all():
            record.expires_at = utcnow() - timedelta(seconds=1)
        session.commit()
    response = client.post(
        "/password-reset/confirm", data={"token": token, "password": NEW_PASSWORD}
    )
    assert response.status_code == 400
    assert client.get("/password-reset/confirm", params={"token": token}).status_code == 400


def test_unknown_token_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/password-reset/confirm", data={"token": "made-up", "password": NEW_PASSWORD}
    )
    assert response.status_code == 400


def test_new_request_invalidates_older_token(client: TestClient, config: Config) -> None:
    request_reset(client)
    first = mailed_token(config.mail_dir)
    request_reset(client)
    response = client.post(
        "/password-reset/confirm", data={"token": first, "password": NEW_PASSWORD}
    )
    assert response.status_code == 400


def test_short_password_is_rejected(client: TestClient, config: Config) -> None:
    request_reset(client)
    token = mailed_token(config.mail_dir)
    response = client.post("/password-reset/confirm", data={"token": token, "password": "short"})
    assert response.status_code == 400
    assert sign_in(client, DEMO_PASSWORD) == 303


def test_unknown_email_sends_nothing(client: TestClient, config: Config) -> None:
    request_reset(client, "nobody@fernway.example")
    assert not config.mail_dir.exists() or not list(config.mail_dir.glob("*.eml"))


def test_reset_token_is_hashed_at_rest(client: TestClient, config: Config) -> None:
    request_reset(client)
    token = mailed_token(config.mail_dir)
    with sessions(client)() as session:
        stored = [record.token_hash for record in session.query(PasswordResetToken).all()]
    assert token not in stored


def test_reset_signs_out_existing_sessions(client: TestClient, config: Config) -> None:
    assert sign_in(client, DEMO_PASSWORD) == 303
    request_reset(client)
    token = mailed_token(config.mail_dir)
    client.post("/password-reset/confirm", data={"token": token, "password": NEW_PASSWORD})
    assert client.get("/", follow_redirects=False).status_code == 303
