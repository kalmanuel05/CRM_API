from __future__ import annotations

from app.csv_utils import dicts_from_csv


def test_csv_upload_parsing_headers_and_rows() -> None:
    raw = b"email,First Name,company\njane@example.com,Jane,Acme\n"
    rows = dicts_from_csv(raw)
    assert rows == [{"email": "jane@example.com", "First Name": "Jane", "company": "Acme"}]


def test_csv_skips_completely_empty_rows() -> None:
    raw = b"a,b\n,\n"
    rows = dicts_from_csv(raw)
    assert rows == []
