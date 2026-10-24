from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Mapping, Optional

from psycopg2.extras import Json, execute_values
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from .derived_tables import ensure_table
from .area_checks import AREA_TEXT_PATTERN, area_verdict
from .previous_sales import FlatSale, PreviousSaleIndex
from .comparables import ComparableRow, ComparablesIndex
from .listing_lineage import ListingGroup, ListingRow, ListingText, build_groups, words_of
from .location_checks import (
    TEXT_CHECK_BORDER_M, LocationVerdict, PlaceFinder, lineage_verdict, load_district_names, load_pin_checks,
    load_place_centres, pin_verdict, text_verdict,
)
from .inferred_types import HOUSE_BUILDING_TYPES, HOUSE_TITLE_PATTERN
from .models import AdMarketSignals, is_masked
from .price_history import BACKFILL_MISSING_OBSERVATIONS

logger = logging.getLogger(__name__)

COMPARABLE_RECENCY = timedelta(days=180)
STALE_AFTER = timedelta(days=45)
TRANSACTION_RECENCY = timedelta(days=730)
MIN_TRANSACTIONS = 8
MAX_FLAT_SALE_AREA = 180
_HOUSE_TITLE = re.compile(HOUSE_TITLE_PATTERN, re.IGNORECASE)
MIN_TRANSACTION_PRICE_PER_M2 = 2000
MAX_TRANSACTION_PRICE_PER_M2 = 60000
_RCN_MARKETS = {"rynekWtorny": "SECONDARY", "rynekPierwotny": "PRIMARY"}
TEXT_BATCH_SIZE = 5000
INSERT_PAGE_SIZE = 5000
_KNOWN_END_STATUSES = ("removed_by_user", "removed_by_parent_ad")

_LISTINGS = text("""
SELECT a.id,
       a.owner_id,
       a.market,
       coalesce(t.offer_type, a.offer_type)   AS offer_type,
       coalesce(t.object_type, a.object_type) AS object_type,
       a.status,
       a.created_at,
       a.modified_at,
       a.scraped_at,
       a.price_value,
       a.area_value::float                    AS area_value,
       a.flat_number_of_rooms,
       a.flat_floor,
       a.building_year,
       a.latitude::float                      AS latitude,
       a.longitude::float                     AS longitude,
       a.city_id,
       c.name                                 AS city_name,
       a.title,
       a.building_type
FROM ads a
LEFT JOIN ad_inferred_types t ON t.ad_id = a.id
LEFT JOIN cities c ON c.id = a.city_id
""")

_TEXTS = text("SELECT id, title, description FROM ads WHERE id = ANY(:ids)")
_ALL_FLAT_SALES = text("""
SELECT t.id,
       t.transaction_date,
       t.rooms,
       ST_Y(t.location_point) AS latitude,
       ST_X(t.location_point) AS longitude,
       t.area_value::float    AS area_value,
       coalesce(t.unit_price, CASE WHEN k.lokale = 1 THEN t.transaction_price END)::float AS price
FROM rcn_transactions t
JOIN (SELECT transaction_key, count(*) AS lokale FROM rcn_transactions GROUP BY transaction_key) k
  ON k.transaction_key = t.transaction_key
WHERE t.function = 'mieszkalna'
  AND (t.share IS NULL OR t.share = '1/1')
  AND (t.transaction_kind IS NULL OR t.transaction_kind = 'wolnyRynek')
  AND t.area_value BETWEEN 15 AND 400
""")
_AREA_TEXTS = text("SELECT id, title, description FROM ads WHERE description ~* :pattern AND description <> '***'")
_FLAT_SALES = text("""
SELECT t.id,
       t.market,
       ST_Y(t.location_point)                                   AS latitude,
       ST_X(t.location_point)                                   AS longitude,
       t.area_value::float                                      AS area_value,
       coalesce(t.unit_price, CASE WHEN k.lokale = 1 THEN t.transaction_price END)::float AS price
FROM rcn_transactions t
JOIN (SELECT transaction_key, count(*) AS lokale FROM rcn_transactions GROUP BY transaction_key) k
  ON k.transaction_key = t.transaction_key
WHERE t.transaction_date >= :since
  AND t.function = 'mieszkalna'
  AND (t.share IS NULL OR t.share = '1/1')
  AND (t.transaction_kind IS NULL OR t.transaction_kind = 'wolnyRynek')
  AND t.area_value BETWEEN 15 AND 400
""")
_OBSERVATIONS = text("SELECT ad_id, observed_at, price_value FROM ad_price_observations ORDER BY observed_at")

