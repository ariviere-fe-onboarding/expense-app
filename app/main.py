"""FastAPI application factory, middleware, and error handling."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import Config, get_config
from app.db import Base, make_engine, make_session_factory
from app.deps import LoginRequired
from app.models import Category, ExpenseStatus
from app.money import format_cents
from app.payouts_client import PayoutsClient
from app.routes import approvals, auth, expenses, profile

PACKAGE_DIR = Path(__file__).parent
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

SECURITY_HEADERS = {
    "content-security-policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
        "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    ),
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "cache-control": "no-store",
}

STATUS_LABELS = {
    ExpenseStatus.SUBMITTED: "Awaiting manager",
    ExpenseStatus.AWAITING_FINANCE: "Awaiting finance",
    ExpenseStatus.APPROVED: "Approved",
    ExpenseStatus.REJECTED: "Rejected",
}


def build_templates() -> Jinja2Templates:
    """Create the template renderer with autoescaping and display filters."""
    templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
    templates.env.filters["cents"] = format_cents
    templates.env.globals["status_labels"] = STATUS_LABELS
    templates.env.globals["category_labels"] = {c: c.value.title() for c in Category}
    return templates


def create_app(
    config: Config | None = None, transport: httpx.BaseTransport | None = None
) -> FastAPI:
    """Build expense-app. Tests pass their own config and a mock payouts transport."""
    cfg = config or get_config()
    engine = make_engine(cfg.database_url)
    Base.metadata.create_all(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(
        title="Fernway expenses", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    app.state.config = cfg
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.templates = build_templates()
    app.state.payouts = PayoutsClient(cfg, transport)

    @app.middleware("http")
    async def same_origin_and_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Cookie-authenticated form posts must come from our own pages (CSRF defense).
        if request.method in UNSAFE_METHODS and request.headers.get("origin") != cfg.public_origin:
            response: Response = PlainTextResponse("Cross-origin request blocked.", status_code=403)
        else:
            response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    @app.exception_handler(LoginRequired)
    async def login_required(_: Request, __: LoginRequired) -> Response:
        return RedirectResponse("/login", status_code=303)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> Response:
        renderer: Jinja2Templates = app.state.templates
        return renderer.TemplateResponse(
            request, "message.html", {"message": error.detail}, status_code=error.status_code
        )

    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
    for router in (auth.router, expenses.router, approvals.router, profile.router):
        app.include_router(router)
    return app
