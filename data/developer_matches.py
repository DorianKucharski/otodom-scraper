from __future__ import annotations

import bisect
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from .developer_prices import place_name
from .street_checks import street_key

AREA_TOLERANCE_M2 = 0.05
EXACT_PRICE_RATIO = 0.01
CLOSE_PRICE_RATIO = 0.05
MIN_SCORE = 2
GONE_AFTER = timedelta(days=3)

_UNITS = text("""
SELECT id, institution_id, dataset_id, developer, investment, town, street, building_number, unit, area::float AS area,
       rooms, price, price_per_m2, price_since, price_with_extras, extras, first_seen, last_seen, first_price,
       highest_price
FROM developer_units
WHERE area IS NOT NULL AND price IS NOT NULL
""")


@dataclass(frozen=True, slots=True)
class DeveloperUnitRow:
    id: int
    institution_id: int
    dataset_id: int
    developer: Optional[str]
    investment: Optional[str]
    town: str
    street: Optional[str]
    building_number: Optional[str]
    unit: str
    area: float
    rooms: Optional[int]
    price: int
    price_per_m2: Optional[int]
    price_since: Optional[datetime]
    price_with_extras: Optional[int]
    extras: tuple[str, ...]
    first_seen: datetime
    last_seen: datetime
    first_price: Optional[int]
    highest_price: Optional[int]

    @property
    def street_key(self) -> Optional[str]:
        return street_key(self.street)

    @property
    def investment_key(self) -> tuple:
        return self.institution_id, place_name(self.investment) or self.street_key or place_name(self.town)


@dataclass(frozen=True)
class InvestmentStats:
    listed: int
    gone: int
    tracked_since: datetime


@dataclass(frozen=True)
class DeveloperMatch:
    unit: DeveloperUnitRow
    gone: bool
    investment: InvestmentStats

    @property
    def investment_label(self) -> str:
        address = " ".join(part for part in (self.unit.street, self.unit.building_number) if part)
        name = self.unit.investment
        if name and address:
            return f"{name}, {address}, {self.unit.town}"
        return ", ".join(part for part in (name or address, self.unit.town) if part)


class DeveloperUnitIndex:
    def __init__(self, units: list[DeveloperUnitRow]):
        self.size = len(units)
        self._by_town: dict[str, list[DeveloperUnitRow]] = defaultdict(list)
        latest: dict[tuple, datetime] = {}
        for unit in units:
            self._by_town[place_name(unit.town)].append(unit)
            group = (unit.institution_id, place_name(unit.town))
            latest[group] = max(latest.get(group, unit.last_seen), unit.last_seen)
        for town_units in self._by_town.values():
            town_units.sort(key=lambda unit: unit.area)
        self._areas = {town: [unit.area for unit in town_units] for town, town_units in self._by_town.items()}
        self._gone = {
            unit.id for unit in units if unit.last_seen < latest[(unit.institution_id, place_name(unit.town))] - GONE_AFTER
        }
        investments: dict[tuple, list[DeveloperUnitRow]] = defaultdict(list)
        for unit in units:
            investments[unit.investment_key].append(unit)
        self._investments = {
            key: InvestmentStats(
                listed=sum(1 for unit in members if unit.id not in self._gone),
                gone=sum(1 for unit in members if unit.id in self._gone),
                tracked_since=min(unit.first_seen for unit in members),
            )
            for key, members in investments.items()
        }

    def match(self, town: Optional[str], street: Optional[str], area: Optional[float], rooms: Optional[int],
              price: Optional[int]) -> Optional[DeveloperMatch]:
        town = place_name(town)
        if not town or not area or not price or town not in self._by_town:
            return None
        units, areas = self._by_town[town], self._areas[town]
        start = bisect.bisect_left(areas, area - AREA_TOLERANCE_M2)
        stop = bisect.bisect_right(areas, area + AREA_TOLERANCE_M2)
        scored = []
        for unit in units[start:stop]:
            score = _score(unit, street, rooms, price)
            if score >= MIN_SCORE:
                scored.append((score, unit))
        if not scored:
            return None
        best_score = max(score for score, _ in scored)
        best = [unit for score, unit in scored if score == best_score]
        best.sort(key=lambda unit: (unit.id in self._gone, abs(unit.price - price), -unit.last_seen.timestamp()))
        chosen = best[0]
        if any(abs(unit.price - chosen.price) > chosen.price * EXACT_PRICE_RATIO
               or unit.institution_id != chosen.institution_id for unit in best[1:]):
            return None
        return DeveloperMatch(unit=chosen, gone=chosen.id in self._gone, investment=self._investments[chosen.investment_key])


def _score(unit: DeveloperUnitRow, street: Optional[str], rooms: Optional[int], price: int) -> int:
    score = 0
    if street and unit.street_key and unit.street_key == street:
        score += 2
    prices = [value for value in (unit.price, unit.first_price, unit.highest_price) if value]
    difference = min(abs(price - value) / value for value in prices)
    if difference <= EXACT_PRICE_RATIO:
        score += 2
    elif difference <= CLOSE_PRICE_RATIO:
        score += 1
    if rooms and unit.rooms:
        score += 1 if rooms == unit.rooms else -2
    return score


def load_developer_units(connection: Connection) -> DeveloperUnitIndex:
    if not inspect(connection).has_table("developer_units"):
        return DeveloperUnitIndex([])
    return DeveloperUnitIndex([
        DeveloperUnitRow(
            id=row.id, institution_id=row.institution_id, dataset_id=row.dataset_id, developer=row.developer,
            investment=row.investment, town=row.town, street=row.street, building_number=row.building_number,
            unit=row.unit, area=row.area, rooms=row.rooms, price=row.price, price_per_m2=row.price_per_m2,
            price_since=row.price_since, price_with_extras=row.price_with_extras, extras=tuple(row.extras or ()),
            first_seen=row.first_seen, last_seen=row.last_seen, first_price=row.first_price,
            highest_price=row.highest_price,
        )
        for row in connection.execute(_UNITS)
    ])
