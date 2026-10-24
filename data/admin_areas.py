from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterator, Optional

import requests
from lxml import etree
from sqlalchemy import text
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)

PRG_WFS_URL = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries"
CITY_LAYER = "ms:A04_Granice_miast"
GMINA_LAYER = "ms:A03_Granice_gmin"
PAGE_SIZE = 200
SIMPLIFY_TOLERANCE_M = 2.0

_NAMESPACES = {
    "wfs": "http://www.opengis.net/wfs/2.0",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
    "gml": "http://www.opengis.net/gml/3.2",
}
_CITY_NAME_SUFFIXES = (" - gmina miejska", " - miasto", " - dzielnica", " - delegatura")
_SPLIT_CITY_SUFFIXES = ("_8", "_9")


@dataclass(frozen=True)
class AdminAreaPart:
    code: str
    name: str
    gml: str


def city_key(code: str) -> str:
    return code[:4] if code.endswith(_SPLIT_CITY_SUFFIXES) else code


def city_name_of(name: str) -> str:
    for suffix in _CITY_NAME_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def iter_layer(layer: str, session: Optional[requests.Session] = None, page_size: int = PAGE_SIZE) -> Iterator[AdminAreaPart]:
    http = session or requests.Session()
    start = 0
    while True:
        response = http.get(PRG_WFS_URL, params={
            "SERVICE": "WFS",
            "VERSION": "2.0.0",
            "REQUEST": "GetFeature",
            "TYPENAMES": layer,
            "COUNT": page_size,
            "STARTINDEX": start,
        }, timeout=300)
        response.raise_for_status()
        parts = list(parse_parts(response.content))
        yield from parts
        if len(parts) < page_size:
            return
        start += page_size


def parse_parts(document: bytes) -> Iterator[AdminAreaPart]:
    root = etree.fromstring(document)
    for member in root.iterfind("wfs:member", _NAMESPACES):
        feature = member[0]
        code = feature.findtext("ms:JPT_KOD_JE", namespaces=_NAMESPACES)
        name = feature.findtext("ms:JPT_NAZWA_", namespaces=_NAMESPACES)
        geometry = feature.find("ms:msGeometry", _NAMESPACES)
        if not code or not name or geometry is None or len(geometry) == 0:
            continue
        yield AdminAreaPart(code=code, name=name, gml=etree.tostring(geometry[0], encoding="unicode"))


_CREATE_STAGING = """
CREATE TEMP TABLE admin_area_parts (
    code text,
    level text,
    name text,
    geom geometry
) ON COMMIT DROP
"""

_INSERT_PART = """
INSERT INTO admin_area_parts (code, level, name, geom)
VALUES (:code, :level, :name, ST_SimplifyPreserveTopology(ST_GeomFromGML(:gml), :tolerance))
"""

_REPLACE_AREAS = """
DELETE FROM admin_areas;

INSERT INTO admin_areas (code, level, name, city_name, province_code, geom)
SELECT code, 'gmina', name, NULL, left(code, 2), ST_Multi(ST_Transform(ST_SetSRID(ST_Union(geom), 2180), 4326))
FROM admin_area_parts
WHERE level = 'gmina'
GROUP BY code, name;

INSERT INTO admin_areas (code, level, name, city_name, province_code, geom)
SELECT p.city_code,
       'city',
       coalesce(g.name, min(p.city_name)),
       coalesce(g.name, min(p.city_name)),
       left(p.city_code, 2),
       ST_Multi(ST_Transform(ST_SetSRID(ST_Union(p.geom), 2180), 4326))
FROM (
    SELECT CASE WHEN code LIKE '%\\_8' OR code LIKE '%\\_9' THEN left(code, 4) ELSE code END AS city_code,
           name AS city_name,
           geom
    FROM admin_area_parts
    WHERE level = 'city'
) p
LEFT JOIN admin_area_parts g
       ON g.level = 'gmina' AND length(p.city_code) = 4 AND g.code = p.city_code || '011'
GROUP BY p.city_code, g.name;
"""


def load_admin_areas(connection: Connection, session: Optional[requests.Session] = None) -> dict[str, int]:
    connection.execute(text(_CREATE_STAGING))
    counts = {}
    for level, layer in (("gmina", GMINA_LAYER), ("city", CITY_LAYER)):
        count = 0
        for part in iter_layer(layer, session):
            name = city_name_of(part.name) if level == "city" else part.name
            connection.execute(text(_INSERT_PART), {
                "code": part.code,
                "level": level,
                "name": name,
                "gml": part.gml,
                "tolerance": SIMPLIFY_TOLERANCE_M,
            })
            count += 1
        counts[level] = count
        logger.info("Loaded %d %s boundary parts from PRG", count, level)
    for statement in _REPLACE_AREAS.split(";\n\n"):
        if statement.strip():
            connection.execute(text(statement))
    return counts
