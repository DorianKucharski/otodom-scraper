from __future__ import annotations

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select

from .models import Ad, AdminArea

OTODOM_RADII_KM = (0, 5, 10, 15, 25, 50, 75)


def within_city_radius(city: str, radius_km: int):
    city_area = (
        select(cast(AdminArea.geom, Geography))
        .where(AdminArea.level == "city", func.lower(AdminArea.city_name) == city.lower())
        .limit(1)
        .scalar_subquery()
    )
    return func.ST_DWithin(cast(Ad.location_point, Geography), city_area, radius_km * 1000)
