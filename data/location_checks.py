from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

NEAR_BORDER_M = 1000
NEAR_BORDER_MIN_CITY_KM2 = 80
OUTSIDE_TOLERANCE_M = 100
TEXT_CHECK_BORDER_M = 2500
NEARBY_PLACE_RADIUS_M = 6000
MIN_ADS_FOR_PLACE_CENTRE = 3

PIN_OUTSIDE_CITY = "pin_outside_city"
NEAR_CITY_BORDER = "near_city_border"
OTHER_PLACE_IN_TEXT = "other_place_in_text"
BORDER_IN_TEXT = "border_in_text"
LINEAGE_CITY_MISMATCH = "lineage_city_mismatch"
CLAIMED_DISTRICT_OF_OTHER_CITY = "district_of_other_city"

PROVINCE_TERYT = {
    "dolnoslaskie": "02", "kujawsko-pomorskie": "04", "lubelskie": "06", "lubuskie": "08",
    "lodzkie": "10", "malopolskie": "12", "mazowieckie": "14", "opolskie": "16",
    "podkarpackie": "18", "podlaskie": "20", "pomorskie": "22", "slaskie": "24",
    "swietokrzyskie": "26", "warminsko-mazurskie": "28", "wielkopolskie": "30", "zachodniopomorskie": "32",
}

_PROVINCE_VALUES = ", ".join(f"('{code}', '{teryt}')" for code, teryt in PROVINCE_TERYT.items())

_CITY_BOUNDS = """
CREATE TEMP TABLE city_bounds ON COMMIT DROP AS
SELECT code, city_name, province_code, geom, ST_Transform(ST_Boundary(geom), 2180) AS boundary,
       ST_Area(geom::geography) / 1e6 AS area_km2
FROM admin_areas
WHERE level = 'city'
"""

_CITY_BOUNDS_INDEX = "CREATE INDEX ON city_bounds USING gist (geom)"

_PIN_CHECKS = f"""
WITH province_teryt(code, teryt) AS (VALUES {_PROVINCE_VALUES})
SELECT a.id,
       claimed.code IS NOT NULL                                              AS claimed_is_town,
       claimed.area_km2                                                      AS claimed_area_km2,
       ST_Contains(claimed.geom, a.location_point)                           AS inside_claimed,
       round(ST_Distance(ST_Transform(a.location_point, 2180), claimed.boundary)) AS border_m,
       pin_city.city_name                                                    AS pin_city_name,
       pin_gmina.name                                                        AS pin_gmina_name
FROM ads a
JOIN cities c ON c.id = a.city_id
LEFT JOIN provinces p ON p.id = a.province_id
LEFT JOIN province_teryt pt ON pt.code = p.code
LEFT JOIN LATERAL (
    SELECT b.code, b.geom, b.boundary, b.area_km2
    FROM city_bounds b
    WHERE b.city_name = c.name
      AND (pt.teryt IS NULL OR b.province_code = pt.teryt)
    ORDER BY b.geom <-> a.location_point
    LIMIT 1
) claimed ON true
LEFT JOIN LATERAL (
    SELECT b.city_name FROM city_bounds b WHERE ST_Contains(b.geom, a.location_point) LIMIT 1
) pin_city ON true
LEFT JOIN LATERAL (
    SELECT g.name FROM admin_areas g WHERE g.level = 'gmina' AND ST_Contains(g.geom, a.location_point) LIMIT 1
) pin_gmina ON true
WHERE a.location_point IS NOT NULL
  AND a.latitude <> 0
"""

_PLACE_CENTRES = """
SELECT a.city_id, c.name, avg(a.latitude)::float AS latitude, avg(a.longitude)::float AS longitude, count(*) AS ads
FROM ads a
JOIN cities c ON c.id = a.city_id
WHERE a.latitude <> 0 AND a.location_point IS NOT NULL
GROUP BY a.city_id, c.name
HAVING count(*) >= :min_ads
"""

_NAME = r"[A-ZŁŚŻŹĆ][\wąćęłńóśźż]+(?:[ -][A-ZŁŚŻŹĆ][\wąćęłńóśźż]+)?"
_DISTRICT_NAMES = """
SELECT DISTINCT c.name AS city_name, d.name AS district_name
FROM ads a
JOIN cities c ON c.id = a.city_id
JOIN districts d ON d.id = a.district_id
"""

