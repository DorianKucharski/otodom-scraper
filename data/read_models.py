from __future__ import annotations

from sqlalchemy import column, table

ad_all_features = table(
    "ad_all_features",
    column("ad_id"),
    column("feature_group"),
    column("value"),
)

district_price_stats = table(
    "district_price_stats",
    column("city_id"),
    column("district_id"),
    column("is_city_level"),
    column("offer_type"),
    column("object_type"),
    column("ad_count"),
    column("median_price_per_m2"),
    column("p25_price_per_m2"),
    column("p75_price_per_m2"),
    column("median_price"),
    column("median_area"),
)
