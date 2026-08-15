from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from geoalchemy2 import Geography
from sqlalchemy import Integer, Select, and_, case, cast, exists, func, or_, select

from data.models import Ad, AdEvaluation, City, District, Province
from data.read_models import ad_all_features
from enricher.schema import SCORE_FIELD_NAMES
from .schemas import AdSearchQuery, FeatureMatchMode, SortDirection

FLOOR_NUMBER = case(
    (Ad.flat_floor == "GROUND_FLOOR", 0),
    (Ad.flat_floor.startswith("FLOOR_", autoescape=True), cast(func.substring(Ad.flat_floor, 7), Integer)),
    else_=None,
)

FEATURES_COUNT = (
    select(func.count())
    .select_from(ad_all_features)
    .where(ad_all_features.c.ad_id == Ad.id)
    .correlate(Ad)
    .scalar_subquery()
)


@dataclass(frozen=True)
class SearchStatements:
    rows: Select
    total: Select


def build_search_statements(query: AdSearchQuery) -> SearchStatements:
    conditions = _conditions_of(query)
    distance = _distance_expression(query)

    rows = (
        select(Ad, AdEvaluation, FEATURES_COUNT.label("features_count"), _distance_column(distance))
        .outerjoin(AdEvaluation, AdEvaluation.ad_id == Ad.id)
        .where(*conditions)
        .order_by(*_order_by(query, distance))
        .limit(query.limit)
        .offset(query.offset)
    )

    total = (
        select(func.count())
        .select_from(Ad)
        .outerjoin(AdEvaluation, AdEvaluation.ad_id == Ad.id)
        .where(*conditions)
    )

    return SearchStatements(rows=rows, total=total)


def _conditions_of(query: AdSearchQuery) -> list:
    conditions = []

    if query.statuses:
        conditions.append(Ad.status.in_(query.statuses))
    if query.text:
        pattern = f"%{query.text}%"
        conditions.append(or_(Ad.title.ilike(pattern), Ad.description.ilike(pattern)))

    conditions.extend(_location_conditions(query))
    conditions.extend(_price_conditions(query))
    conditions.extend(_property_conditions(query))
    conditions.extend(_classification_conditions(query))
    conditions.extend(_feature_conditions(query))
    conditions.extend(_freshness_conditions(query))
    conditions.extend(_evaluation_conditions(query))

    return conditions


def _location_conditions(query: AdSearchQuery) -> list:
    conditions = []

    if query.voivodeships:
        conditions.append(Ad.province_id.in_(
            select(Province.id).where(func.lower(Province.name).in_(_lowered(query.voivodeships)))
        ))
    if query.cities:
        conditions.append(Ad.city_id.in_(
            select(City.id).where(func.lower(City.name).in_(_lowered(query.cities)))
        ))
    if query.districts:
        conditions.append(Ad.district_id.in_(
            select(District.id).where(func.lower(District.name).in_(_lowered(query.districts)))
        ))
    if _has_radius(query):
        conditions.append(func.ST_DWithin(
            cast(Ad.location_point, Geography),
            cast(_search_point(query), Geography),
            query.radius_m,
        ))

    return conditions


def _price_conditions(query: AdSearchQuery) -> list:
    conditions = []

    if query.min_price is not None:
        conditions.append(Ad.price_value >= query.min_price)
    if query.max_price is not None:
        conditions.append(Ad.price_value <= query.max_price)
    if query.min_price_per_m2 is not None:
        conditions.append(Ad.price_per_m2 >= query.min_price_per_m2)
    if query.max_price_per_m2 is not None:
        conditions.append(Ad.price_per_m2 <= query.max_price_per_m2)
    if query.max_rent is not None:
        conditions.append(or_(Ad.rent_value.is_(None), Ad.rent_value <= query.max_rent))

    return conditions


def _property_conditions(query: AdSearchQuery) -> list:
    conditions = []

    if query.min_area is not None:
        conditions.append(Ad.area_value >= query.min_area)
    if query.max_area is not None:
        conditions.append(Ad.area_value <= query.max_area)
    if query.min_rooms is not None:
        conditions.append(Ad.flat_number_of_rooms >= query.min_rooms)
    if query.max_rooms is not None:
        conditions.append(Ad.flat_number_of_rooms <= query.max_rooms)
    if query.min_floor is not None:
        conditions.append(FLOOR_NUMBER >= query.min_floor)
    if query.max_floor is not None:
        conditions.append(FLOOR_NUMBER <= query.max_floor)
    if query.exclude_ground_floor:
        conditions.append(or_(FLOOR_NUMBER.is_(None), FLOOR_NUMBER > 0))
    if query.exclude_top_floor:
        conditions.append(or_(
            FLOOR_NUMBER.is_(None),
            Ad.building_number_of_floors.is_(None),
            FLOOR_NUMBER < Ad.building_number_of_floors,
        ))
    if query.min_building_year is not None:
        conditions.append(Ad.building_year >= query.min_building_year)
    if query.max_building_year is not None:
        conditions.append(Ad.building_year <= query.max_building_year)

    return conditions


