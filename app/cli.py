"""Operator commands: `python -m app.cli seed` and `python -m app.cli retry-webhooks`."""

from __future__ import annotations

import argparse

from app.config import get_config
from app.db import Base, make_engine, make_session_factory
from app.payouts_client import PayoutsClient
from app.seed import seed
from app.webhooks import retry_pending


def main(argv: list[str] | None = None) -> int:
    """Run one operator command against the configured database."""
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    parser.add_argument("command", choices=["seed", "retry-webhooks"])
    args = parser.parse_args(argv)

    config = get_config()
    engine = make_engine(config.database_url)
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as session:
        if args.command == "seed":
            added = seed(session, config.demo_password)
            print(f"Seeded {added} demo users." if added else "Database already seeded.")
        else:
            delivered = retry_pending(session, PayoutsClient(config))
            print(f"Delivered {delivered} pending webhooks.")
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
