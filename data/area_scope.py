from __future__ import annotations

from geoalchemy2 import Geography, Geometry
from sqlalchemy import cast, func, or_, select

from .models import Ad, AdminArea, City
from .search_url import normalize_name

OTODOM_RADII_KM = (0, 5, 10, 15, 25, 50, 75)


def within_city_radius(city: str, radius_km: int):
    slug = (normalize_name(city) or "").replace(" ", "-")
    name_of_slug = select(func.lower(City.name)).where(City.code == slug).limit(1).scalar_subquery()
    surroundings = (
        select(cast(func.ST_Buffer(cast(AdminArea.geom, Geography), radius_km * 1000), Geometry))
        .where(AdminArea.level == "city", or_(
            func.lower(AdminArea.city_name) == city.lower(), func.lower(AdminArea.city_name) == name_of_slug,
        ))
        .limit(1)
        .scalar_subquery()
    )
    return func.ST_Intersects(Ad.location_point, surroundings)
