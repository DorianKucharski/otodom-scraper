from __future__ import annotations

from typing import Optional

from data.feature_groups import labelled_feature_groups
from data.models import Ad, AdEvaluation, AdScreening
from data.description import plain_description
from .schemas import AdDetailResponse, AdSummaryResponse, EvaluationResponse, ImageResponse, MarketStatsResponse


def to_ad_summary(
        ad: Ad,
        evaluation: Optional[AdEvaluation],
        features_count: int,
        distance_m: Optional[float],
) -> AdSummaryResponse:
    return AdSummaryResponse(
        **_common_fields(ad),
        distance_m=distance_m,
        features_count=features_count,
        thumbnail=_thumbnail_of(ad),
        evaluation=to_evaluation(evaluation),
    )


def to_ad_detail(
        ad: Ad,
        evaluation: Optional[AdEvaluation],
        screening: Optional[AdScreening],
        features_count: int,
        market_stats: Optional[MarketStatsResponse],
) -> AdDetailResponse:
    return AdDetailResponse(
        **_common_fields(ad),
        features_count=features_count,
        thumbnail=_thumbnail_of(ad),
        evaluation=to_evaluation(evaluation),
        description=plain_description(ad.description),
        province=ad.province.name if ad.province else None,
        county=ad.county.name if ad.county else None,
        postal_code=ad.postal_code,
        building_type=ad.building_type,
        building_material=ad.building_material,
        building_heating=ad.building_heating,
        building_number_of_floors=ad.building_number_of_floors,
        property_ownership=ad.property_ownership,
        status=_status_value(ad.status),
        images=[
            ImageResponse(
                position=image.position,
                thumbnail=image.thumbnail,
                medium=image.medium,
                large=image.large,
            )
            for image in sorted(ad.images, key=lambda image: image.position)
        ],
        feature_groups={label: list(values) for label, values in labelled_feature_groups(ad)},
        screening_attributes=dict(screening.extracted_attributes or {}) if screening else {},
        market_stats=market_stats,
    )


def to_evaluation(evaluation: Optional[AdEvaluation]) -> Optional[EvaluationResponse]:
    if evaluation is None:
        return None

    return EvaluationResponse(
        status=_status_value(evaluation.status),
        overall_score=evaluation.overall_score,
        finish_quality_score=evaluation.finish_quality_score,
        freshness_score=evaluation.freshness_score,
        move_in_readiness_score=evaluation.move_in_readiness_score,
        layout_score=evaluation.layout_score,
        natural_light_score=evaluation.natural_light_score,
        building_condition_score=evaluation.building_condition_score,
        location_score=evaluation.location_score,
        value_for_money_score=evaluation.value_for_money_score,
        photo_trust_score=evaluation.photo_trust_score,
        renovation_needed=_status_value(evaluation.renovation_needed),
        style_tag=evaluation.style_tag,
        summary=evaluation.summary,
        strengths=list(evaluation.strengths or []),
        concerns=list(evaluation.concerns or []),
        attributes=dict(evaluation.attributes or {}),
        images_evaluated=evaluation.images_evaluated or 0,
        model=evaluation.model,
        evaluated_at=evaluation.evaluated_at,
    )


def _common_fields(ad: Ad) -> dict:
    return {
        "id": ad.id,
        "url": ad.url,
        "title": ad.title,
        "price_value": ad.price_value,
        "price_currency": ad.price_currency,
        "price_per_m2": ad.price_per_m2,
        "rent_value": ad.rent_value,
        "area_value": float(ad.area_value) if ad.area_value is not None else None,
        "rooms": ad.flat_number_of_rooms,
        "floor": ad.flat_floor,
        "building_year": ad.building_year,
        "market": ad.market,
        "advertiser_type": ad.advertiser_type,
        "property_condition": ad.property_condition,
        "city": ad.city.name if ad.city else None,
        "district": ad.district.name if ad.district else None,
        "street": ad.street,
        "latitude": float(ad.latitude) if ad.latitude is not None else None,
        "longitude": float(ad.longitude) if ad.longitude is not None else None,
        "created_at": ad.created_at,
        "modified_at": ad.modified_at,
    }


def _thumbnail_of(ad: Ad) -> Optional[str]:
    images = sorted(ad.images, key=lambda image: image.position)
    return images[0].medium if images else None


def _status_value(status) -> Optional[str]:
    if status is None:
        return None
    return status.value if hasattr(status, "value") else str(status)
