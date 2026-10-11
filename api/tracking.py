from __future__ import annotations

from datetime import datetime
from typing import Optional

from data.models import Ad, AdTracking, AdTrackingEvent, TrackingStatus
from .schemas import TrackingEventRequest


class TrackingEventError(ValueError):
    pass


def record_event(
        tracking: Optional[AdTracking],
        ad: Ad,
        request: TrackingEventRequest,
        author: Optional[str],
        now: datetime,
) -> AdTracking:
    comment = (request.comment or "").strip() or None
    viewing_at = request.viewing_at.replace(tzinfo=None) if request.viewing_at else None

    if request.status is None and comment is None:
        raise TrackingEventError("Podaj nowy status albo komentarz")
    if tracking is None and request.status is None:
        raise TrackingEventError("Pierwszy wpis musi ustawić status")
    if request.status is TrackingStatus.VIEWING_SCHEDULED and viewing_at is None:
        raise TrackingEventError("Umówione oglądanie wymaga daty i godziny")

    if tracking is None:
        tracking = AdTracking(ad_id=ad.id, price_at_save=ad.price_value, created_at=now)

    if request.status is not None:
        tracking.status = request.status
    if viewing_at is not None:
        tracking.viewing_at = viewing_at
    if request.rating is not None:
        tracking.rating = request.rating
    if request.offer_amount is not None:
        tracking.offer_amount = request.offer_amount
    if comment is not None:
        tracking.last_comment = comment

    tracking.updated_at = now
    tracking.updated_by = author
    tracking.events.append(AdTrackingEvent(
        ad_id=ad.id,
        status=request.status,
        comment=comment,
        viewing_at=viewing_at,
        rating=request.rating,
        offer_amount=request.offer_amount,
        author=author,
        created_at=now,
    ))

    return tracking
