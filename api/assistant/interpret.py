from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from data.search_url import normalize_name
from ..labels import (
    ADVERTISER_TYPES, BUILDING_HEATING, BUILDING_MATERIALS, BUILDING_TYPES, MARKETS, OBJECT_TYPES, OFFER_TYPES,
    PROPERTY_CONDITIONS, ValueLabel,
)
from ..schemas import AdSearchQuery, FacetsResponse, SortDirection, SortField

RELEVANCE_SORT = "relevance"

INTEGER_LIMITS = (
    "min_price", "max_price", "min_price_per_m2", "max_price_per_m2", "max_rent",
    "min_rooms", "max_rooms", "min_floor", "max_floor", "min_building_year", "max_building_year",
)
DECIMAL_LIMITS = ("min_area", "max_area")
ASSISTANT_SORTS = (
    RELEVANCE_SORT, "price_value", "price_per_m2", "area_value", "created_at", "overall_score",
    "value_for_money_score",
)
CRITERION_IMPORTANCE = ("must", "nice")

_MARKET_CODES = ("PRIMARY", "SECONDARY")
_MAX_RADIUS_M = 50_000
_SURROUNDINGS_RADIUS_M = 10_000

CODED_FILTERS: tuple[tuple[str, dict[str, ValueLabel]], ...] = (
    ("offer_types", OFFER_TYPES),
    ("object_types", OBJECT_TYPES),
    ("markets", {code: MARKETS[code] for code in _MARKET_CODES}),
    ("advertiser_types", ADVERTISER_TYPES),
    ("building_types", BUILDING_TYPES),
    ("building_materials", BUILDING_MATERIALS),
    ("building_heating", BUILDING_HEATING),
    ("property_conditions", PROPERTY_CONDITIONS),
)


@dataclass(frozen=True)
class Criterion:
    text: str
    importance: str


@dataclass(frozen=True)
class SearchPlan:
    query: AdSearchQuery
    keywords: tuple[str, ...]
    criteria: tuple[Criterion, ...]
    understood: str
    sort: str
    warnings: tuple[str, ...] = field(default_factory=tuple)


def interpretation_schema(facets: FacetsResponse) -> dict:
    feature_labels = [facet.value for facet in facets.features]
    feature_items = {"type": "string", "enum": feature_labels} if feature_labels else {"type": "string"}

    properties = {
        "understood": {
            "type": "string",
            "description": "Jedno do dwóch zdań po polsku: jak zrozumiałeś życzenie i co ustawiłeś.",
        },
        **{
            name: {"type": "array", "items": {"type": "string", "enum": list(labels)}}
            for name, labels in CODED_FILTERS
        },
        "voivodeships": {"type": "array", "items": {"type": "string"}, "description": "Nazwy województw."},
        "cities": {"type": "array", "items": {"type": "string"}, "description": "Nazwy miast lub wsi."},
        "districts": {"type": "array", "items": {"type": "string"}, "description": "Nazwy dzielnic."},
        "near": {
            "type": "array",
            "description": "Najwyżej jedno miejsce, wokół którego szukać, gdy użytkownik chce być blisko "
                           "konkretnego punktu (osiedle, ulica, park, stacja).",
            "items": _object({
                "place": {"type": "string"},
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
                "radius_m": {"type": "integer"},
            }),
        },
        "limits": {
            "type": "array",
            "description": "Progi liczbowe. Ceny w złotych, powierzchnia w m2, piętro 0 to parter.",
            "items": _object({
                "field": {"type": "string", "enum": [*INTEGER_LIMITS, *DECIMAL_LIMITS]},
                "value": {"type": "number"},
            }),
        },
        "exclude_ground_floor": {"type": "boolean"},
        "exclude_top_floor": {"type": "boolean"},
        "features": {"type": "array", "items": feature_items, "description": "Cechy, które ogłoszenie musi mieć."},
        "excluded_features": {"type": "array", "items": feature_items, "description": "Cechy wykluczone."},
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Krótkie frazy do wyszukania w tytule i opisie, z synonimami i rdzeniami słów.",
        },
        "criteria": {
            "type": "array",
            "description": "Wymagania, których nie da się wyrazić filtrem, do oceny ogłoszeń przez czytanie.",
            "items": _object({
                "text": {"type": "string"},
                "importance": {"type": "string", "enum": list(CRITERION_IMPORTANCE)},
            }),
        },
        "sort": {"type": "string", "enum": list(ASSISTANT_SORTS)},
        "direction": {"type": "string", "enum": [direction.value for direction in SortDirection]},
    }
    return _object(properties)


