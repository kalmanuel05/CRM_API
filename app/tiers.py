from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TierId(str, Enum):
    FREE = "free"
    STARTER = "starter"
    GROWTH = "growth"
    PRO = "pro"


@dataclass(frozen=True)
class TierLimits:
    requests_per_minute: int
    requests_per_month: int
    max_batch_records: int
    display_name: str
    price_usd_month: int | None


TIER_LIMITS: dict[TierId, TierLimits] = {
    TierId.FREE: TierLimits(
        requests_per_minute=5,
        requests_per_month=500,
        max_batch_records=50,
        display_name="Free",
        price_usd_month=0,
    ),
    TierId.STARTER: TierLimits(
        requests_per_minute=20,
        requests_per_month=10_000,
        max_batch_records=200,
        display_name="Starter",
        price_usd_month=10,
    ),
    TierId.GROWTH: TierLimits(
        requests_per_minute=60,
        requests_per_month=100_000,
        max_batch_records=500,
        display_name="Growth",
        price_usd_month=30,
    ),
    TierId.PRO: TierLimits(
        requests_per_minute=300,
        requests_per_month=250_000,
        max_batch_records=1000,
        display_name="Pro",
        price_usd_month=100,
    ),
}
