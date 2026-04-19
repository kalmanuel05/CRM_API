from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock

from app.tiers import TierId, TIER_LIMITS


def _month_key(ts: float | None = None) -> str:
    t = time.gmtime(ts or time.time())
    return f"{t.tm_year:04d}-{t.tm_mon:02d}"


@dataclass
class RateLimitState:
    _lock: Lock = field(default_factory=Lock)
    _minute_hits: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))
    _monthly: dict[str, tuple[str, int]] = field(default_factory=dict)

    def check_and_record(self, api_key: str, tier: TierId) -> tuple[bool, str | None, str | None]:
        limits = TIER_LIMITS[tier]
        now = time.monotonic()
        month = _month_key()

        with self._lock:
            dq = self._minute_hits[api_key]
            while dq and now - dq[0] >= 60.0:
                dq.popleft()
            if len(dq) >= limits.requests_per_minute:
                return (
                    False,
                    f"Rate limit exceeded: {limits.requests_per_minute} requests per minute for tier {tier.value}.",
                    "RATE_LIMITED_MINUTE",
                )

            mkey, count = self._monthly.get(api_key, (month, 0))
            if mkey != month:
                mkey, count = month, 0
            if count >= limits.requests_per_month:
                return (
                    False,
                    f"Monthly quota exceeded: {limits.requests_per_month} requests for tier {tier.value}.",
                    "RATE_LIMITED_MONTHLY",
                )
            count += 1
            self._monthly[api_key] = (mkey, count)
            dq.append(now)

        return True, None, None

    def monthly_used(self, api_key: str) -> int:
        month = _month_key()
        with self._lock:
            mkey, count = self._monthly.get(api_key, (month, 0))
            if mkey != month:
                return 0
            return count


state = RateLimitState()
