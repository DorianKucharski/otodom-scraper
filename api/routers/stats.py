from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from data.models import Ad, AdEvaluation, AdStatus, City, District
from ..dependencies import get_session
from ..schemas import DistrictStatsResponse

router = APIRouter(prefix="/api/stats", tags=["stats"])

_ACTIVE_ADS = Ad.status == AdStatus.ACTIVE


@router.get("/districts", response_model=list[DistrictStatsResponse])
def get_district_stats(
        session: Annotated[Session, Depends(get_session)],
        city: Optional[str] = Query(None),
        min_ad_count: int = Query(5, ge=1),
) -> list[DistrictStatsResponse]:
    statement = (
        select(
            City.name,
            District.name,
            func.count(Ad.id),
            func.percentile_cont(0.5).within_group(Ad.price_per_m2),
            func.percentile_cont(0.25).within_group(Ad.price_per_m2),
            func.percentile_cont(0.75).within_group(Ad.price_per_m2),
            func.percentile_cont(0.5).within_group(Ad.price_value),
            func.percentile_cont(0.5).within_group(Ad.area_value),
            func.avg(AdEvaluation.overall_score),
        )
        .select_from(Ad)
        .outerjoin(City, Ad.city_id == City.id)
        .outerjoin(District, Ad.district_id == District.id)
        .outerjoin(AdEvaluation, AdEvaluation.ad_id == Ad.id)
        .where(_ACTIVE_ADS, Ad.price_per_m2.is_not(None))
        .group_by(City.name, District.name)
        .having(func.count(Ad.id) >= min_ad_count)
        .order_by(func.count(Ad.id).desc())
    )

    if city:
        statement = statement.where(func.lower(City.name) == city.lower())

    return [
        DistrictStatsResponse(
            city=row[0],
            district=row[1],
            ad_count=row[2],
            median_price_per_m2=_rounded(row[3]),
            p25_price_per_m2=_rounded(row[4]),
            p75_price_per_m2=_rounded(row[5]),
            median_price=_rounded(row[6]),
            median_area=_as_float(row[7]),
            median_overall_score=_as_float(row[8]),
        )
        for row in session.execute(statement).all()
    ]


def _rounded(value) -> Optional[int]:
    return round(float(value)) if value is not None else None


def _as_float(value) -> Optional[float]:
    return round(float(value), 2) if value is not None else None
