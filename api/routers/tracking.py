from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from data.models import Ad, AdEvaluation, AdMarketSignals, AdTracking, TrackingStatus
from ..dependencies import get_session, get_user_name
from ..mappers import to_ad_summary, to_tracking_detail
from ..query import FEATURES_COUNT
from ..schemas import AdSummaryResponse, TrackingDetailResponse, TrackingEventRequest
from ..tracking import TrackingEventError, record_event

router = APIRouter(prefix="/api/tracking", tags=["tracking"])


@router.get("", response_model=list[AdSummaryResponse])
def list_tracked_ads(
        session: Annotated[Session, Depends(get_session)],
        statuses: Annotated[list[TrackingStatus], Query()] = [],
) -> list[AdSummaryResponse]:
    statement = (
        select(Ad, AdEvaluation, AdTracking, FEATURES_COUNT.label("features_count"), AdMarketSignals)
        .join(AdTracking, AdTracking.ad_id == Ad.id)
        .outerjoin(AdEvaluation, AdEvaluation.ad_id == Ad.id)
        .outerjoin(AdMarketSignals, AdMarketSignals.ad_id == Ad.id)
        .options(selectinload(Ad.images), selectinload(Ad.city), selectinload(Ad.district))
        .order_by(AdTracking.updated_at.desc())
    )
    if statuses:
        statement = statement.where(AdTracking.status.in_(statuses))

    return [
        to_ad_summary(ad, evaluation, tracking, features_count, None, signals)
        for ad, evaluation, tracking, features_count, signals in session.execute(statement).all()
    ]


@router.get("/{ad_id}", response_model=Optional[TrackingDetailResponse])
def get_tracking(
        ad_id: int,
        session: Annotated[Session, Depends(get_session)],
) -> Optional[TrackingDetailResponse]:
    tracking = session.get(AdTracking, ad_id)
    return to_tracking_detail(tracking) if tracking is not None else None


@router.post("/{ad_id}/events", response_model=TrackingDetailResponse, status_code=status.HTTP_201_CREATED)
def add_tracking_event(
        ad_id: int,
        request: TrackingEventRequest,
        session: Annotated[Session, Depends(get_session)],
        user_name: Annotated[Optional[str], Depends(get_user_name)],
) -> TrackingDetailResponse:
    ad = session.get(Ad, ad_id)
    if ad is None:
        raise HTTPException(status_code=404, detail=f"Ad {ad_id} not found")

    existing = session.get(AdTracking, ad_id)
    try:
        tracking = record_event(existing, ad, request, user_name, datetime.now(timezone.utc))
    except TrackingEventError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    if existing is None:
        session.add(tracking)
    session.flush()
    return to_tracking_detail(tracking)


@router.delete("/{ad_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tracking(
        ad_id: int,
        session: Annotated[Session, Depends(get_session)],
) -> Response:
    tracking = session.get(AdTracking, ad_id)
    if tracking is None:
        raise HTTPException(status_code=404, detail=f"Ad {ad_id} is not tracked")

    session.delete(tracking)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
