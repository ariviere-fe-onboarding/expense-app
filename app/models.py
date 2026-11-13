"""Persistence models. Amounts are integer cents; tokens are stored only as hashes."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(UTC)


class Role(StrEnum):
    """What a user may do. Managers approve their reports; finance gives final approval."""

    EMPLOYEE = "employee"
    MANAGER = "manager"
    FINANCE = "finance"


class ExpenseStatus(StrEnum):
    """Lifecycle of an expense."""

    SUBMITTED = "submitted"
    AWAITING_FINANCE = "awaiting_finance"
    APPROVED = "approved"
    REJECTED = "rejected"


class Category(StrEnum):
    """Expense policy categories."""

    TRAVEL = "travel"
    MEALS = "meals"
    LODGING = "lodging"
    SOFTWARE = "software"
    EQUIPMENT = "equipment"
    OTHER = "other"


class User(Base):
    """An employee. IDs match employee IDs in payouts-service."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    team: Mapped[str] = mapped_column(String(50))
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False))
    manager_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(300))


class Expense(Base):
    """A reimbursement request with its receipt."""

    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submitter_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    merchant: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[Category] = mapped_column(Enum(Category, native_enum=False))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    spent_on: Mapped[date] = mapped_column(Date)
    status: Mapped[ExpenseStatus] = mapped_column(
        Enum(ExpenseStatus, native_enum=False), default=ExpenseStatus.SUBMITTED
    )
    receipt_file: Mapped[str | None] = mapped_column(String(64), nullable=True)
    receipt_content_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    submitter: Mapped[User] = relationship()
    approvals: Mapped[list[Approval]] = relationship(
        back_populates="expense", order_by="Approval.created_at"
    )


class Approval(Base):
    """One approval or rejection decision on an expense."""

    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), index=True)
    approver_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    expense: Mapped[Expense] = relationship(back_populates="approvals")
    approver: Mapped[User] = relationship()


class Delegation(Base):
    """A manager's approvals handed to another manager while they are away."""

    __tablename__ = "delegations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manager_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    delegate_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)

    delegate: Mapped[User] = relationship(foreign_keys=[delegate_id])


class UserSession(Base):
    """A login session. Only the SHA-256 of the cookie token is stored."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PasswordResetToken(Base):
    """A single-use password reset token. Only its SHA-256 is stored."""

    __tablename__ = "password_reset_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WebhookDelivery(Base):
    """Transactional outbox for webhooks to payouts-service."""

    __tablename__ = "webhook_deliveries"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), unique=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(200), nullable=True)
