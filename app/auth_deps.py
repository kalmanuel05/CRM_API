from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request, status

from app.config import get_settings
from app.errors import raise_api_error
from app.rate_limit import state as rate_limit_state
from app.tiers import TierId, TIER_LIMITS
import os

class AuthContext:
    __slots__ = ("api_key", "tier", "fingerprint", "auth_disabled")

    def __init__(
        self,
        *,
        api_key: str,
        tier: TierId,
        fingerprint: str,
        auth_disabled: bool,
    ) -> None:
        self.api_key = api_key
        self.tier = tier
        self.fingerprint = fingerprint
        self.auth_disabled = auth_disabled


def _resolve_tier_for_key(api_key: str, key_map: dict[str, TierId]) -> TierId:
    if api_key in key_map:
        return key_map[api_key]
    raise_api_error(
        status.HTTP_401_UNAUTHORIZED,
        "INVALID_API_KEY",
        "Invalid or missing API key.",
    )


async def require_api_key(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    authorization: Annotated[str | None, Header()] = None,
    x_rapidapi_proxy_secret: Annotated[str | None, Header(alias="X-RapidAPI-Proxy-Secret")] = None,
    x_rapidapi_subscription: Annotated[str | None, Header(alias="X-RapidAPI-Subscription")] = None,
    x_rapidapi_user: Annotated[str | None, Header(alias="X-RapidAPI-User")] = None,
) -> AuthContext:
    key_map, auth_disabled, _ = get_settings()

    if auth_disabled:
        return AuthContext(
            api_key="dev",
            tier=TierId.PRO,
            fingerprint="dev",
            auth_disabled=True,
        )

    # RapidAPI proxy validation
    expected_proxy_secret = os.environ.get("RAPIDAPI_PROXY_SECRET", "").strip()
    if expected_proxy_secret and x_rapidapi_proxy_secret == expected_proxy_secret:
        subscription = (x_rapidapi_subscription or "free").strip().lower()

        rapidapi_tier_map = {
            "free": TierId.FREE,
            "starter": TierId.STARTER,
            "growth": TierId.GROWTH,
            "pro": TierId.PRO,
        }
        tier = rapidapi_tier_map.get(subscription, TierId.FREE)

        fingerprint = f"rapidapi:{x_rapidapi_user or 'anonymous'}"
        return AuthContext(
            api_key=f"rapidapi:{x_rapidapi_user or 'anonymous'}",
            tier=tier,
            fingerprint=fingerprint,
            auth_disabled=False,
        )

    # Normal direct API key auth
    raw = x_api_key
    if not raw and authorization and authorization.lower().startswith("bearer "):
        raw = authorization[7:].strip()

    if not raw:
        raise_api_error(
            status.HTTP_401_UNAUTHORIZED,
            "MISSING_API_KEY",
            "Send X-API-Key, Authorization: Bearer <key>, or a valid RapidAPI proxy request.",
        )

    tier = _resolve_tier_for_key(raw, key_map)
    from app.usage_log import fingerprint_key

    return AuthContext(
        api_key=raw,
        tier=tier,
        fingerprint=fingerprint_key(raw),
        auth_disabled=False,
    )


async def enforce_rate_limit(auth: Annotated[AuthContext, Depends(require_api_key)]) -> AuthContext:
    if auth.auth_disabled:
        return auth
    ok, msg, code = rate_limit_state.check_and_record(auth.api_key, auth.tier)
    if not ok:
        raise_api_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            code or "RATE_LIMITED",
            msg or "Rate limited.",
        )
    return auth


def max_batch_for_tier(tier: TierId) -> int:
    return TIER_LIMITS[tier].max_batch_records
