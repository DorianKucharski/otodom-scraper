from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from data.models import Ad, AdEvaluation, AdStatus, City, District, Province
from data.read_models import ad_all_features
from ..dependencies import get_session
from ..schemas import FacetValue, FacetsResponse, RangeFacet

router = APIRouter(prefix="/api/facets", tags=["facets"])

_ACTIVE_ADS = Ad.status == AdStatus.ACTIVE
_MAX_FEATURE_FACETS = 200


@router.get("", response_model=FacetsResponse)
def get_facets(session: Annotated[Session, Depends(get_session)]) -> FacetsResponse:
    return FacetsResponse(
        voivodeships=_location_facets(session, Province, Ad.province_id),
        cities=_location_facets(session, City, Ad.city_id),
        districts=_location_facets(session, District, Ad.district_id),
        features=_feature_facets(session),
        building_types=_column_facets(session, Ad.building_type),
        building_materials=_column_facets(session, Ad.building_material),
        building_heating=_column_facets(session, Ad.building_heating),
        markets=_column_facets(session, Ad.market),
        advertiser_types=_column_facets(session, Ad.advertiser_type),
        property_conditions=_column_facets(session, Ad.property_condition),
        style_tags=_evaluation_facets(session, AdEvaluation.style_tag),
        renovation_needed=_evaluation_facets(session, AdEvaluation.renovation_needed),
        price=_range_facet(session, Ad.price_value),
        price_per_m2=_range_facet(session, Ad.price_per_m2),
        area=_range_facet(session, Ad.area_value),
        rooms=_range_facet(session, Ad.flat_number_of_rooms),
        building_year=_range_facet(session, Ad.building_year),
    )


def _location_facets(session: Session, location_model, foreign_key) -> list[FacetValue]:
    statement = (
        select(location_model.name, func.count(Ad.id))
        .join(Ad, foreign_key == location_model.id)
        .where(_ACTIVE_ADS)
        .group_by(location_model.name)
        .order_by(func.count(Ad.id).desc())
    )
    return _to_facets(session, statement)


def _column_facets(session: Session, column) -> list[FacetValue]:
    statement = (
        select(column, func.count(Ad.id))
        .where(_ACTIVE_ADS, column.is_not(None))
        .group_by(column)
        .order_by(func.count(Ad.id).desc())
    )
    return _to_facets(session, statement)


def _evaluation_facets(session: Session, column) -> list[FacetValue]:
    statement = (
        select(column, func.count(AdEvaluation.ad_id))
        .where(column.is_not(None))
        .group_by(column)
        .order_by(func.count(AdEvaluation.ad_id).desc())
    )
    return _to_facets(session, statement)


def _feature_facets(session: Session) -> list[FacetValue]:
    statement = (
        select(ad_all_features.c.value, func.count())
        .join(Ad, Ad.id == ad_all_features.c.ad_id)
        .where(_ACTIVE_ADS)
        .group_by(ad_all_features.c.value)
        .order_by(func.count().desc())
        .limit(_MAX_FEATURE_FACETS)
    )
    return _to_facets(session, statement)


def _range_facet(session: Session, column) -> RangeFacet:
    minimum, maximum = session.execute(
        select(func.min(column), func.max(column)).where(_ACTIVE_ADS)
    ).one()
    return RangeFacet(min=_as_float(minimum), max=_as_float(maximum))


def _to_facets(session: Session, statement: Select) -> list[FacetValue]:
    return [
        FacetValue(value=str(value), label=_humanize(str(value)), count=count)
        for value, count in session.execute(statement).all()
        if value is not None
    ]


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip().capitalize()


def _as_float(value) -> Optional[float]:
    return float(value) if value is not None else None
