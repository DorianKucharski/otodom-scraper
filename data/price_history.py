from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import text

from .models import Ad, AdPriceObservation, status_value

BACKFILL_MISSING_OBSERVATIONS = text("""
INSERT INTO ad_price_observations (ad_id, observed_at, price_value, area_value, status)
SELECT a.id, coalesce(a.scraped_at, a.modified_at), a.price_value, a.area_value, a.status
FROM ads a
WHERE a.price_value > 0
  AND NOT EXISTS (SELECT 1 FROM ad_price_observations o WHERE o.ad_id = a.id)
""")


@dataclass(frozen=True)
class PriceState:
    price_value: Optional[int]
    area_value: Optional[float]
    status: Optional[str]


def price_state_of(ad: Ad) -> PriceState:
    return PriceState(
        price_value=ad.price_value,
        area_value=float(ad.area_value) if ad.area_value is not None else None,
        status=status_value(ad.status),
    )


def baseline_observation(ad_id: int, previous: PriceState, seen_at: datetime) -> Optional[AdPriceObservation]:
    if not previous.price_value:
        return None
    return AdPriceObservation(
        ad_id=ad_id,
        observed_at=seen_at,
        price_value=previous.price_value,
        area_value=previous.area_value,
        status=previous.status,
    )


def price_observation(ad: Ad, previous: Optional[PriceState], observed_at: datetime) -> Optional[AdPriceObservation]:
    current = price_state_of(ad)
    if not current.price_value:
        return None
    if previous is not None and previous == current:
        return None
    return AdPriceObservation(
        ad_id=ad.id,
        observed_at=observed_at,
        price_value=current.price_value,
        area_value=current.area_value,
        status=current.status,
    )