_INSERT = """
INSERT INTO ad_market_signals (
    ad_id, listing_group_id, listings_count, advertisers_count, first_listed_at, days_on_market,
    first_price, lowest_price, highest_price, price_change_pct,
    comparables_count, comparables_radius_m, comparables_median_price_per_m2,
    comparables_p25_price_per_m2, comparables_p75_price_per_m2, price_vs_comparables_pct,
    transactions_count, transactions_radius_m, transactions_median_price_per_m2,
    transactions_p25_price_per_m2, transactions_p75_price_per_m2, price_vs_transactions_pct,
    pin_city_name, pin_gmina_name, city_border_distance_m, location_flags, location_notes,
    area_flags, area_notes, previous_sale_at, previous_sale_price, previous_sale_distance_m, computed_at
) VALUES %s
"""


@dataclass(frozen=True)
class AdFacts:
    listing: ListingRow
    status: str
    city_name: Optional[str]
    last_seen_at: datetime


@dataclass(frozen=True)
class GroupHistory:
    first_listed_at: datetime
    days_on_market: int
    first_price: Optional[int]
    lowest_price: Optional[int]
    highest_price: Optional[int]
    advertisers_count: int


def market_signals_due(engine: Engine, interval_hours: float, now: Optional[datetime] = None) -> bool:
    if interval_hours <= 0:
        return False
    with engine.connect() as connection:
        last = connection.execute(text("SELECT max(computed_at) FROM ad_market_signals")).scalar()
    return last is None or (now or datetime.now()) - last >= timedelta(hours=interval_hours)


def refresh_market_signals(engine: Engine, now: Optional[datetime] = None) -> int:
    now = now or datetime.now()
    ensure_table(engine, AdMarketSignals.__table__)
    with engine.begin() as connection:
        backfilled = connection.execute(BACKFILL_MISSING_OBSERVATIONS).rowcount
    logger.info("Backfilled %d missing price observations", backfilled)

    with engine.connect() as connection:
        facts = _load_facts(connection, now)
        logger.info("Loaded %d ads for market signals", len(facts))
        groups = build_groups(
            (fact.listing for fact in facts.values()),
            lambda ids: _load_texts(connection, ids),
            now,
        )
        observations = _load_observations(connection)
        place_centres = load_place_centres(connection)
        district_names = load_district_names(connection)
        sales = TransactionIndex(_load_flat_sales(connection, now - TRANSACTION_RECENCY))
        previous_sales = PreviousSaleIndex(_load_all_flat_sales(connection))
    logger.info("Loaded %d recent RCN flat sales", sales.size)

    linked = sum(1 for group in {id(group): group for group in groups.values()}.values() if len(group.member_ids) > 1)
    logger.info("Linked listings into %d multi-listing groups", linked)

    histories = {
        group.group_id: group_history(group, facts, observations, now)
        for group in {group.group_id: group for group in groups.values()}.values()
    }
    comparables = _comparables(facts, groups, now)

    with engine.begin() as connection:
        pin_checks = load_pin_checks(connection)
    logger.info("Checked %d pins against city boundaries", len(pin_checks))

    texts_needed = [
        ad_id for ad_id, check in pin_checks.items()
        if check.claimed_is_town and (not check.inside_claimed or (check.border_m or 0) <= TEXT_CHECK_BORDER_M)
    ]
    with engine.connect() as connection:
        descriptions = _load_raw_texts(connection, texts_needed)
        area_texts = {row.id: (row.title, row.description) for row in connection.execute(_AREA_TEXTS, {"pattern": AREA_TEXT_PATTERN})}
    logger.info("Checking area wording in %d descriptions", len(area_texts))
    places = PlaceFinder(place_centres)

    rows = []
    for ad_id, fact in facts.items():
        group = groups[ad_id]
        history = histories[group.group_id]
        verdict = LocationVerdict()
        check = pin_checks.get(ad_id)
        pin_verdict(fact.city_name, check, verdict)
        if ad_id in descriptions:
            title, description = descriptions[ad_id]
            text_verdict(
                fact.city_name, fact.listing.latitude, fact.listing.longitude, title, description, places, verdict,
                district_names.get(fact.city_name, ()),
            )
        lineage_verdict(fact.city_name, (facts[member].city_name for member in group.member_ids if member != ad_id), verdict)
        area = area_verdict(fact.listing.area, *area_texts[ad_id]) if ad_id in area_texts else None
        stats = comparables.get(ad_id)
        price_per_m2 = fact.listing.price / fact.listing.area if fact.listing.area else None
        sold = sales.stats_for(fact.listing)
        previous = previous_sales.match(
            fact.listing.latitude, fact.listing.longitude, fact.listing.area, fact.listing.rooms,
            fact.listing.created_at, fact.listing.price,
        ) if _is_flat_sale(fact.listing) else None
        rows.append((
            ad_id,
            group.group_id,
            len(group.member_ids),
            history.advertisers_count,
            history.first_listed_at,
            history.days_on_market,
            history.first_price,
            history.lowest_price,
            history.highest_price,
            _change_pct(fact.listing.price, history.first_price),
            stats.count if stats else 0,
            stats.radius_m if stats else None,
            stats.median_price_per_m2 if stats else None,
            stats.p25_price_per_m2 if stats else None,
            stats.p75_price_per_m2 if stats else None,
            stats.difference_pct(price_per_m2) if stats else None,
            sold.count if sold else 0,
            sold.radius_m if sold else None,
            sold.median_price_per_m2 if sold else None,
            sold.p25_price_per_m2 if sold else None,
            sold.p75_price_per_m2 if sold else None,
            sold.difference_pct(price_per_m2) if sold else None,
            check.pin_city_name if check else None,
            check.pin_gmina_name if check else None,
            check.border_m if check else None,
            Json(verdict.flags),
            Json(verdict.notes),
            Json(area.flags if area else []),
            Json(area.notes if area else []),
            previous.sold_at if previous else None,
            previous.price if previous else None,
            previous.distance_m if previous else None,
            now,
        ))

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM ad_market_signals"))
        cursor = connection.connection.cursor()
        execute_values(cursor, _INSERT, rows, page_size=INSERT_PAGE_SIZE)
    logger.info("Market signals written for %d ads", len(rows))
    return len(rows)


