from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Iterable, Mapping, Optional

MAX_PREDECESSOR_DISTANCE_M = 3000
MAX_CROSS_CITY_DISTANCE_M = 2000
MAX_ATTRIBUTE_MATCH_DISTANCE_M = 1000
SIMULTANEOUS_GRACE = timedelta(days=3)
MIN_TEXT_SIMILARITY = 0.35
MIN_DUPLICATE_TEXT_SIMILARITY = 0.8
ATTRIBUTE_MATCH_PRICE_TOLERANCE = 0.15
SAME_OWNER_PRICE_TOLERANCE = 0.10
PRIMARY_MARKET_TEXT_SIMILARITY = 0.9

_WORD = re.compile(r"[0-9a-ząćęłńóśźż]+", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_EARTH_RADIUS_M = 6_371_000
_GRID_DEGREES = 0.03


@dataclass(frozen=True)
class ListingRow:
    id: int
    owner_id: Optional[int]
    market: Optional[str]
    offer_type: Optional[str]
    object_type: Optional[str]
    created_at: datetime
    ended_at: Optional[datetime]
    ended_at_known: bool
    price: int
    area: Optional[float]
    rooms: Optional[int]
    floor: Optional[str]
    building_year: Optional[int]
    latitude: Optional[float]
    longitude: Optional[float]
    city_id: Optional[int]
    title: str

    @property
    def active(self) -> bool:
        return self.ended_at is None


@dataclass(frozen=True)
class Link:
    earlier_id: int
    later_id: int
    kind: str
    score: float


@dataclass(frozen=True)
class ListingText:
    title: frozenset[str]
    description: frozenset[str]


@dataclass
class ListingGroup:
    group_id: int
    member_ids: list[int] = field(default_factory=list)
    link_kinds: set[str] = field(default_factory=set)


def words_of(value: Optional[str]) -> frozenset[str]:
    if not value:
        return frozenset()
    return frozenset(word.lower() for word in _WORD.findall(_TAG.sub(" ", value)) if len(word) >= 3)


def similarity(first: frozenset[str], second: frozenset[str]) -> float:
    if not first or not second:
        return 0.0
    return len(first & second) / len(first | second)


def text_similarity(first: Optional[ListingText], second: Optional[ListingText]) -> float:
    if first is None or second is None:
        return 0.0
    return max(similarity(first.title, second.title), similarity(first.description, second.description))


def distance_m(first: ListingRow, second: ListingRow) -> Optional[float]:
    if not _has_coordinates(first) or not _has_coordinates(second):
        return None
    lat1, lon1, lat2, lon2 = map(math.radians, (first.latitude, first.longitude, second.latitude, second.longitude))
    half_chord = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(half_chord))


def candidate_pairs(rows: Iterable[ListingRow]) -> list[tuple[ListingRow, ListingRow]]:
    buckets: dict[tuple, list[ListingRow]] = defaultdict(list)
    for row in rows:
        if row.area and row.price > 0:
            buckets[_bucket_key(row)].append(row)

    pairs = []
    for key, members in buckets.items():
        neighbours = [other for neighbour_key in _neighbour_keys(key) for other in buckets.get(neighbour_key, ())]
        for later in members:
            for earlier in neighbours:
                if _ordered(earlier, later) and attributes_match(earlier, later):
                    pairs.append((earlier, later))
    return pairs


def attributes_match(earlier: ListingRow, later: ListingRow) -> bool:
    if earlier.id == later.id:
        return False
    if not _same_kind(earlier.offer_type, later.offer_type) or not _same_kind(earlier.object_type, later.object_type):
        return False
    if abs(earlier.area - later.area) > max(0.15, 0.005 * earlier.area):
        return False
    if not _equal_when_known(earlier.rooms, later.rooms):
        return False
    if not _equal_when_known(earlier.floor, later.floor):
        return False
    if earlier.building_year and later.building_year and abs(earlier.building_year - later.building_year) > 1:
        return False
    distance = distance_m(earlier, later)
    if distance is None:
        return earlier.city_id is not None and earlier.city_id == later.city_id
    if distance > MAX_PREDECESSOR_DISTANCE_M:
        return False
    if earlier.city_id and later.city_id and earlier.city_id != later.city_id:
        return distance <= MAX_CROSS_CITY_DISTANCE_M
    return True


