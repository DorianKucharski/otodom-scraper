from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from data.models import TrackingStatus
from enricher.schema import SCORE_FIELD_NAMES
from .auth import MAX_NAME_LENGTH

_BASE_SORT_FIELDS = (
    "price_value",
    "price_per_m2",
    "area_value",
    "flat_number_of_rooms",
    "building_year",
    "created_at",
    "modified_at",
    "features_count",
    "distance",
    "days_on_market",
    "price_vs_comparables_pct",
    "price_change_pct",
    "price_vs_transactions_pct",
)

SortField = Enum(
    "SortField",
    {name.upper(): name for name in (*_BASE_SORT_FIELDS, *SCORE_FIELD_NAMES)},
    type=str,
)


class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class FeatureMatchMode(str, Enum):
    ALL = "all"
    ANY = "any"


class AdSearchQuery(BaseModel):
    text: Optional[str] = Field(None, description="Fragment tytułu lub opisu.")

    voivodeships: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    districts: list[str] = Field(default_factory=list)
    latitude: Optional[float] = Field(None, description="Środek okręgu wyszukiwania.")
    longitude: Optional[float] = None
    radius_m: Optional[int] = Field(None, description="Promień w metrach wokół podanego punktu.")

    min_price: Optional[int] = None
    max_price: Optional[int] = None
    min_price_per_m2: Optional[int] = None
    max_price_per_m2: Optional[int] = None
    max_rent: Optional[int] = None

    min_area: Optional[float] = None
    max_area: Optional[float] = None
    min_rooms: Optional[int] = None
    max_rooms: Optional[int] = None
    min_floor: Optional[int] = None
    max_floor: Optional[int] = None
    exclude_ground_floor: bool = False
    exclude_top_floor: bool = False

    min_building_year: Optional[int] = None
    max_building_year: Optional[int] = None
    building_types: list[str] = Field(default_factory=list)
    building_materials: list[str] = Field(default_factory=list)
    building_heating: list[str] = Field(default_factory=list)

    markets: list[str] = Field(default_factory=list)
    advertiser_types: list[str] = Field(default_factory=list)
    property_types: list[str] = Field(default_factory=list)
    property_conditions: list[str] = Field(default_factory=list)
    object_types: list[str] = Field(default_factory=list)
    offer_types: list[str] = Field(default_factory=list)
    statuses: list[str] = Field(default_factory=lambda: ["active"])

    features: list[str] = Field(default_factory=list, description="Cechy z dowolnej grupy.")
    feature_match: FeatureMatchMode = FeatureMatchMode.ALL
    excluded_features: list[str] = Field(default_factory=list)
    min_features_count: Optional[int] = None

    created_after: Optional[datetime] = None
    modified_after: Optional[datetime] = None

    require_evaluation: bool = False
    min_overall_score: Optional[int] = None
    min_finish_quality_score: Optional[int] = None
    min_freshness_score: Optional[int] = None
    min_move_in_readiness_score: Optional[int] = None
    min_layout_score: Optional[int] = None
    min_natural_light_score: Optional[int] = None
    min_building_condition_score: Optional[int] = None
    min_location_score: Optional[int] = None
    min_value_for_money_score: Optional[int] = None
    min_photo_trust_score: Optional[int] = None
    renovation_needed: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list)
    attributes: list[str] = Field(
        default_factory=list,
        description="Filtry po atrybutach AI w formacie klucz:wartość, na przykład kitchen_type:zamknięta.",
    )

    min_days_on_market: Optional[int] = Field(None, description="Ten sam lokal ogłaszany co najmniej tyle dni, licząc wszystkie jego ogłoszenia.")
    max_days_on_market: Optional[int] = None
    min_listings_count: Optional[int] = Field(None, description="2 = tylko lokale wystawiane ponownie albo przez kilku ogłoszeniodawców.")
    price_trends: list[str] = Field(default_factory=list, description="dropped, raised albo unchanged względem pierwszej znanej ceny lokalu.")
    max_price_vs_comparables_pct: Optional[float] = Field(
        None, description="Cena za metr względem mediany porównywalnych ofert w okolicy, -10 = co najmniej 10% taniej."
    )
    min_price_vs_comparables_pct: Optional[float] = None
    max_price_vs_transactions_pct: Optional[float] = Field(
        None, description="Cena za metr względem mediany transakcji z RCN w okolicy z ostatnich 2 lat."
    )
    hide_unchecked: bool = Field(
        True, description="Ukrywa aktywne ogłoszenia, których scraper nie sprawdzał dłużej niż UNCHECKED_AFTER_DAYS dni."
    )
    excluded_location_flags: list[str] = Field(
        default_factory=list, description="Ukrywa ogłoszenia z którąś z tych flag lokalizacji."
    )
    excluded_area_flags: list[str] = Field(
        default_factory=list, description="Ukrywa ogłoszenia z którąś z tych flag metrażu (usable_area_smaller, attic_slopes, appurtenant_included)."
    )
    excluded_nuisance_flags: list[str] = Field(
        default_factory=list, description="Ukrywa ogłoszenia z pinezką przy drodze szybkiego ruchu, kolei albo na przedłużeniu pasa lotniska (near_expressway, near_railway, under_approach)."
    )

    tracking_statuses: list[TrackingStatus] = Field(
        default_factory=list, description="Tylko ogłoszenia z jednym z tych statusów."
    )
    hide_dismissed: bool = Field(True, description="Ukrywa ogłoszenia odrzucone i niedostępne.")

    sort: SortField = SortField("created_at")
    direction: SortDirection = SortDirection.DESC
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)


