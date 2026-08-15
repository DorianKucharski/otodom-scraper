from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from data.description import plain_description
from data.feature_groups import labelled_feature_groups
from data.models import Ad
from .market_context import MarketContext


@dataclass(frozen=True)
class MarketStatsView:
    ad_count: int
    median_price_per_m2: int
    p25_price_per_m2: int
    p75_price_per_m2: int
    position_label: str


@dataclass(frozen=True)
class AdContext:
    id: int
    url: str
    title: str
    address: str
    description: Optional[str]
    price_label: str
    price_per_m2_label: str
    rent_label: Optional[str]
    area_label: str
    rooms: Optional[int]
    floor: Optional[str]
    building_floors: Optional[int]
    market: Optional[str]
    advertiser_type: Optional[str]
    property_type: Optional[str]
    property_condition: Optional[str]
    property_ownership: Optional[str]
    building_year: Optional[int]
    building_type: Optional[str]
    building_material: Optional[str]
    building_heating: Optional[str]
    created_at_label: str
    images_count: int
    images_evaluated: int
    feature_groups: tuple[tuple[str, tuple[str, ...]], ...]
    market_stats: Optional[MarketStatsView]
    screening_attributes: tuple[tuple[str, str], ...]
    distance_to_center_label: Optional[str]


def build_ad_context(
        ad: Ad,
        market_context: Optional[MarketContext] = None,
        screening_attributes: Optional[Mapping[str, str]] = None,
        images_evaluated: int = 0,
        max_description_characters: Optional[int] = None,
) -> AdContext:
    return AdContext(
        id=ad.id,
        url=ad.url,
        title=ad.title,
        address=_address_of(ad),
        description=plain_description(ad.description, max_description_characters),
        price_label=_money_label(ad.price_value, ad.price_currency),
        price_per_m2_label=_money_label(ad.price_per_m2, ad.price_currency, suffix=" za metr"),
        rent_label=_money_label(ad.rent_value, ad.rent_currency or "PLN") if ad.rent_value else None,
        area_label=f"{float(ad.area_value):.1f} m2" if ad.area_value else "brak danych",
        rooms=ad.flat_number_of_rooms,
        floor=ad.flat_floor,
        building_floors=ad.building_number_of_floors,
        market=ad.market,
        advertiser_type=ad.advertiser_type,
        property_type=ad.property_type,
        property_condition=ad.property_condition,
        property_ownership=ad.property_ownership,
        building_year=ad.building_year,
        building_type=ad.building_type,
        building_material=ad.building_material,
        building_heating=ad.building_heating,
        created_at_label=ad.created_at.strftime("%Y-%m-%d") if ad.created_at else "brak danych",
        images_count=len(ad.images),
        images_evaluated=images_evaluated,
        feature_groups=labelled_feature_groups(ad),
        market_stats=_market_stats_view(ad, market_context),
        screening_attributes=tuple((screening_attributes or {}).items()),
        distance_to_center_label=None,
    )


def _address_of(ad: Ad) -> str:
    parts = [
        ad.street,
        ad.district.name if ad.district else None,
        ad.city.name if ad.city else None,
        ad.province.name if ad.province else None,
    ]
    known_parts = [part for part in parts if part]
    return ", ".join(known_parts) if known_parts else "brak danych"



def _money_label(value: Optional[int], currency: Optional[str], suffix: str = "") -> str:
    if not value:
        return "brak danych"
    return f"{value:,}".replace(",", " ") + f" {currency or 'PLN'}{suffix}"


def _market_stats_view(ad: Ad, market_context: Optional[MarketContext]) -> Optional[MarketStatsView]:
    if market_context is None:
        return None
    stats = market_context.stats_for(ad)
    if stats is None:
        return None
    return MarketStatsView(
        ad_count=stats.ad_count,
        median_price_per_m2=stats.median_price_per_m2,
        p25_price_per_m2=stats.p25_price_per_m2,
        p75_price_per_m2=stats.p75_price_per_m2,
        position_label=stats.position_label(ad.price_per_m2),
    )