def classify(
        earlier: ListingRow,
        later: ListingRow,
        text_similarity: float,
        now: datetime,
) -> Optional[Link]:
    same_owner = earlier.owner_id is not None and earlier.owner_id == later.owner_id
    price_ratio = _price_ratio(earlier, later)
    distance = distance_m(earlier, later)
    primary = "PRIMARY" in ((earlier.market or "").upper(), (later.market or "").upper())

    if primary and text_similarity < PRIMARY_MARKET_TEXT_SIMILARITY:
        return None

    both_active = earlier.active and later.active
    overlapping = earlier.ended_at_known and _simultaneous(earlier, later, now)
    if both_active or overlapping:
        if same_owner and price_ratio <= 0.01 and text_similarity >= MIN_DUPLICATE_TEXT_SIMILARITY:
            return Link(earlier.id, later.id, "duplicate", 3 + text_similarity)
        return None

    gap_penalty = (later.created_at - earlier.created_at).days / 1000
    if same_owner and (text_similarity >= 0.3 or price_ratio <= SAME_OWNER_PRICE_TOLERANCE):
        return Link(earlier.id, later.id, "same_advertiser", 2 + text_similarity - price_ratio - gap_penalty)

    if text_similarity >= MIN_TEXT_SIMILARITY:
        return Link(earlier.id, later.id, "text", 1 + text_similarity - price_ratio - gap_penalty)

    if (
        earlier.rooms and earlier.floor and earlier.building_year
        and later.rooms and later.floor and later.building_year
        and price_ratio <= ATTRIBUTE_MATCH_PRICE_TOLERANCE
        and distance is not None and distance <= MAX_ATTRIBUTE_MATCH_DISTANCE_M
    ):
        return Link(earlier.id, later.id, "attributes", 0.5 - price_ratio - gap_penalty)

    return None


def build_groups(
        rows: Iterable[ListingRow],
        text_of: Callable[[Iterable[int]], Mapping[int, ListingText]],
        now: datetime,
) -> dict[int, ListingGroup]:
    rows = list(rows)
    by_id = {row.id: row for row in rows}
    pairs = candidate_pairs(rows)
    texts = text_of({row.id for pair in pairs for row in pair})

    links = []
    for earlier, later in pairs:
        link = classify(earlier, later, text_similarity(texts.get(earlier.id), texts.get(later.id)), now)
        if link is not None:
            links.append(link)

    parent = {row.id: row.id for row in rows}
    members = {row.id: [row] for row in rows}
    kinds_by_root: dict[int, set[str]] = defaultdict(set)
    for link in sorted(links, key=lambda link: link.score, reverse=True):
        first_root, second_root = _find(parent, link.earlier_id), _find(parent, link.later_id)
        if first_root == second_root:
            kinds_by_root[first_root].add(link.kind)
            continue
        if _any_conflict(members[first_root], members[second_root], now):
            continue
        parent[second_root] = first_root
        members[first_root].extend(members.pop(second_root))
        kinds_by_root[first_root].update(kinds_by_root.pop(second_root, set()))
        kinds_by_root[first_root].add(link.kind)

    groups: dict[int, ListingGroup] = {}
    for row in rows:
        root = _find(parent, row.id)
        group = groups.setdefault(root, ListingGroup(group_id=root))
        group.member_ids.append(row.id)
    for root, kinds in kinds_by_root.items():
        groups[_find(parent, root)].link_kinds.update(kinds)

    by_member: dict[int, ListingGroup] = {}
    for group in groups.values():
        group.member_ids.sort(key=lambda member_id: (by_id[member_id].created_at, member_id))
        group.group_id = group.member_ids[0]
        for member_id in group.member_ids:
            by_member[member_id] = group
    return by_member


def _any_conflict(first: list[ListingRow], second: list[ListingRow], now: datetime) -> bool:
    return any(_live_together(one, other, now) for one in first for other in second)


def _live_together(first: ListingRow, second: ListingRow, now: datetime) -> bool:
    if not (first.ended_at_known and second.ended_at_known):
        return False
    if first.owner_id is not None and first.owner_id == second.owner_id and first.price == second.price:
        return False
    first_end, second_end = first.ended_at or now, second.ended_at or now
    return (
        second.created_at < first_end - SIMULTANEOUS_GRACE
        and first.created_at < second_end - SIMULTANEOUS_GRACE
    )


def _bucket_key(row: ListingRow) -> tuple:
    if _has_coordinates(row):
        cell = (int(row.latitude // _GRID_DEGREES), int(row.longitude // _GRID_DEGREES))
    else:
        cell = ("city", row.city_id)
    return (cell, round(row.area))


def _neighbour_keys(key: tuple) -> Iterable[tuple]:
    cell, area = key
    areas = (area - 1, area, area + 1)
    if cell and cell[0] == "city":
        return [(cell, nearby_area) for nearby_area in areas]
    lat_cell, lon_cell = cell
    return [
        ((lat_cell + d_lat, lon_cell + d_lon), nearby_area)
        for d_lat in (-1, 0, 1)
        for d_lon in (-1, 0, 1)
        for nearby_area in areas
    ]


def _ordered(earlier: ListingRow, later: ListingRow) -> bool:
    return (earlier.created_at, earlier.id) < (later.created_at, later.id)


def _simultaneous(earlier: ListingRow, later: ListingRow, now: datetime) -> bool:
    earlier_end = earlier.ended_at or now
    return earlier_end - SIMULTANEOUS_GRACE > later.created_at


def _price_ratio(earlier: ListingRow, later: ListingRow) -> float:
    return abs(later.price - earlier.price) / max(earlier.price, 1)


def _same_kind(first: Optional[str], second: Optional[str]) -> bool:
    return first is None or second is None or first == second


def _equal_when_known(first, second) -> bool:
    return first is None or second is None or first == second


def _has_coordinates(row: ListingRow) -> bool:
    return bool(row.latitude) and bool(row.longitude)


def _find(parent: dict[int, int], node: int) -> int:
    while parent[node] != node:
        parent[node] = parent[parent[node]]
        node = parent[node]
    return node