class ImageResponse(BaseModel):
    position: int
    thumbnail: str
    medium: str
    large: str


class EvaluationResponse(BaseModel):
    status: str
    overall_score: Optional[int]
    finish_quality_score: Optional[int]
    freshness_score: Optional[int]
    move_in_readiness_score: Optional[int]
    layout_score: Optional[int]
    natural_light_score: Optional[int]
    building_condition_score: Optional[int]
    location_score: Optional[int]
    value_for_money_score: Optional[int]
    photo_trust_score: Optional[int]
    renovation_needed: Optional[str]
    style_tag: Optional[str]
    summary: Optional[str]
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    attributes: dict[str, str] = Field(default_factory=dict)
    images_evaluated: int = 0
    model: Optional[str] = None
    evaluated_at: Optional[datetime] = None


class MarketStatsResponse(BaseModel):
    ad_count: int
    median_price_per_m2: Optional[int]
    p25_price_per_m2: Optional[int]
    p75_price_per_m2: Optional[int]
    is_city_level: bool


class MarketSignalsResponse(BaseModel):
    listing_group_id: int
    listings_count: int
    active_listings_count: int = 1
    advertisers_count: int
    first_listed_at: datetime
    days_on_market: int
    first_price: Optional[int]
    lowest_price: Optional[int]
    highest_price: Optional[int]
    price_change_pct: Optional[float]
    comparables_count: int
    comparables_radius_m: Optional[int]
    comparables_median_price_per_m2: Optional[int]
    comparables_p25_price_per_m2: Optional[int]
    comparables_p75_price_per_m2: Optional[int]
    price_vs_comparables_pct: Optional[float]
    transactions_count: int = 0
    transactions_radius_m: Optional[int] = None
    transactions_median_price_per_m2: Optional[int] = None
    transactions_p25_price_per_m2: Optional[int] = None
    transactions_p75_price_per_m2: Optional[int] = None
    price_vs_transactions_pct: Optional[float] = None
    street_transactions_count: int = 0
    street_transactions_median_price_per_m2: Optional[int] = None
    price_vs_street_transactions_pct: Optional[float] = None
    pin_city_name: Optional[str]
    pin_gmina_name: Optional[str]
    city_border_distance_m: Optional[int]
    location_flags: list[str] = Field(default_factory=list)
    location_notes: list[str] = Field(default_factory=list)
    area_flags: list[str] = Field(default_factory=list)
    area_notes: list[str] = Field(default_factory=list)
    previous_sale_at: Optional[datetime] = None
    previous_sale_price: Optional[int] = None
    previous_sale_distance_m: Optional[int] = None
    expressway_distance_m: Optional[int] = None
    expressway_label: Optional[str] = None
    railway_distance_m: Optional[int] = None
    runway_approach_m: Optional[int] = None
    nuisance_flags: list[str] = Field(default_factory=list)
    nuisance_notes: list[str] = Field(default_factory=list)
    computed_at: datetime


