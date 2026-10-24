from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from psycopg2.extras import execute_values
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from .derived_tables import ensure_table
from .models import OsmStreet, is_masked
from .search_url import normalize_name

PIN_FAR_FROM_STREET = "pin_far_from_street"
FAR_FROM_STREET_M = 1000
BEYOND_COVERAGE_M = 15000

_STREET_PREFIX = re.compile(r"^(?:ul|ulica|al|aleja|aleje|pl|plac|rondo|skwer|bulwar)\.?\s+", re.IGNORECASE)
_NOT_A_STREET = re.compile(r"^(?:os|osiedle|rynek)\b", re.IGNORECASE)

_INSERT = "INSERT INTO osm_streets (osm_id, name, key, geom, loaded_at) VALUES %s"

_ADS_WITH_STREETS = text("""
SELECT a.id, a.street, ST_X(a.location_point) AS longitude, ST_Y(a.location_point) AS latitude
FROM ads a
WHERE a.street IS NOT NULL
  AND EXISTS (SELECT 1 FROM osm_streets nearby WHERE nearby.geom && ST_Expand(a.location_point, 0.003))
  AND EXISTS (
      SELECT 1 FROM admin_areas town
      WHERE town.level = 'city' AND town.geom && a.location_point AND ST_Intersects(town.geom, a.location_point)
  )
""")

_DISTANCES = """
SELECT p.id, round(min(ST_Distance(s.geom::geography, ST_SetSRID(ST_MakePoint(p.longitude, p.latitude), 4326)::geography)))::int
FROM (VALUES %s) AS p (id, key, longitude, latitude)
JOIN osm_streets s ON s.key = p.key
GROUP BY p.id
"""


@dataclass(frozen=True, slots=True)
class StreetCheck:
    street: str
    distance_m: int


def street_key(street: Optional[str]) -> Optional[str]:
    if not street or is_masked(street):
        return None
    street = street.strip()
    if _NOT_A_STREET.match(street):
        return None
    street = _STREET_PREFIX.sub("", street)
    plain = normalize_name(street)
    words = [word for word in re.sub(r"[^a-z0-9]+", " ", plain).split() if len(word) > 2 and not word.isdigit()]
    return words[-1] if words else None


def streets_from_overpass(payload: dict) -> list[tuple[int, str, str, tuple[tuple[float, float], ...]]]:
    streets = []
    for element in payload.get("elements") or []:
        name = (element.get("tags") or {}).get("name")
        key = street_key(name)
        points = tuple((point["lat"], point["lon"]) for point in element.get("geometry") or [])
        if key and len(points) >= 2:
            streets.append((element["id"], name, key, points))
    return streets


def overpass_streets_query(south: float, west: float, north: float, east: float) -> str:
    return f'[out:json][timeout:280];way["highway"]["name"]({south:.5f},{west:.5f},{north:.5f},{east:.5f});out geom tags;'


def store_streets(engine: Engine, streets: list, now: Optional[datetime] = None) -> int:
    if not streets:
        raise ValueError("Overpass returned no streets, keeping the previous ones")
    now = now or datetime.now()
    ensure_table(engine, OsmStreet.__table__)
    rows = [
        (osm_id, name, key, "LINESTRING(" + ", ".join(f"{lon} {lat}" for lat, lon in points) + ")", now)
        for osm_id, name, key, points in streets
    ]
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM osm_streets"))
        execute_values(
            connection.connection.cursor(), _INSERT, rows, template="(%s, %s, %s, ST_GeomFromText(%s, 4326), %s)",
        )
    return len(rows)


def load_street_checks(connection: Connection) -> dict[int, StreetCheck]:
    if not connection.execute(text("SELECT to_regclass('osm_streets') IS NOT NULL")).scalar():
        return {}
    streets: dict[int, str] = {}
    points = []
    for row in connection.execute(_ADS_WITH_STREETS):
        key = street_key(row.street)
        if key:
            streets[row.id] = row.street
            points.append((row.id, key, row.longitude, row.latitude))
    if not points:
        return {}
    cursor = connection.connection.cursor()
    distances = execute_values(cursor, _DISTANCES, points, page_size=5000, fetch=True)
    return {ad_id: StreetCheck(street=streets[ad_id], distance_m=distance) for ad_id, distance in distances}


def street_verdict(check: Optional[StreetCheck], verdict) -> bool:
    if check is None or not FAR_FROM_STREET_M <= check.distance_m <= BEYOND_COVERAGE_M:
        return False
    kilometres = f"{check.distance_m / 1000:.1f}".replace(".", ",")
    verdict.add(
        PIN_FAR_FROM_STREET,
        f"Ulica z ogłoszenia ({check.street}) jest ok. {kilometres} km od pinezki. Pinezka jest pewnie przesunięta, "
        f"więc odległości od granicy, dróg i kolei mogą być nieprawdziwe.",
    )
    return True
