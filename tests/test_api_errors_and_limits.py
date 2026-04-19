from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.auth_deps import AuthContext, enforce_rate_limit
from app.main import app
from app.tiers import TierId


def _assert_error_envelope(data: dict, *, code: str | None = None) -> str:
    assert "error" in data
    err = data["error"]
    assert "code" in err
    assert "message" in err
    assert "request_id" in err
    assert err["request_id"]
    if code is not None:
        assert err["code"] == code
    return str(err["request_id"])


def test_error_response_has_code_message_request_id(client) -> None:
    """JSON body: Pydantic rejects unknown export_format with VALIDATION_ERROR before route logic."""
    r = client.post("/v1/clean", json={"records": [], "export_format": "not-a-format"})
    assert r.status_code == 422
    rid = _assert_error_envelope(r.json(), code="VALIDATION_ERROR")
    assert r.headers.get("X-Request-Id") == rid


def test_invalid_export_format_csv_form(client) -> None:
    """CSV uses string form field; invalid value hits _parse_export_format -> INVALID_EXPORT_FORMAT."""
    files = {"file": ("a.csv", io.BytesIO(b"email\na@b.com\n"), "text/csv")}
    data = {"export_format": "not-a-format", "default_phone_region": "US"}
    r = client.post("/v1/clean/csv", files=files, data=data)
    assert r.status_code == 422
    _assert_error_envelope(r.json(), code="INVALID_EXPORT_FORMAT")


def test_batch_size_rejection_by_tier_free(monkeypatch: pytest.MonkeyPatch) -> None:
    async def free_auth() -> AuthContext:
        return AuthContext(api_key="k", tier=TierId.FREE, fingerprint="fp", auth_disabled=True)

    app.dependency_overrides[enforce_rate_limit] = free_auth
    try:
        records = [{"first_name": "x", "last_name": "y", "email": f"u{i}@e.com", "company": "c"} for i in range(51)]
        with TestClient(app) as c:
            r = c.post("/v1/clean", json={"records": records})
        assert r.status_code == 422
        _assert_error_envelope(r.json(), code="BATCH_TOO_LARGE")
    finally:
        app.dependency_overrides.pop(enforce_rate_limit, None)


def test_pro_tier_monthly_quota_in_settings() -> None:
    from app.tiers import TIER_LIMITS

    assert TIER_LIMITS[TierId.PRO].requests_per_month == 250_000


def test_csv_upload_json_response(client) -> None:
    files = {"file": ("leads.csv", io.BytesIO(b"email,name\na@b.com,Alice\n"), "text/csv")}
    data = {"default_phone_region": "US", "export_format": "generic"}
    r = client.post("/v1/clean/csv", files=files, data=data)
    assert r.status_code == 200
    body = r.json()
    assert "cleaned_records" in body
    assert body["cleaned_records"][0]["email"] == "a@b.com"


def test_invalid_api_key(monkeypatch: pytest.MonkeyPatch, clear_settings_cache) -> None:
    monkeypatch.setenv("CRM_AUTH_DISABLED", "false")
    monkeypatch.setenv("CRM_API_KEYS", "sk_valid:free")
    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as c:
        r = c.post("/v1/clean", json={"records": []}, headers={"X-API-Key": "wrong"})
    assert r.status_code == 401
    _assert_error_envelope(r.json(), code="INVALID_API_KEY")
    get_settings.cache_clear()
    monkeypatch.delenv("CRM_API_KEYS", raising=False)


def test_rate_limited_response(monkeypatch: pytest.MonkeyPatch, clear_settings_cache) -> None:
    monkeypatch.setenv("CRM_AUTH_DISABLED", "false")
    monkeypatch.setenv("CRM_API_KEYS", "sk_rl:free")
    from app.config import get_settings
    from app.rate_limit import state as rate_limit_state

    get_settings.cache_clear()

    def boom(*_a, **_k):
        return False, "Rate limit exceeded for test.", "RATE_LIMITED_MINUTE"

    monkeypatch.setattr(rate_limit_state, "check_and_record", boom)
    with TestClient(app) as c:
        r = c.post("/v1/clean", json={"records": []}, headers={"X-API-Key": "sk_rl"})
    assert r.status_code == 429
    _assert_error_envelope(r.json(), code="RATE_LIMITED_MINUTE")
    get_settings.cache_clear()
    monkeypatch.delenv("CRM_API_KEYS", raising=False)


def test_json_body_size_limit_headers(client, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import HttpLimits

    # Middleware uses Content-Length; any real JSON body is larger than 1 byte.
    monkeypatch.setattr("app.main.get_http_limits", lambda: HttpLimits(1, 5 * 1024 * 1024))
    r = client.post("/v1/clean", json={"records": []})
    assert r.status_code == 413
    _assert_error_envelope(r.json(), code="PAYLOAD_TOO_LARGE")
