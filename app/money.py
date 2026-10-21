"""Money parsing and display. Amounts are always integer cents."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

MAX_EXPENSE_CENTS = 1_000_000


class AmountError(ValueError):
    """Raised when a user-entered amount is not a valid positive dollar amount."""


def parse_amount(text: str) -> int:
    """Convert '1,234.50' or '$12' to integer cents without floating point."""
    cleaned = text.strip().removeprefix("$").replace(",", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation as error:
        raise AmountError("Enter an amount like 42.50.") from error
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -2:
        raise AmountError("Enter an amount with at most two decimal places.")
    cents = int(value * 100)
    if cents <= 0:
        raise AmountError("Amount must be greater than zero.")
    if cents > MAX_EXPENSE_CENTS:
        raise AmountError("Expenses over $10,000.00 must go through procurement.")
    return cents


def format_cents(cents: int, currency: str = "USD") -> str:
    """Render integer cents as '$1,234.50'."""
    symbol = "$" if currency == "USD" else f"{currency} "
    sign = "-" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return f"{sign}{symbol}{whole:,}.{fraction:02d}"
