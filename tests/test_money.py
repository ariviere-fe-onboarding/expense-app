"""Regression coverage for integer-cent parsing and display boundaries."""

import pytest

from app.money import AmountError, format_cents, parse_amount


@pytest.mark.parametrize(
    ("text", "expected_cents"),
    [
        ("0.01", 1),
        ("0.10", 10),
        ("0.99", 99),
        ("1", 100),
        ("1.00", 100),
        ("1.01", 101),
        ("9.99", 999),
        ("10", 1000),
        ("42.50", 4250),
        ("99.99", 9999),
        ("100", 10000),
        ("499.99", 49999),
        ("500.00", 50000),
        ("500.01", 50001),
        ("999.99", 99999),
        ("1,000.00", 100000),
        ("1,234.56", 123456),
        ("9,999.99", 999999),
        ("10,000.00", 1000000),
        ("$0.01", 1),
        ("$12", 1200),
        ("$42.50", 4250),
        ("$1,234.56", 123456),
        ("$10,000.00", 1000000),
        (" 42.50 ", 4250),
        ("\t42.50\n", 4250),
        ("001.00", 100),
        ("12.5", 1250),
        (".50", 50),
        ("0.1", 10),
    ],
)
def test_parse_valid_amount(text: str, expected_cents: int) -> None:
    """Accepted dollar strings retain their exact integer-cent value."""
    assert parse_amount(text) == expected_cents


@pytest.mark.parametrize(
    "text",
    [
        "",
        " ",
        "abc",
        "$",
        "USD 12",
        "12 USD",
        "1.2.3",
        "--1",
        "12.345",
        "0.001",
        "1.000",
        "9999.999",
        "0",
        "0.00",
        "-0",
        "-0.00",
        "-0.01",
        "-1",
        "-42.50",
        "10000.01",
        "10001",
        "20000",
        "$10,000.01",
        "NaN",
        "Infinity",
        "-Infinity",
    ],
)
def test_parse_invalid_amount(text: str) -> None:
    """Invalid, nonpositive, overprecise, and over-limit inputs are rejected."""
    with pytest.raises(AmountError):
        parse_amount(text)


@pytest.mark.parametrize(
    ("amount_cents", "currency", "expected"),
    [
        (0, "USD", "$0.00"),
        (1, "USD", "$0.01"),
        (9, "USD", "$0.09"),
        (10, "USD", "$0.10"),
        (99, "USD", "$0.99"),
        (100, "USD", "$1.00"),
        (101, "USD", "$1.01"),
        (999, "USD", "$9.99"),
        (1000, "USD", "$10.00"),
        (4250, "USD", "$42.50"),
        (49999, "USD", "$499.99"),
        (50000, "USD", "$500.00"),
        (50001, "USD", "$500.01"),
        (99999, "USD", "$999.99"),
        (100000, "USD", "$1,000.00"),
        (123456, "USD", "$1,234.56"),
        (1000000, "USD", "$10,000.00"),
        (-1, "USD", "-$0.01"),
        (-99, "USD", "-$0.99"),
        (-100, "USD", "-$1.00"),
        (-123456, "USD", "-$1,234.56"),
        (0, "EUR", "EUR 0.00"),
        (1, "EUR", "EUR 0.01"),
        (123456, "EUR", "EUR 1,234.56"),
        (-123456, "EUR", "-EUR 1,234.56"),
        (100, "GBP", "GBP 1.00"),
        (123456, "CAD", "CAD 1,234.56"),
        (123456, "AUD", "AUD 1,234.56"),
    ],
)
def test_format_amount(amount_cents: int, currency: str, expected: str) -> None:
    """Formatting preserves signs, grouping, fractions, and currency labels."""
    assert format_cents(amount_cents, currency) == expected
