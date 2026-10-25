from __future__ import annotations

from typing import Optional

from data.feature_groups import labelled_feature_groups
from data.models import Ad, AdEvaluation, AdMarketSignals, AdScreening, AdTracking
from data.description import plain_description
from .labels import (
    ADVERTISER_TYPES, BUILDING_HEATING, BUILDING_MATERIALS, BUILDING_TYPES, MARKETS, PROPERTY_CONDITIONS,
    PROPERTY_OWNERSHIP, STYLE_TAGS, display_label, feature_label,
)
from data.inferred_types import object_type_of, offer_type_of
from .schemas import (
    AdDetailResponse, AdSummaryResponse, EvaluationResponse, ImageResponse, MarketSignalsResponse, MarketStatsResponse,
    TrackingDetailResponse, TrackingEventResponse, TrackingResponse,
)


def to_ad_summary(
        ad: Ad,
        evaluation: Optional[AdEvaluation],
        tracking: Optional[AdTracking],
        features_count: int,
        distance_m: Optional[float],
        signals: Optional[AdMarketSignals] = None,
) -> AdSummaryResponse:
    return AdSummaryResponse(
        **_common_fields(ad),
        distance_m=distance_m,
        features_count=features_count,
        thumbnail=_thumbnail_of(ad),
        evaluation=to_evaluation(evaluation),
        tracking=to_tracking(tracking),
        market_signals=to_market_signals(signals),
    )


def to_ad_detail(
        ad: Ad,
        evaluation: Optional[AdEvaluation],
        screening: Optional[AdScreening],
        tracking: Optional[AdTracking],
        features_count: int,
        market_stats: Optional[MarketStatsResponse],
        signals: Optional[AdMarketSignals] = None,
) -> AdDetailResponse:
    return AdDetailResponse(
        **_common_fields(ad),
        features_count=features_count,
        thumbnail=_thumbnail_of(ad),
        evaluation=to_evaluation(evaluation),
        tracking=to_tracking(tracking),
        market_signals=to_market_signals(signals),
        description=plain_description(ad.description),
        province=ad.province.name if ad.province else None,
        county=ad.county.name if ad.county else None,
        postal_code=ad.postal_code,
        building_type=display_label(BUILDING_TYPES, ad.building_type),
        building_material=display_label(BUILDING_MATERIALS, ad.building_material),
        building_heating=display_label(BUILDING_HEATING, ad.building_heating),
        building_number_of_floors=ad.building_number_of_floors,
        property_ownership=display_label(PROPERTY_OWNERSHIP, ad.property_ownership),
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
        feature_groups={
            label: sorted({feature_label(value) for value in values})
            for label, values in labelled_feature_groups(ad)
        },
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
        style_tag=display_label(STYLE_TAGS, evaluation.style_tag),
        summary=evaluation.summary,
        strengths=list(evaluation.strengths or []),
        concerns=list(evaluation.concerns or []),
        attributes=dict(evaluation.attributes or {}),
        images_evaluated=evaluation.images_evaluated or 0,
        model=evaluation.model,
        evaluated_at=evaluation.evaluated_at,
    )


