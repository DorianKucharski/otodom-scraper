from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Optional

from psycopg2.extras import execute_values
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from .derived_tables import ensure_table
from .geo import METRES_PER_DEGREE
from .models import NuisanceFeature

logger = logging.getLogger(__name__)

EXPRESSWAY = "expressway"
RAILWAY = "railway"
RUNWAY = "runway"

NEAR_EXPRESSWAY = "near_expressway"
NEAR_RAILWAY = "near_railway"
UNDER_APPROACH = "under_approach"

EXPRESSWAY_NEAR_M = 300
RAILWAY_NEAR_M = 150
MIN_RUNWAY_M = 1800
APPROACH_LENGTH_M = 8000
APPROACH_HALF_WIDTH_M = 400
APPROACH_WIDENING = 0.05

_UNPAVED = {"grass", "dirt", "ground", "gravel", "sand", "earth", "unpaved"}
_EXPRESSWAY_HIGHWAYS = {"motorway", "trunk", "motorway_link", "trunk_link"}


_INSERT = """
INSERT INTO nuisance_features (osm_id, kind, label, geom, loaded_at)
VALUES %s
"""

_NEAREST = """
LEFT JOIN LATERAL (
    SELECT nearest.distance_m, nearest.label
    FROM (
        SELECT round(ST_Distance(f.geom::geography, a.location_point::geography))::int AS distance_m, f.label
        FROM nuisance_features f
        WHERE f.kind = '{kind}' AND f.geom && ST_Expand(a.location_point, {degrees})
        ORDER BY f.geom <-> a.location_point
        LIMIT 3
    ) nearest
    ORDER BY nearest.distance_m
    LIMIT 1
) {alias} ON {alias}.distance_m <= {metres}
"""
_CHECKS = text(
    """
SELECT a.id,
       ST_Y(a.location_point) AS latitude,
       ST_X(a.location_point) AS longitude,
       e.distance_m           AS expressway_m,
       e.label                AS expressway_label,
       r.distance_m           AS railway_m
FROM ads a
"""
    + _NEAREST.format(kind="expressway", degrees=0.02, alias="e", metres=1000)
    + _NEAREST.format(kind="railway", degrees=0.01, alias="r", metres=500)
    + """
WHERE a.location_point && (SELECT ST_Expand(ST_Extent(geom), 0.02) FROM nuisance_features)
"""
)

_RUNWAYS = text("SELECT label, ST_AsText(geom) FROM nuisance_features WHERE kind = 'runway'")


@dataclass(frozen=True, slots=True)
class Feature:
    osm_id: int
    kind: str
    label: Optional[str]
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class NuisanceCheck:
    expressway_m: Optional[int] = None
    expressway_label: Optional[str] = None
    railway_m: Optional[int] = None
    approach_m: Optional[int] = None
    approach_label: Optional[str] = None


@dataclass
class NuisanceVerdict:
    flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def overpass_query(south: float, west: float, north: float, east: float) -> str:
    box = f"({south:.5f},{west:.5f},{north:.5f},{east:.5f})"
    return (
        "[out:json][timeout:280];("
        f'way["highway"~"^(motorway|trunk|motorway_link|trunk_link)$"]{box};'
        f'way["railway"="rail"]["usage"~"^(main|branch)$"]{box};'
        f'way["aeroway"="runway"]{box};'
        ");out geom tags;"
    )


def features_from_overpass(payload: dict) -> list[Feature]:
    features = []
    for element in payload.get("elements") or []:
        tags = element.get("tags") or {}
        points = tuple((point["lat"], point["lon"]) for point in element.get("geometry") or [])
        if len(points) < 2 or tags.get("tunnel") not in (None, "no"):
            continue
        kind = _kind_of(tags, points)
        if kind is None:
            continue
        label = road_label(tags) if kind == EXPRESSWAY else tags.get("name") or tags.get("ref")
        features.append(Feature(osm_id=element["id"], kind=kind, label=label, points=points))
    return features


def road_label(tags: dict) -> Optional[str]:
    refs = []
    for ref in (tags.get("ref") or "").split(";"):
        ref = ref.strip().replace(" ", "")
        if not ref:
            continue
        ref = f"DK{ref}" if ref.isdigit() else ref
        if ref not in refs:
            refs.append(ref)
    return "/".join(refs) or tags.get("name")


def _kind_of(tags: dict, points: tuple[tuple[float, float], ...]) -> Optional[str]:
    if tags.get("aeroway") == "runway":
        if tags.get("surface") in _UNPAVED or _length_m(points) < MIN_RUNWAY_M:
            return None
        return RUNWAY
    if tags.get("highway") in _EXPRESSWAY_HIGHWAYS:
        return EXPRESSWAY
    if tags.get("railway") == "rail":
        return RAILWAY
    return None


