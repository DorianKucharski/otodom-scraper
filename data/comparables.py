from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass
from statistics import median, quantiles
from typing import Iterable, Optional

SEARCH_RADII_M = (750, 1500, 3000, 6000, 10000)
MIN_COMPARABLES = 10
AREA_RATIO = 1.35
_CELL_LAT_DEGREES = 0.01
_CELL_LON_DEGREES = 0.015
_METRES_PER_DEGREE = 111_320


@dataclass(frozen=True)
class ComparableRow:
    id: int
    group_id: int
    offer_type: Optional[str]
    object_type: Optional[str]
    latitude: float
    longitude: float
    area: float
    price_per_m2: float


@dataclass(frozen=True)
class ComparableStats:
    count: int
    radius_m: int
    median_price_per_m2: int
    p25_price_per_m2: int
    p75_price_per_m2: int

    def difference_pct(self, price_per_m2: Optional[float]) -> Optional[float]:
        if not price_per_m2 or not self.median_price_per_m2:
            return None
        return round((price_per_m2 / self.median_price_per_m2 - 1) * 100, 1)


class ComparablesIndex:
    def __init__(self, rows: Iterable[ComparableRow], min_comparables: int = MIN_COMPARABLES):
        self._min_comparables = min_comparables
        cells: dict[tuple, list[ComparableRow]] = defaultdict(list)
        for row in rows:
            if row.area and row.price_per_m2 and row.latitude and row.longitude:
                cells[(_kind(row), *_cell_of(row.latitude, row.longitude))].append(row)
        self._cells = {}
        for key, members in cells.items():
            members.sort(key=lambda member: member.area)
            self._cells[key] = (members, [member.area for member in members])

    def stats_for(self, target: ComparableRow) -> Optional[ComparableStats]:
        if not (target.area and target.latitude and target.longitude):
            return None
        kind = _kind(target)
        low_area, high_area = target.area / AREA_RATIO, target.area * AREA_RATIO
        seen_cells: set[tuple] = set()
        nearest_by_group: dict[int, tuple[float, float]] = {}

        for radius in SEARCH_RADII_M:
            for cell in _cells_within(target.latitude, target.longitude, radius):
                if cell in seen_cells:
                    continue
                seen_cells.add(cell)
                bucket = self._cells.get((kind, *cell))
                if bucket is None:
                    continue
                members, areas = bucket
                for member in members[bisect_left(areas, low_area):bisect_right(areas, high_area)]:
                    if member.group_id == target.group_id:
                        continue
                    distance = _distance_m(target.latitude, target.longitude, member.latitude, member.longitude)
                    known = nearest_by_group.get(member.group_id)
                    if known is None or distance < known[0]:
                        nearest_by_group[member.group_id] = (distance, member.price_per_m2)

            within = [price for distance, price in nearest_by_group.values() if distance <= radius]
            if len(within) >= self._min_comparables:
                return _stats(within, radius)
        return None


def _stats(prices: list[float], radius: int) -> ComparableStats:
    quartiles = quantiles(prices, n=4, method="inclusive")
    return ComparableStats(
        count=len(prices),
        radius_m=radius,
        median_price_per_m2=round(median(prices)),
        p25_price_per_m2=round(quartiles[0]),
        p75_price_per_m2=round(quartiles[2]),
    )


def _kind(row: ComparableRow) -> tuple:
    return (row.offer_type, row.object_type)


def _cell_of(latitude: float, longitude: float) -> tuple[int, int]:
    return int(latitude // _CELL_LAT_DEGREES), int(longitude // _CELL_LON_DEGREES)


def _cells_within(latitude: float, longitude: float, radius_m: float) -> list[tuple[int, int]]:
    lat_span = math.ceil(radius_m / (_METRES_PER_DEGREE * _CELL_LAT_DEGREES))
    lon_metres = _METRES_PER_DEGREE * _CELL_LON_DEGREES * math.cos(math.radians(latitude))
    lon_span = math.ceil(radius_m / lon_metres)
    lat_cell, lon_cell = _cell_of(latitude, longitude)
    return [
        (lat_cell + d_lat, lon_cell + d_lon)
        for d_lat in range(-lat_span, lat_span + 1)
        for d_lon in range(-lon_span, lon_span + 1)
    ]


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    mean_lat = math.radians((lat1 + lat2) / 2)
    d_lat = (lat2 - lat1) * _METRES_PER_DEGREE
    d_lon = (lon2 - lon1) * _METRES_PER_DEGREE * math.cos(mean_lat)
    return math.hypot(d_lat, d_lon)
