from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from app.tiers import TierId

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def env_flag(name: str, *, default: bool = False) -> bool:
    """Parse CRM_* boolean env vars (false/0/no/off are false; unset uses default)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY


@dataclass(frozen=True)
class HttpLimits:
    """HTTP input guards (bytes)."""

    max_json_body_bytes: int
    max_csv_upload_bytes: int


def get_http_limits() -> HttpLimits:
    return HttpLimits(
        max_json_body_bytes=int(os.environ.get("CRM_MAX_JSON_BYTES", str(10 * 1024 * 1024))),
        max_csv_upload_bytes=int(os.environ.get("CRM_MAX_CSV_BYTES", str(5 * 1024 * 1024))),
    )


def get_diagnostics_secret() -> str | None:
    raw = os.environ.get("CRM_DIAGNOSTICS_SECRET", "").strip()
    return raw or None


def _parse_api_keys(raw: str | None) -> dict[str, TierId]:
    """
    Env CRM_API_KEYS: comma-separated entries key:tier
    Example: sk_abc123:free,sk_def456:starter
    """
    out: dict[str, TierId] = {}
    if not raw or not raw.strip():
        return out
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            continue
        key, tier_s = part.rsplit(":", 1)
        key = key.strip()
        tier_s = tier_s.strip().lower()
        try:
            out[key] = TierId(tier_s)
        except ValueError:
            continue
    return out


@lru_cache
def get_settings() -> tuple[dict[str, TierId], bool, str]:
    keys = _parse_api_keys(os.environ.get("CRM_API_KEYS"))
    auth_disabled = env_flag("CRM_AUTH_DISABLED", default=False)
    log_path = os.environ.get("CRM_USAGE_LOG_PATH", "logs/usage.jsonl")
    return keys, auth_disabled, log_path