def group_history(
        group: ListingGroup,
        facts: Mapping[int, AdFacts],
        observations: Mapping[int, list[tuple[datetime, int]]],
        now: datetime,
) -> GroupHistory:
    members = [facts[member_id] for member_id in group.member_ids]
    first_listed_at = min(member.listing.created_at for member in members)
    if any(member.listing.active for member in members):
        ended_at = now
    else:
        ended_at = max(member.listing.ended_at or member.last_seen_at for member in members)

    timeline = sorted(
        (observed_at, price)
        for member in members
        for observed_at, price in (observations.get(member.listing.id) or [(member.listing.created_at, member.listing.price)])
        if price
    )
    first_member = members[0].listing
    first_member_prices = observations.get(first_member.id)
    first_price = first_member_prices[0][1] if first_member_prices else first_member.price
    prices = [price for _, price in timeline]
    owners = {member.listing.owner_id for member in members}

    return GroupHistory(
        first_listed_at=first_listed_at,
        days_on_market=max((ended_at - first_listed_at).days, 0),
        first_price=first_price or None,
        lowest_price=min(prices) if prices else None,
        highest_price=max(prices) if prices else None,
        advertisers_count=len(owners),
    )


def listing_from_row(row, now: datetime) -> ListingRow:
    status = _status_value(row.status)
    last_seen = row.scraped_at or row.modified_at
    if status == "active" and last_seen is not None and now - last_seen > STALE_AFTER:
        ended_at, known = last_seen, False
    elif status == "active":
        ended_at, known = None, True
    elif status in _KNOWN_END_STATUSES and row.modified_at is not None:
        ended_at, known = min(row.modified_at, row.scraped_at or row.modified_at), True
    else:
        ended_at, known = row.scraped_at or row.modified_at, False
    return ListingRow(
        id=row.id,
        owner_id=row.owner_id,
        market=row.market,
        offer_type=row.offer_type,
        object_type=row.object_type,
        created_at=row.created_at,
        ended_at=ended_at,
        ended_at_known=known,
        price=row.price_value or 0,
        area=row.area_value,
        rooms=row.flat_number_of_rooms,
        floor=row.flat_floor,
        building_year=row.building_year,
        latitude=row.latitude,
        longitude=row.longitude,
        city_id=row.city_id,
        title=row.title or "",
        building_type=row.building_type,
    )


def _load_facts(connection, now: datetime) -> dict[int, AdFacts]:
    facts = {}
    for row in connection.execute(_LISTINGS):
        listing = listing_from_row(row, now)
        facts[row.id] = AdFacts(
            listing=listing,
            status=_status_value(row.status),
            city_name=row.city_name,
            last_seen_at=row.scraped_at or row.modified_at,
        )
    return facts


def _load_texts(connection, ids: Iterable[int]) -> dict[int, ListingText]:
    return {
        ad_id: ListingText(
            title=words_of(title),
            description=frozenset() if is_masked(description) else words_of(description),
        )
        for ad_id, (title, description) in _load_raw_texts(connection, ids).items()
    }


