"""Exchange rates for foreign-currency expenses. Rates are reviewed monthly by Finance."""

from __future__ import annotations

from fractions import Fraction

SUPPORTED_CURRENCIES = ("USD", "EUR", "GBP", "CAD")

# USD per one unit of each currency, October 2026 Finance rate table.
RATES_TO_USD: dict[str, Fraction] = {
    "USD": Fraction(1),
    "EUR": Fraction(108, 100),
    "GBP": Fraction(127, 100),
    "CAD": Fraction(73, 100),
}


def to_usd(amount_cents: int, currency: str) -> int:
    """Convert to integer USD cents, rounding once to nearest, half cents away from zero."""
    rate = RATES_TO_USD[currency]
    cents, remainder = divmod(abs(amount_cents) * rate.numerator, rate.denominator)
    cents += int(remainder * 2 >= rate.denominator)
    return -cents if amount_cents < 0 else cents
