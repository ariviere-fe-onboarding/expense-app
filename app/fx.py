"""Exchange rates for foreign-currency expenses. Rates are reviewed monthly by Finance."""

from __future__ import annotations

SUPPORTED_CURRENCIES = ("USD", "EUR", "GBP", "CAD")

# USD per one unit of each currency, October 2026 Finance rate table.
RATES_TO_USD: dict[str, float] = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
    "CAD": 0.73,
}


def to_usd(amount_cents: int, currency: str) -> float:
    """Convert an amount in the expense's currency to US dollars."""
    return amount_cents / 100 * RATES_TO_USD[currency]
