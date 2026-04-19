from __future__ import annotations

import pytest

from app.cleaning import (
    clean_name_fields,
    find_duplicate_groups,
    normalize_email,
    normalize_phone,
    process_batch,
)
from app.models import CustomerRecordIn


def test_normalize_email_valid() -> None:
    out, ok = normalize_email("  Jane.Doe+tag@Example.COM  ")
    assert ok is True
    assert out == "jane.doe@example.com"


def test_normalize_email_invalid() -> None:
    out, ok = normalize_email("not-an-email")
    assert ok is False
    assert out == "not-an-email"


def test_normalize_phone_us_valid() -> None:
    out, ok = normalize_phone("(415) 555-2671", "US")
    assert ok is True
    assert out == "+14155552671"


def test_normalize_phone_us_invalid() -> None:
    out, ok = normalize_phone("123", "US")
    assert ok is False
    assert out is None


def test_normalize_phone_gb_with_region() -> None:
    out, ok = normalize_phone("07970123456", "GB")
    assert ok is True
    assert out.startswith("+447")


def test_normalize_phone_wrong_region_invalid() -> None:
    """Local US-looking number without country code is not valid as GB national."""
    out, ok = normalize_phone("4155552671", "GB")
    assert ok is False


def test_name_splitting_from_full_only() -> None:
    rec = CustomerRecordIn.model_validate({"full_name": "  maria   rosa  garcia  "})
    fn, ln, full = clean_name_fields(rec)
    assert fn == "Maria"
    assert ln == "Rosa Garcia"
    assert full == "Maria Rosa Garcia"


def test_name_splitting_first_last_preferred_over_full() -> None:
    rec = CustomerRecordIn.model_validate({"first_name": "Lee", "last_name": "Kim", "full_name": "Ignore This"})
    fn, ln, full = clean_name_fields(rec)
    assert fn == "Lee"
    assert ln == "Kim"
    assert full == "Lee Kim"


def test_duplicate_grouping_by_email() -> None:
    rows = [
        {"email": "a@example.com", "company": "X"},
        {"email": "A@EXAMPLE.COM", "company": "Y"},
    ]
    cleaned, _, dups = process_batch(rows, "US")
    assert len(cleaned) == 2
    assert dups == [[0, 1]]


def test_duplicate_grouping_connected_components() -> None:
    """A matches B by email; B matches C by phone => one group."""
    rows = [
        {"email": "dup@example.com", "phone": "+12025550101", "company": "Co"},
        {"email": "dup@example.com", "phone": "+12025550202", "company": "Co"},
        {"email": "other@example.com", "phone": "+12025550202", "company": "Co"},
    ]
    _, _, dups = process_batch(rows, "US")
    assert dups == [[0, 1, 2]]


def test_warnings_invalid_email_and_phone() -> None:
    rows = [{"email": "bad", "phone": "123", "first_name": "A", "last_name": "B", "company": "C"}]
    _, warnings, _ = process_batch(rows, "US")
    fields = {w.field for w in warnings}
    assert "email" in fields
    assert "phone" in fields
