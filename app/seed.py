"""Synthetic Fernway employees and expenses for local demos."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import Category, Expense, ExpenseStatus, Role, User
from app.security import hash_password

# (id, name, team, role, manager). IDs match the bank accounts seeded in payouts-service.
DEMO_USERS: tuple[tuple[str, str, str, Role, str | None], ...] = (
    ("emp-marcus", "Marcus Bell", "Design", Role.MANAGER, None),
    ("emp-lena", "Lena Ortiz", "Sales", Role.MANAGER, None),
    ("emp-priya", "Priya Nair", "Design", Role.EMPLOYEE, "emp-marcus"),
    ("emp-jonah", "Jonah Park", "Sales", Role.EMPLOYEE, "emp-lena"),
    ("emp-dana", "Dana Whitfield", "Finance", Role.FINANCE, None),
)

# (submitter, merchant, description, category, cents, days ago, status)
DEMO_EXPENSES: tuple[tuple[str, str, str, Category, int, int, ExpenseStatus], ...] = (
    (
        "emp-priya",
        "Brightline Rail",
        "Train to the Portland design review",
        Category.TRAVEL,
        8_640,
        12,
        ExpenseStatus.APPROVED,
    ),
    (
        "emp-priya",
        "Figment Fonts",
        "Annual license for the brand typeface",
        Category.SOFTWARE,
        24_900,
        3,
        ExpenseStatus.SUBMITTED,
    ),
    (
        "emp-priya",
        "Harborview Hotel",
        "Two nights for the client workshop",
        Category.LODGING,
        61_800,
        6,
        ExpenseStatus.SUBMITTED,
    ),
    (
        "emp-jonah",
        "Cedar & Salt",
        "Dinner with the Alder Freight account team",
        Category.MEALS,
        18_450,
        2,
        ExpenseStatus.SUBMITTED,
    ),
    (
        "emp-marcus",
        "Monitor Depot",
        "External monitor for the design lab",
        Category.EQUIPMENT,
        32_999,
        4,
        ExpenseStatus.AWAITING_FINANCE,
    ),
)


def email_for(user_id: str) -> str:
    """Return the synthetic email address for a demo user ID."""
    return f"{user_id.removeprefix('emp-')}@fernway.example"


def seed(session: Session, demo_password: str, today: date | None = None) -> int:
    """Insert demo users and expenses if the database is empty. Returns users added."""
    if session.get(User, DEMO_USERS[0][0]) is not None:
        return 0
    password_hash = hash_password(demo_password)
    for user_id, name, team, role, manager_id in DEMO_USERS:
        session.add(
            User(
                id=user_id,
                email=email_for(user_id),
                name=name,
                team=team,
                role=role,
                manager_id=manager_id,
                password_hash=password_hash,
            )
        )
    session.flush()
    base = today or date.today()
    for submitter, merchant, description, category, cents, days, status in DEMO_EXPENSES:
        session.add(
            Expense(
                submitter_id=submitter,
                merchant=merchant,
                description=description,
                category=category,
                amount_cents=cents,
                spent_on=base - timedelta(days=days),
                status=status,
            )
        )
    session.commit()
    return len(DEMO_USERS)
