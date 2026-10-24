from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from data.models import Ad, AdEvaluation, AdMarketSignals, AdPriceObservation, AdScreening, AdTracking, Owner
from data.read_models import ad_all_features, district_price_stats
from ..dependencies import get_session
from ..mappers import to_ad_detail, to_ad_summary, to_market_signals
from ..query import build_search_statements
from ..labels import ADVERTISER_TYPES, display_label
from ..schemas import (
    AdDetailResponse, AdSearchQuery, AdSearchResponse, ListingHistoryEntry, ListingHistoryResponse, MarketStatsResponse,
    PriceObservationResponse,
)

router = APIRouter(prefix="/api/ads", tags=["ads"])

_AD_RELATIONS = (
    Ad.images,
    Ad.features,
    Ad.flat_equipment,
    Ad.flat_areas,
    Ad.flat_parking,
    Ad.building_windows,
    Ad.building_conveniences,
    Ad.building_security,
    Ad.city,
    Ad.district,
    Ad.county,
    Ad.province,
)


@router.get("", response_model=AdSearchResponse)
def search_ads(
        query: Annotated[AdSearchQuery, Query()],
        session: Annotated[Session, Depends(get_session)],
) -> AdSearchResponse:
    statements = build_search_statements(query)
    ad_ids = list(session.execute(statements.page).scalars())
    rows = session.execute(
        statements.rows_for(ad_ids).options(selectinload(Ad.images), selectinload(Ad.city), selectinload(Ad.district))
    ).all() if ad_ids else []
    position = {ad_id: index for index, ad_id in enumerate(ad_ids)}
    rows = sorted(rows, key=lambda row: position[row[0].id])
    total = session.execute(statements.total).scalar_one()

    return AdSearchResponse(
        total=total,
        limit=query.limit,
        offset=query.offset,
        items=[
            to_ad_summary(ad, evaluation, tracking, features_count, distance_m, signals)
            for ad, evaluation, tracking, features_count, distance_m, signals in rows
        ],
    )


@router.get("/{ad_id}", response_model=AdDetailResponse)
def get_ad(
        ad_id: int,
        session: Annotated[Session, Depends(get_session)],
) -> AdDetailResponse:
    ad = session.execute(
        select(Ad).options(*(selectinload(relation) for relation in _AD_RELATIONS)).where(Ad.id == ad_id)
    ).scalar_one_or_none()

    if ad is None:
        raise HTTPException(status_code=404, detail=f"Ad {ad_id} not found")

    return to_ad_detail(
        ad=ad,
        evaluation=session.get(AdEvaluation, ad_id),
        screening=session.get(AdScreening, ad_id),
        tracking=session.get(AdTracking, ad_id),
        features_count=_features_count(session, ad_id),
        market_stats=_market_stats(session, ad),
        signals=session.get(AdMarketSignals, ad_id),
    )


@router.get("/{ad_id}/history", response_model=ListingHistoryResponse)
def get_ad_history(
        ad_id: int,
        session: Annotated[Session, Depends(get_session)],
) -> ListingHistoryResponse:
    if session.get(Ad, ad_id) is None:
        raise HTTPException(status_code=404, detail=f"Ad {ad_id} not found")

    signals = session.get(AdMarketSignals, ad_id)
    member_ids = [ad_id] if signals is None else list(session.execute(
        select(AdMarketSignals.ad_id).where(AdMarketSignals.listing_group_id == signals.listing_group_id)
    ).scalars())

    listings = session.execute(
        select(Ad, Owner.name)
        .outerjoin(Owner, Owner.id == Ad.owner_id)
        .options(selectinload(Ad.city), selectinload(Ad.district))
        .where(Ad.id.in_(member_ids))
        .order_by(Ad.created_at, Ad.id)
    ).all()
    prices = session.execute(
        select(AdPriceObservation)
        .where(AdPriceObservation.ad_id.in_(member_ids))
        .order_by(AdPriceObservation.observed_at, AdPriceObservation.id)
    ).scalars().all()

    return ListingHistoryResponse(
        ad_id=ad_id,
        signals=to_market_signals(signals),
        listings=[
            ListingHistoryEntry(
                id=ad.id,
                url=ad.url,
                title=ad.title,
                status=ad.status.value if hasattr(ad.status, "value") else str(ad.status),
                advertiser_type=display_label(ADVERTISER_TYPES, ad.advertiser_type),
                advertiser_name=owner_name if owner_name and owner_name.strip() != "***" else None,
                created_at=ad.created_at,
                last_seen_at=ad.scraped_at,
                price_value=ad.price_value,
                area_value=float(ad.area_value) if ad.area_value is not None else None,
                city=ad.city.name if ad.city else None,
                district=ad.district.name if ad.district else None,
                street=ad.street,
            )
            for ad, owner_name in listings
        ],
        prices=[
            PriceObservationResponse(
                ad_id=price.ad_id,
                observed_at=price.observed_at,
                price_value=price.price_value,
                status=price.status,
            )
            for price in prices
        ],
    )


def _features_count(session: Session, ad_id: int) -> int:
    return session.execute(
        select(func.count()).select_from(ad_all_features).where(ad_all_features.c.ad_id == ad_id)
    ).scalar_one()


def _market_stats(session: Session, ad: Ad) -> Optional[MarketStatsResponse]:
    if ad.city_id is None:
        return None

    row = session.execute(
        select(district_price_stats)
        .where(district_price_stats.c.city_id == ad.city_id)
        .where(or_(
            district_price_stats.c.district_id.is_not_distinct_from(ad.district_id),
            district_price_stats.c.is_city_level == 1,
        ))
        .where(district_price_stats.c.offer_type.is_not_distinct_from(ad.offer_type))
        .where(district_price_stats.c.object_type.is_not_distinct_from(ad.object_type))
        .order_by(district_price_stats.c.is_city_level)
        .limit(1)
    ).mappings().first()

    if row is None or row["median_price_per_m2"] is None:
        return None

    return MarketStatsResponse(
        ad_count=row["ad_count"],
        median_price_per_m2=round(row["median_price_per_m2"]),
        p25_price_per_m2=round(row["p25_price_per_m2"]),
        p75_price_per_m2=round(row["p75_price_per_m2"]),
        is_city_level=bool(row["is_city_level"]),
    )