def to_market_signals(signals: Optional[AdMarketSignals]) -> Optional[MarketSignalsResponse]:
    if signals is None:
        return None
    return MarketSignalsResponse(
        listing_group_id=signals.listing_group_id,
        listings_count=signals.listings_count,
        active_listings_count=signals.active_listings_count or 1,
        advertisers_count=signals.advertisers_count,
        first_listed_at=signals.first_listed_at,
        days_on_market=signals.days_on_market,
        first_price=signals.first_price,
        lowest_price=signals.lowest_price,
        highest_price=signals.highest_price,
        price_change_pct=_float(signals.price_change_pct),
        comparables_count=signals.comparables_count,
        comparables_radius_m=signals.comparables_radius_m,
        comparables_median_price_per_m2=signals.comparables_median_price_per_m2,
        comparables_p25_price_per_m2=signals.comparables_p25_price_per_m2,
        comparables_p75_price_per_m2=signals.comparables_p75_price_per_m2,
        price_vs_comparables_pct=_float(signals.price_vs_comparables_pct),
        transactions_count=signals.transactions_count or 0,
        transactions_radius_m=signals.transactions_radius_m,
        transactions_median_price_per_m2=signals.transactions_median_price_per_m2,
        transactions_p25_price_per_m2=signals.transactions_p25_price_per_m2,
        transactions_p75_price_per_m2=signals.transactions_p75_price_per_m2,
        price_vs_transactions_pct=_float(signals.price_vs_transactions_pct),
        street_transactions_count=signals.street_transactions_count or 0,
        street_transactions_median_price_per_m2=signals.street_transactions_median_price_per_m2,
        price_vs_street_transactions_pct=_float(signals.price_vs_street_transactions_pct),
        pin_city_name=signals.pin_city_name,
        pin_gmina_name=signals.pin_gmina_name,
        city_border_distance_m=signals.city_border_distance_m,
        location_flags=list(signals.location_flags or []),
        location_notes=list(signals.location_notes or []),
        area_flags=list(signals.area_flags or []),
        area_notes=list(signals.area_notes or []),
        previous_sale_at=signals.previous_sale_at,
        previous_sale_price=signals.previous_sale_price,
        previous_sale_distance_m=signals.previous_sale_distance_m,
        expressway_distance_m=signals.expressway_distance_m,
        expressway_label=signals.expressway_label,
        railway_distance_m=signals.railway_distance_m,
        runway_approach_m=signals.runway_approach_m,
        nuisance_flags=list(signals.nuisance_flags or []),
        nuisance_notes=list(signals.nuisance_notes or []),
        developer_dataset_id=signals.developer_dataset_id,
        developer_name=signals.developer_name,
        developer_investment=signals.developer_investment,
        developer_unit=signals.developer_unit,
        developer_price=signals.developer_price,
        developer_price_per_m2=signals.developer_price_per_m2,
        developer_price_since=signals.developer_price_since,
        developer_first_seen=signals.developer_first_seen,
        developer_first_price=signals.developer_first_price,
        developer_highest_price=signals.developer_highest_price,
        developer_last_seen=signals.developer_last_seen,
        developer_unit_gone=bool(signals.developer_unit_gone),
        developer_price_with_extras=signals.developer_price_with_extras,
        developer_extras=list(signals.developer_extras or []),
        price_vs_developer_pct=_float(signals.price_vs_developer_pct),
        investment_units_listed=signals.investment_units_listed,
        investment_units_gone=signals.investment_units_gone,
        investment_tracked_since=signals.investment_tracked_since,
        computed_at=signals.computed_at,
    )


def to_tracking(tracking: Optional[AdTracking]) -> Optional[TrackingResponse]:
    if tracking is None:
        return None
    return TrackingResponse(**_tracking_fields(tracking))


def to_tracking_detail(tracking: AdTracking) -> TrackingDetailResponse:
    events = sorted(tracking.events, key=lambda event: (event.created_at, event.id or 0), reverse=True)
    return TrackingDetailResponse(
        **_tracking_fields(tracking),
        ad_id=tracking.ad_id,
        events=[
            TrackingEventResponse(
                id=event.id,
                status=event.status,
                comment=event.comment,
                viewing_at=event.viewing_at,
                rating=event.rating,
                offer_amount=event.offer_amount,
                author=event.author,
                created_at=event.created_at,
            )
            for event in events
        ],
    )


def _tracking_fields(tracking: AdTracking) -> dict:
    return {
        "status": tracking.status,
        "viewing_at": tracking.viewing_at,
        "rating": tracking.rating,
        "offer_amount": tracking.offer_amount,
        "price_at_save": tracking.price_at_save,
        "last_comment": tracking.last_comment,
        "created_at": tracking.created_at,
        "updated_at": tracking.updated_at,
        "updated_by": tracking.updated_by,
    }


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
        "offer_type": offer_type_of(ad),
        "object_type": object_type_of(ad),
        "market": display_label(MARKETS, ad.market),
        "advertiser_type": display_label(ADVERTISER_TYPES, ad.advertiser_type),
        "property_condition": display_label(PROPERTY_CONDITIONS, ad.property_condition),
        "city": ad.city.name if ad.city else None,
        "district": ad.district.name if ad.district else None,
        "street": ad.street,
        "latitude": float(ad.latitude) if ad.latitude is not None else None,
        "longitude": float(ad.longitude) if ad.longitude is not None else None,
        "created_at": ad.created_at,
        "modified_at": ad.modified_at,
        "last_checked_at": ad.scraped_at,
    }


def _thumbnail_of(ad: Ad) -> Optional[str]:
    images = sorted(ad.images, key=lambda image: image.position)
    return images[0].medium if images else None


def _float(value) -> Optional[float]:
    return float(value) if value is not None else None


def _status_value(status) -> Optional[str]:
    if status is None:
        return None
    return status.value if hasattr(status, "value") else str(status)
