from __future__ import annotations

import io

import pytest

from app.config import HttpLimits


def test_csv_upload_rejected_when_bytes_exceed_cap(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.get_http_limits", lambda: HttpLimits(10 * 1024 * 1024, 100))
    blob = b"email\n" + (b"x@y.com\n" * 50)
    assert len(blob) > 100
    files = {"file": ("big.csv", io.BytesIO(blob), "text/csv")}
    r = client.post("/v1/clean/csv", files=files, data={"default_phone_region": "US"})
    assert r.status_code == 413
    err = r.json()["error"]
    assert err["code"] == "CSV_TOO_LARGE"
