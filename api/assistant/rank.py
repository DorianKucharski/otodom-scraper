from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from data.description import plain_description
from data.feature_groups import labelled_feature_groups
from data.inferred_types import object_type_of, offer_type_of
from data.models import Ad, AdEvaluation, AdMarketSignals, AdScreening
from data.signal_phrases import (
    comparables_phrase, listing_history_phrase, location_warnings_phrase, transactions_phrase,
)
from ..labels import (
    BUILDING_HEATING, BUILDING_MATERIALS, BUILDING_TYPES, MARKETS, OBJECT_TYPES, OFFER_TYPES, PROPERTY_CONDITIONS,
    RENOVATION_NEEDED, display_label, feature_label,
)
from ..mappers import to_ad_summary
from ..query import build_search_statements, keyword_relevance
from ..schemas import AdSummaryResponse
from .interpret import RELEVANCE_SORT, SearchPlan

MAX_RESULTS = 10

_FLOOR_NAMES = {
    "GROUND_FLOOR": "parter",
    "CELLAR": "suterena",
    "GARRET": "poddasze",
    "FLOOR_HIGHER_10": "powyżej 10",
}

_CARD_RELATIONS = (
    Ad.images,
    Ad.features,
    Ad.flat_equipment,
    Ad.flat_areas,
    Ad.flat_parking,
    Ad.building_windows,
    Ad.building_conveniences,
    Ad.building_security,
    Ad.city,
    Ad.district,
    Ad.province,
)


@dataclass(frozen=True)
class AdCard:
    id: int
    title: str
    kind: str
    address: str
    price: str
    price_per_m2: Optional[str]
    rent: Optional[str]
    area: Optional[str]
    rooms: Optional[int]
    floor: Optional[str]
    building: str
    market: Optional[str]
    condition: Optional[str]
    features: str
    screening_attributes: str
    evaluation: Optional[str]
    description: Optional[str]
    market_history: Optional[str] = None


@dataclass(frozen=True)
class Candidate:
    summary: AdSummaryResponse
    card: AdCard
    evaluated: bool


@dataclass(frozen=True)
class CandidatePool:
    total_matching: int
    candidates: tuple[Candidate, ...]


@dataclass(frozen=True)
class RankedAd:
    candidate: Candidate
    fit_score: int
    headline: str
    matches: tuple[str, ...]
    gaps: tuple[str, ...]


def load_candidates(session: Session, plan: SearchPlan, limit: int, description_characters: int) -> CandidatePool:
    query = plan.query.model_copy(update={"limit": limit, "offset": 0})
    statements = build_search_statements(
        query, relevance=keyword_relevance(plan.keywords), relevance_first=plan.sort == RELEVANCE_SORT
    )
    ad_ids = list(session.execute(statements.page).scalars())
    total = session.execute(statements.total).scalar_one()
    if not ad_ids:
        return CandidatePool(total_matching=total, candidates=())

    rows = session.execute(
        statements.rows_for(ad_ids).options(*(selectinload(relation) for relation in _CARD_RELATIONS))
    ).all()
    screenings = {
        screening.ad_id: screening
        for screening in session.execute(select(AdScreening).where(AdScreening.ad_id.in_(ad_ids))).scalars()
    }
    position = {ad_id: index for index, ad_id in enumerate(ad_ids)}

    candidates = []
    for ad, evaluation, tracking, features_count, distance_m, signals in sorted(rows, key=lambda row: position[row[0].id]):
        candidates.append(Candidate(
            summary=to_ad_summary(ad, evaluation, tracking, features_count, distance_m, signals),
            card=ad_card(ad, evaluation, screenings.get(ad.id), description_characters, signals),
            evaluated=_is_evaluated(evaluation),
        ))
    return CandidatePool(total_matching=total, candidates=tuple(candidates))


def ranking_schema(candidate_ids: list[int]) -> dict:
    result = _object({
        "ad_id": {"type": "integer", "enum": candidate_ids},
        "fit_score": {"type": "integer", "enum": list(range(1, 11))},
        "headline": {"type": "string", "description": "Jedno zdanie po polsku: dlaczego to ogłoszenie."},
        "matches": {"type": "array", "items": {"type": "string"}, "description": "Spełnione wymagania."},
        "gaps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Wymagania niespełnione albo niemożliwe do sprawdzenia z danych.",
        },
    })
    return _object({
        "overview": {"type": "string", "description": "Dwa do trzech zdań po polsku o tym, co znalazłeś."},
        "results": {"type": "array", "items": result},
    })