def _load_raw_texts(connection, ids: Iterable[int]) -> dict[int, tuple[Optional[str], Optional[str]]]:
    ids = list(ids)
    texts = {}
    for start in range(0, len(ids), TEXT_BATCH_SIZE):
        for row in connection.execute(_TEXTS, {"ids": ids[start:start + TEXT_BATCH_SIZE]}):
            texts[row.id] = (row.title, None if is_masked(row.description) else row.description)
    return texts


def _load_observations(connection) -> dict[int, list[tuple[datetime, int]]]:
    observations: dict[int, list[tuple[datetime, int]]] = defaultdict(list)
    for row in connection.execute(_OBSERVATIONS):
        observations[row.ad_id].append((row.observed_at, row.price_value))
    return observations


def _comparables(facts: Mapping[int, AdFacts], groups: Mapping[int, ListingGroup], now: datetime) -> dict:
    def comparable(fact: AdFacts) -> Optional[ComparableRow]:
        listing = fact.listing
        if not (listing.area and listing.price and listing.latitude and listing.longitude):
            return None
        return ComparableRow(
            id=listing.id,
            group_id=groups[listing.id].group_id,
            offer_type=listing.offer_type,
            object_type=listing.object_type,
            latitude=listing.latitude,
            longitude=listing.longitude,
            area=listing.area,
            price_per_m2=listing.price / listing.area,
        )

    pool_since = now - COMPARABLE_RECENCY
    pool = [
        row for row in (
            comparable(fact) for fact in facts.values()
            if fact.last_seen_at is not None and fact.last_seen_at >= pool_since
        )
        if row is not None
    ]
    index = ComparablesIndex(pool)
    logger.info("Comparables pool: %d listings", len(pool))
    results = {}
    for ad_id, fact in facts.items():
        target = comparable(fact)
        if target is not None:
            stats = index.stats_for(target)
            if stats is not None:
                results[ad_id] = stats
    return results


class TransactionIndex:
    def __init__(self, rows: list[ComparableRow]):
        self.size = len(rows)
        self._by_market = ComparablesIndex(rows, min_comparables=MIN_TRANSACTIONS)
        self._any_market = ComparablesIndex(
            [ComparableRow(**{**row.__dict__, "offer_type": None}) for row in rows], min_comparables=MIN_TRANSACTIONS,
        )

    def stats_for(self, listing: ListingRow):
        if self.size == 0 or not _is_flat_sale(listing) or not (listing.area and listing.latitude and listing.longitude):
            return None
        target = ComparableRow(
            id=-listing.id, group_id=0, offer_type=(listing.market or "").upper() or None, object_type=None,
            latitude=listing.latitude, longitude=listing.longitude, area=listing.area,
            price_per_m2=listing.price / listing.area,
        )
        return self._by_market.stats_for(target) or self._any_market.stats_for(
            ComparableRow(**{**target.__dict__, "offer_type": None})
        )


def _is_flat_sale(listing: ListingRow) -> bool:
    return (
        listing.offer_type in (None, "SALE")
        and listing.object_type in (None, "APARTMENT")
        and listing.price > 0
        and (listing.area or 0) <= MAX_FLAT_SALE_AREA
        and listing.building_type not in HOUSE_BUILDING_TYPES
        and not _HOUSE_TITLE.search(listing.title)
    )


def _load_flat_sales(connection, since: datetime) -> list[ComparableRow]:
    if not inspect(connection).has_table("rcn_transactions"):
        return []
    rows = []
    for row in connection.execute(_FLAT_SALES, {"since": since}):
        if not row.price or not row.area_value:
            continue
        price_per_m2 = row.price / row.area_value
        if not MIN_TRANSACTION_PRICE_PER_M2 <= price_per_m2 <= MAX_TRANSACTION_PRICE_PER_M2:
            continue
        rows.append(ComparableRow(
            id=row.id, group_id=-row.id, offer_type=_RCN_MARKETS.get(row.market), object_type=None,
            latitude=row.latitude, longitude=row.longitude, area=row.area_value, price_per_m2=price_per_m2,
        ))
    return rows


def _load_all_flat_sales(connection) -> list[FlatSale]:
    if not inspect(connection).has_table("rcn_transactions"):
        return []
    return [
        FlatSale(
            id=row.id, sold_at=row.transaction_date, price=row.price, area=row.area_value, rooms=row.rooms,
            latitude=row.latitude, longitude=row.longitude,
        )
        for row in connection.execute(_ALL_FLAT_SALES)
        if row.price and row.area_value and row.price / row.area_value >= MIN_TRANSACTION_PRICE_PER_M2
    ]


def _change_pct(price: Optional[int], first_price: Optional[int]) -> Optional[float]:
    if not price or not first_price:
        return None
    return round((price / first_price - 1) * 100, 1)


def _status_value(status) -> str:
    return status.value if hasattr(status, "value") else str(status)
