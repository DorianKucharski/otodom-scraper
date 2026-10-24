from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import requests
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT_SECONDS = 300
OSM_TABLES = ("nuisance_features", "osm_streets")

_AREA_BOUNDS = text("""
SELECT ST_YMin(b), ST_XMin(b), ST_YMax(b), ST_XMax(b)
FROM (
    SELECT ST_Extent(ST_Buffer(geom::geography, :margin)::geometry) AS b
    FROM admin_areas
    WHERE level = 'city' AND city_name = ANY(:cities)
) bounds
""")


def area_bounds(engine: Engine, cities: list[str], margin_m: int) -> tuple[float, float, float, float]:
    with engine.connect() as connection:
        bounds = connection.execute(_AREA_BOUNDS, {"cities": cities, "margin": margin_m}).one()
    if bounds[0] is None:
        raise ValueError(f"No boundaries loaded for {cities}, run load_boundaries.py first")
    return tuple(bounds)


def fetch(query: str, http: Optional[requests.Session] = None) -> dict:
    response = (http or requests.Session()).post(
        OVERPASS_URL, data={"data": query}, timeout=OVERPASS_TIMEOUT_SECONDS, headers={"User-Agent": "otodom-scraper"},
    )
    response.raise_for_status()
    return response.json()


def osm_due(connection: Connection, refresh_days: float, now: Optional[datetime] = None) -> bool:
    now = now or datetime.now()
    for table in OSM_TABLES:
        if not connection.execute(text("SELECT to_regclass(:table) IS NOT NULL"), {"table": table}).scalar():
            return True
        last = connection.execute(text(f"SELECT max(loaded_at) FROM {table}")).scalar()
        if last is None or now - last >= timedelta(days=refresh_days):
            return True
    return False
