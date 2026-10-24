from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, Optional

import requests
from lxml import etree
from psycopg2.extras import execute_values
from sqlalchemy import text
from sqlalchemy.engine import Connection

from .derived_tables import ensure_table
from .models import RcnTransaction

logger = logging.getLogger(__name__)

RCN_WFS_URL = "https://mapy.geoportal.gov.pl/wss/service/rcn"
FLATS_LAYER = "ms:lokale"
PAGE_SIZE = 1000
TILE_M = 2000

_NAMESPACES = {
    "wfs": "http://www.opengis.net/wfs/2.0",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
    "gml": "http://www.opengis.net/gml/3.2",
}

_AREA_BOUNDS = text("""
SELECT floor(ST_XMin(b))::int, floor(ST_YMin(b))::int, ceil(ST_XMax(b))::int, ceil(ST_YMax(b))::int
FROM (
    SELECT ST_Expand(ST_Extent(ST_Transform(geom, 2180)), :margin) AS b
    FROM admin_areas
    WHERE level = 'city' AND city_name = ANY(:cities)
) bounds
""")

_UPSERT = """
INSERT INTO rcn_transactions (
    id, teryt, transaction_date, document, transaction_key, market, transaction_kind, function, share,
    transaction_price, unit_price, area_value, appurtenant_area, rooms, floor, address, location_point, loaded_at
)
SELECT v.id, v.teryt, v.transaction_date, v.document, v.transaction_key, v.market, v.transaction_kind, v.function,
       v.share, v.transaction_price, v.unit_price, v.area_value, v.appurtenant_area, v.rooms, v.floor, v.address,
       ST_Transform(ST_SetSRID(ST_MakePoint(v.easting, v.northing), 2180), 4326), v.loaded_at
FROM (VALUES %s) AS v(
    id, teryt, transaction_date, document, transaction_key, market, transaction_kind, function, share,
    transaction_price, unit_price, area_value, appurtenant_area, rooms, floor, address, easting, northing, loaded_at
)
ON CONFLICT (id) DO UPDATE SET
    transaction_price = EXCLUDED.transaction_price,
    unit_price = EXCLUDED.unit_price,
    area_value = EXCLUDED.area_value,
    loaded_at = EXCLUDED.loaded_at
"""

_VALUE_TEMPLATE = (
    "(%s, %s, %s::timestamp, %s, %s, %s, %s, %s, %s, %s::numeric, %s::numeric, %s::numeric, %s::numeric, "
    "%s::smallint, %s::smallint, %s, %s::float8, %s::float8, %s::timestamp)"
)


@dataclass(frozen=True)
class RcnFlatSale:
    id: int
    teryt: Optional[str]
    transaction_date: datetime
    document: Optional[str]
    transaction_key: Optional[str]
    market: Optional[str]
    transaction_kind: Optional[str]
    function: Optional[str]
    share: Optional[str]
    transaction_price: Optional[float]
    unit_price: Optional[float]
    area_value: Optional[float]
    appurtenant_area: Optional[float]
    rooms: Optional[int]
    floor: Optional[int]
    address: Optional[str]
    easting: float
    northing: float


