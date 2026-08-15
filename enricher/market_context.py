from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from data.models import Ad

_STATS_QUERY = text("""
SELECT city_id,
       district_id,
       is_city_level,
       offer_type,
       object_type,
       ad_count,
       round(median_price_per_m2)  AS median_price_per_m2,
       round(p25_price_per_m2)     AS p25_price_per_m2,
       round(p75_price_per_m2)     AS p75_price_per_m2
FROM district_price_stats
WHERE ad_count >= :min_ad_count
""")

MIN_ADS_FOR_RELIABLE_STATS = 8


@dataclass(frozen=True)
class DistrictPriceStats:
    ad_count: int
    median_price_per_m2: int
    p25_price_per_m2: int
    p75_price_per_m2: int
    is_city_level: bool

    def position_label(self, price_per_m2: Optional[int]) -> str:
        if price_per_m2 is None:
            return "brak ceny za metr w ogłoszeniu"

        scope = "w mieście" if self.is_city_level else "w dzielnicy"
        difference = round((price_per_m2 / self.median_price_per_m2 - 1) * 100)
        if price_per_m2 < self.p25_price_per_m2:
            position = f"w najtańszej ćwiartce rynku {scope}"
        elif price_per_m2 > self.p75_price_per_m2:
            position = f"w najdroższej ćwiartce rynku {scope}"
        else:
            position = f"w środkowej połowie rynku {scope}"

        relation = "powyżej" if difference > 0 else "poniżej"
        return f"{price_per_m2} zł za metr, {abs(difference)}% {relation} mediany, {position}"


@dataclass(frozen=True)
class MarketContext:
    _stats_by_key: Mapping[tuple, DistrictPriceStats]

    def stats_for(self, ad: Ad) -> Optional[DistrictPriceStats]:
        district_key = (ad.city_id, ad.district_id, False, ad.offer_type, ad.object_type)
        city_key = (ad.city_id, None, True, ad.offer_type, ad.object_type)
        return self._stats_by_key.get(district_key) or self._stats_by_key.get(city_key)

    @classmethod
    def load(cls, session: Session, min_ad_count: int = MIN_ADS_FOR_RELIABLE_STATS) -> "MarketContext":
        rows = session.execute(_STATS_QUERY, {"min_ad_count": min_ad_count}).mappings().all()
        return cls(_stats_by_key={
            (
                row["city_id"],
                row["district_id"],
                bool(row["is_city_level"]),
                row["offer_type"],
                row["object_type"],
            ): DistrictPriceStats(
                ad_count=row["ad_count"],
                median_price_per_m2=int(row["median_price_per_m2"]),
                p25_price_per_m2=int(row["p25_price_per_m2"]),
                p75_price_per_m2=int(row["p75_price_per_m2"]),
                is_city_level=bool(row["is_city_level"]),
            )
            for row in rows
            if row["median_price_per_m2"] is not None
        })
