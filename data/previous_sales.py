from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from .geo import distance_m

MATCH_RADIUS_M = 150
AREA_TOLERANCE = 0.01
MIN_AREA_TOLERANCE_M2 = 0.3
MAX_AMBIGUOUS_MATCHES = 2
MIN_PRICE_RATIO = 0.35
MAX_PRICE_RATIO = 2.0
_CELL_DEGREES = 0.002


@dataclass(frozen=True, slots=True)
class FlatSale:
    id: int
    sold_at: datetime
    price: float
    area: float
    rooms: Optional[int]
    latitude: float
    longitude: float
    floor: Optional[int] = None


@dataclass(frozen=True)
class PreviousSale:
    sold_at: datetime
    price: int
    area: float
    distance_m: int


class PreviousSaleIndex:
    def __init__(self, sales: Iterable[FlatSale]):
        cells: dict[tuple[int, int], list[FlatSale]] = defaultdict(list)
        for sale in sales:
            cells[_cell_of(sale.latitude, sale.longitude)].append(sale)
        self._cells = {}
        for key, members in cells.items():
            members.sort(key=lambda sale: sale.area)
            self._cells[key] = (members, [sale.area for sale in members])

    def match(
            self,
            latitude: Optional[float],
            longitude: Optional[float],
            area: Optional[float],
            rooms: Optional[int],
            listed_at: datetime,
            price: Optional[int] = None,
            floor: Optional[int] = None,
    ) -> Optional[PreviousSale]:
        if not (latitude and longitude and area) or float(area).is_integer():
            return None
        tolerance = max(area * AREA_TOLERANCE, MIN_AREA_TOLERANCE_M2)
        matches = []
        lat_cell, lon_cell = _cell_of(latitude, longitude)
        for d_lat in (-1, 0, 1):
            for d_lon in (-1, 0, 1):
                bucket = self._cells.get((lat_cell + d_lat, lon_cell + d_lon))
                if bucket is None:
                    continue
                members, areas = bucket
                for sale in members[bisect_left(areas, area - tolerance):bisect_right(areas, area + tolerance)]:
                    if sale.sold_at >= listed_at:
                        continue
                    if rooms and sale.rooms and rooms != sale.rooms:
                        continue
                    if price and not MIN_PRICE_RATIO <= sale.price / price <= MAX_PRICE_RATIO:
                        continue
                    if floor is not None and sale.floor is not None and abs(floor - sale.floor) > 1:
                        continue
                    distance = distance_m(latitude, longitude, sale.latitude, sale.longitude)
                    if distance <= MATCH_RADIUS_M:
                        matches.append((sale, distance))
        if not matches or len(matches) > MAX_AMBIGUOUS_MATCHES:
            return None
        sale, distance = max(matches, key=lambda match: match[0].sold_at)
        return PreviousSale(sold_at=sale.sold_at, price=round(sale.price), area=sale.area, distance_m=round(distance))


def floor_number(floor: Optional[str]) -> Optional[int]:
    if floor == "GROUND_FLOOR":
        return 0
    if floor and floor.startswith("FLOOR_") and floor[6:].isdigit():
        return int(floor[6:])
    return None


def _cell_of(latitude: float, longitude: float) -> tuple[int, int]:
    return int(latitude // _CELL_DEGREES), int(longitude // _CELL_DEGREES)
