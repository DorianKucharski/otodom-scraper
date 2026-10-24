from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from .comparables import AREA_RATIO, ComparableStats, stats_of
from .geo import distance_m
from .street_checks import street_key

STREET_RADIUS_M = 1500
MIN_STREET_SALES = 3

_RCN_STREET = re.compile(r"UL:([^;]+)")


@dataclass(frozen=True, slots=True)
class StreetSale:
    key: str
    market: Optional[str]
    latitude: float
    longitude: float
    area: float
    price_per_m2: float


def rcn_street_key(address: Optional[str]) -> Optional[str]:
    match = _RCN_STREET.search(address or "")
    return street_key(match.group(1)) if match else None


class StreetSalesIndex:
    def __init__(self, sales: list[StreetSale]):
        self._by_key: dict[str, list[StreetSale]] = defaultdict(list)
        for sale in sales:
            self._by_key[sale.key].append(sale)

    def stats_for(self, key: Optional[str], latitude: Optional[float], longitude: Optional[float],
                  area: Optional[float], market: Optional[str]) -> Optional[ComparableStats]:
        if not key or not area or latitude is None or longitude is None:
            return None
        nearby = [
            sale for sale in self._by_key.get(key, ())
            if max(sale.area, area) / min(sale.area, area) <= AREA_RATIO
            and distance_m(latitude, longitude, sale.latitude, sale.longitude) <= STREET_RADIUS_M
        ]
        same_market = [sale for sale in nearby if market and sale.market == market]
        for candidates in (same_market, nearby):
            if len(candidates) >= MIN_STREET_SALES:
                return stats_of([sale.price_per_m2 for sale in candidates], STREET_RADIUS_M)
        return None
