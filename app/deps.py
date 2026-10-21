"""Request dependencies: configuration, database session, and the signed-in user."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Config
from app.db import session_scope
from app.models import User, UserSession, utcnow
from app.payouts_client import PayoutsClient
from app.security import token_hash

SESSION_COOKIE = "fernway_session"


class LoginRequired(Exception):
    """Raised when a route needs a signed-in user. Handled by redirecting to /login."""


def app_config(request: Request) -> Config:
    """Return the configuration the running app was built with."""
    config: Config = request.app.state.config
    return config


def db(request: Request) -> Iterator[Session]:
    """Yield a request-scoped database session."""
    yield from session_scope(request.app.state.session_factory)


def payouts(request: Request) -> PayoutsClient:
    """Return the payouts-service client."""
    client: PayoutsClient = request.app.state.payouts
    return client


def templates(request: Request) -> Jinja2Templates:
    """Return the template renderer."""
    renderer: Jinja2Templates = request.app.state.templates
    return renderer


DbSession = Annotated[Session, Depends(db)]
AppConfig = Annotated[Config, Depends(app_config)]
Payouts = Annotated[PayoutsClient, Depends(payouts)]
Templates = Annotated[Jinja2Templates, Depends(templates)]


def optional_user(request: Request, session: DbSession) -> User | None:
    """Return the signed-in user, or None when there is no valid session."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    record = session.scalars(
        select(UserSession).where(UserSession.token_hash == token_hash(token))
    ).first()
    if record is None or record.expires_at.replace(tzinfo=utcnow().tzinfo) <= utcnow():
        return None
    return session.get(User, record.user_id)


def current_user(user: Annotated[User | None, Depends(optional_user)]) -> User:
    """Require a signed-in user."""
    if user is None:
        raise LoginRequired
    return user


CurrentUser = Annotated[User, Depends(current_user)]
