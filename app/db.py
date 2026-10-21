"""Database engine and session management."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Declarative base for all expense-app models."""


def make_engine(database_url: str) -> Engine:
    """Create an engine, preparing the local directory for file-backed SQLite."""
    if database_url.startswith("sqlite:///") and ":memory:" not in database_url:
        Path(database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(database_url, connect_args={"check_same_thread": False})


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a session factory bound to the engine."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a session that is always closed when the request finishes."""
    session = factory()
    try:
        yield session
    finally:
        session.close()
