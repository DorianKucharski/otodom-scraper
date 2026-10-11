from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from data.models import Ad, AdEvaluation, AdScreening, AdTracking
from data.read_models import ad_all_features, district_price_stats
from ..dependencies import get_session
from ..mappers import to_ad_detail, to_ad_summary
from ..query import build_search_statements
from ..schemas import AdDetailResponse, AdSearchQuery, AdSearchResponse, MarketStatsResponse

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
            to_ad_summary(ad, evaluation, tracking, features_count, distance_m)
            for ad, evaluation, tracking, features_count, distance_m in rows
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