class ListingHistoryEntry(BaseModel):
    id: int
    url: str
    title: str
    status: str
    advertiser_type: Optional[str]
    advertiser_name: Optional[str]
    created_at: datetime
    last_seen_at: Optional[datetime]
    price_value: int
    area_value: Optional[float]
    city: Optional[str]
    district: Optional[str]
    street: Optional[str]


class PriceObservationResponse(BaseModel):
    ad_id: int
    observed_at: datetime
    price_value: int
    status: Optional[str]


class ListingHistoryResponse(BaseModel):
    ad_id: int
    signals: Optional[MarketSignalsResponse]
    listings: list[ListingHistoryEntry]
    prices: list[PriceObservationResponse]


class TrackingResponse(BaseModel):
    status: TrackingStatus
    viewing_at: Optional[datetime]
    rating: Optional[int]
    offer_amount: Optional[int]
    price_at_save: Optional[int]
    last_comment: Optional[str]
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[str]


class TrackingEventResponse(BaseModel):
    id: int
    status: Optional[TrackingStatus]
    comment: Optional[str]
    viewing_at: Optional[datetime]
    rating: Optional[int]
    offer_amount: Optional[int]
    author: Optional[str]
    created_at: datetime


class TrackingDetailResponse(TrackingResponse):
    ad_id: int
    events: list[TrackingEventResponse]


class TrackingEventRequest(BaseModel):
    status: Optional[TrackingStatus] = Field(None, description="Brak = sama notatka, status bez zmian.")
    comment: Optional[str] = Field(None, max_length=5000)
    viewing_at: Optional[datetime] = Field(None, description="Lokalna data i godzina oglądania.")
    rating: Optional[int] = Field(None, ge=1, le=5)
    offer_amount: Optional[int] = Field(None, ge=0)


class LoginRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=MAX_NAME_LENGTH)
    password: str = ""


class SessionResponse(BaseModel):
    name: Optional[str]
    auth_enabled: bool


class AdSummaryResponse(BaseModel):
    id: int
    url: str
    title: str
    price_value: int
    price_currency: str
    price_per_m2: Optional[int]
    rent_value: Optional[int]
    area_value: Optional[float]
    rooms: Optional[int]
    floor: Optional[str]
    building_year: Optional[int]
    offer_type: str
    object_type: Optional[str]
    market: Optional[str]
    advertiser_type: Optional[str]
    property_condition: Optional[str]
    city: Optional[str]
    district: Optional[str]
    street: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    distance_m: Optional[float] = None
    features_count: int = 0
    created_at: datetime
    modified_at: datetime
    last_checked_at: Optional[datetime] = None
    thumbnail: Optional[str] = None
    evaluation: Optional[EvaluationResponse] = None
    tracking: Optional[TrackingResponse] = None
    market_signals: Optional[MarketSignalsResponse] = None


class AdDetailResponse(AdSummaryResponse):
    description: Optional[str]
    province: Optional[str]
    county: Optional[str]
    postal_code: Optional[str]
    building_type: Optional[str]
    building_material: Optional[str]
    building_heating: Optional[str]
    building_number_of_floors: Optional[int]
    property_ownership: Optional[str]
    status: str
    images: list[ImageResponse] = Field(default_factory=list)
    feature_groups: dict[str, list[str]] = Field(default_factory=dict)
    screening_attributes: dict[str, str] = Field(default_factory=dict)
    market_stats: Optional[MarketStatsResponse] = None


class AdSearchResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AdSummaryResponse]


class FacetValue(BaseModel):
    value: str
    label: str
    count: int
    description: Optional[str] = None


class RangeFacet(BaseModel):
    min: Optional[float]
    max: Optional[float]


class FacetsResponse(BaseModel):
    offer_types: list[FacetValue]
    object_types: list[FacetValue]
    voivodeships: list[FacetValue]
    cities: list[FacetValue]
    districts: list[FacetValue]
    features: list[FacetValue]
    building_types: list[FacetValue]
    building_materials: list[FacetValue]
    building_heating: list[FacetValue]
    markets: list[FacetValue]
    advertiser_types: list[FacetValue]
    property_conditions: list[FacetValue]
    style_tags: list[FacetValue]
    renovation_needed: list[FacetValue]
    price: RangeFacet
    price_per_m2: RangeFacet
    area: RangeFacet
    rooms: RangeFacet
    building_year: RangeFacet


class SavedSearchRequest(BaseModel):
    name: str
    query: dict


class SavedSearchResponse(BaseModel):
    id: int
    name: str
    query: dict
    created_at: datetime
    updated_at: datetime


class ServiceStatusResponse(BaseModel):
    service: str
    label: str
    status: str
    reported_status: Optional[str] = None
    phase: Optional[str] = None
    detail: Optional[dict] = None
    command: Optional[str] = None
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    seconds_since_update: Optional[int] = None
    is_alive: bool


class ServiceLogEntry(BaseModel):
    id: int
    level: str
    logger_name: str
    message: str
    logged_at: datetime


class ServiceLogsResponse(BaseModel):
    service: str
    entries: list[ServiceLogEntry]


class DistrictStatsResponse(BaseModel):
    city: Optional[str]
    district: Optional[str]
    ad_count: int
    median_price_per_m2: Optional[int]
    p25_price_per_m2: Optional[int]
    p75_price_per_m2: Optional[int]
    median_price: Optional[int]
    median_area: Optional[float]
    median_overall_score: Optional[float] = None


class AssistantCriterion(BaseModel):
    text: str = Field(..., max_length=500)
    importance: str = Field("nice", description="must = warunek konieczny, nice = życzenie.")


class AssistantPlan(BaseModel):
    query: AdSearchQuery
    keywords: list[str] = Field(default_factory=list)
    criteria: list[AssistantCriterion] = Field(default_factory=list)
    understood: str = ""
    sort: str = "relevance"
    warnings: list[str] = Field(default_factory=list)


class AssistantInterpretRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[str] = Field(default_factory=list, max_length=10)
    previous: Optional[AssistantPlan] = None


class AssistantInterpretResponse(BaseModel):
    plan: AssistantPlan
    cost_usd: float


class AssistantRankRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[str] = Field(default_factory=list, max_length=10)
    plan: AssistantPlan


class AssistantRankedAd(BaseModel):
    ad: AdSummaryResponse
    fit_score: int
    headline: str
    matches: list[str]
    gaps: list[str]
    evaluated: bool


class AssistantRankResponse(BaseModel):
    overview: str
    items: list[AssistantRankedAd]
    candidates_considered: int
    total_matching: int
    cost_usd: float


class AssistantStatusResponse(BaseModel):
    enabled: bool
    reason: Optional[str] = None
    spent_today_usd: float = 0
    daily_budget_usd: float = 0


class EvaluationRequestsRequest(BaseModel):
    ad_ids: list[int] = Field(..., min_length=1, max_length=20)


class EvaluationRequestResponse(BaseModel):
    ad_id: int
    status: str
    message: Optional[str]
    requested_at: datetime
    finished_at: Optional[datetime]
