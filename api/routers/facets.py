from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from data.models import Ad, AdEvaluation, AdStatus, City, District, Province
from data.read_models import ad_all_features
from ..dependencies import get_session
from ..labels import (
    ADVERTISER_TYPES, BUILDING_HEATING, BUILDING_MATERIALS, BUILDING_TYPES, FEATURE_LABEL_BY_VALUE, MARKETS,
    OBJECT_TYPES, OFFER_TYPES, PROPERTY_CONDITIONS, RENOVATION_NEEDED, STYLE_TAGS, ValueLabel, humanize, label_of,
)
from ..query import OBJECT_TYPE, OFFER_TYPE
from ..schemas import FacetValue, FacetsResponse, RangeFacet

router = APIRouter(prefix="/api/facets", tags=["facets"])

_ACTIVE_ADS = Ad.status == AdStatus.ACTIVE
_MAX_FEATURE_FACETS = 200

_FEATURE_LABEL = case(FEATURE_LABEL_BY_VALUE, value=ad_all_features.c.value, else_=ad_all_features.c.value)


@router.get("", response_model=FacetsResponse)
def get_facets(session: Annotated[Session, Depends(get_session)]) -> FacetsResponse:
    return FacetsResponse(
        offer_types=_column_facets(session, OFFER_TYPE, OFFER_TYPES),
        object_types=_column_facets(session, OBJECT_TYPE, OBJECT_TYPES),
        voivodeships=_location_facets(session, Province, Ad.province_id),
        cities=_location_facets(session, City, Ad.city_id),
        districts=_location_facets(session, District, Ad.district_id),
        features=_feature_facets(session),
        building_types=_column_facets(session, Ad.building_type, BUILDING_TYPES),
        building_materials=_column_facets(session, Ad.building_material, BUILDING_MATERIALS),
        building_heating=_column_facets(session, Ad.building_heating, BUILDING_HEATING),
        markets=_column_facets(session, Ad.market, MARKETS),
        advertiser_types=_column_facets(session, Ad.advertiser_type, ADVERTISER_TYPES),
        property_conditions=_column_facets(session, Ad.property_condition, PROPERTY_CONDITIONS),
        style_tags=_evaluation_facets(session, AdEvaluation.style_tag, STYLE_TAGS),
        renovation_needed=_evaluation_facets(session, AdEvaluation.renovation_needed, RENOVATION_NEEDED),
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


def _column_facets(session: Session, column, labels: dict[str, ValueLabel]) -> list[FacetValue]:
    statement = (
        select(column, func.count(Ad.id))
        .where(_ACTIVE_ADS, column.is_not(None))
        .group_by(column)
        .order_by(func.count(Ad.id).desc())
    )
    return _to_facets(session, statement, labels)


def _evaluation_facets(session: Session, column, labels: dict[str, ValueLabel]) -> list[FacetValue]:
    statement = (
        select(column, func.count(AdEvaluation.ad_id))
        .where(column.is_not(None))
        .group_by(column)
        .order_by(func.count(AdEvaluation.ad_id).desc())
    )
    return _to_facets(session, statement, labels)


def _feature_facets(session: Session) -> list[FacetValue]:
    statement = (
        select(_FEATURE_LABEL, func.count(func.distinct(ad_all_features.c.ad_id)))
        .join(Ad, Ad.id == ad_all_features.c.ad_id)
        .where(_ACTIVE_ADS)
        .group_by(_FEATURE_LABEL)
        .order_by(func.count(func.distinct(ad_all_features.c.ad_id)).desc())
        .limit(_MAX_FEATURE_FACETS)
    )
    return [
        FacetValue(value=str(value), label=str(value)[:1].upper() + str(value)[1:], count=count)
        for value, count in session.execute(statement).all()
        if value is not None
    ]


def _range_facet(session: Session, column) -> RangeFacet:
    minimum, maximum = session.execute(
        select(func.min(column), func.max(column)).where(_ACTIVE_ADS)
    ).one()
    return RangeFacet(min=_as_float(minimum), max=_as_float(maximum))


def _to_facets(session: Session, statement: Select, labels: Optional[dict[str, ValueLabel]] = None) -> list[FacetValue]:
    facets = []
    for value, count in session.execute(statement).all():
        if value is None:
            continue
        label = label_of(labels, _raw(value)) if labels is not None else ValueLabel(humanize(str(value)))
        facets.append(FacetValue(value=_raw(value), label=label.label, description=label.description, count=count))
    return facets


def _raw(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _as_float(value) -> Optional[float]:
    return float(value) if value is not None else None
