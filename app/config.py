"""Application configuration. The only module that reads the process environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


class ConfigError(RuntimeError):
    """Raised at startup when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    """Validated runtime configuration for expense-app."""

    database_url: str
    public_origin: str
    payouts_base_url: str
    payouts_webhook_secret: str
    payouts_service_token: str
    demo_password: str
    upload_dir: Path
    mail_dir: Path
    cookie_secure: bool = False
    session_hours: int = 8
    reset_token_minutes: int = 30
    payouts_timeout_seconds: float = 3.0
    anthropic_api_key: str | None = None


def _load_env_file(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE file. Values already in the environment take precedence."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


def _required(values: dict[str, str], key: str, min_length: int) -> str:
    value = values.get(key, "")
    if len(value) < min_length:
        raise ConfigError(f"{key} must be set to at least {min_length} characters.")
    return value


def load_config(env_file: Path = Path(".env")) -> Config:
    """Build configuration from the environment, falling back to a local .env file."""
    values = {**_load_env_file(env_file), **os.environ}
    return Config(
        database_url=values.get("FERNWAY_DATABASE_URL", "sqlite:///.local/expenses.sqlite"),
        public_origin=values.get("FERNWAY_PUBLIC_ORIGIN", "http://127.0.0.1:8000"),
        payouts_base_url=values.get("FERNWAY_PAYOUTS_BASE_URL", "http://127.0.0.1:8001"),
        payouts_webhook_secret=_required(values, "PAYOUTS_WEBHOOK_SECRET", 32),
        payouts_service_token=_required(values, "PAYOUTS_SERVICE_TOKEN", 32),
        demo_password=_required(values, "FERNWAY_DEMO_PASSWORD", 12),
        upload_dir=Path(values.get("FERNWAY_UPLOAD_DIR", ".local/receipts")),
        mail_dir=Path(values.get("FERNWAY_MAIL_DIR", ".local/mail")),
        cookie_secure=values.get("FERNWAY_COOKIE_SECURE", "false").lower() == "true",
        anthropic_api_key=values.get("ANTHROPIC_API_KEY") or None,
    )


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Return the process-wide configuration, validated once."""
    return load_config()
