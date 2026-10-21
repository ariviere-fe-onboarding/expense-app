"""Local development mailbox: messages are written as files instead of being sent."""

from __future__ import annotations

from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path


def send_mail(mail_dir: Path, to: str, subject: str, body: str) -> Path:
    """Write the message to mail_dir as an .eml file and return its path."""
    message = EmailMessage()
    message["From"] = "Fernway Expenses <no-reply@fernway.example>"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    mail_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    path = mail_dir / f"{stamp}.eml"
    path.write_bytes(message.as_bytes())
    return path