def _classification_conditions(query: AdSearchQuery) -> list:
    return [
        column.in_(values)
        for column, values in (
            (Ad.building_type, query.building_types),
            (Ad.building_material, query.building_materials),
            (Ad.building_heating, query.building_heating),
            (Ad.market, query.markets),
            (Ad.advertiser_type, query.advertiser_types),
            (Ad.property_type, query.property_types),
            (Ad.property_condition, query.property_conditions),
            (Ad.object_type, query.object_types),
            (Ad.offer_type, query.offer_types),
        )
        if values
    ]


def _feature_conditions(query: AdSearchQuery) -> list:
    conditions = []

    if query.features and query.feature_match is FeatureMatchMode.ALL:
        conditions.extend(_has_feature([feature]) for feature in query.features)
    elif query.features:
        conditions.append(_has_feature(query.features))

    if query.excluded_features:
        conditions.append(~_has_feature(query.excluded_features))

    if query.min_features_count is not None:
        conditions.append(FEATURES_COUNT >= query.min_features_count)

    return conditions


def _freshness_conditions(query: AdSearchQuery) -> list:
    conditions = []

    if query.created_after is not None:
        conditions.append(Ad.created_at >= query.created_after)
    if query.modified_after is not None:
        conditions.append(Ad.modified_at >= query.modified_after)

    return conditions


def _evaluation_conditions(query: AdSearchQuery) -> list:
    conditions = []

    if query.require_evaluation:
        conditions.append(AdEvaluation.ad_id.is_not(None))

    for score_name in SCORE_FIELD_NAMES:
        minimum = getattr(query, f"min_{score_name}", None)
        if minimum is not None:
            conditions.append(getattr(AdEvaluation, score_name) >= minimum)

    if query.renovation_needed:
        conditions.append(AdEvaluation.renovation_needed.in_(query.renovation_needed))
    if query.style_tags:
        conditions.append(AdEvaluation.style_tag.in_(query.style_tags))

    conditions.extend(
        AdEvaluation.attributes[key].astext == value
        for key, value in _parsed_attributes(query.attributes)
    )

    return conditions


def _has_feature(values: list[str]):
    return exists(
        select(ad_all_features.c.ad_id)
        .where(and_(ad_all_features.c.ad_id == Ad.id, ad_all_features.c.value.in_(values)))
        .correlate(Ad)
    )


def _parsed_attributes(raw_attributes: list[str]) -> list[tuple[str, str]]:
    parsed = []
    for raw_attribute in raw_attributes:
        key, separator, value = raw_attribute.partition(":")
        if separator and key.strip() and value.strip():
            parsed.append((key.strip(), value.strip()))
    return parsed


def _has_radius(query: AdSearchQuery) -> bool:
    return query.latitude is not None and query.longitude is not None and query.radius_m is not None


def _search_point(query: AdSearchQuery):
    return func.ST_SetSRID(func.ST_MakePoint(query.longitude, query.latitude), 4326)


def _distance_expression(query: AdSearchQuery):
    if not _has_radius(query) and (query.latitude is None or query.longitude is None):
        return None
    return func.ST_Distance(cast(Ad.location_point, Geography), cast(_search_point(query), Geography))


def _distance_column(distance):
    return (distance if distance is not None else func.cast(None, Integer)).label("distance_m")


def _order_by(query: AdSearchQuery, distance) -> list:
    sort_field = query.sort.value
    descending = query.direction is SortDirection.DESC

    if sort_field == "distance":
        expression = distance if distance is not None else Ad.id
    elif sort_field == "features_count":
        expression = FEATURES_COUNT
    elif sort_field in SCORE_FIELD_NAMES:
        expression = getattr(AdEvaluation, sort_field)
    else:
        expression = getattr(Ad, sort_field)

    ordered = expression.desc() if descending else expression.asc()
    return [ordered.nullslast(), Ad.id.desc()]


def _lowered(values: list[str]) -> list[str]:
    return [value.lower() for value in values]