_BORDER_PHRASES = (
    re.compile(rf"\b(?:na|przy|tuż przy|tuż za|za)\s+granic\w*(?:\s+(?:z|ze|miasta|gminy))?\s+(?P<name>{_NAME})"),
    re.compile(rf"\b\d+(?:[.,]\d+)?\s*km\s+od\s+granic\w*(?:\s+(?:miasta\s+)?(?P<name>{_NAME}))?", re.IGNORECASE),
    re.compile(r"\bpod\s+(?P<name>Krakowem|Warszawą|Wrocławiem|Poznaniem|Gdańskiem|Łodzią|Lublinem|Katowicami|Gdynią|Szczecinem|Bydgoszczą|Toruniem|Rzeszowem|Białymstokiem|Olsztynem|Kielcami|Opolem)\b"),
    re.compile(rf"\b(?:gmin(?:a|ie|y|ą)|gm\.)\s+(?P<name>{_NAME})"),
)
_FOREIGN_BORDERS = ("Czech", "Niemc", "Słowac", "Ukrain", "Litw", "Białoru", "Rosj", "Polsk")
_TRAVEL_BEFORE = re.compile(
    r"(?:\bdo|\bod|\bkoło|\bpod|\bblisko|\bniedaleko|\bobok|\bCH|\bcentrum|\bstacj\w*|\bpętl\w*|\bwęz\w*|\bkierunku|\btrasie|\bdrodze|\bdojazd\w*|\bulic\w*|\bul\.)\s*$",
    re.IGNORECASE,
)
_TRAVEL_AFTER = re.compile(r"^[\s\w,()–-]{0,25}?\d+\s*(?:km|min)", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_METRES_PER_DEGREE = 111_320


@dataclass(frozen=True)
class PinCheck:
    ad_id: int
    claimed_is_town: bool
    claimed_area_km2: Optional[float]
    inside_claimed: Optional[bool]
    border_m: Optional[int]
    pin_city_name: Optional[str]
    pin_gmina_name: Optional[str]


@dataclass(frozen=True)
class PlaceCentre:
    city_id: int
    name: str
    latitude: float
    longitude: float


@dataclass
class LocationVerdict:
    flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add(self, flag: str, note: str):
        if flag not in self.flags:
            self.flags.append(flag)
        self.notes.append(note)


def load_pin_checks(connection: Connection) -> dict[int, PinCheck]:
    connection.execute(text(_CITY_BOUNDS))
    connection.execute(text(_CITY_BOUNDS_INDEX))
    connection.execute(text("ANALYZE city_bounds"))
    return {
        row.id: PinCheck(
            ad_id=row.id,
            claimed_is_town=bool(row.claimed_is_town),
            claimed_area_km2=float(row.claimed_area_km2) if row.claimed_area_km2 is not None else None,
            inside_claimed=row.inside_claimed,
            border_m=int(row.border_m) if row.border_m is not None else None,
            pin_city_name=row.pin_city_name,
            pin_gmina_name=row.pin_gmina_name,
        )
        for row in connection.execute(text(_PIN_CHECKS))
    }


def load_place_centres(connection: Connection) -> list[PlaceCentre]:
    return [
        PlaceCentre(city_id=row.city_id, name=row.name, latitude=row.latitude, longitude=row.longitude)
        for row in connection.execute(text(_PLACE_CENTRES), {"min_ads": MIN_ADS_FOR_PLACE_CENTRE})
    ]


def load_district_names(connection: Connection) -> dict[str, set[str]]:
    names: dict[str, set[str]] = {}
    for row in connection.execute(text(_DISTRICT_NAMES)):
        names.setdefault(row.city_name, set()).add(row.district_name)
    return names


def pin_verdict(claimed_city: Optional[str], check: Optional[PinCheck], verdict: LocationVerdict) -> bool:
    if check is None or not check.claimed_is_town:
        return False
    if not check.inside_claimed and (check.border_m or 0) > OUTSIDE_TOLERANCE_M:
        actual = check.pin_city_name or (f"gmina {check.pin_gmina_name}" if check.pin_gmina_name else "poza miastem")
        verdict.add(
            PIN_OUTSIDE_CITY,
            f"Pinezka leży poza granicami miasta {claimed_city} ({check.border_m} m od granicy), w: {actual}.",
        )
        return True
    if (
        check.inside_claimed and check.border_m is not None and check.border_m < NEAR_BORDER_M
        and (check.claimed_area_km2 or 0) >= NEAR_BORDER_MIN_CITY_KM2
    ):
        verdict.add(
            NEAR_CITY_BORDER,
            f"Pinezka jest {check.border_m} m od granicy miasta {claimed_city}. Ogłoszeniodawcy często przypinają "
            f"oferty spoza miasta do ostatniej ulicy po jego stronie.",
        )
        return True
    return False


def text_verdict(
        claimed_city: Optional[str],
        latitude: Optional[float],
        longitude: Optional[float],
        title: Optional[str],
        description: Optional[str],
        places: "PlaceFinder",
        verdict: LocationVerdict,
        district_names: Iterable[str] = (),
):
    content = _plain(" ".join(part for part in (title, description) if part))
    if not content:
        return
    phrase = _border_phrase(content, claimed_city, district_names)
    if phrase:
        verdict.add(BORDER_IN_TEXT, f"Opis mówi: „{phrase}”.")
    if latitude and longitude:
        for place, excerpt in places.mentioned_near(content, latitude, longitude, claimed_city):
            verdict.add(OTHER_PLACE_IN_TEXT, f"Opis wymienia miejscowość {place}: „{excerpt}”.")


class PlaceFinder:
    def __init__(self, centres: Iterable[PlaceCentre], radius_m: float = NEARBY_PLACE_RADIUS_M):
        self._radius_m = radius_m
        self._cell_degrees = radius_m / _METRES_PER_DEGREE
        self._cells: dict[tuple[int, int], list[PlaceCentre]] = {}
        self._patterns: dict[str, re.Pattern] = {}
        for centre in centres:
            if len(centre.name) < 4:
                continue
            self._cells.setdefault(self._cell_of(centre.latitude, centre.longitude), []).append(centre)
            self._patterns.setdefault(centre.name, _stem_pattern(centre.name))

    def mentioned_near(
            self, content: str, latitude: float, longitude: float, claimed_city: Optional[str],
    ) -> list[tuple[str, str]]:
        found: dict[str, str] = {}
        claimed = (claimed_city or "").lower()
        for centre in self._nearby(latitude, longitude):
            if centre.name.lower() == claimed or centre.name in found:
                continue
            if claimed_city and _same_place(centre.name, claimed_city):
                continue
            if _distance_m(latitude, longitude, centre.latitude, centre.longitude) > self._radius_m:
                continue
            for match in self._patterns[centre.name].finditer(content):
                if _travel_mention(content, match.start(), match.end()):
                    continue
                found[centre.name] = _excerpt(content, match.start(), match.end())
                break
        return list(found.items())

    def _nearby(self, latitude: float, longitude: float) -> Iterable[PlaceCentre]:
        lat_cell, lon_cell = self._cell_of(latitude, longitude)
        for d_lat in (-1, 0, 1):
            for d_lon in (-2, -1, 0, 1, 2):
                yield from self._cells.get((lat_cell + d_lat, lon_cell + d_lon), ())

    def _cell_of(self, latitude: float, longitude: float) -> tuple[int, int]:
        return int(latitude // self._cell_degrees), int(longitude // self._cell_degrees)


def _border_phrase(content: str, claimed_city: Optional[str], district_names: Iterable[str]) -> Optional[str]:
    districts = {_stem(name) for name in district_names if name}
    for pattern in _BORDER_PHRASES:
        for match in pattern.finditer(content):
            name = match.groupdict().get("name")
            if name and _is_irrelevant_border(match.group(0), name, claimed_city, districts):
                continue
            return match.group(0).strip()
    return None


def _is_irrelevant_border(phrase: str, name: str, claimed_city: Optional[str], districts: set[str]) -> bool:
    if name.startswith(_FOREIGN_BORDERS) or name.lower().startswith("dzielnic"):
        return True
    if _stem(name) in districts:
        return True
    is_gmina = phrase.lower().startswith(("gmin", "gm."))
    return is_gmina and claimed_city is not None and _same_place(name, claimed_city)


def _same_place(first: str, second: str) -> bool:
    return _stem(first)[:5].lower() == _stem(second)[:5].lower()


def _stem(name: str) -> str:
    word = name.split()[-1] if name.split() else name
    return word[:-1] if len(word) >= 5 else word


def lineage_verdict(claimed_city: Optional[str], other_cities: Iterable[str], verdict: LocationVerdict):
    others = sorted({city for city in other_cities if city and city != claimed_city})
    if others:
        verdict.add(
            LINEAGE_CITY_MISMATCH,
            f"Inne ogłoszenia tego samego lokalu podawały miejscowość: {', '.join(others)}.",
        )


def _stem_pattern(name: str) -> re.Pattern:
    words = name.split()
    last = words[-1]
    cut = 1 if len(last) >= 5 else 0
    stem = last[: len(last) - cut]
    prefix = r"\s+".join(re.escape(word) for word in words[:-1])
    body = (prefix + r"\s+" if prefix else "") + re.escape(stem)
    return re.compile(rf"(?<![\wąćęłńóśźż]){body}[\wąćęłńóśźż]{{0,4}}(?![\wąćęłńóśźż])")


def _travel_mention(content: str, start: int, end: int) -> bool:
    return bool(_TRAVEL_BEFORE.search(content[max(0, start - 25):start]) or _TRAVEL_AFTER.match(content[end:end + 40]))


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub(" ", value)).strip()


def _excerpt(content: str, start: int, end: int, margin: int = 50) -> str:
    left = max(content.rfind(" ", 0, max(start - margin, 0)) + 1, 0)
    right = content.find(" ", min(end + margin, len(content)))
    right = len(content) if right == -1 else right
    prefix = "…" if left > 0 else ""
    suffix = "…" if right < len(content) else ""
    return f"{prefix}{content[left:right].strip()}{suffix}"


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    mean_lat = math.radians((lat1 + lat2) / 2)
    return math.hypot((lat2 - lat1) * _METRES_PER_DEGREE, (lon2 - lon1) * _METRES_PER_DEGREE * math.cos(mean_lat))
