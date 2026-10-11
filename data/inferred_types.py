from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import case, func, select
from sqlalchemy.dialects import postgresql

from .models import Ad

RENT_PRICE_CEILING = 30000
SALE_MARKETS = ("PRIMARY", "SECONDARY")

INFERRED_OFFER_TYPE = case(
    (Ad.offer_type.is_not(None), Ad.offer_type),
    (Ad.market.in_(SALE_MARKETS), "SALE"),
    (Ad.price_value < RENT_PRICE_CEILING, "RENT"),
    else_="SALE",
)


def offer_type_of(ad: Ad) -> str:
    if ad.offer_type is not None:
        return ad.offer_type
    if ad.market in SALE_MARKETS:
        return "SALE"
    return "RENT" if ad.price_value < RENT_PRICE_CEILING else "SALE"


INVESTMENT_URL_MARKER = "/inwestycja/"
_LETTER = "a-ząćęłńóśźż"
HOUSE_TITLE_PATTERN = (
    f"((^|[^{_LETTER}])(dom|domek|domu|domy|domów|domki|willa|segment|siedlisko|rezydencja|bliźniak|blizniak)"
    f"([^{_LETTER}]|$)|bliźniacz|blizniacz|szeregow|szeregówk|parterow|wolnostoj|działk|dzialk)"
)
FLAT_TITLE_PATTERN = "(mieszkani|kawalerk|apartament|garsonier|kamienic|pokój|pokoj|pokoi|[0-9] ?-?pok|studio|loft|penthouse)"
HOUSE_BUILDING_TYPES = ("DETACHED", "SEMI_DETACHED", "FARM", "RESIDENCE")
FLAT_BUILDING_TYPES = ("BLOCK", "APARTMENT", "TENEMENT", "INFILL", "LOFT")

INFERRED_OBJECT_TYPE = case(
    (func.strpos(Ad.url, INVESTMENT_URL_MARKER) > 0, "INVESTMENT"),
    (Ad.object_type.is_not(None), Ad.object_type),
    (Ad.flat_floor.is_not(None), "APARTMENT"),
    (Ad.building_type.in_(HOUSE_BUILDING_TYPES), "HOUSE"),
    (Ad.property_type == "FLAT", "APARTMENT"),
    (Ad.building_type.in_(FLAT_BUILDING_TYPES), "APARTMENT"),
    (Ad.title.regexp_match(HOUSE_TITLE_PATTERN, flags="i"), "HOUSE"),
    (Ad.title.regexp_match(FLAT_TITLE_PATTERN, flags="i"), "APARTMENT"),
    else_=None,
)


def object_type_of(ad: Ad) -> Optional[str]:
    if INVESTMENT_URL_MARKER in (ad.url or ""):
        return "INVESTMENT"
    if ad.object_type is not None:
        return ad.object_type
    if ad.flat_floor is not None:
        return "APARTMENT"
    if ad.building_type in HOUSE_BUILDING_TYPES:
        return "HOUSE"
    if ad.property_type == "FLAT" or ad.building_type in FLAT_BUILDING_TYPES:
        return "APARTMENT"
    if re.search(HOUSE_TITLE_PATTERN, ad.title or "", re.IGNORECASE):
        return "HOUSE"
    if re.search(FLAT_TITLE_PATTERN, ad.title or "", re.IGNORECASE):
        return "APARTMENT"
    return None


def inferred_types_view_sql() -> str:
    statement = select(
        Ad.id.label("ad_id"),
        INFERRED_OFFER_TYPE.label("offer_type"),
        INFERRED_OBJECT_TYPE.label("object_type"),
    )
    compiled = statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    return f"CREATE MATERIALIZED VIEW IF NOT EXISTS ad_inferred_types AS {compiled}"
