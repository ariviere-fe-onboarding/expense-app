from __future__ import annotations

from pathlib import Path

import pytest

from app import cli
from app.config import get_config


def test_seed_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FERNWAY_DATABASE_URL", f"sqlite:///{tmp_path / 'cli.sqlite'}")
    monkeypatch.setenv("PAYOUTS_WEBHOOK_SECRET", "a" * 40)
    monkeypatch.setenv("PAYOUTS_SERVICE_TOKEN", "b" * 40)
    monkeypatch.setenv("FERNWAY_PAYOUTS_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("FERNWAY_DEMO_PASSWORD", "a-demo-passphrase")
    get_config.cache_clear()
    try:
        assert cli.main(["seed"]) == 0
        assert cli.main(["seed"]) == 0
        assert cli.main(["retry-webhooks"]) == 0
    finally:
        get_config.cache_clear()
    out = capsys.readouterr().out
    assert "Seeded 5 demo users." in out
    assert "already seeded" in out
    assert "Delivered 0 pending webhooks." in out
