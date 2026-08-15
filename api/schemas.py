from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from enricher.schema import SCORE_FIELD_NAMES

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
    thumbnail: Optional[str] = None
    evaluation: Optional[EvaluationResponse] = None


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


class RangeFacet(BaseModel):
    min: Optional[float]
    max: Optional[float]


class FacetsResponse(BaseModel):
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
