from __future__ import annotations

import os

import pytest

# Default: dev mode (Pro limits) so tests do not require real API keys.
os.environ.setdefault("CRM_AUTH_DISABLED", "true")


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def clear_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