def plan_from_payload(payload: dict, facets: FacetsResponse) -> SearchPlan:
    warnings: list[str] = []
    values: dict = {}

    for name, labels in CODED_FILTERS:
        values[name] = [code for code in payload.get(name) or [] if code in labels]

    values["voivodeships"] = _resolved(payload.get("voivodeships"), facets.voivodeships, "województwa", warnings)
    values["cities"] = _resolved(payload.get("cities"), facets.cities, "miejscowości", warnings)
    values["districts"] = _resolved(payload.get("districts"), facets.districts, "dzielnicy", warnings)

    for limit in payload.get("limits") or []:
        name, value = limit.get("field"), limit.get("value")
        if value is None or value < 0:
            continue
        if name in INTEGER_LIMITS:
            values[name] = int(round(value))
        elif name in DECIMAL_LIMITS:
            values[name] = float(value)

    near = next(iter(payload.get("near") or []), None)
    if near and _is_in_poland(near.get("latitude"), near.get("longitude")):
        values["latitude"] = float(near["latitude"])
        values["longitude"] = float(near["longitude"])
        values["radius_m"] = min(max(int(near.get("radius_m") or 1500), 300), _MAX_RADIUS_M)
        if values["radius_m"] > _SURROUNDINGS_RADIUS_M and (values["cities"] or values["districts"]):
            values["cities"], values["districts"] = [], []
            warnings.append(
                f"Szukam w promieniu {values['radius_m'] // 1000} km od „{near.get('place')}”, "
                "więc nie zawężam do samego miasta."
            )
    elif near:
        warnings.append(f"Nie znam położenia miejsca „{near.get('place')}”, pomijam szukanie wokół niego.")

    known_features = {facet.value for facet in facets.features}
    values["features"] = [value for value in payload.get("features") or [] if value in known_features]
    values["excluded_features"] = [value for value in payload.get("excluded_features") or [] if value in known_features]
    values["exclude_ground_floor"] = bool(payload.get("exclude_ground_floor"))
    values["exclude_top_floor"] = bool(payload.get("exclude_top_floor"))

    sort = payload.get("sort") if payload.get("sort") in ASSISTANT_SORTS else RELEVANCE_SORT
    direction = payload.get("direction") if payload.get("direction") in ("asc", "desc") else "desc"
    if sort == RELEVANCE_SORT:
        values["sort"], values["direction"] = SortField("created_at"), SortDirection.DESC
    else:
        values["sort"], values["direction"] = SortField(sort), SortDirection(direction)

    return SearchPlan(
        query=AdSearchQuery(**values),
        keywords=tuple(_unique(keyword.strip() for keyword in payload.get("keywords") or [] if keyword.strip()))[:12],
        criteria=tuple(
            Criterion(text=item["text"].strip(), importance=item.get("importance", "nice"))
            for item in payload.get("criteria") or []
            if item.get("text", "").strip()
        )[:12],
        understood=(payload.get("understood") or "").strip(),
        sort=sort,
        warnings=tuple(warnings),
    )


def vocabulary(facets: FacetsResponse) -> dict:
    return {
        "coded_filters": [
            (name, [(code, label.label, label.description) for code, label in labels.items()])
            for name, labels in CODED_FILTERS
        ],
        "voivodeships": [facet.value for facet in facets.voivodeships],
        "top_cities": [facet.value for facet in facets.cities[:60]],
        "features": [facet.value for facet in facets.features],
    }


def _resolved(names: Optional[Iterable[str]], facets, level: str, warnings: list[str]) -> list[str]:
    by_normalized = {}
    for facet in facets:
        by_normalized.setdefault(normalize_name(facet.value).strip(), facet.value)

    resolved = []
    for name in names or []:
        match = by_normalized.get(normalize_name(name).strip())
        if match is None:
            warnings.append(f"Nie znalazłem {level} „{name}” w ogłoszeniach, pomijam ten filtr.")
        elif match not in resolved:
            resolved.append(match)
    return resolved


def _is_in_poland(latitude, longitude) -> bool:
    return latitude is not None and longitude is not None and 48.9 <= latitude <= 55.1 and 14.0 <= longitude <= 24.2


def _unique(values: Iterable[str]) -> list[str]:
    seen = []
    for value in values:
        if value.casefold() not in (existing.casefold() for existing in seen):
            seen.append(value)
    return seen


def _object(properties: dict) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }
