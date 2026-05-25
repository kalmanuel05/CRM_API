from __future__ import annotations

import os

import pytest

# Match .env.example defaults so API tests work without a local .env file.
TEST_API_KEY = "sk_test_free"
os.environ.setdefault("CRM_AUTH_DISABLED", "false")
os.environ.setdefault("CRM_API_KEYS", f"{TEST_API_KEY}:free")


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    get_settings.cache_clear()
    with TestClient(app, headers={"X-API-Key": TEST_API_KEY}) as c:
        yield c
    get_settings.cache_clear()


@pytest.fixture
def clear_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