def ranked_from_payload(payload: dict, candidates: tuple[Candidate, ...]) -> tuple[RankedAd, ...]:
    by_id = {candidate.card.id: candidate for candidate in candidates}
    ranked, seen = [], set()
    for item in payload.get("results") or []:
        candidate = by_id.get(item.get("ad_id"))
        if candidate is None or candidate.card.id in seen:
            continue
        seen.add(candidate.card.id)
        ranked.append(RankedAd(
            candidate=candidate,
            fit_score=int(item.get("fit_score") or 1),
            headline=(item.get("headline") or "").strip(),
            matches=tuple(text for text in item.get("matches") or [] if text.strip()),
            gaps=tuple(text for text in item.get("gaps") or [] if text.strip()),
        ))
    ranked.sort(key=lambda ad: ad.fit_score, reverse=True)
    return tuple(ranked[:MAX_RESULTS])


def ad_card(
        ad: Ad,
        evaluation: Optional[AdEvaluation],
        screening: Optional[AdScreening],
        description_characters: int,
        signals: Optional[AdMarketSignals] = None,
) -> AdCard:
    return AdCard(
        id=ad.id,
        title=ad.title,
        kind=" ".join(filter(None, (
            display_label(OFFER_TYPES, offer_type_of(ad)), display_label(OBJECT_TYPES, object_type_of(ad))
        ))) or "nie wiadomo",
        address=", ".join(filter(None, (
            ad.street, ad.district.name if ad.district else None, ad.city.name if ad.city else None,
            ad.province.name if ad.province else None,
        ))) or "brak danych",
        price=_money(ad.price_value) or "do ustalenia",
        price_per_m2=_money(ad.price_per_m2),
        rent=_money(ad.rent_value),
        area=f"{float(ad.area_value):.1f} m2" if ad.area_value else None,
        rooms=ad.flat_number_of_rooms,
        floor=_floor_label(ad),
        building=", ".join(filter(None, (
            str(ad.building_year) if ad.building_year else None,
            display_label(BUILDING_TYPES, ad.building_type),
            display_label(BUILDING_MATERIALS, ad.building_material),
            display_label(BUILDING_HEATING, ad.building_heating),
        ))) or "brak danych",
        market=display_label(MARKETS, ad.market),
        condition=display_label(PROPERTY_CONDITIONS, ad.property_condition),
        features=", ".join(sorted({
            feature_label(value) for _, values in labelled_feature_groups(ad) for value in values
        })) or "brak",
        screening_attributes=_pairs((screening.extracted_attributes or {}) if screening else {}),
        evaluation=_evaluation_text(evaluation) if _is_evaluated(evaluation) else None,
        description=plain_description(ad.description, description_characters),
        market_history=_market_history(ad, signals),
    )


def _market_history(ad: Ad, signals: Optional[AdMarketSignals]) -> Optional[str]:
    warnings = location_warnings_phrase(signals)
    parts = [
        listing_history_phrase(signals, ad.price_value),
        comparables_phrase(signals),
        transactions_phrase(signals),
        f"uwaga na lokalizację: {warnings}" if warnings else None,
    ]
    return "; ".join(part for part in parts if part) or None


def _evaluation_text(evaluation: AdEvaluation) -> str:
    parts = [
        f"ogólna {evaluation.overall_score}/10, wykończenie {evaluation.finish_quality_score}, "
        f"gotowość {evaluation.move_in_readiness_score}, światło {evaluation.natural_light_score}, "
        f"rozkład {evaluation.layout_score}, budynek {evaluation.building_condition_score}, "
        f"lokalizacja {evaluation.location_score}, opłacalność {evaluation.value_for_money_score}, "
        f"wiarygodność zdjęć {evaluation.photo_trust_score}",
        f"remont: {display_label(RENOVATION_NEEDED, evaluation.renovation_needed) or 'brak danych'}",
    ]
    if evaluation.summary:
        parts.append(f"podsumowanie: {evaluation.summary}")
    if evaluation.strengths:
        parts.append("mocne strony: " + "; ".join(evaluation.strengths))
    if evaluation.concerns:
        parts.append("zastrzeżenia: " + "; ".join(evaluation.concerns))
    if evaluation.attributes:
        parts.append("ze zdjęć: " + _pairs(evaluation.attributes))
    return "\n".join(parts)


def _is_evaluated(evaluation: Optional[AdEvaluation]) -> bool:
    return evaluation is not None and evaluation.overall_score is not None


def _floor_label(ad: Ad) -> Optional[str]:
    if not ad.flat_floor:
        return None
    floor = _FLOOR_NAMES.get(ad.flat_floor) or ad.flat_floor.removeprefix("FLOOR_").lower()
    return f"{floor} z {ad.building_number_of_floors}" if ad.building_number_of_floors else floor


def _money(value: Optional[int]) -> Optional[str]:
    return f"{value:,} zł".replace(",", " ") if value else None


def _pairs(values: dict) -> str:
    return "; ".join(f"{key}: {value}" for key, value in values.items()) or "brak"


def _object(properties: dict) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }
