from __future__ import annotations

import pytest

from app.fx import to_usd


@pytest.mark.parametrize(
    ("currency", "amount_cents", "usd_cents"),
    [
        ("USD", 123_456, 123_456),
        ("EUR", 8_500, 9_180),
        ("GBP", 1, 1),
        ("GBP", 2, 3),
        ("GBP", 50, 64),
        ("CAD", 50, 37),
        ("CAD", 1, 1),
        ("CAD", 2, 1),
        ("CAD", 0, 0),
        ("CAD", -50, -37),
        ("GBP", -50, -64),
    ],
)
def test_to_usd_rounds_once_to_integer_cents(
    currency: str, amount_cents: int, usd_cents: int
) -> None:
    converted = to_usd(amount_cents, currency)
    assert type(converted) is int
    assert converted == usd_cents
