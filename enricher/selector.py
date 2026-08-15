from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from data.models import Ad, AdEvaluation, AdScreening, AdStatus, City, District, EvaluationStatus, Province, \
    ScreeningStatus
from data.search_url import normalize_name

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdFilter:
    url: Optional[str] = None
    voivodeship: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    object_types: tuple[str, ...] = ()
    offer_types: tuple[str, ...] = ()
    limit: Optional[int] = None


MAX_ATTEMPTS = 3


def screening_candidate_ids(
        session: Session,
        ad_filter: AdFilter,
        prompt_version: str,
        force: bool = False,
) -> list[int]:
    query = screening_candidate_query(session, ad_filter, prompt_version, force)
    return _ids_of(query, ad_filter.limit, AdScreening.ad_id.is_(None).desc())


def evaluation_candidate_ids(
        session: Session,
        ad_filter: AdFilter,
        prompt_version: str,
        price_drift_threshold: float,
        force: bool = False,
        require_passed_screening: bool = True,
) -> list[int]:
    query = evaluation_candidate_query(
        session, ad_filter, prompt_version, price_drift_threshold, force, require_passed_screening
    )
    return _ids_of(query, ad_filter.limit, AdEvaluation.ad_id.is_(None).desc())


def screening_candidate_query(
        session: Session,
        ad_filter: AdFilter,
        prompt_version: str,
        force: bool = False,
):
    query = _filtered_query(session, ad_filter).outerjoin(AdScreening, AdScreening.ad_id == Ad.id)

    if not force:
        query = query.filter(or_(
            AdScreening.ad_id.is_(None),
            AdScreening.prompt_version != prompt_version,
            AdScreening.ad_modified_at.is_distinct_from(Ad.modified_at),
            _is_retryable_failure(AdScreening, ScreeningStatus.FAILED),
        ))

    return query


def evaluation_candidate_query(
        session: Session,
        ad_filter: AdFilter,
        prompt_version: str,
        price_drift_threshold: float,
        force: bool = False,
        require_passed_screening: bool = True,
):
    query = _filtered_query(session, ad_filter)

    if require_passed_screening:
        query = (
            query
            .join(AdScreening, AdScreening.ad_id == Ad.id)
            .filter(AdScreening.status == ScreeningStatus.PASSED)
        )

    query = query.outerjoin(AdEvaluation, AdEvaluation.ad_id == Ad.id)

    if not force:
        query = query.filter(or_(
            AdEvaluation.ad_id.is_(None),
            AdEvaluation.prompt_version != prompt_version,
            AdEvaluation.ad_modified_at.is_distinct_from(Ad.modified_at),
            _is_retryable_failure(AdEvaluation, EvaluationStatus.FAILED),
            AdEvaluation.price_at_evaluation.is_(None),
            func.abs(Ad.price_value - AdEvaluation.price_at_evaluation)
            > AdEvaluation.price_at_evaluation * price_drift_threshold,
        ))

    return query


def _is_retryable_failure(enrichment_model, failed_status):
    return (enrichment_model.status == failed_status) & (enrichment_model.attempts < MAX_ATTEMPTS)


def _filtered_query(session: Session, ad_filter: AdFilter):
    query = session.query(Ad.id).filter(Ad.status == AdStatus.ACTIVE)

    if ad_filter.url:
        return query.filter(Ad.url == ad_filter.url)

    if ad_filter.voivodeship:
        query = query.join(Province, Ad.province_id == Province.id).filter(
            _location_matches(Province, ad_filter.voivodeship)
        )
    if ad_filter.city:
        query = query.join(City, Ad.city_id == City.id).filter(
            _location_matches(City, ad_filter.city)
        )
    if ad_filter.district:
        query = query.join(District, Ad.district_id == District.id).filter(
            _location_matches(District, ad_filter.district)
        )
    if ad_filter.min_price is not None:
        query = query.filter(Ad.price_value >= ad_filter.min_price)
    if ad_filter.max_price is not None:
        query = query.filter(Ad.price_value <= ad_filter.max_price)
    if ad_filter.object_types:
        query = query.filter(_type_matches(Ad.object_type, ad_filter.object_types, "object_type"))
    if ad_filter.offer_types:
        query = query.filter(_type_matches(Ad.offer_type, ad_filter.offer_types, "offer_type"))

    return query


def _location_matches(location_model, value: str):
    slug = (normalize_name(value) or "").replace(" ", "-")
    return or_(location_model.name.ilike(value), location_model.code == slug)


def _type_matches(column, allowed_values: tuple[str, ...], column_name: str):
    logger.info(
        "Filtering by %s in %s and including ads where %s is not set yet",
        column_name, list(allowed_values), column_name,
    )
    return or_(column.in_(allowed_values), column.is_(None))


def _ids_of(query, limit: Optional[int], never_processed_first) -> list[int]:
    query = query.order_by(never_processed_first, Ad.created_at.desc())
    if limit is not None:
        query = query.limit(limit)
    return [row.id for row in query.all()]
