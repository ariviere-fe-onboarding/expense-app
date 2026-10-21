"""Sign-in, sign-out, and password reset."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import delete, select

from app.deps import SESSION_COOKIE, AppConfig, DbSession, Templates
from app.mailer import send_mail
from app.models import PasswordResetToken, User, UserSession, utcnow
from app.security import hash_password, new_token, token_hash, verify_password

router = APIRouter()

MIN_PASSWORD_LENGTH = 12
RESET_SENT = "If an account exists for that address, we've sent a link to reset its password."


@router.get("/login")
def login_form(request: Request, templates: Templates, session: DbSession) -> Response:
    """Show the sign-in form with the synthetic demo accounts."""
    users = session.scalars(select(User).order_by(User.role, User.name)).all()
    return templates.TemplateResponse(request, "login.html", {"demo_users": users})


@router.post("/login")
def login(
    request: Request,
    templates: Templates,
    session: DbSession,
    config: AppConfig,
    email: Annotated[str, Form(max_length=254)],
    password: Annotated[str, Form(max_length=200)],
) -> Response:
    """Verify credentials and start a session."""
    user = session.scalars(select(User).where(User.email == email.strip().lower())).first()
    if user is None or not verify_password(password, user.password_hash):
        users = session.scalars(select(User).order_by(User.role, User.name)).all()
        return templates.TemplateResponse(
            request,
            "login.html",
            {"demo_users": users, "error": "Email or password is incorrect."},
            status_code=401,
        )
    token = new_token()
    session.add(
        UserSession(
            token_hash=token_hash(token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(hours=config.session_hours),
        )
    )
    session.commit()
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=config.session_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=config.cookie_secure,
    )
    return response


@router.post("/logout")
def logout(request: Request, session: DbSession) -> Response:
    """End the current session."""
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        session.execute(delete(UserSession).where(UserSession.token_hash == token_hash(token)))
        session.commit()
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@router.get("/password-reset")
def reset_request_form(request: Request, templates: Templates) -> Response:
    """Show the form to request a reset link."""
    return templates.TemplateResponse(request, "reset_request.html", {})


@router.post("/password-reset")
def request_reset(
    request: Request,
    templates: Templates,
    session: DbSession,
    config: AppConfig,
    email: Annotated[str, Form(max_length=254)],
) -> Response:
    """Email a single-use reset link. The response never reveals whether the account exists."""
    user = session.scalars(select(User).where(User.email == email.strip().lower())).first()
    if user is not None:
        session.execute(
            delete(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)
            )
        )
        token = new_token()
        session.add(
            PasswordResetToken(
                token_hash=token_hash(token),
                user_id=user.id,
                expires_at=utcnow() + timedelta(minutes=config.reset_token_minutes),
            )
        )
        session.commit()
        send_mail(
            config.mail_dir,
            user.email,
            "Reset your Fernway password",
            f"Use this link within {config.reset_token_minutes} minutes:\n\n"
            f"{config.public_origin}/password-reset/confirm?token={token}\n",
        )
    return templates.TemplateResponse(request, "message.html", {"message": RESET_SENT})


def _valid_token(session: DbSession, token: str) -> PasswordResetToken | None:
    record = session.get(PasswordResetToken, token_hash(token))
    if record is None or record.used_at is not None:
        return None
    if record.expires_at.replace(tzinfo=utcnow().tzinfo) <= utcnow():
        return None
    return record


@router.get("/password-reset/confirm")
def reset_confirm_form(
    request: Request, templates: Templates, session: DbSession, token: str | None = None
) -> Response:
    """Show the new-password form for a valid token."""
    if token is None or _valid_token(session, token) is None:
        return templates.TemplateResponse(
            request,
            "message.html",
            {"message": "This reset link is invalid or has expired."},
            status_code=400,
        )
    return templates.TemplateResponse(request, "reset_confirm.html", {"token": token})


@router.post("/password-reset/confirm")
def reset_confirm(
    request: Request,
    templates: Templates,
    session: DbSession,
    token: Annotated[str, Form(max_length=200)],
    password: Annotated[str, Form(max_length=200)],
) -> Response:
    """Set a new password, consume the token, and sign out every session for the user."""
    record = _valid_token(session, token)
    if record is None:
        return templates.TemplateResponse(
            request,
            "message.html",
            {"message": "This reset link is invalid or has expired."},
            status_code=400,
        )
    if len(password) < MIN_PASSWORD_LENGTH:
        return templates.TemplateResponse(
            request,
            "reset_confirm.html",
            {"token": token, "error": f"Use at least {MIN_PASSWORD_LENGTH} characters."},
            status_code=400,
        )
    user = session.get(User, record.user_id)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    user.password_hash = hash_password(password)
    record.used_at = utcnow()
    session.execute(delete(UserSession).where(UserSession.user_id == user.id))
    session.commit()
    return templates.TemplateResponse(
        request, "message.html", {"message": "Password updated. Sign in with your new password."}
    )