def parse_flat_sales(document: bytes) -> Iterator[RcnFlatSale]:
    root = etree.fromstring(document)
    for member in root.iterfind("wfs:member", _NAMESPACES):
        feature = member[0]
        position = feature.findtext(".//ms:GEOMETRIA//gml:pos", namespaces=_NAMESPACES)
        date = feature.findtext(".//ms:DOK_DATA//gml:timePosition", namespaces=_NAMESPACES)
        feature_id = feature.get(f"{{{_NAMESPACES['gml']}}}id", "")
        if not position or not date or "." not in feature_id:
            continue
        northing, easting = (float(value) for value in position.split()[:2])
        field = lambda name: (feature.findtext(f"ms:{name}", namespaces=_NAMESPACES) or "").strip() or None
        yield RcnFlatSale(
            id=int(feature_id.rsplit(".", 1)[1]),
            teryt=field("TERYT"),
            transaction_date=datetime.fromisoformat(date[:10]),
            document=field("DOK_OZNACZENIE"),
            transaction_key=field("TRAN_LOKALNY_ID_IIP") or _document_key(field("DOK_OZNACZENIE"), date, field("DOK_TWORCA")),
            market=field("TRAN_RODZAJ_RYNKU"),
            transaction_kind=field("TRAN_RODZAJ_TRANS"),
            function=field("LOK_FUNKCJA"),
            share=field("NIER_UDZIAL"),
            transaction_price=_number(field("TRAN_CENA_BRUTTO")),
            unit_price=_number(field("LOK_CENA_BRUTTO")),
            area_value=_number(field("LOK_POW_UZYT")),
            appurtenant_area=_number(field("LOK_POW_PRZYN")),
            rooms=_integer(field("LOK_LICZBA_IZB")),
            floor=_integer(field("LOK_NR_KOND")),
            address=field("LOK_ADRES"),
            easting=easting,
            northing=northing,
        )


def tiles(bounds: tuple[int, int, int, int], tile_m: int = TILE_M) -> Iterator[tuple[int, int, int, int]]:
    min_x, min_y, max_x, max_y = bounds
    for x in range(min_x, max_x, tile_m):
        for y in range(min_y, max_y, tile_m):
            yield x, y, min(x + tile_m, max_x), min(y + tile_m, max_y)


def iter_tile(tile: tuple[int, int, int, int], session: requests.Session) -> Iterator[RcnFlatSale]:
    min_x, min_y, max_x, max_y = tile
    start = 0
    while True:
        response = session.get(RCN_WFS_URL, params={
            "SERVICE": "WFS",
            "VERSION": "2.0.0",
            "REQUEST": "GetFeature",
            "TYPENAMES": FLATS_LAYER,
            "COUNT": PAGE_SIZE,
            "STARTINDEX": start,
            "BBOX": f"{min_y},{min_x},{max_y},{max_x},urn:ogc:def:crs:EPSG::2180",
        }, timeout=300)
        response.raise_for_status()
        sales = list(parse_flat_sales(response.content))
        yield from sales
        if len(sales) < PAGE_SIZE:
            return
        start += PAGE_SIZE


def load_flat_sales(connection: Connection, cities: list[str], margin_m: int, now: Optional[datetime] = None) -> int:
    now = now or datetime.now()
    ensure_table(connection.engine, RcnTransaction.__table__)
    bounds = connection.execute(_AREA_BOUNDS, {"cities": cities, "margin": margin_m}).one()
    if bounds[0] is None:
        raise ValueError(f"No boundaries loaded for {cities}, run load_boundaries.py first")
    http = requests.Session()
    cursor = connection.connection.cursor()
    loaded = 0
    tile_list = list(tiles(tuple(bounds)))
    for number, tile in enumerate(tile_list, start=1):
        sales = {sale.id: sale for sale in iter_tile(tile, http)}
        if sales:
            execute_values(cursor, _UPSERT, [_row(sale, now) for sale in sales.values()], template=_VALUE_TEMPLATE)
            loaded += len(sales)
        logger.info("RCN tile %d of %d: %d flat sales (%d so far)", number, len(tile_list), len(sales), loaded)
    return loaded


def _row(sale: RcnFlatSale, loaded_at: datetime) -> tuple:
    return (
        sale.id, sale.teryt, sale.transaction_date, sale.document, sale.transaction_key, sale.market,
        sale.transaction_kind, sale.function, sale.share, sale.transaction_price, sale.unit_price, sale.area_value,
        sale.appurtenant_area, sale.rooms, sale.floor, sale.address, sale.easting, sale.northing, loaded_at,
    )


def _document_key(document: Optional[str], date: str, notary: Optional[str]) -> Optional[str]:
    if not document:
        return None
    return f"{document}|{date[:10]}|{notary or ''}"


def _number(value: Optional[str]) -> Optional[float]:
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _integer(value: Optional[str]) -> Optional[int]:
    number = _number(value)
    return int(number) if number is not None and abs(number) < 1000 else None