def _length_m(points: tuple[tuple[float, float], ...]) -> float:
    return sum(_metres(points[index], points[index + 1]) for index in range(len(points) - 1))


def _metres(start: tuple[float, float], end: tuple[float, float]) -> float:
    cos_lat = math.cos(math.radians((start[0] + end[0]) / 2))
    return math.hypot((end[0] - start[0]) * METRES_PER_DEGREE, (end[1] - start[1]) * METRES_PER_DEGREE * cos_lat)


def store_nuisances(engine: Engine, features: list[Feature], now: Optional[datetime] = None) -> int:
    if not features:
        raise ValueError("Overpass returned no roads, railways or runways, keeping the previous ones")
    now = now or datetime.now()
    ensure_table(engine, NuisanceFeature.__table__)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM nuisance_features"))
        execute_values(
            connection.connection.cursor(), _INSERT, [_row(feature, now) for feature in features],
            template="(%s, %s, %s, ST_GeomFromText(%s, 4326), %s)",
        )
    return len(features)


def _row(feature: Feature, now: datetime) -> tuple:
    line = ", ".join(f"{longitude} {latitude}" for latitude, longitude in feature.points)
    return feature.osm_id, feature.kind, feature.label, f"LINESTRING({line})", now


class ApproachPaths:
    def __init__(self, runways: Iterable[tuple[Optional[str], tuple[tuple[float, float], ...]]]):
        self._ends = []
        for label, points in runways:
            first, last = points[0], points[-1]
            self._ends.append((label, last, _unit(first, last)))
            self._ends.append((label, first, _unit(last, first)))

    def distance_beyond_runway(self, latitude: float, longitude: float) -> Optional[tuple[int, Optional[str]]]:
        best = None
        for label, end, (east, north) in self._ends:
            cos_lat = math.cos(math.radians(end[0]))
            dx = (longitude - end[1]) * METRES_PER_DEGREE * cos_lat
            dy = (latitude - end[0]) * METRES_PER_DEGREE
            along = dx * east + dy * north
            if along <= 0 or along > APPROACH_LENGTH_M:
                continue
            if abs(dx * north - dy * east) > APPROACH_HALF_WIDTH_M + along * APPROACH_WIDENING:
                continue
            if best is None or along < best[0]:
                best = (round(along), label)
        return best


def _unit(start: tuple[float, float], end: tuple[float, float]) -> tuple[float, float]:
    cos_lat = math.cos(math.radians((start[0] + end[0]) / 2))
    east = (end[1] - start[1]) * METRES_PER_DEGREE * cos_lat
    north = (end[0] - start[0]) * METRES_PER_DEGREE
    length = math.hypot(east, north) or 1.0
    return east / length, north / length


def load_nuisance_checks(connection: Connection) -> dict[int, NuisanceCheck]:
    if not connection.execute(text("SELECT to_regclass('nuisance_features') IS NOT NULL")).scalar():
        return {}
    approaches = ApproachPaths(
        (label, _points_of(wkt)) for label, wkt in connection.execute(_RUNWAYS)
    )
    checks = {}
    for row in connection.execute(_CHECKS):
        approach = approaches.distance_beyond_runway(row.latitude, row.longitude)
        if row.expressway_m is None and row.railway_m is None and approach is None:
            continue
        checks[row.id] = NuisanceCheck(
            expressway_m=row.expressway_m,
            expressway_label=row.expressway_label,
            railway_m=row.railway_m,
            approach_m=approach[0] if approach else None,
            approach_label=approach[1] if approach else None,
        )
    return checks


def _points_of(wkt: str) -> tuple[tuple[float, float], ...]:
    inner = wkt[wkt.index("(") + 1:wkt.rindex(")")]
    pairs = (pair.split() for pair in inner.split(","))
    return tuple((float(latitude), float(longitude)) for longitude, latitude in pairs)


def nuisance_verdict(check: Optional[NuisanceCheck]) -> NuisanceVerdict:
    verdict = NuisanceVerdict()
    if check is None:
        return verdict
    if check.expressway_m is not None and check.expressway_m <= EXPRESSWAY_NEAR_M:
        road = f"droga {check.expressway_label}" if check.expressway_label else "droga szybkiego ruchu"
        verdict.flags.append(NEAR_EXPRESSWAY)
        verdict.notes.append(f"{road} ok. {check.expressway_m} m od pinezki")
    if check.railway_m is not None and check.railway_m <= RAILWAY_NEAR_M:
        verdict.flags.append(NEAR_RAILWAY)
        verdict.notes.append(f"linia kolejowa ok. {check.railway_m} m od pinezki")
    if check.approach_m is not None:
        verdict.flags.append(UNDER_APPROACH)
        kilometres = f"{check.approach_m / 1000:.1f}".replace(".", ",")
        verdict.notes.append(f"na przedłużeniu pasa startowego lotniska, ok. {kilometres} km od jego końca")
    return verdict
